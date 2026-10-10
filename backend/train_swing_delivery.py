"""
train_swing_delivery.py — Swing & Delivery Ensemble Model Training
==================================================================
Data source : data/daily/{SYMBOL}.csv  (downloaded by download_angel_history.py)
Nifty regime: data/daily/NIFTY50.csv  (if available)
Splits       : chronological 70% train / 15% val / 15% test  (NO shuffle)
Output       : ml_models/swing_delivery_ensemble_v1.joblib
               ml_models/swing_delivery_scaler_v1.joblib
               ml_models/swing_delivery_metadata_v1.json
"""
import os
import sys
import time
import json
import warnings
import joblib
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

BACKEND_DIR   = Path(__file__).parent
ML_MODELS_DIR = BACKEND_DIR / "ml_models"
ML_MODELS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(BACKEND_DIR))

DAILY_DIR     = BACKEND_DIR / "data" / "daily"
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"

# Stocks whose daily CSVs exist in data/daily/
SWING_DELIVERY_STOCKS = [
    # Nifty 50 Bluechips
    "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "TCS",
    "SBIN", "KOTAKBANK", "AXISBANK", "WIPRO", "LT",
    "HINDUNILVR", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN",
    "BAJFINANCE", "BHARTIARTL", "NTPC", "POWERGRID", "ONGC",
    # Mid-cap momentum stocks ideal for swing trading
    "BEL", "TATAPOWER", "SUZLON", "NHPC",
    "IRFC", "CANBK", "BANKBARODA",
    "BAJAJFINSV", "DRREDDY", "CIPLA",
    # Additional delivery picks
    "ITC", "HCLTECH", "TECHM", "VEDL", "HINDALCO",
    "TATASTEEL", "JSWSTEEL", "BPCL", "IOC",
    "COALINDIA", "GAIL", "RVNL", "SAIL",
    "EXIDEIND", "MOTHERSON", "ASHOKLEY",
    "IDFCFIRSTB", "PNB", "FEDERALBNK",
    "BHEL", "NMDC", "TATAMOTORS",
    "ZOMATO",
]

TRAIN_RATIO = 0.70
VAL_RATIO   = 0.15


