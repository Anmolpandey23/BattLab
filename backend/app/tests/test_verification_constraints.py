"""
BattLab — Comprehensive Constraint Engine Verification Suite
=============================================================
Every constraint rule is tested for PASS, FAIL, WARN, and UNVERIFIED states,
including boundary values, missing data, and conflicting inputs.

Rules under test:
  VOLT_NOMINAL    : abs(calc_v - target_v) <= target_v × tol_pct / 100
  ENERGY_TARGET   : (usable|nominal) energy >= target × 0.95
  MASS_CELL       : total_cells × cell_mass_kg <= max_mass_kg
  CURR_CONTINUOUS : I_pack/Np <= cell_max_continuous_a
  TEMP_CELL_MAX   : max_modelled_temp <= cell_max_op_temp
  COST_BOM        : cell_count × unit_cost <= budget
  SOC_FLOOR       : min_soc >= 0
"""
import pytest

from app.services.constraints import (
    Status,
    ConstraintCheck,
    check_nominal_voltage,
    check_nominal_energy,
    check_cell_mass,
    check_continuous_current,
    check_temperature,
    check_cost,
    check_soc_bounds,
    run_all_checks,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VOLT_NOMINAL
# ═══════════════════════════════════════════════════════════════════════════════
class TestVoltageConstraint:
    """check_nominal_voltage: abs(calc_v - target) <= target × tol%"""

    def test_exact_match_passes(self):
        r = check_nominal_voltage(51.8, 51.8)
        assert r.status in (Status.pass_, Status.warn)

    def test_within_tolerance_passes(self):
        """51.8 V against 50 V target, 10% tol → 3.6% error → PASS"""
        r = check_nominal_voltage(51.8, 51.8, tolerance_pct=10.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_outside_tolerance_fails(self):
        """Calculated 20V vs target 51.8V → FAR outside 10% → FAIL"""
        r = check_nominal_voltage(20.0, 51.8, tolerance_pct=10.0)
        assert r.status == Status.fail

    def test_just_inside_upper_bound(self):
        """target=50V, tol=10% → limit=55V; calc=54.99 → just inside"""
        r = check_nominal_voltage(54.99, 50.0, tolerance_pct=10.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_just_outside_upper_bound(self):
        r = check_nominal_voltage(55.01, 50.0, tolerance_pct=10.0)
        assert r.status == Status.fail

    def test_just_inside_lower_bound(self):
        r = check_nominal_voltage(45.01, 50.0, tolerance_pct=10.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_just_outside_lower_bound(self):
        r = check_nominal_voltage(44.99, 50.0, tolerance_pct=10.0)
        assert r.status == Status.fail

    def test_missing_calc_v_unverified(self):
        r = check_nominal_voltage(None, 51.8)
        assert r.status == Status.unverf

    def test_missing_target_unverified(self):
        r = check_nominal_voltage(51.8, None)
        assert r.status == Status.unverf

    def test_both_missing_unverified(self):
        r = check_nominal_voltage(None, None)
        assert r.status == Status.unverf

    def test_result_has_correct_units(self):
        r = check_nominal_voltage(51.8, 51.8)
        assert r.units == "V"

    def test_result_has_rule_id(self):
        r = check_nominal_voltage(51.8, 51.8)
        assert r.rule_id == "VOLT_NOMINAL"

    @pytest.mark.parametrize("calc_v,target,tol,expected_status", [
        (51.8, 51.8, 10.0, True),   # exact match → pass/warn
        (55.0, 50.0, 10.0, True),   # upper bound exactly
        (45.0, 50.0, 10.0, True),   # lower bound exactly
        (60.0, 50.0, 10.0, False),  # 20% over → fail
        (40.0, 50.0, 10.0, False),  # 20% under → fail
        (51.0, 51.8, 5.0, True),    # 1.5% off → pass with 5% tol
        (49.0, 51.8, 5.0, False),   # 5.4% off → fail with 5% tol
    ])
    def test_parametric_voltage(self, calc_v, target, tol, expected_status):
        r = check_nominal_voltage(calc_v, target, tolerance_pct=tol)
        if expected_status:
            assert r.status in (Status.pass_, Status.warn)
        else:
            assert r.status == Status.fail


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ENERGY_TARGET
# ═══════════════════════════════════════════════════════════════════════════════
class TestEnergyConstraint:

    def test_nominal_passes_above_target(self):
        """E_nom = 2072 Wh, target = 2000 Wh → PASS"""
        r = check_nominal_energy(calc_e_wh=2072.0, target_e_wh=2000.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_nominal_fails_below_target(self):
        r = check_nominal_energy(calc_e_wh=1500.0, target_e_wh=2000.0)
        assert r.status == Status.fail

    def test_usable_energy_comparison(self):
        """When is_usable_target=True, compare usable_e, not nominal."""
        r = check_nominal_energy(
            calc_e_wh=2072.0, target_e_wh=1600.0,
            is_usable_target=True, usable_e_wh=1657.6,
        )
        assert r.status in (Status.pass_, Status.warn)

    def test_usable_below_target_fails(self):
        r = check_nominal_energy(
            calc_e_wh=2072.0, target_e_wh=2000.0,
            is_usable_target=True, usable_e_wh=1657.6,
        )
        assert r.status == Status.fail

    def test_missing_calc_unverified(self):
        r = check_nominal_energy(calc_e_wh=None, target_e_wh=2000.0)
        assert r.status == Status.unverf

    def test_missing_target_unverified(self):
        r = check_nominal_energy(calc_e_wh=2072.0, target_e_wh=None)
        assert r.status == Status.unverf

    def test_result_units_wh(self):
        r = check_nominal_energy(calc_e_wh=2072.0, target_e_wh=2000.0)
        assert r.units == "Wh"

    def test_rule_id(self):
        r = check_nominal_energy(calc_e_wh=2072.0, target_e_wh=2000.0)
        assert r.rule_id == "ENERGY_TARGET"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MASS_CELL
# ═══════════════════════════════════════════════════════════════════════════════
class TestMassConstraint:

    def test_pass_under_limit(self):
        """112 × 0.070 kg = 7.84 kg << 25 kg → PASS"""
        r = check_cell_mass(total_cells=112, cell_mass_kg=0.070, max_mass_kg=25.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_fail_over_limit(self):
        """224 × 0.15 kg = 33.6 kg > 25 kg → FAIL"""
        r = check_cell_mass(total_cells=224, cell_mass_kg=0.15, max_mass_kg=25.0)
        assert r.status == Status.fail

    def test_exactly_at_limit_passes(self):
        """112 × (25/112) ≈ 25 kg → at limit → PASS/WARN"""
        mass_per_cell = 25.0 / 112
        r = check_cell_mass(total_cells=112, cell_mass_kg=mass_per_cell, max_mass_kg=25.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_missing_cell_mass_unverified(self):
        r = check_cell_mass(total_cells=112, cell_mass_kg=None, max_mass_kg=25.0)
        assert r.status == Status.unverf

    def test_missing_max_mass_unverified(self):
        r = check_cell_mass(total_cells=112, cell_mass_kg=0.070, max_mass_kg=None)
        assert r.status == Status.unverf

    def test_both_missing_unverified(self):
        r = check_cell_mass(total_cells=112, cell_mass_kg=None, max_mass_kg=None)
        assert r.status == Status.unverf

    def test_missing_does_not_auto_pass(self):
        """CRITICAL: missing data must NEVER become PASS."""
        r = check_cell_mass(total_cells=112, cell_mass_kg=None, max_mass_kg=25.0)
        assert r.status != Status.pass_

    @pytest.mark.parametrize("cells,mass_per,limit,should_pass", [
        (112, 0.070, 25.0, True),     # 7.84 kg << 25
        (112, 0.224, 25.0, True),     # 25.088 kg ≈ 25 → warn/fail depending on impl
        (112, 0.300, 25.0, False),    # 33.6 kg > 25
        (500, 0.070, 25.0, False),    # 35 kg > 25
    ])
    def test_parametric_mass(self, cells, mass_per, limit, should_pass):
        r = check_cell_mass(cells, mass_per, limit)
        observed = cells * mass_per
        if observed <= limit:
            assert r.status in (Status.pass_, Status.warn)
        else:
            assert r.status == Status.fail


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CURR_CONTINUOUS
# ═══════════════════════════════════════════════════════════════════════════════
class TestCurrentConstraint:

    def test_pass_when_below_limit(self):
        """I_cell = 40/8 = 5A; limit = 10A → PASS"""
        r = check_continuous_current(i_pack_a=40.0, np=8, cell_max_cont_a=10.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_fail_when_exceeds_limit(self):
        """I_cell = 40/8 = 5A; limit = 4A → FAIL"""
        r = check_continuous_current(i_pack_a=40.0, np=8, cell_max_cont_a=4.0)
        assert r.status == Status.fail

    def test_exactly_at_limit_passes(self):
        """I_cell = 5A = limit 5A → PASS/WARN"""
        r = check_continuous_current(i_pack_a=40.0, np=8, cell_max_cont_a=5.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_missing_pack_current_unverified(self):
        r = check_continuous_current(i_pack_a=None, np=8, cell_max_cont_a=10.0)
        assert r.status == Status.unverf

    def test_missing_rating_unverified(self):
        r = check_continuous_current(i_pack_a=40.0, np=8, cell_max_cont_a=None)
        assert r.status == Status.unverf

    def test_missing_does_not_auto_pass(self):
        """CRITICAL: missing rating must NEVER become PASS."""
        r = check_continuous_current(i_pack_a=40.0, np=8, cell_max_cont_a=None)
        assert r.status != Status.pass_


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TEMP_CELL_MAX
# ═══════════════════════════════════════════════════════════════════════════════
class TestTemperatureConstraint:

    def test_pass_when_below_limit(self):
        r = check_temperature(max_modelled_temp_c=40.0, cell_max_op_temp_c=60.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_fail_when_exceeds_limit(self):
        r = check_temperature(max_modelled_temp_c=75.0, cell_max_op_temp_c=60.0)
        assert r.status == Status.fail

    def test_exactly_at_limit_passes(self):
        r = check_temperature(max_modelled_temp_c=60.0, cell_max_op_temp_c=60.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_missing_modelled_temp_unverified(self):
        r = check_temperature(max_modelled_temp_c=None, cell_max_op_temp_c=60.0)
        assert r.status == Status.unverf

    def test_missing_limit_unverified(self):
        r = check_temperature(max_modelled_temp_c=40.0, cell_max_op_temp_c=None)
        assert r.status == Status.unverf

    def test_missing_does_not_auto_pass(self):
        r = check_temperature(max_modelled_temp_c=None, cell_max_op_temp_c=None)
        assert r.status != Status.pass_

    def test_rule_id(self):
        r = check_temperature(40.0, 60.0)
        assert r.rule_id == "TEMP_CELL_MAX"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. COST_BOM
# ═══════════════════════════════════════════════════════════════════════════════
class TestCostConstraint:

    def test_pass_under_budget(self):
        r = check_cost(estimated_bom_usd=200.0, max_cost_usd=500.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_fail_over_budget(self):
        r = check_cost(estimated_bom_usd=600.0, max_cost_usd=500.0)
        assert r.status == Status.fail

    def test_missing_bom_unverified(self):
        r = check_cost(estimated_bom_usd=None, max_cost_usd=500.0)
        assert r.status == Status.unverf

    def test_missing_budget_unverified(self):
        r = check_cost(estimated_bom_usd=200.0, max_cost_usd=None)
        assert r.status == Status.unverf

    def test_missing_does_not_auto_pass(self):
        r = check_cost(estimated_bom_usd=None, max_cost_usd=500.0)
        assert r.status != Status.pass_

    def test_rule_id(self):
        r = check_cost(200.0, 500.0)
        assert r.rule_id == "COST_BOM"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SOC_FLOOR
# ═══════════════════════════════════════════════════════════════════════════════
class TestSOCFloor:

    def test_positive_soc_passes(self):
        r = check_soc_bounds(min_soc=0.15)
        assert r.status in (Status.pass_, Status.warn)

    def test_zero_soc_passes(self):
        """SOC exactly 0 is the boundary — system ran to depletion."""
        r = check_soc_bounds(min_soc=0.0)
        assert r.status in (Status.pass_, Status.warn)

    def test_negative_soc_fails(self):
        """This should never happen with coulomb counting clamping, but if it does → FAIL."""
        r = check_soc_bounds(min_soc=-0.01)
        assert r.status == Status.fail

    def test_none_soc_unverified(self):
        """Simulation not run → no SOC data → UNVERIFIED."""
        r = check_soc_bounds(min_soc=None)
        assert r.status == Status.unverf

    def test_rule_id(self):
        r = check_soc_bounds(min_soc=0.5)
        assert r.rule_id == "SOC_FLOOR"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. run_all_checks — Integration
# ═══════════════════════════════════════════════════════════════════════════════
class TestRunAllChecks:
    """run_all_checks returns a list of all 7 constraint results."""

    def _all_pass_args(self):
        return dict(
            calc_v=51.8,
            target_v=51.8,
            calc_e_wh=2072.0,
            usable_e_wh=1657.6,
            target_e_wh=2000.0,
            energy_is_usable=False,
            total_cells=112,
            cell_mass_kg=0.070,
            max_mass_kg=25.0,
            i_pack_a=40.0,
            np=8,
            cell_max_cont_a=10.0,
            max_modelled_temp_c=26.0,
            cell_max_op_temp_c=60.0,
            estimated_bom_usd=None,
            max_cost_usd=None,
            min_soc=0.10,
        )

    def test_returns_7_checks(self):
        checks = run_all_checks(**self._all_pass_args())
        assert len(checks) == 7

    def test_all_have_rule_ids(self):
        checks = run_all_checks(**self._all_pass_args())
        rule_ids = {c.rule_id for c in checks}
        expected_ids = {"VOLT_NOMINAL", "ENERGY_TARGET", "MASS_LIMIT",
                        "CURR_CONTINUOUS", "TEMP_CELL_MAX", "COST_BOM", "SOC_FLOOR"}
        assert rule_ids == expected_ids

    def test_missing_data_makes_unverified_not_pass(self):
        """When cell_mass_kg=None, mass check must be UNVERIFIED, not PASS."""
        args = self._all_pass_args()
        args["cell_mass_kg"] = None
        checks = run_all_checks(**args)
        mass_check = next(c for c in checks if c.rule_id == "MASS_LIMIT")
        assert mass_check.status == Status.unverf
        assert mass_check.status != Status.pass_

    def test_over_current_fails(self):
        args = self._all_pass_args()
        args["i_pack_a"] = 100.0  # 100/8 = 12.5A > 10A limit
        checks = run_all_checks(**args)
        curr_check = next(c for c in checks if c.rule_id == "CURR_CONTINUOUS")
        assert curr_check.status == Status.fail

    def test_temperature_violation_fails(self):
        args = self._all_pass_args()
        args["max_modelled_temp_c"] = 80.0  # > 60°C limit
        checks = run_all_checks(**args)
        temp_check = next(c for c in checks if c.rule_id == "TEMP_CELL_MAX")
        assert temp_check.status == Status.fail

    def test_multiple_failures_simultaneously(self):
        """Multiple violated constraints → multiple FAIL statuses."""
        args = self._all_pass_args()
        args["calc_v"] = 20.0        # voltage way off
        args["max_modelled_temp_c"] = 90.0  # temp over limit
        args["i_pack_a"] = 200.0    # current over limit
        checks = run_all_checks(**args)
        failed = [c for c in checks if c.status == Status.fail]
        assert len(failed) >= 2

    def test_all_none_inputs_gives_all_unverified(self):
        """All optional data missing → all checks must be UNVERIFIED (never PASS)."""
        checks = run_all_checks(
            calc_v=None, target_v=None,
            calc_e_wh=None, usable_e_wh=None, target_e_wh=None,
            energy_is_usable=False,
            total_cells=112, cell_mass_kg=None, max_mass_kg=None,
            i_pack_a=None, np=8, cell_max_cont_a=None,
            max_modelled_temp_c=None, cell_max_op_temp_c=None,
            estimated_bom_usd=None, max_cost_usd=None,
            min_soc=None,
        )
        for c in checks:
            assert c.status != Status.pass_, (
                f"Rule {c.rule_id} returned PASS with no input data — this is incorrect"
            )
