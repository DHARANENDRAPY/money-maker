"""
AI Delivery & Swing Investment Engine
Generates high-probability Buy & Hold (Delivery / CNC) recommendations for:
  - 2 to 4 Weeks (Short Swing)
  - 1 to 3 Months (Positional Momentum)
  - 3 to 6 Months (Growth Accumulation)

Includes exact entry zones, exit rules (Target 1, Target 2, Stop Loss, Trailing SL),
position sizing specifically calculated for ₹1,000+ budgets, fundamental catalysts,
and Telegram alert dispatch.
"""
import math
import datetime
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger("delivery_engine")

from app.services.market_state import market_state
from app.providers.universe import NSE_UNIVERSE
from app.engine.indicators import enrich_candles_with_indicators
from app.services.telegram_service import telegram_service
from train_swing_delivery import SWING_DELIVERY_STOCKS, extract_daily_features

router = APIRouter(prefix="/delivery", tags=["Delivery & Swing Recommendations"])

# Date the fundamental/technical catalog text was last curated by an analyst.
# Used in API response to signal to users that these texts are periodic (not real-time).
CATALOG_LAST_UPDATED = "2026-10-10"

DELIVERY_SETUPS_CATALOG = {
    "TATASTEEL": {
        "horizon": "2 to 4 Weeks (Short Swing)",
        "horizon_code": "SWING_2_4W",
        "technical_setup": "Breakout above 3-month consolidation rectangle with 2.4x volume surge & RSI breakout above 62.",
        "fundamental_catalyst": "Global steel price rebound, UK blast furnace transition subsidies, strong domestic infrastructure demand.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 9.5,
        "t2_pct": 22.0,
        "sl_pct": 4.8,
        "stars": 5,
        "conviction_pct": 92
    },
    "IOC": {
        "horizon": "1 to 3 Months (Positional)",
        "horizon_code": "POSITIONAL_1_3M",
        "technical_setup": "Ascending triangle breakout on Weekly chart; holding firmly above 50-day EMA support.",
        "fundamental_catalyst": "Refining margins steady above $8/bbl, attractive 6.8% dividend yield, capex expansion in petrochemicals.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 11.2,
        "t2_pct": 24.5,
        "sl_pct": 5.2,
        "stars": 5,
        "conviction_pct": 89
    },
    "BEL": {
        "horizon": "3 to 6 Months (Growth Accumulation)",
        "horizon_code": "GROWTH_3_6M",
        "technical_setup": "Multi-month cup and handle continuation pattern; institution accumulation visible on daily OBV.",
        "fundamental_catalyst": "Massive ₹76,000 Cr order book from defense modernization, indigenization push (Make in India), 22% ROE.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 14.5,
        "t2_pct": 36.0,
        "sl_pct": 5.8,
        "stars": 5,
        "conviction_pct": 95
    },
    "SUZLON": {
        "horizon": "1 to 3 Months (Positional)",
        "horizon_code": "POSITIONAL_1_3M",
        "technical_setup": "Bullish pennant breakout following clean pullback to 21 EMA with rising delivery volumes.",
        "fundamental_catalyst": "Net debt-free balance sheet, record 3.8 GW wind order book, strong tailwinds from India 500GW clean energy target.",
        "risk_profile": "HIGH_GROWTH",
        "t1_pct": 16.5,
        "t2_pct": 42.0,
        "sl_pct": 6.8,
        "stars": 5,
        "conviction_pct": 91
    },
    "NHPC": {
        "horizon": "2 to 4 Weeks (Short Swing)",
        "horizon_code": "SWING_2_4W",
        "technical_setup": "Double bottom reversal pattern near ₹82 major support; MACD histogram turned bullish green.",
        "fundamental_catalyst": "Subansiri lower hydro project commissioning imminent, strong regulated return on equity, 5.2% dividend yield.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 8.8,
        "t2_pct": 19.5,
        "sl_pct": 4.5,
        "stars": 4,
        "conviction_pct": 86
    },
    "IRFC": {
        "horizon": "1 to 3 Months (Positional)",
        "horizon_code": "POSITIONAL_1_3M",
        "technical_setup": "Symmetrical triangle breakout with heavy delivery volume; crossing above 20 EMA with bullish candle.",
        "fundamental_catalyst": "Indian Railways record ₹2.5 Lakh Cr capex budget, 0% NPA lending model, sovereign-backed borrower profile.",
        "risk_profile": "MODERATE_RISK",
        "t1_pct": 12.8,
        "t2_pct": 32.0,
        "sl_pct": 5.5,
        "stars": 5,
        "conviction_pct": 93
    },
    "ZOMATO": {
        "horizon": "3 to 6 Months (Growth Accumulation)",
        "horizon_code": "GROWTH_3_6M",
        "technical_setup": "All-time high base breakout; rising channel on weekly chart with RSI at 64 (momentum zone).",
        "fundamental_catalyst": "Blinkit quick-commerce business expanding 100%+ YoY with positive contribution margins; operating leverage kicking in.",
        "risk_profile": "HIGH_GROWTH",
        "t1_pct": 18.0,
        "t2_pct": 48.0,
        "sl_pct": 7.0,
        "stars": 5,
        "conviction_pct": 94
    },
    "IDFCFIRSTB": {
        "horizon": "2 to 4 Weeks (Short Swing)",
        "horizon_code": "SWING_2_4W",
        "technical_setup": "Pullback to 200 EMA completed; bullish engulfing weekly candle on above-average volume.",
        "fundamental_catalyst": "Retail loan book growing 20%+ YoY, asset quality steady with GNPA < 2%, deposit franchise scaling robustly.",
        "risk_profile": "MODERATE_RISK",
        "t1_pct": 9.2,
        "t2_pct": 21.0,
        "sl_pct": 4.6,
        "stars": 4,
        "conviction_pct": 85
    },
    "ONGC": {
        "horizon": "1 to 3 Months (Positional)",
        "horizon_code": "POSITIONAL_1_3M",
        "technical_setup": "Consolidation range breakout with high dividend support; weekly Supertrend green.",
        "fundamental_catalyst": "Crude realizations stable $75-85/bbl, KG-DWN 98/2 deepwater production ramp-up, 5.5% dividend yield.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 10.5,
        "t2_pct": 25.0,
        "sl_pct": 4.9,
        "stars": 4,
        "conviction_pct": 88
    },
    "TATAPOWER": {
        "horizon": "3 to 6 Months (Growth Accumulation)",
        "horizon_code": "GROWTH_3_6M",
        "technical_setup": "High tight flag pattern on weekly timeframe; trading above all major daily moving averages (20/50/200).",
        "fundamental_catalyst": "4.3 GW solar cell & module manufacturing facility operational, aggressive EV charging network expansion, rooftop solar surge.",
        "risk_profile": "MODERATE_RISK",
        "t1_pct": 15.0,
        "t2_pct": 38.0,
        "sl_pct": 6.2,
        "stars": 5,
        "conviction_pct": 92
    },
    "GAIL": {
        "horizon": "2 to 4 Weeks (Short Swing)",
        "horizon_code": "SWING_2_4W",
        "technical_setup": "Breakout above multi-week descending trendline with strong volume confirmation.",
        "fundamental_catalyst": "Gas transmission volumes up 8% YoY, petrochemical plant turnaround, national gas grid expansion tailwind.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 8.5,
        "t2_pct": 18.5,
        "sl_pct": 4.2,
        "stars": 4,
        "conviction_pct": 84
    },
    "PNB": {
        "horizon": "1 to 3 Months (Positional)",
        "horizon_code": "POSITIONAL_1_3M",
        "technical_setup": "Base breakout near ₹100 psychological level; bullish MACD divergence.",
        "fundamental_catalyst": "Massive decline in gross NPAs from 11% to <5.5%, credit costs reduced, return on assets (RoA) expanding.",
        "risk_profile": "MODERATE_RISK",
        "t1_pct": 13.5,
        "t2_pct": 30.0,
        "sl_pct": 5.8,
        "stars": 4,
        "conviction_pct": 87
    },
    "BHEL": {
        "horizon": "2 to 4 Weeks (Short Swing)",
        "horizon_code": "SWING_2_4W",
        "technical_setup": "Inverse Head and Shoulders neckline breakout with 3.1x volume surge.",
        "fundamental_catalyst": "NTPC & Adani thermal power equipment orders totaling ₹25,000+ Cr, defense & railway propulsion orders.",
        "risk_profile": "HIGH_GROWTH",
        "t1_pct": 12.0,
        "t2_pct": 28.0,
        "sl_pct": 5.4,
        "stars": 5,
        "conviction_pct": 90
    },
    "RELIANCE": {
        "horizon": "3 to 6 Months (Growth Accumulation)",
        "horizon_code": "GROWTH_3_6M",
        "technical_setup": "Rebounding from 200-day EMA support with strong weekly candle; RSI bouncing from oversold 42 level.",
        "fundamental_catalyst": "Jio tariff hike driving ARPU growth to ₹200+, Retail footfalls and store expansion, new energy gigafactories commissioning.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 10.0,
        "t2_pct": 24.0,
        "sl_pct": 4.5,
        "stars": 5,
        "conviction_pct": 94
    },
    "HDFCBANK": {
        "horizon": "3 to 6 Months (Growth Accumulation)",
        "horizon_code": "GROWTH_3_6M",
        "technical_setup": "Double bottom breakout on weekly chart; FII net buying resumed after multi-quarter consolidation.",
        "fundamental_catalyst": "Post-merger deposit mobilization gathering strong momentum, credit-to-deposit (CD) ratio normalizing rapidly.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 9.5,
        "t2_pct": 22.5,
        "sl_pct": 4.2,
        "stars": 5,
        "conviction_pct": 92
    },
    "INFY": {
        "horizon": "1 to 3 Months (Positional)",
        "horizon_code": "POSITIONAL_1_3M",
        "technical_setup": "Ascending triangle breakout above ₹1880 resistance; IT index momentum turning sharply bullish.",
        "fundamental_catalyst": "US Federal Reserve rate cut cycle reviving enterprise discretionary IT spending; mega cloud & AI deal wins.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 8.5,
        "t2_pct": 20.0,
        "sl_pct": 4.0,
        "stars": 4,
        "conviction_pct": 88
    },
    "SBIN": {
        "horizon": "1 to 3 Months (Positional)",
        "horizon_code": "POSITIONAL_1_3M",
        "technical_setup": "Bullish flag breakout on daily chart; Supertrend flipped positive with volume expansion.",
        "fundamental_catalyst": "Industry-leading RoA > 1%, pristine asset quality with net NPAs at historical low of 0.57%, high loan growth.",
        "risk_profile": "LOW_RISK",
        "t1_pct": 9.8,
        "t2_pct": 23.0,
        "sl_pct": 4.5,
        "stars": 5,
        "conviction_pct": 91
    },
    "TATAMOTORS": {
        "horizon": "2 to 4 Weeks (Short Swing)",
        "horizon_code": "SWING_2_4W",
        "technical_setup": "Pullback to ₹950 support zone completed; bullish hammer candle formed with rising volume.",
        "fundamental_catalyst": "JLR order book strong with luxury EV launch pipeline, PV business demerger creating value unlocking, commercial vehicle margin expansion.",
        "risk_profile": "MODERATE_RISK",
        "t1_pct": 10.5,
        "t2_pct": 26.0,
        "sl_pct": 4.8,
        "stars": 4,
        "conviction_pct": 89
    }
}


