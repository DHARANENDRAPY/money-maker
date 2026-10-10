import math
import random
import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from app.providers.base import BaseDataProvider
from app.schemas.market_schemas import Quote, IndexSummary, SectorPerformance, MarketBreadth

# Predefined NSE Universe with base references across all market caps and price segments
NSE_UNIVERSE = {
    # Large Caps & Benchmarks
    "RELIANCE": {"name": "Reliance Industries Ltd", "sector": "Energy & Oil", "base_price": 2940.0, "token": "2885", "cap": "Large"},
    "HDFCBANK": {"name": "HDFC Bank Ltd", "sector": "Banking & Fin", "base_price": 1680.0, "token": "1333", "cap": "Large"},
    "ICICIBANK": {"name": "ICICI Bank Ltd", "sector": "Banking & Fin", "base_price": 1245.0, "token": "4963", "cap": "Large"},
    "INFY": {"name": "Infosys Ltd", "sector": "Information Tech", "base_price": 1890.0, "token": "1594", "cap": "Large"},
    "TCS": {"name": "Tata Consultancy Services", "sector": "Information Tech", "base_price": 4210.0, "token": "11536", "cap": "Large"},
    "SBIN": {"name": "State Bank of India", "sector": "Banking & Fin", "base_price": 815.0, "token": "3045", "cap": "Large"},
    "TATAMOTORS": {"name": "Tata Motors Ltd", "sector": "Automobiles", "base_price": 965.0, "token": "3456", "cap": "Large"},
    "BHARTIARTL": {"name": "Bharti Airtel Ltd", "sector": "Telecom", "base_price": 1640.0, "token": "10604", "cap": "Large"},
    "ITC": {"name": "ITC Ltd", "sector": "FMCG", "base_price": 505.0, "token": "1660", "cap": "Large"},
    "LT": {"name": "Larsen & Toubro Ltd", "sector": "Capital Goods", "base_price": 3620.0, "token": "11483", "cap": "Large"},
    "SUNPHARMA": {"name": "Sun Pharma Industries", "sector": "Healthcare", "base_price": 1880.0, "token": "3351", "cap": "Large"},
    "AXISBANK": {"name": "Axis Bank Ltd", "sector": "Banking & Fin", "base_price": 1180.0, "token": "5900", "cap": "Large"},
    "MARUTI": {"name": "Maruti Suzuki India", "sector": "Automobiles", "base_price": 12650.0, "token": "10999", "cap": "Large"},
    "TITAN": {"name": "Titan Company Ltd", "sector": "Consumer Goods", "base_price": 3480.0, "token": "3506", "cap": "Large"},
    "BAJFINANCE": {"name": "Bajaj Finance Ltd", "sector": "Banking & Fin", "base_price": 7250.0, "token": "317", "cap": "Large"},
    "KOTAKBANK": {"name": "Kotak Mahindra Bank", "sector": "Banking & Fin", "base_price": 1820.0, "token": "1922", "cap": "Large"},
    "WIPRO": {"name": "Wipro Ltd", "sector": "Information Tech", "base_price": 540.0, "token": "3787", "cap": "Large"},
    "HCLTECH": {"name": "HCL Technologies Ltd", "sector": "Information Tech", "base_price": 1780.0, "token": "7229", "cap": "Large"},
    "ASIANPAINT": {"name": "Asian Paints Ltd", "sector": "Consumer Goods", "base_price": 2890.0, "token": "236", "cap": "Large"},
    "NTPC": {"name": "NTPC Ltd", "sector": "Power & Energy", "base_price": 425.0, "token": "11630", "cap": "Large"},

    # High-Growth Midcaps & PSU Power/Railways
    "TATASTEEL": {"name": "Tata Steel Ltd", "sector": "Metals & Mining", "base_price": 158.0, "token": "3499", "cap": "Large"},
    "IOC": {"name": "Indian Oil Corporation", "sector": "Energy & Oil", "base_price": 142.0, "token": "1624", "cap": "Large"},
    "ONGC": {"name": "Oil & Natural Gas Corp", "sector": "Energy & Oil", "base_price": 285.0, "token": "2475", "cap": "Large"},
    "BEL": {"name": "Bharat Electronics Ltd", "sector": "Defense & Capital Goods", "base_price": 298.0, "token": "383", "cap": "Large"},
    "IRFC": {"name": "Indian Railway Finance Corp", "sector": "Railways & Fin", "base_price": 148.0, "token": "2029", "cap": "Mid"},
    "ZOMATO": {"name": "Zomato Ltd", "sector": "Consumer Tech", "base_price": 248.0, "token": "5097", "cap": "Large"},
    "BHEL": {"name": "Bharat Heavy Electricals", "sector": "Capital Goods", "base_price": 255.0, "token": "438", "cap": "Mid"},
    "GAIL": {"name": "GAIL India Ltd", "sector": "Energy & Oil", "base_price": 215.0, "token": "4717", "cap": "Large"},
    "NMDC": {"name": "NMDC Ltd", "sector": "Metals & Mining", "base_price": 228.0, "token": "15332", "cap": "Mid"},
    "COALINDIA": {"name": "Coal India Ltd", "sector": "Metals & Mining", "base_price": 465.0, "token": "20374", "cap": "Large"},
    "VEDL": {"name": "Vedanta Ltd", "sector": "Metals & Mining", "base_price": 485.0, "token": "3063", "cap": "Large"},
    "POWERGRID": {"name": "Power Grid Corporation", "sector": "Power & Energy", "base_price": 328.0, "token": "14977", "cap": "Large"},
    "TATAPOWER": {"name": "Tata Power Co Ltd", "sector": "Power & Energy", "base_price": 435.0, "token": "3426", "cap": "Large"},
    "FEDERALBNK": {"name": "Federal Bank Ltd", "sector": "Banking & Fin", "base_price": 196.0, "token": "1023", "cap": "Mid"},
    "ASHOKLEY": {"name": "Ashok Leyland Ltd", "sector": "Automobiles", "base_price": 224.0, "token": "212", "cap": "Mid"},
    "MOTHERSON": {"name": "Samvardhana Motherson", "sector": "Automobiles", "base_price": 178.0, "token": "4204", "cap": "Large"},

    # Budget-Friendly / Micro-Capital Gems (Under ₹100 & Affordable Stocks for ₹1,000 budget)
    "NHPC": {"name": "NHPC Ltd (Hydro Power)", "sector": "Power & Energy", "base_price": 88.0, "token": "17963", "cap": "Mid"},
    "SUZLON": {"name": "Suzlon Energy Ltd", "sector": "Renewable Energy", "base_price": 62.0, "token": "12018", "cap": "Mid"},
    "IDFCFIRSTB": {"name": "IDFC FIRST Bank Ltd", "sector": "Banking & Fin", "base_price": 76.0, "token": "11184", "cap": "Mid"},
    "PNB": {"name": "Punjab National Bank", "sector": "Banking & Fin", "base_price": 104.0, "token": "10666", "cap": "Large"},
    "SAIL": {"name": "Steel Authority of India", "sector": "Metals & Mining", "base_price": 134.0, "token": "2963", "cap": "Mid"},
    "EXIDEIND": {"name": "Exide Industries Ltd", "sector": "Automobiles & EV", "base_price": 485.0, "token": "958", "cap": "Mid"},
}

