import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculates Volume Weighted Average Price (VWAP) for intraday data, resetting daily."""
    if df.empty or 'volume' not in df.columns:
        return pd.Series(index=df.index, dtype=float)
    
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    vol_price = typical_price * df['volume']

    # Reset VWAP per session if timestamp/date information is present
    if isinstance(df.index, pd.DatetimeIndex):
        dates = df.index.date
        cum_vol_price = vol_price.groupby(dates).cumsum()
        cum_vol = df['volume'].groupby(dates).cumsum()
    elif 'timestamp' in df.columns:
        ts = pd.to_datetime(df['timestamp'], errors='coerce')
        if not ts.isna().all():
            dates = ts.dt.date
            cum_vol_price = vol_price.groupby(dates).cumsum()
            cum_vol = df['volume'].groupby(dates).cumsum()
        else:
            cum_vol_price = vol_price.cumsum()
            cum_vol = df['volume'].cumsum()
    else:
        cum_vol_price = vol_price.cumsum()
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
        
    # Isolate today's session if timestamp/datetime info is available
    if isinstance(df.index, pd.DatetimeIndex):
        latest_date = df.index[-1].date()
        today_df = df[df.index.date == latest_date]
    elif 'timestamp' in df.columns:
        ts = pd.to_datetime(df['timestamp'], errors='coerce')
        valid_ts = ts.dropna()
        if not valid_ts.empty:
            latest_date = valid_ts.iloc[-1].date()
            today_df = df[ts.dt.date == latest_date]
        else:
            today_df = df.tail(min(len(df), 75))
    else:
        today_df = df.tail(min(len(df), 75))

    if today_df.empty:
        today_df = df

    latest_close = float(today_df['close'].iloc[-1])
    day_high = float(today_df['high'].max())
    day_low = float(today_df['low'].min())
    day_open = float(today_df['open'].iloc[0])
    
    # Opening range strictly from today's opening bars (e.g. first 3 x 5m candles = 15m)
    orb_bars = min(len(today_df), opening_range_bars)
    opening_range_high = float(today_df['high'].iloc[:orb_bars].max())
    opening_range_low = float(today_df['low'].iloc[:orb_bars].min())
    
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
        "orb_formed": len(today_df) >= opening_range_bars,
        "pivot": round(pp, 2),
        "resistance_1": round(r1, 2),
        "support_1": round(s1, 2),
        "resistance_2": round(r2, 2),
        "support_2": round(s2, 2)
    }

def calculate_vwap_bands(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Calculates Volume-Weighted Standard Deviation Bands around intraday VWAP.
    Variance = sum(vol * (typical_price - VWAP)^2) / sum(vol)
    StdDev = sqrt(Variance)
    Upper/Lower Bands = VWAP +/- (multiplier * StdDev)
    """
    if df.empty or 'volume' not in df.columns:
        empty_s = pd.Series(index=df.index, dtype=float)
        return {
            "vwap": empty_s, "std": empty_s,
            "upper_1": empty_s, "lower_1": empty_s,
            "upper_2": empty_s, "lower_2": empty_s,
            "upper_3": empty_s, "lower_3": empty_s,
            "zscore": empty_s,
        }
    
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    vol = df['volume']
    vwap = calculate_vwap(df)
    
    # Session-aware cumulative variance
    sq_diff = (typical_price - vwap) ** 2
    vol_sq_diff = vol * sq_diff
    
    if isinstance(df.index, pd.DatetimeIndex):
        dates = df.index.date
        cum_vol_sq_diff = vol_sq_diff.groupby(dates).cumsum()
        cum_vol = vol.groupby(dates).cumsum()
    elif 'timestamp' in df.columns:
        ts = pd.to_datetime(df['timestamp'], errors='coerce')
        if not ts.isna().all():
            dates = ts.dt.date
            cum_vol_sq_diff = vol_sq_diff.groupby(dates).cumsum()
            cum_vol = vol.groupby(dates).cumsum()
        else:
            cum_vol_sq_diff = vol_sq_diff.cumsum()
            cum_vol = vol.cumsum()
    else:
        cum_vol_sq_diff = vol_sq_diff.cumsum()
        cum_vol = vol.cumsum()
        
    variance = cum_vol_sq_diff / cum_vol.replace(0, np.nan)
    vwap_std = np.sqrt(variance.clip(lower=0.0)).ffill().bfill()
    # Fallback standard deviation if 0
    vwap_std = vwap_std.replace(0, np.nan).fillna(typical_price * 0.003).round(2)
    
    zscore = ((df['close'] - vwap) / vwap_std.replace(0, 1.0)).round(2)
    
    return {
        "vwap": vwap,
        "std": vwap_std,
        "upper_1": (vwap + (1.0 * vwap_std)).round(2),
        "lower_1": (vwap - (1.0 * vwap_std)).round(2),
        "upper_2": (vwap + (2.0 * vwap_std)).round(2),
        "lower_2": (vwap - (2.0 * vwap_std)).round(2),
        "upper_3": (vwap + (3.0 * vwap_std)).round(2),
        "lower_3": (vwap - (3.0 * vwap_std)).round(2),
        "zscore": zscore,
    }


