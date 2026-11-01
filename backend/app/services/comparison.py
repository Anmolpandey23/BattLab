"""
BattLab — Comparison Service

Compares multiple simulation runs and produces a structured comparison result
with metric tables, rankings and warnings diff.
"""
from __future__ import annotations

import json
from typing import Any, Optional


def compare_runs(runs_data: list[dict], weights: Optional[dict[str, float]] = None) -> dict:
    """
    Compare simulation runs.

    Parameters
    ----------
    runs_data : list of dicts, each with keys:
        run_id, run_label, config_label, nominal_voltage_v, nominal_energy_wh,
        usable_energy_wh, max_temp_c, min_soc, energy_delivered_wh,
        constraint_pass, constraint_fail, constraint_warning, constraint_unverified,
        cell_mass_kg, bom_cost_usd, ns, np, total_cells
    weights : dict of objective weights (default provided)
    """
    if not runs_data:
        return {"error": "No simulation runs provided for comparison"}

    default_weights = {
        "thermal_margin":   0.25,
        "usable_energy":    0.25,
        "mass":             0.20,
        "cost":             0.15,
        "cell_count":       0.15,
    }
    w = {**default_weights, **(weights or {})}

    metrics = [
        ("Nominal Voltage",     "V",    "nominal_voltage_v"),
        ("Nominal Energy",      "Wh",   "nominal_energy_wh"),
        ("Usable Energy",       "Wh",   "usable_energy_wh"),
        ("Max Modelled Temp",   "°C",   "max_temp_c"),
        ("Min SOC",             "%",    "min_soc"),
        ("Energy Delivered",    "Wh",   "energy_delivered_wh"),
        ("Constraints Pass",    "",     "constraint_pass"),
        ("Constraints Fail",    "",     "constraint_fail"),
        ("Constraints Warning", "",     "constraint_warning"),
        ("Constraints Unverif", "",     "constraint_unverified"),
        ("Est. Cell Mass",      "kg",   "cell_mass_kg"),
        ("Est. BOM Cost",       "USD",  "bom_cost_usd"),
        ("Total Cells",         "",     "total_cells"),
    ]

    metrics_table = []
    for label, unit, key in metrics:
        row = {
            "metric": label,
            "unit": unit,
            "values": {},
        }
        for rd in runs_data:
            val = rd.get(key)
            if key == "min_soc" and val is not None:
                val = round(val * 100, 1)   # convert to %
            row["values"][rd.get("run_label", str(rd.get("run_id", "?")))] = val
        metrics_table.append(row)

    # Ranking: only feasible/unverified runs ranked
    rankings = []
    for rd in runs_data:
        if rd.get("constraint_fail", 0) > 0:
            score = -1000.0
            rank_note = "RANKED LAST: one or more hard constraints failed."
        else:
            score = _ranking_score(rd, w)
            rank_note = f"Weighted score {score:.4f} (weights: {w})."
        rankings.append({
            "run_id": rd.get("run_id"),
            "run_label": rd.get("run_label", "?"),
            "score": round(score, 4),
            "rank_note": rank_note,
            "constraint_fail": rd.get("constraint_fail", 0),
        })

    rankings.sort(key=lambda x: -x["score"])
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    return {
        "runs": runs_data,
        "metrics_table": metrics_table,
        "ranking": rankings,
        "weights_used": w,
    }


def _ranking_score(rd: dict, w: dict) -> float:
    score = 0.0

    # Thermal margin: higher is better (lower max temp)
    max_t = rd.get("max_temp_c")
    if max_t is not None:
        score += w.get("thermal_margin", 0) * max(0, (80 - max_t) / 80)

    # Usable energy: higher is better
    ue = rd.get("usable_energy_wh") or rd.get("nominal_energy_wh")
    if ue:
        score += w.get("usable_energy", 0) * min(1.0, ue / 5000)

    # Mass: lower is better (normalize to 30 kg)
    mass = rd.get("cell_mass_kg")
    if mass:
        score += w.get("mass", 0) * max(0, (30 - mass) / 30)

    # Cost: lower is better (normalize to $500)
    cost = rd.get("bom_cost_usd")
    if cost:
        score += w.get("cost", 0) * max(0, (500 - cost) / 500)

    # Cell count: fewer is better (normalize to 300)
    cells = rd.get("total_cells")
    if cells:
        score += w.get("cell_count", 0) * max(0, (300 - cells) / 300)

    return round(score, 6)
