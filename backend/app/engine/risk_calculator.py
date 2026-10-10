import math
from typing import Dict, Any, Optional
from app.schemas.all_schemas import (
    RiskCalculationRequest,
    PositionSizingResult,
    StatutoryChargesBreakdown
)

def calculate_indian_equity_intraday_charges(
    buy_price: float,
    sell_price: float,
    quantity: int,
    brokerage_type: str = "FLAT",
    flat_brokerage_rate: float = 20.0,
    percent_brokerage_rate: float = 0.03
) -> StatutoryChargesBreakdown:
    """
    Calculates detailed statutory and broker charges for NSE Equity Intraday trades.
    Includes: Brokerage, STT (0.025% sell), Exchange Txn (0.00297%), GST (18%),
    SEBI Charges (0.0001%), Stamp Duty (0.003% buy).
    """
    buy_value = buy_price * quantity
    sell_value = sell_price * quantity
    turnover = buy_value + sell_value
    
    # 1. Brokerage (Buy + Sell legs)
    if brokerage_type.upper() == "FLAT":
        # Flat 20 per executed order (2 orders for buy and sell)
        brokerage = flat_brokerage_rate * 2.0
        # Cap at 0.03% if percentage would be lower (standard discount broker rule)
        max_pct_brokerage = (turnover * (percent_brokerage_rate / 100.0))
        brokerage = min(brokerage, max_pct_brokerage) if max_pct_brokerage > 0 else brokerage
    else:
        brokerage = turnover * (percent_brokerage_rate / 100.0)
        
    # 2. STT (Securities Transaction Tax) - 0.025% on sell side for equity intraday
    stt = sell_value * 0.00025
    
    # 3. Exchange Transaction Charges (NSE ~0.00297% of turnover)
    exchange_charges = turnover * 0.0000297
    
    # 4. SEBI Turnover Charges (Rs 10 per crore = 0.0001% of turnover)
    sebi_charges = turnover * 0.000001
    
    # 5. Stamp Duty (0.003% on buy side only)
    stamp_duty = buy_value * 0.00003
    
    # 6. GST (18% on Brokerage + Exchange charges + SEBI charges)
    gst = (brokerage + exchange_charges + sebi_charges) * 0.18
    
    total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst
    breakeven_points = total_charges / quantity if quantity > 0 else 0.0
    
    return StatutoryChargesBreakdown(
        turnover=round(turnover, 2),
        brokerage=round(brokerage, 2),
        stt=round(stt, 2),
        exchange_txn_charge=round(exchange_charges, 2),
        gst=round(gst, 2),
        sebi_charges=round(sebi_charges, 2),
        stamp_duty=round(stamp_duty, 2),
        total_charges=round(total_charges, 2),
        breakeven_points=round(breakeven_points, 2)
    )

def calculate_position_sizing(req: RiskCalculationRequest, max_portfolio_exposure_pct: float = 50.0) -> PositionSizingResult:
    """
    Computes exact position size based on user risk tolerance, entry, stop loss, and target.
    """
    entry = req.entry_price
    stop = req.stop_loss
    target = req.target_price
    direction = req.direction.upper()
    
    risk_per_share = abs(entry - stop)
    target_per_share = abs(target - entry)
    
    if risk_per_share <= 0:
        risk_per_share = 0.01  # Prevent div zero
        
    rr_ratio = target_per_share / risk_per_share
    
    # Maximum risk amount in INR
    max_risk_amount = req.capital * (req.risk_pct / 100.0)
    
    # Quantity based on risk
    raw_qty = int(math.floor(max_risk_amount / risk_per_share))
    raw_qty = max(raw_qty, 1) if entry > 0 else 0
    
    # Quantity ceiling based on max intraday capital exposure
    max_capital_allowed = req.capital * (max_portfolio_exposure_pct / 100.0)
    max_qty_capital = int(math.floor(max_capital_allowed / entry)) if entry > 0 else raw_qty
    max_qty_capital = max(max_qty_capital, 1)
    
    capped_quantity = min(raw_qty, max_qty_capital)
    total_capital_required = round(capped_quantity * entry, 2)
    capital_utilization = round((total_capital_required / req.capital) * 100.0, 2)
    
    # Financial projections at target vs stop
    if direction == "LONG":
        charges_target = calculate_indian_equity_intraday_charges(entry, target, capped_quantity, req.brokerage_type, req.flat_brokerage_rate, req.percent_brokerage_rate)
        charges_stop = calculate_indian_equity_intraday_charges(entry, stop, capped_quantity, req.brokerage_type, req.flat_brokerage_rate, req.percent_brokerage_rate)
        
        gross_loss_at_stop = -(risk_per_share * capped_quantity)
        net_loss_at_stop = -(abs(gross_loss_at_stop) + charges_stop.total_charges)
        
        gross_profit_at_target = target_per_share * capped_quantity
        net_profit_at_target = gross_profit_at_target - charges_target.total_charges
    else:  # SHORT
        charges_target = calculate_indian_equity_intraday_charges(target, entry, capped_quantity, req.brokerage_type, req.flat_brokerage_rate, req.percent_brokerage_rate)
        charges_stop = calculate_indian_equity_intraday_charges(stop, entry, capped_quantity, req.brokerage_type, req.flat_brokerage_rate, req.percent_brokerage_rate)
        
        gross_loss_at_stop = -(risk_per_share * capped_quantity)
        net_loss_at_stop = -(abs(gross_loss_at_stop) + charges_stop.total_charges)
        
        gross_profit_at_target = target_per_share * capped_quantity
        net_profit_at_target = gross_profit_at_target - charges_target.total_charges
        
    risk_warning = None
    if capped_quantity < raw_qty:
        risk_warning = f"Position scaled down from {raw_qty} to {capped_quantity} shares to respect the {max_portfolio_exposure_pct}% max intraday portfolio exposure limit."
    elif rr_ratio < 1.5:
        risk_warning = f"Risk/Reward ratio (1:{rr_ratio:.2f}) is below the recommended 1:1.5 threshold."
        
    return PositionSizingResult(
        max_risk_amount=round(max_risk_amount, 2),
        risk_per_share=round(risk_per_share, 2),
        target_per_share=round(target_per_share, 2),
        risk_reward_ratio=round(rr_ratio, 2),
        calculated_quantity=raw_qty,
        capped_quantity=capped_quantity,
        total_capital_required=total_capital_required,
        capital_utilization_pct=capital_utilization,
        gross_loss_at_stop=round(gross_loss_at_stop, 2),
        net_loss_at_stop=round(net_loss_at_stop, 2),
        gross_profit_at_target=round(gross_profit_at_target, 2),
        net_profit_at_target=round(net_profit_at_target, 2),
        charges_breakdown=charges_target,
        risk_warning=risk_warning
    )
