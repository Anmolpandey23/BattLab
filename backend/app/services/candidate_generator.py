"""
BattLab — Candidate Generator

Generates feasible battery configurations from requirements and cell specs.
Algorithm is deterministic and explainable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from app.services.electrical import ElectricalInputs, calculate_pack


@dataclass
class CandidateConfig:
    ns: int
    np: int
    total_cells: int
    nominal_voltage_v: float
    nominal_energy_wh: float
    estimated_usable_energy_wh: Optional[float]
    estimated_cell_mass_kg: Optional[float]
    estimated_bom_cost_usd: Optional[float]
    voltage_error_pct: float
    energy_error_pct: float
    status: str        # "feasible" | "unverified" | "infeasible"
    pass_notes: list[str]
    fail_notes: list[str]
    warning_notes: list[str]
    score: float = 0.0


def generate_candidates(
    target_voltage_v: float,
    target_energy_wh: float,
    energy_is_usable: bool,
    v_cell_nominal: float,
    ah_cell: float,
    v_cell_min: Optional[float],
    v_cell_max: Optional[float],
    r_cell_ohm: Optional[float],
    cell_mass_kg: Optional[float],
    unit_cost_usd: Optional[float],
    max_continuous_cell_a: Optional[float],
    max_mass_kg: Optional[float],
    max_cost_usd: Optional[float],
    continuous_pack_a: Optional[float],
    usable_soc_window: float = 0.80,
    voltage_tolerance_pct: float = 15.0,
    max_candidates: int = 10,
) -> list[CandidateConfig]:
    """
    Generate ranked candidate (Ns, Np) configurations.

    Steps:
    1. Enumerate Ns values within voltage_tolerance_pct of target.
    2. For each Ns, find minimum Np satisfying energy target.
    3. Apply mass and cost filters where data is available.
    4. Rank remaining candidates.
    """
    if v_cell_nominal <= 0 or ah_cell <= 0:
        raise ValueError("Cell nominal voltage and capacity must be positive")
    if target_voltage_v <= 0 or target_energy_wh <= 0:
        raise ValueError("Target voltage and energy must be positive")

    candidates: list[CandidateConfig] = []

    # Enumerate Ns
    ns_min = max(1, math.floor(target_voltage_v / v_cell_nominal * (1 - voltage_tolerance_pct / 100)))
    ns_max = math.ceil(target_voltage_v / v_cell_nominal * (1 + voltage_tolerance_pct / 100))
    ns_max = min(ns_max, 500)   # sanity cap

    for ns in range(ns_min, ns_max + 1):
        v_nom = ns * v_cell_nominal
        v_err_pct = (v_nom - target_voltage_v) / target_voltage_v * 100

        if abs(v_err_pct) > voltage_tolerance_pct:
            continue

        # Minimum Np to hit energy target
        e_per_parallel = v_nom * ah_cell  # Wh per parallel string
        if energy_is_usable:
            target_for_calc = target_energy_wh / usable_soc_window
        else:
            target_for_calc = target_energy_wh

        np_min = max(1, math.ceil(target_for_calc / e_per_parallel))
        # Explore a few Np values around the minimum
        for np in range(np_min, min(np_min + 5, 200)):
            inputs = ElectricalInputs(
                ns=ns,
                np=np,
                v_cell_nominal=v_cell_nominal,
                ah_cell=ah_cell,
                r_cell_ohm=r_cell_ohm,
                i_pack_a=continuous_pack_a,
                usable_soc_window=usable_soc_window,
                v_cell_min=v_cell_min,
                v_cell_max=v_cell_max,
                max_continuous_a=max_continuous_cell_a,
            )
            pack = calculate_pack(inputs)

            est_cell_mass = (ns * np * cell_mass_kg) if cell_mass_kg else None
            est_bom = (ns * np * unit_cost_usd) if unit_cost_usd else None
            e_compare = pack.usable_energy_wh if energy_is_usable else pack.nominal_energy_wh
            e_err_pct = ((e_compare or pack.nominal_energy_wh) - target_energy_wh) / target_energy_wh * 100

            pass_notes: list[str] = []
            fail_notes: list[str] = []
            warning_notes: list[str] = []
            status = "feasible"

            # Voltage check
            if abs(v_err_pct) <= voltage_tolerance_pct:
                pass_notes.append(f"Nominal voltage {v_nom:.2f} V within {voltage_tolerance_pct}% of target.")
            else:
                fail_notes.append(f"Nominal voltage {v_nom:.2f} V outside tolerance.")
                status = "infeasible"

            # Energy check
            if e_compare and e_compare >= target_energy_wh * 0.95:
                pass_notes.append(f"Energy {e_compare:.0f} Wh meets target.")
            elif e_compare:
                fail_notes.append(f"Energy {e_compare:.0f} Wh below target {target_energy_wh:.0f} Wh.")
                status = "infeasible"
            else:
                warning_notes.append("Usable energy unverified — cell voltage limits not supplied.")
                if status == "feasible":
                    status = "unverified"

            # Mass check
            if est_cell_mass and max_mass_kg:
                if est_cell_mass > max_mass_kg:
                    fail_notes.append(f"Estimated cell mass {est_cell_mass:.1f} kg exceeds limit {max_mass_kg:.1f} kg.")
                    status = "infeasible"
                else:
                    pass_notes.append(f"Estimated cell mass {est_cell_mass:.1f} kg within limit.")
            elif not cell_mass_kg and max_mass_kg:
                warning_notes.append("Cell mass unknown — mass compliance unverified.")
                if status == "feasible":
                    status = "unverified"

            # Cost check
            if est_bom and max_cost_usd:
                if est_bom > max_cost_usd:
                    fail_notes.append(f"Estimated BOM ${est_bom:.0f} exceeds budget ${max_cost_usd:.0f}.")
                    status = "infeasible"

            # Current check
            if pack.warnings:
                warning_notes.extend(pack.warnings)
                if status == "feasible":
                    status = "unverified"

            score = _score_candidate(
                v_err_pct=v_err_pct,
                e_err_pct=e_err_pct,
                est_mass=est_cell_mass,
                mass_limit=max_mass_kg,
                est_bom=est_bom,
                total_cells=ns * np,
            )

            candidates.append(CandidateConfig(
                ns=ns,
                np=np,
                total_cells=ns * np,
                nominal_voltage_v=round(v_nom, 3),
                nominal_energy_wh=round(pack.nominal_energy_wh, 1),
                estimated_usable_energy_wh=round(pack.usable_energy_wh, 1) if pack.usable_energy_wh else None,
                estimated_cell_mass_kg=round(est_cell_mass, 2) if est_cell_mass else None,
                estimated_bom_cost_usd=round(est_bom, 2) if est_bom else None,
                voltage_error_pct=round(v_err_pct, 2),
                energy_error_pct=round(e_err_pct, 2),
                status=status,
                pass_notes=pass_notes,
                fail_notes=fail_notes,
                warning_notes=warning_notes,
                score=score,
            ))

    # Sort: feasible first, then by score descending
    order = {"feasible": 0, "unverified": 1, "infeasible": 2}
    candidates.sort(key=lambda c: (order.get(c.status, 3), -c.score))
    return candidates[:max_candidates]


def _score_candidate(
    v_err_pct: float,
    e_err_pct: float,
    est_mass: Optional[float],
    mass_limit: Optional[float],
    est_bom: Optional[float],
    total_cells: int,
) -> float:
    """
    Transparent multi-objective score. Higher is better.
    Weights: voltage closeness 0.3, energy excess 0.3, mass margin 0.2, cell count 0.2.
    """
    score = 0.0
    # Voltage closeness
    score += 0.3 * max(0, 1 - abs(v_err_pct) / 15)
    # Energy: slight excess preferred over deficit
    if e_err_pct >= 0:
        score += 0.3 * max(0, 1 - e_err_pct / 20)
    # Mass margin
    if est_mass and mass_limit:
        margin = (mass_limit - est_mass) / mass_limit
        score += 0.2 * max(0, margin)
    # Fewer cells is generally better (cost/weight)
    score += 0.2 * max(0, 1 - total_cells / 500)
    return round(score, 4)
