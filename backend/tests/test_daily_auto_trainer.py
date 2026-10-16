import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.services.auto_trainer import auto_trainer_service, AutoModelTrainingService, IST
from app.routers.ai_trader import get_ai_trader_status, trigger_daily_training


def test_auto_trainer_initial_state():
    """Verify AutoModelTrainingService initializes with daily post-market tracking."""
    assert hasattr(auto_trainer_service, "should_retrain_daily")
    assert hasattr(auto_trainer_service, "get_schedule_info")
    assert hasattr(auto_trainer_service, "sync_daily_market_data")
    assert hasattr(auto_trainer_service, "run_auto_train_job")


def test_should_retrain_daily_logic():
    """Verify should_retrain_daily adheres to weekday and 15:45 IST post-market rules."""
    service = AutoModelTrainingService()

    # Case 1: Market hours (e.g. 11:30 IST on a Tuesday) -> should NOT retrain
    tuesday_1130 = datetime(2026, 10, 13, 11, 30, tzinfo=IST)
    with patch("app.services.auto_trainer.datetime") as mock_dt:
        mock_dt.now.return_value = tuesday_1130
        mock_dt.fromisoformat = datetime.fromisoformat
        service._is_training = False
        service._last_daily_trained_date = "2026-10-12"
        assert service.should_retrain_daily() is False

    # Case 2: Post-market (e.g. 16:00 IST on a Tuesday) -> SHOULD retrain
    tuesday_1600 = datetime(2026, 10, 13, 16, 0, tzinfo=IST)
    with patch("app.services.auto_trainer.datetime") as mock_dt:
        mock_dt.now.return_value = tuesday_1600
        mock_dt.fromisoformat = datetime.fromisoformat
        service._is_training = False
        service._last_daily_trained_date = "2026-10-12"
        assert service.should_retrain_daily() is True

    # Case 3: Already trained today (e.g. 16:30 IST on same Tuesday) -> should NOT duplicate
    with patch("app.services.auto_trainer.datetime") as mock_dt:
        mock_dt.now.return_value = tuesday_1600
        mock_dt.fromisoformat = datetime.fromisoformat
        service._is_training = False
        service._last_daily_trained_date = "2026-10-13"
        assert service.should_retrain_daily() is False

    # Case 4: Weekend (Sunday 16:00 IST) -> should NOT retrain
    sunday_1600 = datetime(2026, 10, 18, 16, 0, tzinfo=IST)
    with patch("app.services.auto_trainer.datetime") as mock_dt:
        mock_dt.now.return_value = sunday_1600
        mock_dt.fromisoformat = datetime.fromisoformat
        service._is_training = False
        service._last_daily_trained_date = "2026-10-16"
        assert service.should_retrain_daily() is False


def test_schedule_info_metadata():
    """Verify get_schedule_info returns comprehensive schedule details."""
    info = auto_trainer_service.get_schedule_info()
    assert "schedule" in info
    assert "15:45 IST" in info["schedule"]
    assert "next_scheduled_run" in info
    assert "is_training" in info
    assert "current_phase" in info


def test_ai_trader_status_includes_daily_training():
    """Verify /api/ai-trader/status exposes daily_training schedule info."""
    status = get_ai_trader_status()
    assert "daily_training" in status
    assert "schedule" in status["daily_training"]
    assert "next_scheduled_run" in status["daily_training"]
