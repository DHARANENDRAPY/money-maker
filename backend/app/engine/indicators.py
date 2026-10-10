import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculates Volume Weighted Average Price (VWAP) for intraday data."""
    if df.empty or 'volume' not in df.columns:
        return pd.Series(index=df.index, dtype=float)
    
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    cum_vol_price = (typical_price * df['volume']).cumsum()
    cum_vol = df['volume'].cumsum()
    
    # Avoid zero division
    vwap = cum_vol_price / cum_vol.replace(0, np.nan)
    return vwap.ffill().bfill()

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index with Wilder's exponential smoothing."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD Line, Signal Line, and Histogram."""
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (ATR)."""
    high = df['high']
    low = df['low']
    close_prev = df['close'].shift(1)
    
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr.bfill()

def calculate_bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands (Upper, Middle, Lower)."""
    middle = calculate_sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return upper, middle, lower

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    """Supertrend indicator (Supertrend line, Direction: 1 for Bullish, -1 for Bearish)."""
    atr = calculate_atr(df, period)
    hl2 = (df['high'] + df['low']) / 2.0
    
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    
    in_uptrend = True
    for i in range(len(df)):
        if i == 0:
            supertrend.iloc[i] = lower_band.iloc[i]
            direction.iloc[i] = 1
            continue
            
        close = df['close'].iloc[i]
        prev_supertrend = supertrend.iloc[i-1]
        prev_upper = upper_band.iloc[i-1]
        prev_lower = lower_band.iloc[i-1]
        
        # Upper band adjustment
        if upper_band.iloc[i] < prev_upper or df['close'].iloc[i-1] > prev_upper:
            curr_upper = upper_band.iloc[i]
        else:
            curr_upper = prev_upper
            
        # Lower band adjustment
        if lower_band.iloc[i] > prev_lower or df['close'].iloc[i-1] < prev_lower:
            curr_lower = lower_band.iloc[i]
        else:
            curr_lower = prev_lower
            
        if in_uptrend:
            if close < curr_lower:
                in_uptrend = False
                supertrend.iloc[i] = curr_upper
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = curr_lower
                direction.iloc[i] = 1
        else:
            if close > curr_upper:
                in_uptrend = True
                supertrend.iloc[i] = curr_lower
                direction.iloc[i] = 1
            else:
                supertrend.iloc[i] = curr_upper
                direction.iloc[i] = -1
                
    return supertrend, direction

def calculate_relative_volume(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Calculates Relative Volume (RVOL) = current volume / rolling average volume."""
    avg_vol = df['volume'].rolling(window=window, min_periods=1).mean()
    rvol = df['volume'] / avg_vol.replace(0, 1)
    return rvol.fillna(1.0)

def detect_key_levels(df: pd.DataFrame, opening_range_bars: int = 3) -> Dict[str, float]:
    """Detects Previous Day High/Low/Close, Opening Range (first 15m), and Pivot levels."""
    if df.empty:
        return {}
        
    latest_close = float(df['close'].iloc[-1])
    day_high = float(df['high'].max())
    day_low = float(df['low'].min())
    day_open = float(df['open'].iloc[0])
    
    # Opening range (e.g. first 3 x 5m candles = 15m)
    orb_bars = min(len(df), opening_range_bars)
    opening_range_high = float(df['high'].iloc[:orb_bars].max())
    opening_range_low = float(df['low'].iloc[:orb_bars].min())
    
    # Pivot Points (Classical)
    pp = (day_high + day_low + latest_close) / 3.0
    r1 = (2 * pp) - day_low
    s1 = (2 * pp) - day_high
    r2 = pp + (day_high - day_low)
    s2 = pp - (day_high - day_low)
    
    return {
        "day_open": round(day_open, 2),
        "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "orb_high": round(opening_range_high, 2),
        "orb_low": round(opening_range_low, 2),
        "pivot": round(pp, 2),
        "resistance_1": round(r1, 2),
        "support_1": round(s1, 2),
        "resistance_2": round(r2, 2),
        "support_2": round(s2, 2)
    }

def enrich_candles_with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Enriches OHLCV DataFrame with core indicators."""
    res = df.copy()
    if res.empty:
        return res
        
    res['vwap'] = calculate_vwap(res)
    res['ema9'] = calculate_ema(res['close'], 9)
    res['ema21'] = calculate_ema(res['close'], 21)
    res['ema50'] = calculate_ema(res['close'], 50)
    res['rsi14'] = calculate_rsi(res['close'], 14)
    res['atr14'] = calculate_atr(res, 14)
    res['rvol'] = calculate_relative_volume(res, 20)
    
    macd_l, signal_l, hist = calculate_macd(res['close'], 12, 26, 9)
    res['macd'] = macd_l
    res['macd_signal'] = signal_l
    res['macd_hist'] = hist
    
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(res['close'], 20, 2.0)
    res['bb_upper'] = bb_upper
    res['bb_lower'] = bb_lower
    
    return res
