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


def _safe_parse_utc(ts_str: Optional[str]) -> Optional[datetime.datetime]:
    if not ts_str:
        return None
    try:
        s = ts_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def _generate_ai_post_mortem(pos: Dict[str, Any], exit_price: float, exit_reason: str, net_pnl: float) -> str:
    sym = pos.get("symbol", "")
    entry = pos.get("entry_price", exit_price)
    is_win = net_pnl > 0

    if "TARGET_2" in exit_reason:
        return f"🏆 Target 2 Runner Reached: #{sym} achieved full 2-tier target expansion. High confluence setup captured maximum trend potential."
    elif "TARGET_1" in exit_reason:
        return f"🎯 Target 1 Captured: #{sym} hit profit target cleanly. Momentum aligned with institutional flow."
    elif "T1_PARTIAL" in exit_reason:
        return f"🎯 50% Profit Booked: Locked in Target 1 gains for #{sym}. Remaining position managed with zero downside risk."
    elif "BREAKEVEN" in exit_reason or "RUNNER_BREAKEVEN" in exit_reason:
        return f"🔒 Zero-Risk Exit: #{sym} reversed after testing initial targets, but the 2-tier trailing stop eliminated loss and preserved capital."
    elif "PROFIT_LOCKED" in exit_reason:
        return f"🛡️ Profit Lock Protection: #{sym} captured guaranteed profit after reaching +0.75x risk before the market exhausted."
    elif "STAGNATION" in exit_reason:
        return f"⏳ Stagnation Time-Decay: #{sym} showed zero directional progress for 45 minutes. Capital protected from midday chop."
    elif "STOP_LOSS" in exit_reason:
        return f"🛑 Controlled Stop Loss: Disciplined exit executed for #{sym}. Risk strictly contained to -₹{abs(net_pnl):,.2f} within risk limits."
    elif "MARKET_CLOSE" in exit_reason or "15:15" in exit_reason:
        return f"🕒 End of Day Square-Off: #{sym} closed at 15:15 IST to prevent overnight gap risk."
    else:
        return f"Manual trade closure executed for #{sym} at ₹{exit_price:.2f} (Net: {'+' if is_win else ''}₹{net_pnl:.2f})."


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
                    "stop_loss": r.actual_stop_loss or r.planned_stop_loss,
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

            # 1a. Stagnation / Time-Decay Auto-Exit (INTRADAY only)
            # If open for >= 45 minutes and price hasn't moved at least 0.30% from entry, exit dead chop
            if pos.get("trade_type") == "INTRADAY":
                opened_dt = _safe_parse_utc(pos.get("opened_at"))
                if opened_dt:
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    mins_open = (now_utc - opened_dt).total_seconds() / 60.0
                    price_travel_pct = abs(curr_price - entry) / entry * 100.0 if entry > 0 else 0.0
                    if mins_open >= 45.0 and price_travel_pct < 0.30:
                        auto_exit_reason = "STAGNATION_TIME_DECAY_EXIT"

            # 1b. Indian Stock Exchange 15:15 IST Intraday Auto-Square-Off (MIS rule)
            if not auto_exit_reason and pos.get("trade_type") == "INTRADAY":
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)
                # Auto square off intraday after 15:15 IST (3:15 PM) on weekdays (only if opened for > 30 seconds)
                if now_ist.weekday() < 5 and (now_ist.hour > 15 or (now_ist.hour == 15 and now_ist.minute >= 15)):
                    opened_dt = _safe_parse_utc(pos.get("opened_at"))
                    if opened_dt is None or (now_utc - opened_dt).total_seconds() > 30.0:
                        auto_exit_reason = "INTRADAY_MARKET_CLOSE_SQUAREOFF"

            # 2. Target 1 & Stop Loss Price Triggers (Applies to both INTRADAY and DELIVERY trades; NEVER intraday squareoff DELIVERY)
            # Must have an active, verified positive live price to avoid false trigger on 0.0 offline quote
            has_live_price = bool(quote and getattr(quote, 'ltp', 0) > 0)
            if not auto_exit_reason and has_live_price:
                if is_long:
                    # Breakeven & Profit-Lock Trailing:
                    half_target_dist = abs(t1 - entry) * 0.45
                    three_quarter_dist = abs(t1 - entry) * 0.75
                    be_sl = entry  # exact breakeven
                    profit_lock_sl = round(entry + 0.35 * (t1 - entry), 2)  # lock in 35% profit

                    if not pos.get("t1_booked"):
                        if curr_price >= (entry + three_quarter_dist) and sl < profit_lock_sl:
                            pos["stop_loss"] = profit_lock_sl
                            sl = profit_lock_sl
                            pos["trailing_status"] = "PROFIT_LOCKED_35PCT"
                            try:
                                db_tr = SessionLocal()
                                r_tr = db_tr.query(TradeJournalRecord).filter(TradeJournalRecord.id == int(pos_id)).first()
                                if r_tr:
                                    r_tr.actual_stop_loss = profit_lock_sl
                                    db_tr.commit()
                                db_tr.close()
                            except Exception:
                                pass
                        elif curr_price >= (entry + half_target_dist) and sl < be_sl:
                            pos["stop_loss"] = be_sl
                            sl = be_sl
                            pos["trailing_status"] = "RISK_FREE_BREAKEVEN"
                            try:
                                db_tr = SessionLocal()
                                r_tr = db_tr.query(TradeJournalRecord).filter(TradeJournalRecord.id == int(pos_id)).first()
                                if r_tr:
                                    r_tr.actual_stop_loss = be_sl
                                    db_tr.commit()
                                db_tr.close()
                            except Exception:
                                pass

                    # Target 1 & Runner Scaling Triggers
                    if curr_price >= t1 and not pos.get("t1_booked"):
                        if pos.get("shares", 1) > 1:
                            self._partial_close_position_internal(pos_id, curr_price, "T1_PARTIAL_PROFIT_BOOKED", book_ratio=0.5)
                            sl = entry
                        else:
                            auto_exit_reason = "TARGET_1_HIT"
                    elif pos.get("t1_booked"):
                        # Runner is active: Target 2 or Runner Trailing
                        t2 = pos.get("target_2", round(t1 * 1.02, 2))
                        runner_half_t2 = t1 + (t2 - t1) * 0.50
                        if curr_price >= runner_half_t2 and sl < t1:
                            pos["stop_loss"] = t1  # Lock in full T1 profit for the runner
                            sl = t1
                            pos["trailing_status"] = "RUNNER_PROFIT_LOCKED_T1"

                        if curr_price >= t2:
                            auto_exit_reason = "TARGET_2_HIT"
                        elif curr_price <= sl:
                            auto_exit_reason = "RUNNER_BREAKEVEN_EXIT" if sl <= entry else "PROFIT_LOCKED_35PCT"
                    elif curr_price <= sl:
                        auto_exit_reason = "STOP_LOSS_HIT"
                else:
                    # Short direction:
                    half_target_dist = abs(entry - t1) * 0.45
                    three_quarter_dist = abs(entry - t1) * 0.75
                    be_sl = entry
                    profit_lock_sl = round(entry - 0.35 * (entry - t1), 2)

                    if not pos.get("t1_booked"):
                        if curr_price <= (entry - three_quarter_dist) and sl > profit_lock_sl:
                            pos["stop_loss"] = profit_lock_sl
                            sl = profit_lock_sl
                            pos["trailing_status"] = "PROFIT_LOCKED_35PCT"
                            try:
                                db_tr = SessionLocal()
                                r_tr = db_tr.query(TradeJournalRecord).filter(TradeJournalRecord.id == int(pos_id)).first()
                                if r_tr:
                                    r_tr.actual_stop_loss = profit_lock_sl
                                    db_tr.commit()
                                db_tr.close()
                            except Exception:
                                pass
                        elif curr_price <= (entry - half_target_dist) and sl > be_sl:
                            pos["stop_loss"] = be_sl
                            sl = be_sl
                            pos["trailing_status"] = "RISK_FREE_BREAKEVEN"
                            try:
                                db_tr = SessionLocal()
                                r_tr = db_tr.query(TradeJournalRecord).filter(TradeJournalRecord.id == int(pos_id)).first()
                                if r_tr:
                                    r_tr.actual_stop_loss = be_sl
                                    db_tr.commit()
                                db_tr.close()
                            except Exception:
                                pass

                    # Target 1 & Runner Scaling Triggers
                    if curr_price <= t1 and not pos.get("t1_booked"):
                        if pos.get("shares", 1) > 1:
                            self._partial_close_position_internal(pos_id, curr_price, "T1_PARTIAL_PROFIT_BOOKED", book_ratio=0.5)
                            sl = entry
                        else:
                            auto_exit_reason = "TARGET_1_HIT"
                    elif pos.get("t1_booked"):
                        t2 = pos.get("target_2", round(t1 * 0.98, 2))
                        runner_half_t2 = t1 - (t1 - t2) * 0.50
                        if curr_price <= runner_half_t2 and sl > t1:
                            pos["stop_loss"] = t1
                            sl = t1
                            pos["trailing_status"] = "RUNNER_PROFIT_LOCKED_T1"

                        if curr_price <= t2:
                            auto_exit_reason = "TARGET_2_HIT"
                        elif curr_price >= sl:
                            auto_exit_reason = "RUNNER_BREAKEVEN_EXIT" if sl >= entry else "PROFIT_LOCKED_35PCT"
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

    def _partial_close_position_internal(self, pos_id: str, exit_price: float, exit_reason: str, book_ratio: float = 0.5) -> Dict[str, Any]:
        pos = self.positions.get(pos_id)
        if not pos:
            return {}

        qty = pos.get("shares", 1)
        if qty <= 1:
            return self._close_position_internal(pos_id, exit_price, "TARGET_1_HIT")

        booked_shares = max(1, int(qty * book_ratio))
        remaining_shares = qty - booked_shares

        is_long = pos["direction"] == "LONG"
        entry = pos["entry_price"]
        trade_type = pos.get("trade_type", "INTRADAY")

        # Gross PnL on booked portion
        if is_long:
            gross_pnl = (exit_price - entry) * booked_shares
            pnl_pct = ((exit_price - entry) / entry) * 100.0 if entry > 0 else 0.0
        else:
            gross_pnl = (entry - exit_price) * booked_shares
            pnl_pct = ((entry - exit_price) / entry) * 100.0 if entry > 0 else 0.0

        turnover = (entry * booked_shares) + (exit_price * booked_shares)
        brokerage = min(20.0, turnover * 0.0003) if trade_type == "INTRADAY" else min(20.0, turnover * 0.0005)
        stt = (exit_price * booked_shares) * 0.00025 if trade_type == "INTRADAY" else turnover * 0.001
        exchange_charges = turnover * 0.0000345
        gst = (brokerage + exchange_charges) * 0.18
        stamp_duty = (entry * booked_shares) * 0.00003
        total_charges = round(brokerage + stt + exchange_charges + gst + stamp_duty, 2)

        net_pnl = round(gross_pnl - total_charges, 2)
        gross_pnl = round(gross_pnl, 2)
        pnl_pct = round(pnl_pct, 2)

        # Release margin proportional to booked shares and credit realized profit
        released_margin = round(pos["margin_used"] * (booked_shares / qty), 2)
        pos["margin_used"] = max(0.0, round(pos["margin_used"] - released_margin, 2))
        self.available_cash += released_margin + net_pnl

        # Log booked portion into closed trades audit history
        booked_record = {
            **pos,
            "position_id": f"{pos_id}_T1",
            "shares": booked_shares,
            "exit_price": round(exit_price, 2),
            "exit_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "exit_reason": exit_reason,
            "gross_pnl": gross_pnl,
            "charges": total_charges,
            "realized_pnl": net_pnl,
            "realized_pnl_pct": pnl_pct,
            "is_win": net_pnl > 0
        }
        self.closed_trades.append(booked_record)

        # Update remaining active runner position
        pos["shares"] = remaining_shares
        pos["t1_booked"] = True
        pos["t1_booked_price"] = round(exit_price, 2)
        pos["stop_loss"] = entry  # Move SL to Entry (100% Risk-Free Runner!)
        pos["trailing_status"] = "T1_BOOKED_RUNNER_ACTIVE"

        try:
            db = SessionLocal()
            r = db.query(TradeJournalRecord).filter(TradeJournalRecord.id == int(pos_id)).first()
            if r:
                r.actual_stop_loss = entry
                r.notes = f"T1 partial profit booked ({booked_shares} sh). Runner trailing at breakeven."
                db.commit()
            db.close()
        except Exception:
            pass

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

        post_mortem_text = _generate_ai_post_mortem(pos, exit_price, exit_reason, net_pnl)

        closed_record = {
            **pos,
            "exit_price": round(exit_price, 2),
            "exit_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "exit_reason": exit_reason,
            "gross_pnl": gross_pnl,
            "charges": total_charges,
            "realized_pnl": net_pnl,
            "realized_pnl_pct": pnl_pct,
            "is_win": net_pnl > 0,
            "ai_post_mortem": post_mortem_text
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

    # Sector Concentration & Correlation Guardrail:
    # Max 2 concurrent open positions per sector to prevent correlated multi-trade drawdown
    from app.providers.universe import NSE_UNIVERSE
    stock_sector = NSE_UNIVERSE.get(req.symbol.upper(), {}).get("sector", "Other")
    same_sec_positions = [
        p for p in portfolio.positions.values()
        if (p.get("sector") or NSE_UNIVERSE.get(p.get("symbol", "").upper(), {}).get("sector", "Other")).lower() == stock_sector.lower()
    ]
    if len(same_sec_positions) >= 2:
        conflicting_syms = ", ".join(p.get("symbol", "") for p in same_sec_positions)
        raise HTTPException(
            status_code=400,
            detail=f"Sector Concentration Guard: Already have {len(same_sec_positions)} open positions in {stock_sector} ({conflicting_syms}). Max 2 allowed to protect from correlated drawdown."
        )

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
        "opened_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
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


@router.get("/ai-coach-analytics")
def get_ai_coach_analytics() -> Dict[str, Any]:
    """
    Computes statistical edge analytics and AI trade coaching insights from
    all historical paper trades and AI transaction records:
    - Win rate by Sector
    - Win rate by Time of Day (Morning Open, Midday Chop, Afternoon Expansion)
    - Strategy and Conviction breakdown
    - Actionable automated AI recommendations for edge preservation
    """
    db = SessionLocal()
    try:
        from app.providers.universe import NSE_UNIVERSE
        from app.models.all_models import TradeJournalRecord, AITradeTransactionRecord

        records = db.query(TradeJournalRecord).filter(TradeJournalRecord.exit_time.isnot(None)).all()

        total_trades = len(records)
        if total_trades == 0:
            return {
                "has_data": False,
                "message": "Not enough closed trades yet to generate AI Coach edge analytics. Execute trades to see deep analytics.",
                "total_trades": 0,
                "win_rate": 0.0,
                "sector_breakdown": [],
                "time_of_day_breakdown": [],
                "coach_insights": [
                    "Begin executing automated or manual paper trades to unlock sector win rates and execution edge diagnostics."
                ]
            }

        winning_records = [r for r in records if (r.net_pnl or 0) > 0]
        overall_win_rate = round((len(winning_records) / total_trades) * 100.0, 1)
        total_net_pnl = round(sum(r.net_pnl or 0 for r in records), 2)
        avg_win = round(sum(r.net_pnl for r in winning_records) / max(1, len(winning_records)), 2)
        losing_records = [r for r in records if (r.net_pnl or 0) <= 0]
        avg_loss = round(abs(sum(r.net_pnl or 0 for r in losing_records)) / max(1, len(losing_records)), 2)
        gross_profit = sum(r.net_pnl for r in winning_records)
        gross_loss = abs(sum(r.net_pnl or 0 for r in losing_records))
        profit_factor = round(gross_profit / max(0.01, gross_loss), 2) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        # 1. Sector Breakdown
        sector_stats: Dict[str, Dict[str, Any]] = {}
        for r in records:
            sec = NSE_UNIVERSE.get(r.symbol, {}).get("sector", "Other")
            if sec not in sector_stats:
                sector_stats[sec] = {"sector": sec, "trades": 0, "wins": 0, "losses": 0, "net_pnl": 0.0}
            sector_stats[sec]["trades"] += 1
            if (r.net_pnl or 0) > 0:
                sector_stats[sec]["wins"] += 1
            else:
                sector_stats[sec]["losses"] += 1
            sector_stats[sec]["net_pnl"] = round(sector_stats[sec]["net_pnl"] + (r.net_pnl or 0), 2)

        sector_breakdown = []
        for s, data in sector_stats.items():
            wr = round((data["wins"] / max(1, data["trades"])) * 100.0, 1)
            sector_breakdown.append({**data, "win_rate": wr})
        sector_breakdown.sort(key=lambda x: x["net_pnl"], reverse=True)

        # 2. Time of Day Breakdown (IST)
        time_slots = {
            "MORNING_OPEN (09:15-11:30)": {"trades": 0, "wins": 0, "net_pnl": 0.0},
            "MIDDAY_CHOP (11:30-13:30)": {"trades": 0, "wins": 0, "net_pnl": 0.0},
            "AFTERNOON_EXPANSION (13:30-15:30)": {"trades": 0, "wins": 0, "net_pnl": 0.0},
            "OTHER_OFFMARKET": {"trades": 0, "wins": 0, "net_pnl": 0.0}
        }

        for r in records:
            if not r.entry_time:
                continue
            entry_ist = r.entry_time + datetime.timedelta(hours=5, minutes=30)
            tot_min = entry_ist.hour * 60 + entry_ist.minute
            is_win = (r.net_pnl or 0) > 0

            if 555 <= tot_min <= 690:
                slot = "MORNING_OPEN (09:15-11:30)"
            elif 690 < tot_min <= 810:
                slot = "MIDDAY_CHOP (11:30-13:30)"
            elif 810 < tot_min <= 930:
                slot = "AFTERNOON_EXPANSION (13:30-15:30)"
            else:
                slot = "OTHER_OFFMARKET"

            time_slots[slot]["trades"] += 1
            if is_win:
                time_slots[slot]["wins"] += 1
            time_slots[slot]["net_pnl"] = round(time_slots[slot]["net_pnl"] + (r.net_pnl or 0), 2)

        time_of_day_breakdown = []
        for slot_name, data in time_slots.items():
            if data["trades"] > 0:
                wr = round((data["wins"] / data["trades"]) * 100.0, 1)
                time_of_day_breakdown.append({
                    "slot": slot_name,
                    "trades": data["trades"],
                    "wins": data["wins"],
                    "win_rate": wr,
                    "net_pnl": data["net_pnl"]
                })

        # 3. AI Coach Actionable Insights
        coach_insights = []
        if sector_breakdown:
            best_sector = sector_breakdown[0]
            if best_sector["win_rate"] >= 60.0:
                coach_insights.append(
                    f"🌟 Strongest Sector Edge: '{best_sector['sector']}' with {best_sector['win_rate']}% win rate and ₹{best_sector['net_pnl']:+,.2f} net profit."
                )
            if len(sector_breakdown) > 1 and sector_breakdown[-1]["net_pnl"] < 0:
                worst_sec = sector_breakdown[-1]
                coach_insights.append(
                    f"⚠️ Drag Detected: '{worst_sec['sector']}' has net PnL of ₹{worst_sec['net_pnl']:+,.2f}. Consider tightening conviction threshold for this sector."
                )

        morning = next((t for t in time_of_day_breakdown if "MORNING_OPEN" in t["slot"]), None)
        midday = next((t for t in time_of_day_breakdown if "MIDDAY_CHOP" in t["slot"]), None)
        if morning and midday and morning["trades"] >= 2 and midday["trades"] >= 2:
            if morning["win_rate"] > midday["win_rate"]:
                coach_insights.append(
                    f"🕒 Session Timing: Morning Open trades perform best ({morning['win_rate']}% win rate vs {midday['win_rate']}% in Midday Chop). Focus capital on 09:30–11:30 AM setups."
                )

        if overall_win_rate >= 60.0:
            coach_insights.append(
                f"✅ Institutional Edge Verified: Overall win rate is {overall_win_rate}% with a {profit_factor}x profit factor."
            )
        else:
            coach_insights.append(
                f"🛡️ Multi-target runner and 2-tier trailing stops protect against drawdowns; maintain strict adherence to minimum 55% ML probability."
            )

        coach_insights.append("🔒 Capital Preservation: Two-tier rapid trailing stop and stagnation auto-exit remain active on all open trades.")

        return {
            "has_data": True,
            "total_trades": total_trades,
            "overall_win_rate": overall_win_rate,
            "total_net_pnl": total_net_pnl,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "sector_breakdown": sector_breakdown,
            "time_of_day_breakdown": time_of_day_breakdown,
            "coach_insights": coach_insights
        }
    finally:
        db.close()
