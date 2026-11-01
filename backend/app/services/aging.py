"""
BattLab — Transparent Semi-Empirical Battery Aging & Degradation Service
========================================================================
Implements:
1. Charge throughput & Equivalent Full Cycle (EFC) accumulation.
2. Diffusional parabolic SEI growth cycle-aging capacity fade (Ah^0.5 / EFC^0.5).
3. Arrhenius temperature-accelerated aging kinetics.
4. Solid Electrolyte Interphase (SEI) film thickening resistance growth.
5. Calendar aging estimation (time & SOC-dependent).
6. Multi-cycle lifetime projection with explicit engineering limitations.

Mathematical Formulation:
--------------------------
1. Equivalent Full Cycles (EFC):
   EFC = Ah_throughput / (2 * Nominal_Capacity_Ah)
   where Ah_throughput = integral(|I_pack(t)| dt) / 3600.

2. Cycle-induced Capacity Fade (%):
   Delta_C_cycle(%) = A_cycle(T, C_rate) * (EFC)^z
   where z = 0.5 (diffusional SEI parabolic growth),
   A_cycle(T) = A_ref * exp( (-E_a / R) * (1/T_K - 1/T_ref_K) ).

3. Resistance Growth (%):
   Delta_R0(%) = k_R * Delta_C_cycle(%)
   where k_R ~= 1.75.

4. State of Health (SOH):
   SOH_C(%) = max(0.0, 100.0 - (Delta_C_cycle + Delta_C_cal))
   SOH_R(%) = 100.0 / (1.0 + Delta_R0 / 100.0)

Engineering Limitations & Scope:
--------------------------------
- Designed for secondary lithium-ion chemistries (NMC, NCA, LFP).
- Parabolic diffusional model reflects dominant negative electrode SEI growth.
- Does NOT model sudden lithium plating knee or mechanical electrode delamination.
- Short simulation runs represent incremental mission wear; lifetime projections
  are illustrative extrapolations, not experimental warranty guarantees.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

R_GAS = 8.31446261815324
T_REF_K = 298.15  # 25°C

# ── Chemistry-Specific Aging Parameters (Literature: Bloom, Safari, Schmalstieg)
CHEMISTRY_AGING_PROFILES: Dict[str, Dict[str, float]] = {
    "NMC": {
        "a_ref": 0.894,         # ~20% fade at 500 EFC (25°C, 1C)
        "z_exp": 0.50,          # Parabolic diffusional growth
        "e_a_j_per_mol": 30000.0,
        "k_resistance": 1.75,   # Resistance increases ~1.75x faster than capacity fades
        "cal_rate_per_day": 0.008, # ~2.5% per year at 25°C / 50% SOC
    },
    "NCA": {
        "a_ref": 0.950,         # ~21% fade at 500 EFC
        "z_exp": 0.50,
        "e_a_j_per_mol": 32000.0,
        "k_resistance": 1.90,
        "cal_rate_per_day": 0.009,
    },
    "LFP": {
        "a_ref": 0.400,         # ~20% fade at 2500 EFC
        "z_exp": 0.50,
        "e_a_j_per_mol": 25000.0,
        "k_resistance": 1.50,
        "cal_rate_per_day": 0.004, # ~1.2% per year
    },
    "DEFAULT": {
        "a_ref": 0.850,
        "z_exp": 0.50,
        "e_a_j_per_mol": 30000.0,
        "k_resistance": 1.75,
        "cal_rate_per_day": 0.008,
    },
}


def _get_aging_params(chemistry: str) -> Dict[str, float]:
    chem_clean = str(chemistry).upper().replace("CHEMISTRY.", "").strip()
    return CHEMISTRY_AGING_PROFILES.get(chem_clean, CHEMISTRY_AGING_PROFILES["DEFAULT"])


@dataclass
class AgingSimulationResult:
    """State of Health and degradation metrics for a simulation run."""
    # Throughput & EFC for this run
    run_throughput_ah: float
    run_efc: float
    
    # Cumulative totals (including prior committed history if any)
    cumulative_throughput_ah: float
    cumulative_efc: float
    
    # Degradation metrics
    capacity_fade_pct: float             # Total % loss of nominal capacity
    cycle_fade_pct: float = 0.0          # Cycle-induced % loss (EFC^z)
    calendar_fade_pct: float = 0.0       # Calendar-induced % loss (time & temp)
    resistance_growth_pct: float = 0.0   # % increase in R0
    soh_capacity_pct: float = 100.0      # Current Capacity SOH (100% = fresh)
    soh_resistance_pct: float = 100.0    # Current Resistance SOH (100% = fresh)
    actual_capacity_ah: float = 0.0      # Derated usable capacity
    actual_r0_ohm: float = 0.0           # Derated internal resistance
    
    # Lifetime projection
    projected_cycles_to_80pct: int = 1000 # Estimated cycles until 80% SOH at this stress level
    lifetime_trajectory: List[Dict[str, float]] = field(default_factory=list) # Points (cycle, soh_pct)
    
    # Transparency
    is_committed: bool = False           # True if committed to pack history; False for preview
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


def evaluate_simulation_aging(
    currents_a: List[float],
    times_s: List[float],
    nominal_capacity_ah: float,
    initial_r0_ohm: float,
    mean_temp_c: float,
    chemistry: str = "NMC",
    prior_cumulative_throughput_ah: float = 0.0,
    prior_cumulative_efc: float = 0.0,
    is_committed: bool = False,
    ambient_temp_c: float = 25.0,
) -> AgingSimulationResult:
    """
    Calculate incremental and cumulative aging from simulation telemetry.
    
    Parameters
    ----------
    currents_a                     : Pack currents [A]
    times_s                        : Time points [s]
    nominal_capacity_ah            : Pack nominal capacity [Ah]
    initial_r0_ohm                 : Fresh cell/pack internal resistance [Ohm]
    mean_temp_c                    : Operating average cell temperature [°C]
    chemistry                      : Cell chemistry enum or string (NMC, LFP, NCA)
    prior_cumulative_throughput_ah : Previously committed pack throughput [Ah]
    prior_cumulative_efc           : Previously committed pack cycles
    is_committed                   : Whether this run commits to pack operating history
    """
    params = _get_aging_params(chemistry)
    
    # 1. Integrate charge throughput: sum(|I| * dt) / 3600
    throughput_ah = 0.0
    for i in range(len(times_s) - 1):
        dt = times_s[i + 1] - times_s[i]
        i_curr = abs(currents_a[i])
        throughput_ah += (i_curr * dt) / 3600.0
        
    pack_cap = max(nominal_capacity_ah, 0.001)
    run_efc = throughput_ah / (2.0 * pack_cap)
    
    # Cumulative accounting
    total_throughput_ah = prior_cumulative_throughput_ah + throughput_ah
    total_efc = prior_cumulative_efc + run_efc
    
    # 2. Temperature acceleration factor: exp( (-E_a / R) * (1/T - 1/T_ref) )
    t_eval_k = max(240.0, min(350.0, mean_temp_c + 273.15))
    e_a = params["e_a_j_per_mol"]
    temp_factor = math.exp((-e_a / R_GAS) * ((1.0 / t_eval_k) - (1.0 / T_REF_K)))
    
    # 3. Cycle fade & Calendar fade
    a_ref = params["a_ref"]
    z = params["z_exp"]
    k_r = params["k_resistance"]
    cal_rate = params.get("cal_rate_per_day", 0.008)

    # Cycle fade from accumulated EFC
    cycle_fade_pct = max(0.0, a_ref * temp_factor * (total_efc ** z)) if total_efc > 0 else 0.0

    # Calendar fade from elapsed duration in days
    duration_days = max(0.0, (times_s[-1] - times_s[0]) / 86400.0) if len(times_s) > 1 else 0.0
    calendar_fade_pct = max(0.0, cal_rate * temp_factor * duration_days)

    # Combined capacity degradation and resistance growth
    total_fade_pct = min(100.0, max(0.0, cycle_fade_pct + calendar_fade_pct))
    res_growth_pct = min(400.0, max(0.0, total_fade_pct * k_r))

    # 4. State of Health (strictly bound [0%, 100%])
    soh_cap = max(0.0, min(100.0, 100.0 - total_fade_pct))
    soh_res = max(0.0, min(100.0, 100.0 / (1.0 + res_growth_pct / 100.0)))

    actual_cap = max(0.0, pack_cap * (soh_cap / 100.0))
    actual_r0 = max(0.0, initial_r0_ohm * (1.0 + res_growth_pct / 100.0))
    
    # 5. Projected cycles to 80% SOH (20% fade threshold)
    # 20.0 = a_ref * temp_factor * (EFC_80)^z  =>  EFC_80 = (20.0 / (a_ref * temp_factor))^(1/z)
    denom = max(1e-6, a_ref * temp_factor)
    projected_cycles_80 = int(round((20.0 / denom) ** (1.0 / z)))
    projected_cycles_80 = max(1, min(10000, projected_cycles_80))
    
    # 6. Illustrative multi-point lifetime trajectory (0 to 1.5x of projected 80% life)
    cycle_checkpoints = [
        0,
        int(projected_cycles_80 * 0.1),
        int(projected_cycles_80 * 0.25),
        int(projected_cycles_80 * 0.50),
        int(projected_cycles_80 * 0.75),
        projected_cycles_80,
        int(projected_cycles_80 * 1.25),
        int(projected_cycles_80 * 1.50),
    ]
    trajectory = []
    for cyc in sorted(list(set(cycle_checkpoints))):
        c_fade = min(100.0, a_ref * temp_factor * ((cyc if cyc > 0 else 0.0) ** z))
        trajectory.append({
            "cycle": cyc,
            "soh_pct": round(max(0.0, 100.0 - c_fade), 2),
            "resistance_factor": round(1.0 + (c_fade * k_r) / 100.0, 3),
        })
        
    assumptions = [
        f"Semi-empirical SEI diffusional growth model for {chemistry}: Delta_C = A(T) * EFC^{z:.2f}.",
        f"Arrhenius kinetic activation energy E_a = {e_a / 1000:.1f} kJ/mol with T_mean = {mean_temp_c:.1f}°C.",
        f"Resistance growth coupled to capacity loss with coefficient k_R = {k_r:.2f}.",
        "Simulation mode: " + ("COMMITTED TO PACK HISTORY" if is_committed else "PREVIEW ONLY (no permanent history applied)."),
    ]
    
    limitations = [
        "Short simulation runs represent incremental mission wear; lifetime projections are extrapolations.",
        "Model assumes continuous calendar/cycle operation under the simulated duty cycle.",
        "Sudden non-linear aging transitions (lithium plating knee) are not modelled.",
    ]
    
    return AgingSimulationResult(
        run_throughput_ah=round(throughput_ah, 4),
        run_efc=round(run_efc, 4),
        cumulative_throughput_ah=round(total_throughput_ah, 4),
        cumulative_efc=round(total_efc, 4),
        capacity_fade_pct=round(total_fade_pct, 4),
        cycle_fade_pct=round(cycle_fade_pct, 4),
        calendar_fade_pct=round(calendar_fade_pct, 4),
        resistance_growth_pct=round(res_growth_pct, 4),
        soh_capacity_pct=round(soh_cap, 2),
        soh_resistance_pct=round(soh_res, 2),
        actual_capacity_ah=round(actual_cap, 3),
        actual_r0_ohm=round(actual_r0, 6),
        projected_cycles_to_80pct=projected_cycles_80,
        lifetime_trajectory=trajectory,
        is_committed=is_committed,
        assumptions=assumptions,
        limitations=limitations,
    )

