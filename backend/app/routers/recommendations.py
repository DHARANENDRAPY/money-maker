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
from app.providers.universe import NSE_UNIVERSE
from app.engine.indicators import enrich_candles_with_indicators
from app.engine.signals import SignalGenerator
from app.schemas.all_schemas import SignalItem

router = APIRouter()


_intra_recs_cache = {}
_intra_recs_cache_time = None
_INTRA_RECS_CACHE_TTL = 15.0  # 15 seconds cache


def _conviction_label(score: float) -> str:
    if score >= 0.65:
        return "HIGH_CONVICTION"
    elif score >= 0.45:
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
    # ML probability component (40%) — 0.46 baseline, 0.62+ is excellent
    ml_score = min(1.0, max(0.0, (ml_prob - 0.46) / 0.16)) * 0.40

    # R:R quality component (25%) — 1.4 = baseline, 2.8 = excellent
    rr_score = min(1.0, max(0.0, (rr_ratio - 1.4) / 1.4)) * 0.25

    # Volume confirmation (15%) — RVOL > 1.0 is bullish volume
    vol_score = min(1.0, max(0.0, (rvol - 0.9) / 1.4)) * 0.15

    # Regime alignment (10%)
    regime_score = 0.10 if regime_aligned else 0.0

    # Factor alignment (10%)
    factor_net = n_supporting - (n_conflicting * 2)
    factor_score = min(1.0, max(0.0, factor_net / 3.0)) * 0.10

    total = ml_score + rr_score + vol_score + regime_score + factor_score
    return round(min(0.98, max(0.10, total)), 3)


@router.get("/recommendations")
def get_ai_recommendations(limit: int = 5) -> Dict[str, Any]:
    """
    AI-powered top trade recommendations for the current market session.
    
    Scans all stocks in the NSE universe, generates signals, ranks by conviction score,
    and returns the top N setups with full trade plans.
    """
    global _intra_recs_cache, _intra_recs_cache_time
    now = datetime.datetime.now(datetime.timezone.utc)
    if _intra_recs_cache_time and (now - _intra_recs_cache_time).total_seconds() < _INTRA_RECS_CACHE_TTL and _intra_recs_cache:
        cached_top = _intra_recs_cache.get("top_recommendations", [])
        return {
            **_intra_recs_cache,
            "top_recommendations": cached_top[:limit]
        }

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

            # Filter out setups with poor confidence (< 0.40)
            if ml_prob < 0.40:
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

    # Persist top recommendations into RecommendationHistoryRecord database table
    try:
        from app.database import SessionLocal
        from app.models.all_models import RecommendationHistoryRecord
        from app.services.telegram_service import telegram_service
        import threading

        db = SessionLocal()
        for rec in top:
            today_str = datetime.datetime.utcnow().strftime("%Y%m%d")
            rec_id = f"INTRA-{rec['symbol']}-{rec.get('direction', 'LONG')}-{today_str}"
            exists = db.query(RecommendationHistoryRecord).filter_by(rec_id=rec_id).first()
            if not exists:
                new_rec = RecommendationHistoryRecord(
                    rec_id=rec_id,
                    symbol=rec["symbol"],
                    name=rec.get("name", rec["symbol"]),
                    sector=rec.get("sector", "NSE Equity"),
                    trade_type="INTRADAY",
                    direction=rec.get("direction", "LONG"),
                    strategy=rec.get("strategy", "AI Algorithmic Setup"),
                    entry_price=rec.get("entry_price", 0.0),
                    target_1=rec.get("target_price", 0.0),
                    stop_loss=rec.get("stop_loss", 0.0),
                    risk_reward_ratio=rec.get("risk_reward_ratio", 1.5),
                    expected_profit_pct=round(abs((rec.get("target_price", 0) - rec.get("entry_price", 0)) / max(rec.get("entry_price", 1), 0.01) * 100), 2),
                    expected_loss_pct=round(abs((rec.get("entry_price", 0) - rec.get("stop_loss", 0)) / max(rec.get("entry_price", 1), 0.01) * 100), 2),
                    holding_period="15 to 45 Mins (MIS)",
                    win_probability_pct=int((rec.get("ml_probability") or 0.5) * 100),
                    conviction_pct=int((rec.get("conviction_score") or 0.5) * 100),
                    reason=f"{rec.get('strategy', 'Setup')} | Regime: {market_regime}",
                    supporting_catalysts=rec.get("supporting_factors", [])
                )
                db.add(new_rec)
                db.commit()

                # Dispatch Telegram alert for newly entered recommended stock
                if telegram_service.enabled:
                    def _send_tg(r_copy, rid):
                        try:
                            res = telegram_service.send_recommendation_alert(r_copy)
                            if res.get("success"):
                                db_inner = SessionLocal()
                                item = db_inner.query(RecommendationHistoryRecord).filter_by(rec_id=rid).first()
                                if item:
                                    item.telegram_sent = True
                                    item.telegram_sent_at = datetime.datetime.utcnow()
                                    db_inner.commit()
                                db_inner.close()
                        except Exception:
                            pass
                    threading.Thread(target=_send_tg, args=(dict(rec), rec_id), daemon=True).start()
        db.close()
    except Exception as e:
        print(f"Error persisting recommendation history: {e}")

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


@router.get("/recommendations/history")
def get_recommendations_history(
    trade_type: str = "ALL",  # ALL, INTRADAY, DELIVERY
    limit: int = 100
) -> Dict[str, Any]:
    """
    Returns full history of all Intraday & Delivery stocks suggested by the system,
    including date, time, entry price, targets, stop loss, win accuracy, and rationale.
    """
    from app.database import SessionLocal
    from app.models.all_models import RecommendationHistoryRecord

    db = SessionLocal()
    try:
        query = db.query(RecommendationHistoryRecord)
        if trade_type != "ALL":
            query = query.filter(RecommendationHistoryRecord.trade_type == trade_type.upper())
        records = query.order_by(RecommendationHistoryRecord.timestamp.desc()).limit(limit).all()

        results = []
        for r in records:
            results.append({
                "id": r.id,
                "rec_id": r.rec_id,
                "symbol": r.symbol,
                "name": r.name,
                "sector": r.sector,
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                "trade_type": r.trade_type,
                "direction": r.direction,
                "strategy": r.strategy,
                "entry_price": r.entry_price,
                "target_1": r.target_1,
                "target_2": r.target_2,
                "stop_loss": r.stop_loss,
                "risk_reward_ratio": r.risk_reward_ratio,
                "expected_profit_pct": r.expected_profit_pct,
                "expected_loss_pct": r.expected_loss_pct,
                "holding_period": r.holding_period,
                "win_probability_pct": r.win_probability_pct,
                "conviction_pct": r.conviction_pct,
                "reason": r.reason,
                "supporting_catalysts": r.supporting_catalysts or [],
                "telegram_sent": r.telegram_sent,
                "telegram_sent_at": r.telegram_sent_at.isoformat() if r.telegram_sent_at else None
            })

        return {
            "total_count": len(results),
            "trade_type_filter": trade_type,
            "history": results
        }
    finally:
        db.close()

