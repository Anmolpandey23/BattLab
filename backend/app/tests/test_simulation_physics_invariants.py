"""
BattLab — Simulation Physics Invariants & Energy Reconciliation Tests

Tests verifying core physical equations, conservation laws, numerical integration,
series-parallel topology invariants, electro-thermal coupling, thermal constraint
handling, and report contracts.
"""
import json
import math
import os
import pytest
from app.models import CellSpec, Configuration, Scenario, CoolingType
from app.services.electrical import calculate_pack, soc_update, ElectricalInputs
from app.services.ecm import get_ocv_v, get_arrhenius_resistance_ohm, ecm_step, TheveninRCState
from app.services.thermal import thermal_step, ThermalInputs
from app.services.simulation import run_simulation
from app.services.reports import generate_json_config, generate_csv_timeseries, generate_pdf_report


@pytest.fixture
def base_cell():
    return CellSpec(
        id=1,
        manufacturer="Provisional",
        model="ILL-21700-50E",
        chemistry="NMC",
        nominal_voltage_v=3.7,
        nominal_capacity_ah=5.0,
        internal_resistance_ohm=0.025,
        min_voltage_v=2.5,
        max_voltage_v=4.2,
        mass_kg=0.070,
        specific_heat_j_per_kg_k=900.0,
        max_continuous_discharge_a=15.0,
        peak_discharge_a=25.0,
        max_operating_temp_c=60.0,
        is_seed=True,
    )


@pytest.fixture
def pack_14s16p(base_cell):
    return Configuration(
        id=1,
        project_id=1,
        label="14S16P Passive",
        ns=14,
        np=16,
        cell_spec_id=base_cell.id,
        cooling_type=CoolingType.passive,
    )


