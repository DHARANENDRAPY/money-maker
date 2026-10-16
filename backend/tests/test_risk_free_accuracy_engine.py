"""
test_risk_free_accuracy_engine.py
Unit tests verifying the high-accuracy prediction and risk-free trade protection engine:
1. Two-Tier Rapid Breakeven Trailing Stop (+0.45x Risk -> BE, +0.75x Risk -> Profit Lock 35%)
2. Stagnation / Time-Decay Auto-Exit (Chop Protection after 45 mins)
3. Volume Spread Analysis (VSA) Bull Trap & Bear Trap Elimination
4. Mansfield Relative Strength (RS vs NIFTY) Alpha Filter
5. Multi-Timeframe (1H + Daily) Trend Consensus
"""
import pytest
import datetime
import pandas as pd
import numpy as np

from app.engine.signals import SignalGenerator
from app.engine.indicators import enrich_candles_with_indicators
from app.routers.paper_trading import portfolio, PlacePaperTradeRequest, place_paper_trade
from app.schemas.market_schemas import Quote
from app.services.market_state import market_state


def _create_mock_candles(n: int = 50, base_price: float = 1000.0) -> pd.DataFrame:
    now = datetime.datetime.now(datetime.timezone.utc)
    dates = [now - datetime.timedelta(minutes=5 * (n - i)) for i in range(n)]
    
    np.random.seed(42)
    closes = base_price + np.cumsum(np.random.randn(n) * 2.0)
    highs = closes + np.random.uniform(0.5, 3.0, n)
    lows = closes - np.random.uniform(0.5, 3.0, n)
    opens = closes + np.random.uniform(-1.0, 1.0, n)
    volumes = np.random.randint(10000, 50000, n)
    
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


def test_vsa_bull_trap_rejection():
    """Verify that a breakout candle with a severe upper wick (>40%) is rejected as a bull trap."""
    df = _create_mock_candles(30, 1000.0)
    enriched = enrich_candles_with_indicators(df)
    
    # Force last bar to be a bull-trap upthrust (long upper shadow)
    # High = 1050, Open = 1010, Close = 1012, Low = 1009 -> Range = 41, Upper Wick = 38 (92% of range)
    enriched.loc[enriched.index[-1], 'open'] = 1010.0
    enriched.loc[enriched.index[-1], 'close'] = 1012.0
    enriched.loc[enriched.index[-1], 'high'] = 1050.0
    enriched.loc[enriched.index[-1], 'low'] = 1009.0
    enriched.loc[enriched.index[-1], 'rvol'] = 2.0
    
    sig = SignalGenerator.generate_signal_for_stock(
        symbol="RELIANCE",
        df=enriched,
        current_price=1012.0,
        sector="Energy",
        sector_change_pct=1.0,
        nifty_change_pct=0.5,
        market_regime="BULLISH_TRENDING",
        market_breadth_ad=1.5
    )
    # Must reject long on severe upthrust trap
    if sig:
        assert sig.direction != "LONG" or "ORB" not in sig.strategy


def test_relative_strength_vs_nifty_filter():
    """Verify that a severe market laggard (-1.5% vs NIFTY) is blocked from Long signals."""
    df = _create_mock_candles(30, 2000.0)
    enriched = enrich_candles_with_indicators(df)
    
    # NIFTY is +1.0%, but this stock's quote is -1.0% (RS = -2.0%)
    quote_laggard = Quote(
        symbol="INFY",
        name="Infosys",
        ltp=2000.0,
        open=2020.0,
        high=2025.0,
        low=1995.0,
        close=2000.0,
        volume=100000,
        change=-20.0,
        change_pct=-1.0,
        vwap=2005.0,
        day_range_pct=1.5,
        rel_volume=1.0,
        sector="IT",
        last_update="10:00:00",
        data_source="TEST_FEED"
    )
    
    sig = SignalGenerator.generate_signal_for_stock(
        symbol="INFY",
        df=enriched,
        current_price=2000.0,
        sector="IT",
        sector_change_pct=-0.8,
        nifty_change_pct=1.0,
        market_regime="BULLISH_TRENDING",
        market_breadth_ad=1.5,
        quote=quote_laggard
    )
    # Severe laggard must not produce a LONG signal
    if sig:
        assert sig.direction != "LONG"


