"""
BattLab — Test Suite: Experimental Validation, Ingestion, and Statistical Metrics
================================================================================
Comprehensive verification of:
1. Dataset ingestion & parsing (canonical aliases, bounds, NaNs, infinities, non-monotonicity).
2. Analytical metric verification (MAE, RMSE, MBE, MaxError, R^2, percentiles).
3. Calibration vs. held-out validation dataset splitting.
4. Physical experimental validation blocking criteria.
5. FastAPI endpoints for dataset ingestion checking and simulation validation.
"""
import math
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.experimental_validation import (
    parse_and_validate_csv_dataset,
    align_and_evaluate_validation,
    DatasetValidationReport,
    ExperimentalValidationResult,
    ErrorMoments,
)

client = TestClient(app)


# ── Fixtures & Benchmark Data ──────────────────────────────────────────────────

VALID_CSV = """t_s,current_a,voltage_v,temp_surface_c
0.0,10.0,4.20,25.0
10.0,10.0,4.15,25.4
20.0,10.0,4.10,25.8
30.0,10.0,4.05,26.2
40.0,10.0,4.00,26.6
50.0,10.0,3.95,27.0
"""

ALIASED_CSV = """time,i_pack_a,v_pack_v,temp_c
0.0,10.0,4.20,25.0
10.0,10.0,4.15,25.4
20.0,10.0,4.10,25.8
"""

NON_MONOTONIC_CSV = """t_s,current_a,voltage_v
0.0,10.0,4.20
20.0,10.0,4.10
10.0,10.0,4.15
"""

NAN_CSV = """t_s,current_a,voltage_v
0.0,10.0,4.20
10.0,NaN,4.15
20.0,10.0,4.10
"""

INF_CSV = """t_s,current_a,voltage_v
0.0,10.0,4.20
10.0,10.0,inf
20.0,10.0,4.10
"""

MISSING_REQUIRED_CSV = """t_s,temp_surface_c
0.0,25.0
10.0,25.4
"""


# ── 1. Ingestion & Schema Tests ───────────────────────────────────────────────

def test_valid_csv_ingestion():
    report, records = parse_and_validate_csv_dataset(VALID_CSV, is_physical_data=False)
    assert report.is_valid is True
    assert report.valid_rows == 6
    assert len(report.errors) == 0
    assert report.column_mapping["t_s"] == "t_s"
    assert report.column_mapping["voltage_v"] == "voltage_v"
    assert report.column_mapping["current_a"] == "current_a"
    assert report.column_mapping["temp_surface_c"] == "temp_surface_c"
    assert report.dataset_classification == "SYNTHETIC_BENCHMARK"


def test_aliased_column_mapping():
    report, records = parse_and_validate_csv_dataset(ALIASED_CSV)
    assert report.is_valid is True
    assert report.valid_rows == 3
    assert report.column_mapping["t_s"] == "time"
    assert report.column_mapping["current_a"] == "i_pack_a"
    assert report.column_mapping["voltage_v"] == "v_pack_v"
    assert report.column_mapping["temp_surface_c"] == "temp_c"


def test_missing_required_column_rejection():
    report, records = parse_and_validate_csv_dataset(MISSING_REQUIRED_CSV)
    assert report.is_valid is False
    assert len(records) == 0
    assert any("current_a" in err for err in report.errors)
    assert any("voltage_v" in err for err in report.errors)


def test_non_monotonic_timestamp_rejection():
    report, records = parse_and_validate_csv_dataset(NON_MONOTONIC_CSV)
    assert report.is_valid is False
    assert any("Non-monotonic timestamp" in err for err in report.errors)


def test_nan_and_infinity_rejection():
    rep_nan, _ = parse_and_validate_csv_dataset(NAN_CSV)
    assert rep_nan.is_valid is False
    assert any("NaN" in err for err in rep_nan.errors)

    rep_inf, _ = parse_and_validate_csv_dataset(INF_CSV)
    assert rep_inf.is_valid is False
    assert any("Infinity" in err for err in rep_inf.errors)


def test_empty_csv_rejection():
    report, records = parse_and_validate_csv_dataset("")
    assert report.is_valid is False
    assert "Empty CSV" in report.errors[0]

    report2, records2 = parse_and_validate_csv_dataset("   \n\n  ")
    assert report2.is_valid is False


# ── 2. Analytical Metric Verification ─────────────────────────────────────────

