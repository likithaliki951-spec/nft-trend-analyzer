"""Advanced Machine Learning Regressors: Support Vector Regression (SVR) and GRU-based Hybrid Time-Series Forecasting."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor

from nft_analysis import build_time_features


def check_gru_data_sufficiency(
    dates: pd.Series, target: pd.Series, min_sequence_rows: int = 24
) -> tuple[bool, str]:
    """Determine whether the available chronological data has sufficient sequential depth for recurrent neural modeling."""
    valid = dates.notna() & target.notna() & np.isfinite(target)
    valid_count = int(valid.sum())
    if valid_count < min_sequence_rows:
        return (
            False,
            f"Insufficient sequential records: GRU recurrent networks require at least {min_sequence_rows} "
            f"chronologically ordered observations to construct multi-step input windows. Dataset has {valid_count} valid rows.",
        )
    std_val = float(np.std(target.loc[valid].to_numpy(dtype=float)))
    if std_val < 1e-8:
        return (
            False,
            "Target metric has zero variance across timestamps. Recurrent models cannot learn dynamics from constant values.",
        )
    return True, "Dataset meets chronological sequence depth requirements for recurrent modeling."


class NumpyGRUCell:
    """Self-contained NumPy Gated Recurrent Unit (GRU) cell for zero-dependency deployment portability."""

    def __init__(self, input_dim: int, hidden_dim: int, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        # Xavier/Glorot initialization
        scale_in = 1.0 / np.sqrt(max(1, input_dim))
        scale_hid = 1.0 / np.sqrt(max(1, hidden_dim))

        # Update gate weights (z)
        self.W_z = rng.uniform(-scale_in, scale_in, (input_dim, hidden_dim))
        self.U_z = rng.uniform(-scale_hid, scale_hid, (hidden_dim, hidden_dim))
        self.b_z = np.zeros(hidden_dim)

        # Reset gate weights (r)
        self.W_r = rng.uniform(-scale_in, scale_in, (input_dim, hidden_dim))
        self.U_r = rng.uniform(-scale_hid, scale_hid, (hidden_dim, hidden_dim))
        self.b_r = np.zeros(hidden_dim)

        # Candidate state weights (h)
        self.W_h = rng.uniform(-scale_in, scale_in, (input_dim, hidden_dim))
        self.U_h = rng.uniform(-scale_hid, scale_hid, (hidden_dim, hidden_dim))
        self.b_h = np.zeros(hidden_dim)

        self.hidden_dim = hidden_dim

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -15.0, 15.0)))

    def forward_sequence(self, x_seq: np.ndarray) -> np.ndarray:
        """Forward pass across a sequence of shape (seq_len, input_dim). Returns final hidden state h_T."""
        h_t = np.zeros(self.hidden_dim)
        for t in range(len(x_seq)):
            x_t = x_seq[t]
            z_t = self._sigmoid(x_t @ self.W_z + h_t @ self.U_z + self.b_z)
            r_t = self._sigmoid(x_t @ self.W_r + h_t @ self.U_r + self.b_r)
            h_tilde = np.tanh(x_t @ self.W_h + (r_t * h_t) @ self.U_h + self.b_h)
            h_t = (1.0 - z_t) * h_t + z_t * h_tilde
        return h_t


class GRUHybridTimeSeriesRegressor:
    """Hybrid Time-Series Regressor combining GRU sequence memory with tabular lagged features.

    Architecture:
    1. Chronological Sequence Pathway: Encodes past W steps of price/volume into a dense hidden state h_T via GRU.
    2. Tabular Feature Pathway: Takes calendar components and immediate prior observations.
    3. Hybrid Head: Regresses the fused latent representation (h_T + Tabular) to forecast y_t.
    """

    def __init__(self, window_size: int = 4, hidden_dim: int = 8, seed: int = 42) -> None:
        self.window_size = window_size
        self.hidden_dim = hidden_dim
        self.seed = seed
        self.gru_cell: NumpyGRUCell | None = None
        self.scaler_seq: StandardScaler = StandardScaler()
        self.scaler_tab: StandardScaler = StandardScaler()
        self.head: Ridge = Ridge(alpha=1.0)
        self.fitted_ = False

    def _build_sequences(
        self, target_series: np.ndarray, tabular_features: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build sliding window sequences [t-W ... t-1] strictly from past observations."""
        seqs = []
        tabs = []
        targets = []
        w = self.window_size
        n = len(target_series)
        for i in range(w, n):
            # Target window strictly prior to step i
            seqs.append(target_series[i - w : i].reshape(w, 1))
            tabs.append(tabular_features[i])
            targets.append(target_series[i])
        return np.array(seqs), np.array(tabs), np.array(targets)

    def fit(self, y_train: np.ndarray, x_train_tab: np.ndarray) -> GRUHybridTimeSeriesRegressor:
        """Fit the GRU feature extractor and hybrid regression head strictly using training rows."""
        y_train = np.asarray(y_train, dtype=float)
        x_train_tab = np.asarray(x_train_tab, dtype=float)

        if len(y_train) <= self.window_size + 2:
            raise ValueError(f"Training set has too few observations ({len(y_train)}) for window size {self.window_size}.")

        seqs, tabs, targets = self._build_sequences(y_train, x_train_tab)
        num_samples, seq_len, in_dim = seqs.shape

        # Scale sequence inputs based on training data only
        seqs_flat = seqs.reshape(-1, in_dim)
        self.scaler_seq.fit(seqs_flat)
        seqs_scaled = self.scaler_seq.transform(seqs_flat).reshape(num_samples, seq_len, in_dim)

        # Scale tabular features based on training data only
        tabs_scaled = self.scaler_tab.fit_transform(tabs)

        # Initialize GRU cell
        self.gru_cell = NumpyGRUCell(input_dim=in_dim, hidden_dim=self.hidden_dim, seed=self.seed)

        # Forward pass to obtain GRU latent temporal states
        gru_embeddings = np.array([self.gru_cell.forward_sequence(seq) for seq in seqs_scaled])

        # Concatenate GRU state vector with scaled tabular features (Hybrid Fusion)
        fused_train = np.hstack([gru_embeddings, tabs_scaled])

        # Fit hybrid regression head
        self.head.fit(fused_train, targets)
        self.fitted_ = True
        return self

    def predict(self, y_all: np.ndarray, x_all_tab: np.ndarray, test_indices: np.ndarray) -> np.ndarray:
        """Forecast test set steps using sliding window histories."""
        if not self.fitted_ or self.gru_cell is None:
            raise RuntimeError("Model must be fitted before predict.")

        predictions = []
        w = self.window_size
        in_dim = 1

        for idx in test_indices:
            if idx < w:
                predictions.append(float(np.nan))
                continue
            seq = y_all[idx - w : idx].reshape(w, in_dim)
            seq_scaled = self.scaler_seq.transform(seq)
            h_t = self.gru_cell.forward_sequence(seq_scaled)
            tab_scaled = self.scaler_tab.transform(x_all_tab[idx].reshape(1, -1))[0]
            fused = np.hstack([h_t, tab_scaled]).reshape(1, -1)
            pred = float(self.head.predict(fused)[0])
            predictions.append(pred)

        return np.array(predictions)