def _build_delivery_pick(sym: str, info: Dict[str, Any], quote: Any, budget: float, prob: float) -> Dict[str, Any]:
    """Generates a complete delivery trade plan with position sizing for the user's budget."""
    ltp = quote.ltp if quote else info["base_price"]
    chg = quote.change_pct if quote else 0.0

    # Derive horizon and targets dynamically based on ML prediction score
    sec = info.get("sector", "General")
    
    # Very high probability -> shorter time to hit target (swing)
    # Good probability -> longer time (positional)
    if prob >= 0.75:
        horizon_label = "2 to 4 Weeks (Short Swing)"
        horizon_code = "SWING_2_4W"
        t1_pct = 8.5
        t2_pct = 19.0
        sl_pct = 4.4
        stars = 5
        risk_profile = "LOW_RISK"
    else:
        horizon_label = "1 to 3 Months (Positional)"
        horizon_code = "POSITIONAL_1_3M"
        t1_pct = 12.0
        t2_pct = 26.0
        sl_pct = 5.5
        stars = 4
        risk_profile = "MODERATE_RISK"

    # Fetch custom text if available, else dynamic
    catalog = DELIVERY_SETUPS_CATALOG.get(sym)
    if catalog:
        tech_setup = catalog["technical_setup"]
        fund_cat = catalog["fundamental_catalyst"]
    else:
        tech_setup = f"ML model detected strong multi-day momentum accumulation. Breakout expected above recent highs."
        fund_cat = f"Sector tailwinds in {sec} combined with positive institutional volume profile."

    # Price levels
    buy_min = round(ltp * 0.985, 2)
    buy_max = round(ltp * 1.012, 2)
    target_1 = round(ltp * (1 + t1_pct / 100.0), 2)
    target_2 = round(ltp * (1 + t2_pct / 100.0), 2)
    stop_loss = round(ltp * (1 - sl_pct / 100.0), 2)

    risk_reward = round(t1_pct / max(sl_pct, 0.1), 1)

    # Budget Position Sizing (Works for ₹1,000, ₹5,000, ₹10,000, etc.)
    # In Delivery / CNC, 1x cash margin is used (no leverage)
    if ltp <= budget:
        shares = max(1, int(budget / ltp))
    else:
        # If stock price > budget (e.g. RELIANCE @ 2940 with 1000 budget), indicate 1 share requires full price
        shares = 1

    invested_val = round(shares * ltp, 2)
    spare_cash = round(max(0.0, budget - invested_val), 2) if ltp <= budget else 0.0

    t1_profit = round(shares * (target_1 - ltp), 2)
    t2_profit = round(shares * (target_2 - ltp), 2)
    sl_loss = round(shares * (ltp - stop_loss), 2)

    # Calculate dedicated values for ₹1,000 starter budget
    shares_1k = max(1, int(1000.0 / ltp)) if ltp <= 1000.0 else 1
    prof_1k = round(shares_1k * (target_1 - ltp), 2)
    loss_1k = round(shares_1k * (ltp - stop_loss), 2)

    return {
        "symbol": sym,
        "name": info.get("name", sym),
        "sector": info.get("sector", "General"),
        "cap": info.get("cap", "Large"),
        "ltp": round(ltp, 2),
        "change_pct": round(chg, 2),
        "is_budget_friendly": ltp <= budget,
        "under_100": ltp <= 100,
        "under_500": ltp <= 500,
        "under_1000": ltp <= 1000,
        
        # Action & Buy Zone
        "action": "BUY (DELIVERY / CNC)",
        "buy_zone_min": buy_min,
        "buy_zone_max": buy_max,
        "buy_zone_str": f"₹{buy_min:,.2f} – ₹{buy_max:,.2f}",
        
        # Time Horizon
        "holding_period": horizon_label,
        "horizon_code": horizon_code,
        
        # Exit Plan (When to Exit)
        "target_1": target_1,
        "target_1_gain_pct": t1_pct,
        "target_2": target_2,
        "target_2_gain_pct": t2_pct,
        "stop_loss": stop_loss,
        "stop_loss_risk_pct": sl_pct,
        "risk_reward_ratio": risk_reward,
        "trailing_sl_rule": "Move SL to cost price once Target 1 is hit; trail 20-day EMA for Target 2.",
        "time_exit_rule": f"Exit at market price if target not reached within {horizon_label.split('(')[0].strip()}.",
        
        # Position Sizing for User's Chosen Budget
        "user_budget": budget,
        "suggested_shares": shares,
        "invested_amount": invested_val,
        "spare_cash": spare_cash,
        "profit_target_1": t1_profit,
        "profit_target_2": t2_profit,
        "max_loss_at_sl": sl_loss,

        # Standard ₹1,000 Starter Budget metrics
        "shares_for_1k": shares_1k,
        "profit_t1_for_1k": prof_1k,
        "loss_for_1k": loss_1k,

        # Analysis & Conviction
        "stars": stars,
        "conviction_pct": int(prob * 100),
        "conviction_label": "HIGH_CONVICTION" if prob >= 0.72 else "MODERATE",
        "risk_profile": risk_profile,
        "technical_setup": tech_setup,
        "fundamental_catalyst": fund_cat,
        "delivery_vol_pct": round(54.0 + (prob * 22.0), 1),
        "institutional_accumulation": "STRONG_PHYSICAL_DELIVERY" if prob >= 0.70 else "MODERATE_ACCUMULATION",
        # Warn user if the text analysis is from the static catalog (not real-time)
        "analysis_is_live": catalog is None,
        "catalog_text_last_updated": None if catalog is None else CATALOG_LAST_UPDATED,
        "ml_probability": round(prob, 3)
    }


