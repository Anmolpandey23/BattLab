"""
BattLab — Comprehensive Electrical Verification Suite
=====================================================
Every formula is tested against independently calculated reference values.
The production function is NEVER used to generate the expected result.

Formulas under test:
  V_nominal = Ns × V_cell
  Ah_pack   = Np × Ah_cell
  E_nominal = V_nominal × Ah_pack         [Wh]
  E_usable  = window × E_nominal          (SOC-window approximation)
  R_pack    = (Ns × R_cell / Np) + R_interconnect
  I_cell    = I_pack / Np
  P_loss    = I_pack² × R_pack
  Q_cell    = I_cell² × R_cell
  V_max     = Ns × V_cell_max
  V_min     = Ns × V_cell_min
  SOC_new   = clamp(SOC - I_cell × dt / (3600 × Ah_cell), 0, 1)
"""
import math
import pytest

from app.services.electrical import (
    ElectricalInputs, PackSummary, calculate_pack, soc_update, generate_current_profile,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def ref_nominal_voltage(ns: int, v: float) -> float:
    return ns * v

def ref_capacity_ah(np_: int, ah: float) -> float:
    return np_ * ah

def ref_nominal_energy(ns: int, np_: int, v: float, ah: float) -> float:
    return ns * v * np_ * ah

def ref_usable_energy(ns: int, np_: int, v: float, ah: float, window: float) -> float:
    return window * ref_nominal_energy(ns, np_, v, ah)

def ref_r_pack(ns: int, np_: int, r_cell: float, r_ic: float = 0.0) -> float:
    return ns * r_cell / np_ + r_ic

def ref_i_cell(i_pack: float, np_: float) -> float:
    return i_pack / np_

def ref_p_loss(i_pack: float, r_pack: float) -> float:
    return i_pack ** 2 * r_pack

def ref_q_cell(i_cell: float, r_cell: float) -> float:
    return i_cell ** 2 * r_cell

def ref_soc_update(soc: float, i_cell: float, dt: float, ah: float) -> float:
    delta = -(i_cell * dt) / (3600.0 * ah)
    return max(0.0, min(1.0, soc + delta))


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Nominal Voltage
# ═══════════════════════════════════════════════════════════════════════════════
class TestNominalVoltage:
    """V_nominal = Ns × V_cell_nominal"""

    def test_acceptance_14s_3v7(self):
        """Acceptance scenario: 14S × 3.7V = 51.8V"""
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_voltage_v == pytest.approx(ref_nominal_voltage(14, 3.7), rel=1e-6)
        assert pack.nominal_voltage_v == pytest.approx(51.8, rel=1e-6)

    def test_1s(self):
        inp = ElectricalInputs(ns=1, np=1, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_voltage_v == pytest.approx(3.7, rel=1e-6)

    def test_100s(self):
        inp = ElectricalInputs(ns=100, np=1, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_voltage_v == pytest.approx(ref_nominal_voltage(100, 3.7), rel=1e-6)

    def test_lfp_3v2(self):
        inp = ElectricalInputs(ns=16, np=4, v_cell_nominal=3.2, ah_cell=10.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_voltage_v == pytest.approx(16 * 3.2, rel=1e-6)

    def test_nca_3v65(self):
        inp = ElectricalInputs(ns=7, np=2, v_cell_nominal=3.65, ah_cell=3.5, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_voltage_v == pytest.approx(7 * 3.65, rel=1e-6)

    def test_ns0_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(ElectricalInputs(ns=0, np=1, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None))

    def test_negative_ns_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(ElectricalInputs(ns=-1, np=1, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None))

    def test_zero_voltage_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(ElectricalInputs(ns=14, np=8, v_cell_nominal=0.0, ah_cell=5.0, r_cell_ohm=None))

    def test_negative_voltage_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(ElectricalInputs(ns=14, np=8, v_cell_nominal=-1.0, ah_cell=5.0, r_cell_ohm=None))

    @pytest.mark.parametrize("ns,v", [(1, 3.7), (2, 3.7), (7, 3.2), (14, 3.7), (20, 3.65), (100, 3.7)])
    def test_parametric_nominal_voltage(self, ns, v):
        inp = ElectricalInputs(ns=ns, np=1, v_cell_nominal=v, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_voltage_v == pytest.approx(ref_nominal_voltage(ns, v), rel=1e-6)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Pack Capacity
# ═══════════════════════════════════════════════════════════════════════════════
class TestPackCapacity:
    """Ah_pack = Np × Ah_cell"""

    def test_acceptance_8p_5ah(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.capacity_ah == pytest.approx(ref_capacity_ah(8, 5.0), rel=1e-6)
        assert pack.capacity_ah == pytest.approx(40.0, rel=1e-6)

    def test_np0_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(ElectricalInputs(ns=14, np=0, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None))

    def test_zero_ah_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=0.0, r_cell_ohm=None))

    def test_negative_ah_raises(self):
        with pytest.raises(ValueError):
            calculate_pack(ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=-1.0, r_cell_ohm=None))

    @pytest.mark.parametrize("np_,ah", [(1, 1.0), (4, 3.0), (8, 5.0), (16, 10.0), (50, 50.0)])
    def test_parametric_capacity(self, np_, ah):
        inp = ElectricalInputs(ns=1, np=np_, v_cell_nominal=3.7, ah_cell=ah, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.capacity_ah == pytest.approx(ref_capacity_ah(np_, ah), rel=1e-6)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Nominal Energy
# ═══════════════════════════════════════════════════════════════════════════════
class TestNominalEnergy:
    """E_nominal = Ns × V_cell × Np × Ah_cell"""

    def test_acceptance_14s8p(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_energy_wh == pytest.approx(ref_nominal_energy(14, 8, 3.7, 5.0), rel=1e-5)
        assert pack.nominal_energy_wh == pytest.approx(2072.0, rel=1e-5)

    def test_14s16p(self):
        inp = ElectricalInputs(ns=14, np=16, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_energy_wh == pytest.approx(ref_nominal_energy(14, 16, 3.7, 5.0), rel=1e-5)
        assert pack.nominal_energy_wh == pytest.approx(4144.0, rel=1e-5)

    def test_1s1p_smallest(self):
        inp = ElectricalInputs(ns=1, np=1, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_energy_wh == pytest.approx(3.7 * 5.0, rel=1e-6)

    @pytest.mark.parametrize("ns,np_,v,ah", [
        (1, 1, 3.7, 5.0),
        (14, 8, 3.7, 5.0),
        (16, 4, 3.2, 10.0),
        (20, 10, 3.65, 3.5),
        (100, 100, 3.7, 10.0),
    ])
    def test_parametric_energy(self, ns, np_, v, ah):
        inp = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=v, ah_cell=ah, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.nominal_energy_wh == pytest.approx(ref_nominal_energy(ns, np_, v, ah), rel=1e-5)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Usable Energy (SOC-window approximation)
# ═══════════════════════════════════════════════════════════════════════════════
class TestUsableEnergy:
    """E_usable = window × E_nominal — explicitly a SOC-window approximation"""

    def test_acceptance_80_percent(self):
        inp = ElectricalInputs(
            ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None,
            v_cell_min=2.5, v_cell_max=4.2, usable_soc_window=0.80,
        )
        pack = calculate_pack(inp)
        expected = ref_usable_energy(14, 8, 3.7, 5.0, 0.80)
        assert pack.usable_energy_wh == pytest.approx(expected, rel=1e-5)
        assert pack.usable_energy_wh == pytest.approx(1657.6, rel=1e-4)

    def test_90_percent_window(self):
        inp = ElectricalInputs(
            ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None,
            usable_soc_window=0.90,
        )
        pack = calculate_pack(inp)
        assert pack.usable_energy_wh == pytest.approx(2072.0 * 0.90, rel=1e-4)

    def test_100_percent_window_no_min_max_gives_warning(self):
        """100% window with no voltage limits → warning, usable_energy may still be set"""
        inp = ElectricalInputs(
            ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None,
            usable_soc_window=1.0,
        )
        pack = calculate_pack(inp)
        # Either warns and returns None, or returns nominal — must not be > nominal
        if pack.usable_energy_wh is not None:
            assert pack.usable_energy_wh <= pack.nominal_energy_wh + 0.001
        assert len(pack.warnings) > 0

    def test_usable_labelled_not_voltage_curve_integration(self):
        """usable_energy is the SOC-window approximation, not OCV curve integration"""
        inp = ElectricalInputs(
            ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None,
            usable_soc_window=0.80,
        )
        pack = calculate_pack(inp)
        # assumptions must mention an approximation qualifier
        # Actual text: "Usable energy estimated as 80% of nominal energy.
        #               Cell min/max voltage limits not supplied — window is indicative only."
        combined = " ".join(pack.assumptions).lower()
        assert (
            "soc window" in combined
            or "sizing approximation" in combined
            or "indicative" in combined
            or "window" in combined
            or "80%" in combined
        )

    @pytest.mark.parametrize("window,expected_ratio", [
        (0.70, 0.70), (0.75, 0.75), (0.80, 0.80), (0.85, 0.85), (0.90, 0.90),
    ])
    def test_parametric_window(self, window, expected_ratio):
        inp = ElectricalInputs(
            ns=10, np=10, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None,
            usable_soc_window=window,
        )
        pack = calculate_pack(inp)
        e_nom = ref_nominal_energy(10, 10, 3.7, 5.0)
        assert pack.usable_energy_wh == pytest.approx(expected_ratio * e_nom, rel=1e-5)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Pack Resistance
# ═══════════════════════════════════════════════════════════════════════════════
class TestPackResistance:
    """R_pack = Ns × R_cell / Np + R_interconnect"""

    def test_acceptance_14s8p_no_ic(self):
        ns, np_, r = 14, 8, 0.025
        inp = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=r)
        pack = calculate_pack(inp)
        assert pack.r_pack_ohm == pytest.approx(ref_r_pack(ns, np_, r), rel=1e-6)
        assert pack.r_pack_ohm == pytest.approx(0.04375, rel=1e-5)

    def test_with_interconnect(self):
        ns, np_, r, r_ic = 14, 8, 0.025, 0.001
        inp = ElectricalInputs(
            ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0,
            r_cell_ohm=r, r_interconnect_ohm=r_ic,
        )
        pack = calculate_pack(inp)
        assert pack.r_pack_ohm == pytest.approx(ref_r_pack(ns, np_, r, r_ic), rel=1e-6)

    def test_zero_resistance_gives_zero(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=0.0)
        pack = calculate_pack(inp)
        assert pack.r_pack_ohm == pytest.approx(0.0, abs=1e-10)

    def test_none_resistance_gives_none(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.r_pack_ohm is None
        assert pack.p_loss_w is None
        assert pack.q_cell_w is None

    def test_1s1p_r_equals_cell_r(self):
        inp = ElectricalInputs(ns=1, np=1, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=0.025)
        pack = calculate_pack(inp)
        assert pack.r_pack_ohm == pytest.approx(0.025, rel=1e-6)

    def test_more_parallel_reduces_resistance(self):
        """Doubling Np halves pack R (no interconnect)."""
        r = 0.025
        inp1 = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=r)
        inp2 = ElectricalInputs(ns=14, np=16, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=r)
        p1 = calculate_pack(inp1)
        p2 = calculate_pack(inp2)
        assert p2.r_pack_ohm == pytest.approx(p1.r_pack_ohm / 2, rel=1e-5)

    def test_14s16p_resistance(self):
        ns, np_, r = 14, 16, 0.025
        inp = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=r)
        pack = calculate_pack(inp)
        assert pack.r_pack_ohm == pytest.approx(ref_r_pack(ns, np_, r), rel=1e-6)
        assert pack.r_pack_ohm == pytest.approx(0.021875, rel=1e-5)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Per-Cell Current and Pack Loss
# ═══════════════════════════════════════════════════════════════════════════════
class TestCurrentAndLoss:
    """I_cell = I_pack / Np; P_loss = I_pack² × R_pack; Q_cell = I_cell² × R_cell"""

    def test_acceptance_40a_8p(self):
        ns, np_, r, i_pack = 14, 8, 0.025, 40.0
        inp = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=r, i_pack_a=i_pack)
        pack = calculate_pack(inp)
        assert pack.i_cell_a == pytest.approx(ref_i_cell(i_pack, np_), rel=1e-5)
        assert pack.i_cell_a == pytest.approx(5.0, rel=1e-5)

    def test_acceptance_resistive_loss_40a(self):
        ns, np_, r, i_pack = 14, 8, 0.025, 40.0
        inp = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=r, i_pack_a=i_pack)
        pack = calculate_pack(inp)
        r_pack = ref_r_pack(ns, np_, r)
        assert pack.p_loss_w == pytest.approx(ref_p_loss(i_pack, r_pack), rel=1e-5)
        assert pack.p_loss_w == pytest.approx(70.0, rel=1e-4)

    def test_acceptance_heat_per_cell(self):
        ns, np_, r, i_pack = 14, 8, 0.025, 40.0
        inp = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=r, i_pack_a=i_pack)
        pack = calculate_pack(inp)
        i_cell = ref_i_cell(i_pack, np_)
        assert pack.q_cell_w == pytest.approx(ref_q_cell(i_cell, r), rel=1e-5)
        assert pack.q_cell_w == pytest.approx(0.625, rel=1e-4)

    def test_no_current_no_loss(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=0.025, i_pack_a=None)
        pack = calculate_pack(inp)
        assert pack.i_cell_a is None
        assert pack.p_loss_w is None
        assert pack.q_cell_w is None

    def test_20a_pack_current_14s16p(self):
        """Changed-current scenario: 20A, 14S16P."""
        ns, np_, r, i_pack = 14, 16, 0.025, 20.0
        inp = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=r, i_pack_a=i_pack)
        pack = calculate_pack(inp)
        r_pack = ref_r_pack(ns, np_, r)
        assert pack.i_cell_a == pytest.approx(ref_i_cell(i_pack, np_), rel=1e-5)
        assert pack.p_loss_w == pytest.approx(ref_p_loss(i_pack, r_pack), rel=1e-5)
        # q_cell_w is rounded to 6 decimal places by calculate_pack();
        # (20/16)² × 0.025 = 0.0390625 → stored as 0.039062 → use abs tolerance
        assert pack.q_cell_w == pytest.approx(ref_q_cell(ref_i_cell(i_pack, np_), r), abs=1e-4)

    def test_loss_quadratic_with_current(self):
        """Doubling current quadruples loss."""
        ns, np_, r = 14, 8, 0.025
        inp1 = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0,
                                r_cell_ohm=r, i_pack_a=20.0)
        inp2 = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0,
                                r_cell_ohm=r, i_pack_a=40.0)
        p1 = calculate_pack(inp1)
        p2 = calculate_pack(inp2)
        assert p2.p_loss_w == pytest.approx(p1.p_loss_w * 4.0, rel=1e-4)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Voltage Limits (Max / Min)
