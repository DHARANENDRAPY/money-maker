import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from app.database import Base

class SignalRecord(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(64), unique=True, index=True)
    symbol = Column(String(32), index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    strategy = Column(String(64))  # e.g., "VWAP Breakout", "Opening Range Breakout", "Mean Reversion"
    direction = Column(String(16))  # "LONG", "SHORT", "NO_TRADE"
    market_regime = Column(String(32))  # "BULLISH", "BEARISH", "SIDEWAYS", "UNCERTAIN"
    
    entry_price = Column(Float)
    stop_loss = Column(Float)
    target_price = Column(Float)
    risk_reward_ratio = Column(Float)
    
    ml_probability = Column(Float, nullable=True)  # Calibrated probability target reached before stop
    ml_model_version = Column(String(32), nullable=True)
    
    status = Column(String(32), default="candidate")  # candidate, confirmed, invalidated, expired, completed
    invalidation_reason = Column(String(255), nullable=True)
    
    supporting_factors = Column(JSON, default=list)
    conflicting_factors = Column(JSON, default=list)
    factor_scores = Column(JSON, default=dict)
    
    data_freshness_seconds = Column(Float, default=0.0)
    expiry_time = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    outcome = Column(String(32), nullable=True)  # "TARGET_HIT", "STOP_HIT", "EXPIRED", "CANCELLED"
    pnl_realized_r = Column(Float, nullable=True)  # In multiples of R (risk)

class AlertRecord(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(64), unique=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    alert_type = Column(String(32))  # "NEW_CANDIDATE", "CONFIRMED_SETUP", "SIGNAL_INVALIDATED", "SIGNAL_EXPIRED", "RISK_WARNING", "FEED_INTERRUPTED", "NEWS_EVENT"
    severity = Column(String(16), default="INFO")  # "INFO", "WARNING", "SUCCESS", "DANGER"
    symbol = Column(String(32), nullable=True)
    title = Column(String(255))
    message = Column(Text)
    details = Column(JSON, default=dict)
    is_dismissed = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

class WatchlistRecord(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, index=True)
    symbols = Column(JSON, default=list)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class TradeJournalRecord(Base):
    __tablename__ = "trade_journal"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), index=True)
    direction = Column(String(16))  # "LONG", "SHORT"
    entry_time = Column(DateTime, default=datetime.datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    
    planned_entry = Column(Float)
    actual_entry = Column(Float)
    planned_stop_loss = Column(Float)
    actual_stop_loss = Column(Float)
    planned_target = Column(Float)
    actual_exit = Column(Float, nullable=True)
    quantity = Column(Integer)
    
    # Financials
    gross_pnl = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    brokerage_charges = Column(Float, default=0.0)
    stt_charges = Column(Float, default=0.0)
    exchange_charges = Column(Float, default=0.0)
    gst_charges = Column(Float, default=0.0)
    stamp_duty = Column(Float, default=0.0)
    total_charges = Column(Float, default=0.0)
    
    # Strategy & Setup
    setup_strategy = Column(String(64), nullable=True)
    matched_signal_id = Column(String(64), nullable=True)
    
    # Discipline Metrics & Notes
    followed_plan = Column(Boolean, default=True)
    discipline_score = Column(Float, default=100.0)  # 0 to 100
    deviations = Column(JSON, default=list)  # ["CHASED_ENTRY", "MOVED_STOP_LOSS", "EARLY_EXIT", "OVERSIZED"]
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=list)

class ModelMetadataRecord(Base):
    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(String(64), unique=True, index=True)
    model_type = Column(String(64))  # e.g., "GradientBoostingClassifier", "CalibratedRandomForest"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    train_start_date = Column(String(32))
    train_end_date = Column(String(32))
    test_start_date = Column(String(32))
    test_end_date = Column(String(32))
    sample_count = Column(Integer)
    
    # Metrics
    brier_score = Column(Float, nullable=True)
    log_loss = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    precision_score = Column(Float, nullable=True)
    recall_score = Column(Float, nullable=True)
    roc_auc = Column(Float, nullable=True)
    
    # Backtest Expectancy
    profit_factor = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    max_drawdown_pct = Column(Float, nullable=True)
    expectancy_r = Column(Float, nullable=True)
    
    feature_importance = Column(JSON, default=dict)
    calibration_curve_data = Column(JSON, default=dict)
    regime_breakdown = Column(JSON, default=dict)
    is_active = Column(Boolean, default=False)


class RecommendationHistoryRecord(Base):
    __tablename__ = "recommendation_history"

    id = Column(Integer, primary_key=True, index=True)
    rec_id = Column(String(64), unique=True, index=True)
    symbol = Column(String(32), index=True)
    name = Column(String(128), nullable=True)
    sector = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    trade_type = Column(String(32), index=True)  # "INTRADAY" or "DELIVERY"
    direction = Column(String(16), default="LONG")  # "LONG" or "SHORT"
    strategy = Column(String(64), nullable=True)
    
    entry_price = Column(Float)
    target_1 = Column(Float)
    target_2 = Column(Float, nullable=True)
    stop_loss = Column(Float)
    risk_reward_ratio = Column(Float, default=1.5)
    
    expected_profit_pct = Column(Float, default=0.0)
    expected_loss_pct = Column(Float, default=0.0)
    
    holding_period = Column(String(64), default="15-45 Mins")  # e.g. "15-45 Mins" or "2-4 Weeks"
    win_probability_pct = Column(Integer, default=60)
    conviction_pct = Column(Integer, default=70)
    
    reason = Column(Text, nullable=True)
    supporting_catalysts = Column(JSON, default=list)
    telegram_sent = Column(Boolean, default=False)
    telegram_sent_at = Column(DateTime, nullable=True)


class AITradeTransactionRecord(Base):
    """
    Dedicated persistent transaction log for all automated trades executed by the AI.
    Stores complete setup features and outcome metrics for future model retraining and accuracy analytics.
    """
    __tablename__ = "ai_trade_transactions"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String(64), unique=True, index=True)
    position_id = Column(String(64), index=True, nullable=True)
    symbol = Column(String(32), index=True)
    direction = Column(String(16), default="LONG")  # "LONG" or "SHORT"
    trade_type = Column(String(32), default="INTRADAY")  # Strictly "INTRADAY"

    entry_time = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    exit_time = Column(DateTime, nullable=True)

    entry_price = Column(Float)
    target_price = Column(Float)
    stop_loss_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, default=1)

    # Performance
    gross_pnl = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    total_charges = Column(Float, default=0.0)
    status = Column(String(32), default="OPEN")  # "OPEN", "PROFIT_BOOKED", "STOP_LOSS_HIT", "SQUAREOFF"
    is_win = Column(Boolean, nullable=True)
    exit_reason = Column(String(128), nullable=True)

    # AI Quality Metrics at time of order
    strategy = Column(String(64), nullable=True)
    ml_probability = Column(Float, nullable=True)
    conviction_score = Column(Float, nullable=True)
    risk_reward_ratio = Column(Float, nullable=True)
    rvol = Column(Float, nullable=True)
    market_regime = Column(String(32), nullable=True)
    supporting_factors = Column(JSON, default=list)

    # Flag for whether this record has been exported or used in ML training
    trained_in_ml = Column(Boolean, default=False)


