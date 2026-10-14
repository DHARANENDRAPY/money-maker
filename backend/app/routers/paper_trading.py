"""
Paper Trading & Portfolio Simulator Engine
Allows risk-free live paper trading with virtual capital (default ₹10,000).
Features:
- 1-Click order execution from Intraday and Delivery recommendations
- Dynamic position sizing tailored for ₹1,000 budgets
- Real-time P&L tracking against live broker ticks
- Automated target & stop-loss execution (auto-exits when Target 1 / SL is hit)
- Complete performance analytics (Win Rate, Total P&L, Profit Factor)
"""
import uuid
import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services.market_state import market_state
from app.database import SessionLocal
from app.models.all_models import TradeJournalRecord

router = APIRouter(prefix="/paper", tags=["Paper Trading Simulator"])


class PlacePaperTradeRequest(BaseModel):
    symbol: str
    direction: str = "LONG"  # LONG or SHORT
    trade_type: Optional[str] = None  # INTRADAY or DELIVERY
    product_type: Optional[str] = None  # MIS or CNC
    entry_price: float
    target_1: float
    target_2: Optional[float] = None
    stop_loss: float
    budget: float = 1000.0  # User's allocated budget in INR
    shares: Optional[int] = None
    quantity: Optional[int] = None  # alias for shares
    strategy: Optional[str] = "AI Setup"
    source: Optional[str] = None


# In-memory paper trading portfolio store (persists during backend session)
DEFAULT_PAPER_CAPITAL = 10000000.0  # ₹1 Crore (10,000,000 INR)