def evaluate_extended_models(
    dataframe: pd.DataFrame, date_column: str, target_column: str
) -> dict[str, Any]:
    """Fit and benchmark Linear Regression, Random Forest, Support Vector Regression (SVR), and GRU Hybrid Model."""
    features, target, dates = build_time_features(dataframe, date_column, target_column)
    split_index = int(len(features) * 0.8)
    if split_index < 4 or len(features) - split_index < 2:
        raise ValueError("Too few usable observations for at least 4 training and 2 test rows.")

    x_train, x_test = features.iloc[:split_index], features.iloc[split_index:]
    y_train, y_test = target.iloc[:split_index], target.iloc[split_index:]
    test_dates = dates.iloc[split_index:]

    # Model Pipelines for Standard Algorithms
    model_factories = {
        "Linear Regression": lambda: Pipeline(
            [("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", LinearRegression())]
        ),
        "Random Forest": lambda: Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", RandomForestRegressor(n_estimators=250, random_state=42, min_samples_leaf=2, n_jobs=-1)),
            ]
        ),
        "Support Vector Regressor (SVR)": lambda: Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", SVR(kernel="rbf", C=10.0, epsilon=0.05)),
            ]
        ),
    }

    results: dict[str, Any] = {
        "metrics": {},
        "predictions": {},
        "residuals": {},
        "actual": y_test.reset_index(drop=True),
        "dates": test_dates.reset_index(drop=True),
        "features": list(features.columns),
        "training_rows": len(x_train),
        "test_rows": len(x_test),
        "split_date": test_dates.iloc[0],
        "training_times": {},
        "gru_status": {"available": False, "reason": ""},
    }

    for model_name, factory in model_factories.items():
        t0 = time.perf_counter()
        pipeline = factory()
        pipeline.fit(x_train, y_train)
        preds = np.asarray(pipeline.predict(x_test), dtype=float)
        train_time = time.perf_counter() - t0

        results["predictions"][model_name] = preds
        results["residuals"][model_name] = (y_test.to_numpy() - preds)
        results["training_times"][model_name] = round(train_time, 4)
        results["metrics"][model_name] = {
            "MAE": float(mean_absolute_error(y_test, preds)),
            "RMSE": float(np.sqrt(mean_squared_error(y_test, preds))),
            "R²": float(r2_score(y_test, preds)) if len(y_test) >= 2 else float("nan"),
        }

    # Evaluate GRU Hybrid Model if data meets sequence depth
    gru_ok, gru_msg = check_gru_data_sufficiency(dates, target, min_sequence_rows=16)
    results["gru_status"] = {"available": gru_ok, "reason": gru_msg}

    if gru_ok:
        try:
            t0 = time.perf_counter()
            gru_hybrid = GRUHybridTimeSeriesRegressor(window_size=3, hidden_dim=8, seed=42)
            imputer = SimpleImputer(strategy="median")
            imputed_features = imputer.fit_transform(features)

            gru_hybrid.fit(y_train.to_numpy(), imputed_features[:split_index])
            all_target = target.to_numpy()
            test_indices = np.arange(split_index, len(features))
            gru_preds = gru_hybrid.predict(all_target, imputed_features, test_indices)
            train_time = time.perf_counter() - t0

            # Guard against any NaNs in initial window
            valid_mask = np.isfinite(gru_preds)
            if valid_mask.sum() >= 2:
                results["predictions"]["GRU Hybrid Model"] = gru_preds
                results["residuals"]["GRU Hybrid Model"] = (y_test.to_numpy() - gru_preds)
                results["training_times"]["GRU Hybrid Model"] = round(train_time, 4)
                results["metrics"]["GRU Hybrid Model"] = {
                    "MAE": float(mean_absolute_error(y_test.loc[valid_mask], gru_preds[valid_mask])),
                    "RMSE": float(np.sqrt(mean_squared_error(y_test.loc[valid_mask], gru_preds[valid_mask]))),
                    "R²": float(r2_score(y_test.loc[valid_mask], gru_preds[valid_mask])),
                }
        except Exception as e:
            results["gru_status"] = {"available": False, "reason": f"GRU Hybrid training encountered an issue: {e}"}

    return results
