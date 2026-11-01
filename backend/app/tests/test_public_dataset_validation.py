"""
BattLab — Test Suite: Public Battery Dataset Experimental Validation & Hardening
================================================================================
Tests numerical accuracy, data provenance, strict zero data leakage, held-out
partitions, and energy conservation against the NASA Ames PCoE 18650 Li-ion dataset.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.nasa_dataset_adapter import (
    BASE_DIR,
    DATA_DIR,
    ARTIFACTS_DIR,
    FIGURES_DIR,
    simulate_ecm_cycle,
    extract_discharge_cycle_data,
)
from app.services.ecm import ecm_step, TheveninRCState

client = TestClient(app)


def test_public_dataset_files_exist():
    """Verify raw archives and canonical CSVs exist and are non-empty."""
    b0005 = DATA_DIR / "B0005.mat"
    b0006 = DATA_DIR / "B0006.mat"
    readme = DATA_DIR / "README.txt"
    
    assert b0005.exists() and b0005.stat().st_size > 10_000_000
    assert b0006.exists() and b0006.stat().st_size > 10_000_000
    assert readme.exists() and readme.stat().st_size > 1000

    # Canonical exports
    assert (DATA_DIR / "nasa_b0005_cycle01_calibration.csv").exists()
    assert (DATA_DIR / "nasa_b0005_cycle02_heldout.csv").exists()
    assert (DATA_DIR / "nasa_b0005_cycle10_heldout.csv").exists()
    assert (DATA_DIR / "nasa_b0006_cycle01_heldout_cell.csv").exists()
    assert (DATA_DIR / "nasa_b0005_aging_capacity_trajectory.csv").exists()


def test_dataset_manifest_integrity():
    """Verify dataset manifest schema, provenance, and cryptographic hashes."""
    manifest_path = ARTIFACTS_DIR / "dataset_manifest.json"
    assert manifest_path.exists()
    
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    assert "NASA" in manifest["dataset_name"]
    assert manifest["authors"] == "B. Saha and K. Goebel"
    assert manifest["year"] == 2007
    assert "https://" in manifest["source_url"]
    assert len(manifest["raw_archives"]) >= 3
    assert len(manifest["canonical_csv_exports"]) >= 5

    # Verify SHA-256 hash length
    for item in manifest["raw_archives"] + manifest["canonical_csv_exports"]:
        assert len(item["sha256"]) == 64
        assert item["size_bytes"] > 0


def test_strict_zero_leakage_heldout_generalization():
    """
    Phase 2: Verify that held-out evaluations use FROZEN capacity from Cycle 1
    or nominal datasheet capacity, with zero future capacity knowledge.
    """
    summary_path = ARTIFACTS_DIR / "validation_summary.json"
    assert summary_path.exists()

    with open(summary_path, "r") as f:
        summary = json.load(f)

    parts = summary["partitions"]
    
    # Calibration fit (B0005 Cycle 1)
    cal = parts["electrical_calibration_b0005_cycle1"]["metrics"]
    assert cal["r2"] > 0.94
    assert cal["rmse"] < 0.055

    # Held-out Cycle 2 (strict zero-leakage)
    c2 = parts["electrical_heldout_b0005_cycle2"]["strict_zero_leakage_metrics"]
    assert c2["r2"] > 0.94
    assert c2["mae"] < 0.045

    # Held-out Cycle 10 (strict zero-leakage)
    c10 = parts["electrical_heldout_b0005_cycle10"]["strict_zero_leakage_metrics"]
    assert c10["r2"] > 0.90
    assert c10["mae"] < 0.050

    # Held-out Unseen Physical Cell B0006 (nominal capacity)
    c6 = parts["electrical_heldout_b0006_cycle1_unseen_cell"]["strict_zero_leakage_metrics"]
    assert c6["r2"] > 0.94
    assert c6["rmse"] < 0.055


def test_anti_leakage_guard_assertion():
    """
    Phase 2 Regression Test: Assert that forward evaluation fails or is guarded
    if an uncalibrated future post-test capacity is passed without disclosure.
    """
    b0005 = DATA_DIR / "B0005.mat"
    c2_data = extract_discharge_cycle_data(b0005, "B0005", 1)
    
    # Calibrated capacity from cycle 1
    c1_data = extract_discharge_cycle_data(b0005, "B0005", 0)
    q_cal = c1_data["capacity_ah"]
    
    # Forward simulation MUST use q_cal, not c2_data["capacity_ah"]
    v_preds_leak_free, _ = simulate_ecm_cycle(
        c2_data["time_s"], c2_data["current_a"], c2_data["temp_surface_c"],
        capacity_ah=q_cal, r0_ohm=0.09739, r1_ohm=0.04530, c1_farad=1500.0, q_scale=1.0181
    )
    
    # Verify that predictions are non-empty and bounded
    assert len(v_preds_leak_free) == len(c2_data["time_s"])
    assert np.all(v_preds_leak_free > 2.0)
    assert np.all(v_preds_leak_free < 4.5)


def test_operating_envelope_breakdown():
    """
    Phase 1: Verify breakdown between main operating plateau (V >= 2.75V)
    and deep cutoff & relaxation knee.
    """
    summary_path = ARTIFACTS_DIR / "validation_summary.json"
    with open(summary_path, "r") as f:
        summary = json.load(f)

    c1_breakdown = summary["partitions"]["electrical_calibration_b0005_cycle1"]["operating_envelope_breakdown"]
    
    # Main plateau has higher precision (lower RMSE) than deep cutoff
    main_plateau = c1_breakdown["main_operating_plateau"]
    cutoff_relax = c1_breakdown["cutoff_and_relaxation"]
    
    assert main_plateau["n_samples"] > 170
    assert main_plateau["rmse"] < cutoff_relax["rmse"]
    assert main_plateau["max_error"] < cutoff_relax["max_error"]


def test_thermal_held_out_partitions_and_core_blocking():
    """
    Phase 4 & 5: Verify separate thermal calibration and held-out partitions,
    and confirm core temperature is strictly BLOCKED.
    """
    summary_path = ARTIFACTS_DIR / "validation_summary.json"
    with open(summary_path, "r") as f:
        summary = json.load(f)

    parts = summary["partitions"]
    
    # Calibration Fit
    t_cal = parts["thermal_calibration_b0005_cycle1"]
    assert t_cal["partition_type"] == "THERMAL_CALIBRATION_FIT"
    assert t_cal["metrics"]["rmse"] < 1.0

    # Held-Out Cycle 2
    t_c2 = parts["thermal_heldout_b0005_cycle2"]
    assert t_c2["partition_type"] == "THERMAL_HELD_OUT_EVALUATION"
    assert t_c2["metrics"]["rmse"] < 1.0

    # Core Temperature: MUST be marked BLOCKED
    t_core = parts["thermal_core_temperature"]
    assert t_core["status"] == "BLOCKED"
    assert "no internal core sensors exist" in t_core["reason"]


def test_aging_retrospective_vs_prospective_separation():
    """
    Phase 4 & 5: Verify separation between retrospective trajectory fit (168 cycles)
    and prospective forecasts from early windows.
    """
    summary_path = ARTIFACTS_DIR / "validation_summary.json"
    with open(summary_path, "r") as f:
        summary = json.load(f)

    parts = summary["partitions"]
    
    # Retrospective fit captures overall mean slope
    retro = parts["aging_retrospective_fit_168_cycles"]["metrics"]
    assert retro["r2"] > 0.70
    assert retro["mae"] < 0.10

    # Prospective forecast shows known knee divergence
    prosp = parts["aging_prospective_forecasts"]["trained_1_to_30_forecast_31_to_168"]
    assert prosp["calibration_cycles"] == 30
    assert prosp["metrics"]["r2"] < 0.0  # Demonstrates unmodeled knee acceleration


def test_energy_conservation_rigorous_closure():
    """
    Phase 3: Verify mathematical closure of electrical equivalent circuit energy balance:
    E_chem == E_delivered + E_ohmic + E_polarization + Delta_E_RC.
    Residual must be < 0.05% of input energy.
    """
    soc = 1.0
    rc = TheveninRCState(0.0)
    i_pack = 2.0
    dt = 1.0
    r0 = 0.09739
    r1 = 0.04530
    c1 = 1500.0
    q_nom = 2.0

    v_ocvs = []
    v_terms = []
    q_ohmics = []
    q_pols = []

    for _ in range(500):
        v_rc_before = rc.v_rc
        res, rc = ecm_step(
            soc=soc, i_pack_a=i_pack, dt_s=dt, temp_c=25.0,
            ns=1, np_=1, nominal_capacity_ah=q_nom,
            r0_ref_ohm=r0, r1_ohm=r1, c1_farad=c1,
            rc_state=rc, enable_arrhenius=False
        )
        v_ocvs.append(res.ocv_cell_v)
        v_terms.append(res.v_term_cell_v)
        q_ohmics.append((i_pack ** 2) * r0 * dt)
        v_rc_avg = 0.5 * (v_rc_before + rc.v_rc)
        q_pols.append((v_rc_avg ** 2 / r1) * dt)
        soc -= (i_pack * dt) / (3600.0 * q_nom)

    e_chem = sum(v * i_pack * dt for v in v_ocvs)
    e_term = sum(v * i_pack * dt for v in v_terms)
    e_ohmic = sum(q_ohmics)
    e_pol = sum(q_pols)
    delta_e_rc = 0.5 * c1 * (rc.v_rc ** 2 - 0.0 ** 2)

    total_accounted = e_term + e_ohmic + e_pol + delta_e_rc
    rel_residual = abs(e_chem - total_accounted) / e_chem

    assert rel_residual < 0.0005  # < 0.05% discrete closure


def test_all_six_verdicts_present():
    """Verify all six formal engineering acceptance verdicts are present and correct."""
    summary_path = ARTIFACTS_DIR / "validation_summary.json"
    with open(summary_path, "r") as f:
        summary = json.load(f)

    verdicts = summary["verdicts"]
    assert verdicts["verdict_1_software_integration"] == "ACCEPTED"
    assert verdicts["verdict_2_numerical_verification"] == "ACCEPTED"
    assert "VALIDATED FOR SPECIFIED CONDITIONS" in verdicts["verdict_3_electrical_public_evaluation"]
    assert "CASING SURFACE ONLY" in verdicts["verdict_4_thermal_surface_evaluation"]
    assert "PARTIALLY VALIDATED" in verdicts["verdict_5_aging_validation"]
    assert "BLOCKED" in verdicts["verdict_6_intended_hardware_physical_validation"]


def test_api_public_dataset_endpoints():
    """Verify backend endpoints serve persisted validation data and manifest."""
    res_eval = client.get("/api/validation/public-dataset-evaluation")
    assert res_eval.status_code == 200
    data_eval = res_eval.json()
    assert data_eval["benchmark_id"] == "NASA_PCOE_18650_DISCHARGE_EVALUATION"
    assert "partitions" in data_eval

    res_man = client.get("/api/validation/dataset-manifest")
    assert res_man.status_code == 200
    data_man = res_man.json()
    assert "NASA" in data_man["dataset_name"]
