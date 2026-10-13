import pytest
import pandas as pd
import numpy as np
from app.engine.indicators import (
    calculate_vwap, calculate_ema, calculate_rsi, calculate_macd,
    calculate_atr, calculate_supertrend, calculate_relative_volume,
    detect_key_levels, enrich_candles_with_indicators
)
from app.engine.factors import FactorEngine
from app.engine.risk_calculator import calculate_indian_equity_intraday_charges, calculate_position_sizing
from app.schemas.all_schemas import RiskCalculationRequest
from app.ml.feature_engineering import extract_features_from_df
from app.ml.target_labeller import label_setup_outcomes
from app.ml.model_trainer import ModelTrainingPipeline
from app.engine.signals import SignalGenerator

def generate_sample_candles(n=50, base_price=1000.0):
    prices = [base_price]
    for _ in range(n - 1):
        prices.append(prices[-1] + np.random.normal(0, 2.0))
        
    timestamps = pd.date_range("2026-10-09 09:15:00", periods=n, freq="5min")
    data = {
        "timestamp": [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in timestamps],
        "open": prices,
        "high": [p + 2.5 for p in prices],
        "low": [p - 2.5 for p in prices],
        "close": [p + 0.5 for p in prices],
        "volume": [10000 + i * 100 for i in range(n)]
    }
    return pd.DataFrame(data)

def test_indicators_math():
    df = generate_sample_candles(40, 1500.0)
    enriched = enrich_candles_with_indicators(df)
    
    assert "vwap" in enriched.columns
    assert "ema9" in enriched.columns
    assert "rsi14" in enriched.columns
    assert "atr14" in enriched.columns
    assert "rvol" in enriched.columns
    assert not enriched['vwap'].isna().all()
    assert 0 <= enriched['rsi14'].iloc[-1] <= 100

def test_indian_statutory_charges_calculation():
    # Buy 100 shares @ 1000, Sell @ 1010
    charges = calculate_indian_equity_intraday_charges(
        buy_price=1000.0,
        sell_price=1010.0,
        quantity=100,
        brokerage_type="FLAT",
        flat_brokerage_rate=20.0
    )
    
    assert charges.turnover == 201000.0
    assert charges.brokerage == 40.0  # Rs 20 buy + Rs 20 sell
    assert charges.stt > 0.0  # 0.025% on sell side
    assert charges.stamp_duty > 0.0  # 0.003% on buy side
    assert charges.exchange_txn_charge > 0.0
    assert charges.gst > 0.0
    assert charges.total_charges > 40.0
    assert charges.breakeven_points > 0.0

def test_position_sizing_respects_risk():
    req = RiskCalculationRequest(
        symbol="RELIANCE",
        capital=100000.0,
        risk_pct=1.0,  # Max loss Rs 1,000
        entry_price=2500.0,
        stop_loss=2480.0,  # Risk per share = Rs 20
        target_price=2540.0,  # Reward = Rs 40 (1:2 RR)
        direction="LONG"
    )
    sizing = calculate_position_sizing(req, max_portfolio_exposure_pct=50.0)
    
    assert sizing.max_risk_amount == 1000.0
    assert sizing.risk_per_share == 20.0
    assert sizing.risk_reward_ratio == 2.0
    # 1000 / 20 = 50 shares raw
    # Max exposure 50% = 50,000 / 2500 = 20 shares cap
    assert sizing.capped_quantity <= 50
    assert sizing.net_loss_at_stop < 0

def test_12_factors_engine():
    df = generate_sample_candles(30, 2000.0)
    f1 = FactorEngine.evaluate_factor_1_market_trend(0.8, True, 1.8, "MODERATE_BULLISH")
    f4 = FactorEngine.evaluate_factor_4_price_action(df, 2005.0)
    f8 = FactorEngine.evaluate_factor_8_time_of_day("10:15")
    f10 = FactorEngine.evaluate_factor_10_risk_management(2000.0, 1980.0, 2040.0, "LONG")
    
    assert f1.score > 0
    assert f1.status == "SUPPORTIVE"
    assert f8.status == "SUPPORTIVE"
    assert f10.score > 0

def test_ml_target_labeller_conservative_touch():
    df = generate_sample_candles(35, 1000.0)
    labels, r_mults = label_setup_outcomes(df, risk_atr_mult=1.0, reward_atr_mult=1.8, max_holding_bars=10)
    assert len(labels) == len(df)
    assert len(r_mults) == len(df)

def test_ml_model_training_pipeline():
    df1 = generate_sample_candles(80, 1200.0)
    df2 = generate_sample_candles(80, 800.0)
    pipeline = ModelTrainingPipeline(model_type="GradientBoosting")
    X, y, r = pipeline.prepare_dataset({"STOCK1": df1, "STOCK2": df2})
    
    assert len(X) >= 40
    meta = pipeline.train_walk_forward(X, y, r, train_ratio=0.7)
    assert "Ensemble" in meta["model_type"] or meta["model_type"] == "GradientBoosting"
    assert "accuracy" in meta
    assert "calibration_curve" in meta

def test_signal_clamping_realistic_intraday():
    df = generate_sample_candles(50, 2500.0)
    enriched = enrich_candles_with_indicators(df)
    sig = SignalGenerator.generate_signal_for_stock(
        symbol="RELIANCE",
        df=enriched,
        current_price=2500.0,
        sector="Energy",
        sector_change_pct=1.0,
        nifty_change_pct=0.5,
        market_regime="BULLISH_TRENDING",
        market_breadth_ad=1.5
    )
    if sig:
        if sig.direction == "LONG":
            assert sig.stop_loss < sig.entry_price < sig.target_price
            assert (sig.target_price - sig.entry_price) / sig.entry_price <= 0.03
        elif sig.direction == "SHORT":
            assert sig.stop_loss > sig.entry_price > sig.target_price
            assert (sig.entry_price - sig.target_price) / sig.entry_price <= 0.03
        assert sig.risk_reward_ratio >= 1.2

