"""
BattLab — Comprehensive Thermal Verification Suite
====================================================
Every thermal formula tested against independent analytical solutions.

Model implemented:
  m × cp × dT/dt = Q_gen − hA × (T − T_amb)

Exact analytical solution per step (with constant Q, hA):
  T_eq   = T_amb + Q / hA
  τ      = m × cp / hA
  T(t)   = T_eq + (T_0 − T_eq) × exp(−t / τ)

Special case (hA = 0):
  T(t)   = T_0 + (Q / (m × cp)) × t  (Euler)
"""
import math
import pytest

from app.services.thermal import (
    ThermalInputs, ThermalStep, thermal_step, run_thermal_simulation,
)


# ── Reference analytical solution ────────────────────────────────────────────

def ref_t_next(T0, T_amb, Q, hA, m, cp, dt):
    """Exact analytical solution for one step of the lumped ODE."""
    m_cp = m * cp
    if hA < 1e-9:
        # No cooling: linear
        return T0 + (Q / m_cp) * dt
    T_eq = T_amb + Q / hA
    tau = m_cp / hA
    return T_eq + (T0 - T_eq) * math.exp(-dt / tau)

def ref_t_at_time(T0, T_amb, Q, hA, m, cp, t_total):
    """Analytical temperature at time t_total (single step from T0)."""
    return ref_t_next(T0, T_amb, Q, hA, m, cp, t_total)

def ref_t_equilibrium(T_amb, Q, hA):
    if hA < 1e-9:
        return float("inf")
    return T_amb + Q / hA

