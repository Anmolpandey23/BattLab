"""
BattLab — Electrical Calculation Service

All engineering calculations for pack topology, energy, resistance, current.
Equations and assumptions are documented in docs/ENGINEERING_MODELS.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ElectricalInputs:
    """Validated inputs for electrical calculations."""
    ns: int                          # series cell count
    np: int                          # parallel cell count
    v_cell_nominal: float            # V
    ah_cell: float                   # Ah
    r_cell_ohm: Optional[float]      # Ohm; None = unknown
    r_interconnect_ohm: float = 0.0  # Ohm total busbar/interconnect
    i_pack_a: Optional[float] = None # A; pack-level current (positive = discharge)
    usable_soc_window: float = 0.80  # fraction
    v_cell_min: Optional[float] = None
    v_cell_max: Optional[float] = None
    max_continuous_a: Optional[float] = None  # cell rating
    max_peak_a: Optional[float] = None


@dataclass
class PackSummary:
    """Calculated pack-level electrical metrics."""
    nominal_voltage_v: float
    max_voltage_v: Optional[float]
    min_voltage_v: Optional[float]
    capacity_ah: float
    nominal_energy_wh: float
    usable_energy_wh: Optional[float]
    total_cells: int
    r_pack_ohm: Optional[float]      # simplified equivalent resistance
    i_cell_a: Optional[float]        # per-cell current (equal sharing)
    p_loss_w: Optional[float]        # pack ohmic loss
    q_cell_w: Optional[float]        # per-cell heat generation
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def calculate_pack(inputs: ElectricalInputs) -> PackSummary:
    """
    Calculate pack-level electrical parameters.

    Equations used (see ENGINEERING_MODELS.md):
      V_nominal = Ns × V_cell_nominal
      Ah_pack   = Np × Ah_cell
      E_nominal = V_nominal × Ah_pack   [Wh]
      R_pack    = Ns × R_cell / Np  (matched cells, equal sharing)
      I_cell    = I_pack / Np
      P_loss    = I_pack² × R_pack
      Q_cell    = I_cell² × R_cell
    """
    if inputs.ns < 1 or inputs.np < 1:
        raise ValueError("Series and parallel counts must be >= 1")
    if inputs.v_cell_nominal <= 0:
        raise ValueError("Cell nominal voltage must be positive")
    if inputs.ah_cell <= 0:
        raise ValueError("Cell capacity must be positive")

    assumptions: list[str] = []
    warnings: list[str] = []

    v_nominal = inputs.ns * inputs.v_cell_nominal
    v_max = (inputs.ns * inputs.v_cell_max) if inputs.v_cell_max else None
    v_min = (inputs.ns * inputs.v_cell_min) if inputs.v_cell_min else None
    ah_pack = inputs.np * inputs.ah_cell
    e_nominal = v_nominal * ah_pack  # Wh

    # Usable energy estimate
    usable_energy: Optional[float] = None
    if inputs.v_cell_min and inputs.v_cell_max:
        # Voltage-weighted usable window approximation
        v_usable_mid = 0.5 * (inputs.v_cell_min + inputs.v_cell_max)
        # Simple linear interpolation assumption
        usable_energy = inputs.usable_soc_window * e_nominal
        assumptions.append(
            f"Usable energy estimated as {inputs.usable_soc_window*100:.0f}% of nominal "
            "energy using configured SOC window. This is a sizing approximation."
        )
    elif inputs.usable_soc_window < 1.0:
        usable_energy = inputs.usable_soc_window * e_nominal
        assumptions.append(
            f"Usable energy estimated as {inputs.usable_soc_window*100:.0f}% of nominal "
            "energy. Cell min/max voltage limits not supplied — window is indicative only."
        )
    else:
        warnings.append(
            "Usable energy cannot be estimated: cell voltage limits not supplied and "
            "usable SOC window is 1.0 (100%). Verify with cell datasheet."
        )

    # Resistance
    r_pack: Optional[float] = None
    i_cell: Optional[float] = None
    p_loss: Optional[float] = None
    q_cell: Optional[float] = None

    if inputs.r_cell_ohm is not None:
        r_series_string = inputs.ns * inputs.r_cell_ohm
        r_pack = r_series_string / inputs.np + inputs.r_interconnect_ohm
        assumptions.append(
            "Pack resistance uses matched-cell, equal-current-sharing approximation. "
            "Real pack resistance depends on cell variation, tab/interconnect geometry and temperature."
        )
        if inputs.i_pack_a is not None:
            i_cell = inputs.i_pack_a / inputs.np
            p_loss = (inputs.i_pack_a ** 2) * r_pack
            q_cell = (i_cell ** 2) * inputs.r_cell_ohm
    else:
        warnings.append(
            "Cell internal resistance not supplied. Pack resistance, ohmic loss "
            "and cell heat generation cannot be calculated."
        )

    # Current warnings
    if inputs.r_cell_ohm is not None and inputs.i_pack_a is not None:
        i_cell_val = inputs.i_pack_a / inputs.np
        if inputs.max_continuous_a and i_cell_val > inputs.max_continuous_a:
            warnings.append(
                f"Per-cell current {i_cell_val:.2f} A exceeds rated continuous limit "
                f"{inputs.max_continuous_a:.2f} A. Verify configuration."
            )
        if inputs.max_peak_a and i_cell_val > inputs.max_peak_a:
            warnings.append(
                f"Per-cell current {i_cell_val:.2f} A exceeds rated peak limit "
                f"{inputs.max_peak_a:.2f} A."
            )

    return PackSummary(
        nominal_voltage_v=round(v_nominal, 4),
        max_voltage_v=round(v_max, 4) if v_max else None,
        min_voltage_v=round(v_min, 4) if v_min else None,
        capacity_ah=round(ah_pack, 4),
        nominal_energy_wh=round(e_nominal, 4),
        usable_energy_wh=round(usable_energy, 4) if usable_energy else None,
        total_cells=inputs.ns * inputs.np,
        r_pack_ohm=round(r_pack, 6) if r_pack is not None else None,
        i_cell_a=round(i_cell, 4) if i_cell is not None else None,
        p_loss_w=round(p_loss, 4) if p_loss is not None else None,
        q_cell_w=round(q_cell, 6) if q_cell is not None else None,
        assumptions=assumptions,
        warnings=warnings,
    )


def soc_update(
    soc: float,
    i_cell_a: float,      # positive = discharge
    dt_s: float,
    ah_cell: float,
    efficiency: float = 1.0,
) -> float:
    """
    Coulomb counting SOC update.

    dSOC = -I_cell × dt / (3600 × Ah_cell) for discharge.
    Efficiency η applied to charge only (η < 1 means more charge input needed).
    SOC is clamped to [0, 1].

    Sign convention: positive I = discharge → SOC decreases.
    """
    if ah_cell <= 0:
        raise ValueError("Cell capacity must be positive")
    if dt_s <= 0:
        raise ValueError("Time step must be positive")
    soc_change = -(i_cell_a * dt_s) / (3600.0 * ah_cell)
    if i_cell_a < 0:
        # Charging — apply efficiency
        soc_change *= efficiency
    new_soc = soc + soc_change
    return max(0.0, min(1.0, new_soc))


def generate_current_profile(
    profile_type: str,
    duration_s: float,
    dt_s: float,
    base_current_a: float,
) -> list[tuple[float, float]]:
    """
    Generate a synthetic current profile (t_s, I_pack_A).

    Profiles are clearly synthetic for illustrative purposes.
    Positive current = discharge.
    """
    import numpy as np

    t = np.arange(0, duration_s + dt_s, dt_s)
    n = len(t)
    I = np.zeros(n)

    if profile_type == "steady_cruise":
        # Constant discharge
        I[:] = base_current_a
        profile_note = "Steady constant-discharge profile (illustrative)."

    elif profile_type == "mixed":
        # Simple mixed: cruise + acceleration pulses
        I[:] = base_current_a * 0.6
        # Add 5 acceleration pulses
        pulse_count = 5
        pulse_duration = int(20 / dt_s)
        spacing = n // (pulse_count + 1)
        for k in range(1, pulse_count + 1):
            start = k * spacing
            end = min(start + pulse_duration, n)
            I[start:end] = base_current_a * 1.8
        profile_note = "Mixed cruise + acceleration profile (illustrative synthetic data)."

    elif profile_type == "high_load":
        I[:] = base_current_a * 1.5
        # Occasional brief rest
        rest_duration = int(10 / dt_s)
        for k in range(3, n, n // 5):
            end = min(k + rest_duration, n)
            I[k:end] = 0.0
        profile_note = "High-load profile with brief rests (illustrative synthetic data)."

    elif profile_type == "rest":
        I[:] = 0.0
        profile_note = "Rest profile with zero discharge current (illustrative)."

    elif profile_type == "regen":
        I[:] = -abs(base_current_a) * 0.5
        profile_note = "Regenerative charging profile (illustrative)."

    else:
        I[:] = base_current_a
        profile_note = "Default steady profile (illustrative)."

    return [(float(t[i]), float(I[i])) for i in range(n)]
