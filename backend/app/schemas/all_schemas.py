from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class SignalItem(BaseModel):
    signal_id: str
    symbol: str
    timestamp: str
    strategy: str
    direction: str  # "LONG", "SHORT", "NO_TRADE"
    market_regime: str
    entry_price: float
    stop_loss: float
    target_price: float
    risk_reward_ratio: float
    ml_probability: Optional[float] = None
    ml_model_version: Optional[str] = None
    status: str  # candidate, confirmed, invalidated, expired, completed
    invalidation_reason: Optional[str] = None
    supporting_factors: List[str] = []
    conflicting_factors: List[str] = []
    factor_scores: Dict[str, float] = {}
    data_freshness_seconds: float = 0.0
    expiry_time: Optional[str] = None
    outcome: Optional[str] = None
    pnl_realized_r: Optional[float] = None

class AlertItem(BaseModel):
    alert_id: str
    timestamp: str
    alert_type: str
    severity: str  # "INFO", "WARNING", "SUCCESS", "DANGER"
    symbol: Optional[str] = None
    title: str
    message: str
    details: Dict[str, Any] = {}
    is_dismissed: bool = False

# Risk Calculator Schemas (Indian Equity Intraday STT / Stamp Duty / Exchange / GST / SEBI / Brokerage)
class RiskCalculationRequest(BaseModel):
    symbol: str
    capital: float = 100000.0
    risk_pct: float = 1.0  # Max acceptable loss in % of capital
    entry_price: float
    stop_loss: float
    target_price: float
    direction: str = "LONG"  # "LONG" or "SHORT"
    brokerage_type: str = "FLAT"  # "FLAT" (Rs 20) or "PERCENT" (0.03%)
    flat_brokerage_rate: float = 20.0
    percent_brokerage_rate: float = 0.03

class StatutoryChargesBreakdown(BaseModel):
    turnover: float
    brokerage: float
    stt: float  # Securities Transaction Tax (0.025% on sell for equity intraday)
    exchange_txn_charge: float  # NSE ~0.00297%
    gst: float  # 18% on (Brokerage + Exchange Txn Charges + SEBI)
    sebi_charges: float  # Rs 10 per crore
    stamp_duty: float  # 0.003% on buy value
    total_charges: float
    breakeven_points: float  # Points move needed to cover all taxes & costs

class PositionSizingResult(BaseModel):
    max_risk_amount: float
    risk_per_share: float
    target_per_share: float
    risk_reward_ratio: float
    calculated_quantity: int
    capped_quantity: int  # Capped by max intraday margin/capital
    total_capital_required: float
    capital_utilization_pct: float
    
    # Financial Projections
    gross_loss_at_stop: float
    net_loss_at_stop: float
    gross_profit_at_target: float
    net_profit_at_target: float
    charges_breakdown: StatutoryChargesBreakdown
    risk_warning: Optional[str] = None

# News Schemas
class NewsItem(BaseModel):
    news_id: str
    timestamp: str
    source: str
    headline: str
    summary: str
    sentiment: str  # "POSITIVE", "NEGATIVE", "NEUTRAL", "UNCERTAIN"
    sentiment_score: float  # -1.0 to 1.0
    impact_level: str  # "HIGH", "MEDIUM", "LOW"
    affected_symbols: List[str] = []
    affected_sectors: List[str] = []
    category: str  # "EARNINGS", "POLICY", "CORPORATE_ACTION", "MACRO", "GENERAL"

# Journal Schemas
class TradeJournalCreate(BaseModel):
    symbol: str
    direction: str
    planned_entry: float
    actual_entry: float
    planned_stop_loss: float
    actual_stop_loss: float
    planned_target: float
    actual_exit: Optional[float] = None
    quantity: int
    setup_strategy: Optional[str] = None
    matched_signal_id: Optional[str] = None
    notes: Optional[str] = None
    deviations: List[str] = []
    tags: List[str] = []

class DisciplineAnalytics(BaseModel):
    total_logged_trades: int
    plan_adherence_rate: float  # % of trades following initial plan
    avg_discipline_score: float
    common_deviations: Dict[str, int]
    revenge_trading_flags: int
    overtrading_days: int
    win_rate_when_disciplined: float
    win_rate_when_deviated: float
    avg_r_multiple_disciplined: float
    avg_r_multiple_deviated: float

# Settings Schemas
class SettingsUpdateRequest(BaseModel):
    data_provider: Optional[str] = None
    demo_mode: Optional[bool] = None
    angel_api_key: Optional[str] = None
    angel_client_code: Optional[str] = None
    angel_pin: Optional[str] = None
    angel_totp_secret: Optional[str] = None
    default_capital: Optional[float] = None
    default_max_risk_per_trade_pct: Optional[float] = None
    default_max_portfolio_exposure_pct: Optional[float] = None
    default_timeframe: Optional[str] = None
    scan_interval_seconds: Optional[int] = None