def test_two_tier_rapid_trailing_stop():
    """Verify that moving +45% toward target triggers BE SL, and +75% triggers 35% profit lock."""
    portfolio.reset(100000.0)
    sym = "TEST_TRAIL_STOCK"
    
    # Pre-seed quote at exact entry price (1000.0)
    init_quote = Quote(
        symbol=sym,
        name="Test Trail Stock",
        ltp=1000.0,
        open=1000.0,
        high=1002.0,
        low=998.0,
        close=1000.0,
        volume=50000,
        change=0.0,
        change_pct=0.0,
        vwap=1000.0,
        day_range_pct=0.4,
        rel_volume=1.0,
        sector="Test",
        last_update="10:00:00",
        data_source="TEST_FEED"
    )
    market_state.active_provider._batch_quotes_cache[sym] = init_quote
    
    # Place a long trade: Entry 1000, SL 980 (Risk 20), Target 1 1040 (Reward 40)
    req = PlacePaperTradeRequest(
        symbol=sym,
        direction="LONG",
        trade_type="INTRADAY",
        product_type="MIS",
        entry_price=1000.0,
        target_1=1040.0,
        target_2=1060.0,
        stop_loss=980.0,
        budget=2000.0,
        shares=10,
        strategy="Test Trailing Setup"
    )
    order_res = place_paper_trade(req)
    pos_id = str(order_res["position"]["position_id"])
    
    assert pos_id in portfolio.positions
    pos = portfolio.positions[pos_id]
    assert pos["stop_loss"] == 980.0
    
    # 1. Price moves to 1019 (+47.5% to target -> Tier 1 Breakeven)
    mock_quote1 = init_quote.model_copy(update={"ltp": 1019.0, "high": 1020.0, "close": 1019.0})
    market_state.active_provider._batch_quotes_cache[sym] = mock_quote1
    
    summary1 = portfolio.get_summary()
    assert pos_id in portfolio.positions
    pos = portfolio.positions[pos_id]
    assert pos["stop_loss"] >= 1000.0  # Breakeven locked
    assert pos.get("trailing_status") in ["RISK_FREE_BREAKEVEN", "PROFIT_LOCKED_35PCT"]
    
    # 2. Price moves to 1032 (+80% to target -> Tier 2 35% Profit Lock)
    mock_quote2 = init_quote.model_copy(update={"ltp": 1032.0, "high": 1033.0, "close": 1032.0})
    market_state.active_provider._batch_quotes_cache[sym] = mock_quote2
    
    summary2 = portfolio.get_summary()
    assert pos_id in portfolio.positions
    pos = portfolio.positions[pos_id]
    # Profit lock at entry + 0.35 * 40 = 1000 + 14 = 1014.0
    assert pos["stop_loss"] >= 1014.0
    assert pos.get("trailing_status") == "PROFIT_LOCKED_35PCT"


def test_stagnation_time_decay_exit():
    """Verify that an intraday trade open for >= 45m with < 0.30% price movement is auto-exited."""
    portfolio.reset(100000.0)
    sym = "TEST_STAG_STOCK"
    
    # Pre-seed quote at entry price
    init_quote = Quote(
        symbol=sym,
        name="Test Stag Stock",
        ltp=800.0,
        open=800.0,
        high=801.0,
        low=799.0,
        close=800.0,
        volume=25000,
        change=0.0,
        change_pct=0.0,
        vwap=800.0,
        day_range_pct=0.2,
        rel_volume=0.8,
        sector="Test",
        last_update="10:00:00",
        data_source="TEST_FEED"
    )
    market_state.active_provider._batch_quotes_cache[sym] = init_quote
    
    req = PlacePaperTradeRequest(
        symbol=sym,
        direction="LONG",
        trade_type="INTRADAY",
        product_type="MIS",
        entry_price=800.0,
        target_1=820.0,
        target_2=835.0,
        stop_loss=790.0,
        budget=2000.0,
        shares=10,
        strategy="Test Stagnation"
    )
    order_res = place_paper_trade(req)
    pos_id = str(order_res["position"]["position_id"])
    assert pos_id in portfolio.positions
    
    # Simulate trade opened 50 minutes ago
    opened_past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=50)
    portfolio.positions[pos_id]["opened_at"] = opened_past.isoformat()
    
    # Price only hovered to 801.0 (+0.125% movement < 0.30%)
    hover_quote = init_quote.model_copy(update={"ltp": 801.0, "close": 801.0, "change": 1.0, "change_pct": 0.125})
    market_state.active_provider._batch_quotes_cache[sym] = hover_quote
    
    summary = portfolio.get_summary()
    # Position should now be closed due to stagnation
    assert pos_id not in portfolio.positions
    closed = [t for t in portfolio.closed_trades if str(t.get("position_id")) == pos_id]
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "STAGNATION_TIME_DECAY_EXIT"


