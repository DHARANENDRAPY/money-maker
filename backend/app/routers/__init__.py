from app.routers.api import router as api_router
from app.routers.recommendations import router as recommendations_router
from app.routers.delivery import router as delivery_router
from app.routers.paper_trading import router as paper_trading_router
from app.routers.options_radar import router as options_radar_router

__all__ = [
    "api_router",
    "recommendations_router",
    "delivery_router",
    "paper_trading_router",
    "options_radar_router"
]
