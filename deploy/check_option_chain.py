#!/usr/bin/env python3
"""
Simple verification script: print latest OptionSnapshot rows (option chain + greeks)
Run from repo root after activating virtualenv:
  . venv/bin/activate && python3 deploy/check_option_chain.py
"""
import os
from datetime import datetime
from backend.database.database import db as database
from backend.database.models import OptionSnapshot

# load .env if present
from dotenv import load_dotenv
load_dotenv()


def sample_latest(n=10):
    session = database.get_session()
    try:
        rows = session.query(OptionSnapshot).order_by(OptionSnapshot.timestamp.desc()).limit(n).all()
        if not rows:
            print("No OptionSnapshot rows found — check that option chain ingestion is running and DB credentials are correct.")
            return
        for r in rows:
            print(f"{r.timestamp} | {r.symbol} {r.option_type} {r.strike_price} | LTP={r.ltp} OI={r.oi} IV={r.iv} Δ={r.delta} Γ={r.gamma} Θ={r.theta} ν={r.vega}")
    finally:
        session.close()


if __name__ == '__main__':
    print("Querying latest option snapshot rows:")
    sample_latest(20)
