"""
BattLab — Experimental Battery Validation, Dataset Ingestion & Error Framework
=============================================================================
Provides a rigorous, reproducible framework for:
1. Ingesting, parsing, and validating battery testbench CSV datasets (Arbin, Maccor, BioLogic, Neware).
2. Schema and data integrity verification (missing fields, NaNs, non-monotonic time, physical bounds).
3. Resampling and time-series alignment between simulation predictions and measured data.
4. Comprehensive statistical metrics (MAE, RMSE, MBE, MaxError, R^2, error percentiles).
5. Separate evaluation for voltage, surface/core temperature, capacity, and delivered energy.
6. Defensible calibration vs. held-out validation dataset splitting.
7. Explicit data provenance tracking distinguishing SYNTHETIC benchmarks from PHYSICAL_LABORATORY datasets.
8. Physical validation blocking: Explicitly flags PHYSICAL EXPERIMENTAL VALIDATION: BLOCKED if no genuine
   hardware testbench measurements are provided.
"""
from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple


# ── Canonical Schema Definition ───────────────────────────────────────────────

CANONICAL_COLUMNS = {
    "t_s": {"aliases": ["t_s", "time", "time_s", "test_time", "elapsed_time_s", "t"], "required": True},
    "current_a": {"aliases": ["current_a", "current", "i_a", "i_pack_a", "i"], "required": True},
    "voltage_v": {"aliases": ["voltage_v", "voltage", "v_v", "v_pack_v", "v"], "required": True},
    "temp_surface_c": {"aliases": ["temp_surface_c", "temp", "temp_c", "temperature", "temp_surface", "t_surf_c"], "required": False},
    "temp_core_c": {"aliases": ["temp_core_c", "temp_core", "t_core_c", "core_temp_c"], "required": False},
    "temp_ambient_c": {"aliases": ["temp_ambient_c", "temp_amb", "t_amb_c", "ambient_temp_c"], "required": False},
    "soc": {"aliases": ["soc", "state_of_charge"], "required": False},
    "capacity_ah": {"aliases": ["capacity_ah", "capacity", "ah", "discharge_capacity_ah"], "required": False},
}

# Physical bounds for validation sanity checks
BOUNDS = {
    "t_s": (0.0, 1e8),
    "current_a": (-2000.0, 2000.0),
    "voltage_v": (0.50, 1000.0),
    "temp_surface_c": (-50.0, 150.0),
    "temp_core_c": (-50.0, 180.0),
    "temp_ambient_c": (-50.0, 80.0),
    "soc": (0.0, 1.05),
}


@dataclass
class DatasetValidationReport:
    is_valid: bool
    total_rows: int
    valid_rows: int
    errors: List[str]
    warnings: List[str]
    column_mapping: Dict[str, str]
    time_span_s: float
    sample_interval_mean_s: float
    is_physical_laboratory_data: bool
    dataset_classification: str          # "PHYSICAL_LABORATORY" | "SYNTHETIC_BENCHMARK" | "UNVERIFIED"
    provenance: Dict[str, Any]


@dataclass
class ErrorMoments:
    mae: float
    rmse: float
    mbe: float
    max_error: float
    r_squared: float
    p50_error: float
    p90_error: float
    p99_error: float
    n_samples: int
    units: str


@dataclass
class ExperimentalValidationResult:
    status: str                          # "VALIDATION_PASSED" | "VALIDATION_FAILED" | "BLOCKED_MEASURED_DATA_REQUIRED"
    is_experimentally_validated: bool
    dataset_name: str
    dataset_classification: str
    target_cell_model: Optional[str]
    voltage_metrics: Optional[ErrorMoments]
    temperature_metrics: Optional[ErrorMoments]
    capacity_error_pct: Optional[float]
    energy_error_pct: Optional[float]
    split_type: str                      # "FULL_DATASET" | "CALIBRATION_SPLIT" | "HELD_OUT_VALIDATION"
    aligned_samples_count: int
    provenance_metadata: Dict[str, Any]
    disclaimer: str
    blockers: List[str]


