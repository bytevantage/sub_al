import json
from datetime import datetime
from pathlib import Path

DATE = "2025-11-19"
DATA_FILE = Path(f"data/historical/{DATE}_db.json")

if not DATA_FILE.exists():
    raise SystemExit(f"Snapshot file not found: {DATA_FILE}")

with DATA_FILE.open() as f:
    raw = json.load(f)

entries = sorted(raw.items(), key=lambda kv: kv[0])

capital = 100000.0
portfolio = []
results = []
last_state = {}

for ts_str, bucket in entries:
    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    nifty = bucket.get("NIFTY")
    if not nifty:
        continue
    spot = nifty.get("spot_price")
    option_chain = nifty.get("option_chain", {})

    total_vol = 0
    for leg in option_chain.get("calls", {}).values():
        total_vol += leg.get("volume", 0)
    for leg in option_chain.get("puts", {}).values():
        total_vol += leg.get("volume", 0)

    if not spot or total_vol == 0:
        continue

    prev = last_state.get("NIFTY")
    last_state["NIFTY"] = {"spot": spot, "volume": total_vol, "timestamp": ts}

    # close positions (exit next snapshot)
    for pos in portfolio[:]:
        exit_price = spot * (1.015 if pos["direction"] == "CALL" else 0.985)
        pnl = (exit_price - pos["entry"]) * pos["quantity"] * (1 if pos["direction"] == "CALL" else -1)
        capital += exit_price * pos["quantity"] + pnl
        pos.update({"exit": exit_price, "pnl": pnl, "exit_time": ts_str})
        portfolio.remove(pos)
        results.append(pos)

    if not prev:
        continue

    price_change_pct = ((spot - prev["spot"]) / prev["spot"]) * 100
    volume_ratio = total_vol / (prev["volume"] or 1)

    if abs(price_change_pct) < 0.35 or volume_ratio < 1.4:
        continue

    entry_price = spot * 0.01
    quantity = max(1, int((capital * 0.005) / entry_price))
    capital -= entry_price * quantity

    trade = {
        "time": ts_str,
        "direction": "CALL" if price_change_pct > 0 else "PUT",
        "entry": entry_price,
        "quantity": quantity,
        "price_spike": price_change_pct,
        "volume_ratio": volume_ratio,
    }
    portfolio.append(trade)

# Close leftover positions at last price
if portfolio and entries:
    last_ts, last_bucket = entries[-1]
    spot = last_bucket["NIFTY"].get("spot_price")
    for pos in portfolio:
        exit_price = spot * (1.01 if pos["direction"] == "CALL" else 0.99)
        pnl = (exit_price - pos["entry"]) * pos["quantity"] * (1 if pos["direction"] == "CALL" else -1)
        capital += exit_price * pos["quantity"] + pnl
        pos.update({"exit": exit_price, "pnl": pnl, "exit_time": last_ts})
        results.append(pos)

initial_capital = 100000.0

print(f"Trades: {len(results)}")
print(f"Final Capital: ₹{capital:,.2f}")
print(f"Total P&L: ₹{capital-initial_capital:,.2f} ({(capital-initial_capital)/initial_capital*100:.2f}%)")
if results:
    win_rate = sum(1 for r in results if r['pnl'] > 0) / len(results) * 100
    print(f"Win Rate: {win_rate:.1f}%")

    print("\nSample Trades:")
    for row in results[:10]:
        print(row)
