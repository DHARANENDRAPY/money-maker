import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any

def label_setup_outcomes(
    df: pd.DataFrame,
    risk_atr_mult: float = 1.0,
    reward_atr_mult: float = 1.8,
    max_holding_bars: int = 12,
    direction: str = "LONG"
) -> Tuple[pd.Series, pd.Series]:
    """
    Labels historical outcomes for hypothetical setups:
    1 = Target reached before Stop Loss
    0 = Stop Loss hit first, or target not reached within max_holding_bars
    
    Conservative Rule: If both Target and Stop Loss are breached within the same candle,
    it is conservatively recorded as a Stop-Loss hit (0).
    """
    n = len(df)
    labels = np.zeros(n, dtype=int)
    r_multiples = np.zeros(n, dtype=float)
    
    if 'atr14' not in df.columns:
        from app.engine.indicators import calculate_atr
        df['atr14'] = calculate_atr(df, 14)
        
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    atrs = df['atr14'].values
    
    for i in range(n - max_holding_bars):
        entry = closes[i]
        atr = atrs[i]
        if atr <= 0 or np.isnan(atr):
            continue
            
        if direction.upper() == "LONG":
            sl = entry - (risk_atr_mult * atr)
            tp = entry + (reward_atr_mult * atr)
            
            outcome_found = False
            for step in range(1, max_holding_bars + 1):
                idx = i + step
                bar_h = highs[idx]
                bar_l = lows[idx]
                
                # Check simultaneous breach (Conservative penalty)
                if bar_h >= tp and bar_l <= sl:
                    labels[i] = 0
                    r_multiples[i] = -1.0
                    outcome_found = True
                    break
                elif bar_l <= sl:
                    labels[i] = 0
                    r_multiples[i] = -1.0
                    outcome_found = True
                    break
                elif bar_h >= tp:
                    labels[i] = 1
                    r_multiples[i] = reward_atr_mult / risk_atr_mult
                    outcome_found = True
                    break
                    
            if not outcome_found:
                # Time exit after max_holding_bars
                exit_price = closes[i + max_holding_bars]
                pnl_r = (exit_price - entry) / (risk_atr_mult * atr)
                labels[i] = 1 if pnl_r > 0 else 0
                r_multiples[i] = pnl_r
                
        else:  # SHORT
            sl = entry + (risk_atr_mult * atr)
            tp = entry - (reward_atr_mult * atr)
            
            outcome_found = False
            for step in range(1, max_holding_bars + 1):
                idx = i + step
                bar_h = highs[idx]
                bar_l = lows[idx]
                
                if bar_l <= tp and bar_h >= sl:
                    labels[i] = 0
                    r_multiples[i] = -1.0
                    outcome_found = True
                    break
                elif bar_h >= sl:
                    labels[i] = 0
                    r_multiples[i] = -1.0
                    outcome_found = True
                    break
                elif bar_l <= tp:
                    labels[i] = 1
                    r_multiples[i] = reward_atr_mult / risk_atr_mult
                    outcome_found = True
                    break
                    
            if not outcome_found:
                exit_price = closes[i + max_holding_bars]
                pnl_r = (entry - exit_price) / (risk_atr_mult * atr)
                labels[i] = 1 if pnl_r > 0 else 0
                r_multiples[i] = pnl_r
                
    return pd.Series(labels, index=df.index), pd.Series(r_multiples, index=df.index)
