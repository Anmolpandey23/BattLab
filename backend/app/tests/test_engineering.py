"""
BattLab — Unit tests for engineering calculation services.

Tests are self-contained and do not require a running database.
"""
import math
import pytest

from app.services.electrical import (
    ElectricalInputs, calculate_pack, soc_update, generate_current_profile,
)
from app.services.thermal import ThermalInputs, thermal_step, run_thermal_simulation
from app.services.constraints import (
    check_nominal_voltage, check_nominal_energy, check_cell_mass,
    check_continuous_current, check_temperature, Status,
)
from app.services.candidate_generator import generate_candidates


# ═══════════════════════════════════════════════════════════════════════════════
# Electrical Service Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPackCalculations:
    def _inputs(self, ns=14, np=8, v=3.7, ah=5.0, r=0.025, i=None) -> ElectricalInputs:
        return ElectricalInputs(
            ns=ns, np=np, v_cell_nominal=v, ah_cell=ah,
            r_cell_ohm=r, i_pack_a=i,
            v_cell_min=2.5, v_cell_max=4.2,
            usable_soc_window=0.80,
        )

    def test_nominal_voltage(self):
        pack = calculate_pack(self._inputs(ns=14, np=8, v=3.7))
        assert pack.nominal_voltage_v == pytest.approx(14 * 3.7)

    def test_pack_capacity(self):
        pack = calculate_pack(self._inputs(ns=14, np=8, ah=5.0))
        assert pack.capacity_ah == pytest.approx(8 * 5.0)

    def test_nominal_energy(self):
        pack = calculate_pack(self._inputs(ns=14, np=8, v=3.7, ah=5.0))
        expected_e = 14 * 3.7 * 8 * 5.0
        assert pack.nominal_energy_wh == pytest.approx(expected_e, rel=1e-4)

    def test_total_cells(self):
        pack = calculate_pack(self._inputs(ns=14, np=8))
        assert pack.total_cells == 112

    def test_pack_resistance(self):
        # R_pack = Ns * R_cell / Np  (no interconnect)
        ns, np_, r = 14, 8, 0.025
        pack = calculate_pack(self._inputs(ns=ns, np=np_, r=r))
        assert pack.r_pack_ohm == pytest.approx(ns * r / np_, rel=1e-5)

    def test_cell_current_equal_sharing(self):
        ns, np_, i_pack = 14, 8, 40.0
        pack = calculate_pack(self._inputs(ns=ns, np=np_, i=i_pack))
        assert pack.i_cell_a == pytest.approx(i_pack / np_, rel=1e-5)

    def test_resistive_heat_per_cell(self):
        ns, np_, r, i_pack = 14, 8, 0.025, 40.0
        pack = calculate_pack(self._inputs(ns=ns, np=np_, r=r, i=i_pack))
        i_cell = i_pack / np_
        expected_q = i_cell ** 2 * r
        assert pack.q_cell_w == pytest.approx(expected_q, rel=1e-4)

    def test_max_min_voltage(self):
        pack = calculate_pack(self._inputs(ns=14, np=8, v=3.7))
        assert pack.max_voltage_v == pytest.approx(14 * 4.2)
        assert pack.min_voltage_v == pytest.approx(14 * 2.5)

    def test_usable_energy(self):
        pack = calculate_pack(self._inputs(ns=14, np=8, v=3.7, ah=5.0))
        e_nom = 14 * 3.7 * 8 * 5.0
        assert pack.usable_energy_wh == pytest.approx(e_nom * 0.80, rel=1e-4)

    def test_invalid_ns_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(self._inputs(ns=0))

    def test_invalid_voltage_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(self._inputs(v=0.0))

    def test_no_resistance_gives_none(self):
        inputs = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inputs)
        assert pack.r_pack_ohm is None
        assert pack.p_loss_w is None

    def test_14s16p_demo_values(self):
        """Demo project: 14S16P at 3.7V/5Ah."""
        pack = calculate_pack(ElectricalInputs(
            ns=14, np=16, v_cell_nominal=3.7, ah_cell=5.0,
            r_cell_ohm=0.025, v_cell_min=2.5, v_cell_max=4.2,
            usable_soc_window=0.80,
        ))
        assert pack.nominal_voltage_v == pytest.approx(51.8, rel=1e-4)
        assert pack.capacity_ah == pytest.approx(80.0, rel=1e-4)
        assert pack.nominal_energy_wh == pytest.approx(4144.0, rel=1e-4)
        assert pack.total_cells == 224


