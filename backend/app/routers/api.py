import datetime
import numpy as np
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.market_state import market_state
from app.services.alert_service import alert_service
from app.providers.universe import NSE_UNIVERSE
from app.schemas.market_schemas import OverviewResponse, Quote, Candle, StockAnalysisResponse
from app.schemas.all_schemas import SignalItem, AlertItem, RiskCalculationRequest, PositionSizingResult, NewsItem, TradeJournalCreate, DisciplineAnalytics, SettingsUpdateRequest
from app.engine.indicators import enrich_candles_with_indicators, detect_key_levels
from app.engine.factors import FactorEngine
from app.engine.scanner import MarketScanner
from app.engine.risk_calculator import calculate_position_sizing
from app.engine.discipline import evaluate_discipline_journal
from app.engine.signals import SignalGenerator
from app.models.all_models import TradeJournalRecord, WatchlistRecord, ModelMetadataRecord

router = APIRouter()

# 1. OVERVIEW
@router.get("/overview", response_model=OverviewResponse)
def get_overview():
    provider = market_state.active_provider
    indices = provider.get_indices()
    nifty = indices.get("NIFTY 50")
    banknifty = indices.get("BANKNIFTY")
    breadth = provider.get_market_breadth()
    sectors = provider.get_sector_performance()
    conn_status = provider.get_connection_status()
    
    # Active candidate vs confirmed vs invalidated counts
    active_cand = len([s for s in market_state.active_signals.values() if s.status == "candidate"])
    confirmed = len([s for s in market_state.active_signals.values() if s.status == "confirmed"])
    invalidated = len([s for s in market_state.active_signals.values() if s.status == "invalidated"])
    
    return OverviewResponse(
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        is_live_feed=provider.is_live_feed(),
        data_source=provider.get_provider_name(),
        connection_status=conn_status.get("status", "Unknown"),
        nifty50=nifty,
        banknifty=banknifty,
        market_breadth=breadth,
        sectors=sectors,
        stats={
            "total_universe_scanned": len(NSE_UNIVERSE),
            "watchlist_count": len(market_state.watchlist),
            "market_phase": FactorEngine.evaluate_factor_8_time_of_day().details.get("market_phase", "Active")
        },
        active_candidates=active_cand,
        confirmed_setups=confirmed,
        invalidated_signals=invalidated,
        model_status=market_state.model_status,
        model_version=market_state.model_version
    )

# 2. MARKET SCANNER
@router.get("/scanner")
def get_scanner_data(
    sector: Optional[str] = Query(None),
    setup_type: Optional[str] = Query(None),
    min_liquidity: Optional[float] = Query(None),
    watchlist_only: bool = Query(False),
    search: Optional[str] = Query(None)
):
    provider = market_state.active_provider
    nifty = provider.get_indices().get("NIFTY 50")
    nifty_chg = nifty.change_pct if nifty else 0.58
    breadth = provider.get_market_breadth()
    
    items = []
    for sym, info in NSE_UNIVERSE.items():
        if watchlist_only and sym not in market_state.watchlist:
            continue
        if search and search.upper() not in sym.upper() and search.lower() not in info["name"].lower():
            continue
            
        df = provider.get_candles(sym, "5m", 75)
        sec_perf = next((s for s in provider.get_sector_performance() if s.sector == info["sector"]), None)
        sec_chg = sec_perf.change_pct if sec_perf else 0.0
        
        item = MarketScanner.scan_stock(
            symbol=sym,
            name=info["name"],
            sector=info["sector"],
            df=df,
            nifty_change_pct=nifty_chg,
            sector_change_pct=sec_chg,
            market_regime=breadth.market_regime,
            is_watchlist=sym in market_state.watchlist,
            ml_model=market_state.ml_pipeline.calibrated_model
        )
        
        if sector and sector.lower() not in item.sector.lower():
            continue
        if setup_type and setup_type.lower() not in item.setup_type.lower():
            continue
        if min_liquidity and item.liquidity_score < min_liquidity:
            continue
            
        items.append(item)
        
    return {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "data_source": provider.get_provider_name(),
        "is_live": provider.is_live_feed(),
        "total_count": len(items),
        "items": items
    }