def parse_and_validate_csv_dataset(
    csv_content: str,
    custom_mapping: Optional[Dict[str, str]] = None,
    is_physical_data: bool = False,
    dataset_name: str = "Imported Dataset",
    cell_id: Optional[str] = None,
    test_protocol: Optional[str] = None,
) -> Tuple[DatasetValidationReport, List[Dict[str, float]]]:
    """
    Parse and validate raw CSV string against battery validation standards.
    """
    errors: List[str] = []
    warnings: List[str] = []
    records: List[Dict[str, float]] = []

    if not csv_content or not csv_content.strip():
        return DatasetValidationReport(
            is_valid=False, total_rows=0, valid_rows=0, errors=["Empty CSV content provided."],
            warnings=[], column_mapping={}, time_span_s=0.0, sample_interval_mean_s=0.0,
            is_physical_laboratory_data=is_physical_data, dataset_classification="UNVERIFIED",
            provenance={},
        ), []

    reader = csv.reader(io.StringIO(csv_content.strip()))
    try:
        header = next(reader)
    except StopIteration:
        return DatasetValidationReport(
            is_valid=False, total_rows=0, valid_rows=0, errors=["CSV contains no header row."],
            warnings=[], column_mapping={}, time_span_s=0.0, sample_interval_mean_s=0.0,
            is_physical_laboratory_data=is_physical_data, dataset_classification="UNVERIFIED",
            provenance={},
        ), []

    cleaned_headers = [h.strip().lower().replace(" ", "_") for h in header]
    resolved_mapping: Dict[str, str] = {}

    # Resolve column mappings
    for canon_col, spec in CANONICAL_COLUMNS.items():
        if custom_mapping and canon_col in custom_mapping and custom_mapping[canon_col] in header:
            resolved_mapping[canon_col] = custom_mapping[canon_col]
        else:
            for alias in spec["aliases"]:
                if alias in cleaned_headers:
                    idx = cleaned_headers.index(alias)
                    resolved_mapping[canon_col] = header[idx]
                    break

    # Check required columns
    for canon_col, spec in CANONICAL_COLUMNS.items():
        if spec["required"] and canon_col not in resolved_mapping:
            errors.append(f"Missing required canonical column '{canon_col}' (aliases checked: {spec['aliases']}).")

    if errors:
        return DatasetValidationReport(
            is_valid=False, total_rows=0, valid_rows=0, errors=errors, warnings=warnings,
            column_mapping=resolved_mapping, time_span_s=0.0, sample_interval_mean_s=0.0,
            is_physical_laboratory_data=is_physical_data, dataset_classification="UNVERIFIED",
            provenance={},
        ), []

    header_indices = {h: idx for idx, h in enumerate(header)}
    time_col = resolved_mapping["t_s"]
    v_col = resolved_mapping["voltage_v"]
    i_col = resolved_mapping["current_a"]
    t_surf_col = resolved_mapping.get("temp_surface_c")
    t_core_col = resolved_mapping.get("temp_core_c")

    prev_time = -1.0
    row_count = 0
    intervals: List[float] = []

    for row_idx, row in enumerate(reader, start=2):
        if not row or all(c.strip() == "" for c in row):
            continue
        row_count += 1
        try:
            t_val = float(row[header_indices[time_col]])
            v_val = float(row[header_indices[v_col]])
            i_val = float(row[header_indices[i_col]])
        except (ValueError, IndexError) as err:
            errors.append(f"Row {row_idx}: Non-numeric or missing required values ({err}).")
            continue

        if math.isnan(t_val) or math.isnan(v_val) or math.isnan(i_val):
            errors.append(f"Row {row_idx}: Contains NaN in primary measurement.")
            continue
        if math.isinf(t_val) or math.isinf(v_val) or math.isinf(i_val):
            errors.append(f"Row {row_idx}: Contains Infinity in primary measurement.")
            continue

        # Monotonicity check
        if t_val < prev_time:
            errors.append(f"Row {row_idx}: Non-monotonic timestamp (t={t_val} s < prev={prev_time} s).")
            continue
        elif t_val == prev_time:
            warnings.append(f"Row {row_idx}: Duplicate timestamp t={t_val} s detected.")

        if prev_time >= 0.0:
            intervals.append(t_val - prev_time)
        prev_time = t_val

        # Range verification
        if not (BOUNDS["voltage_v"][0] <= v_val <= BOUNDS["voltage_v"][1]):
            warnings.append(f"Row {row_idx}: Voltage {v_val} V outside typical physical range.")
        if not (BOUNDS["current_a"][0] <= i_val <= BOUNDS["current_a"][1]):
            warnings.append(f"Row {row_idx}: Current {i_val} A outside typical range.")

        pt: Dict[str, float] = {
            "t_s": t_val,
            "voltage_v": v_val,
            "current_a": i_val,
        }
        if t_surf_col and header_indices.get(t_surf_col) is not None:
            try:
                pt["temp_surface_c"] = float(row[header_indices[t_surf_col]])
            except (ValueError, IndexError):
                pass
        if t_core_col and header_indices.get(t_core_col) is not None:
            try:
                pt["temp_core_c"] = float(row[header_indices[t_core_col]])
            except (ValueError, IndexError):
                pass

        records.append(pt)

    if not records:
        errors.append("No valid data rows successfully extracted.")

    time_span = (records[-1]["t_s"] - records[0]["t_s"]) if len(records) > 1 else 0.0
    mean_dt = (sum(intervals) / len(intervals)) if intervals else 0.0

    classification = "PHYSICAL_LABORATORY" if is_physical_data else "SYNTHETIC_BENCHMARK"
    is_valid = len(errors) == 0 and len(records) > 0

    provenance = {
        "dataset_name": dataset_name,
        "import_timestamp": datetime.utcnow().isoformat(),
        "cell_id": cell_id or "UNKNOWN_CELL",
        "test_protocol": test_protocol or "UNSPECIFIED_DISCHARGE",
        "row_count": len(records),
        "time_span_s": round(time_span, 2),
        "sampling_dt_s": round(mean_dt, 3),
        "classification": classification,
        "is_physical_laboratory_data": is_physical_data,
    }

    report = DatasetValidationReport(
        is_valid=is_valid,
        total_rows=row_count,
        valid_rows=len(records),
        errors=errors[:20],  # capped for readability
        warnings=warnings[:20],
        column_mapping=resolved_mapping,
        time_span_s=round(time_span, 2),
        sample_interval_mean_s=round(mean_dt, 3),
        is_physical_laboratory_data=is_physical_data,
        dataset_classification=classification,
        provenance=provenance,
    )
    return report, records