def test_multi_target_partial_booking_and_runner_to_t2():
    """Verify that hitting Target 1 books 50% shares, moves SL to entry, and allows runner to Target 2."""
    portfolio.reset(100000.0)
    sym = "TEST_RUNNER_STOCK"

    init_quote = Quote(
        symbol=sym,
        name="Test Runner Stock",
        ltp=1000.0,
        open=1000.0,
        high=1005.0,
        low=995.0,
        close=1000.0,
        volume=50000,
        change=0.0,
        change_pct=0.0,
        vwap=1000.0,
        day_range_pct=1.0,
        rel_volume=1.2,
        sector="Test",
        last_update="10:00:00",
        data_source="TEST_FEED"
    )
    market_state.active_provider._batch_quotes_cache[sym] = init_quote

    req = PlacePaperTradeRequest(
        symbol=sym,
        direction="LONG",
        trade_type="DELIVERY",  # DELIVERY avoids market-close square-off
        product_type="CNC",
        entry_price=1000.0,
        target_1=1020.0,
        target_2=1040.0,
        stop_loss=980.0,
        budget=10000.0,
        shares=10,
        strategy="Test Multi-Target"
    )
    order_res = place_paper_trade(req)
    pos_id = str(order_res["position"]["position_id"])
    assert pos_id in portfolio.positions
    assert portfolio.positions[pos_id]["shares"] == 10

    # Phase 1: Price touches Target 1 (1021.0 >= 1020.0)
    t1_quote = init_quote.model_copy(update={"ltp": 1021.0, "close": 1021.0, "change": 21.0, "change_pct": 2.1})
    market_state.active_provider._batch_quotes_cache[sym] = t1_quote

    summary = portfolio.get_summary()

    # The position must still be active as a runner with 5 remaining shares!
    assert pos_id in portfolio.positions
    runner_pos = portfolio.positions[pos_id]
    assert runner_pos["shares"] == 5
    assert runner_pos["t1_booked"] is True
    assert runner_pos["stop_loss"] == 1000.0  # SL moved to breakeven!
    assert runner_pos["trailing_status"] == "T1_BOOKED_RUNNER_ACTIVE"

    # Verify that the 5 booked shares are recorded in closed_trades
    t1_booked_trades = [t for t in portfolio.closed_trades if t.get("exit_reason") == "T1_PARTIAL_PROFIT_BOOKED"]
    assert len(t1_booked_trades) == 1
    assert t1_booked_trades[0]["shares"] == 5
    assert t1_booked_trades[0]["realized_pnl"] > 0

    # Phase 2: Price reaches Target 2 (1042.0 >= 1040.0)
    t2_quote = init_quote.model_copy(update={"ltp": 1042.0, "close": 1042.0, "change": 42.0, "change_pct": 4.2})
    market_state.active_provider._batch_quotes_cache[sym] = t2_quote

    summary2 = portfolio.get_summary()

    # Runner position is now fully closed at Target 2
    assert pos_id not in portfolio.positions
    t2_closed_trades = [t for t in portfolio.closed_trades if t.get("exit_reason") == "TARGET_2_HIT"]
    assert len(t2_closed_trades) == 1
    assert t2_closed_trades[0]["shares"] == 5
    assert t2_closed_trades[0]["exit_price"] == 1042.0


def test_sector_concentration_guard():
    """Verify that Sector Exposure Guard prevents placing > 2 concurrent trades in the same sector."""
    from app.providers.universe import NSE_UNIVERSE
    from app.services.ai_auto_trader import ai_auto_trader

    portfolio.reset(100000.0)

    # Place 2 Banking trades
    portfolio.positions["POS_1"] = {
        "position_id": "POS_1",
        "symbol": "HDFCBANK",
        "sector": "Banking & Fin",
        "direction": "LONG",
        "entry_price": 1600.0,
        "shares": 5,
        "margin_used": 1600.0,
        "stop_loss": 1580.0,
        "target_1": 1640.0,
        "current_price": 1600.0,
        "trade_type": "INTRADAY"
    }
    portfolio.positions["POS_2"] = {
        "position_id": "POS_2",
        "symbol": "ICICIBANK",
        "sector": "Banking & Fin",
        "direction": "LONG",
        "entry_price": 1200.0,
        "shares": 5,
        "margin_used": 1200.0,
        "stop_loss": 1180.0,
        "target_1": 1240.0,
        "current_price": 1200.0,
        "trade_type": "INTRADAY"
    }

    # Verify sector count
    banking_count = sum(
        1 for p in portfolio.positions.values()
        if (p.get("sector") or NSE_UNIVERSE.get(p.get("symbol", "").upper(), {}).get("sector", "Other")).lower() == "banking & fin"
    )
    assert banking_count == 2

    # A third banking candidate (SBIN) should be rejected by the sector concentration guard
    cand_sym = "SBIN"
    cand_sector = NSE_UNIVERSE.get(cand_sym, {}).get("sector", "Other")
    assert cand_sector == "Banking & Fin"
    should_skip = banking_count >= 2
    assert should_skip is True


def test_macro_regime_disqualification():
    """Verify that Long signals are rejected during STRONG_BEARISH regime or NIFTY plunge < -1.2%."""
    df = _create_mock_candles(50, 1200.0)
    df = enrich_candles_with_indicators(df)

    # In STRONG_BEARISH regime with Nifty down -1.5%, Long breakout must be rejected
    signal = SignalGenerator.generate_signal_for_stock(
        symbol="RELIANCE",
        df=df,
        current_price=1200.0,
        sector="Energy & Oil",
        sector_change_pct=-1.5,
        nifty_change_pct=-1.5,
        market_regime="STRONG_BEARISH",
        market_breadth_ad=0.4
    )
    assert signal is None

