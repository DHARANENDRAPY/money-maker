import asyncio
import datetime
import json
from pathlib import Path
try:
    import joblib
    _JOBLIB_OK = True
except ImportError:
    _JOBLIB_OK = False
from typing import Dict, List, Any, Optional, Set
from fastapi import WebSocket
import pandas as pd

from app.config import settings
from app.providers.universe import NSE_UNIVERSE
from app.providers.angel_one_provider import AngelOneSmartAPIProvider
from app.providers.news_provider import NewsProvider
from app.engine.scanner import MarketScanner
from app.engine.signals import SignalGenerator
from app.schemas.all_schemas import SignalItem, AlertItem
from app.services.alert_service import alert_service
from app.ml.model_trainer import ModelTrainingPipeline

class MarketStateManager:
    """
    Central hub managing data providers, active signals, scanner state,
    and connected WebSocket subscribers. Exclusively uses live broker (Angel One).
    """

    def __init__(self):
        self.angel_provider = AngelOneSmartAPIProvider(
            api_key=settings.ANGEL_API_KEY,
            client_code=settings.ANGEL_CLIENT_CODE,
            pin=settings.ANGEL_PIN,
            totp_secret=settings.ANGEL_TOTP_SECRET
        )
        self.news_provider = NewsProvider()
        self.active_provider = self.angel_provider
        self.active_provider_name = "angel_one"
        
        # Authenticate on boot if credentials are present
        if settings.ANGEL_API_KEY and settings.ANGEL_CLIENT_CODE:
            auth_res = self.angel_provider.authenticate()
            if not auth_res.get("success"):
                logger.warning(f"Angel One initial boot auth failed: {auth_res.get('error')}")
        
        self.watchlist: Set[str] = {"RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "TATAMOTORS", "TCS", "SBIN"}
        self.active_signals: Dict[str, SignalItem] = {}
        self.ws_clients: Set[WebSocket] = set()
        
        # Initial ML model initialization
        self.ml_pipeline = ModelTrainingPipeline(model_type="GradientBoosting")
        self.model_status = "Initializing..."
        self.model_version = "v2.0-ensemble-calibrated"
        self.swing_model = None
        self.swing_scaler = None
        self.swing_metadata = {}
        self.swing_status = "Not Loaded"
        self._daily_candles_cache = {}
        self._daily_candles_last_update = None
        self._load_or_train_model()
        self._init_sample_signals()

    def _load_or_train_model(self):
        """Loads production model artifacts if available, else trains on demo data."""
        ml_dir = Path(__file__).parent.parent.parent / "ml_models"
        model_path = ml_dir / "intraday_ensemble_v3.joblib"
        scaler_path = ml_dir / "scaler_v3.joblib"
        meta_path = ml_dir / "metadata_v3.json"

        production_loaded = False
        if _JOBLIB_OK and model_path.exists() and scaler_path.exists():
            try:
                loaded_model = joblib.load(model_path)
                loaded_scaler = joblib.load(scaler_path)
                # Inject the production model into the pipeline
                self.ml_pipeline.calibrated_model = loaded_model
                self.ml_pipeline.model = loaded_model
                self.ml_pipeline.scaler = loaded_scaler
                if meta_path.exists():
                    with open(meta_path) as f:
                        meta = json.load(f)
                    self.ml_pipeline.metadata = meta
                    self.model_version = meta.get("model_version", "v3.0-production")
                    wr = meta.get("win_rate", "?")
                    pf = meta.get("profit_factor", "?")
                    self.model_status = f"Active (Production {self.model_version} | WinRate={wr}% | PF={pf}x)"
                else:
                    self.model_version = "v3.0-production"
                    self.model_status = "Active (Production v3.0 ensemble loaded)"
                production_loaded = True
            except Exception as e:
                self.model_status = f"Load Error -- falling back to mock: {e}"

        # Load swing model
        swing_model_path = ml_dir / "swing_delivery_ensemble_v1.joblib"
        swing_scaler_path = ml_dir / "swing_delivery_scaler_v1.joblib"
        swing_meta_path = ml_dir / "swing_delivery_metadata_v1.json"

        if _JOBLIB_OK and swing_model_path.exists() and swing_scaler_path.exists():
            try:
                self.swing_model = joblib.load(swing_model_path)
                self.swing_scaler = joblib.load(swing_scaler_path)
                if swing_meta_path.exists():
                    with open(swing_meta_path) as f:
                        self.swing_metadata = json.load(f)
                self.swing_status = f"Loaded (v1.0 | WR={self.swing_metadata.get('win_rate', '?')}%)"
            except Exception as e:
                self.swing_status = f"Load Error: {e}"

        if not production_loaded:
            self.model_status = "Awaiting Live Market Data"

    def _init_sample_signals(self):
        # Only initialize signals if active broker provider is authenticated
        if not self.active_provider.is_live_feed():
            return
        nifty = self.active_provider.get_indices().get("NIFTY 50")
        nifty_chg = nifty.change_pct if nifty else 0.58
        breadth = self.active_provider.get_market_breadth()
        if not breadth:
            return
        
        for sym in ["INFY", "RELIANCE", "TATAMOTORS", "ICICIBANK"]:
            df = self.active_provider.get_candles(sym, "5m", 75)
            q = self.active_provider.get_quote(sym)
            if q and not df.empty:
                sig = SignalGenerator.generate_signal_for_stock(
                    symbol=sym,
                    df=df,
                    current_price=q.ltp,
                    sector=q.sector,
                    sector_change_pct=q.change_pct,
                    nifty_change_pct=nifty_chg,
                    market_regime=breadth.market_regime,
                    market_breadth_ad=breadth.advance_decline_ratio,
                    ml_model=self.ml_pipeline.calibrated_model,
                    ml_model_version=self.model_version
                )
                if sig:
                    self.active_signals[sig.signal_id] = sig

    def switch_provider(self, provider_name: str, config: Optional[Dict[str, Any]] = None):
        """Authenticates and connects Angel One SmartAPI live broker feed."""
        if config:
            self.angel_provider = AngelOneSmartAPIProvider(
                api_key=config.get("api_key", ""),
                client_code=config.get("client_code", ""),
                pin=config.get("pin", ""),
                totp_secret=config.get("totp_secret", "")
            )
        res = self.angel_provider.authenticate()
        if res.get("success"):
            self.active_provider = self.angel_provider
            self.active_provider_name = "angel_one"
            alert_service.create_alert(
                alert_type="FEED_INTERRUPTED",
                severity="SUCCESS",
                title="Live Broker Connected",
                message=f"Connected to Angel One SmartAPI (Client {self.angel_provider.client_code}).",
                symbol=None
            )
            return {"success": True, "provider": "ANGEL_ONE_SMARTAPI", "message": "Live Angel One feed active."}
        else:
            return {"success": False, "provider": "ANGEL_ONE_SMARTAPI", "error": res.get("error", "Authentication failed. Check credentials.")}

    async def register_ws(self, websocket: WebSocket):
        await websocket.accept()
        self.ws_clients.add(websocket)

    def unregister_ws(self, websocket: WebSocket):
        if websocket in self.ws_clients:
            self.ws_clients.remove(websocket)

    async def broadcast_ws(self, message: Dict[str, Any]):
        dead = []
        for ws in self.ws_clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister_ws(ws)

    # Stocks known to fail on yfinance (delisted / symbol issues)
    _YFINANCE_BLACKLIST = {"ZOMATO", "TATAMOTORS"}

    async def _refresh_daily_candles_loop(self):
        """Background loop to keep 1-year daily candles warm for swing ML inference."""
        import yfinance as yf
        from train_swing_delivery import SWING_DELIVERY_STOCKS
        while True:
            try:
                valid_stocks = [s for s in SWING_DELIVERY_STOCKS if s not in self._YFINANCE_BLACKLIST]
                tickers = [s + ".NS" for s in valid_stocks]
                df_all = await asyncio.to_thread(
                    yf.download, tickers, period="1y", interval="1d", auto_adjust=True, progress=False
                )
                
                new_cache = {}
                for sym in valid_stocks:
                    ticker = sym + ".NS"
                    try:
                        if isinstance(df_all.columns, pd.MultiIndex):
                            # yfinance returns multi-index if multiple tickers
                            df = df_all.xs(ticker, axis=1, level=1)
                        else:
                            df = df_all
                        
                        df.columns = [str(c).lower() for c in df.columns]
                        keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
                        df = df[keep].dropna()
                        
                        if len(df) >= 50:
                            new_cache[sym] = df
                    except Exception:
                        pass
                
                if new_cache:
                    self._daily_candles_cache = new_cache
                    self._daily_candles_last_update = datetime.datetime.utcnow()
                    
            except Exception as e:
                print(f"Daily candle refresh failed: {e}")
                # Retry faster on failure (5 min) instead of full 6 hour wait
                await asyncio.sleep(5 * 60)
                continue
            
            # Success — refresh every 6 hours
            await asyncio.sleep(6 * 3600)

    def get_daily_candles(self, symbol: str) -> Optional[pd.DataFrame]:
        if symbol in self._daily_candles_cache:
            return self._daily_candles_cache[symbol]
            
        # Fast local daily files fallback
        local_daily_dir = Path(__file__).parent.parent.parent / "data" / "daily"
        path = local_daily_dir / f"{symbol}.csv"
        if not path.exists():
            path = Path(__file__).parent.parent.parent / "data" / "processed" / symbol / "1d.csv"
            
        if path.exists():
            try:
                df = pd.read_csv(path, index_col="datetime", parse_dates=True)
                df.columns = [c.lower() for c in df.columns]
                keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
                df = df[keep].dropna()
                if len(df) >= 30:
                    self._daily_candles_cache[symbol] = df
                    return df
            except Exception:
                pass
                
        return None

market_state = MarketStateManager()
