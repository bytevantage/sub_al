"""Export option-chain snapshots with Greeks into per-minute market data JSON."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, Any

from zoneinfo import ZoneInfo

from backend.database.database import db
from backend.database.models import OptionChainSnapshot
from backend.core.logger import logger

IST = ZoneInfo("Asia/Kolkata")


def bucket_timestamp(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(IST).replace(second=0, microsecond=0)


def build_symbol_snapshot(existing: Dict[str, Any], snap: OptionChainSnapshot) -> Dict[str, Any]:
    snapshot = existing or {
        "symbol": snap.symbol,
        "spot_price": snap.spot_price,
        "atm_strike": round(snap.spot_price or snap.strike_price, -2) if snap.spot_price else snap.strike_price,
        "option_chain": {"calls": {}, "puts": {}},
        "multi_timeframe": {},
    }

    leg = "calls" if snap.option_type.upper() == "CALL" else "puts"
    chain_entry = {
        "strike": snap.strike_price,
        "ltp": snap.ltp,
        "bid": snap.bid,
        "ask": snap.ask,
        "volume": snap.volume,
        "oi": snap.oi,
        "oi_change": snap.oi_change,
        "delta": snap.delta,
        "gamma": snap.gamma,
        "theta": snap.theta,
        "vega": snap.vega,
        "iv": snap.iv,
        "expiry": snap.expiry.isoformat() if isinstance(snap.expiry, datetime) else snap.expiry,
    }

    snapshot["option_chain"].setdefault(leg, {})[str(int(snap.strike_price))] = chain_entry
    snapshot["spot_price"] = snap.spot_price or snapshot["spot_price"]

    return snapshot


def enrich_summary(symbol_data: Dict[str, Any]) -> None:
    option_chain = symbol_data.get("option_chain", {})
    calls = option_chain.get("calls", {})
    puts = option_chain.get("puts", {})

    total_call_oi = sum(entry.get("oi", 0) for entry in calls.values())
    total_put_oi = sum(entry.get("oi", 0) for entry in puts.values())
    total_call_oi_change = sum(entry.get("oi_change", 0) for entry in calls.values())
    total_put_oi_change = sum(entry.get("oi_change", 0) for entry in puts.values())

    option_chain["total_call_oi"] = total_call_oi
    option_chain["total_put_oi"] = total_put_oi
    option_chain["total_call_oi_change"] = total_call_oi_change
    option_chain["total_put_oi_change"] = total_put_oi_change

    option_chain["call_oi_change_pct"] = (total_call_oi_change / total_call_oi * 100) if total_call_oi else 0
    option_chain["put_oi_change_pct"] = (total_put_oi_change / total_put_oi * 100) if total_put_oi else 0
    option_chain["pcr"] = (total_put_oi / total_call_oi) if total_call_oi else 0


def export_snapshots_for_day(target_date: datetime) -> Path:
    session = db.get_session()
    start_ist = datetime.combine(target_date.date(), time(0, 0), tzinfo=IST)
    end_ist = start_ist + timedelta(days=1)

    start_utc = start_ist.astimezone(ZoneInfo("UTC"))
    end_utc = end_ist.astimezone(ZoneInfo("UTC"))

    logger.info(f"Exporting option chain snapshots between {start_ist} and {end_ist} IST")

    snapshots = (
        session.query(OptionChainSnapshot)
        .filter(OptionChainSnapshot.timestamp >= start_utc.replace(tzinfo=None))
        .filter(OptionChainSnapshot.timestamp < end_utc.replace(tzinfo=None))
        .order_by(OptionChainSnapshot.timestamp)
        .all()
    )

    aggregated: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    for snap in snapshots:
        bucket = bucket_timestamp(snap.timestamp)
        bucket_key = bucket.isoformat()
        symbol_map = aggregated[bucket_key]
        symbol_map[snap.symbol] = build_symbol_snapshot(symbol_map.get(snap.symbol), snap)

    # Enrich aggregates and serialize
    for bucket in aggregated.values():
        for symbol_snapshot in bucket.values():
            enrich_summary(symbol_snapshot)

    output_dir = Path("data/historical")
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"{target_date.date()}_db.json"

    with filename.open("w") as f:
        json.dump(aggregated, f, default=str)

    logger.info(f"Exported {len(aggregated)} minute buckets to {filename}")
    session.close()
    return filename


if __name__ == "__main__":
    target = datetime.now(IST)
    export_snapshots_for_day(target)