def test_identical_series_zero_error():
    # If simulated equals measured identically, errors must be zero and R^2 = 1.0
    sim = [{"t_s": float(i * 10), "voltage_v": 4.2 - 0.005 * i, "temp_c": 25.0 + 0.1 * i, "current_a": 10.0} for i in range(10)]
    meas = [{"t_s": float(i * 10), "voltage_v": 4.2 - 0.005 * i, "temp_surface_c": 25.0 + 0.1 * i, "current_a": 10.0} for i in range(10)]

    res = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        is_physical_laboratory_data=True,
    )
    assert res.voltage_metrics is not None
    assert res.voltage_metrics.mae == 0.0
    assert res.voltage_metrics.rmse == 0.0
    assert res.voltage_metrics.max_error == 0.0
    assert res.voltage_metrics.mbe == 0.0
    assert res.voltage_metrics.r_squared == 1.0
    assert res.status == "VALIDATION_PASSED"
    assert res.is_experimentally_validated is True


def test_constant_offset_metric_exactness():
    # Constant offset of +0.050 V
    offset = 0.050
    sim = [{"t_s": float(i * 10), "voltage_v": 4.0 + offset, "temp_c": 25.0} for i in range(20)]
    meas = [{"t_s": float(i * 10), "voltage_v": 4.0, "temp_surface_c": 25.0} for i in range(20)]

    res = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        is_physical_laboratory_data=True,
    )
    assert res.voltage_metrics is not None
    assert math.isclose(res.voltage_metrics.mae, offset, abs_tol=1e-4)
    assert math.isclose(res.voltage_metrics.rmse, offset, abs_tol=1e-4)
    assert math.isclose(res.voltage_metrics.mbe, offset, abs_tol=1e-4)
    assert math.isclose(res.voltage_metrics.max_error, offset, abs_tol=1e-4)


def test_known_rmse_calculation():
    # Residuals: [+0.03, -0.04] -> RMSE = sqrt((0.0009 + 0.0016)/2) = sqrt(0.00125) = 0.035355 V
    sim = [
        {"t_s": 0.0, "voltage_v": 4.03},
        {"t_s": 10.0, "voltage_v": 3.96},
    ]
    meas = [
        {"t_s": 0.0, "voltage_v": 4.00},
        {"t_s": 10.0, "voltage_v": 4.00},
    ]
    res = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        is_physical_laboratory_data=True,
    )
    assert res.voltage_metrics is not None
    expected_rmse = math.sqrt((0.03**2 + (-0.04)**2) / 2.0)
    assert math.isclose(res.voltage_metrics.rmse, expected_rmse, abs_tol=1e-3)
    assert math.isclose(res.voltage_metrics.mae, 0.035, abs_tol=1e-3)
    assert math.isclose(res.voltage_metrics.mbe, -0.005, abs_tol=1e-3)
    assert math.isclose(res.voltage_metrics.max_error, 0.040, abs_tol=1e-3)


# ── 3. Calibration vs. Validation Separation ──────────────────────────────────

def test_calibration_vs_validation_split():
    # 100 samples split 70% calibration, 30% held-out validation
    meas = [{"t_s": float(i), "voltage_v": 4.0 - 0.001 * i} for i in range(100)]
    sim = [{"t_s": float(i), "voltage_v": 4.0 - 0.001 * i} for i in range(100)]

    res_cal = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        split_ratio_calibration=0.70,
        split_mode="CALIBRATION",
        is_physical_laboratory_data=True,
    )
    assert res_cal.aligned_samples_count == 70
    assert res_cal.split_type == "CALIBRATION"

    res_val = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        split_ratio_calibration=0.70,
        split_mode="HELD_OUT_VALIDATION",
        is_physical_laboratory_data=True,
    )
    assert res_val.aligned_samples_count == 30
    assert res_val.split_type == "HELD_OUT_VALIDATION"


# ── 4. Physical Validation Blocking Criteria ──────────────────────────────────

def test_physical_validation_blocking_on_synthetic_data():
    sim = [{"t_s": float(i * 10), "voltage_v": 4.0} for i in range(10)]
    meas = [{"t_s": float(i * 10), "voltage_v": 4.0} for i in range(10)]

    # Even with zero numerical error, if is_physical_laboratory_data is False,
    # physical validation must be BLOCKED
    res = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        is_physical_laboratory_data=False,
    )
    assert res.status == "BLOCKED_MEASURED_DATA_REQUIRED"
    assert res.is_experimentally_validated is False
    assert any("BLOCKED" in b for b in res.blockers)