class PaperPortfolioStore:
    def __init__(self):
        self.starting_cash = DEFAULT_PAPER_CAPITAL
        self.available_cash = DEFAULT_PAPER_CAPITAL
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        self._load_from_db()

    def _load_from_db(self):
        db = SessionLocal()
        try:
            records = db.query(TradeJournalRecord).all()
            self.positions.clear()
            self.closed_trades.clear()
            margin_used_total = 0.0
            
            for r in records:
                # Reconstruct position dict
                pos = {
                    "position_id": str(r.id),
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "trade_type": r.tags[0] if r.tags and len(r.tags)>0 else "INTRADAY",
                    "strategy": r.setup_strategy or "AI Algorithmic Setup",
                    "entry_price": r.actual_entry or r.planned_entry,
                    "shares": r.quantity,
                    "allocated_budget": 1000.0,
                    "target_1": r.planned_target,
                    "target_2": r.planned_target * 1.08,
                    "stop_loss": r.planned_stop_loss,
                    "current_price": r.actual_entry or r.planned_entry,
                    "unrealized_pnl": 0.0,
                    "unrealized_pct": 0.0,
                    "unrealized_pnl_pct": 0.0,
                    "opened_at": r.entry_time.isoformat() + "Z" if r.entry_time else datetime.datetime.utcnow().isoformat() + "Z",
                    "t1_booked": False
                }
                
                margin_mult = 5.0 if pos["trade_type"] == "INTRADAY" else 1.0
                pos["margin_used"] = round((pos["shares"] * pos["entry_price"]) / margin_mult, 2)

                if r.exit_time:
                    # Closed trade
                    pos["exit_price"] = r.actual_exit or r.planned_entry
                    pos["exit_time"] = r.exit_time.isoformat() + "Z" if r.exit_time else ""
                    pos["exit_reason"] = r.notes or "MANUAL_EXIT"
                    pos["gross_pnl"] = r.gross_pnl or 0.0
                    pos["charges"] = r.total_charges or 0.0
                    pos["realized_pnl"] = r.net_pnl or 0.0
                    if pos["entry_price"] > 0 and pos["shares"] > 0:
                        pos["realized_pnl_pct"] = round(((r.net_pnl or 0.0) / (pos["entry_price"] * pos["shares"])) * 100.0, 2)
                    else:
                        pos["realized_pnl_pct"] = 0.0
                    pos["is_win"] = (r.net_pnl or 0.0) > 0
                    self.closed_trades.append(pos)
                else:
                    # Open position
                    self.positions[pos["position_id"]] = pos
                    margin_used_total += pos["margin_used"]
                    
            # Recalculate available cash based on realized PnL of closed trades
            realized_pnl_total = sum(t.get("realized_pnl", 0.0) for t in self.closed_trades)
            self.available_cash = self.starting_cash + realized_pnl_total - margin_used_total
            
        except Exception as e:
            print(f"Error loading paper portfolio from DB: {e}")
        finally:
            db.close()

    def reset(self, initial_cash: float = DEFAULT_PAPER_CAPITAL):
        db = SessionLocal()
        try:
            from app.models.all_models import (
                TradeJournalRecord,
                RecommendationHistoryRecord,
                AITradeTransactionRecord,
                SignalRecord,
                AlertRecord
            )
            db.query(TradeJournalRecord).delete()
            db.query(RecommendationHistoryRecord).delete()
            db.query(AITradeTransactionRecord).delete()
            db.query(SignalRecord).delete()
            db.query(AlertRecord).delete()
            db.commit()
        except Exception as e:
            print(f"Error clearing DB: {e}")
        finally:
            db.close()
            
        self.starting_cash = initial_cash
        self.available_cash = initial_cash
        self.positions.clear()
        self.closed_trades.clear()
        market_state.active_signals.clear()

    def get_summary(self) -> Dict[str, Any]:
        provider = market_state.active_provider
        quotes = provider.get_all_quotes()

        # Update floating P&L and check automated exit conditions
        open_list = []
        realized_pnl = sum(t.get("realized_pnl", 0.0) for t in self.closed_trades)
        total_unrealized_pnl = 0.0
        margin_locked = 0.0

        for pos_id, pos in list(self.positions.items()):
            sym = pos["symbol"]
            quote = quotes.get(sym)
            curr_price = float(quote.ltp) if (quote and getattr(quote, 'ltp', 0) > 0) else float(pos["entry_price"])
            pos["current_price"] = round(curr_price, 2)

            is_long = pos["direction"] == "LONG"
            entry = pos["entry_price"]
            qty = pos["shares"]
            t1 = pos["target_1"]
            t2 = pos.get("target_2") or (entry + (t1 - entry) * 1.5 if is_long else entry - (entry - t1) * 1.5)
            sl = pos["stop_loss"]

            # Calculate floating P&L
            if is_long:
                unrealized = (curr_price - entry) * qty
                unrealized_pct = ((curr_price - entry) / entry) * 100.0 if entry > 0 else 0.0
            else:
                unrealized = (entry - curr_price) * qty
                unrealized_pct = ((entry - curr_price) / entry) * 100.0 if entry > 0 else 0.0

            pos["unrealized_pnl"] = round(unrealized, 2)
            pos["unrealized_pct"] = round(unrealized_pct, 2)
            pos["unrealized_pnl_pct"] = round(unrealized_pct, 2)
            total_unrealized_pnl += unrealized
            margin_locked += pos["margin_used"]

            # Check Auto-Exit Triggers
            auto_exit_reason = None

            # 1. Indian Stock Exchange 15:15 IST Intraday Auto-Square-Off (MIS rule)
            if pos.get("trade_type") == "INTRADAY":
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)
                # Auto square off intraday after 15:15 IST (3:15 PM) on weekdays
                if now_ist.weekday() < 5 and (now_ist.hour > 15 or (now_ist.hour == 15 and now_ist.minute >= 15)):
                    auto_exit_reason = "INTRADAY_MARKET_CLOSE_SQUAREOFF"

            # 2. Target 1 & Stop Loss Price Triggers (STRICTLY FOR INTRADAY ONLY; NEVER AUTO-SELL DELIVERY)
            # Must have an active, verified positive live price to avoid false trigger on 0.0 offline quote
            has_live_price = bool(quote and getattr(quote, 'ltp', 0) > 0)
            if not auto_exit_reason and pos.get("trade_type") == "INTRADAY" and has_live_price:
                if is_long:
                    # Breakeven Trailing: If price advances >= 50% toward Target 1, move Stop Loss to Entry
                    half_target_dist = abs(t1 - entry) * 0.5
                    if curr_price >= (entry + half_target_dist) and sl < entry:
                        pos["stop_loss"] = entry
                        sl = entry

                    if curr_price >= t1 and not pos.get("t1_booked"):
                        auto_exit_reason = "TARGET_1_HIT"
                    elif curr_price <= sl:
                        auto_exit_reason = "STOP_LOSS_HIT"
                else:
                    # Breakeven Trailing: If price advances >= 50% toward Target 1 (short), move Stop Loss to Entry
                    half_target_dist = abs(entry - t1) * 0.5
                    if curr_price <= (entry - half_target_dist) and sl > entry:
                        pos["stop_loss"] = entry
                        sl = entry

                    if curr_price <= t1 and not pos.get("t1_booked"):
                        auto_exit_reason = "TARGET_1_HIT"
                    elif curr_price >= sl:
                        auto_exit_reason = "STOP_LOSS_HIT"

            if auto_exit_reason:
                # Close trade automatically at current live market price
                closed = self._close_position_internal(pos_id, curr_price, auto_exit_reason)
                continue

            open_list.append(pos)

        # Performance metrics
        total_trades = len(self.closed_trades)
        winning_trades = [t for t in self.closed_trades if t.get("realized_pnl", 0) > 0]
        losing_trades = [t for t in self.closed_trades if t.get("realized_pnl", 0) <= 0]
        win_rate = round((len(winning_trades) / total_trades * 100.0), 1) if total_trades > 0 else 0.0
        
        gross_profit = sum(t.get("realized_pnl", 0) for t in winning_trades)
        gross_loss = abs(sum(t.get("realized_pnl", 0) for t in losing_trades))
        profit_factor = round(gross_profit / max(gross_loss, 0.01), 2) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        # Day Profit & Loss Breakdown (IST today)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)
        today_date_str = now_ist.strftime("%Y-%m-%d")

        today_closed = []
        for t in self.closed_trades:
            exit_time_str = t.get("exit_time", "")
            if exit_time_str:
                try:
                    # Parse ISO string
                    dt = datetime.datetime.fromisoformat(exit_time_str.replace("Z", "+00:00"))
                    ist_dt = dt + datetime.timedelta(hours=5, minutes=30)
                    if ist_dt.strftime("%Y-%m-%d") == today_date_str:
                        today_closed.append(t)
                except Exception:
                    pass

        today_profit = sum(t.get("realized_pnl", 0) for t in today_closed if t.get("realized_pnl", 0) > 0)
        today_loss = abs(sum(t.get("realized_pnl", 0) for t in today_closed if t.get("realized_pnl", 0) < 0))
        today_realized_pnl = today_profit - today_loss
        today_total_pnl = today_realized_pnl + total_unrealized_pnl

        # Total charges across all closed trades
        total_charges = sum(t.get("charges", 0) for t in self.closed_trades)

        total_portfolio_value = round(self.available_cash + margin_locked + total_unrealized_pnl, 2)
        total_pnl = round(total_portfolio_value - self.starting_cash, 2)
        total_pnl_pct = round((total_pnl / self.starting_cash) * 100.0, 2)

        return {
            "starting_cash": self.starting_cash,
            "available_cash": round(self.available_cash, 2),
            "margin_locked": round(margin_locked, 2),
            "total_portfolio_value": total_portfolio_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "today_profit": round(today_profit, 2),
            "today_loss": round(today_loss, 2),
            "today_realized_pnl": round(today_realized_pnl, 2),
            "today_total_pnl": round(today_total_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "total_charges": round(total_charges, 2),
            "open_positions": open_list,
            "open_count": len(open_list),
            "closed_trades": self.closed_trades[::-1],  # newest first
            "closed_count": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "wins_count": len(winning_trades),
            "losses_count": len(losing_trades)
        }

    def _close_position_internal(self, pos_id: str, exit_price: float, exit_reason: str) -> Dict[str, Any]:
        pos = self.positions.pop(pos_id, None)
        if not pos:
            return {}

        is_long = pos["direction"] == "LONG"
        entry = pos["entry_price"]
        qty = pos["shares"]
        trade_type = pos.get("trade_type", "INTRADAY")

        # Gross PnL
        if is_long:
            gross_pnl = (exit_price - entry) * qty
            pnl_pct = ((exit_price - entry) / entry) * 100.0
        else:
            gross_pnl = (entry - exit_price) * qty
            pnl_pct = ((entry - exit_price) / entry) * 100.0

        # Realistic NSE Charges & Brokerage (Discount broker model: ₹20/order)
        turnover = (entry * qty) + (exit_price * qty)
        brokerage = min(40.0, turnover * 0.0003) if trade_type == "INTRADAY" else min(40.0, turnover * 0.0005)
        stt = (exit_price * qty) * 0.00025 if trade_type == "INTRADAY" else turnover * 0.001
        exchange_charges = turnover * 0.0000345
        gst = (brokerage + exchange_charges) * 0.18
        stamp_duty = (entry * qty) * 0.00003
        total_charges = round(brokerage + stt + exchange_charges + gst + stamp_duty, 2)

        net_pnl = round(gross_pnl - total_charges, 2)
        gross_pnl = round(gross_pnl, 2)
        pnl_pct = round(pnl_pct, 2)

        # Release margin and add net P&L back to cash
        self.available_cash += pos["margin_used"] + net_pnl

        closed_record = {
            **pos,
            "exit_price": round(exit_price, 2),
            "exit_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "exit_reason": exit_reason,
            "gross_pnl": gross_pnl,
            "charges": total_charges,
            "realized_pnl": net_pnl,
            "realized_pnl_pct": pnl_pct,
            "is_win": net_pnl > 0
        }
        self.closed_trades.append(closed_record)
        
        # Save exit to DB
        db = SessionLocal()
        try:
            r = db.query(TradeJournalRecord).filter(TradeJournalRecord.id == int(pos_id)).first()
            if r:
                r.exit_time = datetime.datetime.now(datetime.timezone.utc)
                r.actual_exit = closed_record["exit_price"]
                r.gross_pnl = gross_pnl
                r.brokerage_charges = brokerage
                r.stt_charges = stt
                r.exchange_charges = exchange_charges
                r.gst_charges = gst
                r.stamp_duty = stamp_duty
                r.total_charges = total_charges
                r.net_pnl = net_pnl
                r.notes = closed_record["exit_reason"]
                db.commit()

            # Also sync with AITradeTransactionRecord if this was an AI trade
            from sqlalchemy import or_, and_
            from app.models.all_models import AITradeTransactionRecord
            ai_tx = db.query(AITradeTransactionRecord).filter(
                or_(
                    AITradeTransactionRecord.position_id == str(pos_id),
                    and_(
                        AITradeTransactionRecord.symbol == pos["symbol"],
                        AITradeTransactionRecord.status == "OPEN"
                    )
                )
            ).first()
            if ai_tx:
                ai_tx.exit_time = datetime.datetime.now(datetime.timezone.utc)
                ai_tx.exit_price = closed_record["exit_price"]
                ai_tx.gross_pnl = gross_pnl
                ai_tx.net_pnl = net_pnl
                ai_tx.pnl_pct = pnl_pct
                ai_tx.total_charges = total_charges
                ai_tx.is_win = (net_pnl > 0)
                ai_tx.exit_reason = exit_reason
                if "TARGET" in exit_reason.upper():
                    ai_tx.status = "PROFIT_BOOKED"
                elif "STOP" in exit_reason.upper():
                    ai_tx.status = "STOP_LOSS_HIT"
                else:
                    ai_tx.status = "CLOSED"
                db.commit()
        except Exception as e:
            print(f"Error saving close to DB: {e}")
        finally:
            db.close()
            
        return closed_record


portfolio = PaperPortfolioStore()


@router.get("/portfolio")
def get_paper_portfolio() -> Dict[str, Any]:
    """Returns the current live paper trading portfolio and performance metrics."""
    portfolio._load_from_db()
    return portfolio.get_summary()


@router.post("/reload")
def reload_paper_portfolio() -> Dict[str, Any]:
    """Forces reloading portfolio positions and closed trades from DB."""
    portfolio._load_from_db()
    return {
        "status": "SUCCESS",
        "open_count": len(portfolio.positions),
        "closed_count": len(portfolio.closed_trades)
    }


@router.post("/place-trade")
def place_paper_trade(req: PlacePaperTradeRequest) -> Dict[str, Any]:
    """
    Executes a simulated paper order with custom capital budget (default ₹1,000).
    """
    # Use live quote LTP if live feed is available, ensuring realistic execution at current price
    provider = market_state.active_provider
    live_quote = provider.get_quote(req.symbol)
    if live_quote and live_quote.ltp > 0:
        entry = live_quote.ltp
    else:
        entry = req.entry_price

    if entry <= 0:
        raise HTTPException(status_code=400, detail="Invalid entry price")

    # Determine trade type: CNC / DELIVERY = 1x cash (NO LEVERAGE), MIS / INTRADAY = 5x leverage
    req_type = (req.trade_type or req.product_type or "INTRADAY").upper()
    is_delivery = ("DELIVERY" in req_type) or ("CNC" in req_type)
    normalized_trade_type = "DELIVERY" if is_delivery else "INTRADAY"

    # Only intraday gets 5x leverage (20% margin). Delivery requires 100% full cash (1x, NO LEVERAGE).
    margin_mult = 1.0 if is_delivery else 5.0

    qty_val = req.shares or req.quantity
    if qty_val and qty_val > 0:
        shares = qty_val
    else:
        # Sizing according to user's budget
        buying_power = req.budget * margin_mult
        shares = max(1, int(buying_power / entry))

    margin_required = round((shares * entry) / margin_mult, 2)

    if margin_required > portfolio.available_cash:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient virtual cash. Required cash/margin: ₹{margin_required:,.2f}, Available: ₹{portfolio.available_cash:,.2f}"
        )

    # Deduct margin
    portfolio.available_cash -= margin_required

    # Add to DB first to get ID
    db = SessionLocal()
    pos_id_str = f"POS-{uuid.uuid4().hex[:8].upper()}"
    try:
        r = TradeJournalRecord(
            symbol=req.symbol,
            direction=req.direction.upper(),
            planned_entry=round(entry, 2),
            actual_entry=round(entry, 2),
            planned_stop_loss=round(req.stop_loss, 2),
            actual_stop_loss=round(req.stop_loss, 2),
            planned_target=round(req.target_1, 2),
            quantity=shares,
            setup_strategy=req.strategy or ("AI Delivery Setup" if is_delivery else "AI Intraday Setup"),
            tags=[normalized_trade_type],
            notes="OPEN"
        )
        db.add(r)
        db.commit()
        db.refresh(r)
        pos_id_str = str(r.id)
    except Exception as e:
        print(f"Error creating position in DB: {e}")
    finally:
        db.close()

    position_data = {
        "position_id": pos_id_str,
        "symbol": req.symbol,
        "direction": req.direction.upper(),
        "trade_type": normalized_trade_type,
        "strategy": req.strategy or ("AI Delivery Setup" if is_delivery else "AI Intraday Setup"),
        "entry_price": round(entry, 2),
        "shares": shares,
        "margin_used": margin_required,
        "allocated_budget": req.budget,
        "target_1": round(req.target_1, 2),
        "target_2": round(req.target_2, 2) if req.target_2 else round(req.target_1 * 1.08, 2),
        "stop_loss": round(req.stop_loss, 2),
        "current_price": round(entry, 2),
        "unrealized_pnl": 0.0,
        "unrealized_pct": 0.0,
        "unrealized_pnl_pct": 0.0,
        "opened_at": datetime.datetime.utcnow().isoformat() + "Z",
        "t1_booked": False
    }

    portfolio.positions[pos_id_str] = position_data

    return {
        "success": True,
        "message": f"Successfully placed {req.trade_type} paper trade: {shares} shares of #{req.symbol} @ ₹{entry:,.2f}",
        "position": position_data,
        "portfolio": portfolio.get_summary()
    }