# 3. STOCK ANALYSIS (ALL 12 FACTORS)
@router.get("/analysis/{symbol}", response_model=StockAnalysisResponse)
def get_stock_analysis(symbol: str):
    sym = symbol.upper()
    if sym not in NSE_UNIVERSE:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found in configured NSE universe.")
        
    provider = market_state.active_provider
    quote = provider.get_quote(sym)
    df = provider.get_candles(sym, "5m", 75)
    enriched = enrich_candles_with_indicators(df)
    
    nifty = provider.get_indices().get("NIFTY 50")
    nifty_chg = nifty.change_pct if nifty else 0.58
    breadth = provider.get_market_breadth()
    sec_perf = next((s for s in provider.get_sector_performance() if s.sector == quote.sector), None)
    sec_chg = sec_perf.change_pct if sec_perf else 0.0
    
    # News for symbol
    news = market_state.news_provider.get_latest_news(limit=5, symbol=sym)
    
    # Evaluate All 12 Factors
    f1 = FactorEngine.evaluate_factor_1_market_trend(nifty_chg, True, breadth.advance_decline_ratio, breadth.market_regime)
    f2 = FactorEngine.evaluate_factor_2_sector_performance(quote.sector, sec_chg, nifty_chg, sec_perf.momentum_score if sec_perf else 50.0)
    f3 = FactorEngine.evaluate_factor_3_news_events([n.model_dump() for n in news])
    f4 = FactorEngine.evaluate_factor_4_price_action(enriched, quote.ltp)
    f5 = FactorEngine.evaluate_factor_5_volume_order_flow(enriched, quote.volume, quote.rel_volume, order_imbalance_ratio=1.2)
    atr = enriched['atr14'].iloc[-1] if 'atr14' in enriched.columns else quote.ltp * 0.01
    f6 = FactorEngine.evaluate_factor_6_volatility(enriched, quote.ltp, float(atr))
    f7 = FactorEngine.evaluate_factor_7_liquidity_execution(0.025, (quote.volume * quote.ltp) / 10000000.0)
    f8 = FactorEngine.evaluate_factor_8_time_of_day()
    f9 = FactorEngine.evaluate_factor_9_technical_indicators(enriched, quote.ltp)
    
    # Check if active setup exists
    sig = SignalGenerator.generate_signal_for_stock(
        symbol=sym,
        df=enriched,
        current_price=quote.ltp,
        sector=quote.sector,
        sector_change_pct=sec_chg,
        nifty_change_pct=nifty_chg,
        market_regime=breadth.market_regime,
        market_breadth_ad=breadth.advance_decline_ratio,
        ml_model=market_state.ml_pipeline.calibrated_model
    )
    
    entry_p = sig.entry_price if sig else quote.ltp
    sl_p = sig.stop_loss if sig else quote.ltp * 0.99
    tp_p = sig.target_price if sig else quote.ltp * 1.02
    
    f10 = FactorEngine.evaluate_factor_10_risk_management(entry_p, sl_p, tp_p, sig.direction if sig else "LONG")
    f11 = FactorEngine.evaluate_factor_11_data_latency_freshness(1.1)
    f12 = FactorEngine.evaluate_factor_12_trader_discipline(consecutive_losses=0, trades_logged_today=1)
    
    factors = [f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12]
    
    # Composite Bias & Confidence
    scores = [f.score for f in factors if f.status != "UNAVAILABLE"]
    avg_score = float(np.mean(scores)) if scores else 0.0
    confidence = min(0.95, max(0.40, abs(avg_score) * 0.8 + 0.35))
    
    composite_bias = "LONG" if avg_score > 0.2 else ("SHORT" if avg_score < -0.2 else "NO_TRADE")
    
    # Format candles list
    candle_list = []
    for _, row in enriched.iterrows():
        candle_list.append(Candle(
            timestamp=str(row['timestamp']),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=int(row['volume']),
            vwap=float(row['vwap']) if 'vwap' in row else None,
            ema9=float(row['ema9']) if 'ema9' in row else None,
            ema21=float(row['ema21']) if 'ema21' in row else None,
            rsi14=float(row['rsi14']) if 'rsi14' in row else None
        ))
        
    return StockAnalysisResponse(
        symbol=sym,
        quote=quote,
        candles=candle_list,
        factors=factors,
        composite_bias=composite_bias,
        confidence_score=round(confidence, 2),
        key_levels=detect_key_levels(enriched),
        order_flow_imbalance=1.2,
        time_of_day_context=f8.details,
        data_freshness_sec=1.1,
        data_source=provider.get_provider_name()
    )

# 4. SIGNALS
@router.get("/signals", response_model=List[SignalItem])
def get_signals(status: Optional[str] = None):
    sigs = list(market_state.active_signals.values())
    if status:
        sigs = [s for s in sigs if s.status.lower() == status.lower()]
    return sigs

# 5. ALERTS
@router.get("/alerts", response_model=List[AlertItem])
def get_alerts(unread_only: bool = False, limit: int = 50):
    return alert_service.get_alerts(limit=limit, unread_only=unread_only)