class TestSOC:
    def test_discharge_reduces_soc(self):
        new_soc = soc_update(1.0, i_cell_a=5.0, dt_s=3600, ah_cell=5.0)
        assert new_soc == pytest.approx(0.0, abs=1e-6)  # 1C for 1 hour = 0 SOC

    def test_soc_clamped_at_zero(self):
        new_soc = soc_update(0.1, i_cell_a=10.0, dt_s=3600, ah_cell=5.0)
        assert new_soc == 0.0

    def test_soc_clamped_at_one(self):
        new_soc = soc_update(0.9, i_cell_a=-10.0, dt_s=3600, ah_cell=5.0)
        assert new_soc == 1.0  # clamped

    def test_zero_current_no_change(self):
        new_soc = soc_update(0.75, i_cell_a=0.0, dt_s=100, ah_cell=5.0)
        assert new_soc == pytest.approx(0.75)

    def test_invalid_dt_raises(self):
        with pytest.raises(ValueError):
            soc_update(1.0, 1.0, dt_s=-1, ah_cell=5.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Thermal Service Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestThermal:
    def test_no_cooling_temperature_rises(self):
        step = thermal_step(ThermalInputs(
            cell_mass_kg=1.0, cp_j_per_kg_k=900.0, ha_w_per_k=0.0,
            q_gen_w=10.0, t_current_c=25.0, t_ambient_c=25.0, dt_s=100.0,
        ))
        assert step.t_next_c > step.t_current_c

    def test_equilibrium_temperature(self):
        """T_eq = T_amb + Q/hA"""
        q, ha, t_amb = 20.0, 5.0, 25.0
        step = thermal_step(ThermalInputs(
            cell_mass_kg=5.0, cp_j_per_kg_k=900.0, ha_w_per_k=ha,
            q_gen_w=q, t_current_c=25.0, t_ambient_c=t_amb, dt_s=1e8,  # huge dt → equilibrium
        ))
        expected_eq = t_amb + q / ha
        assert step.t_next_c == pytest.approx(expected_eq, abs=0.1)

    def test_cooling_reduces_excess_temperature(self):
        """With cooling, a hot cell should cool toward ambient."""
        step = thermal_step(ThermalInputs(
            cell_mass_kg=1.0, cp_j_per_kg_k=900.0, ha_w_per_k=10.0,
            q_gen_w=0.0, t_current_c=50.0, t_ambient_c=25.0, dt_s=100.0,
        ))
        assert step.t_next_c < step.t_current_c

    def test_thermal_time_constant(self):
        """After tau = m*cp/hA, temperature excess should decay by 1/e."""
        m, cp, ha = 1.0, 900.0, 9.0   # tau = 100 s
        tau = m * cp / ha
        step = thermal_step(ThermalInputs(
            cell_mass_kg=m, cp_j_per_kg_k=cp, ha_w_per_k=ha,
            q_gen_w=0.0, t_current_c=50.0, t_ambient_c=25.0, dt_s=tau,
        ))
        excess_initial = 50.0 - 25.0
        excess_after = step.t_next_c - 25.0
        assert excess_after == pytest.approx(excess_initial / math.e, rel=1e-3)

    def test_simulation_produces_correct_length(self):
        times = list(range(0, 101, 10))  # 11 points
        q_gens = [10.0] * 10
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_gens,
            t_ambient_c=25.0, t_initial_c=25.0,
            cell_mass_kg=1.0, cp_j_per_kg_k=900.0, ha_w_per_k=5.0,
        )
        assert len(result.temperatures_c) == len(times)

    def test_temperature_limit_warning(self):
        times = list(range(0, 3601, 10))
        q_gens = [50.0] * (len(times) - 1)  # large heat gen
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_gens,
            t_ambient_c=25.0, t_initial_c=25.0,
            cell_mass_kg=0.07, cp_j_per_kg_k=900.0, ha_w_per_k=0.5,
            t_max_limit_c=45.0,
        )
        assert any("exceeds configured cell limit" in w for w in result.warnings)


