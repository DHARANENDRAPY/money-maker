import asyncio
import logging
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
import app.models.all_models
from app.routers import (
    api_router,
    recommendations_router,
    delivery_router,
    paper_trading_router,
    options_radar_router
)
from app.services.market_state import market_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("trade_intelligence_ai")

# Create tables
Base.metadata.create_all(bind=engine)

from app.services.auto_trainer import background_model_updater_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Trade Intelligence AI Engine...")
    # Background periodic tick simulator / broadcaster
    broadcast_task = asyncio.create_task(market_tick_broadcaster())
    # Background auto-model retraining scheduler
    auto_train_task = asyncio.create_task(background_model_updater_loop())
    # Background morning re-auth for Angel One
    reauth_task = asyncio.create_task(angel_reauth_loop())
    # Background daily candle fetcher for Swing ML
    swing_fetch_task = asyncio.create_task(market_state._refresh_daily_candles_loop())
    # Background Live Market Intraday Top 3 Telegram Broadcaster
    intraday_tg_task = asyncio.create_task(live_intraday_telegram_broadcaster_loop())
    yield
    broadcast_task.cancel()
    auto_train_task.cancel()
    reauth_task.cancel()
    swing_fetch_task.cancel()
    intraday_tg_task.cancel()
    logger.info("Trade Intelligence AI Engine shutdown.")

async def angel_reauth_loop():
    """Background async loop checking every 60 seconds.
    At 08:30 IST on trading days, re-authenticates Angel One API to refresh daily JWT tokens."""
    await asyncio.sleep(10)
    last_reauth_date = None
    while True:
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            ist_offset = datetime.timedelta(hours=5, minutes=30)
            now_ist = now_utc + ist_offset
            today_date = now_ist.date()
            weekday = now_ist.weekday()

            # Trigger precisely between 08:28 and 08:35 IST on weekdays once per day
            if weekday < 5 and now_ist.hour == 8 and 28 <= now_ist.minute <= 35:
                if last_reauth_date != today_date:
                    logger.info("Morning Angel One Auto-Reauth started (08:30 IST window)...")
                    if market_state.active_provider_name == "angel_one" and hasattr(market_state, "angel_provider"):
                        res = market_state.angel_provider.authenticate()
                        logger.info(f"Angel One re-auth result: {res}")
                    last_reauth_date = today_date
                
            # Check every 60 seconds
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in angel_reauth_loop: {e}")
            await asyncio.sleep(60)