def ref_tau(m, cp, hA):
    return (m * cp) / hA


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Single thermal_step correctness
# ═══════════════════════════════════════════════════════════════════════════════
class TestThermalStep:
    """thermal_step() must match the analytical first-order solution."""

    # Reference parameters from acceptance scenario (14S8P, 40A)
    # Q_total = 112 cells × 0.625 W = 70 W
    # Total mass ≈ 112 × 0.070 kg = 7.84 kg; cp = 900 J/kg/K
    # hA (passive) = 2.0 W/K × 112 = 224 W/K
    M, CP, HA, Q = 7.84, 900.0, 224.0, 70.0
    T_AMB, T0 = 25.0, 25.0
    DT = 10.0  # s

    def _inp(self, T0=T0, T_amb=T_AMB, Q=Q, hA=HA, m=M, cp=CP, dt=DT) -> ThermalInputs:
        return ThermalInputs(
            cell_mass_kg=m, cp_j_per_kg_k=cp, ha_w_per_k=hA,
            q_gen_w=Q, t_current_c=T0, t_ambient_c=T_amb, dt_s=dt,
        )

    def test_matches_analytical_at_t_amb(self):
        """T_start = T_amb, Q > 0 → temperature rises."""
        inp = self._inp(T0=25.0, Q=70.0)
        step = thermal_step(inp)
        expected = ref_t_next(25.0, 25.0, 70.0, self.HA, self.M, self.CP, self.DT)
        assert step.t_next_c == pytest.approx(expected, rel=1e-8)

    def test_matches_analytical_above_amb(self):
        """T_start > T_amb, Q = 0 → cooling toward T_amb."""
        inp = self._inp(T0=50.0, Q=0.0)
        step = thermal_step(inp)
        expected = ref_t_next(50.0, 25.0, 0.0, self.HA, self.M, self.CP, self.DT)
        assert step.t_next_c == pytest.approx(expected, rel=1e-8)

    def test_equilibrium_temperature(self):
        """T_eq = T_amb + Q / hA."""
        inp = self._inp()
        step = thermal_step(inp)
        expected_eq = ref_t_equilibrium(self.T_AMB, self.Q, self.HA)
        assert step.t_equilibrium_c == pytest.approx(expected_eq, rel=1e-6)

    def test_no_cooling_euler_mode(self):
        """hA = 0: Euler mode T_next = T + Q/(m×cp) × dt."""
        inp = self._inp(hA=0.0)
        step = thermal_step(inp)
        expected = 25.0 + (70.0 / (self.M * self.CP)) * self.DT
        assert step.t_next_c == pytest.approx(expected, rel=1e-8)

    def test_no_heat_generation_at_equilibrium(self):
        """Q = 0, T = T_amb → no change."""
        inp = self._inp(T0=25.0, Q=0.0)
        step = thermal_step(inp)
        # At thermal equilibrium with Q=0: T should remain at T_amb
        assert step.t_next_c == pytest.approx(25.0, abs=1e-6)

    def test_zero_mass_raises(self):
        with pytest.raises(ValueError):
            thermal_step(ThermalInputs(
                cell_mass_kg=0.0, cp_j_per_kg_k=900, ha_w_per_k=100,
                q_gen_w=10, t_current_c=25, t_ambient_c=25, dt_s=10,
            ))

    def test_negative_mass_raises(self):
        with pytest.raises(ValueError):
            thermal_step(ThermalInputs(
                cell_mass_kg=-1.0, cp_j_per_kg_k=900, ha_w_per_k=100,
                q_gen_w=10, t_current_c=25, t_ambient_c=25, dt_s=10,
            ))

    def test_zero_cp_raises(self):
        with pytest.raises(ValueError):
            thermal_step(ThermalInputs(
                cell_mass_kg=1.0, cp_j_per_kg_k=0.0, ha_w_per_k=100,
                q_gen_w=10, t_current_c=25, t_ambient_c=25, dt_s=10,
            ))

    def test_zero_dt_raises(self):
        with pytest.raises(ValueError):
            thermal_step(ThermalInputs(
                cell_mass_kg=1.0, cp_j_per_kg_k=900, ha_w_per_k=100,
                q_gen_w=10, t_current_c=25, t_ambient_c=25, dt_s=0.0,
            ))

    def test_negative_dt_raises(self):
        with pytest.raises(ValueError):
            thermal_step(ThermalInputs(
                cell_mass_kg=1.0, cp_j_per_kg_k=900, ha_w_per_k=100,
                q_gen_w=10, t_current_c=25, t_ambient_c=25, dt_s=-1.0,
            ))

    def test_high_ha_approaches_ambient_quickly(self):
        """Very high hA (perfect cooling) → next T ≈ T_eq ≈ T_amb + Q/hA."""
        hA = 1e6  # nearly perfect cooling
        Q = 100.0
        T_eq = 25.0 + Q / hA  # = 25.0001
        inp = self._inp(hA=hA, Q=Q)
        step = thermal_step(inp)
        assert step.t_next_c == pytest.approx(T_eq, abs=0.001)

    def test_t_above_equilibrium_cools(self):
        """T > T_eq → step decreases temperature."""
        T_eq = self.T_AMB + self.Q / self.HA
        inp = self._inp(T0=T_eq + 20)  # above equilibrium
        step = thermal_step(inp)
        assert step.t_next_c < step.t_current_c

    def test_t_below_equilibrium_heats(self):
        """T < T_eq → step increases temperature."""
        T_eq = self.T_AMB + self.Q / self.HA
        inp = self._inp(T0=T_eq - 5)  # below equilibrium
        step = thermal_step(inp)
        assert step.t_next_c > step.t_current_c

    def test_q_removed_at_steady_state(self):
        """At T = T_eq: q_removed ≈ Q."""
        T_eq = ref_t_equilibrium(self.T_AMB, self.Q, self.HA)
        inp = self._inp(T0=T_eq)
        step = thermal_step(inp)
        assert step.q_removed_w == pytest.approx(self.HA * (T_eq - self.T_AMB), rel=1e-6)

    @pytest.mark.parametrize("T0,T_amb,Q,hA,m,cp,dt", [
        (25.0, 25.0, 70.0, 224.0, 7.84, 900.0, 10.0),
        (40.0, 20.0, 100.0, 50.0, 2.0, 1000.0, 5.0),
        (60.0, 30.0, 0.0, 10.0, 1.0, 800.0, 1.0),
        (25.0, 25.0, 0.5, 0.5, 0.07, 900.0, 10.0),   # single cell
    ])
    def test_parametric_analytical_match(self, T0, T_amb, Q, hA, m, cp, dt):
        inp = ThermalInputs(cell_mass_kg=m, cp_j_per_kg_k=cp, ha_w_per_k=hA,
                            q_gen_w=Q, t_current_c=T0, t_ambient_c=T_amb, dt_s=dt)
        step = thermal_step(inp)
        expected = ref_t_next(T0, T_amb, Q, hA, m, cp, dt)
        assert step.t_next_c == pytest.approx(expected, rel=1e-8)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. run_thermal_simulation correctness
