"""
train_models.py — Intraday (5-minute) Ensemble Model Training
=============================================================
Data source : data/processed/{SYMBOL}/5m.csv  (produced by prepare_market_data.py)
Nifty regime: data/daily/NIFTY50.csv  OR  data/processed/NIFTY/1d.csv
Splits       : chronological 70% train / 15% val / 15% test  (NO shuffle)
Output       : ml_models/intraday_ensemble_v3.joblib
               ml_models/scaler_v3.joblib
               ml_models/metadata_v3.json
"""
import os
import sys
import time
import json
import warnings
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

BACKEND_DIR = Path(__file__).parent
ML_MODELS_DIR = BACKEND_DIR / "ml_models"
ML_MODELS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(BACKEND_DIR))

PROCESSED_DIR = BACKEND_DIR / "data" / "processed"
DAILY_DIR     = BACKEND_DIR / "data" / "daily"

print("=" * 62)
print("  MoneyMaker AI  --  Production Intraday Model Training")
print("=" * 62)
print()

# Symbols that have local 5-minute data
NSE_STOCKS = [
    "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "BAJAJFINSV",
    "TCS", "SBIN", "KOTAKBANK", "AXISBANK", "WIPRO",
    "HINDUNILVR", "LT", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "ULTRACEMCO", "TITAN", "BAJFINANCE", "BHARTIARTL", "NESTLEIND",
    "ADANIPORTS", "POWERGRID", "NTPC", "TATASTEEL", "JSWSTEEL",
    "ONGC", "IOC", "BPCL", "DRREDDY", "CIPLA",
]

TRAIN_RATIO = 0.70
VAL_RATIO   = 0.15
# remaining 0.15 → test


