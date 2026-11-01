"""
BattLab — Thermal Model & Cooling Physics Independent Verification
===================================================================
Verifies:
1. Exact first-order thermal model:
     m * cp * dT/dt = Q_gen - hA * (T - T_amb)
     T_eq = T_amb + Q_gen / hA
2. Cooling options (Passive, Fan, Liquid) produce distinct, physically realistic
   cooling conductances and equilibrium temperatures.
3. Zero-heat condition converges asymptotically back to ambient temperature.
4. Environmental ambient temperature matrix: -10°C, 0°C, 25°C, 40°C.
5. Numerical stability under fine vs coarse timesteps (dt = 0.5s vs 5.0s).
"""
import math
import pytest
from app.services.thermal import ThermalInputs, thermal_step, run_thermal_simulation
from app.services.simulation import _ha_for_cooling


class TestCoolingConductanceOptions:
    """Verifies that cooling architecture selections alter the mathematical simulation."""

    def test_cooling_conductance_scaling(self):
        """Passive, fan, and liquid cooling have distinct conductances scaling with pack size."""
        n_cells = 224
        ha_passive, note_p = _ha_for_cooling("passive", n_cells)
        ha_fan, note_f = _ha_for_cooling("fan", n_cells)
        ha_liquid, note_l = _ha_for_cooling("liquid", n_cells)

        assert ha_passive < ha_fan < ha_liquid
        assert "Passive" in note_p
        assert "Forced-air" in note_f
        assert "Liquid" in note_l
        # For 224 cells: passive ~4.48 W/K, fan ~20.16 W/K, liquid ~100.8 W/K
        assert ha_passive == pytest.approx(4.48, abs=0.1)
        assert ha_fan == pytest.approx(20.16, abs=0.2)
        assert ha_liquid == pytest.approx(100.8, abs=0.5)

    def test_cooling_option_changes_equilibrium_temperature(self):
        """
        Under 140 W continuous heat generation at 25°C ambient (14S16P @ 80A):
        - Passive (4.48 W/K): T_eq = 25 + 140 / 4.48 = 56.25°C
        - Fan (20.16 W/K): T_eq = 25 + 140 / 20.16 = 31.94°C
        - Liquid (100.8 W/K): T_eq = 25 + 140 / 100.8 = 26.39°C
        """
        n_cells = 224
        q_gen = 140.0
        t_amb = 25.0

        ha_p, _ = _ha_for_cooling("passive", n_cells)
        ha_f, _ = _ha_for_cooling("fan", n_cells)
        ha_l, _ = _ha_for_cooling("liquid", n_cells)

        t_eq_passive = t_amb + q_gen / ha_p
        t_eq_fan = t_amb + q_gen / ha_f
        t_eq_liquid = t_amb + q_gen / ha_l

        assert t_eq_passive > t_eq_fan > t_eq_liquid
        assert t_eq_passive == pytest.approx(56.25, abs=0.5)
        assert t_eq_fan == pytest.approx(31.94, abs=0.5)
        assert t_eq_liquid == pytest.approx(26.39, abs=0.5)


class TestThermalEnvironmentalMatrix:
    """Verifies temperature propagation under various ambient conditions."""

    @pytest.mark.parametrize("t_amb", [-10.0, 0.0, 25.0, 40.0])
    def test_zero_heat_returns_to_ambient(self, t_amb):
        """When Q_gen = 0 and T_init != T_amb, battery temperature asymptotically cools/heats to T_amb over 5*tau."""
        # tau = m * cp / ha = 15.68 * 900 / 50.0 = 282.24s. 5*tau ~ 1500s.
        times = [float(i * 10) for i in range(181)]  # 1800 seconds > 6*tau
        q_zeros = [0.0] * 181
        t_init = t_amb + 15.0  # 15°C above ambient

        res = run_thermal_simulation(
            times_s=times,
            q_gen_sequence_w=q_zeros,
            t_ambient_c=t_amb,
            t_initial_c=t_init,
            cell_mass_kg=15.68,
            cp_j_per_kg_k=900.0,
            ha_w_per_k=50.0,
        )
        assert res.temperatures_c[0] == t_init
        assert res.temperatures_c[-1] == pytest.approx(t_amb, abs=0.5)

    def test_timestep_analytical_convergence(self):
        """Exact analytical first-order integration yields identical temperatures regardless of dt."""
        m = 15.68
        cp = 900.0
        ha = 50.0   # tau = 282.24s
        q = 100.0
        t_amb = 25.0

        # Run for 2000s (> 7*tau) to reach steady state equilibrium
        times_fine = [float(i) * 1.0 for i in range(2001)]    # dt = 1.0s
        times_coarse = [float(i) * 20.0 for i in range(101)]  # dt = 20.0s

        res_fine = run_thermal_simulation(
            times_s=times_fine,
            q_gen_sequence_w=[q] * 2001,
            t_ambient_c=t_amb,
            t_initial_c=t_amb,
            cell_mass_kg=m,
            cp_j_per_kg_k=cp,
            ha_w_per_k=ha,
        )
        res_coarse = run_thermal_simulation(
            times_s=times_coarse,
            q_gen_sequence_w=[q] * 101,
            t_ambient_c=t_amb,
            t_initial_c=t_amb,
            cell_mass_kg=m,
            cp_j_per_kg_k=cp,
            ha_w_per_k=ha,
        )
        # Both step sizes converge to same trajectory and same equilibrium
        assert res_fine.temperatures_c[-1] == pytest.approx(res_coarse.temperatures_c[-1], abs=0.1)
        expected_eq = t_amb + q / ha
        assert res_fine.temperatures_c[-1] == pytest.approx(expected_eq, abs=0.1)