@router.post("/alerts/{alert_id}/dismiss")
def dismiss_alert(alert_id: str):
    success = alert_service.dismiss_alert(alert_id)
    return {"success": success}

# 6. RISK CALCULATOR
@router.post("/risk/calculate", response_model=PositionSizingResult)
def calculate_risk(req: RiskCalculationRequest):
    return calculate_position_sizing(req)

# 7. NEWS
@router.get("/news", response_model=List[NewsItem])
def get_news(limit: int = 20, symbol: Optional[str] = None, sector: Optional[str] = None):
    return market_state.news_provider.get_latest_news(limit=limit, symbol=symbol, sector=sector)

# 8. MODEL PERFORMANCE & BACKTESTING
@router.get("/ml/performance")
def get_model_performance():
    return {
        "model_version": market_state.model_version,
        "model_status": market_state.model_status,
        "metadata": market_state.ml_pipeline.metadata,
        "active_features": market_state.ml_pipeline.feature_names
    }

@router.post("/ml/backtest")
def run_backtest(
    initial_capital: float = 100000.0,
    risk_pct: float = 1.0,
    slippage_bps: float = 5.0
):
    df_dict = {sym: market_state.active_provider.get_candles(sym, "5m", 75) for sym in NSE_UNIVERSE.keys()}
    from app.ml.backtester import BacktestEngine
    results = BacktestEngine.run_backtest(
        df_dict=df_dict,
        initial_capital=initial_capital,
        risk_per_trade_pct=risk_pct,
        slippage_bps=slippage_bps
    )
    return results

# 9. TRADE JOURNAL
@router.get("/journal")
def get_journal_entries(db: Session = Depends(get_db)):
    entries = db.query(TradeJournalRecord).order_by(TradeJournalRecord.id.desc()).all()
    analytics = evaluate_discipline_journal(entries)
    return {
        "analytics": analytics,
        "entries": entries
    }

