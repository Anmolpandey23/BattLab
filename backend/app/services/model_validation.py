"""
BattLab — Model Validation and Error Analysis Framework
=======================================================
Compares simulated model predictions against trusted reference or laboratory
experimental time-series observations.

Calculates:
- Mean Absolute Error (MAE)
- Root Mean Square Error (RMSE)
- Mean Bias Error (MBE)
- Maximum Error (MaxError)
- R^2 Coefficient of Determination
- Per-point error residuals

Distinguishes Calibration from Validation:
- Physical validation requires independent test datasets not used during parameter fitting.
- If physical data is absent, the framework flags the validation dataset provenance explicitly.
"""
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ValidationMetrics:
    mae: float
    rmse: float
    mbe: float
    max_error: float
    r_squared: float
    n_samples: int
    units: str


def compute_validation_metrics(
    predictions: List[float],
    observations: List[float],
    units: str = "V",
) -> ValidationMetrics:
    """
    Compute standard statistical validation error metrics.
    """
    if len(predictions) != len(observations):
        raise ValueError(f"Length mismatch: {len(predictions)} predictions vs {len(observations)} observations")
    if len(predictions) == 0:
        raise ValueError("Cannot compute metrics on empty series")

    n = len(predictions)
    residuals = [predictions[i] - observations[i] for i in range(n)]

    mae = sum(abs(r) for r in residuals) / n
    mse = sum(r ** 2 for r in residuals) / n
    rmse = math.sqrt(mse)
    mbe = sum(residuals) / n
    max_err = max(abs(r) for r in residuals)

    # R^2 calculation
    mean_obs = sum(observations) / n
    ss_tot = sum((o - mean_obs) ** 2 for o in observations)
    ss_res = sum(r ** 2 for r in residuals)

    if ss_tot > 1e-12:
        r2 = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot)))
    else:
        r2 = 1.0 if ss_res < 1e-12 else 0.0

    return ValidationMetrics(
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        mbe=round(mbe, 4),
        max_error=round(max_err, 4),
        r_squared=round(r2, 4),
        n_samples=n,
        units=units,
    )


def run_benchmark_validation(
    simulated_timeseries: List[Dict[str, Any]],
    target_metric: str = "voltage_v",
    reference_dataset_name: str = "SYNTHETIC_BENCHMARK_CC_40A",
) -> Dict[str, Any]:
    """
    Execute validation against a known reference profile.
    """
    # Extract predicted values at non-null timestamps
    valid_points = [
        pt for pt in simulated_timeseries
        if pt.get(target_metric) is not None
    ]

    if not valid_points:
        return {
            "status": "UNVALIDATED",
            "reason": f"No valid simulated points found for metric '{target_metric}'",
            "dataset_provenance": "Missing observation data",
        }

    preds = [float(pt[target_metric]) for pt in valid_points]

    # Reference benchmark generation based on calibrated physics
    # Note: Clearly labelled as benchmark/synthetic unless user attaches an imported lab CSV
    obs = []
    for pt in valid_points:
        # Expected reference discharge curve for 14S at nominal 40A
        # with literature voltage sag
        soc = pt.get("soc", 1.0)
        v_ideal_ocv = 14.0 * (3.0 + soc * (4.2 - 3.0))
        # Simulated observation with realistic sag
        v_ref = v_ideal_ocv - (40.0 * 0.04375)
        obs.append(v_ref)

    metrics = compute_validation_metrics(preds, obs, units="V")

    return {
        "status": "BENCHMARK_EVALUATED",
        "dataset_name": reference_dataset_name,
        "dataset_type": "Analytical Benchmark Reference (Synthetic Literature Calibrated)",
        "is_physical_laboratory_data": False,
        "target_metric": target_metric,
        "metrics": metrics.__dict__,
        "disclaimer": (
            "Reference comparison uses an analytical benchmark dataset. "
            "It establishes model software agreement, NOT physical hardware calibration."
        ),
    }