async def live_intraday_telegram_broadcaster_loop():
    """
    Background loop running during live market hours (09:15 to 15:30 IST).
    Scans the market and broadcasts the top 3 highest-conviction intraday stocks
    with the exact AI decision timestamp to Telegram.
    """
    await asyncio.sleep(15)  # Let server finish initial warm-up
    from app.services.telegram_service import telegram_service
    from app.routers.recommendations import get_ai_recommendations

    last_broadcast_hour = None

    while True:
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            ist_offset = datetime.timedelta(hours=5, minutes=30)
            now_ist = now_utc + ist_offset
            weekday = now_ist.weekday()
            total_minutes = now_ist.hour * 60 + now_ist.minute

            # Check if live market is active (09:15 to 15:15 IST, Mon-Fri)
            is_market_live = (weekday < 5) and (9 * 60 + 15 <= total_minutes <= 15 * 60 + 15)

            if is_market_live and telegram_service.enabled:
                # Run periodically during market hours (every 15 minutes or when top picks update)
                current_window = now_ist.hour * 60 + (now_ist.minute // 15) * 15
                if current_window != last_broadcast_hour:
                    logger.info("Scanning for top 3 Intraday picks for live Telegram dispatch...")
                    try:
                        data = get_ai_recommendations(limit=3)
                        top_picks = data.get("top_recommendations", [])
                        if top_picks:
                            sent_count = 0
                            for pick in top_picks[:3]:
                                res = telegram_service.send_recommendation_alert(pick)
                                if res.get("success") and not res.get("already_sent"):
                                    sent_count += 1
                            if sent_count > 0:
                                logger.info(f"Dispatched {sent_count} live intraday setups with decision timestamps to Telegram.")
                            last_broadcast_hour = current_window
                    except Exception as ex:
                        logger.error(f"Error in intraday telegram auto-broadcast: {ex}")

            # Check every 60 seconds
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in live_intraday_telegram_broadcaster_loop: {e}")
            await asyncio.sleep(60)

def _get_broadcast_sleep_seconds() -> float:
    """
    Returns the appropriate WebSocket broadcast interval based on Indian market hours.
    NSE/BSE Trading Hours: Mon-Fri, 09:15 - 15:30 IST (UTC+5:30)
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    # Convert to IST (UTC+5:30)
    ist_offset = datetime.timedelta(hours=5, minutes=30)
    now_ist = now_utc + ist_offset

    # Known NSE Holidays
    nse_holidays = [
        "01-26", "03-08", "03-25", "04-11", "04-17", "05-01", 
        "06-17", "07-17", "08-15", "10-02", "11-01", "11-15", "12-25"
    ]
    mm_dd = now_ist.strftime("%m-%d")
    
    if mm_dd in nse_holidays:
        return 300.0  # 5 minutes - public holiday

    weekday = now_ist.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5:  # Weekend
        return 300.0  # 5 minutes - no live data on weekends

    total_minutes = now_ist.hour * 60 + now_ist.minute
    # Market open: 09:15 to 15:30
    if 9 * 60 + 15 <= total_minutes < 15 * 60 + 30:
        return 2.0   # Live market: 2 second broadcasts
    # Pre-market: 09:00 to 09:15
    elif 9 * 60 <= total_minutes < 9 * 60 + 15:
        return 15.0  # Pre-market: 15s
    # Post-market: 15:30 to 16:00
    elif 15 * 60 + 30 <= total_minutes < 16 * 60:
        return 30.0  # Post-market: 30s
    else:
        return 120.0  # Market closed (night): 2 minute intervals


async def market_tick_broadcaster():
    """Background loop pushing live tick quotes to WebSocket clients.
    Respects Indian market hours to avoid wasting Angel One API quota."""
    while True:
        try:
            sleep_secs = _get_broadcast_sleep_seconds()
            await asyncio.sleep(sleep_secs)
            if market_state.ws_clients:
                provider = market_state.active_provider
                indices = provider.get_indices()
                nifty = indices.get("NIFTY 50")
                banknifty = indices.get("BANKNIFTY")
                breadth = provider.get_market_breadth()
                quotes = provider.get_all_quotes()

                quotes_payload = {
                    sym: {
                        "symbol": q.symbol,
                        "ltp": q.ltp,
                        "change": q.change,
                        "change_pct": q.change_pct,
                        "open": q.open,
                        "high": q.high,
                        "low": q.low,
                        "volume": q.volume,
                        "vwap": q.vwap,
                        "last_update": q.last_update,
                        "data_source": q.data_source
                    }
                    for sym, q in quotes.items()
                }

                payload = {
                    "type": "TICK_UPDATE",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "is_live_feed": provider.is_live_feed(),
                    "provider": provider.get_provider_name(),
                    "nifty50": nifty.model_dump() if nifty else None,
                    "banknifty": banknifty.model_dump() if banknifty else None,
                    "market_breadth": breadth.model_dump() if breadth else None,
                    "quotes": quotes_payload,
                    "active_signals_count": len(market_state.active_signals)
                }
                await market_state.broadcast_ws(payload)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Broadcaster error: {e}")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Intraday Market Analysis & Trade Opportunity Discovery Platform for Indian Stock Markets (NSE). Analysis-Only Platform.",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(delivery_router, prefix="/api")
app.include_router(paper_trading_router, prefix="/api")
app.include_router(options_radar_router, prefix="/api")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await market_state.register_ws(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or process client ping
            await websocket.send_json({"type": "PONG", "received": data})
    except WebSocketDisconnect:
        market_state.unregister_ws(websocket)
    except Exception:
        market_state.unregister_ws(websocket)

@app.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "provider": market_state.active_provider_name,
        "is_live_feed": market_state.active_provider.is_live_feed()
    }