# Per-stock random drift to create persistent but varied personalities
_STOCK_DRIFT = {sym: float(np.random.default_rng(hash(sym) % (2**32)).normal(0.0005, 0.0008)) for sym in NSE_UNIVERSE}

class DemoDataProvider(BaseDataProvider):
    """
    High-fidelity realistic market data provider for Indian markets.
    Simulates intraday price action, VWAP profiles, volume bursts, and index movements.
    Prices refresh every 5-minute bar based on wall-clock time so the simulation evolves
    naturally throughout the trading day.
    Clearly marks all data as synthetic/demo so users are never misled.
    """

    CACHE_TTL_SECONDS = 30  # Refresh candle cache every 30 seconds to show live-like updates

    def __init__(self):
        self._candle_cache: Dict[str, pd.DataFrame] = {}
        self._cache_timestamps: Dict[str, datetime.datetime] = {}

    def _get_candles_for_symbol(self, symbol: str) -> pd.DataFrame:
        """Build time-anchored intraday candle series for the symbol."""
        info = NSE_UNIVERSE[symbol]
        base = info["base_price"]
        
        # Use a seed that changes with time (minute-level) so prices slowly drift
        now = datetime.datetime.utcnow()
        # Seed changes every 5 minutes + per-symbol hash for uniqueness
        time_seed = (now.hour * 60 + now.minute) // 5
        sym_seed = hash(symbol) % (2**32)
        rng = np.random.default_rng(sym_seed ^ time_seed)
        
        # Determine market phase based on IST time
        ist_hour = (now.hour + 5) % 24
        ist_min = (now.minute + 30) % 60
        ist_decimal = ist_hour + ist_min / 60.0
        
        # Add slight real-time micro-noise based on wall-clock seconds
        micro_noise = (now.second / 60.0) * base * 0.0003
        
        drift = _STOCK_DRIFT.get(symbol, 0.0003)
        
        candles = []
        start_dt = datetime.datetime(now.year, now.month, now.day, 3, 45)  # 09:15 IST = 03:45 UTC
        
        curr_p = base * (1 + rng.normal(drift * 5, 0.006))  # Opening gap
        
        for i in range(75):
            bar_time = start_dt + datetime.timedelta(minutes=i * 5)
            
            # Higher volatility at open (first 30min) and close (last 30min)
            if i < 6:
                volatility = 0.007  # Opening range burst
            elif i > 66:
                volatility = 0.005  # Closing volatility
            else:
                volatility = 0.0025  # Mid-day chop
                
            # Sector-based drift
            sector = info["sector"]
            if "Tech" in sector or "Information" in sector:
                bar_drift = drift * 1.4
            elif "Auto" in sector:
                bar_drift = drift * 0.6
            elif "FMCG" in sector:
                bar_drift = drift * 0.4
            else:
                bar_drift = drift
                
            open_bar = curr_p
            change = curr_p * rng.normal(bar_drift, volatility)
            close_bar = max(1.0, open_bar + change)
            
            high_bar = max(open_bar, close_bar) + abs(curr_p * rng.normal(0, volatility * 0.5))
            low_bar = min(open_bar, close_bar) - abs(curr_p * rng.normal(0, volatility * 0.5))
            low_bar = max(1.0, low_bar)
            
            # Volume: U-shaped throughout the day
            u_weight = 1.0 + 1.5 * ((i - 37.5) / 37.5) ** 2
            avg_vol = {
                "RELIANCE": 45000, "HDFCBANK": 38000, "INFY": 32000, "TCS": 18000,
                "SBIN": 85000, "TATAMOTORS": 120000, "ICICIBANK": 65000
            }.get(symbol, 28000)
            
            bar_vol = int(rng.normal(avg_vol, avg_vol * 0.2) * u_weight)
            bar_vol = max(bar_vol, 500)
            
            curr_p = close_bar
            candles.append({
                "timestamp": bar_time.strftime("%Y-%m-%d %H:%M:%S"),
                "open": round(open_bar, 2),
                "high": round(high_bar, 2),
                "low": round(low_bar, 2),
                "close": round(close_bar, 2),
                "volume": bar_vol
            })

        df = pd.DataFrame(candles)
        
        # Add micro-noise to the last bar to simulate live tick updates
        if len(df) > 0:
            df.loc[df.index[-1], 'close'] = round(float(df['close'].iloc[-1]) + micro_noise, 2)
            df.loc[df.index[-1], 'high'] = round(max(float(df['high'].iloc[-1]), float(df['close'].iloc[-1])), 2)
        
        return df

    def _get_cached_candles(self, symbol: str) -> pd.DataFrame:
        """Returns cached candles, refreshing if TTL expired."""
        now = datetime.datetime.utcnow()
        last_ts = self._cache_timestamps.get(symbol)
        
        if (last_ts is None or (now - last_ts).total_seconds() > self.CACHE_TTL_SECONDS
                or symbol not in self._candle_cache):
            self._candle_cache[symbol] = self._get_candles_for_symbol(symbol)
            self._cache_timestamps[symbol] = now
        
        return self._candle_cache[symbol]

    def get_provider_name(self) -> str:
        return "DEMO_SYNTHETIC"

    def is_live_feed(self) -> bool:
        return False

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "provider": "DEMO_SYNTHETIC",
            "is_connected": True,
            "is_live_broker": False,
            "status": "Running (Demo Mode - Real Market Live Feed Not Connected)",
            "message": "Providing high-fidelity synthetic intraday NSE simulation. To connect live Angel One feeds, configure API credentials in Settings.",
            "latency_ms": 12,
            "subscribed_symbols_count": len(NSE_UNIVERSE),
            "last_heartbeat": datetime.datetime.utcnow().isoformat() + "Z"
        }

    def get_quote(self, symbol: str) -> Optional[Quote]:
        if symbol not in NSE_UNIVERSE:
            return None
            
        info = NSE_UNIVERSE[symbol]
        df = self._get_cached_candles(symbol)
        
        if df.empty:
            return None
        
        last = df.iloc[-1]
        first = df.iloc[0]
        
        ltp = float(last['close'])
        open_p = float(first['open'])
        high_p = float(df['high'].max())
        low_p = float(df['low'].min())
        volume = int(df['volume'].sum())
        
        change = round(ltp - open_p, 2)
        change_pct = round((change / open_p) * 100.0, 2)
        
        typical = (df['high'] + df['low'] + df['close']) / 3.0
        vwap_series = (typical * df['volume']).cumsum() / df['volume'].cumsum()
        vwap = float(vwap_series.iloc[-1]) if not vwap_series.empty else ltp
        
        day_range_pct = round(((high_p - low_p) / low_p) * 100.0, 2)
        
        avg_vol = df['volume'].iloc[-20:].mean()
        rvol = round(float(last['volume'] / avg_vol) if avg_vol > 0 else 1.0, 2)
        
        return Quote(
            symbol=symbol,
            name=info["name"],
            ltp=ltp,
            open=open_p,
            high=high_p,
            low=low_p,
            close=ltp,
            volume=volume,
            change=change,
            change_pct=change_pct,
            vwap=round(vwap, 2),
            day_range_pct=day_range_pct,
            rel_volume=rvol,
            sector=info["sector"],
            last_update=datetime.datetime.utcnow().strftime("%H:%M:%S IST"),
            data_source="DEMO_SYNTHETIC"
        )

    def get_candles(self, symbol: str, timeframe: str = "5m", count: int = 75) -> pd.DataFrame:
        if symbol not in NSE_UNIVERSE:
            return pd.DataFrame()
        return self._get_cached_candles(symbol).tail(count).copy()

    def get_indices(self) -> Dict[str, IndexSummary]:
        """Returns dynamically fluctuating index values."""
        now = datetime.datetime.utcnow()
        # Micro-fluctuation based on seconds
        noise = math.sin(now.timestamp() / 30.0) * 15.0  # ±15 point oscillation
        noise_bn = math.sin(now.timestamp() / 25.0) * 55.0  # ±55 point oscillation for BankNifty
        
        nifty_base = 24850.40
        bn_base = 51320.80
        
        # Use time-based seed for intraday trend consistency
        time_seed = (now.hour * 60 + now.minute) // 5
        rng = np.random.default_rng(time_seed ^ 99999)
        daily_drift = float(rng.normal(0.58, 0.3))  # Daily change %
        
        nifty_ltp = round(nifty_base * (1 + daily_drift / 100.0) + noise, 2)
        nifty_change = round(nifty_ltp - nifty_base, 2)
        
        bn_ltp = round(bn_base * (1 + (daily_drift * 0.95) / 100.0) + noise_bn, 2)
        bn_change = round(bn_ltp - bn_base, 2)
        
        return {
            "NIFTY 50": IndexSummary(
                symbol="NIFTY 50",
                name="Nifty 50 Index",
                ltp=nifty_ltp,
                change=nifty_change,
                change_pct=round(daily_drift, 2),
                trend="BULLISH" if daily_drift > 0.1 else ("BEARISH" if daily_drift < -0.1 else "SIDEWAYS"),
                advance_decline_ratio=1.65 if daily_drift > 0 else 0.85
            ),
            "BANKNIFTY": IndexSummary(
                symbol="BANKNIFTY",
                name="Nifty Bank Index",
                ltp=bn_ltp,
                change=bn_change,
                change_pct=round(daily_drift * 0.95, 2),
                trend="BULLISH" if daily_drift > 0.1 else ("BEARISH" if daily_drift < -0.1 else "SIDEWAYS"),
                advance_decline_ratio=1.40 if daily_drift > 0 else 0.75
            ),
            "NIFTY IT": IndexSummary(
                symbol="NIFTY IT",
                name="Nifty IT Index",
                ltp=round(41850.0 * (1 + (daily_drift * 1.1) / 100.0) + noise * 2.5, 2),
                change=round(41850.0 * (daily_drift * 1.1) / 100.0, 2),
                change_pct=round(daily_drift * 1.1, 2),
                trend="BULLISH" if daily_drift > 0.1 else ("BEARISH" if daily_drift < -0.1 else "SIDEWAYS"),
                advance_decline_ratio=2.10 if daily_drift > 0 else 0.80
            ),
            "NIFTY AUTO": IndexSummary(
                symbol="NIFTY AUTO",
                name="Nifty Auto Index",
                ltp=round(25600.0 * (1 + (daily_drift * 0.7) / 100.0) + noise * 1.5, 2),
                change=round(25600.0 * (daily_drift * 0.7) / 100.0, 2),
                change_pct=round(daily_drift * 0.7, 2),
                trend="BULLISH" if daily_drift > 0.1 else ("BEARISH" if daily_drift < -0.1 else "SIDEWAYS"),
                advance_decline_ratio=1.20 if daily_drift > 0 else 0.70
            )
        }

    def get_market_breadth(self) -> MarketBreadth:
        now = datetime.datetime.utcnow()
        time_seed = (now.hour * 60 + now.minute) // 5
        rng = np.random.default_rng(time_seed ^ 77777)
        adv = int(rng.integers(24, 38))
        dec = 50 - adv
        ad_ratio = round(adv / max(dec, 1), 2)
        regime = "STRONG_BULLISH" if adv > 35 else ("MODERATE_BULLISH" if adv > 28 else ("SIDEWAYS" if adv > 22 else "MODERATE_BEARISH"))
        return MarketBreadth(
            advances=adv,
            declines=dec,
            unchanged=1,
            advance_decline_ratio=ad_ratio,
            nifty500_above_20ema_pct=round(float(rng.uniform(52.0, 72.0)), 1),
            market_regime=regime,
            regime_confidence=round(float(rng.uniform(0.65, 0.88)), 2)
        )

    def get_sector_performance(self) -> List[SectorPerformance]:
        now = datetime.datetime.utcnow()
        time_seed = (now.hour * 60 + now.minute) // 5
        rng = np.random.default_rng(time_seed ^ 55555)
        
        base_sectors = [
            ("Information Tech", 0.94, 82.5, "INFY (+1.4%)", "WIPRO (+0.1%)"),
            ("Energy & Oil", 0.82, 76.0, "RELIANCE (+1.1%)", "NTPC (+0.4%)"),
            ("Banking & Fin", 0.56, 68.0, "ICICIBANK (+0.9%)", "KOTAKBANK (-0.2%)"),
            ("Telecom", 0.45, 62.0, "BHARTIARTL (+0.45%)", "BHARTIARTL (+0.45%)"),
            ("Healthcare", 0.15, 48.0, "SUNPHARMA (+0.3%)", "CIPLA (-0.1%)"),
            ("Automobiles", -0.18, 38.0, "TATAMOTORS (+0.2%)", "MARUTI (-0.5%)"),
            ("FMCG", -0.35, 32.0, "ITC (-0.1%)", "HINDUNILVR (-0.6%)"),
        ]
        
        result = []
        for (sector, base_chg, base_mom, gainer, loser) in base_sectors:
            noise = float(rng.normal(0.0, 0.08))
            chg = round(base_chg + noise, 2)
            mom = round(max(10.0, min(95.0, base_mom + float(rng.normal(0.0, 2.5)))), 1)
            rs = round(chg - 0.58, 2)  # Relative to Nifty
            result.append(SectorPerformance(
                sector=sector,
                change_pct=chg,
                relative_strength=rs,
                momentum_score=mom,
                top_gainer=gainer,
                top_loser=loser
            ))
        return result