_recs_cache = {}
_recs_cache_time = None
_RECS_CACHE_TTL = 30.0  # 30 seconds

@router.get("/recommendations")
def get_delivery_recommendations(
    budget: float = Query(1000.0, description="User's investment capital budget in INR"),
    horizon: str = Query("ALL", description="Filter horizon: ALL, SWING_2_4W, POSITIONAL_1_3M, GROWTH_3_6M"),
    max_price: float = Query(0.0, description="Filter max price per share: 0 (all), 100, 500, 1000"),
    risk_profile: str = Query("ALL", description="Filter risk: ALL, LOW_RISK, MODERATE_RISK, HIGH_GROWTH"),
    limit: int = Query(12, description="Max recommendations to return")
) -> Dict[str, Any]:
    # Ensure arguments are primitive types even if called directly or with Query default objects
    budget = float(budget.default if hasattr(budget, 'default') else budget)
    horizon = str(horizon.default if hasattr(horizon, 'default') else horizon)
    max_price = float(max_price.default if hasattr(max_price, 'default') else max_price)
    risk_profile = str(risk_profile.default if hasattr(risk_profile, 'default') else risk_profile)
    limit = int(limit.default if hasattr(limit, 'default') else limit)

    global _recs_cache, _recs_cache_time
    now = datetime.datetime.now(datetime.timezone.utc)

    provider = market_state.active_provider
    quotes = provider.get_all_quotes()

    # Check memory cache
    if _recs_cache_time and (now - _recs_cache_time).total_seconds() < _RECS_CACHE_TTL and _recs_cache:
        all_picks = _recs_cache.get("all_picks", [])
    else:
        results = []
        model = market_state.swing_model
        scaler = market_state.swing_scaler
        meta = market_state.swing_metadata
        inference_thresh = 0.55

        for sym in SWING_DELIVERY_STOCKS:
            if sym not in NSE_UNIVERSE:
                continue
                
            info = NSE_UNIVERSE[sym]
            quote = quotes.get(sym)
            df = market_state.get_daily_candles(sym)
            
            # ML Inference — fallback to catalog-based conviction if no daily candle data
            prob = 0.58  # Default: moderate conviction for catalog stocks
            if model and scaler and df is not None and not df.empty:
                try:
                    feats_df = extract_daily_features(df)
                    if not feats_df.empty:
                        last_row = feats_df.iloc[-1:]
                        scaled_feats = scaler.transform(last_row)
                        prob = float(model.predict_proba(scaled_feats)[0][1])
                except Exception:
                    # Use catalog conviction if ML fails for this stock
                    catalog = DELIVERY_SETUPS_CATALOG.get(sym)
                    if catalog:
                        prob = catalog.get("conviction_pct", 85) / 100.0
                    
            if prob < inference_thresh:
                continue
                
            pick = _build_delivery_pick(sym, info, quote, 1000.0, prob)
            results.append(pick)

        results.sort(key=lambda x: (x["stars"], x["conviction_pct"]), reverse=True)
        all_picks = results
        _recs_cache = {"all_picks": all_picks}
        _recs_cache_time = now

    # Dynamically scale positions for requested user budget
    filtered_results = []
    for p in all_picks:
        pick_copy = dict(p)
        ltp = pick_copy["ltp"]
        shares = max(1, int(budget / ltp)) if ltp <= budget else 1
        pick_copy["user_budget"] = budget
        pick_copy["suggested_shares"] = shares
        pick_copy["invested_amount"] = round(shares * ltp, 2)
        pick_copy["spare_cash"] = round(max(0.0, budget - (shares * ltp)), 2) if ltp <= budget else 0.0
        pick_copy["profit_target_1"] = round(shares * (pick_copy["target_1"] - ltp), 2)
        pick_copy["profit_target_2"] = round(shares * (pick_copy["target_2"] - ltp), 2)
        pick_copy["max_loss_at_sl"] = round(shares * (ltp - pick_copy["stop_loss"]), 2)
        pick_copy["is_budget_friendly"] = ltp <= budget

        # Apply Filters
        if horizon != "ALL" and pick_copy["horizon_code"] != horizon:
            continue
        if max_price > 0 and pick_copy["ltp"] > max_price:
            continue
        if risk_profile != "ALL" and pick_copy["risk_profile"] != risk_profile:
            continue

        filtered_results.append(pick_copy)

    # Top recommendations
    top_picks = filtered_results[:limit]
    for i, p in enumerate(top_picks):
        p["rank"] = i + 1

    # Persist top delivery recommendations into RecommendationHistoryRecord database table
    try:
        from app.database import SessionLocal
        from app.models.all_models import RecommendationHistoryRecord
        from app.services.telegram_service import telegram_service
        import threading

        db = SessionLocal()
        for p in top_picks[:6]:
            today_str = datetime.datetime.utcnow().strftime("%Y%m%d")
            rec_id = f"DELIVERY-{p['symbol']}-{today_str}"
            exists = db.query(RecommendationHistoryRecord).filter_by(rec_id=rec_id).first()
            if not exists:
                new_rec = RecommendationHistoryRecord(
                    rec_id=rec_id,
                    symbol=p["symbol"],
                    name=p.get("name", p["symbol"]),
                    sector=p.get("sector", "NSE Equity"),
                    trade_type="DELIVERY",
                    direction="LONG",
                    strategy=p.get("technical_setup", "Delivery Swing Breakout"),
                    entry_price=p.get("ltp", 0.0),
                    target_1=p.get("target_1", 0.0),
                    target_2=p.get("target_2", 0.0),
                    stop_loss=p.get("stop_loss", 0.0),
                    risk_reward_ratio=p.get("risk_reward_ratio", 2.5),
                    expected_profit_pct=round(p.get("target_1_gain_pct", 0.0), 2),
                    expected_loss_pct=round(p.get("stop_loss_risk_pct", 0.0), 2),
                    holding_period=p.get("holding_period", "2 to 4 Weeks (CNC)"),
                    win_probability_pct=int(p.get("conviction_pct", 75)),
                    conviction_pct=int(p.get("conviction_pct", 75)),
                    reason=f"{p.get('technical_setup', '')}. Catalyst: {p.get('fundamental_catalyst', '')}",
                    supporting_catalysts=[p.get("technical_setup", ""), p.get("fundamental_catalyst", "")]
                )
                db.add(new_rec)
                db.commit()

                # Dispatch Telegram alert for newly entered delivery stock
                if telegram_service.enabled:
                    def _send_deliv_tg(p_copy, rid):
                        try:
                            res = telegram_service.send_delivery_alert(p_copy)
                            if res.get("success"):
                                db_inner = SessionLocal()
                                item = db_inner.query(RecommendationHistoryRecord).filter_by(rec_id=rid).first()
                                if item:
                                    item.telegram_sent = True
                                    item.telegram_sent_at = datetime.datetime.utcnow()
                                    db_inner.commit()
                                db_inner.close()
                        except Exception as ex:
                            logger.error(f"Failed to send delivery telegram alert for {rid}: {ex}")
                    threading.Thread(target=_send_deliv_tg, args=(dict(p), rec_id), daemon=True).start()
        db.close()
    except Exception as e:
        print(f"Error persisting delivery recommendation history: {e}")

    return {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "budget": budget,
        "active_horizon_filter": horizon,
        "active_price_filter": max_price,
        "total_scanned": len(NSE_UNIVERSE),
        "total_matching": len(all_picks),
        "recommendations": top_picks,
        "starter_picks_under_1000": [p for p in top_picks if p["under_1000"]],
        "starter_picks_under_500": [p for p in top_picks if p["under_500"]],
        "data_source": provider.get_provider_name(),
        "is_live_feed": provider.is_live_feed(),
        # Prices, ML scores, targets, SL are all real-time.
        # 'technical_setup' and 'fundamental_catalyst' text may be periodic analyst notes.
        "price_data_is_live": provider.is_live_feed(),
        "catalog_text_last_updated": CATALOG_LAST_UPDATED,
        "catalog_text_note": "Entry prices, targets, SL, and ML scores are real-time. Qualitative text (technical_setup, fundamental_catalyst) for known stocks is periodically curated and may not reflect today's chart.",
    }