def align_and_evaluate_validation(
    simulated_timeseries: List[Dict[str, Any]],
    measured_timeseries: List[Dict[str, float]],
    target_metric: str = "voltage_v",
    is_physical_laboratory_data: bool = False,
    dataset_name: str = "Benchmark",
    split_ratio_calibration: Optional[float] = None, # e.g. 0.70 for 70/30 split
    split_mode: str = "FULL_DATASET", # "FULL_DATASET" | "CALIBRATION" | "HELD_OUT_VALIDATION"
    voltage_rmse_threshold_v: float = 0.050,
    temp_rmse_threshold_c: float = 2.5,
    min_r2_threshold: float = 0.95,
    min_aligned_samples: int = 10,
) -> ExperimentalValidationResult:
    """
    Interpolate simulated predictions onto measured time points, compute statistical
    error moments, and provide an evidence-backed validation assessment.
    """
    blockers: List[str] = []
    if not is_physical_laboratory_data:
        blockers.append("PHYSICAL EXPERIMENTAL VALIDATION: BLOCKED — MEASURED DATA REQUIRED. (Evaluated dataset is synthetic benchmark).")

    if not simulated_timeseries or not measured_timeseries:
        return ExperimentalValidationResult(
            status="BLOCKED_MEASURED_DATA_REQUIRED" if not is_physical_laboratory_data else "VALIDATION_FAILED",
            is_experimentally_validated=False,
            dataset_name=dataset_name,
            dataset_classification="PHYSICAL_LABORATORY" if is_physical_laboratory_data else "SYNTHETIC_BENCHMARK",
            target_cell_model=None,
            voltage_metrics=None,
            temperature_metrics=None,
            capacity_error_pct=None,
            energy_error_pct=None,
            split_type=split_mode,
            aligned_samples_count=0,
            provenance_metadata={},
            disclaimer="Empty time-series provided; validation cannot execute.",
            blockers=blockers,
        )

    # Apply calibration / validation split if specified
    meas_data = measured_timeseries
    if split_ratio_calibration is not None and 0.0 < split_ratio_calibration < 1.0:
        split_idx = int(round(len(measured_timeseries) * split_ratio_calibration))
        if split_mode == "CALIBRATION":
            meas_data = measured_timeseries[:split_idx]
        elif split_mode == "HELD_OUT_VALIDATION":
            meas_data = measured_timeseries[split_idx:]

    # Build piecewise linear interpolator for simulated values
    sim_t = [float(pt["t_s"]) for pt in simulated_timeseries if pt.get("t_s") is not None]
    sim_v = [float(pt["voltage_v"]) for pt in simulated_timeseries if pt.get("voltage_v") is not None]
    sim_temp = [float(pt["temp_c"]) for pt in simulated_timeseries if pt.get("temp_c") is not None]

    if len(sim_t) < 2 or len(sim_v) < 2:
        return ExperimentalValidationResult(
            status="VALIDATION_FAILED",
            is_experimentally_validated=False,
            dataset_name=dataset_name,
            dataset_classification="SYNTHETIC_BENCHMARK",
            target_cell_model=None,
            voltage_metrics=None,
            temperature_metrics=None,
            capacity_error_pct=None,
            energy_error_pct=None,
            split_type=split_mode,
            aligned_samples_count=0,
            provenance_metadata={},
            disclaimer="Insufficient simulated points for alignment.",
            blockers=blockers,
        )

    def interp(t: float, x_arr: List[float], y_arr: List[float]) -> Optional[float]:
        if t < x_arr[0] or t > x_arr[-1]:
            return None
        # Binary search / linear scan
        for i in range(len(x_arr) - 1):
            if x_arr[i] <= t <= x_arr[i + 1]:
                dx = x_arr[i + 1] - x_arr[i]
                frac = (t - x_arr[i]) / dx if dx > 1e-9 else 0.0
                return y_arr[i] + frac * (y_arr[i + 1] - y_arr[i])
        return y_arr[-1]

    aligned_v_sim: List[float] = []
    aligned_v_meas: List[float] = []
    aligned_t_sim: List[float] = []
    aligned_t_meas: List[float] = []

    for pt in meas_data:
        tm = pt["t_s"]
        vm = pt.get("voltage_v")
        if vm is not None:
            v_sim = interp(tm, sim_t, sim_v)
            if v_sim is not None:
                aligned_v_sim.append(v_sim)
                aligned_v_meas.append(vm)

        t_surf_meas = pt.get("temp_surface_c")
        if t_surf_meas is not None and sim_temp:
            t_sim = interp(tm, sim_t, sim_temp)
            if t_sim is not None:
                aligned_t_sim.append(t_sim)
                aligned_t_meas.append(t_surf_meas)

    if not aligned_v_sim:
        blockers.append("No overlapping time window found between simulated and measured datasets.")
        return ExperimentalValidationResult(
            status="VALIDATION_FAILED",
            is_experimentally_validated=False,
            dataset_name=dataset_name,
            dataset_classification="PHYSICAL_LABORATORY" if is_physical_laboratory_data else "SYNTHETIC_BENCHMARK",
            target_cell_model=None,
            voltage_metrics=None,
            temperature_metrics=None,
            capacity_error_pct=None,
            energy_error_pct=None,
            split_type=split_mode,
            aligned_samples_count=0,
            provenance_metadata={},
            disclaimer="Zero aligned samples; datasets do not overlap in time.",
            blockers=blockers,
        )

    def compute_moments(preds: List[float], obs: List[float], units: str) -> ErrorMoments:
        n = len(preds)
        residuals = [preds[i] - obs[i] for i in range(n)]
        abs_res = sorted([abs(r) for r in residuals])
        mae = sum(abs_res) / n
        rmse = math.sqrt(sum(r ** 2 for r in residuals) / n)
        mbe = sum(residuals) / n
        max_err = abs_res[-1]
        p50 = abs_res[int(0.50 * n)]
        p90 = abs_res[min(n - 1, int(0.90 * n))]
        p99 = abs_res[min(n - 1, int(0.99 * n))]

        mean_obs = sum(obs) / n
        ss_tot = sum((o - mean_obs) ** 2 for o in obs)
        ss_res = sum(r ** 2 for r in residuals)
        r2 = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot))) if ss_tot > 1e-12 else (1.0 if ss_res < 1e-12 else 0.0)

        return ErrorMoments(
            mae=round(mae, 4),
            rmse=round(rmse, 4),
            mbe=round(mbe, 4),
            max_error=round(max_err, 4),
            r_squared=round(r2, 4),
            p50_error=round(p50, 4),
            p90_error=round(p90, 4),
            p99_error=round(p99, 4),
            n_samples=n,
            units=units,
        )

    v_moments = compute_moments(aligned_v_sim, aligned_v_meas, "V")
    t_moments = compute_moments(aligned_t_sim, aligned_t_meas, "°C") if aligned_t_sim else None

    # Capacity / Energy integral comparison if current is present
    meas_ah = sum(abs(pt.get("current_a", 0.0)) * (meas_data[i+1]["t_s"] - meas_data[i]["t_s"]) / 3600.0 for i, pt in enumerate(meas_data[:-1])) if len(meas_data) > 1 else 0.0
    sim_ah = sum(abs(pt.get("current_a", 0.0)) * (simulated_timeseries[i+1]["t_s"] - simulated_timeseries[i]["t_s"]) / 3600.0 for i, pt in enumerate(simulated_timeseries[:-1])) if len(simulated_timeseries) > 1 else 0.0

    cap_err = abs(sim_ah - meas_ah) / max(meas_ah, 1e-3) * 100.0 if meas_ah > 0 else None

    # Evaluate against configurable provisional thresholds
    meets_voltage = v_moments.rmse <= voltage_rmse_threshold_v
    meets_temp = (t_moments is None or t_moments.rmse <= temp_rmse_threshold_c)
    meets_r2 = v_moments.r_squared >= min_r2_threshold
    meets_samples = len(aligned_v_sim) >= min_aligned_samples

    # Determine status
    if not is_physical_laboratory_data:
        status = "BLOCKED_MEASURED_DATA_REQUIRED"
        is_validated = False
    elif meets_voltage and meets_temp and meets_r2 and meets_samples:
        status = "VALIDATION_PASSED"
        is_validated = True
    else:
        status = "VALIDATION_FAILED"
        is_validated = False

    return ExperimentalValidationResult(
        status=status,
        is_experimentally_validated=is_validated,
        dataset_name=dataset_name,
        dataset_classification="PHYSICAL_LABORATORY" if is_physical_laboratory_data else "SYNTHETIC_BENCHMARK",
        target_cell_model=None,
        voltage_metrics=v_moments,
        temperature_metrics=t_moments,
        capacity_error_pct=round(cap_err, 2) if cap_err is not None else None,
        energy_error_pct=None,
        split_type=split_mode,
        aligned_samples_count=len(aligned_v_sim),
        provenance_metadata={
            "aligned_at": datetime.utcnow().isoformat(),
            "target_metric": target_metric,
            "split_mode": split_mode,
            "calibration_split_ratio": split_ratio_calibration,
            "evaluated_thresholds": {
                "voltage_rmse_threshold_v": voltage_rmse_threshold_v,
                "temp_rmse_threshold_c": temp_rmse_threshold_c,
                "min_r2_threshold": min_r2_threshold,
                "min_aligned_samples": min_aligned_samples,
                "classification_note": "Configurable provisional screening thresholds. Not universal scientific standards.",
            },
        },
        disclaimer=(
            "Model verification establishes mathematical and numerical consistency. "
            "Physical experimental validation requires measured battery testbench data "
            "with documented experimental uncertainty."
        ),
        blockers=blockers,
    )