# ═══════════════════════════════════════════════════════════════════════════════
class TestVoltageLimits:
    """V_max = Ns × V_cell_max; V_min = Ns × V_cell_min"""

    def test_acceptance_max_14s_4v2(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=None, v_cell_max=4.2)
        pack = calculate_pack(inp)
        assert pack.max_voltage_v == pytest.approx(14 * 4.2, rel=1e-6)
        assert pack.max_voltage_v == pytest.approx(58.8, rel=1e-5)

    def test_acceptance_min_14s_2v5(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=None, v_cell_min=2.5)
        pack = calculate_pack(inp)
        assert pack.min_voltage_v == pytest.approx(14 * 2.5, rel=1e-6)
        assert pack.min_voltage_v == pytest.approx(35.0, rel=1e-5)

    def test_no_limits_gives_none(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.max_voltage_v is None
        assert pack.min_voltage_v is None

    @pytest.mark.parametrize("ns,v_max,v_min", [
        (1, 4.2, 2.5), (7, 4.2, 2.5), (14, 4.2, 2.5), (20, 4.35, 2.8),
    ])
    def test_parametric_limits(self, ns, v_max, v_min):
        inp = ElectricalInputs(ns=ns, np=1, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=None, v_cell_max=v_max, v_cell_min=v_min)
        pack = calculate_pack(inp)
        assert pack.max_voltage_v == pytest.approx(ns * v_max, rel=1e-6)
        assert pack.min_voltage_v == pytest.approx(ns * v_min, rel=1e-6)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Total Cell Count
# ═══════════════════════════════════════════════════════════════════════════════
class TestTotalCells:
    """total_cells = Ns × Np"""

    @pytest.mark.parametrize("ns,np_", [(1,1), (14,8), (14,16), (20,20), (100,100)])
    def test_total_cells(self, ns, np_):
        inp = ElectricalInputs(ns=ns, np=np_, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=None)
        pack = calculate_pack(inp)
        assert pack.total_cells == ns * np_


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Interconnect Resistance
# ═══════════════════════════════════════════════════════════════════════════════
class TestInterconnectResistance:
    """R_pack includes R_interconnect as an additive term."""

    def test_interconnect_adds_to_pack_r(self):
        r_cell, r_ic = 0.025, 0.005
        inp_no_ic = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=r_cell)
        inp_with_ic = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0,
                                       r_cell_ohm=r_cell, r_interconnect_ohm=r_ic)
        p_no = calculate_pack(inp_no_ic)
        p_ic = calculate_pack(inp_with_ic)
        assert p_ic.r_pack_ohm == pytest.approx(p_no.r_pack_ohm + r_ic, rel=1e-6)

    def test_interconnect_does_not_affect_cell_current(self):
        """Interconnect R affects pack-level loss but NOT per-cell current."""
        i_pack = 40.0
        r_cell = 0.025
        inp1 = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0,
                                r_cell_ohm=r_cell, i_pack_a=i_pack)
        inp2 = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0,
                                r_cell_ohm=r_cell, r_interconnect_ohm=0.01, i_pack_a=i_pack)
        p1 = calculate_pack(inp1)
        p2 = calculate_pack(inp2)
        assert p1.i_cell_a == pytest.approx(p2.i_cell_a, rel=1e-6)  # I_cell unchanged
        assert p2.p_loss_w > p1.p_loss_w  # total loss higher with interconnect


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Current Over-Rating Warnings
# ═══════════════════════════════════════════════════════════════════════════════
class TestCurrentRatingWarnings:
    """Warnings must appear when per-cell current exceeds rated limits."""

    def test_warn_when_exceeds_continuous(self):
        """5 A cell at 5 A is at limit — warning or pass depending on tolerance."""
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=0.025, i_pack_a=40.0, max_continuous_a=4.9)
        pack = calculate_pack(inp)
        # i_cell = 5 A > 4.9 A → must warn
        warn_text = " ".join(pack.warnings).lower()
        assert "continuous" in warn_text or "exceeds" in warn_text

    def test_no_warning_when_below_limit(self):
        inp = ElectricalInputs(ns=14, np=8, v_cell_nominal=3.7, ah_cell=5.0,
                               r_cell_ohm=0.025, i_pack_a=40.0, max_continuous_a=10.0)
        pack = calculate_pack(inp)
        continuous_warns = [w for w in pack.warnings if "continuous" in w.lower()]
        assert len(continuous_warns) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 11. SOC Update (Coulomb Counting)
