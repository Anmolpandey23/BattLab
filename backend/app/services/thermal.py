"""
BattLab — Lumped Thermal Simulation Engine

Implements a first-order lumped thermal model per the equation:
  m × cp × dT/dt = Q_generated − Q_removed
  Q_removed = hA × (T − T_ambient)

Exact first-order update (analytical for constant Q and hA per step):
  T_eq   = T_ambient + Q_gen / hA
  T_next = T_eq + (T_current − T_eq) × exp(−hA × dt / (m × cp))

See docs/ENGINEERING_MODELS.md for full derivation and assumptions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ThermalInputs:
    """Inputs for the lumped thermal model."""
    # Pack-level lumped mass
    cell_mass_kg: float               # kg — total thermal mass being modelled
    cp_j_per_kg_k: float              # J/kg/K — specific heat capacity
    ha_w_per_k: float                 # W/K — effective thermal conductance to ambient
    q_gen_w: float                    # W — heat generation rate (from electrical model)
    t_current_c: float                # °C — current temperature
    t_ambient_c: float                # °C — ambient temperature
    dt_s: float                       # s — time step


@dataclass
class ThermalStep:
    t_current_c: float
    t_next_c: float
    t_equilibrium_c: float
    q_gen_w: float
    q_removed_w: float
    ha_w_per_k: float


def thermal_step(inputs: ThermalInputs) -> ThermalStep:
    """
    Compute the next temperature using the exact first-order analytical update.

    Handles the degenerate case hA = 0 (no cooling) with a simple Euler step.
    """
    if inputs.cell_mass_kg <= 0:
        raise ValueError("Thermal mass (cell_mass_kg) must be positive")
    if inputs.cp_j_per_kg_k <= 0:
        raise ValueError("Specific heat capacity must be positive")
    if inputs.dt_s <= 0:
        raise ValueError("Time step must be positive")

    ha = max(0.0, inputs.ha_w_per_k)
    q = inputs.q_gen_w
    T = inputs.t_current_c
    T_amb = inputs.t_ambient_c
    m_cp = inputs.cell_mass_kg * inputs.cp_j_per_kg_k

    if ha < 1e-9:
        # No cooling: dT/dt = Q / (m × cp)
        T_next = T + (q / m_cp) * inputs.dt_s
        T_eq = float("inf")  # no equilibrium without cooling
        q_removed = 0.0
    else:
        T_eq = T_amb + q / ha
        tau = m_cp / ha
        T_next = T_eq + (T - T_eq) * math.exp(-inputs.dt_s / tau)
        q_removed = ha * (T - T_amb)

    return ThermalStep(
        t_current_c=T,
        t_next_c=T_next,
        t_equilibrium_c=T_eq if ha >= 1e-9 else T,
        q_gen_w=q,
        q_removed_w=q_removed,
        ha_w_per_k=ha,
    )


@dataclass
class ThermalSimulationResult:
    temperatures_c: list[float]
    q_generated_w: list[float]
    q_removed_w: list[float]
    max_temp_c: float
    min_temp_c: float
    equilibrium_temp_c: Optional[float]
    assumptions: list[str]
    warnings: list[str]


def run_thermal_simulation(
    times_s: list[float],
    q_gen_sequence_w: list[float],        # heat generation per step
    t_ambient_c: float,
    t_initial_c: float,
    cell_mass_kg: float,
    cp_j_per_kg_k: float,
    ha_w_per_k: float,
    t_max_limit_c: Optional[float] = None,
    t_min_limit_c: Optional[float] = None,
) -> ThermalSimulationResult:
    """
    Run a lumped thermal simulation over a time series.

    Parameters
    ----------
    times_s         : list of time points [s]
    q_gen_sequence_w: heat generation for each interval [W]
    t_ambient_c     : ambient temperature [°C]
    t_initial_c     : initial cell temperature [°C]
    cell_mass_kg    : total lumped thermal mass [kg]
    cp_j_per_kg_k   : specific heat capacity [J/kg/K]
    ha_w_per_k      : effective thermal conductance [W/K]
    t_max_limit_c   : optional maximum temperature limit [°C]
    t_min_limit_c   : optional minimum temperature limit [°C]
    """
    assumptions: list[str] = [
        "Single-node (lumped) thermal model. Does not predict spatial temperature distribution.",
        "Heat generation assumed uniform across all cells at each time step.",
        "Thermal conductance hA assumed constant throughout simulation.",
        "Specific heat capacity assumed constant with temperature.",
    ]
    warnings_out: list[str] = []

    if not times_s:
        return ThermalSimulationResult([], [], [], 0, 0, None, assumptions, ["No time series provided"])

    T = t_initial_c
    temps = [T]
    q_gens = []
    q_removeds = []

    for i in range(len(times_s) - 1):
        dt = times_s[i + 1] - times_s[i]
        if dt <= 0:
            continue
        q_now = q_gen_sequence_w[i] if i < len(q_gen_sequence_w) else 0.0
        step = thermal_step(ThermalInputs(
            cell_mass_kg=cell_mass_kg,
            cp_j_per_kg_k=cp_j_per_kg_k,
            ha_w_per_k=ha_w_per_k,
            q_gen_w=q_now,
            t_current_c=T,
            t_ambient_c=t_ambient_c,
            dt_s=dt,
        ))
        T = step.t_next_c
        temps.append(T)
        q_gens.append(q_now)
        q_removeds.append(step.q_removed_w)

    max_t = max(temps)
    min_t = min(temps)

    if t_max_limit_c and max_t > t_max_limit_c:
        warnings_out.append(
            f"Modelled maximum temperature {max_t:.1f}°C exceeds configured cell limit "
            f"{t_max_limit_c:.1f}°C. This is a single-node estimate — actual internal "
            "temperatures may be higher."
        )
    if t_min_limit_c and min_t < t_min_limit_c:
        warnings_out.append(
            f"Modelled minimum temperature {min_t:.1f}°C is below configured cell limit "
            f"{t_min_limit_c:.1f}°C."
        )

    # Equilibrium temperature at final operating point
    eq_temp = None
    if ha_w_per_k > 1e-9 and q_gen_sequence_w:
        q_final = q_gen_sequence_w[-1]
        eq_temp = t_ambient_c + q_final / ha_w_per_k

    if ha_w_per_k < 1e-9:
        assumptions.append(
            "Thermal conductance hA = 0: no heat removal modelled. "
            "Temperature rises indefinitely — passive cooling not configured."
        )

    return ThermalSimulationResult(
        temperatures_c=temps,
        q_generated_w=q_gens,
        q_removed_w=q_removeds,
        max_temp_c=round(max_t, 3),
        min_temp_c=round(min_t, 3),
        equilibrium_temp_c=round(eq_temp, 3) if eq_temp else None,
        assumptions=assumptions,
        warnings=warnings_out,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Multi-Node Thermal Network Engine (Core — Surface — Cold Plate)
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class MultiNodeThermalInputs:
    """
    Inputs for 3-node pack thermal network:
    Node 1 (Core): Jelly-roll / internal active electrode material.
    Node 2 (Surface): Cell steel/aluminum casing and tabs.
    Node 3 (Plate): Cold plate / heat sink / enclosure conduction buffer.
    """
    c_core_j_per_k: float        # J/K — Heat capacity of core
    c_surface_j_per_k: float     # J/K — Heat capacity of cell casing
    c_plate_j_per_k: float       # J/K — Heat capacity of cold plate / chassis
    g_cs_w_per_k: float          # W/K — Conductance from Core to Surface
    g_sp_w_per_k: float          # W/K — Conductance from Surface to Plate
    g_pa_w_per_k: float          # W/K — Conductance from Plate to Ambient (hA)
    q_core_w: float              # W — Heat generated inside Core
    q_surface_w: float           # W — Heat generated at Surface / Interconnects
    q_plate_w: float             # W — Heat generated in plate (auxiliary)
    t_core_c: float              # °C — Current Core temperature
    t_surface_c: float           # °C — Current Surface temperature
    t_plate_c: float             # °C — Current Plate temperature
    t_ambient_c: float           # °C — Ambient temperature
    dt_s: float                  # s — Time step


@dataclass
class MultiNodeThermalStep:
    t_core_next_c: float
    t_surface_next_c: float
    t_plate_next_c: float
    q_removed_w: float
    delta_u_joules: float        # Internal energy change in step


def multi_node_thermal_step(inputs: MultiNodeThermalInputs) -> MultiNodeThermalStep:
    """
    Compute next multi-node temperatures using unconditionally stable implicit Euler.
    
    Differential Equations:
      C_c * dT_c/dt = Q_c - G_cs * (T_c - T_s)
      C_s * dT_s/dt = Q_s + G_cs * (T_c - T_s) - G_sp * (T_s - T_p)
      C_p * dT_p/dt = Q_p + G_sp * (T_s - T_p) - G_pa * (T_p - T_amb)
      
    Discretized implicitly at step k+1:
      [ C_c + dt*G_cs,       -dt*G_cs,                 0            ] [ T_c ]   [ C_c * T_c0 + dt * Q_c ]
      [ -dt*G_cs,      C_s + dt*(G_cs + G_sp),     -dt*G_sp         ] [ T_s ] = [ C_s * T_s0 + dt * Q_s ]
      [    0,                -dt*G_sp,        C_p + dt*(G_sp + G_pa)] [ T_p ]   [ C_p * T_p0 + dt * (Q_p + G_pa * T_amb) ]
    """
    dt = inputs.dt_s
    if dt <= 0:
        raise ValueError("Time step dt_s must be positive")
    if inputs.c_core_j_per_k <= 0 or inputs.c_surface_j_per_k <= 0 or inputs.c_plate_j_per_k <= 0:
        raise ValueError("Node heat capacities must be positive")

    cc = inputs.c_core_j_per_k
    cs = inputs.c_surface_j_per_k
    cp = inputs.c_plate_j_per_k

    g_cs = max(0.0, inputs.g_cs_w_per_k)
    g_sp = max(0.0, inputs.g_sp_w_per_k)
    g_pa = max(0.0, inputs.g_pa_w_per_k)

    # Matrix elements (tridiagonal symmetric M = C - dt * K)
    m11 = cc + dt * g_cs
    m12 = -dt * g_cs
    m13 = 0.0

    m21 = -dt * g_cs
    m22 = cs + dt * (g_cs + g_sp)
    m23 = -dt * g_sp

    m31 = 0.0
    m32 = -dt * g_sp
    m33 = cp + dt * (g_sp + g_pa)

    # Right-hand side
    r1 = cc * inputs.t_core_c + dt * inputs.q_core_w
    r2 = cs * inputs.t_surface_c + dt * inputs.q_surface_w
    r3 = cp * inputs.t_plate_c + dt * (inputs.q_plate_w + g_pa * inputs.t_ambient_c)

    # Solve 3x3 system via standard forward elimination / back-substitution
    # Row 2 elimination using Row 1:
    f21 = m21 / m11
    m22_prime = m22 - f21 * m12
    r2_prime = r2 - f21 * r1

    # Row 3 elimination using Row 2:
    f32 = m32 / m22_prime
    m33_prime = m33 - f32 * m23
    r3_prime = r3 - f32 * r2_prime

    # Back-substitution:
    t_p_next = r3_prime / m33_prime
    t_s_next = (r2_prime - m23 * t_p_next) / m22_prime
    t_c_next = (r1 - m12 * t_s_next) / m11

    q_removed = g_pa * (t_p_next - inputs.t_ambient_c)
    delta_u = (
        cc * (t_c_next - inputs.t_core_c) +
        cs * (t_s_next - inputs.t_surface_c) +
        cp * (t_p_next - inputs.t_plate_c)
    )

    return MultiNodeThermalStep(
        t_core_next_c=t_c_next,
        t_surface_next_c=t_s_next,
        t_plate_next_c=t_p_next,
        q_removed_w=q_removed,
        delta_u_joules=delta_u,
    )


@dataclass
class MultiNodeThermalResult:
    times_s: list[float]
    t_core_c: list[float]
    t_surface_c: list[float]
    t_plate_c: list[float]
    max_core_temp_c: float
    max_surface_temp_c: float
    max_plate_temp_c: float
    max_gradient_c: float          # Peak (T_core - T_surface)
    q_generated_total_j: float
    q_removed_total_j: float
    energy_conservation_residual_j: float
    assumptions: list[str]
    warnings: list[str]


def run_multi_node_thermal_simulation(
    times_s: list[float],
    q_gen_sequence_w: list[float],
    t_ambient_c: float,
    t_initial_c: float,
    total_cell_mass_kg: float,
    cell_count: int,
    cp_j_per_kg_k: float,
    ha_w_per_k: float,
    t_max_limit_c: Optional[float] = None,
) -> MultiNodeThermalResult:
    """
    Run 3-node thermal simulation over current profile time-steps.
    """
    assumptions = [
        "Multi-node thermal network active: 3-Node Core-Surface-Plate model.",
        "Node 1 (Core): Jelly roll active electrode material (70% of cell thermal mass). Receives 85% internal Joule & polarization dissipation.",
        "Node 2 (Surface): Cell casing and terminal tabs (30% of cell thermal mass; Core + Surface = 100% of cell mass). Receives 15% loss and interconnect heating.",
        "Node 3 (Cold Plate): External cold plate & chassis conduction buffer (15% of cell thermal mass equivalent). Convects to ambient via system hA.",
        "Unconditionally stable implicit Euler time-integration with strict internal energy conservation.",
    ]
    warnings_out = []

    if not times_s:
        return MultiNodeThermalResult(
            times_s=[], t_core_c=[], t_surface_c=[], t_plate_c=[],
            max_core_temp_c=0.0, max_surface_temp_c=0.0, max_plate_temp_c=0.0,
            max_gradient_c=0.0, q_generated_total_j=0.0, q_removed_total_j=0.0,
            energy_conservation_residual_j=0.0, assumptions=assumptions,
            warnings=["No time series provided"],
        )

    # Calibrated physical node capacitances
    # Cell internal partition: Core (70%) + Surface casing/tabs (30%) = 100% of cell thermal mass.
    # Cold plate buffer: External hardware thermal capacity (15% of cell thermal mass equivalent).
    c_cell_total = total_cell_mass_kg * cp_j_per_kg_k
    c_core = 0.70 * c_cell_total
    c_surf = 0.30 * c_cell_total
    c_plate = 0.15 * c_cell_total

    # Conductances: radial core-to-surface ~1.8 W/K per 21700 cell
    g_cs = cell_count * 1.80
    g_sp = cell_count * 3.20  # Surface to thermal interface pad
    g_pa = max(0.1, ha_w_per_k)

    t_c = t_initial_c
    t_s = t_initial_c
    t_p = t_initial_c

    t_core_series = [t_c]
    t_surf_series = [t_s]
    t_plate_series = [t_p]

    total_q_in_j = 0.0
    total_q_out_j = 0.0

    for i in range(len(times_s) - 1):
        dt = times_s[i + 1] - times_s[i]
        if dt <= 0:
            continue
        q_tot = q_gen_sequence_w[i] if i < len(q_gen_sequence_w) else 0.0
        q_c = 0.85 * q_tot
        q_s = 0.15 * q_tot
        q_p = 0.0

        step = multi_node_thermal_step(MultiNodeThermalInputs(
            c_core_j_per_k=c_core,
            c_surface_j_per_k=c_surf,
            c_plate_j_per_k=c_plate,
            g_cs_w_per_k=g_cs,
            g_sp_w_per_k=g_sp,
            g_pa_w_per_k=g_pa,
            q_core_w=q_c,
            q_surface_w=q_s,
            q_plate_w=q_p,
            t_core_c=t_c,
            t_surface_c=t_s,
            t_plate_c=t_p,
            t_ambient_c=t_ambient_c,
            dt_s=dt,
        ))

        t_c = step.t_core_next_c
        t_s = step.t_surface_next_c
        t_p = step.t_plate_next_c

        t_core_series.append(t_c)
        t_surf_series.append(t_s)
        t_plate_series.append(t_p)

        total_q_in_j += q_tot * dt
        total_q_out_j += step.q_removed_w * dt

    delta_u_total_j = (
        c_core * (t_c - t_initial_c) +
        c_surf * (t_s - t_initial_c) +
        c_plate * (t_p - t_initial_c)
    )
    residual_j = abs(delta_u_total_j - (total_q_in_j - total_q_out_j))

    max_c = max(t_core_series)
    max_s = max(t_surf_series)
    max_p = max(t_plate_series)
    max_grad = max(c - s for c, s in zip(t_core_series, t_surf_series))

    if t_max_limit_c and max_c > t_max_limit_c:
        warnings_out.append(
            f"Multi-node internal core peak {max_c:.1f}°C exceeds cell maximum operating "
            f"limit {t_max_limit_c:.1f}°C (surface was {max_s:.1f}°C, internal gradient {max_grad:.1f}°C)."
        )

    return MultiNodeThermalResult(
        times_s=times_s,
        t_core_c=[round(t, 2) for t in t_core_series],
        t_surface_c=[round(t, 2) for t in t_surf_series],
        t_plate_c=[round(t, 2) for t in t_plate_series],
        max_core_temp_c=round(max_c, 3),
        max_surface_temp_c=round(max_s, 3),
        max_plate_temp_c=round(max_p, 3),
        max_gradient_c=round(max_grad, 3),
        q_generated_total_j=round(total_q_in_j, 2),
        q_removed_total_j=round(total_q_out_j, 2),
        energy_conservation_residual_j=round(residual_j, 6),
        assumptions=assumptions,
        warnings=warnings_out,
    )

