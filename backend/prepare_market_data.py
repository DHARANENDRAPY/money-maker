from pathlib import Path
import pandas as pd
import numpy as np

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")

# Chronological splits: never randomly shuffle time-series candles.
TRAIN_RATIO = 0.70
VALIDATION_RATIO = 0.15

IST = "Asia/Kolkata"


def load_candles(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, compression="infer")

    required = {"time", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}")

    # The published dataset uses Unix timestamps in seconds.
    df["datetime"] = pd.to_datetime(
        pd.to_numeric(df["time"], errors="coerce"),
        unit="s", utc=True, errors="coerce"
    ).dt.tz_convert(IST)

    volume_col = next(
        (c for c in df.columns if c.lower() == "volume"), None
    )
    if volume_col is None:
        raise ValueError(f"{path.name}: no volume column")

    df["volume"] = pd.to_numeric(df[volume_col], errors="coerce")

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(
        subset=["datetime", "open", "high", "low", "close", "volume"]
    )
    df = df.set_index("datetime").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # Reject invalid prices and impossible OHLC relationships.
    valid = (
        (df[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (df["high"] >= df[["open", "close", "low"]].max(axis=1))
        & (df["low"] <= df[["open", "close", "high"]].min(axis=1))
        & (df["volume"] >= 0)
    )
    df = df.loc[valid, ["open", "high", "low", "close", "volume"]]

    # NSE regular session only. Retain source timestamps in IST.
    minutes = df.index.hour * 60 + df.index.minute
    df = df.loc[(minutes >= 9 * 60 + 15) & (minutes < 15 * 60 + 30)]

    return df


def resample_ohlcv(df: pd.DataFrame, rule: str,
                   expected_bars: int) -> pd.DataFrame:
    # Align bars to the NSE session open, 09:15 IST.
    grouped = df.resample(
        rule,
        origin="start_day",
        offset="9h15min",
        label="left",
        closed="left"
    )

    out = grouped.agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })

    # Exclude incomplete bars rather than inventing missing candles.
    counts = grouped["close"].count()
    out = out.loc[counts == expected_bars]
    return out.dropna(subset=["open", "high", "low", "close"])


def make_daily(df: pd.DataFrame) -> pd.DataFrame:
    # Aggregate only observed session candles.
    daily = df.groupby(df.index.date).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    daily.index = pd.to_datetime(daily.index).tz_localize(IST)
    daily.index.name = "datetime"
    return daily.dropna()


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    close = x["close"]
    high, low = x["high"], x["low"]

    x["return_1"] = close.pct_change()
    x["return_5"] = close.pct_change(5)
    x["sma_10"] = close.rolling(10).mean()
    x["sma_20"] = close.rolling(20).mean()
    x["ema_9"] = close.ewm(span=9, adjust=False).mean()
    x["ema_21"] = close.ewm(span=21, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    x["rsi_14"] = 100 - (100 / (1 + rs))

    prev_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    x["atr_14"] = true_range.rolling(14).mean()

    volume_mean = x["volume"].rolling(20).mean()
    x["volume_ratio_20"] = x["volume"] / volume_mean.replace(0, np.nan)

    # Research target only; not a guaranteed prediction.
    # The final 5 future bars are unavailable at the dataset's end.
    x["future_return_5"] = close.shift(-5) / close - 1

    return x.replace([np.inf, -np.inf], np.nan)


def save_chronological_splits(df: pd.DataFrame, folder: Path):
    # Remove rows without enough indicator history or a known target.
    # For production inference, retain the latest rows separately.
    ready = df.dropna()
    if len(ready) < 100:
        return

    n = len(ready)
    train_end = int(n * TRAIN_RATIO)
    val_end = int(n * (TRAIN_RATIO + VALIDATION_RATIO))

    ready.iloc[:train_end].to_csv(folder / "train.csv")
    ready.iloc[train_end:val_end].to_csv(folder / "validation.csv")
    ready.iloc[val_end:].to_csv(folder / "test.csv")


def process_file(path: Path) -> dict:
    symbol = path.name.replace("_1m.csv.gz", "").replace(".csv.gz", "")
    folder = OUT_DIR / symbol
    folder.mkdir(parents=True, exist_ok=True)

    one_min = load_candles(path)
    if one_min.empty:
        raise ValueError("No valid session candles found")

    five_min = resample_ohlcv(one_min, "5min", 5)
    fifteen_min = resample_ohlcv(one_min, "15min", 15)
    daily = make_daily(one_min)

    one_min.to_csv(folder / "1m.csv")
    five_min.to_csv(folder / "5m.csv")
    fifteen_min.to_csv(folder / "15m.csv")
    daily.to_csv(folder / "1d.csv")

    # Indicators and labels are for research, not automatic trade execution.
    intraday_features = add_features(five_min)
    daily_features = add_features(daily)

    intraday_features.to_csv(folder / "5m_features.csv")
    daily_features.to_csv(folder / "1d_features.csv")

    split_dir = folder / "splits"
    split_dir.mkdir(exist_ok=True)
    save_chronological_splits(intraday_features, split_dir / "unused") \
        if False else None

    # Save intraday research splits.
    save_chronological_splits(
        intraday_features, split_dir
    )

    return {
        "symbol": symbol,
        "source_file": path.name,
        "first_candle": str(one_min.index.min()),
        "last_candle": str(one_min.index.max()),
        "one_minute_rows": len(one_min),
        "five_minute_rows": len(five_min),
        "fifteen_minute_rows": len(fifteen_min),
        "daily_rows": len(daily),
        "status": "OK",
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.rglob("*.csv.gz"))

    if not files:
        raise SystemExit(
            f"No .csv.gz files found under {RAW_DIR.resolve()}. "
            "Download and extract the dataset first."
        )

    reports = []
    for path in files:
        try:
            report = process_file(path)
            reports.append(report)
            print(
                f"OK {report['symbol']}: "
                f"{report['five_minute_rows']} five-minute candles"
            )
        except Exception as exc:
            reports.append({
                "symbol": path.stem,
                "source_file": path.name,
                "status": "ERROR",
                "error": str(exc),
            })
            print(f"ERROR {path.name}: {exc}")

    pd.DataFrame(reports).to_csv(
        OUT_DIR / "data_quality_report.csv", index=False
    )
    print(f"\nFinished. Report: {OUT_DIR / 'data_quality_report.csv'}")


if __name__ == "__main__":
    main()
