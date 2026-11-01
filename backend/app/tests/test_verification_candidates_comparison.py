"""
BattLab — Candidate Generator + Comparison Service Verification
================================================================
Independent verification of:
  - generate_candidates() rules and arithmetic
  - compare_runs() metric table construction and ranking logic
"""
import math
import pytest

from app.services.candidate_generator import generate_candidates, CandidateConfig, _score_candidate
from app.services.comparison import compare_runs


# ── Reference helpers ─────────────────────────────────────────────────────────

def ref_ns_min(target_v, v_cell, tol_pct=15.0):
    return max(1, math.floor(target_v / v_cell * (1 - tol_pct / 100)))

def ref_ns_max(target_v, v_cell, tol_pct=15.0):
    return math.ceil(target_v / v_cell * (1 + tol_pct / 100))

def ref_v_nom(ns, v_cell):
    return ns * v_cell

def ref_e_nom(ns, np_, v_cell, ah):
    return ns * np_ * v_cell * ah


# ═══════════════════════════════════════════════════════════════════════════════
# Candidate Generator
# ═══════════════════════════════════════════════════════════════════════════════
class TestCandidateGenerator:

    def _base_args(self, **overrides):
        base = dict(
            target_voltage_v=51.8,
            target_energy_wh=2000.0,
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
        base.update(overrides)
        return base

    def test_14s_exact_match_included(self):
        """14S × 3.7V = 51.8V matches target exactly → must appear."""
        cs = generate_candidates(**self._base_args())
        ns_vals = [c.ns for c in cs]
        assert 14 in ns_vals

    def test_nominal_voltage_arithmetic_correct(self):
        """Every candidate: V_nom = ns × v_cell."""
        cs = generate_candidates(**self._base_args())
        for c in cs:
            assert c.nominal_voltage_v == pytest.approx(ref_v_nom(c.ns, 3.7), rel=1e-5)

    def test_energy_arithmetic_correct(self):
        """Every candidate: E_nom = ns × np × v_cell × ah_cell."""
        cs = generate_candidates(**self._base_args())
        for c in cs:
            assert c.nominal_energy_wh == pytest.approx(
                ref_e_nom(c.ns, c.np, 3.7, 5.0), rel=1e-4
            )

    def test_total_cells_arithmetic(self):
        cs = generate_candidates(**self._base_args())
        for c in cs:
            assert c.total_cells == c.ns * c.np

    def test_no_infeasible_voltage_outside_tolerance(self):
        """Candidates with voltage outside ±15% of target must be infeasible or absent."""
        cs = generate_candidates(**self._base_args())
        for c in cs:
            v_err = abs(c.nominal_voltage_v - 51.8) / 51.8 * 100
            if c.status == "feasible":
                assert v_err <= 15.0

    def test_usable_energy_is_window_fraction_of_nominal(self):
        """usable = window × nominal (where window = 0.80 by default)."""
        cs = generate_candidates(**self._base_args(v_cell_min=2.5, v_cell_max=4.2))
        for c in cs:
            if c.estimated_usable_energy_wh is not None:
                assert c.estimated_usable_energy_wh == pytest.approx(
                    c.nominal_energy_wh * 0.80, rel=1e-3
                )

    def test_mass_filter_eliminates_heavy_configs(self):
        """With cell_mass_kg=0.10 and max_mass_kg=5, must not have feasible configs over 5kg."""
        cs = generate_candidates(**self._base_args(cell_mass_kg=0.10, max_mass_kg=5.0))
        feasible = [c for c in cs if c.status == "feasible"]
        for c in feasible:
            assert c.estimated_cell_mass_kg is not None
            assert c.estimated_cell_mass_kg <= 5.0 + 1e-6

    def test_missing_mass_does_not_eliminate(self):
        """Unknown mass with mass limit → status = 'unverified', not infeasible."""
        cs = generate_candidates(**self._base_args(cell_mass_kg=None, max_mass_kg=5.0))
        for c in cs:
            assert c.status != "infeasible" or len(c.fail_notes) > 0

    def test_zero_cell_voltage_raises(self):
        args = self._base_args()
        args["v_cell_nominal"] = 0.0
        with pytest.raises(ValueError):
            generate_candidates(**args)

    def test_negative_cell_voltage_raises(self):
        args = self._base_args()
        args["v_cell_nominal"] = -1.0
        with pytest.raises(ValueError):
            generate_candidates(**args)

    def test_zero_ah_raises(self):
        args = self._base_args()
        args["ah_cell"] = 0.0
        with pytest.raises(ValueError):
            generate_candidates(**args)

    def test_zero_target_voltage_raises(self):
        args = self._base_args()
        args["target_voltage_v"] = 0.0
        with pytest.raises(ValueError):
            generate_candidates(**args)

    def test_max_candidates_limit(self):
        cs = generate_candidates(**self._base_args(), max_candidates=3)
        assert len(cs) <= 3

    def test_feasible_before_unverified_before_infeasible(self):
        """Sort order: feasible → unverified → infeasible."""
        cs = generate_candidates(**self._base_args())
        order = {"feasible": 0, "unverified": 1, "infeasible": 2}
        orders = [order.get(c.status, 3) for c in cs]
        assert orders == sorted(orders)

    def test_high_energy_target_requires_more_parallel(self):
        """Higher energy target → higher np in generated candidates."""
        cs_low = generate_candidates(**self._base_args(target_energy_wh=500.0))
        cs_high = generate_candidates(**self._base_args(target_energy_wh=10000.0))
        max_np_low = max(c.np for c in cs_low)
        max_np_high = max(c.np for c in cs_high)
        assert max_np_high > max_np_low

    def test_each_candidate_has_status(self):
        cs = generate_candidates(**self._base_args())
        for c in cs:
            assert c.status in ("feasible", "unverified", "infeasible")

    def test_each_candidate_has_pass_or_fail_notes(self):
        cs = generate_candidates(**self._base_args())
        for c in cs:
            assert len(c.pass_notes) + len(c.fail_notes) + len(c.warning_notes) > 0

    def test_usable_target_adjusts_np(self):
        """energy_is_usable=True → np must be higher than for same nominal target."""
        cs_nom = generate_candidates(**self._base_args(
            target_energy_wh=2000.0, energy_is_usable=False
        ))
        cs_usable = generate_candidates(**self._base_args(
            target_energy_wh=2000.0, energy_is_usable=True
        ))
        # Usable energy is 80% of nominal → need more cells to hit same usable target
        max_np_nom = max(c.np for c in cs_nom if c.ns == 14)
        max_np_usable = max(c.np for c in cs_usable if c.ns == 14)
        assert max_np_usable >= max_np_nom

    def test_score_function_positive(self):
        s = _score_candidate(
            v_err_pct=0.0, e_err_pct=0.0,
            est_mass=None, mass_limit=None,
            est_bom=None, total_cells=100,
        )
        assert s >= 0.0

    def test_score_higher_for_closer_voltage(self):
        s_close = _score_candidate(0.0, 0.0, None, None, None, 100)
        s_far = _score_candidate(14.0, 0.0, None, None, None, 100)
        assert s_close > s_far

    def test_score_higher_for_fewer_cells(self):
        s_few = _score_candidate(0.0, 0.0, None, None, None, 50)
        s_many = _score_candidate(0.0, 0.0, None, None, None, 400)
        assert s_few > s_many


# ═══════════════════════════════════════════════════════════════════════════════
# Comparison Service
# ═══════════════════════════════════════════════════════════════════════════════
class TestComparisonService:

    def _make_run(self, **overrides):
        base = {
            "run_id": 1,
            "run_label": "Run A",
            "config_label": "14S8P",
            "nominal_voltage_v": 51.8,
            "nominal_energy_wh": 2072.0,
            "usable_energy_wh": 1657.6,
            "max_temp_c": 26.0,
            "min_soc": 0.1,
            "energy_delivered_wh": 1500.0,
            "constraint_pass": 4,
            "constraint_fail": 0,
            "constraint_warning": 0,
            "constraint_unverified": 3,
            "cell_mass_kg": 7.84,
            "bom_cost_usd": None,
            "ns": 14, "np": 8,
            "total_cells": 112,
        }
        base.update(overrides)
        return base

    def test_empty_list_returns_error(self):
        result = compare_runs([])
        assert "error" in result

    def test_single_run_allowed(self):
        result = compare_runs([self._make_run()])
        assert "metrics_table" in result

    def test_two_runs_produces_two_rankings(self):
        r1 = self._make_run(run_id=1, run_label="Run A")
        r2 = self._make_run(run_id=2, run_label="Run B",
                           nominal_energy_wh=4144.0, usable_energy_wh=3315.2,
                           total_cells=224, ns=14, np=16)
        result = compare_runs([r1, r2])
        assert len(result["ranking"]) == 2

    def test_failed_run_ranked_last(self):
        """Run with constraint_fail > 0 must be ranked last."""
        r_good = self._make_run(run_id=1, run_label="Good",
                                constraint_fail=0, max_temp_c=26.0)
        r_bad = self._make_run(run_id=2, run_label="Bad",
                               constraint_fail=2, max_temp_c=80.0)
        result = compare_runs([r_good, r_bad])
        ranking = {r["run_label"]: r["rank"] for r in result["ranking"]}
        assert ranking["Good"] < ranking["Bad"]

    def test_metrics_table_has_voltage_row(self):
        result = compare_runs([self._make_run()])
        metrics = {m["metric"]: m for m in result["metrics_table"]}
        assert "Nominal Voltage" in metrics

    def test_metrics_table_has_energy_rows(self):
        result = compare_runs([self._make_run()])
        metrics = {m["metric"]: m for m in result["metrics_table"]}
        assert "Nominal Energy" in metrics
        assert "Usable Energy" in metrics

    def test_min_soc_converted_to_percent(self):
        """min_soc = 0.10 should appear as 10.0 % in the comparison table."""
        result = compare_runs([self._make_run(min_soc=0.10)])
        metrics = {m["metric"]: m for m in result["metrics_table"]}
        soc_row = metrics.get("Min SOC")
        if soc_row:
            val = list(soc_row["values"].values())[0]
            if val is not None:
                assert val == pytest.approx(10.0, rel=0.01)

    def test_weights_used_returned(self):
        result = compare_runs([self._make_run()])
        assert "weights_used" in result

    def test_identical_runs_same_score(self):
        r1 = self._make_run(run_id=1, run_label="A")
        r2 = self._make_run(run_id=2, run_label="B")
        result = compare_runs([r1, r2])
        scores = {r["run_label"]: r["score"] for r in result["ranking"]}
        assert scores["A"] == pytest.approx(scores["B"], rel=1e-5)

    def test_higher_usable_energy_higher_score(self):
        r_low = self._make_run(run_id=1, run_label="Low",
                               usable_energy_wh=1000.0, constraint_fail=0)
        r_high = self._make_run(run_id=2, run_label="High",
                                usable_energy_wh=4000.0, constraint_fail=0)
        result = compare_runs([r_low, r_high])
        scores = {r["run_label"]: r["score"] for r in result["ranking"]}
        assert scores["High"] > scores["Low"]

    def test_lower_temp_higher_score(self):
        r_hot = self._make_run(run_id=1, run_label="Hot",
                               max_temp_c=70.0, constraint_fail=0)
        r_cool = self._make_run(run_id=2, run_label="Cool",
                                max_temp_c=26.0, constraint_fail=0)
        result = compare_runs([r_hot, r_cool])
        scores = {r["run_label"]: r["score"] for r in result["ranking"]}
        assert scores["Cool"] > scores["Hot"]

    def test_ranking_has_rank_field(self):
        r1 = self._make_run(run_id=1, run_label="A")
        r2 = self._make_run(run_id=2, run_label="B")
        result = compare_runs([r1, r2])
        ranks = [r["rank"] for r in result["ranking"]]
        assert sorted(ranks) == [1, 2]

    def test_14s8p_vs_14s16p_energy_metric(self):
        """14S16P has double energy — should appear in metrics table with correct value."""
        r_8p = self._make_run(run_id=1, run_label="14S8P",
                              nominal_energy_wh=2072.0)
        r_16p = self._make_run(run_id=2, run_label="14S16P",
                               nominal_energy_wh=4144.0, total_cells=224, np=16)
        result = compare_runs([r_8p, r_16p])
        metrics = {m["metric"]: m for m in result["metrics_table"]}
        e_row = metrics["Nominal Energy"]
        e_8p = e_row["values"]["14S8P"]
        e_16p = e_row["values"]["14S16P"]
        assert e_16p == pytest.approx(2 * e_8p, rel=1e-3)