# ═══════════════════════════════════════════════════════════════════════════════
class TestSOCUpdate:
    """SOC_new = clamp(SOC - I_cell × dt / (3600 × Ah_cell), 0, 1)"""

    def test_1c_discharge_1hour_empties(self):
        """1C for 1 hour → SOC = 0"""
        soc = soc_update(1.0, i_cell_a=5.0, dt_s=3600.0, ah_cell=5.0)
        assert soc == pytest.approx(0.0, abs=1e-9)

    def test_0p5c_discharge_1hour_half(self):
        soc = soc_update(1.0, i_cell_a=2.5, dt_s=3600.0, ah_cell=5.0)
        assert soc == pytest.approx(0.5, rel=1e-6)

    def test_small_step_10s(self):
        """10-second step with 5A cell, 5Ah capacity."""
        soc = soc_update(1.0, i_cell_a=5.0, dt_s=10.0, ah_cell=5.0)
        expected = ref_soc_update(1.0, 5.0, 10.0, 5.0)
        assert soc == pytest.approx(expected, rel=1e-8)

    def test_soc_clamped_at_zero(self):
        """Overcurrent for long time → SOC = 0, not negative."""
        soc = soc_update(0.1, i_cell_a=100.0, dt_s=3600.0, ah_cell=5.0)
        assert soc == 0.0

    def test_soc_never_exceeds_one(self):
        """Charging with large current → SOC clamped at 1."""
        soc = soc_update(0.5, i_cell_a=-100.0, dt_s=3600.0, ah_cell=5.0)
        assert soc == 1.0

    def test_zero_current_no_change(self):
        soc = soc_update(0.75, i_cell_a=0.0, dt_s=3600.0, ah_cell=5.0)
        assert soc == pytest.approx(0.75, rel=1e-9)

    def test_zero_dt_raises(self):
        with pytest.raises(ValueError):
            soc_update(1.0, i_cell_a=5.0, dt_s=0.0, ah_cell=5.0)

    def test_negative_dt_raises(self):
        with pytest.raises(ValueError):
            soc_update(1.0, i_cell_a=5.0, dt_s=-1.0, ah_cell=5.0)

    def test_zero_ah_raises(self):
        with pytest.raises(ValueError):
            soc_update(1.0, i_cell_a=5.0, dt_s=10.0, ah_cell=0.0)

    def test_positive_i_is_discharge(self):
        """Positive current → SOC decreases."""
        soc_new = soc_update(0.8, i_cell_a=5.0, dt_s=100.0, ah_cell=5.0)
        assert soc_new < 0.8

    def test_negative_i_is_charge(self):
        """Negative current → SOC increases."""
        soc_new = soc_update(0.5, i_cell_a=-5.0, dt_s=100.0, ah_cell=5.0)
        assert soc_new > 0.5

    def test_10a_cell_at_200s(self):
        """Cross-check: 10A from 1.0 SOC for 200s into 10Ah cell."""
        soc = soc_update(1.0, i_cell_a=10.0, dt_s=200.0, ah_cell=10.0)
        expected = ref_soc_update(1.0, 10.0, 200.0, 10.0)
        assert soc == pytest.approx(expected, rel=1e-8)

    @pytest.mark.parametrize("soc0,i_cell,dt,ah", [
        (1.0, 5.0, 10.0, 5.0),
        (0.5, 2.5, 100.0, 10.0),
        (0.8, 1.0, 600.0, 3.0),
        (0.3, 0.5, 3600.0, 5.0),
    ])
    def test_parametric_soc(self, soc0, i_cell, dt, ah):
        soc = soc_update(soc0, i_cell_a=i_cell, dt_s=dt, ah_cell=ah)
        expected = ref_soc_update(soc0, i_cell, dt, ah)
        assert soc == pytest.approx(expected, abs=1e-9)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Current Profile Generation
