import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Trade Intelligence AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API & Host
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
    
    # Database
    DATABASE_URL: str = "sqlite:///./trade_intelligence.db"
    
    # Market Data Provider
    DATA_PROVIDER: str = "demo"  # 'demo' or 'angel_one'
    DEMO_MODE: bool = True
    
    # Angel One SmartAPI Credentials (empty by default, configured via UI or .env)
    ANGEL_API_KEY: str = ""
    ANGEL_CLIENT_CODE: str = ""
    ANGEL_PIN: str = ""
    ANGEL_TOTP_SECRET: str = ""
    ANGEL_FEED_TOKEN: str = ""
    ANGEL_AUTH_TOKEN: str = ""
    
    # Intraday Risk Defaults (NSE Equity)
    DEFAULT_CAPITAL: float = 100000.0  # INR
    DEFAULT_MAX_RISK_PER_TRADE_PCT: float = 1.0  # 1% max risk
    DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT: float = 50.0  # 50% max intraday capital deployment
    DEFAULT_BROKERAGE_PER_ORDER: float = 20.0  # INR flat or 0.03%
    DEFAULT_SLIPPAGE_BPS: float = 5.0  # 0.05%
    
    # Scanner & Engine
    SCAN_INTERVAL_SECONDS: int = 5
    DEFAULT_TIMEFRAME: str = "5m"  # 1m, 3m, 5m, 15m
    MARKET_START_TIME: str = "09:15"
    MARKET_END_TIME: str = "15:30"
    
    # Signal Expiry
    CANDIDATE_SIGNAL_EXPIRY_MINUTES: int = 15
    CONFIRMED_SIGNAL_EXPIRY_MINUTES: int = 60
    
    # ML Models path
    MODEL_DIR: str = "./ml_models"

    # Telegram Notifications
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ENABLED: bool = False

    class Config:
        env_file = (".env", "../.env")
        extra = "ignore"

settings = Settings()
