"""
AI Recommendations Engine
Scans the full NSE universe, runs all 5 setup patterns, and ranks the top trades
by a composite conviction score: ML Probability × R:R × Volume × Regime Alignment.
"""
import datetime
import numpy as np
from typing import List, Optional, Dict, Any
from fastapi import APIRouter

from app.services.market_state import market_state
from app.providers.demo_provider import NSE_UNIVERSE
from app.engine.indicators import enrich_candles_with_indicators
from app.engine.signals import SignalGenerator
from app.schemas.all_schemas import SignalItem

router = APIRouter()


def _conviction_label(score: float) -> str:
    if score >= 0.75:
        return "HIGH_CONVICTION"
    elif score >= 0.58:
        return "MODERATE"
    else:
        return "SPECULATIVE"


def _compute_conviction_score(
    ml_prob: float,
    rr_ratio: float,
    rvol: float,
    n_supporting: int,
    n_conflicting: int,
    regime_aligned: bool,
    sector_change_pct: float,
    direction: str,
) -> float:
    """
    Composite conviction score (0.0 – 1.0):
    Weights: ML probability (40%) + R:R quality (25%) + Volume (15%) + 
             Regime alignment (10%) + Factor alignment (10%)
    """
    # ML probability component (40%) — baseline now 0.50 (random), 0.90 = excellent
    ml_score = min(1.0, max(0.0, (ml_prob - 0.50) / 0.45)) * 0.40

    # R:R quality component (25%) — 1.4 = baseline, 3.0 = excellent
    rr_score = min(1.0, max(0.0, (rr_ratio - 1.4) / 1.6)) * 0.25

    # Volume confirmation (15%) — RVOL > 1.5 is bullish volume
    vol_score = min(1.0, max(0.0, (rvol - 1.0) / 2.0)) * 0.15

    # Regime alignment (10%)
    regime_score = 0.10 if regime_aligned else 0.0

    # Factor alignment (10%)
    factor_net = n_supporting - (n_conflicting * 2)
    factor_score = min(1.0, max(0.0, factor_net / 4.0)) * 0.10

    total = ml_score + rr_score + vol_score + regime_score + factor_score
    return round(min(0.98, max(0.10, total)), 3)


