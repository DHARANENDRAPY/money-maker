"""
test_new_trading_features.py
Unit tests verifying the 5 advanced accuracy & risk-free trading improvements:
1. TTM Volatility Squeeze Momentum Detector (calculate_ttm_squeeze)
2. Algorithmic Candlestick Pattern Recognition Engine (detect_candlestick_patterns)
3. Sector Concentration & Correlation Guardrail (max 2 per sector)
4. Automated AI Post-Mortem trade reflection
5. Strategy Parameter Optimization & Fine-Tuning Grid Search
"""
import pytest
import datetime
import pandas as pd
import numpy as np
from fastapi import HTTPException

from app.engine.indicators import calculate_ttm_squeeze, detect_candlestick_patterns
from app.routers.paper_trading import portfolio, PlacePaperTradeRequest, place_paper_trade, _generate_ai_post_mortem
from app.routers.backtest import optimize_strategy_parameters, OptimizeRequest
from app.schemas.market_schemas import Quote
from app.services.market_state import market_state


def _generate_test_candles(n: int = 50, base_price: float = 1000.0) -> pd.DataFrame:
    now = datetime.datetime.now(datetime.timezone.utc)
    dates = [now - datetime.timedelta(minutes=5 * (n - i)) for i in range(n)]
    
    np.random.seed(42)
    closes = base_price + np.cumsum(np.random.randn(n) * 1.5)
    highs = closes + 1.0
    lows = closes - 1.0
    opens = closes - 0.5
    volumes = np.full(n, 20000)
    
    df = pd.DataFrame({
        "timestamp": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    })
    df.set_index("timestamp", inplace=True)
    return df


def test_ttm_squeeze_detector():
    """Verify that calculate_ttm_squeeze computes BB and Keltner contraction and expansion."""
    df = _generate_test_candles(40, 500.0)
    res = calculate_ttm_squeeze(df)
    
    assert "squeeze_status" in res
    assert "is_squeeze_on" in res
    assert "is_fired" in res
    assert "momentum_value" in res
    assert isinstance(res["is_squeeze_on"], bool)
    assert isinstance(res["momentum_value"], float)


def test_candlestick_pattern_recognition():
    """Verify detection of key reversal candlestick formations."""
    df = _generate_test_candles(30, 200.0)
    
    # Force a Hammer Pinbar on the last candle:
    # Lower wick >= 2.0 * body and upper wick <= 0.25 * range
    # Open: 204.0, Close: 205.0 (body=1.0), High: 205.2 (upper wick=0.2), Low: 195.0 (lower wick=9.0 >= 2.0)
    df.loc[df.index[-1], 'open'] = 204.0
    df.loc[df.index[-1], 'close'] = 205.0
    df.loc[df.index[-1], 'high'] = 205.2
    df.loc[df.index[-1], 'low'] = 195.0
    
    res = detect_candlestick_patterns(df)
    assert isinstance(res, dict)
    assert "primary_pattern" in res
    assert res["primary_pattern"] == "Hammer (Bullish Pinbar)"
    assert res["bias"] == "BULLISH"


def _make_mock_quote(symbol: str, ltp: float, sector: str) -> Quote:
    return Quote(
        symbol=symbol,
        name=symbol,
        ltp=ltp,
        open=ltp,
        high=ltp * 1.01,
        low=ltp * 0.99,
        close=ltp,
        volume=50000,
        change=0.0,
        change_pct=0.0,
        vwap=ltp,
        day_range_pct=0.5,
        rel_volume=1.0,
        sector=sector,
        last_update="12:00:00",
        data_source="TEST_FEED"
    )


def test_sector_concentration_guardrail():
    """Verify that paper trading rejects order if sector already has 2 active positions."""
    portfolio.reset(1000000.0)
    
    # Inject 2 Banking quotes into cache
    q1 = _make_mock_quote("HDFCBANK", 1600.0, "Banking & Financials")
    q2 = _make_mock_quote("ICICIBANK", 1100.0, "Banking & Financials")
    q3 = _make_mock_quote("KOTAKBANK", 1800.0, "Banking & Financials")
    
    market_state.active_provider._batch_quotes_cache["HDFCBANK"] = q1
    market_state.active_provider._batch_quotes_cache["ICICIBANK"] = q2
    market_state.active_provider._batch_quotes_cache["KOTAKBANK"] = q3
    
    req1 = PlacePaperTradeRequest(symbol="HDFCBANK", direction="LONG", entry_price=1600.0, target_1=1630.0, stop_loss=1580.0, shares=10)
    req2 = PlacePaperTradeRequest(symbol="ICICIBANK", direction="LONG", entry_price=1100.0, target_1=1120.0, stop_loss=1080.0, shares=10)
    
    res1 = place_paper_trade(req1)
    res2 = place_paper_trade(req2)
    assert res1["success"] is True
    assert res2["success"] is True
    
    # 3rd Banking position should be strictly blocked by the Sector Concentration Guardrail
    req3 = PlacePaperTradeRequest(symbol="KOTAKBANK", direction="LONG", entry_price=1800.0, target_1=1830.0, stop_loss=1780.0, shares=10)
    with pytest.raises(HTTPException) as exc_info:
        place_paper_trade(req3)
    assert exc_info.value.status_code == 400
    assert "Sector Concentration Guard" in exc_info.value.detail


def test_ai_post_mortem_generation():
    """Verify that _generate_ai_post_mortem produces structured diagnostic reflections."""
    pos = {"symbol": "TCS", "entry_price": 3800.0}
    
    reflection_t1 = _generate_ai_post_mortem(pos, 3850.0, "TARGET_1_HIT", 500.0)
    assert "Target 1 Captured" in reflection_t1
    assert "#TCS" in reflection_t1
    
    reflection_sl = _generate_ai_post_mortem(pos, 3770.0, "STOP_LOSS_HIT", -300.0)
    assert "Controlled Stop Loss" in reflection_sl
    
    reflection_be = _generate_ai_post_mortem(pos, 3800.0, "RUNNER_BREAKEVEN_EXIT", 10.0)
    assert "Zero-Risk Exit" in reflection_be


def test_backtest_strategy_parameter_optimizer():
    """Verify the grid search optimization matrix generation."""
    req = OptimizeRequest(
        symbol="RELIANCE",
        days=15,
        timeframe="5m",
        initial_capital=100000.0,
        budget_per_trade=10000.0
    )
    res = optimize_strategy_parameters(req)
    assert res["status"] == "success"
    assert res["grid_tested"] == 6
    assert "best_setup" in res
    assert "optimization_matrix" in res
    assert len(res["optimization_matrix"]) == 6
    
    best = res["best_setup"]
    assert "profit_factor" in best
    assert "win_rate" in best
    assert "sl_multiplier" in best
    assert "target_multiplier" in best
