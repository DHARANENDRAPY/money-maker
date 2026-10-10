import numpy as np
import pandas as pd
from typing import Tuple, List
from app.engine.indicators import enrich_candles_with_indicators, calculate_supertrend

FEATURE_COLUMNS = [
    # Momentum & Returns
    "ret_1", "ret_3", "ret_5", "ret_10",
    # VWAP & EMA positioning
    "vwap_dist_pct", "ema_spread_pct", "ema9_slope", "ema21_slope",
    # Oscillators
    "rsi14_norm", "rsi_momentum",
    # Volatility
    "atr14_pct", "bb_squeeze", "range_pct",
    # Volume
    "rvol", "vol_acceleration",
    # MACD
    "macd_hist_norm", "macd_cross",
    # Candle structure
    "body_ratio", "upper_wick_ratio", "lower_wick_ratio",
    # Trend
    "supertrend_dir", "price_vs_ema50_pct",
    # Multi-timeframe momentum proxy
    "ret_high_5", "ret_low_5",
    # Intraday time encoding
    "time_sin", "time_cos",
    # Support/Resistance proximity
    "orb_dist_pct", "above_vwap",
    # Intraday session phase (0=morning, 0.5=midday, 1.0=afternoon)
    "session_phase",
]

def extract_features_from_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts 28 strictly backward-looking features with zero lookahead bias.
    All features at time t depend strictly on data available at or before bar t.
    """
    if df.empty or len(df) < 25:
        return pd.DataFrame()

    enriched = enrich_candles_with_indicators(df)

    close = enriched['close']
    open_p = enriched['open']
    high = enriched['high']
    low = enriched['low']
    vwap = enriched['vwap']
    ema9 = enriched['ema9']
    ema21 = enriched['ema21']
    ema50 = enriched['ema50']
    rsi = enriched['rsi14']
    atr = enriched['atr14']
    rvol = enriched['rvol']
    macd_hist = enriched['macd_hist']
    bb_upper = enriched['bb_upper']
    bb_lower = enriched['bb_lower']

    # Supertrend direction
    try:
        _, st_dir = calculate_supertrend(enriched, period=10, multiplier=3.0)
    except Exception:
        st_dir = pd.Series(1, index=enriched.index)

    feats = pd.DataFrame(index=enriched.index)

    # 1. Momentum & Returns
    feats['ret_1'] = close.pct_change(1).fillna(0)
    feats['ret_3'] = close.pct_change(3).fillna(0)
    feats['ret_5'] = close.pct_change(5).fillna(0)
    feats['ret_10'] = close.pct_change(10).fillna(0)

    # 2. VWAP & EMA positioning
    feats['vwap_dist_pct'] = (close - vwap) / vwap.replace(0, np.nan)
    feats['ema_spread_pct'] = (ema9 - ema21) / close.replace(0, np.nan)
    feats['ema9_slope'] = ema9.pct_change(3).fillna(0)
    feats['ema21_slope'] = ema21.pct_change(3).fillna(0)

    # 3. Oscillators
    feats['rsi14_norm'] = (rsi - 50.0) / 50.0
    feats['rsi_momentum'] = rsi.diff(3).fillna(0) / 50.0

    # 4. Volatility
    feats['atr14_pct'] = atr / close.replace(0, np.nan)
    # Bollinger Band squeeze: narrow bands = low volatility = potential breakout
    bb_width = (bb_upper - bb_lower) / close.replace(0, np.nan)
    feats['bb_squeeze'] = bb_width.fillna(0.04)
    feats['range_pct'] = (high - low) / close.replace(0, np.nan)

    # 5. Volume
    feats['rvol'] = rvol
    vol_ma = enriched['volume'].rolling(5, min_periods=1).mean()
    feats['vol_acceleration'] = (enriched['volume'] / vol_ma.replace(0, 1)).fillna(1.0)

    # 6. MACD
    macd_scale = atr.where(atr > 0, close * 0.01)
    feats['macd_hist_norm'] = (macd_hist / macd_scale).fillna(0)
    feats['macd_cross'] = (macd_hist > 0).astype(float) - (macd_hist.shift(1) > 0).astype(float)

    # 7. Candle structure (body vs wick ratios)
    candle_range = (high - low).replace(0, np.nan)
    body = (close - open_p).abs()
    feats['body_ratio'] = (body / candle_range).fillna(0.5)
    feats['upper_wick_ratio'] = ((high - pd.concat([close, open_p], axis=1).max(axis=1)) / candle_range).fillna(0)
    feats['lower_wick_ratio'] = ((pd.concat([close, open_p], axis=1).min(axis=1) - low) / candle_range).fillna(0)

    # 8. Trend
    feats['supertrend_dir'] = st_dir.fillna(1).astype(float)
    feats['price_vs_ema50_pct'] = (close - ema50) / ema50.replace(0, np.nan)

    # 9. Rolling high/low momentum (structure)
    feats['ret_high_5'] = (high - high.rolling(5, min_periods=1).max().shift(1)) / close.replace(0, np.nan)
    feats['ret_low_5'] = (low - low.rolling(5, min_periods=1).min().shift(1)) / close.replace(0, np.nan)

    # 10. Intraday cyclical time encoding (IST market 9:15 to 15:30)
    if 'timestamp' in enriched.columns:
        try:
            times = pd.to_datetime(enriched['timestamp'])
            minutes_since_open = (times.dt.hour * 60 + times.dt.minute) - (9 * 60 + 15)
            angle = (minutes_since_open.clip(0, 375) / 375.0) * (2 * np.pi)
            feats['time_sin'] = np.sin(angle)
            feats['time_cos'] = np.cos(angle)
        except Exception:
            feats['time_sin'] = 0.0
            feats['time_cos'] = 0.0
    else:
        feats['time_sin'] = 0.0
        feats['time_cos'] = 0.0

    # 11. ORB proximity (distance from opening range high/low)
    orb_high = float(enriched['high'].iloc[:3].max()) if len(enriched) >= 3 else float(close.iloc[0])
    orb_low = float(enriched['low'].iloc[:3].min()) if len(enriched) >= 3 else float(close.iloc[0])
    orb_mid = (orb_high + orb_low) / 2.0
    feats['orb_dist_pct'] = (close - orb_mid) / close.replace(0, np.nan)
    feats['above_vwap'] = (close > vwap).astype(float)

    # 12. Session phase: 0.0=morning (9:15-10:30), 0.5=midday (10:30-13:30), 1.0=afternoon (13:30-15:30)
    if 'timestamp' in enriched.columns:
        try:
            times = pd.to_datetime(enriched['timestamp'])
            mins = times.dt.hour * 60 + times.dt.minute
            session = pd.cut(
                mins,
                bins=[0, 9*60+30, 10*60+30, 13*60+30, 24*60],
                labels=[0.0, 0.0, 0.5, 1.0],
                ordered=False
            ).astype(float).fillna(0.5)
            feats['session_phase'] = session.values
        except Exception:
            feats['session_phase'] = 0.5
    else:
        feats['session_phase'] = 0.5

    return feats[FEATURE_COLUMNS].fillna(0.0)


def extract_features_single_bar(
    enriched: pd.DataFrame,
    current_price: float,
    vwap: float,
    ema9: float,
    ema21: float,
    ema50: float,
    rsi: float,
    atr: float,
    rvol: float,
    macd_hist: float,
    bb_upper: float,
    bb_lower: float,
    supertrend_dir: int,
    bar_open: float,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    minutes_since_open: int = 60,
    orb_high: float = 0.0,
    orb_low: float = 0.0,
) -> np.ndarray:
    """
    Extracts the same 28 features for a single live bar — used by the signal engine
    to feed the trained ML model at prediction time without lookahead.
    Feature order matches FEATURE_COLUMNS exactly.
    """
    close = current_price
    if close <= 0:
        return np.zeros((1, len(FEATURE_COLUMNS)))

    # Compute from enriched df for rolling features
    closes = enriched['close']

    def safe_pct(a, b):
        return (a / b - 1.0) if b and b != 0 else 0.0

    # Returns
    n = len(closes)
    ret_1 = safe_pct(closes.iloc[-1], closes.iloc[-2]) if n >= 2 else 0.0
    ret_3 = safe_pct(closes.iloc[-1], closes.iloc[-4]) if n >= 4 else 0.0
    ret_5 = safe_pct(closes.iloc[-1], closes.iloc[-6]) if n >= 6 else 0.0
    ret_10 = safe_pct(closes.iloc[-1], closes.iloc[-11]) if n >= 11 else 0.0

    vwap_dist_pct = (close - vwap) / vwap if vwap else 0.0
    ema_spread_pct = (ema9 - ema21) / close if close else 0.0

    ema9s = enriched['ema9'] if 'ema9' in enriched.columns else None
    ema21s = enriched['ema21'] if 'ema21' in enriched.columns else None
    ema9_slope = safe_pct(ema9s.iloc[-1], ema9s.iloc[-4]) if ema9s is not None and len(ema9s) >= 4 else 0.0
    ema21_slope = safe_pct(ema21s.iloc[-1], ema21s.iloc[-4]) if ema21s is not None and len(ema21s) >= 4 else 0.0

    rsi14_norm = (rsi - 50.0) / 50.0
    rsi_s = enriched['rsi14'] if 'rsi14' in enriched.columns else None
    rsi_momentum = (rsi_s.iloc[-1] - rsi_s.iloc[-4]) / 50.0 if rsi_s is not None and len(rsi_s) >= 4 else 0.0

    atr14_pct = atr / close if close else 0.0
    bb_width = (bb_upper - bb_lower) / close if close and bb_upper and bb_lower else 0.04
    bb_squeeze = bb_width

    highs = enriched['high']
    lows = enriched['low']
    range_pct = (bar_high - bar_low) / close if close else 0.01

    vol_s = enriched['volume']
    vol_ma = float(vol_s.tail(5).mean()) if len(vol_s) >= 5 else float(vol_s.mean())
    vol_acceleration = (float(vol_s.iloc[-1]) / vol_ma) if vol_ma else 1.0

    macd_scale = atr if atr > 0 else close * 0.01
    macd_hist_norm = macd_hist / macd_scale if macd_scale else 0.0
    mh_s = enriched['macd_hist'] if 'macd_hist' in enriched.columns else None
    macd_cross = 0.0
    if mh_s is not None and len(mh_s) >= 2:
        macd_cross = float(mh_s.iloc[-1] > 0) - float(mh_s.iloc[-2] > 0)

    candle_range = bar_high - bar_low
    body = abs(bar_close - bar_open)
    body_ratio = body / candle_range if candle_range else 0.5
    upper_wick = bar_high - max(bar_close, bar_open)
    lower_wick = min(bar_close, bar_open) - bar_low
    upper_wick_ratio = upper_wick / candle_range if candle_range else 0.0
    lower_wick_ratio = lower_wick / candle_range if candle_range else 0.0

    supertrend_dir_f = float(supertrend_dir)
    price_vs_ema50_pct = (close - ema50) / ema50 if ema50 else 0.0

    ret_high_5 = (bar_high - float(highs.tail(6).iloc[:-1].max())) / close if len(highs) >= 6 else 0.0
    ret_low_5 = (bar_low - float(lows.tail(6).iloc[:-1].min())) / close if len(lows) >= 6 else 0.0

    angle = (min(max(minutes_since_open, 0), 375) / 375.0) * (2 * np.pi)
    time_sin = float(np.sin(angle))
    time_cos = float(np.cos(angle))

    orb_mid = (orb_high + orb_low) / 2.0 if orb_high and orb_low else close
    orb_dist_pct = (close - orb_mid) / close if close else 0.0
    above_vwap = 1.0 if close > vwap else 0.0

    # Session phase: 0.0 = morning, 0.5 = midday, 1.0 = afternoon
    ist_total_minutes = (9 * 60 + 15) + minutes_since_open
    if ist_total_minutes < 10 * 60 + 30:
        session_phase = 0.0   # Morning
    elif ist_total_minutes < 13 * 60 + 30:
        session_phase = 0.5   # Midday
    else:
        session_phase = 1.0   # Afternoon

    features = np.array([[
        ret_1, ret_3, ret_5, ret_10,
        vwap_dist_pct, ema_spread_pct, ema9_slope, ema21_slope,
        rsi14_norm, rsi_momentum,
        atr14_pct, bb_squeeze, range_pct,
        rvol, vol_acceleration,
        macd_hist_norm, macd_cross,
        body_ratio, upper_wick_ratio, lower_wick_ratio,
        supertrend_dir_f, price_vs_ema50_pct,
        ret_high_5, ret_low_5,
        time_sin, time_cos,
        orb_dist_pct, above_vwap,
        session_phase,
    ]], dtype=float)

    # Replace any NaN/inf with 0
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    return features
