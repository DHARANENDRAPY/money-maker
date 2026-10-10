import math
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime
from app.schemas.market_schemas import FactorEvaluation
from app.engine.indicators import detect_key_levels

class FactorEngine:
    """
    Evaluates the 12 Trading Factors independently for any given stock.
    Each factor returns a normalized score (-1.0 to +1.0), status, and transparent explanation.
    """

    @staticmethod
    def evaluate_factor_1_market_trend(
        nifty_change_pct: float,
        nifty_above_ema20: bool,
        market_breadth_ad_ratio: float,
        market_regime: str
    ) -> FactorEvaluation:
        """Factor 1: Overall Market Trend."""
        score = 0.0
        details = {
            "nifty_change_pct": nifty_change_pct,
            "nifty_above_ema20": nifty_above_ema20,
            "advance_decline_ratio": market_breadth_ad_ratio,
            "regime": market_regime
        }
        
        # Calculate composite score
        if nifty_change_pct > 0.5 and nifty_above_ema20:
            score += 0.5
        elif nifty_change_pct < -0.5 and not nifty_above_ema20:
            score -= 0.5
        else:
            score += (nifty_change_pct / 2.0)
            
        if market_breadth_ad_ratio > 1.5:
            score += 0.4
        elif market_breadth_ad_ratio < 0.67:
            score -= 0.4
            
        score = max(min(score, 1.0), -1.0)
        
        status = "SUPPORTIVE" if score > 0.25 else ("CONFLICTING" if score < -0.25 else "NEUTRAL")
        summary = f"Broad Market is {market_regime.replace('_', ' ')} (NIFTY {nifty_change_pct:+.2f}%, A/D Ratio {market_breadth_ad_ratio:.2f})."
        
        return FactorEvaluation(
            factor_id=1,
            name="Overall Market Trend",
            category="Macro & Market Context",
            score=round(score, 2),
            status=status,
            weight_desc="High",
            summary=summary,
            details=details,
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_2_sector_performance(
        stock_sector: str,
        sector_change_pct: float,
        nifty_change_pct: float,
        sector_relative_strength: float
    ) -> FactorEvaluation:
        """Factor 2: Sector Performance & Relative Strength."""
        rel_strength = sector_change_pct - nifty_change_pct
        score = max(min(rel_strength / 1.5, 1.0), -1.0)
        
        status = "SUPPORTIVE" if score > 0.25 else ("CONFLICTING" if score < -0.25 else "NEUTRAL")
        bias_str = "Outperforming" if rel_strength > 0 else "Underperforming"
        summary = f"{stock_sector} is {bias_str} Nifty by {rel_strength:+.2f}% ({sector_change_pct:+.2f}% vs {nifty_change_pct:+.2f}%)."
        
        return FactorEvaluation(
            factor_id=2,
            name="Sector Performance",
            category="Macro & Market Context",
            score=round(score, 2),
            status=status,
            weight_desc="Medium-High",
            summary=summary,
            details={
                "sector": stock_sector,
                "sector_change_pct": sector_change_pct,
                "nifty_change_pct": nifty_change_pct,
                "relative_strength_spread": round(rel_strength, 2),
                "sector_momentum_rank": round(sector_relative_strength, 2)
            },
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_3_news_events(
        news_items: List[Dict[str, Any]]
    ) -> FactorEvaluation:
        """Factor 3: News and Events with Sentiment Analysis."""
        if not news_items:
            return FactorEvaluation(
                factor_id=3,
                name="News & Events",
                category="Information Flow",
                score=0.0,
                status="NEUTRAL",
                weight_desc="Medium",
                summary="No major corporate announcement or high-impact news detected today.",
                details={"news_count": 0, "sentiment_scores": []},
                uncertainty_level="MODERATE"
            )
            
        scores = [item.get("sentiment_score", 0.0) for item in news_items]
        avg_score = float(np.mean(scores))
        avg_score = max(min(avg_score, 1.0), -1.0)
        
        top_headline = news_items[0].get("headline", "")
        status = "SUPPORTIVE" if avg_score > 0.25 else ("CONFLICTING" if avg_score < -0.25 else "NEUTRAL")
        summary = f"News sentiment is {'Positive' if avg_score > 0 else 'Cautious/Negative'} ({len(news_items)} updates). Top: {top_headline[:60]}..."
        
        return FactorEvaluation(
            factor_id=3,
            name="News & Events",
            category="Information Flow",
            score=round(avg_score, 2),
            status=status,
            weight_desc="Medium",
            summary=summary,
            details={"news_count": len(news_items), "headlines": [n.get("headline") for n in news_items[:3]]},
            uncertainty_level="LOW" if len(news_items) > 0 else "MODERATE"
        )

    @staticmethod
    def evaluate_factor_4_price_action(
        df: pd.DataFrame,
        current_price: float
    ) -> FactorEvaluation:
        """Factor 4: Price Action (ORB, PDH/PDL, Support/Resistance)."""
        if df.empty or len(df) < 5:
            return FactorEvaluation(
                factor_id=4,
                name="Price Action",
                category="Technical Structure",
                score=0.0,
                status="UNAVAILABLE",
                weight_desc="Very High",
                summary="Insufficient intraday candle data for price action analysis.",
                details={},
                uncertainty_level="HIGH"
            )
            
        levels = detect_key_levels(df)
        orb_high = levels.get("orb_high", current_price)
        orb_low = levels.get("orb_low", current_price)
        day_open = levels.get("day_open", current_price)
        
        score = 0.0
        notes = []
        
        # Opening Range Breakout / Breakdown
        if current_price > orb_high:
            score += 0.5
            notes.append("Trading above 15m Opening Range High")
        elif current_price < orb_low:
            score -= 0.5
            notes.append("Trading below 15m Opening Range Low")
        else:
            notes.append("Inside 15m Opening Range")
            
        # Day Open comparison
        if current_price > day_open:
            score += 0.3
            notes.append("Above Open price")
        else:
            score -= 0.3
            notes.append("Below Open price")
            
        # Recent candle rejection wicks
        last_candle = df.iloc[-1]
        candle_range = last_candle['high'] - last_candle['low']
        if candle_range > 0:
            lower_wick = min(last_candle['open'], last_candle['close']) - last_candle['low']
            upper_wick = last_candle['high'] - max(last_candle['open'], last_candle['close'])
            if lower_wick / candle_range > 0.4:
                score += 0.2
                notes.append("Bullish lower wick rejection")
            elif upper_wick / candle_range > 0.4:
                score -= 0.2
                notes.append("Bearish upper wick rejection")
                
        score = max(min(score, 1.0), -1.0)
        status = "SUPPORTIVE" if score > 0.25 else ("CONFLICTING" if score < -0.25 else "NEUTRAL")
        summary = " | ".join(notes)
        
        return FactorEvaluation(
            factor_id=4,
            name="Price Action",
            category="Technical Structure",
            score=round(score, 2),
            status=status,
            weight_desc="Very High",
            summary=summary,
            details=levels,
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_5_volume_order_flow(
        df: pd.DataFrame,
        current_volume: int,
        rvol: float,
        order_imbalance_ratio: Optional[float] = None
    ) -> FactorEvaluation:
        """Factor 5: Volume and Order Flow."""
        if df.empty or len(df) < 5:
            return FactorEvaluation(
                factor_id=5,
                name="Volume & Order Flow",
                category="Participation & Flow",
                score=0.0,
                status="UNAVAILABLE",
                weight_desc="High",
                summary="Insufficient volume data.",
                details={},
                uncertainty_level="HIGH"
            )
            
        score = 0.0
        notes = []
        
        # RVOL assessment
        if rvol > 2.0:
            notes.append(f"High RVOL ({rvol:.1f}x normal)")
            score += 0.4 if df['close'].iloc[-1] > df['open'].iloc[-1] else -0.4
        elif rvol > 1.2:
            notes.append(f"Moderate RVOL ({rvol:.1f}x normal)")
            score += 0.2 if df['close'].iloc[-1] > df['open'].iloc[-1] else -0.2
        else:
            notes.append(f"Low RVOL ({rvol:.1f}x normal - below average)")
            score += 0.0
            
        # Price-Volume Confirmation
        recent_price_chg = df['close'].iloc[-1] - df['close'].iloc[-3]
        recent_vol_chg = df['volume'].iloc[-1] - df['volume'].iloc[-3]
        if recent_price_chg > 0 and recent_vol_chg > 0:
            score += 0.3
            notes.append("Expanding volume on price rise")
        elif recent_price_chg < 0 and recent_vol_chg > 0:
            score -= 0.3
            notes.append("Expanding volume on price fall")
            
        # Orderbook Imbalance if available from live feed
        if order_imbalance_ratio is not None:
            if order_imbalance_ratio > 1.3:
                score += 0.3
                notes.append(f"Buy depth dominance ({order_imbalance_ratio:.2f})")
            elif order_imbalance_ratio < 0.77:
                score -= 0.3
                notes.append(f"Sell depth dominance ({order_imbalance_ratio:.2f})")
                
        score = max(min(score, 1.0), -1.0)
        status = "SUPPORTIVE" if score > 0.2 else ("CONFLICTING" if score < -0.2 else "NEUTRAL")
        
        return FactorEvaluation(
            factor_id=5,
            name="Volume & Order Flow",
            category="Participation & Flow",
            score=round(score, 2),
            status=status,
            weight_desc="High",
            summary=" | ".join(notes),
            details={
                "rvol": round(rvol, 2),
                "current_volume": current_volume,
                "order_imbalance": round(order_imbalance_ratio, 2) if order_imbalance_ratio else None
            },
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_6_volatility(
        df: pd.DataFrame,
        current_price: float,
        atr: float
    ) -> FactorEvaluation:
        """Factor 6: Volatility (ATR, Realized Intraday Range, Volatility Contraction)."""
        if df.empty or atr <= 0:
            return FactorEvaluation(
                factor_id=6,
                name="Volatility Range",
                category="Risk & Regimes",
                score=0.0,
                status="UNAVAILABLE",
                weight_desc="Medium",
                summary="Insufficient volatility data.",
                details={},
                uncertainty_level="HIGH"
            )
            
        day_range = df['high'].max() - df['low'].min()
        atr_pct = (atr / current_price) * 100.0
        day_range_atr_ratio = day_range / atr if atr > 0 else 1.0
        
        # Volatility is generally directional-neutral but sets target/stop feasibility
        summary = f"ATR(14) is ₹{atr:.2f} ({atr_pct:.2f}% of price). Day range is {day_range_atr_ratio:.1f}x ATR."
        score = 0.2 if 1.0 <= day_range_atr_ratio <= 2.5 else (-0.2 if day_range_atr_ratio > 3.0 else 0.0)
        
        return FactorEvaluation(
            factor_id=6,
            name="Volatility Range",
            category="Risk & Regimes",
            score=round(score, 2),
            status="SUPPORTIVE" if abs(score) <= 0.2 else "NEUTRAL",
            weight_desc="Medium",
            summary=summary,
            details={
                "atr": round(atr, 2),
                "atr_pct": round(atr_pct, 2),
                "intraday_range": round(day_range, 2),
                "range_to_atr_multiple": round(day_range_atr_ratio, 2)
            },
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_7_liquidity_execution(
        spread_pct: float,
        turnover_crores: float
    ) -> FactorEvaluation:
        """Factor 7: Liquidity & Execution Feasibility (Bid-Ask Spread & Turnover)."""
        # Low spread and high turnover = highly liquid, high execution safety
        score = 0.0
        if spread_pct <= 0.03 and turnover_crores >= 50:
            score = 0.8
            status = "SUPPORTIVE"
            summary = f"Excellent institutional liquidity (Spread {spread_pct:.3f}%, Turnover ₹{turnover_crores:.1f} Cr)."
        elif spread_pct <= 0.08 and turnover_crores >= 10:
            score = 0.4
            status = "SUPPORTIVE"
            summary = f"Adequate intraday liquidity (Spread {spread_pct:.3f}%, Turnover ₹{turnover_crores:.1f} Cr)."
        else:
            score = -0.5
            status = "CONFLICTING"
            summary = f"Thin liquidity / wide spread ({spread_pct:.3f}%). Slippage risk elevated."
            
        return FactorEvaluation(
            factor_id=7,
            name="Liquidity & Execution",
            category="Execution Quality",
            score=round(score, 2),
            status=status,
            weight_desc="Medium-High",
            summary=summary,
            details={
                "bid_ask_spread_pct": round(spread_pct, 4),
                "turnover_inr_crores": round(turnover_crores, 2)
            },
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_8_time_of_day(
        current_time_ist: Optional[str] = None
    ) -> FactorEvaluation:
        """Factor 8: Time-of-Day Effects for Indian Market (09:15 to 15:30 IST)."""
        now = datetime.now()
        curr_time_str = current_time_ist or now.strftime("%H:%M")
        
        # Session slots
        if "09:15" <= curr_time_str < "09:45":
            score = 0.3
            phase = "Opening Discovery (09:15-09:45)"
            summary = "High volatility opening auction & ORB setup zone. Use confirmed closes."
        elif "09:45" <= curr_time_str < "11:30":
            score = 0.7
            phase = "Prime Trend Window (09:45-11:30)"
            summary = "Optimal intraday liquidity and highest signal follow-through probability."
        elif "11:30" <= curr_time_str < "13:30":
            score = -0.2
            phase = "Midday Consolidation (11:30-13:30)"
            summary = "Lower volume, false breakouts frequent. Tighten risk parameters."
        elif "13:30" <= curr_time_str < "15:00":
            score = 0.5
            phase = "Afternoon Momentum / European Open (13:30-15:00)"
            summary = "Second expansion leg, good institutional flow."
        elif "15:00" <= curr_time_str <= "15:30":
            score = -0.8
            phase = "MIS Square-Off Window (15:00-15:30)"
            summary = "Intraday position unwind phase. High slippage & erratic moves. New trades discouraged."
        else:
            score = 0.0
            phase = "Pre/Post Market"
            summary = "Market is closed. Analysis is purely reflective."
            
        status = "SUPPORTIVE" if score >= 0.3 else ("CONFLICTING" if score <= -0.3 else "NEUTRAL")
        
        return FactorEvaluation(
            factor_id=8,
            name="Time-of-Day Context",
            category="Temporal Seasonality",
            score=round(score, 2),
            status=status,
            weight_desc="High",
            summary=f"{phase}: {summary}",
            details={"current_ist": curr_time_str, "market_phase": phase},
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_9_technical_indicators(
        df: pd.DataFrame,
        current_price: float
    ) -> FactorEvaluation:
        """Factor 9: Technical Indicators (VWAP, EMA9/21, RSI, MACD)."""
        if df.empty or len(df) < 20:
            return FactorEvaluation(
                factor_id=9,
                name="Technical Indicators",
                category="Quantitative Indicators",
                score=0.0,
                status="UNAVAILABLE",
                weight_desc="Very High",
                summary="Insufficient bars for indicator computation.",
                details={},
                uncertainty_level="HIGH"
            )
            
        last = df.iloc[-1]
        vwap = last.get('vwap', current_price)
        ema9 = last.get('ema9', current_price)
        ema21 = last.get('ema21', current_price)
        rsi = last.get('rsi14', 50.0)
        macd_hist = last.get('macd_hist', 0.0)
        
        score = 0.0
        notes = []
        
        # VWAP positioning
        if current_price > vwap:
            score += 0.35
            notes.append("Above VWAP (Bullish Institutional Benchmark)")
        else:
            score -= 0.35
            notes.append("Below VWAP (Bearish Institutional Benchmark)")
            
        # EMA trend
        if ema9 > ema21 and current_price > ema9:
            score += 0.3
            notes.append("EMA 9 > EMA 21 Alignment")
        elif ema9 < ema21 and current_price < ema9:
            score -= 0.3
            notes.append("EMA 9 < EMA 21 Alignment")
            
        # RSI Momentum
        if 55 <= rsi <= 70:
            score += 0.2
            notes.append(f"RSI in Bullish Momentum zone ({rsi:.1f})")
        elif 30 <= rsi <= 45:
            score -= 0.2
            notes.append(f"RSI in Bearish Momentum zone ({rsi:.1f})")
        elif rsi > 75:
            notes.append(f"RSI Overbought ({rsi:.1f})")
        elif rsi < 25:
            notes.append(f"RSI Oversold ({rsi:.1f})")
            
        # MACD Histogram
        if macd_hist > 0:
            score += 0.15
        else:
            score -= 0.15
            
        score = max(min(score, 1.0), -1.0)
        status = "SUPPORTIVE" if score > 0.25 else ("CONFLICTING" if score < -0.25 else "NEUTRAL")
        
        return FactorEvaluation(
            factor_id=9,
            name="Technical Indicators",
            category="Quantitative Indicators",
            score=round(score, 2),
            status=status,
            weight_desc="Very High",
            summary=" | ".join(notes),
            details={
                "vwap": round(vwap, 2),
                "ema9": round(ema9, 2),
                "ema21": round(ema21, 2),
                "rsi14": round(rsi, 2),
                "macd_histogram": round(macd_hist, 3)
            },
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_10_risk_management(
        entry: float,
        stop_loss: float,
        target: float,
        direction: str
    ) -> FactorEvaluation:
        """Factor 10: Risk Management & Reward/Risk Feasibility."""
        if stop_loss == entry or entry == 0:
            return FactorEvaluation(
                factor_id=10,
                name="Risk/Reward Structure",
                category="Risk & Geometry",
                score=-1.0,
                status="CONFLICTING",
                weight_desc="Crucial",
                summary="Invalid Stop-Loss or Entry level.",
                details={},
                uncertainty_level="HIGH"
            )
            
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
        score = 0.0
        if rr_ratio >= 2.0:
            score = 0.9
            status = "SUPPORTIVE"
            summary = f"Favorable Asymmetry: Risk/Reward ratio is 1:{rr_ratio:.2f} (Target ₹{target:.2f}, SL ₹{stop_loss:.2f})."
        elif rr_ratio >= 1.5:
            score = 0.5
            status = "SUPPORTIVE"
            summary = f"Acceptable Asymmetry: Risk/Reward ratio is 1:{rr_ratio:.2f}."
        elif rr_ratio >= 1.0:
            score = -0.2
            status = "NEUTRAL"
            summary = f"Suboptimal Risk/Reward (1:{rr_ratio:.2f}). Minimum recommended threshold is 1:1.5."
        else:
            score = -0.8
            status = "CONFLICTING"
            summary = f"Unfavorable Risk/Reward (1:{rr_ratio:.2f}). Risk exceeds potential upside."
            
        return FactorEvaluation(
            factor_id=10,
            name="Risk/Reward Structure",
            category="Risk & Geometry",
            score=round(score, 2),
            status=status,
            weight_desc="Crucial",
            summary=summary,
            details={
                "entry": round(entry, 2),
                "stop_loss": round(stop_loss, 2),
                "target": round(target, 2),
                "risk_points": round(risk, 2),
                "reward_points": round(reward, 2),
                "risk_reward_ratio": round(rr_ratio, 2)
            },
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_11_data_latency_freshness(
        freshness_seconds: float
    ) -> FactorEvaluation:
        """Factor 11: Execution Speed & Data Latency."""
        if freshness_seconds <= 2.0:
            score = 0.9
            status = "SUPPORTIVE"
            summary = f"Real-time stream (Age: {freshness_seconds:.1f}s). Latency is optimal."
        elif freshness_seconds <= 10.0:
            score = 0.4
            status = "SUPPORTIVE"
            summary = f"Acceptable data freshness ({freshness_seconds:.1f}s age)."
        elif freshness_seconds <= 60.0:
            score = -0.3
            status = "NEUTRAL"
            summary = f"Slightly delayed quote ({freshness_seconds:.1f}s age)."
        else:
            score = -0.9
            status = "CONFLICTING"
            summary = f"Stale feed ({freshness_seconds:.1f}s age). Invalidation risk high."
            
        return FactorEvaluation(
            factor_id=11,
            name="Data Freshness & Latency",
            category="System Health",
            score=round(score, 2),
            status=status,
            weight_desc="High",
            summary=summary,
            details={"freshness_seconds": round(freshness_seconds, 2)},
            uncertainty_level="LOW"
        )

    @staticmethod
    def evaluate_factor_12_trader_discipline(
        consecutive_losses: int = 0,
        trades_logged_today: int = 0,
        plan_adherence_rate: float = 100.0
    ) -> FactorEvaluation:
        """Factor 12: Trader Discipline & Behavioral Guardrails."""
        score = 0.5
        notes = []
        
        if consecutive_losses >= 3:
            score = -0.7
            notes.append("3+ Consecutive losses today (Cooldown recommended to avoid revenge trading)")
        elif consecutive_losses == 2:
            score = -0.2
            notes.append("2 consecutive losses (Reduce position size by 50%)")
        else:
            notes.append("Healthy risk buffer")
            
        if trades_logged_today >= 5:
            score -= 0.4
            notes.append("Max intraday trade count threshold reached")
            
        status = "SUPPORTIVE" if score > 0.2 else ("CONFLICTING" if score < -0.2 else "NEUTRAL")
        
        return FactorEvaluation(
            factor_id=12,
            name="Trader Discipline Context",
            category="Behavioral Guardrails",
            score=round(score, 2),
            status=status,
            weight_desc="High",
            summary=" | ".join(notes),
            details={
                "consecutive_losses": consecutive_losses,
                "trades_logged_today": trades_logged_today,
                "plan_adherence_rate": plan_adherence_rate
            },
            uncertainty_level="LOW"
        )