@router.get("/recommendations")
def get_ai_recommendations(limit: int = 5) -> Dict[str, Any]:
    """
    AI-powered top trade recommendations for the current market session.
    
    Scans all stocks in the NSE universe, generates signals, ranks by conviction score,
    and returns the top N setups with full trade plans.
    """
    provider = market_state.active_provider
    indices = provider.get_indices()
    nifty = indices.get("NIFTY 50")
    nifty_chg = nifty.change_pct if nifty else 0.0
    breadth = provider.get_market_breadth()
    market_regime = breadth.market_regime

    recommendations = []

    for sym, info in NSE_UNIVERSE.items():
        try:
            df = provider.get_candles(sym, "5m", 75)
            if df.empty or len(df) < 20:
                continue

            enriched = enrich_candles_with_indicators(df)
            quote = provider.get_quote(sym)
            if quote is None:
                continue

            sec_perf = next(
                (s for s in provider.get_sector_performance() if s.sector == info["sector"]),
                None
            )
            sec_chg = sec_perf.change_pct if sec_perf else 0.0
            rvol = float(enriched['rvol'].iloc[-1]) if 'rvol' in enriched.columns else 1.0

            signal: Optional[SignalItem] = SignalGenerator.generate_signal_for_stock(
                symbol=sym,
                df=enriched,
                current_price=quote.ltp,
                sector=info["sector"],
                sector_change_pct=sec_chg,
                nifty_change_pct=nifty_chg,
                market_regime=market_regime,
                market_breadth_ad=breadth.advance_decline_ratio,
                ml_model=market_state.ml_pipeline.calibrated_model,
                ml_model_version=market_state.model_version,
            )

            if signal is None:
                continue

            ml_prob = signal.ml_probability or 0.50

            # === HARD ML GATE ===
            # Only allow signals where the model has >= 60% confidence.
            # This is the primary fix for the over-trading / low precision issue.
            ML_CONFIDENCE_THRESHOLD = 0.60
            if ml_prob < ML_CONFIDENCE_THRESHOLD:
                continue

            # Regime alignment check
            regime_aligned = (
                (signal.direction == "LONG" and "BULLISH" in market_regime) or
                (signal.direction == "SHORT" and "BEARISH" in market_regime) or
                "SIDEWAYS" in market_regime
            )

            conviction = _compute_conviction_score(
                ml_prob=ml_prob,
                rr_ratio=signal.risk_reward_ratio,
                rvol=rvol,
                n_supporting=len(signal.supporting_factors),
                n_conflicting=len(signal.conflicting_factors),
                regime_aligned=regime_aligned,
                sector_change_pct=sec_chg,
                direction=signal.direction,
            )

            # Risk amount per trade at 1% capital risk (₹1,00,000 default)
            risk_per_share = abs(signal.entry_price - signal.stop_loss)
            qty_at_1pct = int(1000 / risk_per_share) if risk_per_share > 0 else 1
            max_loss = round(qty_at_1pct * risk_per_share, 2)
            max_profit = round(qty_at_1pct * abs(signal.target_price - signal.entry_price), 2)

            recommendations.append({
                "rank": 0,  # filled after sort
                "symbol": sym,
                "name": info["name"],
                "sector": info["sector"],
                "ltp": quote.ltp,
                "change_pct": quote.change_pct,
                "direction": signal.direction,
                "strategy": signal.strategy,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "target_price": signal.target_price,
                "risk_reward_ratio": signal.risk_reward_ratio,
                "ml_probability": ml_prob,
                "conviction_score": conviction,
                "conviction_label": _conviction_label(conviction),
                "rvol": round(rvol, 2),
                "supporting_factors": signal.supporting_factors,
                "conflicting_factors": signal.conflicting_factors,
                "regime_aligned": regime_aligned,
                "market_regime": market_regime,
                "suggested_qty": max(1, qty_at_1pct),
                "max_loss_inr": max_loss,
                "max_profit_inr": max_profit,
                "signal_id": signal.signal_id,
                "expiry_time": signal.expiry_time,
                "data_source": provider.get_provider_name(),
            })
        except Exception:
            continue

    # Sort by conviction score descending
    recommendations.sort(key=lambda x: x["conviction_score"], reverse=True)

    # Assign ranks and apply limit
    top = recommendations[:limit]
    for i, rec in enumerate(top):
        rec["rank"] = i + 1

    # Auto-dispatch top recommendations to Telegram asynchronously if enabled
    try:
        from app.services.telegram_service import telegram_service
        
        # Determine if Indian Market is currently Open (prevent spam when closed or restarted at night)
        now_utc = datetime.datetime.utcnow()
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset
        weekday = now_ist.weekday()
        total_minutes = now_ist.hour * 60 + now_ist.minute
        
        # Market open: 09:15 to 15:30, Mon-Fri
        is_market_open = (weekday < 5) and (9 * 60 + 15 <= total_minutes < 15 * 60 + 30)

        # Only auto-send if Market is OPEN and the feed is Live
        if telegram_service.enabled and provider.is_live_feed() and is_market_open:
            import threading
            def _async_send(recs_to_send):
                for rec in recs_to_send:
                    try:
                        telegram_service.send_recommendation_alert(rec)
                    except Exception:
                        pass
            threading.Thread(target=_async_send, args=(list(top[:3]),), daemon=True).start()
    except Exception:
        pass

    return {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "market_regime": market_regime,
        "nifty_change_pct": round(nifty_chg, 2),
        "is_live_feed": provider.is_live_feed(),
        "data_source": provider.get_provider_name(),
        "total_scanned": len(NSE_UNIVERSE),
        "signals_found": len(recommendations),
        "top_recommendations": top,
    }