# ═══════════════════════════════════════════════════════════════════════════════
# Constraint Engine Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstraints:
    def test_voltage_pass(self):
        result = check_nominal_voltage(51.8, 51.8)
        assert result.status == Status.pass_

    def test_voltage_fail(self):
        result = check_nominal_voltage(40.0, 51.8)
        assert result.status == Status.fail

    def test_voltage_missing_returns_unverified(self):
        result = check_nominal_voltage(None, 51.8)
        assert result.status == Status.unverf

    def test_energy_pass(self):
        result = check_nominal_energy(4200.0, 4000.0)
        assert result.status == Status.pass_

    def test_energy_fail(self):
        result = check_nominal_energy(2000.0, 4000.0)
        assert result.status == Status.fail

    def test_mass_missing_cell_mass_unverified(self):
        result = check_cell_mass(224, None, 25.0)
        assert result.status == Status.unverf

    def test_mass_pass(self):
        result = check_cell_mass(224, 0.07, 25.0)
        # 224 × 0.07 = 15.68 kg < 25 kg → pass
        assert result.status in (Status.pass_, Status.warn)

    def test_mass_fail(self):
        result = check_cell_mass(224, 0.15, 25.0)
        # 224 × 0.15 = 33.6 kg > 25 kg → fail
        assert result.status == Status.fail

    def test_current_no_rating_unverified(self):
        result = check_continuous_current(i_pack_a=40.0, np=8, cell_max_cont_a=None)
        assert result.status == Status.unverf

    def test_temperature_pass(self):
        result = check_temperature(max_modelled_temp_c=40.0, cell_max_op_temp_c=60.0)
        assert result.status in (Status.pass_, Status.warn)

    def test_temperature_fail(self):
        result = check_temperature(max_modelled_temp_c=75.0, cell_max_op_temp_c=60.0)
        assert result.status == Status.fail

    def test_temperature_missing_limit(self):
        result = check_temperature(max_modelled_temp_c=45.0, cell_max_op_temp_c=None)
        assert result.status == Status.unverf


# ═══════════════════════════════════════════════════════════════════════════════
# Candidate Generator Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCandidateGenerator:
    def test_generates_candidates(self):
        candidates = generate_candidates(
            target_voltage_v=51.8,
            target_energy_wh=4000.0,
            energy_is_usable=False,
            v_cell_nominal=3.7,
            ah_cell=5.0,
            v_cell_min=2.5,
            v_cell_max=4.2,
            r_cell_ohm=0.025,
            cell_mass_kg=None,
            unit_cost_usd=None,
            max_continuous_cell_a=None,
            max_mass_kg=None,
            max_cost_usd=None,
            continuous_pack_a=None,
        )
        assert len(candidates) > 0

    def test_14s_included(self):
        """14S at 3.7V = 51.8V which matches target exactly."""
        candidates = generate_candidates(
            target_voltage_v=51.8,
            target_energy_wh=4000.0,
            energy_is_usable=False,
            v_cell_nominal=3.7,
            ah_cell=5.0,
            v_cell_min=2.5,
            v_cell_max=4.2,
            r_cell_ohm=0.025,
            cell_mass_kg=None, unit_cost_usd=None,
            max_continuous_cell_a=None, max_mass_kg=None,
            max_cost_usd=None, continuous_pack_a=None,
        )
        ns_values = [c.ns for c in candidates]
        assert 14 in ns_values

    def test_mass_constraint_eliminates_heavy(self):
        """With a very low mass limit and known cell mass, heavier configs should be infeasible."""
        candidates = generate_candidates(
            target_voltage_v=51.8,
            target_energy_wh=4000.0,
            energy_is_usable=False,
            v_cell_nominal=3.7,
            ah_cell=5.0,
            v_cell_min=2.5,
            v_cell_max=4.2,
            r_cell_ohm=0.025,
            cell_mass_kg=0.10,      # 100 g per cell
            unit_cost_usd=None,
            max_continuous_cell_a=None,
            max_mass_kg=5.0,        # very tight → most configs infeasible
            max_cost_usd=None,
            continuous_pack_a=None,
        )
        feasible = [c for c in candidates if c.status == "feasible"]
        # Most 14S × Np configurations with 100g cell and mass limit 5 kg
        # would require Np <= 5/14*0.1 ~= 3.6 i.e. Np <= 3
        # Very few feasible; all feasible should have small total cells
        for c in feasible:
            assert c.estimated_cell_mass_kg <= 5.0

    def test_energy_arithmetic(self):
        """Nominal energy = Ns × Np × V_cell × Ah_cell."""
        candidates = generate_candidates(
            target_voltage_v=51.8,
            target_energy_wh=4000.0,
            energy_is_usable=False,
            v_cell_nominal=3.7,
            ah_cell=5.0,
            v_cell_min=None, v_cell_max=None,
            r_cell_ohm=None, cell_mass_kg=None,
            unit_cost_usd=None, max_continuous_cell_a=None,
            max_mass_kg=None, max_cost_usd=None, continuous_pack_a=None,
        )
        for c in candidates:
            expected = c.ns * c.np * 3.7 * 5.0
            assert c.nominal_energy_wh == pytest.approx(expected, rel=1e-3)
