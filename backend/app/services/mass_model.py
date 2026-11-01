"""
BattLab — Transparent Component-Level Battery Mass Breakdown Service
=====================================================================
Calculates a transparent, component-by-component mass breakdown of a battery pack,
distinguishing manufacturer-specified cell mass from estimated structural,
thermal, electrical, and BMS auxiliary masses.

Component Mass Modeling Principles:
-----------------------------------
1. Cell Mass:
   Directly derived from library CellSpec:
     M_cells = N_cells * m_cell = (Ns * Np) * m_cell
   If m_cell is null/missing in library, total pack mass is marked UNAVAILABLE.

2. Busbars & Electrical Interconnects:
   Nickel-plated copper / aluminum current collectors connecting parallel cell
   groups and series strings:
     M_busbars = N_cells * m_interconnect_per_cell
   Default baseline: 4.5 g (0.0045 kg) per 21700 cell.

3. Battery Management System (BMS):
   Master control board, current sense shunt resistor, contactors, and cell tap harness:
     M_bms = m_bms_base + Ns * m_tap_per_series
   Default baseline: 0.250 kg base + 0.005 kg per series channel.

4. Enclosure & Structural Compression:
   Extruded aluminum casing, top cover, compression endplates, and silicone sealing:
     M_enclosure = m_casing_base + N_cells * m_structure_per_cell
   Default baseline: 0.800 kg structural endplates + 0.018 kg perimeter casing per cell.

5. Thermal Management Hardware:
   Dependent on configuration.cooling_type:
   - Passive: 0.0 kg (casing convection only)
   - Fan: 0.380 kg (dual 12V axial fans + duct shroud)
   - Liquid: aluminum chill plate + 50/50 water-glycol coolant fluid + manifold fittings:
       M_cooling = 0.500 kg (manifold + pump/fittings) + N_cells * 0.018 kg (cold plate + coolant)
   - Phase-Change Material (PCM): paraffin-graphite matrix:
       M_cooling = N_cells * 0.008 kg

6. High-Voltage Internal Wiring & Bulkhead Connectors:
   Power cables, HV fuse block, and main connectors (Anderson / Radsok):
     M_wiring = 0.220 kg base + Ns * 0.002 kg

Engineering Limitations:
------------------------
- Auxiliary masses are first-order sizing approximations based on production light-EV packs.
- Real hardware weight must be confirmed on a physical scale once manufactured.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MassComponentItem:
    label: str
    mass_kg: Optional[float]
    status: str          # "measured_or_manufacturer", "engineering_estimate", "unavailable"
    fraction_pct: Optional[float]
    note: str


@dataclass
class PackMassBreakdown:
    cell_count: int
    ns: int
    np_: int
    cooling_type: str
    form_factor: str
    cell_mass_kg: Optional[float]
    total_cell_mass_kg: Optional[float]
    total_pack_mass_kg: Optional[float]
    cell_to_pack_mass_ratio: Optional[float]
    gravimetric_energy_density_cell_wh_per_kg: Optional[float]
    gravimetric_energy_density_pack_wh_per_kg: Optional[float]
    components: Dict[str, Dict[str, Any]]
    status: str          # "complete", "cells_only", "unavailable"
    assumptions: List[str]
    limitations: List[str]


def calculate_pack_mass_breakdown(
    ns: int,
    np_: int,
    cell_mass_kg: Optional[float] = None,
    cooling_type: str = "passive",
    form_factor: str = "21700",
    nominal_energy_wh: Optional[float] = None,
    custom_enclosure_mass_kg: Optional[float] = None,
    custom_bms_mass_kg: Optional[float] = None,
) -> PackMassBreakdown:
    """
    Calculate a component-level mass breakdown for a battery pack.

    Parameters
    ----------
    ns : int
        Series cell count.
    np_ : int
        Parallel cell count.
    cell_mass_kg : float or None
        Mass of an individual cell from library specification.
    cooling_type : str
        Cooling architecture: "passive", "fan", "liquid", "phase_change".
    form_factor : str
        Cell form factor (e.g. "21700", "18650", "prismatic").
    nominal_energy_wh : float or None
        Pack gross nominal energy in Wh.
    """
    if ns <= 0 or np_ <= 0:
        raise ValueError("Series (ns) and parallel (np) counts must be positive integers.")

    cell_count = ns * np_
    assumptions: List[str] = []
    limitations: List[str] = [
        "Cell mass is taken directly from the selected cell library specification.",
        "Pack auxiliary masses (enclosure, busbars, BMS, cooling, wiring) are first-order engineering sizing estimates.",
        "Measured physical weight of final assembled hardware is required for formal certification.",
    ]

    components: Dict[str, Dict[str, Any]] = {}

    # 1. Active Cell Mass
    if cell_mass_kg is not None and cell_mass_kg > 0:
        total_cell_mass = round(cell_count * cell_mass_kg, 3)
        components["cells"] = {
            "label": "Active Battery Cells",
            "mass_kg": total_cell_mass,
            "status": "measured_or_manufacturer",
            "note": f"{cell_count} cells ({ns}S{np_}P) × {cell_mass_kg:.3f} kg/cell ({form_factor})",
        }
        assumptions.append(f"Cell mass: {total_cell_mass:.2f} kg from manufacturer spec ({cell_mass_kg * 1000:.1f} g/cell).")
    else:
        total_cell_mass = None
        components["cells"] = {
            "label": "Active Battery Cells",
            "mass_kg": None,
            "status": "unavailable",
            "note": "Cell mass is not available in the component library specification.",
        }
        assumptions.append("Cell mass unavailable: total pack mass cannot be computed.")

    # 2. Busbars & Electrical Interconnects
    busbar_per_cell = 0.0045 if form_factor in ("21700", "18650") else 0.0080
    busbars_mass = round(cell_count * busbar_per_cell, 3)
    components["busbars_interconnects"] = {
        "label": "Busbars & Cell Interconnects",
        "mass_kg": busbars_mass,
        "status": "engineering_estimate",
        "note": f"{cell_count} cells × {busbar_per_cell * 1000:.1f} g/cell (nickel-plated copper current collectors)",
    }
    assumptions.append(f"Busbar mass estimated at {busbar_per_cell * 1000:.1f} g/cell for {form_factor} cells.")

    # 3. BMS Electronics & Shunt
    if custom_bms_mass_kg is not None and custom_bms_mass_kg > 0:
        bms_mass = round(custom_bms_mass_kg, 3)
        bms_status = "user_specified"
        bms_note = f"User-specified BMS mass: {bms_mass:.3f} kg"
    else:
        bms_mass = round(0.250 + ns * 0.005, 3)
        bms_status = "engineering_estimate"
        bms_note = f"Master BMS control board (250g) + {ns} series balance taps (5g/channel)"
    components["bms_electronics"] = {
        "label": "BMS & Current Shunt",
        "mass_kg": bms_mass,
        "status": bms_status,
        "note": bms_note,
    }

    # 4. Enclosure & Mechanical Structure
    if custom_enclosure_mass_kg is not None and custom_enclosure_mass_kg > 0:
        enclosure_mass = round(custom_enclosure_mass_kg, 3)
        enclosure_status = "user_specified"
        enclosure_note = f"User-specified enclosure mass: {enclosure_mass:.3f} kg"
    else:
        enclosure_mass = round(0.800 + cell_count * 0.018, 3)
        enclosure_status = "engineering_estimate"
        enclosure_note = f"2.5mm aluminum housing (800g base endplates + 18g/cell perimeter structure)"
    components["enclosure_structure"] = {
        "label": "Enclosure & Structural Housing",
        "mass_kg": enclosure_mass,
        "status": enclosure_status,
        "note": enclosure_note,
    }

    # 5. Thermal Management Hardware
    cooling_key = cooling_type.lower()
    if cooling_key == "fan":
        cooling_mass = 0.380
        cooling_note = "Dual 12V DC axial cooling fans and polymer ducting"
    elif cooling_key == "liquid":
        coolant_mass = round(0.300 + cell_count * 0.006, 3)
        plate_mass = round(cell_count * 0.012, 3)
        cooling_mass = round(0.200 + plate_mass + coolant_mass, 3)
        cooling_note = f"Aluminum cold plate ({plate_mass:.2f} kg) + 50/50 water-glycol coolant ({coolant_mass:.2f} kg) + fittings (200g)"
    elif cooling_key == "phase_change":
        cooling_mass = round(cell_count * 0.008, 3)
        cooling_note = f"Paraffin-graphite PCM buffer matrix ({cell_count} × 8g)"
    else:
        # passive
        cooling_mass = 0.000
        cooling_note = "Passive natural convection and enclosure radiation (no dedicated cooling hardware mass)"

    components["cooling_hardware"] = {
        "label": "Thermal Management Hardware",
        "mass_kg": cooling_mass,
        "status": "engineering_estimate",
        "note": cooling_note,
    }

    # 6. High-Voltage Wiring & Main Connectors
    wiring_mass = round(0.220 + ns * 0.002, 3)
    components["wiring_connectors"] = {
        "label": "HV Cabling, Fuse & Terminals",
        "mass_kg": wiring_mass,
        "status": "engineering_estimate",
        "note": f"4 AWG silicone power cables, main pyrofuse/fuse block, and Radsok bulkheads",
    }

    # Summation and gravimetric densities
    if total_cell_mass is not None:
        aux_mass = busbars_mass + bms_mass + enclosure_mass + cooling_mass + wiring_mass
        total_pack_mass = round(total_cell_mass + aux_mass, 3)
        cell_ratio = round(total_cell_mass / total_pack_mass, 4)
        status = "complete"

        # Percentage breakdown
        for k in components:
            m = components[k]["mass_kg"]
            if m is not None:
                components[k]["fraction_pct"] = round((m / total_pack_mass) * 100.0, 1)

        # Gravimetric densities
        if nominal_energy_wh and nominal_energy_wh > 0:
            cell_density = round(nominal_energy_wh / total_cell_mass, 1)
            pack_density = round(nominal_energy_wh / total_pack_mass, 1)
        else:
            cell_density = None
            pack_density = None
    else:
        total_pack_mass = None
        cell_ratio = None
        cell_density = None
        pack_density = None
        status = "unavailable"
        for k in components:
            components[k]["fraction_pct"] = None

    return PackMassBreakdown(
        cell_count=cell_count,
        ns=ns,
        np_=np_,
        cooling_type=cooling_type,
        form_factor=form_factor,
        cell_mass_kg=cell_mass_kg,
        total_cell_mass_kg=total_cell_mass,
        total_pack_mass_kg=total_pack_mass,
        cell_to_pack_mass_ratio=cell_ratio,
        gravimetric_energy_density_cell_wh_per_kg=cell_density,
        gravimetric_energy_density_pack_wh_per_kg=pack_density,
        components=components,
        status=status,
        assumptions=assumptions,
        limitations=limitations,
    )