# ═══════════════════════════════════════════════════════════════════════════════
class TestRunThermalSimulation:
    """Simulation loop must accumulate steps correctly and match analytical."""

    def test_output_length_matches_time_series(self):
        times = [float(t) for t in range(0, 361, 10)]  # 0..360 step 10 → 37 pts
        q_seq = [70.0] * (len(times) - 1)
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_seq,
            t_ambient_c=25.0, t_initial_c=25.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=224.0,
        )
        assert len(result.temperatures_c) == len(times)

    def test_first_temperature_is_initial(self):
        times = [0.0, 10.0, 20.0]
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=[70.0, 70.0],
            t_ambient_c=25.0, t_initial_c=30.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=224.0,
        )
        assert result.temperatures_c[0] == pytest.approx(30.0, abs=1e-9)

    def test_steady_state_approaches_equilibrium(self):
        """After very long run with constant Q, T → T_eq = T_amb + Q/hA."""
        Q, hA, T_amb = 70.0, 224.0, 25.0
        T_eq = ref_t_equilibrium(T_amb, Q, hA)
        # Very long run: 10 000 s, dt=10
        times = [float(t) for t in range(0, 10001, 10)]
        q_seq = [Q] * (len(times) - 1)
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_seq,
            t_ambient_c=T_amb, t_initial_c=T_amb,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=hA,
        )
        assert result.temperatures_c[-1] == pytest.approx(T_eq, abs=0.01)

    def test_no_heat_no_temperature_change(self):
        """Q = 0, T = T_amb → stays at T_amb."""
        times = [0.0, 10.0, 20.0, 30.0]
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=[0.0, 0.0, 0.0],
            t_ambient_c=25.0, t_initial_c=25.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=224.0,
        )
        for T in result.temperatures_c:
            assert T == pytest.approx(25.0, abs=1e-8)

    def test_cooling_without_heat_returns_to_ambient(self):
        """T0 > T_amb, Q=0 → temperature should decrease toward T_amb."""
        times = [float(t) for t in range(0, 1001, 10)]
        q_seq = [0.0] * (len(times) - 1)
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_seq,
            t_ambient_c=25.0, t_initial_c=60.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=224.0,
        )
        assert result.temperatures_c[-1] < 60.0
        assert result.temperatures_c[-1] > 25.0  # Not yet fully cooled in 1000s (check)
        # All temps should be monotonically decreasing
        for i in range(1, len(result.temperatures_c)):
            assert result.temperatures_c[i] <= result.temperatures_c[i-1] + 1e-8

    def test_step_1_matches_analytical(self):
        """After exactly one step, simulation output matches single-step analytical."""
        T0, T_amb, Q, hA, m, cp, dt = 25.0, 25.0, 70.0, 224.0, 7.84, 900.0, 10.0
        times = [0.0, dt]
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=[Q],
            t_ambient_c=T_amb, t_initial_c=T0,
            cell_mass_kg=m, cp_j_per_kg_k=cp, ha_w_per_k=hA,
        )
        expected = ref_t_next(T0, T_amb, Q, hA, m, cp, dt)
        assert result.temperatures_c[1] == pytest.approx(expected, rel=1e-8)

    def test_max_temp_reported_correctly(self):
        times = [float(t) for t in range(0, 101, 10)]
        q_seq = [200.0] * (len(times) - 1)  # high heat
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_seq,
            t_ambient_c=25.0, t_initial_c=25.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=1.0,  # poor cooling
        )
        # max_temp_c is rounded to 3 decimal places in run_thermal_simulation();
        # compare with abs tolerance matching that rounding
        assert result.max_temp_c == pytest.approx(max(result.temperatures_c), abs=0.001)

    def test_min_temp_reported_correctly(self):
        times = [0.0, 10.0, 20.0, 30.0]
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=[0.0, 0.0, 0.0],
            t_ambient_c=25.0, t_initial_c=60.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=224.0,
        )
        assert result.min_temp_c == pytest.approx(min(result.temperatures_c), rel=1e-5)

    def test_max_temp_warning_when_exceeded(self):
        times = [float(t) for t in range(0, 1001, 10)]
        q_seq = [500.0] * (len(times) - 1)  # very high heat
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_seq,
            t_ambient_c=25.0, t_initial_c=25.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=5.0,
            t_max_limit_c=60.0,
        )
        if result.max_temp_c > 60.0:
            assert any("60" in w or "limit" in w.lower() for w in result.warnings)

    def test_empty_time_series_returns_empty(self):
        result = run_thermal_simulation(
            times_s=[], q_gen_sequence_w=[],
            t_ambient_c=25.0, t_initial_c=25.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=224.0,
        )
        assert result.temperatures_c == []

    def test_single_node_disclaimer_in_assumptions(self):
        times = [0.0, 10.0]
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=[70.0],
            t_ambient_c=25.0, t_initial_c=25.0,
            cell_mass_kg=7.84, cp_j_per_kg_k=900.0, ha_w_per_k=224.0,
        )
        combined = " ".join(result.assumptions).lower()
        assert "lumped" in combined or "single-node" in combined

    def test_different_timesteps_converge_to_same_equilibrium(self):
        """Coarser dt converges to same equilibrium but with less accuracy en route."""
        Q, hA, T_amb, m, cp = 70.0, 224.0, 25.0, 7.84, 900.0
        T_eq = ref_t_equilibrium(T_amb, Q, hA)
        # Both dt=1s and dt=100s should approach T_eq after long run
        for dt in [1.0, 100.0]:
            end_t = 50000.0  # well beyond multiple tau values
            n = int(end_t / dt) + 1
            times = [i * dt for i in range(n)]
            q_seq = [Q] * (n - 1)
            result = run_thermal_simulation(
                times_s=times, q_gen_sequence_w=q_seq,
                t_ambient_c=T_amb, t_initial_c=T_amb,
                cell_mass_kg=m, cp_j_per_kg_k=cp, ha_w_per_k=hA,
            )
            assert result.temperatures_c[-1] == pytest.approx(T_eq, abs=0.1)

    def test_tau_scaling(self):
        """After 1 tau, (T - T_eq) / (T0 - T_eq) ≈ exp(-1) ≈ 0.368."""
        Q, hA, T_amb, m, cp = 0.0, 10.0, 25.0, 1.0, 1000.0
        T0 = 60.0
        tau = ref_tau(m, cp, hA)
        T_eq = T_amb + Q / hA
        times = [0.0, tau]
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=[Q],
            t_ambient_c=T_amb, t_initial_c=T0,
            cell_mass_kg=m, cp_j_per_kg_k=cp, ha_w_per_k=hA,
        )
        ratio = (result.temperatures_c[1] - T_eq) / (T0 - T_eq)
        assert ratio == pytest.approx(math.exp(-1), rel=1e-6)

    def test_acceptance_scenario_max_temp(self):
        """Acceptance scenario: 14S8P, 40A, passive cooling, 3600s."""
        # hA = 2.0 W/K × 112 cells = 224 W/K (provisional)
        # Q_total = 112 × 0.625 W = 70 W
        # T_eq = 25 + 70/224 ≈ 25.31°C
        Q, hA, T_amb, m, cp = 70.0, 224.0, 25.0, 7.84, 900.0
        T_eq_expected = ref_t_equilibrium(T_amb, Q, hA)
        times = [float(t) for t in range(0, 3601, 10)]
        q_seq = [Q] * (len(times) - 1)
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_seq,
            t_ambient_c=T_amb, t_initial_c=T_amb,
            cell_mass_kg=m, cp_j_per_kg_k=cp, ha_w_per_k=hA,
        )
        # Max temp should be close to T_eq (near-equilibrium after 3600s)
        assert result.max_temp_c == pytest.approx(T_eq_expected, abs=0.5)
        assert result.max_temp_c < 27.0  # physically plausible with passive cooling

    def test_no_ha_rises_linearly(self):
        """hA = 0: temperature rises as dT/dt = Q/(m×cp)."""
        Q, m, cp = 70.0, 7.84, 900.0
        T0, T_amb = 25.0, 25.0
        dt = 10.0
        times = [0.0, dt, 2 * dt, 3 * dt]
        q_seq = [Q] * 3
        result = run_thermal_simulation(
            times_s=times, q_gen_sequence_w=q_seq,
            t_ambient_c=T_amb, t_initial_c=T0,
            cell_mass_kg=m, cp_j_per_kg_k=cp, ha_w_per_k=0.0,
        )
        dT_expected = (Q / (m * cp)) * dt
        assert result.temperatures_c[1] == pytest.approx(T0 + dT_expected, rel=1e-6)
        assert result.temperatures_c[2] == pytest.approx(T0 + 2 * dT_expected, rel=1e-6)