@router.post("/journal")
def add_journal_entry(entry: TradeJournalCreate, db: Session = Depends(get_db)):
    risk_req = RiskCalculationRequest(
        symbol=entry.symbol,
        entry_price=entry.actual_entry,
        stop_loss=entry.actual_stop_loss,
        target_price=entry.planned_target,
        direction=entry.direction
    )
    sizing = calculate_position_sizing(risk_req)
    
    charges = sizing.charges_breakdown.total_charges
    gross_pnl = 0.0
    net_pnl = 0.0
    if entry.actual_exit is not None:
        if entry.direction.upper() == "LONG":
            gross_pnl = (entry.actual_exit - entry.actual_entry) * entry.quantity
        else:
            gross_pnl = (entry.actual_entry - entry.actual_exit) * entry.quantity
        net_pnl = gross_pnl - charges
        
    followed = len(entry.deviations) == 0
    score = max(0.0, 100.0 - (len(entry.deviations) * 25.0))
    
    rec = TradeJournalRecord(
        symbol=entry.symbol.upper(),
        direction=entry.direction.upper(),
        planned_entry=entry.planned_entry,
        actual_entry=entry.actual_entry,
        planned_stop_loss=entry.planned_stop_loss,
        actual_stop_loss=entry.actual_stop_loss,
        planned_target=entry.planned_target,
        actual_exit=entry.actual_exit,
        quantity=entry.quantity,
        gross_pnl=round(gross_pnl, 2),
        net_pnl=round(net_pnl, 2),
        total_charges=round(charges, 2),
        setup_strategy=entry.setup_strategy,
        matched_signal_id=entry.matched_signal_id,
        followed_plan=followed,
        discipline_score=score,
        deviations=entry.deviations,
        notes=entry.notes,
        tags=entry.tags
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

# 10. SETTINGS & PROVIDER CONFIG
@router.get("/settings")
def get_settings():
    from app.services.telegram_service import telegram_service
    provider = market_state.active_provider
    if hasattr(provider, "ensure_authenticated"):
        provider.ensure_authenticated()

    angel = market_state.angel_provider
    has_creds = bool(
        angel and getattr(angel, "api_key", None) and getattr(angel, "client_code", None) and 
        getattr(angel, "pin", None) and getattr(angel, "totp_secret", None)
    )
    return {
        "active_provider": market_state.active_provider_name,
        "is_live_feed": provider.is_live_feed(),
        "provider_status": provider.get_connection_status(),
        "watchlist": list(market_state.watchlist),
        "default_capital": 100000.0,
        "default_risk_pct": 1.0,
        "angel_client_code": angel.client_code if angel else "",
        "angel_api_key_configured": bool(angel and angel.api_key),
        "angel_authenticated": angel.is_authenticated if angel else False,
        "has_credentials": has_creds,
        "telegram": telegram_service.get_status()
    }

@router.post("/settings/test-angel")
def test_angel_connection():
    angel = market_state.angel_provider
    if not angel:
        return {"success": False, "error": "Angel One provider not initialized."}
    res = angel.authenticate()
    return res

@router.post("/settings/provider")
def update_provider_settings(req: SettingsUpdateRequest):
    res = market_state.switch_provider(
        provider_name=req.data_provider or "angel_one",
        config={
            "api_key": req.angel_api_key,
            "client_code": req.angel_client_code,
            "pin": req.angel_pin,
            "totp_secret": req.angel_totp_secret
        }
    )
    return res

@router.post("/watchlist/toggle")
def toggle_watchlist_symbol(symbol: str = Query(...)):
    sym = symbol.upper()
    if sym in market_state.watchlist:
        market_state.watchlist.remove(sym)
        return {"symbol": sym, "is_watchlist": False}
    else:
        market_state.watchlist.add(sym)
        return {"symbol": sym, "is_watchlist": True}

# 11. TELEGRAM ALERTS
@router.get("/telegram/status")
def get_telegram_status():
    from app.services.telegram_service import telegram_service
    return telegram_service.get_status()

@router.post("/telegram/config")
def update_telegram_config(payload: Dict[str, Any]):
    from app.services.telegram_service import telegram_service
    bot_token = payload.get("bot_token", "")
    chat_id = payload.get("chat_id", "")
    enabled = payload.get("enabled", True)
    telegram_service.update_config(bot_token, chat_id, enabled)
    return {"success": True, "status": telegram_service.get_status()}

@router.post("/telegram/test")
def test_telegram_alert():
    from app.services.telegram_service import telegram_service
    return telegram_service.send_test_alert()

@router.post("/telegram/broadcast-picks")
def broadcast_picks_to_telegram(limit: int = 3):
    from app.services.telegram_service import telegram_service
    from app.routers.recommendations import get_ai_recommendations
    data = get_ai_recommendations(limit=limit)
    top_picks = data.get("top_recommendations", [])
    sent = []
    errors = []
    for pick in top_picks:
        res = telegram_service.send_recommendation_alert(pick)
        if res.get("success"):
            sent.append(pick["symbol"])
        elif res.get("error"):
            errors.append(res.get("error"))
    return {"sent_count": len(sent), "symbols": sent, "errors": errors}

# 12. ML MODEL RETRAINING & PERFORMANCE
@router.get("/ml/status")
def get_ml_status():
    pipeline = market_state.ml_pipeline
    is_trained = pipeline.calibrated_model is not None
    meta = pipeline.metadata or {}
    return {
        "status": market_state.model_status,
        "version": meta.get("model_version", market_state.model_version),
        "is_calibrated": is_trained,
        "architecture": meta.get("model_type", "Ensemble"),
        "features_count": meta.get("n_features", len(pipeline.feature_names)),
        "last_metrics": {
            "win_rate": meta.get("win_rate", 0),
            "expected_r": meta.get("expectancy_r", 0),
            "brier_score": meta.get("brier_score", 0),
            "roc_auc": meta.get("roc_auc", 0),
            "profit_factor": meta.get("profit_factor", 1)
        },
        "trained_at": meta.get("trained_at", datetime.datetime.utcnow().isoformat() + "Z")
    }

@router.post("/ml/retrain")
def retrain_ml_model():
    provider = market_state.active_provider
    df_dict = {sym: provider.get_candles(sym, "5m", 75) for sym in NSE_UNIVERSE.keys()}
    X, y, r = market_state.ml_pipeline.prepare_dataset(df_dict)
    if len(X) < 40:
        return {"success": False, "message": "Insufficient historical candles for retrain."}
    
    metrics = market_state.ml_pipeline.train_walk_forward(X, y, r, train_ratio=0.75)
    now_str = datetime.datetime.utcnow().isoformat() + "Z"
    market_state.ml_pipeline.metadata = {
        "metrics": metrics,
        "trained_at": now_str,
        "train_samples": len(X)
    }
    market_state.model_status = "Active & Calibrated"
    market_state.model_version = f"v2.1-calibrated-{datetime.datetime.utcnow().strftime('%H%M')}"
    return {
        "success": True,
        "status": market_state.model_status,
        "version": market_state.model_version,
        "train_samples": len(X),
        "metrics": metrics
    }