def detect_opening_gap(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detects Opening Gap physics relative to previous day close and ATR:
    Classifications:
    - GAP_AND_GO_BULLISH: Gap up >= 0.6%, price holding above opening candle low
    - GAP_AND_GO_BEARISH: Gap down <= -0.6%, price holding below opening candle high
    - GAP_FADE_BEARISH: Gap up broke back below opening low (gap fill underway)
    - GAP_FADE_BULLISH: Gap down broke back above opening high (gap fill bounce)
    - FLAT_OPEN: Gap < 0.4%
    """
    if df.empty or len(df) < 3:
        return {"gap_pct": 0.0, "gap_type": "FLAT_OPEN", "prev_close": 0.0, "open_price": 0.0}

    # Extract today's session vs previous session
    if isinstance(df.index, pd.DatetimeIndex):
        latest_date = df.index[-1].date()
        today_df = df[df.index.date == latest_date]
        prev_df = df[df.index.date < latest_date]
    elif 'timestamp' in df.columns:
        ts = pd.to_datetime(df['timestamp'], errors='coerce')
        valid_ts = ts.dropna()
        if not valid_ts.empty:
            latest_date = valid_ts.iloc[-1].date()
            today_df = df[ts.dt.date == latest_date]
            prev_df = df[ts.dt.date < latest_date]
        else:
            today_df = df.tail(min(len(df), 75))
            prev_df = pd.DataFrame()
    else:
        today_df = df.tail(min(len(df), 75))
        prev_df = pd.DataFrame()

    if today_df.empty:
        today_df = df
    
    today_open = float(today_df['open'].iloc[0])
    curr_price = float(today_df['close'].iloc[-1])
    open_bar_high = float(today_df['high'].iloc[0])
    open_bar_low = float(today_df['low'].iloc[0])

    prev_close = float(prev_df['close'].iloc[-1]) if not prev_df.empty else float(today_df['open'].iloc[0])
    if prev_close <= 0:
        return {"gap_pct": 0.0, "gap_type": "FLAT_OPEN", "prev_close": today_open, "open_price": today_open}

    gap_pct = round(((today_open - prev_close) / prev_close) * 100.0, 2)

    # Gap Classification
    if gap_pct >= 0.6:
        if curr_price >= open_bar_low:
            gap_type = "GAP_AND_GO_BULLISH"
        else:
            gap_type = "GAP_FADE_BEARISH"
    elif gap_pct <= -0.6:
        if curr_price <= open_bar_high:
            gap_type = "GAP_AND_GO_BEARISH"
        else:
            gap_type = "GAP_FADE_BULLISH"
    else:
        gap_type = "FLAT_OPEN"

    return {
        "gap_pct": gap_pct,
        "gap_type": gap_type,
        "prev_close": round(prev_close, 2),
        "open_price": round(today_open, 2),
        "curr_price": round(curr_price, 2)
    }


def enrich_candles_with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Enriches OHLCV DataFrame with core indicators including VWAP standard deviation bands."""
    res = df.copy()
    if res.empty:
        return res
        
    vwap_bands = calculate_vwap_bands(res)
    res['vwap'] = vwap_bands['vwap']
    res['vwap_std'] = vwap_bands['std']
    res['vwap_upper_1'] = vwap_bands['upper_1']
    res['vwap_lower_1'] = vwap_bands['lower_1']
    res['vwap_upper_2'] = vwap_bands['upper_2']
    res['vwap_lower_2'] = vwap_bands['lower_2']
    res['vwap_upper_3'] = vwap_bands['upper_3']
    res['vwap_lower_3'] = vwap_bands['lower_3']
    res['vwap_zscore'] = vwap_bands['zscore']

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


def calculate_multi_timeframe_confluence(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluates Multi-Timeframe (MTF) trend consensus across 5m, 15m, and 1h horizons.
    Helps eliminate counter-trend whipsaws and false intraday breakouts.
    """
    if df.empty or len(df) < 6:
        return {
            "trend_5m": "NEUTRAL",
            "trend_15m": "NEUTRAL",
            "trend_1h": "NEUTRAL",
            "alignment": "NEUTRAL",
            "confluence_score": 50,
            "is_full_alignment": False,
            "detail": "Insufficient candle bars for MTF evaluation."
        }

    close = df['close']
    curr_price = float(close.iloc[-1])

    # 1. 5-Minute Horizon (EMA9 & EMA21)
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    curr_ema9 = float(ema9.iloc[-1])
    curr_ema21 = float(ema21.iloc[-1])

    if curr_price >= curr_ema9 >= curr_ema21:
        trend_5m = "BULLISH"
    elif curr_price <= curr_ema9 <= curr_ema21:
        trend_5m = "BEARISH"
    elif curr_price >= curr_ema21:
        trend_5m = "BULLISH"
    elif curr_price <= curr_ema21:
        trend_5m = "BEARISH"
    else:
        trend_5m = "NEUTRAL"

    # 2. 15-Minute Horizon (Synthesized 3-bar span ≈ 27 bars)
    span_15m = min(len(close), 27)
    ema15 = close.ewm(span=span_15m, adjust=False).mean()
    curr_ema15 = float(ema15.iloc[-1])
    if curr_price > curr_ema15 * 1.001:
        trend_15m = "BULLISH"
    elif curr_price < curr_ema15 * 0.999:
        trend_15m = "BEARISH"
    else:
        trend_15m = "NEUTRAL"

    # 3. 1-Hour Horizon (Synthesized 12-bar span ≈ 60 bars)
    span_1h = min(len(close), 60)
    ema1h = close.ewm(span=span_1h, adjust=False).mean()
    curr_ema1h = float(ema1h.iloc[-1])
    if curr_price > curr_ema1h * 1.002:
        trend_1h = "BULLISH"
    elif curr_price < curr_ema1h * 0.998:
        trend_1h = "BEARISH"
    else:
        trend_1h = "NEUTRAL"

    # Evaluate Confluence & Consensus
    bull_count = sum(1 for t in [trend_5m, trend_15m, trend_1h] if t == "BULLISH")
    bear_count = sum(1 for t in [trend_5m, trend_15m, trend_1h] if t == "BEARISH")

    if bull_count == 3:
        alignment = "FULL_BULLISH"
        score = 96
        detail = "Triple MTF Confluence: 5m, 15m & 1H all Bullish"
    elif bull_count == 2 and bear_count == 0:
        alignment = "PARTIAL_BULLISH"
        score = 80
        detail = "Dual MTF Confluence: 2/3 Timeframes Bullish"
    elif bear_count == 3:
        alignment = "FULL_BEARISH"
        score = 96
        detail = "Triple MTF Confluence: 5m, 15m & 1H all Bearish"
    elif bear_count == 2 and bull_count == 0:
        alignment = "PARTIAL_BEARISH"
        score = 80
        detail = "Dual MTF Confluence: 2/3 Timeframes Bearish"
    elif (trend_5m == "BULLISH" and trend_1h == "BEARISH") or (trend_5m == "BEARISH" and trend_1h == "BULLISH"):
        alignment = "COUNTER_TREND"
        score = 25
        detail = f"Counter-Trend Trap: 5m {trend_5m} vs 1H {trend_1h}"
    else:
        alignment = "NEUTRAL"
        score = 50
        detail = "Mixed Timeframe Consolidation"

    return {
        "trend_5m": trend_5m,
        "trend_15m": trend_15m,
        "trend_1h": trend_1h,
        "alignment": alignment,
        "confluence_score": score,
        "is_full_alignment": alignment in ["FULL_BULLISH", "FULL_BEARISH"],
        "detail": detail
    }


def calculate_ttm_squeeze(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes TTM Squeeze Volatility Momentum.
    Compares 20-period Bollinger Bands (2.0 std) with 20-period Keltner Channels (1.5 ATR).
    - When Bollinger Bands are inside Keltner Channels: Volatility Squeeze is ON (energy coiling).
    - When Bollinger Bands expand outside Keltner Channels: Volatility Squeeze is FIRED (momentum explosion).
    Histogram measures price displacement from the average of Donchian midline and SMA.
    """
    if df.empty or len(df) < 20:
        return {
            "squeeze_status": "NO_SQUEEZE",
            "is_squeeze_on": False,
            "is_fired": False,
            "momentum_value": 0.0,
            "momentum_color": "GRAY",
            "momentum_direction": "NEUTRAL",
            "detail": "Insufficient bars for TTM Squeeze calculation."
        }

    close = df['close']
    high = df['high']
    low = df['low']

    # 1. 20-period SMA
    sma20 = close.rolling(window=20).mean()

    # 2. Bollinger Bands (20, 2.0)
    std20 = close.rolling(window=20).std()
    bb_upper = sma20 + 2.0 * std20
    bb_lower = sma20 - 2.0 * std20

    # 3. Keltner Channels (20, 1.5 ATR)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr20 = tr.rolling(window=20).mean()

    kc_upper = sma20 + 1.5 * atr20
    kc_lower = sma20 - 1.5 * atr20

    # Current and previous squeeze conditions
    squeeze_series = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    is_squeeze_on = bool(squeeze_series.iloc[-1])
    was_squeeze_on = bool(squeeze_series.iloc[-2]) if len(squeeze_series) >= 2 else is_squeeze_on

    # 4. Momentum Histogram: Linear displacement
    highest_20 = high.rolling(window=20).max()
    lowest_20 = low.rolling(window=20).min()
    donchian_mid = (highest_20 + lowest_20) / 2.0
    delta = close - ((donchian_mid + sma20) / 2.0)
    
    mom_series = delta.rolling(window=5).mean().fillna(0)
    curr_mom = float(mom_series.iloc[-1])
    prev_mom = float(mom_series.iloc[-2]) if len(mom_series) >= 2 else curr_mom

    if is_squeeze_on:
        status = "SQUEEZE_ON"
        detail = "⚡ Volatility Squeeze Active (Energy Coiling for Breakout)"
    elif was_squeeze_on and not is_squeeze_on:
        if curr_mom > 0:
            status = "SQUEEZE_FIRED_BULLISH"
            detail = "🔥 Squeeze Fired Bullish (Explosive Momentum Expansion Up)"
        else:
            status = "SQUEEZE_FIRED_BEARISH"
            detail = "💥 Squeeze Fired Bearish (Explosive Momentum Expansion Down)"
    else:
        status = "NO_SQUEEZE"
        detail = "Normal Volatility Flow"

    # Momentum coloring
    if curr_mom > 0:
        mom_color = "LIGHT_GREEN" if curr_mom >= prev_mom else "DARK_GREEN"
        mom_dir = "BULLISH_EXPANDING" if curr_mom >= prev_mom else "BULLISH_CONTRACTING"
    else:
        mom_color = "LIGHT_RED" if curr_mom <= prev_mom else "DARK_RED"
        mom_dir = "BEARISH_EXPANDING" if curr_mom <= prev_mom else "BEARISH_CONTRACTING"

    return {
        "squeeze_status": status,
        "is_squeeze_on": is_squeeze_on,
        "is_fired": "FIRED" in status,
        "momentum_value": round(curr_mom, 2),
        "momentum_color": mom_color,
        "momentum_direction": mom_dir,
        "detail": detail
    }


def detect_candlestick_patterns(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Scans the latest 1 to 3 candles for high-probability institutional candlestick patterns:
    - Bullish / Bearish Engulfing
    - Hammer Pinbar / Shooting Star Pinbar
    - Morning Star / Evening Star
    - Inside Bar Breakout
    """
    if df.empty or len(df) < 5:
        return {
            "patterns": [],
            "primary_pattern": None,
            "bias": "NEUTRAL",
            "reliability_score": 0,
            "count": 0
        }

    c0 = df.iloc[-1]   # Current / latest candle
    c1 = df.iloc[-2]   # Previous candle
    c2 = df.iloc[-3] if len(df) >= 3 else c1

    o0, h0, l0, cl0 = float(c0['open']), float(c0['high']), float(c0['low']), float(c0['close'])
    o1, h1, l1, cl1 = float(c1['open']), float(c1['high']), float(c1['low']), float(c1['close'])
    o2, h2, l2, cl2 = float(c2['open']), float(c2['high']), float(c2['low']), float(c2['close'])

    range0 = max(0.01, h0 - l0)
    body0 = abs(cl0 - o0)
    lower_wick0 = min(o0, cl0) - l0
    upper_wick0 = h0 - max(o0, cl0)

    patterns = []
    bullish_weight = 0
    bearish_weight = 0

    # 1. Bullish Engulfing
    if cl1 < o1 and cl0 > o0 and cl0 >= o1 and o0 <= cl1 and body0 > (abs(cl1 - o1) * 1.1):
        patterns.append({"name": "Bullish Engulfing", "type": "BULLISH", "desc": "Strong buyer takeover engulfing previous bear bar."})
        bullish_weight += 30

    # 2. Bearish Engulfing
    if cl1 > o1 and cl0 < o0 and cl0 <= o1 and o0 >= cl1 and body0 > (abs(cl1 - o1) * 1.1):
        patterns.append({"name": "Bearish Engulfing", "type": "BEARISH", "desc": "Aggressive seller takeover engulfing previous bull bar."})
        bearish_weight += 30

    # 3. Hammer (Bullish Pinbar)
    if lower_wick0 >= (2.0 * body0) and upper_wick0 <= (0.25 * range0) and cl0 >= l0 + (range0 * 0.65):
        patterns.append({"name": "Hammer (Bullish Pinbar)", "type": "BULLISH", "desc": "Rejection of lower lows with heavy buyer absorption."})
        bullish_weight += 25

    # 4. Shooting Star (Bearish Pinbar)
    if upper_wick0 >= (2.0 * body0) and lower_wick0 <= (0.25 * range0) and cl0 <= l0 + (range0 * 0.35):
        patterns.append({"name": "Shooting Star (Bearish Pinbar)", "type": "BEARISH", "desc": "Rejection of overhead highs with heavy seller supply."})
        bearish_weight += 25

    # 5. Morning Star (3-candle bullish reversal)
    if cl2 < o2 and abs(cl1 - o1) <= (abs(cl2 - o2) * 0.4) and cl0 > o0 and cl0 > (o2 + cl2) / 2.0:
        patterns.append({"name": "Morning Star", "type": "BULLISH", "desc": "3-bar institutional reversal sequence confirming bottom."})
        bullish_weight += 35

    # 6. Evening Star (3-candle bearish reversal)
    if cl2 > o2 and abs(cl1 - o1) <= (abs(cl2 - o2) * 0.4) and cl0 < o0 and cl0 < (o2 + cl2) / 2.0:
        patterns.append({"name": "Evening Star", "type": "BEARISH", "desc": "3-bar institutional reversal sequence confirming top."})
        bearish_weight += 35

    # 7. Inside Bar Breakout
    is_c1_inside = (h1 <= h2) and (l1 >= l2)
    if is_c1_inside and cl0 > h1:
        patterns.append({"name": "Inside Bar Bullish Breakout", "type": "BULLISH", "desc": "Coiled range expansion breaking upward."})
        bullish_weight += 20
    elif is_c1_inside and cl0 < l1:
        patterns.append({"name": "Inside Bar Bearish Breakdown", "type": "BEARISH", "desc": "Coiled range expansion breaking downward."})
        bearish_weight += 20

    if bullish_weight > bearish_weight:
        overall_bias = "BULLISH"
        score = min(100, bullish_weight)
    elif bearish_weight > bullish_weight:
        overall_bias = "BEARISH"
        score = min(100, bearish_weight)
    else:
        overall_bias = "NEUTRAL"
        score = 0

    primary = patterns[0]["name"] if patterns else None

    return {
        "patterns": patterns,
        "primary_pattern": primary,
        "bias": overall_bias,
        "reliability_score": score,
        "count": len(patterns)
    }


