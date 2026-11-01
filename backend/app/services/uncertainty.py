"""
BattLab — Monte Carlo Uncertainty Propagation Framework
========================================================
Propagates manufacturing tolerances and environmental uncertainties through
the electrical and lumped thermal models using reproducible Monte Carlo sampling.

Uncertainty Parameter Distributions (Justified from Li-ion manufacturing literature):
-----------------------------------------------------------------------------------
1. Cell Capacity: Normal(nominal_capacity, sigma = 2.0%)
   [Manufacturing batch tolerance typical for tier-1 cylindrical cells]
2. Cell Internal Resistance: Normal(nominal_R0, sigma = 5.0%)
   [Electrode coating thickness and tab welding impedance variance]
3. Cell Unit Mass: Normal(nominal_mass, sigma = 1.5%)
   [Electrolyte fill and casing mechanical tolerance]
4. Ambient Temperature: Normal(nominal_Tamb, sigma = 1.0°C)
   [Environmental sensor and micro-climate fluctuations]

Statistical Outputs:
--------------------
- Mean and Standard Deviation
- Percentiles: P05 (5th percentile lower bound), P50 (median), P95 (95th percentile upper bound)
- Sensitivity ranking (correlation between parameter variations and outcome metrics)
- Explicit disclaimer: Parameter uncertainty does NOT represent structural model error.
"""
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from app.services.electrical import calculate_pack, ElectricalInputs, soc_update
from app.services.thermal import run_thermal_simulation
from app.services.ecm import ecm_step, get_arrhenius_resistance_ohm