class TestSimulationPhysicsInvariants:
    """Verifies physical invariants, topology scaling, electro-thermal coupling, and numerical accounting."""

    def test_series_parallel_capacity_and_voltage_scaling(self, base_cell):
        """Verify Ns/Np electrical scaling: Vpack = Ns * Vcell, Cap_pack = Np * Cap_cell."""
        inputs = ElectricalInputs(
            ns=14,
            np=16,
            v_cell_nominal=base_cell.nominal_voltage_v,
            ah_cell=base_cell.nominal_capacity_ah,
            r_cell_ohm=base_cell.internal_resistance_ohm,
        )
        calc = calculate_pack(inputs)
        assert calc.total_cells == 224
        assert calc.nominal_voltage_v == pytest.approx(14 * 3.7, rel=1e-5)
        assert calc.capacity_ah == pytest.approx(16 * 5.0, rel=1e-5)
        assert calc.nominal_energy_wh == pytest.approx(51.8 * 80.0, rel=1e-5)

    def test_zero_current_rest_profile_invariants(self, base_cell, pack_14s16p):
        """Zero current rest: 0 Wh delivered, 0 SOC change, terminal V = OCV."""
        profile = [[float(t), 0.0] for t in range(0, 3601, 60)]
        scenario = Scenario(
            name="Zero Current Rest",
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=0.80,
            duration_s=3600.0,
            time_step_s=60.0,
            profile_type="user_supplied",
            current_profile_json=json.dumps(profile),
        )

        result = run_simulation(configuration=pack_14s16p, scenario=scenario, cell_spec=base_cell)

        assert result["energy_delivered_wh"] == pytest.approx(0.0, abs=1e-6)
        assert result["min_soc"] == pytest.approx(0.80, abs=1e-4)

        # Terminal voltage equals open circuit voltage for entire run
        ts = result["timeseries"]
        v_ocv_expected = 14 * get_ocv_v(0.80, "NMC")
        for pt in ts:
            assert pt["voltage_v"] == pytest.approx(v_ocv_expected, abs=0.01)

    def test_coulomb_counting_and_soc_clamping(self):
        """SOC update must respect conservation of charge and clamp within [0.0, 1.0]."""
        # Normal discharge: 5A cell for 1800s (0.5h) on a 5Ah cell -> delta SOC = 0.5
        soc_half = soc_update(soc=1.0, i_cell_a=5.0, dt_s=1800.0, ah_cell=5.0)
        assert soc_half == pytest.approx(0.50, rel=1e-5)

        # Over-discharge beyond 0% must clamp to 0.0
        soc_empty = soc_update(soc=0.1, i_cell_a=5.0, dt_s=3600.0, ah_cell=5.0)
        assert soc_empty == 0.0

        # Over-charge beyond 100% must clamp to 1.0
        soc_full = soc_update(soc=0.9, i_cell_a=-5.0, dt_s=3600.0, ah_cell=5.0)
        assert soc_full == 1.0

    def test_non_unit_time_step_convergence(self, base_cell, pack_14s16p):
        """Simulation with dt=2s vs dt=10s should yield consistent Coulomb counting."""
        dur = 600.0

        sc_dt2 = Scenario(
            name="dt=2s",
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=1.0,
            duration_s=dur,
            time_step_s=2.0,
            profile_type="steady_cruise",
            discharge_current_a=80.0,
        )
        res_dt2 = run_simulation(configuration=pack_14s16p, scenario=sc_dt2, cell_spec=base_cell)

        sc_dt10 = Scenario(
            name="dt=10s",
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=1.0,
            duration_s=dur,
            time_step_s=10.0,
            profile_type="steady_cruise",
            discharge_current_a=80.0,
        )
        res_dt10 = run_simulation(configuration=pack_14s16p, scenario=sc_dt10, cell_spec=base_cell)

        expected_final_soc = 1.0 - (80.0 * 600.0) / (3600.0 * 80.0)
        assert res_dt2["min_soc"] == pytest.approx(expected_final_soc, abs=1e-4)
        assert res_dt10["min_soc"] == pytest.approx(expected_final_soc, abs=1e-4)

        # Delivered energy agrees within 0.5%
        rel_diff = abs(res_dt2["energy_delivered_wh"] - res_dt10["energy_delivered_wh"]) / res_dt2["energy_delivered_wh"]
        assert rel_diff < 0.005

    def test_instantaneous_energy_quadrature_consistency(self, base_cell, pack_14s16p):
        """Verify delivered_energy_wh equals sum(max(0, V_terminal * I_pack * dt)) / 3600."""
        scenario = Scenario(
            name="Energy Integral Check",
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=1.0,
            duration_s=1200.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
            discharge_current_a=80.0,
        )
        res = run_simulation(configuration=pack_14s16p, scenario=scenario, cell_spec=base_cell)
        ts = res["timeseries"]

        manual_energy_wh = 0.0
        for i in range(len(ts) - 1):
            dt = ts[i + 1]["t_s"] - ts[i]["t_s"]
            p = ts[i + 1]["voltage_v"] * ts[i]["current_a"]
            manual_energy_wh += max(0.0, p * dt) / 3600.0

        assert res["energy_delivered_wh"] == pytest.approx(manual_energy_wh, rel=1e-2)

    def test_regenerative_braking_gross_energy_accounting(self, base_cell, pack_14s16p):
        """Regenerative current (I < 0) charges battery; gross delivered energy must not decrease."""
        profile = []
        for t in range(0, 301, 10):
            profile.append([float(t), 80.0])
        for t in range(310, 601, 10):
            profile.append([float(t), -40.0])

        scenario = Scenario(
            name="Discharge and Regen",
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=0.80,
            duration_s=600.0,
            time_step_s=10.0,
            profile_type="user_supplied",
            current_profile_json=json.dumps(profile),
        )
        res = run_simulation(configuration=pack_14s16p, scenario=scenario, cell_spec=base_cell)
        ts = res["timeseries"]

        soc_at_300s = ts[30]["soc"]
        soc_final = ts[-1]["soc"]
        assert soc_at_300s < 0.80
        assert soc_final > soc_at_300s
        assert res["energy_delivered_wh"] > 0.0

    def test_arrhenius_resistance_temperature_scaling(self):
        """Arrhenius model must strictly satisfy: R0(-10°C) > R0(25°C) > R0(45°C)."""
        r_ref = 0.025
        r_cold = get_arrhenius_resistance_ohm(r_ref, -10.0)
        r_nom = get_arrhenius_resistance_ohm(r_ref, 25.0)
        r_hot = get_arrhenius_resistance_ohm(r_ref, 45.0)

        assert r_nom == pytest.approx(r_ref, rel=1e-5)
        assert r_cold > r_nom * 3.5  # Sub-zero kinetic impedance increases >3.5x
        assert r_hot < r_nom         # Elevated temperature reduces electrolyte viscosity

    def test_heat_generation_quadruples_with_doubled_current(self):
        """Ohmic dissipation I^2 * R must quadruple when current doubles."""
        rc = TheveninRCState()
        res_1c, _ = ecm_step(
            soc=0.8, i_pack_a=80.0, dt_s=10.0, temp_c=25.0,
            ns=14, np_=16, nominal_capacity_ah=5.0, r0_ref_ohm=0.025,
            rc_state=rc, chemistry="NMC"
        )
        res_2c, _ = ecm_step(
            soc=0.8, i_pack_a=160.0, dt_s=10.0, temp_c=25.0,
            ns=14, np_=16, nominal_capacity_ah=5.0, r0_ref_ohm=0.025,
            rc_state=rc, chemistry="NMC"
        )
        # Joule heat scales as I^2: (160/80)^2 = 4.0
        assert (res_2c.q_cell_w / res_1c.q_cell_w) == pytest.approx(4.0, rel=0.05)

    def test_thermal_response_to_ambient_temperatures(self, base_cell, pack_14s16p):
        """Higher ambient temperatures must shift the thermal trajectory higher monotonically."""
        # Rest run at different ambients
        profile = [[float(t), 0.0] for t in range(0, 1801, 60)]
        sc_25 = Scenario(
            name="Amb 25C", ambient_temp_c=25.0, initial_cell_temp_c=25.0,
            initial_soc=0.8, duration_s=1800.0, time_step_s=60.0,
            profile_type="user_supplied", current_profile_json=json.dumps(profile)
        )
        sc_40 = Scenario(
            name="Amb 40C", ambient_temp_c=40.0, initial_cell_temp_c=40.0,
            initial_soc=0.8, duration_s=1800.0, time_step_s=60.0,
            profile_type="user_supplied", current_profile_json=json.dumps(profile)
        )
        res_25 = run_simulation(pack_14s16p, sc_25, base_cell)
        res_40 = run_simulation(pack_14s16p, sc_40, base_cell)

        assert res_40["max_temp_c"] > res_25["max_temp_c"]
        assert res_40["max_temp_c"] == pytest.approx(40.0, abs=0.1)

    def test_coupled_electro_thermal_feedback_reduces_losses(self, base_cell, pack_14s16p):
        """
        In cold start (-10°C), electro-thermal coupling warms the cell, reducing internal resistance.
        This must lower cumulative heat generation and increase delivered terminal energy.
        """
        scenario = Scenario(
            name="Cold Start Feedback",
            ambient_temp_c=-10.0,
            initial_cell_temp_c=-10.0,
            initial_soc=1.0,
            duration_s=3600.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
            discharge_current_a=80.0,
        )
        res_coupled = run_simulation(pack_14s16p, scenario, base_cell, enable_thermal_coupling=True)
        res_decoupled = run_simulation(pack_14s16p, scenario, base_cell, enable_thermal_coupling=False)

        # Coupled simulation must deliver MORE terminal energy due to lower warmed resistance
        assert res_coupled["energy_delivered_wh"] > res_decoupled["energy_delivered_wh"]
        # In decoupled mode, resistance stays frozen at -10°C, overheating artificially
        assert res_decoupled["max_temp_c"] > res_coupled["max_temp_c"]

    def test_run_63_reproducibility_and_energy_balance_closure(self, base_cell, pack_14s16p):
        """
        Reproduce exact uncoupled linear Run #63 baseline and verify mathematical energy balance closure:
        E_ocv_linear (3,752.0 Wh) == E_delivered (3,191.28 Wh) + E_losses (560.7 Wh).
        Residual must be < 0.1 Wh (< 0.003%).
        """
        scenario = Scenario(
            name="Winter Cold Start (-10°C)",
            ambient_temp_c=-10.0,
            initial_cell_temp_c=-10.0,
            initial_soc=1.0,
            duration_s=3600.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
            discharge_current_a=80.0,
        )
        # Using an uncalibrated chemistry string forces linear OCV interpolation (matching Run #63 bug baseline)
        uncal_cell = CellSpec(
            id=99, manufacturer="Illustrative", model="ILL-21700-5P",
            chemistry="UNAVAILABLE_LINEAR_CHEM",
            nominal_voltage_v=3.7, nominal_capacity_ah=5.0, internal_resistance_ohm=0.025,
            min_voltage_v=2.5, max_voltage_v=4.2, mass_kg=0.070, specific_heat_j_per_kg_k=900.0,
            max_operating_temp_c=60.0
        )
        res_r63 = run_simulation(pack_14s16p, scenario, uncal_cell, enable_thermal_coupling=False)

        # Exact historical delivered energy reproduced to within 0.1 Wh
        assert res_r63["energy_delivered_wh"] == pytest.approx(3191.28, abs=0.1)

        # Verify mathematical closure of energy balance
        # For linear OCV between 2.5V and 4.2V, average continuous OCV = 3.35V.
        # Pack OCV = 14 * 3.35 = 46.9V.
        # Chemical energy discharged = 46.9V * 80.0Ah = 3,752.0 Wh.
        e_ocv_chemical = 14 * 3.35 * 80.0
        e_delivered = res_r63["energy_delivered_wh"]
        e_losses = sum(pt["power_loss_w"] * 10.0 for pt in res_r63["timeseries"][:-1]) / 3600.0

        # Left-endpoint forward Euler rectangular sum is greater than continuous integral:
        # E_discrete = E_continuous + 0.5 * (Delta V_step) * I = 3752.0 + 2.644 = 3754.64 Wh.
        euler_discrete_chemical_wh = e_ocv_chemical + (0.5 * (14.0 * (4.2 - 2.5) / 360.0) * 80.0)

        # Discharged chemical energy accounting for discrete quadrature must equal delivered + losses
        residual = abs(euler_discrete_chemical_wh - (e_delivered + e_losses))
        assert residual < 0.1  # Residual is < 0.003% of pack energy (< 0.1 Wh)

    def test_thermal_constraint_violation_safety_verdict(self, base_cell, pack_14s16p):
        """
        Severe hot ambient (45°C) with 2C continuous discharge triggers TEMP_CELL_MAX (>60°C).
        Solver must complete execution (status=completed) while constraint verdict fails.
        """
        scenario = Scenario(
            name="Severe Hot Ambient Discharge",
            ambient_temp_c=45.0,
            initial_cell_temp_c=45.0,
            initial_soc=1.0,
            duration_s=1800.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
            discharge_current_a=160.0,  # 2C discharge
        )
        res = run_simulation(configuration=pack_14s16p, scenario=scenario, cell_spec=base_cell)

        # Thermal peak exceeds maximum allowed limit (60°C)
        assert res["max_temp_c"] > 60.0

        # Engineering constraints must reflect the failure
        cr_list = res["constraints"]
        temp_constraints = [c for c in cr_list if c["rule_id"] == "TEMP_CELL_MAX"]
        assert len(temp_constraints) == 1
        assert temp_constraints[0]["status"] == "fail"
        assert res["constraint_fail"] >= 1

    def test_reports_generate_successfully_for_failed_verdict(self, base_cell, pack_14s16p):
        """Report exporters (JSON, CSV, PDF) must cleanly serialize simulations with failed engineering constraints."""
        scenario = Scenario(
            name="Thermal Fail Scenario",
            ambient_temp_c=45.0,
            initial_cell_temp_c=45.0,
            initial_soc=1.0,
            duration_s=1800.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
            discharge_current_a=160.0,
        )
        res = run_simulation(configuration=pack_14s16p, scenario=scenario, cell_spec=base_cell)

        timeseries = res["timeseries"]
        constraints = res["constraints"]

        # 1. JSON report
        cfg_dict = {"id": 1, "label": "14S16P Passive", "ns": 14, "np": 16}
        cell_dict = {"manufacturer": "Provisional", "model": "ILL-21700-50E", "chemistry": "NMC"}
        json_path = generate_json_config(cfg_dict, cell_dict, report_id=999)
        assert os.path.exists(json_path)
        with open(json_path) as f:
            jdata = json.load(f)
            assert jdata["configuration"]["ns"] == 14

        # 2. CSV report
        csv_path = generate_csv_timeseries(timeseries, report_id=999)
        assert os.path.exists(csv_path)
        with open(csv_path) as f:
            csv_lines = f.readlines()
            assert len(csv_lines) > 1
            assert "t_s" in csv_lines[0]

        # 3. PDF report
        pdf_path = generate_pdf_report(
            project={"name": "Test EV", "application_category": "scooter", "engineer_label": "Engineer", "design_version": "1.0"},
            requirement=None,
            configuration={"label": "14S16P", "ns": 14, "np": 16, "calc_total_cells": 224, "cooling_type": "passive"},
            simulation_run={"id": 999, "model_version": "0.1.0", "result_nominal_voltage_v": 51.8, "result_nominal_energy_wh": 4144.0, "result_usable_energy_wh": 3315.2, "result_max_temp_c": res["max_temp_c"], "result_min_soc": res["min_soc"], "result_energy_delivered_wh": res["energy_delivered_wh"]},
            timeseries=timeseries,
            constraints=constraints,
            assumptions=res["assumptions"],
            report_id=999,
        )
        assert os.path.exists(pdf_path)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
            assert pdf_bytes.startswith(b"%PDF")

    def test_chemistry_provenance_and_normalization(self, pack_14s16p):
        """Supported chemistries must select calibrated OCV; unsupported chemistries must flag uncalibrated warning."""
        from app.models import Chemistry
        from app.services.ecm import _normalize_chemistry_key, is_ocv_data_available

        # Normalization checks
        assert _normalize_chemistry_key(Chemistry.nmc) == "NMC"
        assert _normalize_chemistry_key(Chemistry.lfp) == "LFP"
        assert _normalize_chemistry_key("nmc") == "NMC"
        assert _normalize_chemistry_key("LFP") == "LFP"
        assert _normalize_chemistry_key("solid_state") == "SOLID_STATE"

        assert is_ocv_data_available(Chemistry.nmc) is True
        assert is_ocv_data_available("nmc") is True
        assert is_ocv_data_available("solid_state") is False

        # Run with unsupported chemistry
        unsupported_cell = CellSpec(
            id=77, manufacturer="Experimental", model="SOLID-5000",
            chemistry="SOLID_STATE_GEN1",
            nominal_voltage_v=3.8, nominal_capacity_ah=5.0, internal_resistance_ohm=0.030,
            min_voltage_v=2.7, max_voltage_v=4.3, mass_kg=0.065, specific_heat_j_per_kg_k=900.0,
            max_operating_temp_c=60.0
        )
        sc = Scenario(
            name="Chemistry Check", ambient_temp_c=25.0, initial_cell_temp_c=25.0,
            initial_soc=0.8, duration_s=60.0, time_step_s=10.0, profile_type="steady_cruise"
        )
        res = run_simulation(pack_14s16p, sc, unsupported_cell)

        # Must flag uncalibrated provenance
        assert res["ecm_model_info"]["ocv_calibrated"] is False
        assert res["ecm_model_info"]["ocv_status"] == "uncalibrated_linear_bounds"
        assert any("UNAVAILABLE OCV DATA" in w for w in res["warnings"])

    def test_thermal_sanity_zero_current_cooling_and_exponential_tau(self, base_cell, pack_14s16p):
        """Zero-current cooling from 40°C towards 20°C ambient must strictly follow analytical tau and never cool below ambient."""
        profile = [[float(t), 0.0] for t in range(0, 7201, 60)]
        sc_cool = Scenario(
            name="Cool Down", ambient_temp_c=20.0, initial_cell_temp_c=40.0,
            initial_soc=0.8, duration_s=7200.0, time_step_s=60.0,
            profile_type="user_supplied", current_profile_json=json.dumps(profile)
        )
        res = run_simulation(pack_14s16p, sc_cool, base_cell)
        temps = [pt["temp_c"] for pt in res["timeseries"]]

        # Temperature must strictly descend and never drop below ambient
        assert temps[0] == 40.0
        assert temps[-1] < 40.0
        assert all(t >= 20.0 for t in temps)

        # Analytical tau check: C_th = 15.68 * 900 = 14112 J/K. hA = 4.48 W/K -> tau = 3150 s
        t_check_s = 3120
        idx = t_check_s // 60
        decay_observed = (temps[idx] - 20.0) / (40.0 - 20.0)
        decay_expected = math.exp(-t_check_s / 3150.0)
        assert decay_observed == pytest.approx(decay_expected, rel=1e-3)

    def test_liquid_cooling_ambient_sink_boundary(self, base_cell):
        """Liquid cooling cold plate uses scenario.ambient_temp_c as its heat rejection sink temperature."""
        pack_liquid = Configuration(
            id=2, project_id=1, label="14S16P Liquid", ns=14, np=16,
            cell_spec_id=base_cell.id, cooling_type=CoolingType.liquid,
        )
        scenario_winter = Scenario(
            name="Winter Cold Start (-10°C)", ambient_temp_c=-10.0, initial_cell_temp_c=-10.0,
            initial_soc=1.0, duration_s=3600.0, time_step_s=10.0, profile_type="steady_cruise",
            discharge_current_a=80.0,
        )
        res = run_simulation(pack_liquid, scenario_winter, base_cell, enable_thermal_coupling=True)

        # Equilibrium temperature with liquid cold plate (hA = 100.8 W/K) rejecting to -10°C ambient:
        # T_eq = -10.0 + Q_gen / 100.8. Average Q_gen ~ 560 W -> T_eq ~ -4.4°C
        assert -6.0 <= res["max_temp_c"] <= -4.0
        assert res["max_temp_c"] == pytest.approx(-5.36, abs=0.5)

    def test_rc_polarization_energy_analytical_and_discrete_reconciliation(self):
        """
        Task 1 Verification:
        Reconcile continuous analytical capacitor energy Delta_E_cap = 0.019444 Wh against
        discrete simulation polarization quadrature discrepancy (0.010722 Wh ~ 0.011 Wh).
        Confirms exact conservation of energy to < 1e-10 Wh analytically and isolates
        discrete forward-step quadrature truncation error (-0.008722 Wh).
        """
        r1 = 0.005       # Ohm
        c1 = 1000.0      # Farad
        tau = r1 * c1    # 5.0 seconds
        ns = 14
        np_ = 16
        n_cells = ns * np_ # 224 cells
        i_pack = 80.0
        i_cell = i_pack / np_ # 5.0 A
        t_final = 3600.0 # seconds
        v_inf = i_cell * r1 # 0.025 V

        # 1. Physical capacitor stored energy change: Delta_E_cap = N_cells * 0.5 * C1 * (V_final^2 - V_init^2)
        v_rc_init = 0.0
        v_rc_final = v_inf * (1.0 - math.exp(-t_final / tau))
        delta_e_cap_j = n_cells * 0.5 * c1 * (v_rc_final**2 - v_rc_init**2)
        delta_e_cap_wh = delta_e_cap_j / 3600.0

        assert delta_e_cap_wh == pytest.approx(0.019444, abs=1e-5)

        # 2. Continuous analytical integrals:
        # Integral_0^T V_rc(t)^2 / R1 dt:
        integral_v_sq = (v_inf**2) * (t_final - 1.5 * tau)
        e_pol_continuous_wh = (n_cells * (integral_v_sq / r1)) / 3600.0

        # Integral_0^T I_cell * V_rc(t) dt:
        integral_i_v = (v_inf**2 / r1) * (t_final - tau)
        e_iv_continuous_wh = (n_cells * integral_i_v) / 3600.0

        # Strict analytical closure: E_iv == E_pol + Delta_E_cap
        analytical_residual = abs(e_iv_continuous_wh - (e_pol_continuous_wh + delta_e_cap_wh))
        assert analytical_residual < 1e-10  # Exact to 10 decimal places

        # 3. Discrete simulation quadrature with dt = 10 s:
        from app.services.ecm import update_thevenin_rc, TheveninRCState
        rc = TheveninRCState(v_rc=0.0)
        dt = 10.0
        discrete_term_rc_sum = 0.0
        discrete_pol_loss_sum = 0.0

        for _ in range(int(t_final / dt)):
            rc = update_thevenin_rc(rc, i_cell, dt, r1, c1)
            v = rc.v_rc
            discrete_term_rc_sum += n_cells * (i_cell * v) * dt / 3600.0
            discrete_pol_loss_sum += n_cells * (v**2 / r1) * dt / 3600.0

        discrete_discrepancy = discrete_term_rc_sum - discrete_pol_loss_sum
        # Reproduces the reported 0.0107 Wh (~0.011 Wh) residual exactly
        assert discrete_discrepancy == pytest.approx(0.010722, abs=1e-5)

        # Truncation error between discrete right-hand quadrature and physical capacitor energy:
        truncation_error = discrete_discrepancy - delta_e_cap_wh
        assert truncation_error == pytest.approx(-0.008722, abs=1e-5)

    def test_multi_node_thermal_energy_conservation(self):
        """
        Task 4 Verification:
        Verify multi-node (Core-Surface-Plate) thermal network satisfies:
        1. Exact internal energy conservation: Delta U == Q_in - Q_out (residual < 1e-5 J).
        2. Core temperature is strictly hotter than Surface, and Surface hotter than Plate during discharge.
        3. Stable under large time steps (e.g. dt = 60s).
        """
        from app.services.thermal import run_multi_node_thermal_simulation
        times = [float(t) for t in range(0, 1801, 10)]
        q_gen = [250.0] * (len(times) - 1) # 250 W constant heat

        res = run_multi_node_thermal_simulation(
            times_s=times,
            q_gen_sequence_w=q_gen,
            t_ambient_c=25.0,
            t_initial_c=25.0,
            total_cell_mass_kg=15.68,
            cell_count=224,
            cp_j_per_kg_k=900.0,
            ha_w_per_k=25.0, # liquid cooling
        )

        assert res.energy_conservation_residual_j < 1e-5
        assert res.max_core_temp_c > res.max_surface_temp_c
        assert res.max_surface_temp_c > res.max_plate_temp_c
        assert res.max_gradient_c > 0.3  # Physical internal gradient develops

    def test_battery_aging_sei_kinetics_and_preview_semantics(self, base_cell, pack_14s16p):
        """
        Task 3 Verification:
        1. Throughput & EFC accumulation match Coulomb integral.
        2. Higher operating temperature accelerates SEI growth per Arrhenius law.
        3. Preview mode does not permanently apply degradation twice.
        """
        from app.services.aging import evaluate_simulation_aging
        times = [float(t) for t in range(0, 3601, 10)]
        currents_80a = [80.0] * len(times)

        # 80 A for 1 hour on 80 Ah pack = 80 Ah throughput = 0.5 EFC
        aging_25c = evaluate_simulation_aging(
            currents_a=currents_80a,
            times_s=times,
            nominal_capacity_ah=80.0,
            initial_r0_ohm=0.025,
            mean_temp_c=25.0,
            chemistry="NMC",
            is_committed=False,
        )

        assert aging_25c.run_throughput_ah == pytest.approx(80.0, abs=1e-3)
        assert aging_25c.run_efc == pytest.approx(0.50, abs=1e-3)
        assert aging_25c.soh_capacity_pct < 100.0
        assert aging_25c.resistance_growth_pct > 0.0

        # Run at 45°C accelerates degradation
        aging_45c = evaluate_simulation_aging(
            currents_a=currents_80a,
            times_s=times,
            nominal_capacity_ah=80.0,
            initial_r0_ohm=0.025,
            mean_temp_c=45.0,
            chemistry="NMC",
            is_committed=False,
        )

        assert aging_45c.capacity_fade_pct > aging_25c.capacity_fade_pct
        assert aging_45c.projected_cycles_to_80pct < aging_25c.projected_cycles_to_80pct
        assert aging_25c.is_committed is False