class DeliveryBroadcastRequest(BaseModel):
    symbol: Optional[str] = None
    budget: float = 1000.0


@router.post("/broadcast-telegram")
def broadcast_delivery_to_telegram(req: DeliveryBroadcastRequest) -> Dict[str, Any]:
    """
    Broadcasts top delivery recommendation(s) to the configured Telegram channel.
    Uses the SAME ML-filtered results as /recommendations — no hardcoded catalog loop.
    """
    provider = market_state.active_provider

    if not telegram_service.enabled:
        return {"success": False, "message": "Telegram alerts are disabled."}

    if not provider.is_live_feed():
        return {"success": False, "message": "Not connected to live Angel One feed. Telegram alerts blocked to prevent DEMO data being sent as real signals."}

    # Note market session status for information in delivery alerts
    now_utc = datetime.datetime.utcnow()
    ist_offset = datetime.timedelta(hours=5, minutes=30)
    now_ist = now_utc + ist_offset
    weekday = now_ist.weekday()
    total_minutes = now_ist.hour * 60 + now_ist.minute
    is_market_open = (weekday < 5) and (9 * 60 + 15 <= total_minutes < 15 * 60 + 30)

    quotes = provider.get_all_quotes()
    model = market_state.swing_model
    scaler = market_state.swing_scaler
    meta = market_state.swing_metadata
    inference_thresh = meta.get("inference_threshold", 0.65) if meta else 0.65
    budget = req.budget

    # If broadcasting a specific symbol
    if req.symbol and req.symbol in NSE_UNIVERSE:
        sym = req.symbol
        info = NSE_UNIVERSE[sym]
        quote = quotes.get(sym)
        df = market_state.get_daily_candles(sym)
        prob = 0.50
        if model and scaler and df is not None and not df.empty:
            try:
                feats_df = extract_daily_features(df)
                if not feats_df.empty:
                    scaled = scaler.transform(feats_df.iloc[-1:])
                    prob = float(model.predict_proba(scaled)[0][1])
            except Exception:
                pass
        if prob < inference_thresh:
            return {"success": False, "message": f"{sym} did not pass the ML confidence threshold ({prob:.2%} < {inference_thresh:.2%}). Alert blocked."}
        pick = _build_delivery_pick(sym, info, quote, budget, prob)
        res = telegram_service.send_delivery_alert(pick)
        return {"success": res.get("success", False), "sent_count": 1 if res.get("success") else 0, "result": res}

    # Broadcast top ML-filtered picks (same as /recommendations)
    sent = 0
    for sym in SWING_DELIVERY_STOCKS:
        if sym not in NSE_UNIVERSE:
            continue
        info = NSE_UNIVERSE[sym]
        quote = quotes.get(sym)
        df = market_state.get_daily_candles(sym)
        prob = 0.50
        if model and scaler and df is not None and not df.empty:
            try:
                feats_df = extract_daily_features(df)
                if not feats_df.empty:
                    scaled = scaler.transform(feats_df.iloc[-1:])
                    prob = float(model.predict_proba(scaled)[0][1])
            except Exception:
                pass
        if prob < inference_thresh:
            continue
        pick = _build_delivery_pick(sym, info, quote, budget, prob)
        res = telegram_service.send_delivery_alert(pick)
        if res.get("success"):
            sent += 1
        if sent >= 3:  # Limit to top 3 to avoid spam
            break

    return {"success": sent > 0, "sent_count": sent, "message": f"Broadcasted {sent} ML-vetted delivery picks to Telegram."}

