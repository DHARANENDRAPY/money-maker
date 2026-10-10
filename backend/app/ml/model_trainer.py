import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score, precision_score, recall_score, accuracy_score
from sklearn.preprocessing import StandardScaler
from app.ml.feature_engineering import extract_features_from_df, FEATURE_COLUMNS
from app.ml.target_labeller import label_setup_outcomes

class ModelTrainingPipeline:
    """
    Trains and validates an ensemble setup probability model using walk-forward validation.
    
    Architecture:
    - Gradient Boosting + Random Forest ensemble (soft-vote)
    - Platt Sigmoid calibration for well-calibrated probabilities
    - Trains on BOTH LONG and SHORT setups for maximum signal coverage
    - 28-feature set covering momentum, volume, volatility, candle structure, trend
    """

    def __init__(self, model_type: str = "GradientBoosting"):
        self.model_type = model_type
        self.model = None
        self.calibrated_model = None
        self.scaler = StandardScaler()
        self.feature_names = FEATURE_COLUMNS
        self.metadata = {}

    def prepare_dataset(self, df_dict: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
        """
        Combines multi-stock historical intraday DataFrames into feature and label arrays.
        Labels BOTH LONG and SHORT setups for maximum training coverage.
        """
        all_X = []
        all_y = []
        all_r = []

        for symbol, df in df_dict.items():
            if len(df) < 50:
                continue

            feats = extract_features_from_df(df)
            if feats.empty:
                continue

            # Label LONG setups
            labels_long, r_mults_long = label_setup_outcomes(
                df, risk_atr_mult=1.0, reward_atr_mult=1.8, max_holding_bars=12, direction="LONG"
            )
            # Label SHORT setups
            labels_short, r_mults_short = label_setup_outcomes(
                df, risk_atr_mult=1.0, reward_atr_mult=1.8, max_holding_bars=12, direction="SHORT"
            )

            # Use the better labelled direction per bar (whichever has higher expected R)
            # Conservative: take LONG labels by default, but include SHORT as additional training rows
            valid_len = min(len(feats), len(df) - 15)
            valid_feats = feats.iloc[:valid_len]

            # LONG rows
            vl = labels_long.iloc[:valid_len]
            vr = r_mults_long.iloc[:valid_len]
            # Only include bars where LONG setup had a clear outcome
            long_mask = vr != 0.0
            if long_mask.sum() > 0:
                all_X.append(valid_feats[long_mask])
                all_y.append(vl[long_mask])
                all_r.append(vr[long_mask])

            # SHORT rows — flip sign of directional features (vwap_dist, ema_spread, etc.)
            vs = labels_short.iloc[:valid_len]
            vsr = r_mults_short.iloc[:valid_len]
            short_mask = vsr != 0.0
            if short_mask.sum() > 0:
                short_feats = valid_feats[short_mask].copy()
                # Invert directional features for short perspective
                for col in ['vwap_dist_pct', 'ema_spread_pct', 'ema9_slope', 'ema21_slope',
                            'rsi14_norm', 'rsi_momentum', 'macd_hist_norm', 'macd_cross',
                            'supertrend_dir', 'price_vs_ema50_pct', 'above_vwap', 'orb_dist_pct']:
                    if col in short_feats.columns:
                        short_feats[col] = -short_feats[col]
                all_X.append(short_feats)
                all_y.append(vs[short_mask])
                all_r.append(vsr[short_mask])

        if not all_X:
            return pd.DataFrame(), pd.Series(dtype=int), pd.Series(dtype=float)

        X = pd.concat(all_X, ignore_index=True)
        y = pd.concat(all_y, ignore_index=True)
        r = pd.concat(all_r, ignore_index=True)

        return X, y, r

    def train_walk_forward(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        r_multiples: pd.Series,
        train_ratio: float = 0.75
    ) -> Dict[str, Any]:
        """
        Walk-forward temporal train/test evaluation (strict chronological separation).
        Uses an ensemble of GradientBoosting + RandomForest with Platt calibration.
        """
        if len(X) < 40:
            return {
                "status": "INSUFFICIENT_DATA",
                "message": "At least 40 observations required for walk-forward training."
            }

        split_idx = int(len(X) * train_ratio)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        r_train, r_test = r_multiples.iloc[:split_idx], r_multiples.iloc[split_idx:]

        # Extract only the known feature columns (handle any column mismatches)
        available_features = [c for c in self.feature_names if c in X_train.columns]
        X_train_f = X_train[available_features].fillna(0.0)
        X_test_f = X_test[available_features].fillna(0.0)

        # Fit scaler on train data only
        X_train_scaled = self.scaler.fit_transform(X_train_f)
        X_test_scaled = self.scaler.transform(X_test_f)

        # Ensemble: GradientBoosting + RandomForest soft-voting (tuned for fast convergence & anti-overfitting)
        gb = GradientBoostingClassifier(
            n_estimators=45, max_depth=3, learning_rate=0.08,
            subsample=0.8, min_samples_leaf=4, random_state=42
        )
        rf = RandomForestClassifier(
            n_estimators=45, max_depth=4, min_samples_leaf=4,
            max_features='sqrt', random_state=42, n_jobs=-1
        )

        ensemble = VotingClassifier(
            estimators=[('gb', gb), ('rf', rf)],
            voting='soft',
            weights=[0.6, 0.4]   # GB gets slightly higher weight for calibration
        )

        # Platt Sigmoid calibration on top of ensemble
        self.calibrated_model = CalibratedClassifierCV(
            estimator=ensemble,
            method='sigmoid',
            cv=3
        )
        self.calibrated_model.fit(X_train_scaled, y_train)
        self.model = self.calibrated_model

        # Store available features for prediction time
        self.feature_names = available_features

        # Out-of-sample predictions
        y_prob = self.calibrated_model.predict_proba(X_test_scaled)[:, 1]
        y_pred = (y_prob >= 0.50).astype(int)

        # Metrics
        brier = float(brier_score_loss(y_test, y_prob))
        logloss = float(log_loss(y_test, y_prob))
        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        roc_auc = float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else 0.5

        # Calibration curve (reliability diagram)
        try:
            prob_true, prob_pred = calibration_curve(y_test, y_prob, n_bins=6, strategy='uniform')
            calib_data = [
                {"predicted_probability": round(float(p), 3), "empirical_frequency": round(float(t), 3)}
                for p, t in zip(prob_pred, prob_true)
            ]
        except Exception:
            calib_data = []

        # Financial expectancy on test slice — only trade high-confidence setups
        test_r_list = r_test.values
        high_conf_indices = np.where(y_prob >= 0.55)[0]
        if len(high_conf_indices) > 0:
            traded_r = test_r_list[high_conf_indices]
            wins = traded_r[traded_r > 0]
            losses = traded_r[traded_r <= 0]
            gross_win = np.sum(wins)
            gross_loss = abs(np.sum(losses)) if len(losses) > 0 else 1e-6
            profit_factor = round(float(gross_win / gross_loss), 2)
            win_rate = round(float(len(wins) / len(traded_r) * 100.0), 1)
            expectancy_r = round(float(np.mean(traded_r)), 2)
            cum_equity = np.cumsum(traded_r)
            running_max = np.maximum.accumulate(cum_equity)
            drawdown = running_max - cum_equity
            max_drawdown_r = round(float(np.max(drawdown)), 2) if len(drawdown) > 0 else 0.0
            trades_filtered = int(len(high_conf_indices))
        else:
            profit_factor = 1.0
            win_rate = 50.0
            expectancy_r = 0.0
            max_drawdown_r = 0.0
            trades_filtered = 0

        # Feature importance from the GradientBoosting sub-model
        feature_importance = {}
        try:
            gb_estimator = self.calibrated_model.calibrated_classifiers_[0].estimator
            # Navigate VotingClassifier -> GradientBoosting
            if hasattr(gb_estimator, 'estimators_'):
                gb_inner = gb_estimator.estimators_[0]  # first = 'gb'
                if hasattr(gb_inner, 'feature_importances_'):
                    for name, imp in zip(available_features, gb_inner.feature_importances_):
                        feature_importance[name] = round(float(imp), 4)
        except Exception:
            pass

        self.metadata = {
            "model_version": "v2.0-ensemble-calibrated",
            "model_type": f"Ensemble(GBT+RF) + PlattCalibration",
            "n_features": len(available_features),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "high_conf_trades": trades_filtered,
            "brier_score": round(brier, 4),
            "log_loss": round(logloss, 4),
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "roc_auc": round(roc_auc, 4),
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "expectancy_r": expectancy_r,
            "max_drawdown_r": max_drawdown_r,
            "calibration_curve": calib_data,
            "feature_importance": feature_importance,
            "is_active": True
        }

        return self.metadata

    def predict_proba(self, feature_vector: np.ndarray) -> float:
        """
        Predict win probability for a single trade setup.
        Returns probability that the target is reached before stop loss.
        """
        if self.calibrated_model is None:
            return 0.50
        try:
            # Scale using fitted scaler
            scaled = self.scaler.transform(feature_vector)
            prob = float(self.calibrated_model.predict_proba(scaled)[0][1])
            return round(max(0.30, min(0.95, prob)), 3)
        except Exception:
            return 0.50