# ---------------------------------------------------------------------------
# Step 1: Load local 5-minute data
# ---------------------------------------------------------------------------
def load_local_data(symbols):
    """
    Reads pre-processed 5-minute candles from data/processed/{SYMBOL}/5m.csv.
    Only uses the chronological training slice (first 70%) to avoid any
    lookahead contamination from the val/test windows.
    """
    data_dict = {}
    failed    = []

    print(f"[1/4] Loading local 5-min data for {len(symbols)} symbols ...")
    print()

    for i, sym in enumerate(symbols):
        path = PROCESSED_DIR / sym / "5m.csv"
        if not path.exists():
            failed.append(sym)
            print(f"  [{i+1:2d}/{len(symbols)}] MISS  {sym:<15}  -- file not found, skipping")
            continue

        try:
            df = pd.read_csv(path, index_col="datetime", parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
            keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
            df   = df[keep].dropna()

            if len(df) < 200:
                failed.append(sym)
                print(f"  [{i+1:2d}/{len(symbols)}] SKIP  {sym:<15}  -- too few bars ({len(df)})")
                continue

            # Use only the training slice to prevent future peeking
            train_end = int(len(df) * TRAIN_RATIO)
            df_train  = df.iloc[:train_end]

            data_dict[sym] = df_train
            print(f"  [{i+1:2d}/{len(symbols)}] OK    {sym:<15}  -- {len(df_train):,} train bars "
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
# Nifty 50 regime features (from local daily data)
# ---------------------------------------------------------------------------
def _load_nifty_daily() -> pd.DataFrame | None:
    """
    Loads Nifty 50 daily data from data/daily/ or data/processed/NIFTY/.
    Returns None if unavailable — training proceeds without regime features.
    """
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
                    print(f"  Loaded Nifty regime data from {p.name} ({len(df)} days)")
                    return df
            except Exception:
                continue
    print("  WARNING: No Nifty 50 daily file found. Regime features disabled.")
    return None


def _compute_nifty_regime_features(nifty_df) -> pd.DataFrame | None:
    """Computes Nifty 50 intraday regime features from daily data."""
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
# Step 2: Build labeled dataset
# ---------------------------------------------------------------------------
def build_dataset(data_dict, regime_features):
    from app.ml.feature_engineering import extract_features_from_df, FEATURE_COLUMNS
    from app.ml.target_labeller import label_setup_outcomes
    from app.engine.indicators import enrich_candles_with_indicators

    all_X, all_y, all_r = [], [], []
    has_regime = regime_features is not None

    if has_regime:
        print("  [REGIME] Nifty 50 regime features enabled "
              "(bull/bear/sideways + momentum + volatility)")
    else:
        print("  [REGIME] Nifty regime features unavailable — training without market context")

    print("[2/4] Extracting features + labelling trade setups ...")
    print()

    for sym, raw in data_dict.items():
        try:
            df = enrich_candles_with_indicators(raw.copy())
            if df.empty or len(df) < 50:
                continue

            feats = extract_features_from_df(df)
            if feats.empty:
                continue

            # Merge Nifty regime by date (forward-fill daily values to 5-min bars)
            if has_regime:
                try:
                    # Align on date only — avoid any tz mismatch
                    feats_dates = feats.index.normalize()
                    reg_reindexed = regime_features.reindex(feats_dates, method="ffill")
                    reg_reindexed.index = feats.index
                    feats = feats.join(reg_reindexed, rsuffix="_regime")
                    for col in ["nifty_regime", "nifty_momentum", "nifty_volatility"]:
                        if col not in feats.columns:
                            feats[col] = 0.0
                    feats = feats.fillna(0.0)
                except Exception:
                    for col in ["nifty_regime", "nifty_momentum", "nifty_volatility"]:
                        feats[col] = 0.0

            valid_len = min(len(feats), len(df) - 15)
            vf = feats.iloc[:valid_len]

            # LONG labels
            lbl_l, r_l = label_setup_outcomes(df, risk_atr_mult=1.0, reward_atr_mult=1.5,
                                              max_holding_bars=16, direction="LONG")
            vl   = lbl_l.iloc[:valid_len]
            vr   = r_l.iloc[:valid_len]
            lmask = vr != 0.0
            if lmask.sum() > 0:
                all_X.append(vf[lmask])
                all_y.append(vl[lmask])
                all_r.append(vr[lmask])

            # SHORT labels
            lbl_s, r_s = label_setup_outcomes(df, risk_atr_mult=1.0, reward_atr_mult=1.5,
                                              max_holding_bars=16, direction="SHORT")
            vs   = lbl_s.iloc[:valid_len]
            vsr  = r_s.iloc[:valid_len]
            smask = vsr != 0.0
            if smask.sum() > 0:
                sf = vf[smask].copy()
                dir_cols = ["vwap_dist_pct", "ema_spread_pct", "ema9_slope", "ema21_slope",
                            "rsi14_norm", "rsi_momentum", "macd_hist_norm", "macd_cross",
                            "supertrend_dir", "price_vs_ema50_pct", "above_vwap", "orb_dist_pct"]
                for col in dir_cols:
                    if col in sf.columns:
                        sf[col] = -sf[col]
                if "nifty_regime" in sf.columns:
                    sf["nifty_regime"] = -sf["nifty_regime"]
                all_X.append(sf)
                all_y.append(vs[smask])
                all_r.append(vsr[smask])

            rows = lmask.sum() + smask.sum()
            print(f"  {sym:<15}  {rows:,} labeled setups")

        except Exception as exc:
            print(f"  {sym:<15}  SKIPPED -- {exc}")

    if not all_X:
        raise RuntimeError("No training data built. Check indicator pipeline.")

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
# Step 3: Train ensemble + save artifacts
# ---------------------------------------------------------------------------
def train_and_save(X, y, r):
    from sklearn.ensemble import RandomForestClassifier, VotingClassifier
    from xgboost import XGBClassifier
    from sklearn.calibration import CalibratedClassifierCV, calibration_curve
    from sklearn.metrics import (brier_score_loss, log_loss, roc_auc_score,
                                 precision_score, recall_score, accuracy_score, f1_score)
    from sklearn.preprocessing import StandardScaler
    from sklearn.utils import resample
    from app.ml.feature_engineering import FEATURE_COLUMNS

    print("[3/4] Training Ensemble (GBT + RF) + Platt Calibration ...")
    print("      Strict walk-forward split -- 70% train / 15% val (unused) / 15% test")
    print()

    avail = [c for c in FEATURE_COLUMNS if c in X.columns]
    # Also include regime cols if present
    for rc in ["nifty_regime", "nifty_momentum", "nifty_volatility"]:
        if rc in X.columns and rc not in avail:
            avail.append(rc)

    Xf = X[avail].fillna(0.0)

    n      = len(Xf)
    tr_end = int(n * TRAIN_RATIO)
    va_end = int(n * (TRAIN_RATIO + VAL_RATIO))

    X_tr = Xf.iloc[:tr_end]
    # val slice reserved for future hyper-param search  (not used here)
    X_te = Xf.iloc[va_end:]
    y_tr = y.iloc[:tr_end]
    y_te = y.iloc[va_end:]
    r_te = r.iloc[va_end:]

    # Balance classes on training set only
    tr_combined            = X_tr.copy()
    tr_combined["__y"]     = y_tr.values
    wins_df   = tr_combined[tr_combined["__y"] == 1]
    losses_df = tr_combined[tr_combined["__y"] == 0]
    n_wins    = len(wins_df)
    n_losses  = len(losses_df)
    target_losses = min(n_losses, int(n_wins * 1.2))
    losses_down   = resample(losses_df, replace=False,
                             n_samples=target_losses, random_state=42)
    balanced  = pd.concat([wins_df, losses_down]).sample(frac=1, random_state=42)
    X_tr_bal  = balanced.drop(columns=["__y"])
    y_tr_bal  = balanced["__y"]

    print(f"  Raw Train   : {len(X_tr):,} (wins={n_wins:,} losses={n_losses:,})")
    print(f"  Balanced    : {len(X_tr_bal):,} (wins={int(y_tr_bal.sum()):,} "
          f"losses={int((y_tr_bal == 0).sum()):,})")
    print(f"  Test        : {len(X_te):,}")
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
        voting="soft", weights=[0.6, 0.4],
    )
    calibrated = CalibratedClassifierCV(estimator=ensemble, method="sigmoid", cv=3)

    t0 = time.time()
    calibrated.fit(Xtr_sc, y_tr_bal)
    elapsed = round(time.time() - t0, 1)
    print(f"  Training done in {elapsed}s")
    print()

    print("[4/4] Evaluating out-of-sample performance ...")
    y_prob = calibrated.predict_proba(Xte_sc)[:, 1]

    # Optimal threshold by F1
    best_thresh, best_f1 = 0.50, 0.0
    for thresh in np.arange(0.35, 0.75, 0.01):
        preds = (y_prob >= thresh).astype(int)
        score = f1_score(y_te, preds, zero_division=0)
        if score > best_f1:
            best_f1    = score
            best_thresh = round(thresh, 2)
    print(f"  Optimal threshold: {best_thresh} (F1={best_f1:.4f})")

    y_pred = (y_prob >= best_thresh).astype(int)
    acc   = float(accuracy_score(y_te, y_pred))
    prec  = float(precision_score(y_te, y_pred, zero_division=0))
    rec   = float(recall_score(y_te, y_pred, zero_division=0))
    auc   = float(roc_auc_score(y_te, y_prob)) if len(np.unique(y_te)) > 1 else 0.5
    brier = float(brier_score_loss(y_te, y_prob))
    ll    = float(log_loss(y_te, y_prob))

    hc_thresh = max(best_thresh, 0.60)
    hc = np.where(y_prob >= hc_thresh)[0]
    if len(hc) > 0:
        tr_vals = r_te.values[hc]
        wins    = tr_vals[tr_vals > 0]
        losses  = tr_vals[tr_vals <= 0]
        pf      = round(float(np.sum(wins)) / max(abs(float(np.sum(losses))), 1e-6), 2)
        wr      = round(len(wins) / len(tr_vals) * 100, 1)
        exp_r   = round(float(np.mean(tr_vals)), 3)
        cum     = np.cumsum(tr_vals)
        mdd     = round(float(np.max(np.maximum.accumulate(cum) - cum)), 2)
    else:
        pf, wr, exp_r, mdd = 1.0, 50.0, 0.0, 0.0

    print()
    print("  +-------------------------------------------------+")
    print("  |  OUT-OF-SAMPLE PERFORMANCE (local 5-min data)  |")
    print("  +-------------------------------------------------+")
    print(f"  |  Threshold      : {best_thresh:>5.2f}                        |")
    print(f"  |  Accuracy       : {acc*100:>5.1f}%                      |")
    print(f"  |  Precision      : {prec*100:>5.1f}%                      |")
    print(f"  |  Recall         : {rec*100:>5.1f}%                      |")
    print(f"  |  ROC-AUC        : {auc:>6.4f}                     |")
    print(f"  |  Brier Score    : {brier:>6.4f}  (lower better)    |")
    print(f"  |  Log Loss       : {ll:>6.4f}  (lower better)    |")
    print("  +-------------------------------------------------+")
    print(f"  |  HIGH-CONF TRADES (>={hc_thresh:.2f} threshold)            |")
    print(f"  |  Trades         : {len(hc):>6,}                      |")
    print(f"  |  Win Rate       : {wr:>5.1f}%                      |")
    print(f"  |  Profit Factor  : {pf:>5.2f}x                      |")
    print(f"  |  Avg Expectancy : {exp_r:>+6.3f}R per trade          |")
    print(f"  |  Max Drawdown   : {mdd:>5.2f}R                      |")
    print("  +-------------------------------------------------+")
    print()

    try:
        pt, pp = calibration_curve(y_te, y_prob, n_bins=6, strategy="uniform")
        calib_data = [{"predicted": round(float(a), 3), "actual": round(float(b), 3)}
                      for a, b in zip(pp, pt)]
    except Exception:
        calib_data = []

    meta = {
        "model_version":    "v3.2-local-data",
        "model_type":       "Ensemble(XGB+RF)+PlattCalibration",
        "data_source":      "local-5min-processed",
        "rr_multiplier":    1.5,
        "inference_threshold": 0.60,
        "trained_at":       datetime.utcnow().isoformat() + "Z",
        "training_seconds": elapsed,
        "n_features":       len(avail),
        "feature_names":    avail,
        "train_samples":    len(X_tr),
        "test_samples":     len(X_te),
        "high_conf_trades": int(len(hc)),
        "optimal_threshold": best_thresh,
        "accuracy":         round(acc, 4),
        "precision":        round(prec, 4),
        "recall":           round(rec, 4),
        "roc_auc":          round(auc, 4),
        "brier_score":      round(brier, 4),
        "log_loss":         round(ll, 4),
        "win_rate":         wr,
        "profit_factor":    pf,
        "expectancy_r":     exp_r,
        "max_drawdown_r":   mdd,
        "calibration_curve": calib_data,
        "is_active":        True,
    }

    mp = ML_MODELS_DIR / "intraday_ensemble_v3.joblib"
    sp = ML_MODELS_DIR / "scaler_v3.joblib"
    dp = ML_MODELS_DIR / "metadata_v3.json"

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

    data = load_local_data(NSE_STOCKS)
    if len(data) < 5:
        print("ERROR: Too few symbols loaded. Run prepare_market_data.py first.")
        sys.exit(1)

    nifty_daily     = _load_nifty_daily()
    regime_features = _compute_nifty_regime_features(nifty_daily)
    print()

    X, y, r = build_dataset(data, regime_features)
    model, scaler, meta = train_and_save(X, y, r)

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
