"""
BattLab — Test Suite: ECM, Validation Framework & Uncertainty Propagation
========================================================================
Independent unit and integration tests verifying:
1. Calibrated Equivalent Circuit Model (OCV, Arrhenius, Thevenin RC, entropic heat)
2. Model validation error metrics (MAE, RMSE, MBE, R^2)
3. Parameter provenance cataloging and confidence scoring
4. Monte Carlo parameter uncertainty distributions and sensitivity
5. API endpoints for provenance, validation, and uncertainty
"""
import pytest
import math
from fastapi.testclient import TestClient

from app.main import app
from app.services.ecm import (
    get_ocv_v,
    get_arrhenius_resistance_ohm,
    get_temperature_derated_capacity_ah,
    update_thevenin_rc,
    TheveninRCState,
    ecm_step,
    OCV_CURVES,
)
from app.services.model_validation import (
    compute_validation_metrics,
    run_benchmark_validation,
)
from app.services.provenance import (
    generate_provenance_catalog,
    ProvenanceCategory,
    ConfidenceLevel,
)
from app.services.uncertainty import (
    run_monte_carlo_uncertainty,
    _percentile,
)

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ECM Core Unit Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEquivalentCircuitModel:
    def test_ocv_monotonicity_nmc(self):
        """NMC OCV curve must be strictly monotonically increasing from 0% to 100% SOC."""
        soc_points = [0.0, 0.05, 0.20, 0.50, 0.80, 0.95, 1.0]
        ocvs = [get_ocv_v(s, chemistry="NMC") for s in soc_points]
        for i in range(len(ocvs) - 1):
            assert ocvs[i + 1] > ocvs[i], f"OCV non-monotonic at SOC={soc_points[i]}: {ocvs[i]} -> {ocvs[i+1]}"

    def test_ocv_monotonicity_lfp(self):
        """LFP OCV curve must be monotonic and feature characteristic 3.29-3.32V plateau."""
        soc_points = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
        ocvs = [get_ocv_v(s, chemistry="LFP") for s in soc_points]
        for i in range(len(ocvs) - 1):
            assert ocvs[i + 1] >= ocvs[i]
        # Mid-SOC plateau check
        assert 3.28 <= get_ocv_v(0.5, chemistry="LFP") <= 3.32

    def test_ocv_fallback_chemistry(self):
        """Unknown chemistry smoothly scales between specified v_min and v_max."""
        v = get_ocv_v(0.5, chemistry="CUSTOM_SODIUM", v_min=2.0, v_max=4.0)
        assert pytest.approx(v, abs=1e-3) == 3.0

    def test_arrhenius_resistance_temperature_scaling(self):
        """Arrhenius equation must predict higher resistance at low temp and lower at high temp."""
        r_ref = 0.020  # 20 mOhm at 25°C
        r_cold = get_arrhenius_resistance_ohm(r_ref, temp_c=-10.0)
        r_room = get_arrhenius_resistance_ohm(r_ref, temp_c=25.0)
        r_warm = get_arrhenius_resistance_ohm(r_ref, temp_c=45.0)

        assert pytest.approx(r_room, rel=1e-4) == r_ref
        assert r_cold > r_room * 1.5, f"Expected cold R > 1.5x room R, got {r_cold} vs {r_room}"
        assert r_warm < r_room, f"Expected warm R < room R, got {r_warm} vs {r_room}"

    def test_thevenin_rc_relaxation_exponential_decay(self):
        """Current interruption must produce exponential polarization decay: V_RC(t) = V0 * exp(-t/tau)."""
        r1 = 0.010    # 10 mOhm
        c1 = 1000.0   # 1000 Farad -> tau = 10 s
        dt = 5.0      # half time-constant
        state = TheveninRCState(v_rc=0.50)  # initially 500 mV polarized

        # Step with 0 current (relaxation)
        decayed = update_thevenin_rc(state, i_cell_a=0.0, dt_s=dt, r1_ohm=r1, c1_farad=c1)
        expected = 0.50 * math.exp(-5.0 / 10.0)
        assert pytest.approx(decayed.v_rc, rel=1e-4) == expected

    def test_thevenin_rc_steady_state_asymptote(self):
        """Constant current discharge over several time-constants must approach I * R1."""
        r1 = 0.010
        c1 = 100.0  # tau = 1.0 s
        i_cell = 20.0
        state = TheveninRCState(v_rc=0.0)

        # Step 10 seconds (10 time constants)
        for _ in range(10):
            state = update_thevenin_rc(state, i_cell_a=i_cell, dt_s=1.0, r1_ohm=r1, c1_farad=c1)

        expected_v_rc = i_cell * r1  # 0.20 V
        assert pytest.approx(state.v_rc, rel=1e-2) == expected_v_rc

    def test_ecm_step_pack_terminal_voltage_arithmetic(self):
        """Pack voltage must equal Ns * (Voc - Icell*R0 - Vrc) - Ipack * R_interconnect."""
        ns = 14
        np_ = 8
        i_pack = 40.0
        i_cell = i_pack / np_  # 5.0 A
        r0 = 0.020
        r_inter = 0.005
        rc = TheveninRCState(v_rc=0.05)

        res, new_rc = ecm_step(
            soc=0.80,
            i_pack_a=i_pack,
            dt_s=1.0,
            temp_c=25.0,
            ns=ns,
            np_=np_,
            nominal_capacity_ah=5.0,
            r0_ref_ohm=r0,
            r1_ohm=0.010,
            c1_farad=500.0,
            rc_state=rc,
            r_interconnect_ohm=r_inter,
            chemistry="NMC",
        )

        expected_ocv = get_ocv_v(0.80, chemistry="NMC")
        expected_v_cell = expected_ocv - (i_cell * r0) - 0.05
        expected_v_pack = (ns * expected_v_cell) - (i_pack * r_inter)

        assert pytest.approx(res.ocv_cell_v, rel=1e-3) == expected_ocv
        assert pytest.approx(res.v_term_cell_v, rel=1e-3) == expected_v_cell
        assert pytest.approx(res.v_pack_v, rel=1e-3) == expected_v_pack


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Model Validation Framework Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelValidationMetrics:
    def test_perfect_agreement_gives_zero_error_and_r2_one(self):
        """Identical predictions and observations must yield MAE=0, RMSE=0, R^2=1.0."""
        data = [3.6, 3.7, 3.8, 3.9, 4.0]
        m = compute_validation_metrics(data, data, units="V")
        assert m.mae == 0.0
        assert m.rmse == 0.0
        assert m.mbe == 0.0
        assert m.max_error == 0.0
        assert m.r_squared == 1.0
        assert m.n_samples == 5

    def test_known_error_vector(self):
        """Known residual vector must compute analytical statistical moments."""
        preds = [4.1, 4.2, 4.3]
        obs   = [4.0, 4.0, 4.0]  # residuals = [+0.1, +0.2, +0.3]
        m = compute_validation_metrics(preds, obs, units="V")
        assert pytest.approx(m.mae, rel=1e-4) == 0.20
        assert pytest.approx(m.mbe, rel=1e-4) == 0.20
        assert pytest.approx(m.max_error, rel=1e-4) == 0.30
        # rmse = sqrt((0.01 + 0.04 + 0.09) / 3) = sqrt(0.14 / 3) = 0.21602
        assert pytest.approx(m.rmse, rel=1e-3) == 0.216

    def test_mismatched_length_raises_value_error(self):
        with pytest.raises(ValueError):
            compute_validation_metrics([1.0, 2.0], [1.0])

    def test_benchmark_validation_identifies_synthetic_provenance(self):
        """Validation output must explicitly declare benchmark dataset type and disclaimer."""
        sim_ts = [
            {"t_s": 0.0, "voltage_v": 58.0, "soc": 1.0},
            {"t_s": 10.0, "voltage_v": 56.5, "soc": 0.95},
        ]
        rep = run_benchmark_validation(sim_ts, target_metric="voltage_v")
        assert rep["status"] == "BENCHMARK_EVALUATED"
        assert rep["is_physical_laboratory_data"] is False
        assert "Synthetic" in rep["dataset_type"]
        assert "disclaimer" in rep


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Monte Carlo Uncertainty Propagation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestUncertaintyPropagation:
    def test_reproducible_random_seed(self):
        """Identical random seeds must yield identical Monte Carlo percentile distributions."""
        class MockObj:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        cell = MockObj(nominal_capacity_ah=5.0, nominal_voltage_v=3.7, internal_resistance_ohm=0.020, mass_kg=0.070)
        cfg = MockObj(ns=14, np=8, interconnect_resistance_ohm=0.005)
        sc = MockObj(ambient_temp_c=25.0, discharge_current_a=40.0, duration_s=100.0)

        run1 = run_monte_carlo_uncertainty(cell, cfg, sc, n_iterations=30, random_seed=999)
        run2 = run_monte_carlo_uncertainty(cell, cfg, sc, n_iterations=30, random_seed=999)

        assert run1["distributions"]["nominal_energy_wh"]["p50"] == run2["distributions"]["nominal_energy_wh"]["p50"]
        assert run1["distributions"]["total_cell_mass_kg"]["p05"] == run2["distributions"]["total_cell_mass_kg"]["p05"]

    def test_percentile_ordering_p05_le_p50_le_p95(self):
        """P05 <= P50 <= P95 must hold strictly for all physical outcome variables."""
        class MockObj:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        cell = MockObj(nominal_capacity_ah=5.0, nominal_voltage_v=3.7, internal_resistance_ohm=0.020, mass_kg=0.070)
        cfg = MockObj(ns=14, np=8, interconnect_resistance_ohm=0.005)
        sc = MockObj(ambient_temp_c=25.0, discharge_current_a=40.0, duration_s=100.0)

        res = run_monte_carlo_uncertainty(cell, cfg, sc, n_iterations=40, random_seed=42)
        dist = res["distributions"]

        for var_name in ["nominal_energy_wh", "total_cell_mass_kg", "simulated_max_temp_c", "end_terminal_voltage_v"]:
            p05 = dist[var_name]["p05"]
            p50 = dist[var_name]["p50"]
            p95 = dist[var_name]["p95"]
            assert p05 <= p50 <= p95, f"{var_name} percentile order violated: {p05} <= {p50} <= {p95}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. API Endpoints: Voltage Output, Provenance, Validation & Uncertainty
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictiveSimulationAPI:
    def _create_and_run_simulation(self) -> int:
        p_res = client.post("/api/projects", json={"name": "Predictive Verification Project", "application": "electric_scooter"})
        assert p_res.status_code in (200, 201)
        pid = p_res.json()["id"]

        cells = client.get("/api/library/cells").json()
        assert len(cells) > 0
        cell_id = cells[0]["id"]

        scenarios = client.get("/api/scenarios").json()
        assert len(scenarios) > 0
        sc_id = scenarios[0]["id"]

        cfg_res = client.post(f"/api/projects/{pid}/configurations", json={
            "label": "14S8P-ECM",
            "ns": 14,
            "np": 8,
            "cell_spec_id": cell_id,
            "cooling_type": "passive",
        })
        assert cfg_res.status_code in (200, 201)
        cfg_id = cfg_res.json()["id"]

        sim_res = client.post(f"/api/configurations/{cfg_id}/simulate", json={
            "configuration_id": cfg_id,
            "scenario_id": sc_id,
            "run_label": "Predictive Verification Run",
        })
        assert sim_res.status_code == 202
        return sim_res.json()["simulation_id"]

    def test_simulation_populates_real_voltage_timeseries(self):
        """Voltage in timeseries must now be populated with realistic pack terminal voltage (not None)."""
        sim_id = self._create_and_run_simulation()
        r = client.get(f"/api/simulations/{sim_id}/results")
        assert r.status_code == 200
        data = r.json()
        ts = data["timeseries"]
        assert len(ts) > 0

        # Check voltage is a populated float between 30V (depleted under load) and 65V (fully charged)
        voltages = [pt["voltage_v"] for pt in ts if pt.get("voltage_v") is not None]
        assert len(voltages) == len(ts), "All timeseries points must have non-null voltage_v"
        assert all(30.0 <= v <= 65.0 for v in voltages), f"Pack voltages out of physical range: min={min(voltages)}, max={max(voltages)}"

    def test_get_simulation_provenance_endpoint(self):
        """GET /api/simulations/{id}/provenance returns catalog with confidence scoring."""
        sim_id = self._create_and_run_simulation()
        r = client.get(f"/api/simulations/{sim_id}/provenance")
        assert r.status_code == 200
        cat = r.json()
        assert "parameters" in cat
        assert "summary" in cat
        assert len(cat["parameters"]) > 0

    def test_get_simulation_validation_endpoint(self):
        """GET /api/simulations/{id}/validation computes MAE, RMSE, and returns benchmark status."""
        sim_id = self._create_and_run_simulation()
        r = client.get(f"/api/simulations/{sim_id}/validation")
        assert r.status_code == 200
        val = r.json()
        assert val["status"] == "BENCHMARK_EVALUATED"
        assert "metrics" in val
        assert "mae" in val["metrics"]
        assert "rmse" in val["metrics"]

    def test_post_simulation_uncertainty_endpoint(self):
        """POST /api/simulations/{id}/uncertainty runs Monte Carlo and returns distributions."""
        sim_id = self._create_and_run_simulation()
        r = client.post(f"/api/simulations/{sim_id}/uncertainty", json={"n_iterations": 25, "random_seed": 100})
        assert r.status_code == 200
        unc = r.json()
        assert "distributions" in unc
        assert "sensitivity_ranking" in unc
        assert "disclaimer" in unc
        assert "nominal_energy_wh" in unc["distributions"]

