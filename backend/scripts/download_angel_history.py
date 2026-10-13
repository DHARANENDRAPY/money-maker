"""
download_angel_history.py

Downloads 3-5 years of historical daily data from Angel One SmartAPI.
Features:
- Incremental downloading
- Chunking requests to respect API limits (usually ~100 days per request)
- Backoff and retry on failures
- Writes to data/daily/{SYMBOL}.csv
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import requests

sys.path.insert(0, str(Path.cwd()))
from app.providers.angel_one_provider import AngelOneSmartAPIProvider
from app.providers.universe import NSE_UNIVERSE
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("download_history")

OUT_DIR = Path("data/daily")

def setup_provider():
    provider = AngelOneSmartAPIProvider(
        api_key=settings.ANGEL_API_KEY,
        client_code=settings.ANGEL_CLIENT_CODE,
        pin=settings.ANGEL_PIN,
        totp_secret=settings.ANGEL_TOTP_SECRET
    )
    if not provider.api_key or not provider.client_code:
        logger.error("Missing Angel One credentials in .env")
        sys.exit(1)
        
    auth_res = provider.authenticate()
    if not auth_res.get("success"):
        logger.error(f"Authentication failed: {auth_res.get('error')}")
        sys.exit(1)
        
    return provider


def fetch_chunk(provider, token: str, interval: str, from_date: str, to_date: str) -> list:
    url = f"{provider.BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData"
    payload = {
        "exchange": "NSE",
        "symboltoken": token,
        "interval": interval,
        "fromdate": from_date,
        "todate": to_date,
    }
    
    retries = 3
    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=provider._get_headers(), json=payload, timeout=10)
            data = resp.json()
            if not data.get("status"):
                err = data.get("message", "unknown error")
                if "AB8051" in err or "limit" in err.lower() or "too many" in err.lower():
                    logger.warning(f"Rate limit hit. Waiting 5s... (Attempt {attempt+1})")
                    time.sleep(5)
                    continue
                else:
                    logger.warning(f"API Error: {err}")
                    return []
            
            return data.get("data", [])
            
        except Exception as e:
            logger.warning(f"Request error: {e}. Retrying...")
            time.sleep(2)
            
    return []


def download_symbol(provider, symbol: str, token: str, years: int = 4):
    out_file = OUT_DIR / f"{symbol}.csv"
    
    # Calculate target start date (e.g. 4 years ago)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    
    existing_df = None
    if out_file.exists():
        try:
            existing_df = pd.read_csv(out_file, index_col="datetime", parse_dates=True)
            if not existing_df.empty:
                # Resume from the last available date
                last_date = existing_df.index.max().replace(tzinfo=None)
                if last_date >= end_date - timedelta(days=2):
                    logger.info(f"[{symbol}] Data is up-to-date. Skipping.")
                    return
                # Update start date to fetch only missing data
                start_date = last_date + timedelta(days=1)
                logger.info(f"[{symbol}] Resuming download from {start_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            logger.warning(f"[{symbol}] Failed to read existing file: {e}")
            existing_df = None

    if start_date >= end_date:
        return

    # Angel One limit is ~100 days for ONE_DAY per request
    chunk_size = 90
    current_date = start_date
    
    all_raw = []
    
    logger.info(f"[{symbol}] Fetching {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    while current_date < end_date:
        next_date = min(current_date + timedelta(days=chunk_size), end_date)
        
        f_str = current_date.strftime("%Y-%m-%d %H:%M")
        t_str = next_date.strftime("%Y-%m-%d %H:%M")
        
        raw = fetch_chunk(provider, token, "ONE_DAY", f_str, t_str)
        if raw:
            all_raw.extend(raw)
            
        current_date = next_date
        # Sleep to respect rate limits (3 requests per second limit globally)
        time.sleep(0.4)

    if not all_raw:
        logger.warning(f"[{symbol}] No new data found.")
        return

    df = pd.DataFrame(all_raw, columns=["datetime", "open", "high", "low", "close", "volume"])
    dt = pd.to_datetime(df["datetime"])
    if dt.dt.tz is None:
        df["datetime"] = dt.dt.tz_localize("Asia/Kolkata")
    else:
        df["datetime"] = dt.dt.tz_convert("Asia/Kolkata")
    df.set_index("datetime", inplace=True)
    
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float).round(2)
    df["volume"] = df["volume"].astype(int)
    
    if existing_df is not None:
        combined = pd.concat([existing_df, df])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = df.sort_index()
        
    combined.to_csv(out_file)
    logger.info(f"[{symbol}] Saved {len(combined)} daily candles.")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Needs to be called from the backend directory to resolve imports
    if "backend" not in str(Path.cwd()):
        logger.error("Please run this script from the backend directory.")
        sys.exit(1)
        
    provider = setup_provider()
    
    # Always include Nifty 50 index for regime features
    EXTRA_INDICES = [
        {"symbol": "NIFTY50", "token": "99926000"},
        {"symbol": "BANKNIFTY", "token": "99926009"},
    ]
    for idx in EXTRA_INDICES:
        logger.info(f"--- Downloading index: {idx['symbol']} ---")
        download_symbol(provider, idx["symbol"], idx["token"], years=4)

    symbols = list(NSE_UNIVERSE.keys())
    total = len(symbols)
    
    for i, sym in enumerate(symbols):
        logger.info(f"--- Processing {i+1}/{total}: {sym} ---")
        token = NSE_UNIVERSE[sym]["token"]
        download_symbol(provider, sym, token, years=4)
        
    logger.info("Daily history download complete.")


if __name__ == "__main__":
    main()