def test_physical_validation_fails_on_high_error():
    # Large error (offset 0.200 V > 0.050 V threshold) on physical data
    sim = [{"t_s": float(i * 10), "voltage_v": 4.20} for i in range(10)]
    meas = [{"t_s": float(i * 10), "voltage_v": 4.00} for i in range(10)]

    res = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        is_physical_laboratory_data=True,
    )
    assert res.status == "VALIDATION_FAILED"
    assert res.is_experimentally_validated is False


# ── 5. API Ingestion & Validation Endpoint Tests ──────────────────────────────

def test_api_ingest_check_endpoint():
    resp = client.post("/api/validation/ingest-check", json={"csv_content": VALID_CSV})
    assert resp.status_code == 200
    data = resp.json()
    assert data["report"]["is_valid"] is True
    assert data["record_count"] == 6


def test_api_simulation_validate_dataset_endpoint():
    import json
    from app.database import engine
    from sqlmodel import Session
    from app.models import Project, Configuration, SimulationRun, CellSpec

    with Session(engine) as session:
        proj = Project(name="ValTest Project", application_category="Custom")
        session.add(proj)
        session.commit()
        session.refresh(proj)

        cell = CellSpec(manufacturer="ValCorp", model="V1", nominal_voltage_v=3.7, nominal_capacity_ah=5.0)
        session.add(cell)
        session.commit()
        session.refresh(cell)

        cfg = Configuration(project_id=proj.id, label="14S8P", ns=14, np=8, cell_spec_id=cell.id)
        session.add(cfg)
        session.commit()
        session.refresh(cfg)

        ts = [
            {"t_s": 0.0, "voltage_v": 4.20, "current_a": 10.0, "temp_c": 25.0},
            {"t_s": 10.0, "voltage_v": 4.15, "current_a": 10.0, "temp_c": 25.4},
            {"t_s": 20.0, "voltage_v": 4.10, "current_a": 10.0, "temp_c": 25.8},
            {"t_s": 30.0, "voltage_v": 4.05, "current_a": 10.0, "temp_c": 26.2},
            {"t_s": 40.0, "voltage_v": 4.00, "current_a": 10.0, "temp_c": 26.6},
            {"t_s": 50.0, "voltage_v": 3.95, "current_a": 10.0, "temp_c": 27.0},
        ]
        run = SimulationRun(
            project_id=proj.id,
            configuration_id=cfg.id,
            timeseries_json=json.dumps(ts),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    # Test invalid CSV returns 422 Unprocessable Entity
    bad_resp = client.post(
        f"/api/simulations/{run_id}/validate-dataset",
        json={"csv_content": NON_MONOTONIC_CSV},
    )
    assert bad_resp.status_code == 422

    # Test valid CSV executes alignment and validation
    good_resp = client.post(
        f"/api/simulations/{run_id}/validate-dataset",
        json={"csv_content": VALID_CSV, "is_physical_laboratory_data": False},
    )
    assert good_resp.status_code == 200
    result_data = good_resp.json()
    assert "dataset_report" in result_data
    assert "validation_result" in result_data
    assert result_data["validation_result"]["status"] == "BLOCKED_MEASURED_DATA_REQUIRED"
    assert result_data["validation_result"]["is_experimentally_validated"] is False


def test_configurable_acceptance_thresholds():
    sim = [{"t_s": float(i * 10), "voltage_v": 3.70 + 0.020, "temp_c": 25.0} for i in range(20)]
    meas = [{"t_s": float(i * 10), "voltage_v": 3.70, "temp_surface_c": 25.0} for i in range(20)]

    # With tight voltage threshold of 0.010 V (RMSE is 0.020 V) -> fails
    res_tight = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        is_physical_laboratory_data=True,
        voltage_rmse_threshold_v=0.010,
    )
    assert res_tight.status == "VALIDATION_FAILED"

    # With loose threshold of 0.030 V -> passes
    res_loose = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        is_physical_laboratory_data=True,
        voltage_rmse_threshold_v=0.030,
        min_r2_threshold=0.0,  # constant offset on flat line
    )
    assert res_loose.status == "VALIDATION_PASSED"
    assert "evaluated_thresholds" in res_loose.provenance_metadata


def test_disjoint_time_windows():
    sim = [{"t_s": float(i), "voltage_v": 3.70} for i in range(10)]
    meas = [{"t_s": float(100 + i), "voltage_v": 3.70} for i in range(10)]
    res = align_and_evaluate_validation(
        simulated_timeseries=sim,
        measured_timeseries=meas,
        is_physical_laboratory_data=True,
    )
    assert res.status == "VALIDATION_FAILED"
    assert "Zero aligned samples" in res.disclaimer
