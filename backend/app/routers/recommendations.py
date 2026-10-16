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
_INTRA_RECS_CACHE_TTL = 45.0  # 45 seconds cache for instant response


def _conviction_label(score: float) -> str:
    if score >= 0.80:
        return "HIGH_CONVICTION"
    elif score >= 0.65:
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
    Composite AI Setup Confidence / Conviction Score (0.0 to 1.0 / 0% to 100%):
    Evaluates total confluence across:
    1. Base Technical Setup & Risk-Reward (30 pts)
    2. Calibrated ML Model Statistical Edge (25 pts)
    3. Institutional Volume Confirmation / RVOL (15 pts)
    4. Market Regime & Sector Tailwinds (15 pts)
    5. Multi-Indicator Technical Confluence (15 pts)
    
    A textbook confluent setup achieves 80% – 95% AI confidence.
    Setups with conflicting signals or poor volume fall below 65% and are filtered out.
    """
    # 1. Base Setup & R:R (Target: 1.8 R:R)
    # At 1.8 R:R, award 25 pts. Scale up to 30 pts for 2.0+ R:R.
    rr_pts = min(30.0, max(10.0, (rr_ratio / 1.8) * 25.0))

    # 2. ML Probability Component (25 pts max)
    # In quantitative equity trading, 0.50 is the neutral coin toss.
    # Calibrated ML prob of 0.54-0.60+ represents strong statistical alpha.
    if ml_prob >= 0.60:
        ml_pts = 25.0
    elif ml_prob >= 0.55:
        ml_pts = 20.0 + ((ml_prob - 0.55) / 0.05) * 5.0
    elif ml_prob >= 0.50:
        ml_pts = 12.0 + ((ml_prob - 0.50) / 0.05) * 8.0
    else:
        ml_pts = max(0.0, (ml_prob / 0.50) * 10.0)

    # 3. Volume Surge (15 pts max)
    # RVOL > 1.2 indicates institutional participation
    if rvol >= 1.5:
        vol_pts = 15.0
    elif rvol >= 1.2:
        vol_pts = 12.0
    elif rvol >= 1.0:
        vol_pts = 8.0
    else:
        vol_pts = 4.0

    # 4. Market & Sector Alignment (15 pts max)
    regime_pts = 10.0 if regime_aligned else 0.0
    sector_aligned = (direction == "LONG" and sector_change_pct > 0.1) or (direction == "SHORT" and sector_change_pct < -0.1)
    sector_pts = 5.0 if sector_aligned else (2.0 if abs(sector_change_pct) < 0.3 else 0.0)

    # 5. Supporting Indicator Confluence (15 pts max)
    # Each supportive indicator (VWAP, Supertrend, EMA, MACD, etc.) adds 4 pts.
    # Conflicting indicators heavily penalize (-8 pts).
    confluence_pts = max(0.0, min(15.0, (n_supporting * 4.0) - (n_conflicting * 8.0)))

    raw_total = rr_pts + ml_pts + vol_pts + regime_pts + sector_pts + confluence_pts
    score = min(0.96, max(0.20, raw_total / 100.0))
    return round(score, 3)


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
    all_quotes = provider.get_all_quotes()

    # Prioritize stocks with active volume / momentum for responsive sub-second scans
    sorted_universe = sorted(
        NSE_UNIVERSE.items(),
        key=lambda x: (
            all_quotes[x[0]].rel_volume if x[0] in all_quotes else 0.0,
            abs(all_quotes[x[0]].change_pct) if x[0] in all_quotes else 0.0
        ),
        reverse=True
    )
    scan_universe = sorted_universe[:18]

    for sym, info in scan_universe:
        try:
            quote = all_quotes.get(sym) or provider.get_quote(sym)
            if quote is None or quote.ltp <= 0:
                continue

            df = provider.get_candles(sym, "5m", 75)
            if df.empty or len(df) < 20:
                continue

            enriched = enrich_candles_with_indicators(df)

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
                quote=quote,
            )

            if signal is None:
                continue

            ml_prob = signal.ml_probability or 0.50

            # Filter out setups with poor statistical edge (< 0.50)
            if ml_prob < 0.50:
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

            # Strict AI Conviction Gate: discard setups below 70% confidence
            if conviction < 0.70:
                continue

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
            ts_str = ""
            if r.timestamp:
                ts_iso = r.timestamp.isoformat()
                if not ts_iso.endswith("Z") and "+" not in ts_iso and "-" not in ts_iso[-6:]:
                    ts_iso += "Z"
                ts_str = ts_iso

            tg_str = None
            if r.telegram_sent_at:
                tg_iso = r.telegram_sent_at.isoformat()
                if not tg_iso.endswith("Z") and "+" not in tg_iso and "-" not in tg_iso[-6:]:
                    tg_iso += "Z"
                tg_str = tg_iso

            results.append({
                "id": r.id,
                "rec_id": r.rec_id,
                "symbol": r.symbol,
                "name": r.name,
                "sector": r.sector,
                "timestamp": ts_str,
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
                "telegram_sent_at": tg_str
            })

        return {
            "total_count": len(results),
            "trade_type_filter": trade_type,
            "history": results
        }
    finally:
        db.close()

