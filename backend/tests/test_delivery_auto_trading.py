import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import datetime
from app.services.ai_auto_trader import ai_auto_trader
from app.routers.paper_trading import portfolio, PlacePaperTradeRequest, place_paper_trade
from app.database import SessionLocal
from app.models.all_models import AITradeTransactionRecord, TradeJournalRecord
from app.schemas.market_schemas import Quote


def test_ai_auto_trader_dual_mode_config():
    """Verify AIAutoTraderService supports both Intraday and Delivery auto-trading."""
    assert hasattr(ai_auto_trader, 'enable_intraday')
    assert hasattr(ai_auto_trader, 'enable_delivery')
    assert ai_auto_trader.enable_intraday is True
    assert ai_auto_trader.enable_delivery is True
    assert ai_auto_trader.delivery_budget_per_order >= 1000.0


def test_add_custom_delivery_trade_execution():
    """Verify add_custom_delivery_trade properly executes a Delivery paper trade with 1x cash sizing."""
    portfolio.available_cash = 50000.0

    symbol = "TATASTEEL"
    # TATASTEEL base price is 158.0. Target 185.0 (> 158.0), SL 145.0 (< 158.0)
    res = ai_auto_trader.add_custom_delivery_trade(
        symbol=symbol,
        entry_price=158.0,
        target_1=185.0,
        target_2=200.0,
        stop_loss=145.0,
        shares=10,
        budget=2000.0
    )

    assert res["success"] is True
    assert res["symbol"] == symbol
    assert res["trade_type"] == "DELIVERY"
    assert res["shares"] == 10
    assert res["target_1"] == 185.0
    assert res["stop_loss"] == 145.0

    pos_id = str(res["position_id"])
    assert pos_id in portfolio.positions
    pos = portfolio.positions[pos_id]
    assert pos["symbol"] == symbol
    assert pos["trade_type"] == "DELIVERY"
    # Sizing for delivery must be 1x cash (no 5x leverage)
    assert pos["margin_used"] == pos["entry_price"] * 10

    # Verify persisted in AITradeTransactionRecord
    db = SessionLocal()
    try:
        tx = db.query(AITradeTransactionRecord).filter(
            AITradeTransactionRecord.trade_id == res["trade_id"]
        ).first()
        assert tx is not None
        assert tx.symbol == symbol
        assert tx.trade_type == "DELIVERY"
        assert tx.status == "OPEN"
        assert tx.quantity == 10
    finally:
        db.close()

    # Clean up position
    portfolio._close_position_internal(pos_id, pos["entry_price"], "TEST_CLEANUP")


def test_delivery_breakeven_trailing_and_target_exit():
    """Verify delivery shares trade like intraday with breakeven trailing stop & automated profit booking."""
    portfolio.available_cash = 50000.0

    symbol = "BEL"
    # Close any lingering test position
    for pid, p in list(portfolio.positions.items()):
        if p.get("symbol") == symbol:
            portfolio._close_position_internal(pid, p.get("entry_price", 380.0), "TEST_SETUP_CLEAN")

    # Live BEL LTP is ~380.0
    entry = 380.0
    target_1 = 410.0  # +30 pts (target)
    stop_loss = 360.0  # -20 pts (SL)
    shares = 10

    res = ai_auto_trader.add_custom_delivery_trade(
        symbol=symbol,
        entry_price=entry,
        target_1=target_1,
        target_2=430.0,
        stop_loss=stop_loss,
        shares=shares,
        budget=4000.0
    )

    pos_id = str(res["position_id"])
    assert pos_id in portfolio.positions
    pos = portfolio.positions[pos_id]
    actual_entry = pos["entry_price"]
    assert pos["stop_loss"] == 360.0

    from app.services.market_state import market_state as ms
    existing_quote = ms.active_provider.get_quote(symbol)

    # 1. Simulate price advance 50% toward Target 1 (entry 380 + half distance (15) = 395)
    # Mock quote at 396.0 (>= 395.0)
    mock_quote = existing_quote.model_copy(update={"ltp": 396.0, "high": 398.0})

    if hasattr(ms.active_provider, '_batch_quotes_cache'):
        ms.active_provider._batch_quotes_cache[symbol] = mock_quote

    # Trigger portfolio health check / summary
    summary = portfolio.get_summary()

    # Check that breakeven trailing stop moved SL to Entry
    assert pos["stop_loss"] == actual_entry

    # 2. Simulate price hitting Target 1 (412.0 >= 410.0)
    mock_quote_tgt = existing_quote.model_copy(update={"ltp": 412.0, "high": 415.0})
    if hasattr(ms.active_provider, '_batch_quotes_cache'):
        ms.active_provider._batch_quotes_cache[symbol] = mock_quote_tgt

    # Trigger auto-exit check
    summary2 = portfolio.get_summary()

    # Position should now be auto-exited with TARGET_1_HIT!
    assert pos_id not in portfolio.positions
    closed_trade = next((t for t in portfolio.closed_trades if str(t.get("position_id")) == pos_id), None)
    assert closed_trade is not None
    assert closed_trade["exit_reason"] == "TARGET_1_HIT"
    assert closed_trade["is_win"] is True
    assert closed_trade["realized_pnl"] > 0

    # Sync into AI Trade Transactions
    ai_auto_trader.sync_closed_positions()

    db = SessionLocal()
    try:
        tx = db.query(AITradeTransactionRecord).filter(
            AITradeTransactionRecord.trade_id == res["trade_id"]
        ).first()
        assert tx is not None
        assert tx.status == "PROFIT_BOOKED"
        assert tx.is_win is True
        assert tx.net_pnl > 0
    finally:
        db.close()


def test_ai_trader_api_router_status_and_toggle():
    """Verify /status and /toggle endpoints in ai_trader router."""
    from app.routers.ai_trader import get_ai_trader_status, toggle_ai_trader, ToggleTraderRequest

    status = get_ai_trader_status()
    assert "enabled" in status
    assert "enable_intraday" in status
    assert "enable_delivery" in status
    assert "trade_budget_per_order" in status
    assert "delivery_budget_per_order" in status
    assert "statistics" in status
    assert "intraday_trades" in status["statistics"]
    assert "delivery_trades" in status["statistics"]

    # Toggle test
    toggle_res = toggle_ai_trader(ToggleTraderRequest(
        enabled=True,
        enable_intraday=True,
        enable_delivery=True,
        delivery_budget=2500.0
    ))
    assert toggle_res["success"] is True
    assert toggle_res["enable_delivery"] is True
    assert toggle_res["delivery_budget_per_order"] == 2500.0