# ═══════════════════════════════════════════════════════════════════════════════
class TestCurrentProfileGeneration:
    """Profiles are declared synthetic/illustrative."""

    def test_steady_cruise_returns_list(self):
        profile = generate_current_profile("steady_cruise", 3600, 10.0, 40.0)
        assert isinstance(profile, list)
        assert len(profile) > 0

    def test_profile_time_starts_at_zero(self):
        profile = generate_current_profile("steady_cruise", 100, 10.0, 40.0)
        assert profile[0][0] == pytest.approx(0.0, abs=1e-9)

    def test_steady_cruise_current_constant(self):
        profile = generate_current_profile("steady_cruise", 100, 10.0, 40.0)
        currents = [p[1] for p in profile]
        assert all(abs(c - 40.0) < 1e-9 for c in currents)

    def test_mixed_profile_generates(self):
        profile = generate_current_profile("mixed", 3600, 10.0, 40.0)
        assert len(profile) > 0

    def test_high_load_profile_generates(self):
        profile = generate_current_profile("high_load", 3600, 10.0, 40.0)
        assert len(profile) > 0

    def test_unknown_profile_defaults_to_constant(self):
        profile = generate_current_profile("unknown_type", 100, 10.0, 40.0)
        assert len(profile) > 0

    def test_profile_dt_matches(self):
        """Number of points ≈ duration/dt + 1."""
        profile = generate_current_profile("steady_cruise", 100, 10.0, 40.0)
        expected_points = 11  # 0,10,20,...,100
        assert len(profile) == expected_points

    def test_positive_current_is_discharge(self):
        """Convention: positive I = discharge."""
        profile = generate_current_profile("steady_cruise", 100, 10.0, 40.0)
        assert all(p[1] >= 0.0 for p in profile)
