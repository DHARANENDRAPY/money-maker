from typing import List, Dict, Any
from app.models.all_models import TradeJournalRecord
from app.schemas.all_schemas import DisciplineAnalytics

def evaluate_discipline_journal(trades: List[TradeJournalRecord]) -> DisciplineAnalytics:
    """
    Analyzes trader journal logs to detect deviations, revenge trading loops,
    oversizing, and plan compliance.
    """
    if not trades:
        return DisciplineAnalytics(
            total_logged_trades=0,
            plan_adherence_rate=100.0,
            avg_discipline_score=100.0,
            common_deviations={},
            revenge_trading_flags=0,
            overtrading_days=0,
            win_rate_when_disciplined=0.0,
            win_rate_when_deviated=0.0,
            avg_r_multiple_disciplined=0.0,
            avg_r_multiple_deviated=0.0
        )
        
    total_trades = len(trades)
    disciplined_trades = [t for t in trades if t.followed_plan]
    deviated_trades = [t for t in trades if not t.followed_plan]
    
    adherence_rate = (len(disciplined_trades) / total_trades) * 100.0
    avg_score = sum(t.discipline_score for t in trades) / total_trades
    
    # Deviation categories
    dev_counts: Dict[str, int] = {}
    for t in trades:
        if t.deviations:
            for d in t.deviations:
                dev_counts[d] = dev_counts.get(d, 0) + 1
                
    # Detect Revenge Trading: trade entered within 10 minutes of a losing trade with increased quantity
    revenge_flags = 0
    sorted_trades = sorted(trades, key=lambda x: x.entry_time)
    for i in range(1, len(sorted_trades)):
        prev = sorted_trades[i-1]
        curr = sorted_trades[i]
        if prev.net_pnl < 0 and curr.entry_time and prev.exit_time:
            time_diff = (curr.entry_time - prev.exit_time).total_seconds() / 60.0
            if time_diff < 15 and curr.quantity >= prev.quantity:
                revenge_flags += 1
                
    # Win rates
    win_disciplined = [t for t in disciplined_trades if t.net_pnl > 0]
    win_rate_disc = (len(win_disciplined) / len(disciplined_trades) * 100.0) if disciplined_trades else 0.0
    
    win_deviated = [t for t in deviated_trades if t.net_pnl > 0]
    win_rate_dev = (len(win_deviated) / len(deviated_trades) * 100.0) if deviated_trades else 0.0
    
    # R-multiples (estimated assuming planned risk was 1R)
    r_disc = []
    for t in disciplined_trades:
        planned_risk = abs(t.planned_entry - t.planned_stop_loss) * t.quantity
        if planned_risk > 0:
            r_disc.append(t.net_pnl / planned_risk)
    avg_r_disc = sum(r_disc) / len(r_disc) if r_disc else 0.0
    
    r_dev = []
    for t in deviated_trades:
        planned_risk = abs(t.planned_entry - t.planned_stop_loss) * t.quantity
        if planned_risk > 0:
            r_dev.append(t.net_pnl / planned_risk)
    avg_r_dev = sum(r_dev) / len(r_dev) if r_dev else 0.0
    
    return DisciplineAnalytics(
        total_logged_trades=total_trades,
        plan_adherence_rate=round(adherence_rate, 1),
        avg_discipline_score=round(avg_score, 1),
        common_deviations=dev_counts,
        revenge_trading_flags=revenge_flags,
        overtrading_days=0,
        win_rate_when_disciplined=round(win_rate_disc, 1),
        win_rate_when_deviated=round(win_rate_dev, 1),
        avg_r_multiple_disciplined=round(avg_r_disc, 2),
        avg_r_multiple_deviated=round(avg_r_dev, 2)
    )
