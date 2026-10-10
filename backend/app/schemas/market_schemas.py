from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class Candle(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    ema9: Optional[float] = None
    ema21: Optional[float] = None
    rsi14: Optional[float] = None

class Quote(BaseModel):
    symbol: str
    name: str
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    change: float
    change_pct: float
    vwap: float
    day_range_pct: float
    rel_volume: float
    sector: str
    last_update: str
    data_source: str  # "DEMO" or "ANGEL_ONE"

class IndexSummary(BaseModel):
    symbol: str
    name: str
    ltp: float
    change: float
    change_pct: float
    trend: str  # "BULLISH", "BEARISH", "SIDEWAYS", "UNCERTAIN"
    advance_decline_ratio: Optional[float] = None

class SectorPerformance(BaseModel):
    sector: str
    change_pct: float
    relative_strength: float  # vs NIFTY 50
    momentum_score: float
    top_gainer: str
    top_loser: str

class MarketBreadth(BaseModel):
    advances: int
    declines: int
    unchanged: int
    advance_decline_ratio: float
    nifty500_above_20ema_pct: float
    market_regime: str  # "STRONG_BULLISH", "MODERATE_BULLISH", "SIDEWAYS", "MODERATE_BEARISH", "STRONG_BEARISH", "UNCERTAIN"
    regime_confidence: float  # 0.0 to 1.0

class OverviewResponse(BaseModel):
    timestamp: str
    is_live_feed: bool
    data_source: str
    connection_status: str
    nifty50: IndexSummary
    banknifty: IndexSummary
    market_breadth: MarketBreadth
    sectors: List[SectorPerformance]
    stats: Dict[str, Any]
    active_candidates: int
    confirmed_setups: int
    invalidated_signals: int
    model_status: str
    model_version: str

class ScannerItem(BaseModel):
    symbol: str
    name: str
    ltp: float
    change: float
    change_pct: float
    volume: int
    rel_volume: float
    sector: str
    trend_alignment: str  # "ALIGNED_BULLISH", "ALIGNED_BEARISH", "COUNTER_TREND", "NEUTRAL"
    setup_type: str  # e.g., "VWAP Pullback", "ORB Breakout", "Mean Reversion", "No Setup"
    ml_probability: Optional[float] = None
    expected_volatility_pct: float
    risk_reward: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    data_freshness_sec: float
    signal_status: str  # "candidate", "confirmed", "invalidated", "no_signal"
    direction: str  # "LONG", "SHORT", "NEUTRAL"
    liquidity_score: float  # 0-100
    spread_pct: float
    is_watchlist: bool = False

class FactorEvaluation(BaseModel):
    factor_id: int
    name: str
    category: str
    score: float  # -1.0 (strongly bearish) to +1.0 (strongly bullish)
    status: str  # "SUPPORTIVE", "NEUTRAL", "CONFLICTING", "UNAVAILABLE"
    weight_desc: str
    summary: str
    details: Dict[str, Any]
    uncertainty_level: str  # "LOW", "MODERATE", "HIGH"

class StockAnalysisResponse(BaseModel):
    symbol: str
    quote: Quote
    candles: List[Candle]
    factors: List[FactorEvaluation]
    composite_bias: str  # "LONG", "SHORT", "NO_TRADE"
    confidence_score: float
    key_levels: Dict[str, float]  # support_1, resistance_1, vwap, pdh, pdl, orh, orl
    order_flow_imbalance: Optional[float] = None
    time_of_day_context: Dict[str, Any]
    data_freshness_sec: float
    data_source: str
