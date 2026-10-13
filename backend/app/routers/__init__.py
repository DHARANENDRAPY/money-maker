from app.routers.api import router as api_router
from app.routers.recommendations import router as recommendations_router
from app.routers.delivery import router as delivery_router
from app.routers.paper_trading import router as paper_trading_router
from app.routers.ai_trader import router as ai_trader_router

__all__ = [
    "api_router",
    "recommendations_router",
    "delivery_router",
    "paper_trading_router",
    "ai_trader_router"
]

