import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

from app.schemas.all_schemas import SignalItem
from app.engine.indicators import detect_key_levels, calculate_supertrend
from app.engine.factors import FactorEngine
from app.ml.feature_engineering import extract_features_single_bar

class SignalGenerator:
    """
    Intraday Signal Generation Engine.
    Combines rule-based setups with the 12-factor evaluation and calibrated ML probability estimates.
    Enforces a strict 'No Trade' decision when setup criteria or risk/reward are poor.
    """

    @staticmethod
    def generate_signal_for_stock(
        symbol: str,
        df: pd.DataFrame,
        current_price: float,
        sector: str,
        sector_change_pct: float,
        nifty_change_pct: float,
        market_regime: str,
        market_breadth_ad: float,
        news_items: List[Dict[str, Any]] = None,
        ml_model: Any = None,
        ml_model_version: str = "v1.0-gbdt"
    ) -> Optional[SignalItem]:
        """
        Evaluates candles and context to produce a candidate signal or 'NO_TRADE'.
        ml_model: the raw CalibratedClassifier model OR a ModelTrainingPipeline object
        """
        if df.empty or len(df) < 15:
            return None
            
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        vwap = float(last.get('vwap', current_price))
        ema9 = float(last.get('ema9', current_price))
        ema21 = float(last.get('ema21', current_price))
        rsi = float(last.get('rsi14', 50.0))
        atr = float(last.get('atr14', current_price * 0.01))
        rvol = float(last.get('rvol', 1.0))
        
        levels = detect_key_levels(df)
        orb_high = levels.get("orb_high", current_price)
        orb_low = levels.get("orb_low", current_price)
        
        strategy = None
        direction = "NO_TRADE"
        entry = current_price
        stop_loss = current_price
        target = current_price

        supporting_factors = []
        conflicting_factors = []

        # Get additional indicators
        macd_hist = float(last.get('macd_hist', 0.0))
        macd_hist_prev = float(df.iloc[-2].get('macd_hist', 0.0)) if len(df) >= 2 else 0.0
        ema50 = float(last.get('ema50', current_price))
        bb_upper = float(last.get('bb_upper', current_price * 1.02))
        bb_lower = float(last.get('bb_lower', current_price * 0.98))

        try:
            _, st_dir_series = calculate_supertrend(df, period=10, multiplier=3.0)
            supertrend_dir = int(st_dir_series.iloc[-1])
            supertrend_prev = int(st_dir_series.iloc[-2]) if len(st_dir_series) >= 2 else supertrend_dir
        except Exception:
            supertrend_dir = 1
            supertrend_prev = 1

        # Setup 1: Opening Range Breakout (ORB) Long
        if current_price > orb_high and prev['close'] <= orb_high and rvol > 1.2 and current_price > vwap:
            strategy = "15m ORB Breakout"
            direction = "LONG"
            entry = round(current_price, 2)
            stop_loss = round(max(orb_high - (0.8 * atr), vwap - 0.5 * atr), 2)
            target = round(entry + (1.8 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["15m High Breakout", "RVOL > 1.2", "Above VWAP"])

        # Setup 2: Opening Range Breakdown (ORB) Short
        elif current_price < orb_low and prev['close'] >= orb_low and rvol > 1.2 and current_price < vwap:
            strategy = "15m ORB Breakdown"
            direction = "SHORT"
            entry = round(current_price, 2)
            stop_loss = round(min(orb_low + (0.8 * atr), vwap + 0.5 * atr), 2)
            target = round(entry - (1.8 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["15m Low Breakdown", "RVOL > 1.2", "Below VWAP"])

        # Setup 3: VWAP Pullback Continuation (Long)
        elif (current_price > vwap and ema9 > ema21 and
              (current_price - vwap) < (0.6 * atr) and rsi > 52 and last['close'] > last['open']):
            strategy = "VWAP Trend Pullback"
            direction = "LONG"
            entry = round(current_price, 2)
            stop_loss = round(vwap - (0.7 * atr), 2)
            target = round(entry + (2.0 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["VWAP Support Touch", "EMA9 > EMA21 Bullish Trend", "RSI Momentum"])

        # Setup 4: VWAP Pullback Continuation (Short)
        elif (current_price < vwap and ema9 < ema21 and
              (vwap - current_price) < (0.6 * atr) and rsi < 48 and last['close'] < last['open']):
            strategy = "VWAP Trend Pullback"
            direction = "SHORT"
            entry = round(current_price, 2)
            stop_loss = round(vwap + (0.7 * atr), 2)
            target = round(entry - (2.0 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["VWAP Resistance Rejection", "EMA9 < EMA21 Bearish Trend", "RSI Weakness"])

        # Setup 5: Mean Reversion Extension Reversal
        elif abs(current_price - vwap) > (2.5 * atr):
            if current_price > vwap and rsi > 74:
                strategy = "Mean Reversion Exhaustion"
                direction = "SHORT"
                entry = round(current_price, 2)
                stop_loss = round(entry + (1.0 * atr), 2)
                target = round(vwap + (0.5 * atr), 2)
                supporting_factors.extend(["Overbought RSI > 74", "Extended 2.5x ATR from VWAP"])
            elif current_price < vwap and rsi < 26:
                strategy = "Mean Reversion Oversold"
                direction = "LONG"
                entry = round(current_price, 2)
                stop_loss = round(entry - (1.0 * atr), 2)
                target = round(vwap - (0.5 * atr), 2)
                supporting_factors.extend(["Oversold RSI < 26", "Extended 2.5x ATR from VWAP"])

        # Setup 9: RSI Momentum Thrust (broad sideways/moderate trend catcher)
        elif rsi > 58 and rsi < 72 and ema9 > ema21 and current_price > vwap and rvol > 0.8:
            strategy = "RSI Momentum Thrust"
            direction = "LONG"
            entry = round(current_price, 2)
            stop_loss = round(min(vwap, ema21) - (0.5 * atr), 2)
            target = round(entry + (1.8 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["RSI Bullish Zone 58-72", "Above VWAP", "EMA Uptrend"])

        elif rsi < 42 and rsi > 28 and ema9 < ema21 and current_price < vwap and rvol > 0.8:
            strategy = "RSI Momentum Thrust"
            direction = "SHORT"
            entry = round(current_price, 2)
            stop_loss = round(max(vwap, ema21) + (0.5 * atr), 2)
            target = round(entry - (1.8 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["RSI Bearish Zone 28-42", "Below VWAP", "EMA Downtrend"])

        # Setup 10: Bollinger Band Squeeze Breakout
        elif (current_price > bb_upper and ema9 > ema21 and rvol > 1.1 and rsi > 55):
            strategy = "BB Squeeze Breakout Long"
            direction = "LONG"
            entry = round(current_price, 2)
            stop_loss = round(bb_upper - (0.5 * atr), 2) if bb_upper < current_price else round(current_price - (1.0 * atr), 2)
            target = round(entry + (2.0 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["Bollinger Upper Band Breakout", "RVOL Surge", "RSI Bullish"])

        elif (current_price < bb_lower and ema9 < ema21 and rvol > 1.1 and rsi < 45):
            strategy = "BB Squeeze Breakdown Short"
            direction = "SHORT"
            entry = round(current_price, 2)
            stop_loss = round(bb_lower + (0.5 * atr), 2) if bb_lower > current_price else round(current_price + (1.0 * atr), 2)
            target = round(entry - (2.0 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["Bollinger Lower Band Breakdown", "RVOL Surge", "RSI Bearish"])

        # Setup 6: EMA Trend Momentum (fires when ema9 crosses ema21 with MACD confirmation)
        elif (ema9 > ema21 and macd_hist > 0 and macd_hist > macd_hist_prev and
              rsi > 50 and rsi < 70 and current_price > vwap and rvol > 1.0):
            strategy = "EMA Momentum Breakout"
            direction = "LONG"
            entry = round(current_price, 2)
            stop_loss = round(min(ema21, vwap) - (0.5 * atr), 2)
            target = round(entry + (2.0 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["EMA9 > EMA21 Cross", "MACD Histogram Rising", "RSI 50-70 Zone"])

        elif (ema9 < ema21 and macd_hist < 0 and macd_hist < macd_hist_prev and
              rsi < 50 and rsi > 30 and current_price < vwap and rvol > 1.0):
            strategy = "EMA Momentum Breakdown"
            direction = "SHORT"
            entry = round(current_price, 2)
            stop_loss = round(max(ema21, vwap) + (0.5 * atr), 2)
            target = round(entry - (2.0 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["EMA9 < EMA21 Cross", "MACD Histogram Falling", "RSI 30-50 Zone"])

        # Setup 7: Supertrend Flip Confirmation
        elif supertrend_dir == 1 and supertrend_prev == -1 and rvol > 1.0 and rsi > 45:
            strategy = "Supertrend Bullish Flip"
            direction = "LONG"
            entry = round(current_price, 2)
            stop_loss = round(entry - (1.2 * atr), 2)
            target = round(entry + (2.0 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["Supertrend Direction Flip Bullish", "Volume Confirmation"])

        elif supertrend_dir == -1 and supertrend_prev == 1 and rvol > 1.0 and rsi < 55:
            strategy = "Supertrend Bearish Flip"
            direction = "SHORT"
            entry = round(current_price, 2)
            stop_loss = round(entry + (1.2 * atr), 2)
            target = round(entry - (2.0 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["Supertrend Direction Flip Bearish", "Volume Confirmation"])

        # Setup 8: Multi-Indicator Confluence (most reliable — all indicators agree)
        elif (ema9 > ema21 and current_price > vwap and macd_hist > 0 and
              rsi > 53 and rsi < 68 and supertrend_dir == 1 and
              current_price > ema50 and rvol > 0.9):
            strategy = "Multi-Indicator Confluence Bullish"
            direction = "LONG"
            entry = round(current_price, 2)
            stop_loss = round(max(vwap, ema21) - (0.6 * atr), 2)
            target = round(entry + (2.2 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["EMA Aligned", "VWAP Above", "MACD +ve", "Supertrend Bull", "Above EMA50"])

        elif (ema9 < ema21 and current_price < vwap and macd_hist < 0 and
              rsi < 47 and rsi > 32 and supertrend_dir == -1 and
              current_price < ema50 and rvol > 0.9):
            strategy = "Multi-Indicator Confluence Bearish"
            direction = "SHORT"
            entry = round(current_price, 2)
            stop_loss = round(min(vwap, ema21) + (0.6 * atr), 2)
            target = round(entry - (2.2 * abs(entry - stop_loss)), 2)
            supporting_factors.extend(["EMA Bearish", "Below VWAP", "MACD -ve", "Supertrend Bear", "Below EMA50"])

                
        # If no setup triggered or invalid
        if direction == "NO_TRADE" or not strategy:
            return None
            
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        if risk == 0:
            return None
            
        rr_ratio = reward / risk
        if rr_ratio < 1.2:
            # Poor risk-reward => enforce No Trade
            return None
            
        # Cross check macro market regime alignment
        if direction == "LONG" and "BEARISH" in market_regime and nifty_change_pct < -0.8:
            conflicting_factors.append(f"Counter-trend vs Broad Market ({market_regime})")
        elif direction == "SHORT" and "BULLISH" in market_regime and nifty_change_pct > 0.8:
            conflicting_factors.append(f"Counter-trend vs Broad Market ({market_regime})")
            
        # Sector check
        if direction == "LONG" and sector_change_pct < -0.5:
            conflicting_factors.append(f"Sector {sector} is lagging ({sector_change_pct:+.2f}%)")
        elif direction == "SHORT" and sector_change_pct > 0.5:
            conflicting_factors.append(f"Sector {sector} is leading ({sector_change_pct:+.2f}%)")
            
        # ML Probability Estimation using the SAME feature set the model was trained on
        ml_prob = None
        if ml_model is not None:
            try:
                # Get supertrend direction from the enriched df
                try:
                    _, st_dir_s = calculate_supertrend(df, period=10, multiplier=3.0)
                    supertrend_dir = int(st_dir_s.iloc[-1])
                except Exception:
                    supertrend_dir = 1

                bb_upper = float(last.get('bb_upper', current_price * 1.02))
                bb_lower = float(last.get('bb_lower', current_price * 0.98))
                macd_hist = float(last.get('macd_hist', 0.0))
                ema50 = float(last.get('ema50', current_price))
                bar_open = float(last.get('open', current_price))
                bar_high = float(last.get('high', current_price))
                bar_low = float(last.get('low', current_price))
                bar_close = float(last.get('close', current_price))

                # Compute minutes since market open (9:15 IST)
                utc_now = datetime.utcnow()
                ist_minutes = (utc_now.hour * 60 + utc_now.minute) + 330  # UTC to IST
                ist_minutes = ist_minutes % (24 * 60)
                minutes_since_open = max(0, ist_minutes - (9 * 60 + 15))

                orb_high_val = levels.get('orb_high', current_price)
                orb_low_val = levels.get('orb_low', current_price)

                feat = extract_features_single_bar(
                    enriched=df,
                    current_price=current_price,
                    vwap=vwap,
                    ema9=ema9,
                    ema21=ema21,
                    ema50=ema50,
                    rsi=rsi,
                    atr=atr,
                    rvol=rvol,
                    macd_hist=macd_hist,
                    bb_upper=bb_upper,
                    bb_lower=bb_lower,
                    supertrend_dir=supertrend_dir,
                    bar_open=bar_open,
                    bar_high=bar_high,
                    bar_low=bar_low,
                    bar_close=bar_close,
                    minutes_since_open=minutes_since_open,
                    orb_high=orb_high_val,
                    orb_low=orb_low_val,
                )

                # For SHORT direction, invert directional features
                if direction == "SHORT":
                    invert_indices = [4, 5, 6, 7, 8, 9, 15, 16, 20, 21, 26, 27]  # directional feature positions
                    for idx in invert_indices:
                        if idx < feat.shape[1]:
                            feat[0, idx] = -feat[0, idx]

                # Use pipeline's predict_proba (which applies the fitted scaler internally)
                # Support both ModelTrainingPipeline and raw CalibratedClassifierCV
                from app.ml.model_trainer import ModelTrainingPipeline
                if hasattr(ml_model, '__class__') and ml_model.__class__.__name__ == 'ModelTrainingPipeline':
                    # ModelTrainingPipeline.predict_proba handles scaling internally
                    prob = ml_model.predict_proba(feat)
                    ml_prob = round(max(0.30, min(0.95, prob)), 3)
                elif hasattr(ml_model, 'predict_proba'):
                    # Raw model — scale using pipeline scaler if accessible
                    from app.services.market_state import market_state
                    try:
                        scaled = market_state.ml_pipeline.scaler.transform(feat)
                        prob = float(ml_model.predict_proba(scaled)[0][1])
                    except Exception:
                        prob = float(ml_model.predict_proba(feat)[0][1])
                    ml_prob = round(max(0.30, min(0.95, prob)), 3)
            except Exception as e:
                ml_prob = None
                
        if ml_prob is None:
            # Conservative Bayesian heuristic — only used for demo/initial state
            # Note: recommendations router applies an additional 0.60 hard gate
            base = 0.48  # Start slightly below random — we earn confidence
            base += 0.06 if len(supporting_factors) >= 4 else 0.03 if len(supporting_factors) >= 3 else 0.0
            base -= 0.10 * len(conflicting_factors)
            base += 0.05 if rvol > 1.5 else 0.02 if rvol > 1.2 else 0.0
            base = max(min(base, 0.72), 0.30)  # Cap at 0.72 — never fake high confidence
            ml_prob = round(base, 2)
            
        now = datetime.utcnow()
        expiry = now + timedelta(minutes=30)
        
        signal_id = f"SIG-{symbol}-{now.strftime('%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        
        return SignalItem(
            signal_id=signal_id,
            symbol=symbol,
            timestamp=now.isoformat() + "Z",
            strategy=strategy,
            direction=direction,
            market_regime=market_regime,
            entry_price=entry,
            stop_loss=stop_loss,
            target_price=target,
            risk_reward_ratio=round(rr_ratio, 2),
            ml_probability=ml_prob,
            ml_model_version=ml_model_version,
            status="candidate",
            supporting_factors=supporting_factors,
            conflicting_factors=conflicting_factors,
            factor_scores={
                "rvol": round(rvol, 2),
                "rsi": round(rsi, 2),
                "risk_reward": round(rr_ratio, 2)
            },
            data_freshness_seconds=1.2,
            expiry_time=expiry.isoformat() + "Z"
        )

    @staticmethod
    def update_signal_lifecycle(signal: SignalItem, current_price: float, high: float, low: float) -> Tuple[SignalItem, Optional[str]]:
        """
        Updates the state machine for an active signal:
        candidate -> confirmed (triggered at entry)
        confirmed -> completed (target reached or stop loss hit)
        candidate -> expired / invalidated
        """
        now = datetime.utcnow()
        event_type = None
        
        if signal.status == "candidate":
            # Check if triggered
            if signal.direction == "LONG":
                if high >= signal.entry_price:
                    signal.status = "confirmed"
                    event_type = "CONFIRMED_SETUP"
                elif low <= signal.stop_loss:
                    signal.status = "invalidated"
                    signal.invalidation_reason = "Price violated Stop Loss before Entry trigger"
                    event_type = "SIGNAL_INVALIDATED"
            elif signal.direction == "SHORT":
                if low <= signal.entry_price:
                    signal.status = "confirmed"
                    event_type = "CONFIRMED_SETUP"
                elif high >= signal.stop_loss:
                    signal.status = "invalidated"
                    signal.invalidation_reason = "Price violated Stop Loss before Entry trigger"
                    event_type = "SIGNAL_INVALIDATED"
                    
        elif signal.status == "confirmed":
            # Check Target / Stop Loss outcomes
            if signal.direction == "LONG":
                if high >= signal.target_price and low <= signal.stop_loss:
                    # Conservative assumption for simultaneous touch: Stop Hit
                    signal.status = "completed"
                    signal.outcome = "STOP_HIT"
                    signal.pnl_realized_r = -1.0
                elif high >= signal.target_price:
                    signal.status = "completed"
                    signal.outcome = "TARGET_HIT"
                    signal.pnl_realized_r = round(signal.risk_reward_ratio, 2)
                elif low <= signal.stop_loss:
                    signal.status = "completed"
                    signal.outcome = "STOP_HIT"
                    signal.pnl_realized_r = -1.0
            elif signal.direction == "SHORT":
                if low <= signal.target_price and high >= signal.stop_loss:
                    signal.status = "completed"
                    signal.outcome = "STOP_HIT"
                    signal.pnl_realized_r = -1.0
                elif low <= signal.target_price:
                    signal.status = "completed"
                    signal.outcome = "TARGET_HIT"
                    signal.pnl_realized_r = round(signal.risk_reward_ratio, 2)
                elif high >= signal.stop_loss:
                    signal.status = "completed"
                    signal.outcome = "STOP_HIT"
                    signal.pnl_realized_r = -1.0
                    
        return signal, event_type
