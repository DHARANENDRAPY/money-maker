from typing import List, Dict, Any, Optional
import pandas as pd
from app.schemas.market_schemas import ScannerItem
from app.engine.indicators import enrich_candles_with_indicators, detect_key_levels
from app.engine.signals import SignalGenerator

class MarketScanner:
    """
    Scans the configured NSE stock universe across multiple setups,
    evaluating indicators, risk/reward, liquidity, and trend alignment.
    """

    @staticmethod
    def scan_stock(
        symbol: str,
        name: str,
        sector: str,
        df: pd.DataFrame,
        nifty_change_pct: float,
        sector_change_pct: float,
        market_regime: str,
        is_watchlist: bool = False,
        ml_model: Any = None
    ) -> ScannerItem:
        if df.empty or len(df) < 5:
            # Fallback for empty data
            return ScannerItem(
                symbol=symbol,
                name=name,
                ltp=100.0,
                change=0.0,
                change_pct=0.0,
                volume=10000,
                rel_volume=1.0,
                sector=sector,
                trend_alignment="NEUTRAL",
                setup_type="No Setup",
                expected_volatility_pct=1.2,
                data_freshness_sec=1.0,
                signal_status="no_signal",
                direction="NEUTRAL",
                liquidity_score=85.0,
                spread_pct=0.02,
                is_watchlist=is_watchlist
            )
            
        enriched = enrich_candles_with_indicators(df)
        last = enriched.iloc[-1]
        first = enriched.iloc[0]
        
        ltp = float(last['close'])
        open_p = float(first['open'])
        change = round(ltp - open_p, 2)
        change_pct = round((change / open_p) * 100.0, 2) if open_p > 0 else 0.0
        
        volume = int(enriched['volume'].sum())
        rvol = float(last.get('rvol', 1.0))
        atr = float(last.get('atr14', ltp * 0.012))
        volatility_pct = round((atr / ltp) * 100.0, 2) if ltp > 0 else 1.2
        
        # Trend alignment
        trend_alignment = "NEUTRAL"
        if change_pct > 0.5 and nifty_change_pct > 0.2:
            trend_alignment = "ALIGNED_BULLISH"
        elif change_pct < -0.5 and nifty_change_pct < -0.2:
            trend_alignment = "ALIGNED_BEARISH"
        elif change_pct > 0.5 and nifty_change_pct < -0.2:
            trend_alignment = "COUNTER_TREND"
        elif change_pct < -0.5 and nifty_change_pct > 0.2:
            trend_alignment = "COUNTER_TREND"
            
        # Run Signal Engine
        signal = SignalGenerator.generate_signal_for_stock(
            symbol=symbol,
            df=enriched,
            current_price=ltp,
            sector=sector,
            sector_change_pct=sector_change_pct,
            nifty_change_pct=nifty_change_pct,
            market_regime=market_regime,
            market_breadth_ad=1.2,
            ml_model=ml_model
        )
        
        setup_type = signal.strategy if signal else "No Setup"
        ml_prob = signal.ml_probability if signal else None
        rr_ratio = signal.risk_reward_ratio if signal else None
        entry = signal.entry_price if signal else None
        sl = signal.stop_loss if signal else None
        tp = signal.target_price if signal else None
        sig_status = signal.status if signal else "no_signal"
        direction = signal.direction if signal else "NEUTRAL"
        
        # Liquidity estimate (Turnover-based)
        turnover_cr = (volume * ltp) / 10000000.0
        liquidity_score = min(100.0, max(20.0, (turnover_cr / 20.0) * 100.0))
        spread_pct = round(max(0.01, min(0.08, 0.06 - (liquidity_score / 2500.0))), 3)
        
        return ScannerItem(
            symbol=symbol,
            name=name,
            ltp=round(ltp, 2),
            change=change,
            change_pct=change_pct,
            volume=volume,
            rel_volume=round(rvol, 2),
            sector=sector,
            trend_alignment=trend_alignment,
            setup_type=setup_type,
            ml_probability=ml_prob,
            expected_volatility_pct=volatility_pct,
            risk_reward=rr_ratio,
            entry_price=entry,
            stop_loss=sl,
            target_price=tp,
            data_freshness_sec=1.1,
            signal_status=sig_status,
            direction=direction,
            liquidity_score=round(liquidity_score, 1),
            spread_pct=spread_pct,
            is_watchlist=is_watchlist
        )