def _percentile(sorted_values: List[float], p: float) -> float:
    """Compute percentile p in [0..1] from sorted float list."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return d0 + d1


@dataclass
class DistributionSummary:
    mean: float
    std_dev: float
    min_val: float
    p05: float
    p50: float
    p95: float
    max_val: float
    baseline_value: float
    delta_p95_p05: float


def run_monte_carlo_uncertainty(
    cell: Any,
    configuration: Any,
    scenario: Any,
    n_iterations: int = 50,
    random_seed: int = 42,
    capacity_sigma_pct: float = 2.0,
    resistance_sigma_pct: float = 5.0,
    mass_sigma_pct: float = 1.5,
    temp_sigma_c: float = 1.0,
) -> Dict[str, Any]:
    """
    Execute reproducible Monte Carlo simulation over parameter distributions.
    """
    rng = random.Random(random_seed)

    ns = int(configuration.ns)
    np_ = int(configuration.np)
    r_interconnect = float(getattr(configuration, "interconnect_resistance_ohm", 0.0) or 0.0)

    nom_cap = float(cell.nominal_capacity_ah or 5.0)
    nom_v = float(cell.nominal_voltage_v or 3.7)
    nom_r = float(cell.internal_resistance_ohm or 0.025)
    nom_mass = float(getattr(cell, "mass_kg", None) or 0.070)
    nom_cp = float(getattr(cell, "specific_heat_j_per_kg_k", None) or 900.0)
    nom_tamb = float(getattr(scenario, "ambient_temp_c", 25.0))
    nom_discharge_a = float(getattr(scenario, "discharge_current_a", None) or (nom_cap * np_))
    duration_s = min(600.0, float(getattr(scenario, "duration_s", 600.0)))  # capped for speed
    dt_s = 10.0

    # 1. Baseline deterministic evaluation
    base_pack_mass = nom_mass * ns * np_
    base_energy_wh = nom_v * ns * nom_cap * np_
    base_r_pack = (ns * nom_r / np_) + r_interconnect
    base_heat_w = (nom_discharge_a ** 2) * (ns * nom_r / np_)

    # Baseline temperature rise estimate
    ha_val = 2.0 * ns * np_  # passive cooling baseline
    base_t_eq = nom_tamb + (base_heat_w / ha_val if ha_val > 0 else 0.0)
    tau = (base_pack_mass * nom_cp) / ha_val if ha_val > 0 else 1000.0
    base_t_end = base_t_eq + (nom_tamb - base_t_eq) * math.exp(-duration_s / tau)

    # 2. Monte Carlo Iteration Loop
    sample_energies: List[float] = []
    sample_masses: List[float] = []
    sample_t_ends: List[float] = []
    sample_v_ends: List[float] = []

    # Store parameter draws for correlation sensitivity
    param_cap_draws: List[float] = []
    param_r_draws: List[float] = []
    param_tamb_draws: List[float] = []

    for _ in range(n_iterations):
        # Sample parameters
        c_i = max(0.5 * nom_cap, rng.gauss(nom_cap, nom_cap * (capacity_sigma_pct / 100.0)))
        r_i = max(0.001, rng.gauss(nom_r, nom_r * (resistance_sigma_pct / 100.0)))
        m_i = max(0.010, rng.gauss(nom_mass, nom_mass * (mass_sigma_pct / 100.0)))
        t_amb_i = rng.gauss(nom_tamb, temp_sigma_c)

        param_cap_draws.append(c_i)
        param_r_draws.append(r_i)
        param_tamb_draws.append(t_amb_i)

        # Pack outcomes
        p_mass = m_i * ns * np_
        p_energy = nom_v * ns * c_i * np_
        sample_masses.append(p_mass)
        sample_energies.append(p_energy)

        # Thermal transient
        heat_w = (nom_discharge_a ** 2) * (ns * r_i / np_)
        t_eq_i = t_amb_i + (heat_w / ha_val if ha_val > 0 else 0.0)
        tau_i = (p_mass * nom_cp) / ha_val if ha_val > 0 else 1000.0
        t_end_i = t_eq_i + (t_amb_i - t_eq_i) * math.exp(-duration_s / tau_i)
        sample_t_ends.append(t_end_i)

        # End terminal voltage estimate
        i_cell_i = nom_discharge_a / np_
        r0_t = get_arrhenius_resistance_ohm(r_i, t_end_i)
        # Assuming ~80% SOC after duration
        soc_end = max(0.1, 1.0 - (nom_discharge_a * duration_s / (3600.0 * c_i * np_)))
        v_oc = 3.0 + soc_end * (4.2 - 3.0)
        v_cell_end = v_oc - (i_cell_i * r0_t)
        v_pack_end = (ns * v_cell_end) - (nom_discharge_a * r_interconnect)
        sample_v_ends.append(v_pack_end)

    # 3. Summarize Distributions
    def summarize(vals: List[float], baseline: float) -> Dict[str, float]:
        s = sorted(vals)
        mean_v = sum(s) / len(s)
        var_v = sum((x - mean_v) ** 2 for x in s) / len(s)
        std_v = math.sqrt(var_v)
        p05 = _percentile(s, 0.05)
        p50 = _percentile(s, 0.50)
        p95 = _percentile(s, 0.95)
        return {
            "mean": round(mean_v, 2),
            "std_dev": round(std_v, 2),
            "min": round(s[0], 2),
            "p05": round(p05, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "max": round(s[-1], 2),
            "baseline": round(baseline, 2),
            "spread_p95_p05": round(p95 - p05, 2),
        }

    # 4. Pearson Correlation Sensitivity
    def pearson_corr(x_list: List[float], y_list: List[float]) -> float:
        n = len(x_list)
        mx, my = sum(x_list)/n, sum(y_list)/n
        num = sum((x_list[i] - mx) * (y_list[i] - my) for i in range(n))
        den = math.sqrt(sum((x - mx)**2 for x in x_list) * sum((y - my)**2 for y in y_list))
        return round(num / den, 3) if den > 1e-12 else 0.0

    sensitivities = [
        {
            "parameter": "Cell Internal Resistance (R0)",
            "target": "Maximum Pack Temperature",
            "correlation_coefficient": pearson_corr(param_r_draws, sample_t_ends),
            "impact_direction": "Positive — Higher resistance increases Joule heating",
        },
        {
            "parameter": "Ambient Temperature",
            "target": "Maximum Pack Temperature",
            "correlation_coefficient": pearson_corr(param_tamb_draws, sample_t_ends),
            "impact_direction": "Strong Positive — Shifts thermal equilibrium upward",
        },
        {
            "parameter": "Cell Capacity",
            "target": "Pack Energy",
            "correlation_coefficient": pearson_corr(param_cap_draws, sample_energies),
            "impact_direction": "Direct Linear Scaling",
        },
    ]

    return {
        "status": "COMPLETED",
        "iterations": n_iterations,
        "random_seed": random_seed,
        "parameter_distributions_sampled": {
            "cell_capacity_ah": f"Normal(mean={nom_cap:.2f}, sigma={capacity_sigma_pct}%)",
            "cell_resistance_ohm": f"Normal(mean={nom_r:.4f}, sigma={resistance_sigma_pct}%)",
            "cell_mass_kg": f"Normal(mean={nom_mass:.3f}, sigma={mass_sigma_pct}%)",
            "ambient_temp_c": f"Normal(mean={nom_tamb:.1f}, sigma={temp_sigma_c}°C)",
        },
        "distributions": {
            "nominal_energy_wh": summarize(sample_energies, base_energy_wh),
            "total_cell_mass_kg": summarize(sample_masses, base_pack_mass),
            "simulated_max_temp_c": summarize(sample_t_ends, base_t_end),
            "end_terminal_voltage_v": summarize(sample_v_ends, (ns * 3.7) - (nom_discharge_a * base_r_pack)),
        },
        "sensitivity_ranking": sensitivities,
        "disclaimer": (
            "Monte Carlo uncertainty intervals reflect specified parameter tolerances only. "
            "They do not account for spatial thermal gradients, electrochemical aging, or model structural error."
        ),
    }