@router.post("/close-position")
def close_paper_position(position_id: str = Query(..., description="ID of position to close")) -> Dict[str, Any]:
    """Manually closes an open paper trade position at the current live market price."""
    pos = portfolio.positions.get(position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found or already closed.")

    provider = market_state.active_provider
    quote = provider.get_quote(pos["symbol"])
    curr_price = quote.ltp if quote else pos["entry_price"]

    closed = portfolio._close_position_internal(position_id, curr_price, "MANUAL_EXIT")
    return {
        "success": True,
        "message": f"Position #{pos['symbol']} closed at ₹{curr_price:,.2f}. Realized P&L: ₹{closed.get('realized_pnl', 0):,.2f}",
        "closed_trade": closed,
        "portfolio": portfolio.get_summary()
    }


@router.post("/reset")
def reset_paper_portfolio(initial_cash: float = Query(10000.0, description="Starting virtual cash in INR")) -> Dict[str, Any]:
    """Resets the virtual paper portfolio to starting balance."""
    portfolio.reset(initial_cash)
    return {
        "success": True,
        "message": f"Paper portfolio reset to ₹{initial_cash:,.2f} virtual cash.",
        "portfolio": portfolio.get_summary()
    }


@router.get("/history")
def get_paper_trading_history(limit: int = 100) -> Dict[str, Any]:
    """
    Returns the complete persistent history of all paper trades from the SQLite database,
    including exact timestamps for when bought and when sold, entry and exit prices,
    brokerage/statutory fees, and realized profit or loss.
    """
    db = SessionLocal()
    try:
        records = db.query(TradeJournalRecord).order_by(TradeJournalRecord.entry_time.desc()).limit(limit).all()
        history = []
        for r in records:
            history.append({
                "id": r.id,
                "symbol": r.symbol,
                "direction": r.direction,
                "trade_type": r.tags[0] if r.tags and len(r.tags) > 0 else "INTRADAY",
                "strategy": r.setup_strategy or "AI Algorithmic Setup",
                "shares": r.quantity,
                "bought_at_price": r.actual_entry or r.planned_entry,
                "bought_at_time": r.entry_time.isoformat() + "Z" if r.entry_time else None,
                "sold_at_price": r.actual_exit,
                "sold_at_time": r.exit_time.isoformat() + "Z" if r.exit_time else None,
                "status": "CLOSED" if r.exit_time else "OPEN",
                "exit_reason": r.notes if r.exit_time else "POSITION_OPEN",
                "planned_target": r.planned_target,
                "planned_stop_loss": r.planned_stop_loss,
                "gross_pnl": r.gross_pnl or 0.0,
                "charges": r.total_charges or 0.0,
                "net_pnl": r.net_pnl or 0.0,
                "is_win": (r.net_pnl or 0.0) > 0 if r.exit_time else None
            })

        total_closed = [h for h in history if h["status"] == "CLOSED"]
        wins = [h for h in total_closed if h["is_win"]]
        win_rate = round((len(wins) / len(total_closed) * 100.0), 1) if total_closed else 0.0

        return {
            "total_count": len(history),
            "open_count": len([h for h in history if h["status"] == "OPEN"]),
            "closed_count": len(total_closed),
            "win_rate": win_rate,
            "history": history
        }
    finally:
        db.close()
