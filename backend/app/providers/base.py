from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import pandas as pd
from app.schemas.market_schemas import Quote, IndexSummary, SectorPerformance, MarketBreadth

class BaseDataProvider(ABC):
    """
    Abstract interface for market data providers (Demo, Angel One SmartAPI, etc.).
    Ensures modularity and zero coupling between analysis logic and broker APIs.
    """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns the provider identifier (e.g. 'DEMO', 'ANGEL_ONE')."""
        pass

    @abstractmethod
    def is_live_feed(self) -> bool:
        """True if connected to real broker WebSocket/REST stream, False for synthetic/demo."""
        pass

    @abstractmethod
    def get_connection_status(self) -> Dict[str, Any]:
        """Returns connection health, latency, last ping, and active subscriptions."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Fetches the latest LTP, OHLC, volume, and spread for a symbol."""
        pass

    @abstractmethod
    def get_all_quotes(self) -> Dict[str, Quote]:
        """Fetches latest quotes for all universe stocks."""
        pass

    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str = "5m", count: int = 75) -> pd.DataFrame:
        """
        Fetches historical intraday candles as a pandas DataFrame:
        Columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        pass

    @abstractmethod
    def get_indices(self) -> Dict[str, IndexSummary]:
        """Fetches major index quotes (NIFTY 50, NIFTY BANK, etc.)."""
        pass

    @abstractmethod
    def get_market_breadth(self) -> MarketBreadth:
        """Calculates advances, declines, and broad market regime."""
        pass

    @abstractmethod
    def get_sector_performance(self) -> List[SectorPerformance]:
        """Returns sector performance and relative strength rankings."""
        pass