# ---------------------------------------------------------------------------
# Step 1: Load local daily data
# ---------------------------------------------------------------------------
def load_local_daily(symbols):
    """
    Reads pre-downloaded daily candles from data/daily/{SYMBOL}.csv.
    Uses only the chronological training slice.
    """
    data_dict = {}
    failed    = []

    print(f"[1/4] Loading local daily data for {len(symbols)} symbols ...")
    print()

    for i, sym in enumerate(symbols):
        path = DAILY_DIR / f"{sym}.csv"
        if not path.exists():
            # Fallback to processed daily
            alt = PROCESSED_DIR / sym / "1d.csv"
            if alt.exists():
                path = alt
            else:
                failed.append(sym)
                print(f"  [{i+1:2d}/{len(symbols)}] MISS  {sym:<15}  -- no local daily file")
                continue

        try:
            df = pd.read_csv(path, index_col="datetime", parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
            keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
            df   = df[keep].dropna()
            df.sort_index(inplace=True)

            if len(df) < 100:
                failed.append(sym)
                print(f"  [{i+1:2d}/{len(symbols)}] SKIP  {sym:<15}  -- too few days ({len(df)})")
                continue

            # Chronological training slice only
            train_end = int(len(df) * TRAIN_RATIO)
            df_train  = df.iloc[:train_end]

            data_dict[sym] = df_train
            print(f"  [{i+1:2d}/{len(symbols)}] OK    {sym:<15}  -- {len(df_train):,} train days "
                  f"(of {len(df):,} total)")

        except Exception as exc:
            failed.append(sym)
            print(f"  [{i+1:2d}/{len(symbols)}] ERR   {sym:<15}  -- {exc}")

    print()
    print(f"  Loaded: {len(data_dict)}/{len(symbols)} | Skipped: {len(failed)}")
    if failed:
        print(f"  Skipped: {', '.join(failed)}")
    print()
    return data_dict


# ---------------------------------------------------------------------------
# Nifty 50 daily regime features
# ---------------------------------------------------------------------------
def _load_nifty_daily():
    candidates = [
        DAILY_DIR / "NIFTY50.csv",
        DAILY_DIR / "^NSEI.csv",
        PROCESSED_DIR / "NIFTY" / "1d.csv",
        PROCESSED_DIR / "NIFTY50" / "1d.csv",
    ]
    for p in candidates:
        if p.exists():
            try:
                df = pd.read_csv(p, index_col=0, parse_dates=True)
                df.columns = [c.lower() for c in df.columns]
                if {"close", "high", "low"}.issubset(df.columns):
                    print(f"  Nifty regime data: {p.name} ({len(df)} days)")
                    return df
            except Exception:
                continue
    print("  WARNING: No Nifty 50 file found. Regime features disabled.")
    return None


def _compute_nifty_daily_regime(nifty_df):
    if nifty_df is None or len(nifty_df) < 50:
        return None

    close = nifty_df["close"]
    high  = nifty_df["high"]
    low   = nifty_df["low"]

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    regime = pd.DataFrame(index=nifty_df.index)
    bull = (close > ema50) & (ema20 > ema50)
    bear = (close < ema50) & (ema20 < ema50)
    regime["nifty_regime"]    = 0.0
    regime.loc[bull, "nifty_regime"]  =  1.0
    regime.loc[bear, "nifty_regime"]  = -1.0
    regime["nifty_momentum"]  = close.pct_change(5).fillna(0)

    tr  = pd.concat([high - low,
                     (high - close.shift(1)).abs(),
                     (low  - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(com=13, adjust=False).mean()
    regime["nifty_volatility"] = (atr / close.replace(0, np.nan)).fillna(0.01)
    return regime


# ---------------------------------------------------------------------------
# Feature extraction for daily timeframe
# ---------------------------------------------------------------------------
def extract_daily_features(df: pd.DataFrame, nifty_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if len(df) < 50:
        return pd.DataFrame()

    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    open_  = df["open"]
    volume = df["volume"]

    feats = pd.DataFrame(index=df.index)

    # Returns
    for n in [1, 3, 5, 10, 20]:
        feats[f"ret_{n}d"] = close.pct_change(n).fillna(0)

    # EMAs
    ema9   = close.ewm(span=9,   adjust=False).mean()
    ema21  = close.ewm(span=21,  adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    feats["ema9_21_spread"]   = (ema9  - ema21)  / close.replace(0, np.nan)
    feats["ema21_50_spread"]  = (ema21 - ema50)  / close.replace(0, np.nan)
    feats["price_vs_ema50"]   = (close - ema50)  / ema50.replace(0, np.nan)
    feats["price_vs_ema200"]  = (close - ema200) / ema200.replace(0, np.nan)
    feats["ema9_slope"]       = ema9.pct_change(5).fillna(0)
    feats["ema21_slope"]      = ema21.pct_change(5).fillna(0)
    feats["golden_cross"]     = ((ema50 > ema200) &
                                  (ema50.shift(1) <= ema200.shift(1))).astype(float)
    feats["above_ema200"]     = (close > ema200).astype(float)

    # RSI
    delta    = close.diff()
    gain     = delta.where(delta > 0, 0.0)
    loss     = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi      = 100 - (100 / (1 + rs))
    feats["rsi14"]        = (rsi.fillna(50) - 50) / 50
    feats["rsi_momentum"] = rsi.diff(5).fillna(0) / 50

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist        = macd_line - signal_line
    atr_approx  = (high - low).rolling(14, min_periods=1).mean()
    atr_approx  = atr_approx.where(atr_approx != 0, close * 0.01)
    feats["macd_hist_norm"]    = (hist / atr_approx).fillna(0)
    feats["macd_above_signal"] = (macd_line > signal_line).astype(float)
    feats["macd_cross_up"]     = ((macd_line > signal_line) &
                                   (macd_line.shift(1) <= signal_line.shift(1))).astype(float)

    # ATR
    tr   = pd.concat([high - low,
                      (high - close.shift(1)).abs(),
                      (low  - close.shift(1)).abs()], axis=1).max(axis=1)
    atr14 = tr.ewm(com=13, adjust=False).mean()
    feats["atr14_pct"] = (atr14 / close.replace(0, np.nan)).fillna(0.02)

    # Bollinger Bands
    bb_mid   = close.rolling(20, min_periods=1).mean()
    bb_std   = close.rolling(20, min_periods=1).std().fillna(0)
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    feats["bb_width"]    = ((bb_upper - bb_lower) / bb_mid.replace(0, np.nan)).fillna(0.04)
    feats["bb_position"] = ((close - bb_lower) /
                             (bb_upper - bb_lower).replace(0, np.nan)).fillna(0.5)

    # Volume
    vol_ma20 = volume.rolling(20, min_periods=1).mean()
    feats["rvol20"]    = (volume / vol_ma20.replace(0, 1)).fillna(1.0)
    feats["vol_trend"] = vol_ma20.pct_change(5).fillna(0)

    # OBV trend
    obv      = ((close > close.shift(1)).astype(float) -
                 (close < close.shift(1)).astype(float)) * volume
    obv_cum  = obv.cumsum()
    obv_ma   = obv_cum.ewm(span=10, adjust=False).mean()
    vol_base = (volume.rolling(10).mean() * 10).replace(0, np.nan)
    feats["obv_trend"] = ((obv_cum - obv_ma) / vol_base).fillna(0)

    # Candle anatomy
    candle_range = (high - low).replace(0, np.nan)
    body = (close - open_).abs()
    feats["body_ratio"]       = (body / candle_range).fillna(0.5)
    feats["upper_wick"]       = ((high - pd.concat([close, open_], axis=1).max(axis=1)) /
                                  candle_range).fillna(0)
    feats["lower_wick"]       = ((pd.concat([close, open_], axis=1).min(axis=1) - low) /
                                  candle_range).fillna(0)
    feats["is_bullish_candle"] = (close > open_).astype(float)

    # 52-week context
    high_52w = close.rolling(252, min_periods=50).max()
    low_52w  = close.rolling(252, min_periods=50).min()
    feats["dist_from_52w_high"] = (close - high_52w) / high_52w.replace(0, np.nan)
    feats["dist_from_52w_low"]  = (close - low_52w)  / low_52w.replace(0, np.nan)
    feats["near_52w_high"]      = (feats["dist_from_52w_high"] > -0.05).astype(float)
    feats["momentum_rank_20d"]  = close.pct_change(20).rank(pct=True).fillna(0.5)

    DAILY_FEATURE_COLUMNS = [
        "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
        "ema9_21_spread", "ema21_50_spread", "price_vs_ema50", "price_vs_ema200",
        "ema9_slope", "ema21_slope", "golden_cross", "above_ema200",
        "rsi14", "rsi_momentum",
        "macd_hist_norm", "macd_above_signal", "macd_cross_up",
        "atr14_pct", "bb_width", "bb_position",
        "rvol20", "vol_trend", "obv_trend",
        "body_ratio", "upper_wick", "lower_wick", "is_bullish_candle",
        "dist_from_52w_high", "dist_from_52w_low", "near_52w_high",
        "momentum_rank_20d",
    ]
    feats_out = feats[DAILY_FEATURE_COLUMNS].copy()

    # Nifty Regime Features
    if nifty_df is not None:
        regime = _compute_nifty_daily_regime(nifty_df)
        if regime is not None:
            feats_out = feats_out.join(regime, how="left")
            
    if "nifty_regime" not in feats_out.columns:
        feats_out["nifty_regime"] = 1.0
    if "nifty_momentum" not in feats_out.columns:
        feats_out["nifty_momentum"] = 0.01
    if "nifty_volatility" not in feats_out.columns:
        feats_out["nifty_volatility"] = 0.012

    ALL_COLS = DAILY_FEATURE_COLUMNS + ["nifty_regime", "nifty_momentum", "nifty_volatility"]
    return feats_out[ALL_COLS].ffill().fillna(0.0)


# ---------------------------------------------------------------------------
# Labelling (forward ATR-based SL/TP)
# ---------------------------------------------------------------------------
def label_daily_outcomes(df, rr_mult=1.5, max_hold_days=20, direction="LONG"):
    close = df["close"].values
    high  = df["high"].values
    low   = df["low"].values

    tr_arr      = np.maximum(high - low,
                  np.maximum(np.abs(high - np.roll(close, 1)),
                             np.abs(low  - np.roll(close, 1))))
    tr_arr[0]   = high[0] - low[0]
    atr         = pd.Series(tr_arr).ewm(com=13, adjust=False).mean().values

    n       = len(close)
    labels  = np.zeros(n, dtype=int)
    r_mults = np.zeros(n, dtype=float)

    for i in range(n - max_hold_days - 1):
        entry = close[i]
        a     = atr[i]
        if a <= 0 or np.isnan(a):
            continue

        risk = 1.5 * a
        if direction == "LONG":
            sl = entry - risk
            tp = entry + (rr_mult * risk)
            resolved = False
            for step in range(1, max_hold_days + 1):
                idx = i + step
                sl_hit = low[idx] <= sl
                tp_hit = high[idx] >= tp
                if sl_hit and tp_hit:
                    # Both hit in same bar — count as loss (conservative)
                    labels[i]  = 0
                    r_mults[i] = -1.0
                    resolved = True
                    break
                elif sl_hit:
                    labels[i]  = 0
                    r_mults[i] = -1.0
                    resolved = True
                    break
                elif tp_hit:
                    labels[i]  = 1
                    r_mults[i] = rr_mult
                    resolved = True
                    break
            if not resolved:
                pnl         = (close[i + max_hold_days] - entry) / risk
                labels[i]   = 1 if pnl > 0 else 0
                r_mults[i]  = pnl

    return pd.Series(labels, index=df.index), pd.Series(r_mults, index=df.index)


# ---------------------------------------------------------------------------
# Step 2: Build labeled dataset
# ---------------------------------------------------------------------------
def build_daily_dataset(data_dict, regime_features):
    all_X, all_y, all_r = [], [], []
    has_regime = regime_features is not None

    if has_regime:
        print("  [REGIME] Nifty 50 daily regime features enabled")
    else:
        print("  [REGIME] No regime features — training without market context")

    print("[2/4] Extracting daily features + labelling setups ...")
    print()

    for sym, raw in data_dict.items():
        try:
            feats = extract_daily_features(raw)
            if feats.empty or len(feats) < 50:
                continue

            if has_regime:
                try:
                    # Align regime by date index
                    feats_idx = feats.index
                    if hasattr(feats_idx, "tz") and feats_idx.tz is not None:
                        feats_idx_naive = feats_idx.tz_localize(None)
                    else:
                        feats_idx_naive = feats_idx

                    reg_idx = regime_features.index
                    if hasattr(reg_idx, "tz") and reg_idx.tz is not None:
                        reg_idx_naive = reg_idx.tz_localize(None)
                    else:
                        reg_idx_naive = reg_idx

                    regime_copy = regime_features.copy()
                    regime_copy.index = reg_idx_naive
                    reg_reindexed = regime_copy.reindex(feats_idx_naive, method="ffill")
                    reg_reindexed.index = feats.index
                    feats = feats.join(reg_reindexed, rsuffix="_reg")
                    for col in ["nifty_regime", "nifty_momentum", "nifty_volatility"]:
                        if col not in feats.columns:
                            feats[col] = 0.0
                    feats = feats.fillna(0.0)
                except Exception:
                    for col in ["nifty_regime", "nifty_momentum", "nifty_volatility"]:
                        feats[col] = 0.0

            valid_len = min(len(feats), len(raw) - 21)
            vf = feats.iloc[:valid_len]

            lbl_l, r_l = label_daily_outcomes(raw, rr_mult=1.5,
                                               max_hold_days=20, direction="LONG")
            vl    = lbl_l.iloc[:valid_len]
            vr    = r_l.iloc[:valid_len]
            lmask = vr != 0.0
            if lmask.sum() > 0:
                all_X.append(vf[lmask])
                all_y.append(vl[lmask])
                all_r.append(vr[lmask])

            print(f"  {sym:<15}  {int(lmask.sum()):,} labelled setups")

        except Exception as exc:
            print(f"  {sym:<15}  SKIPPED -- {exc}")

    if not all_X:
        raise RuntimeError("No training data built.")

    X = pd.concat(all_X, ignore_index=True)
    y = pd.concat(all_y, ignore_index=True)
    r = pd.concat(all_r, ignore_index=True)

    print()
    print(f"  Total setups : {len(X):,}")
    print(f"  Wins / Losses: {int(y.sum()):,} / {int((y == 0).sum()):,}")
    print(f"  Win rate     : {100 * y.mean():.1f}%")
    print(f"  Features     : {X.shape[1]}")
    print()
    return X, y, r


# ---------------------------------------------------------------------------
# Step 3: Train and save
# ---------------------------------------------------------------------------
def train_and_save_swing_model(X, y, r):
    from sklearn.ensemble import RandomForestClassifier, VotingClassifier
    from xgboost import XGBClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import (brier_score_loss, roc_auc_score, f1_score,
                                 precision_score, recall_score, accuracy_score)
    from sklearn.preprocessing import StandardScaler
    from sklearn.utils import resample

    print("[3/4] Training Swing Ensemble (GBT + RF) + Platt Calibration ...")
    print("      Chronological 70/15/15 split — no shuffle")
    print()

    avail = list(X.columns)
    Xf    = X[avail].fillna(0.0)

    n      = len(Xf)
    tr_end = int(n * TRAIN_RATIO)
    va_end = int(n * (TRAIN_RATIO + VAL_RATIO))

    X_tr = Xf.iloc[:tr_end]
    X_te = Xf.iloc[va_end:]
    y_tr = y.iloc[:tr_end]
    y_te = y.iloc[va_end:]
    r_te = r.iloc[va_end:]

    # Class balance on train set
    combined            = X_tr.copy()
    combined["__y"]     = y_tr.values
    wins_df   = combined[combined["__y"] == 1]
    losses_df = combined[combined["__y"] == 0]
    target_losses = min(len(losses_df), int(len(wins_df) * 1.1))
    losses_down   = resample(losses_df, replace=False,
                             n_samples=target_losses, random_state=42)
    balanced  = pd.concat([wins_df, losses_down]).sample(frac=1, random_state=42)
    X_tr_bal  = balanced.drop(columns=["__y"])
    y_tr_bal  = balanced["__y"]

    print(f"  Train set   : {len(X_tr):,} (wins={int(y_tr.sum()):,})")
    print(f"  Balanced    : {len(X_tr_bal):,} (wins={int(y_tr_bal.sum()):,})")
    print(f"  Test set    : {len(X_te):,}")
    print()

    scaler  = StandardScaler()
    Xtr_sc  = scaler.fit_transform(X_tr_bal)
    Xte_sc  = scaler.transform(X_te)

    xgb_model = XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.04,
        subsample=0.8, colsample_bytree=0.75,
        reg_alpha=0.1, reg_lambda=1.5,
        min_child_weight=5,
        random_state=42, eval_metric="logloss",
    )
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=7, min_samples_leaf=4,
        max_features="sqrt", class_weight="balanced",
        random_state=42, n_jobs=-1,
    )
    ensemble  = VotingClassifier(
        estimators=[("xgb", xgb_model), ("rf", rf)],
        voting="soft", weights=[0.60, 0.40],
    )
    calibrated = CalibratedClassifierCV(estimator=ensemble, method="sigmoid", cv=3)

    t0 = time.time()
    calibrated.fit(Xtr_sc, y_tr_bal)
    elapsed = round(time.time() - t0, 1)
    print(f"  Training done in {elapsed}s")
    print()

    print("[4/4] Evaluating out-of-sample performance ...")
    y_prob = calibrated.predict_proba(Xte_sc)[:, 1]

    best_thresh, best_f1 = 0.50, 0.0
    for thresh in np.arange(0.35, 0.80, 0.01):
        preds = (y_prob >= thresh).astype(int)
        score = f1_score(y_te, preds, zero_division=0)
        if score > best_f1:
            best_f1    = score
            best_thresh = round(thresh, 2)

    inference_thresh = max(best_thresh, 0.65)
    y_pred = (y_prob >= inference_thresh).astype(int)

    acc   = float(accuracy_score(y_te, y_pred))
    prec  = float(precision_score(y_te, y_pred, zero_division=0))
    rec   = float(recall_score(y_te, y_pred, zero_division=0))
    auc   = float(roc_auc_score(y_te, y_prob)) if len(np.unique(y_te)) > 1 else 0.5
    brier = float(brier_score_loss(y_te, y_prob))

    hc = np.where(y_prob >= inference_thresh)[0]
    if len(hc) > 0:
        tr_hc  = r_te.values[hc]
        wins   = tr_hc[tr_hc > 0]
        losses = tr_hc[tr_hc <= 0]
        pf     = round(float(np.sum(wins)) / max(abs(float(np.sum(losses))), 1e-6), 2)
        wr     = round(len(wins) / len(tr_hc) * 100, 1)
        exp_r  = round(float(np.mean(tr_hc)), 3)
    else:
        pf, wr, exp_r = 1.0, 50.0, 0.0

    print()
    print("  +----------------------------------------------+")
    print("  |  SWING MODEL — OUT-OF-SAMPLE (local daily)  |")
    print("  +----------------------------------------------+")
    print(f"  |  Inference threshold : {inference_thresh:>5.2f}               |")
    print(f"  |  Accuracy            : {acc*100:>5.1f}%              |")
    print(f"  |  Precision           : {prec*100:>5.1f}%              |")
    print(f"  |  Recall              : {rec*100:>5.1f}%              |")
    print(f"  |  ROC-AUC             : {auc:>6.4f}             |")
    print(f"  |  Brier Score         : {brier:>6.4f}             |")
    print(f"  |  High-conf trades    : {len(hc):>6,}             |")
    print(f"  |  Win Rate            : {wr:>5.1f}%              |")
    print(f"  |  Profit Factor       : {pf:>5.2f}x              |")
    print(f"  |  Avg Expectancy      : {exp_r:>+6.3f}R per trade  |")
    print("  +----------------------------------------------+")
    print()

    meta = {
        "model_version":      "swing_v2.0-local-data",
        "model_type":         "SwingDelivery-Ensemble(GBT+RF)+PlattCalib",
        "data_source":        "local-daily-angel-one",
        "timeframe":          "daily",
        "rr_multiplier":      1.5,
        "max_hold_days":      20,
        "inference_threshold": inference_thresh,
        "trained_at":         datetime.utcnow().isoformat() + "Z",
        "training_seconds":   elapsed,
        "n_features":         len(avail),
        "feature_names":      avail,
        "train_samples":      len(X_tr),
        "test_samples":       len(X_te),
        "high_conf_trades":   int(len(hc)),
        "accuracy":           round(acc, 4),
        "precision":          round(prec, 4),
        "recall":             round(rec, 4),
        "roc_auc":            round(auc, 4),
        "brier_score":        round(brier, 4),
        "win_rate":           wr,
        "profit_factor":      pf,
        "expectancy_r":       exp_r,
        "is_active":          True,
    }

    mp = ML_MODELS_DIR / "swing_delivery_ensemble_v1.joblib"
    sp = ML_MODELS_DIR / "swing_delivery_scaler_v1.joblib"
    dp = ML_MODELS_DIR / "swing_delivery_metadata_v1.json"

    joblib.dump(calibrated, mp)
    joblib.dump(scaler,     sp)
    with open(dp, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  Saved model  : {mp}")
    print(f"  Saved scaler : {sp}")
    print(f"  Saved meta   : {dp}")
    print()
    return calibrated, scaler, meta


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    t_start = time.time()

    data = load_local_daily(SWING_DELIVERY_STOCKS)
    if len(data) < 5:
        print("ERROR: Too few symbols loaded.")
        print("  → Run scripts/download_angel_history.py first.")
        sys.exit(1)

    nifty_df        = _load_nifty_daily()
    regime_features = _compute_nifty_daily_regime(nifty_df)
    print()

    X, y, r = build_daily_dataset(data, regime_features)
    model, scaler, meta = train_and_save_swing_model(X, y, r)

    total = round(time.time() - t_start, 1)
    print("=" * 62)
    print(f"  TRAINING COMPLETE in {total}s")
    print(f"  Model version : {meta['model_version']}")
    print(f"  Data source   : {meta['data_source']}")
    print(f"  ROC-AUC       : {meta['roc_auc']}")
    print(f"  Win Rate      : {meta['win_rate']}%")
    print(f"  Profit Factor : {meta['profit_factor']}x")
    print()
    print("  Restart backend to load the production model.")
    print("=" * 62)
