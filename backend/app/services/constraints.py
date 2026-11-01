"""
BattLab — Constraint & Compatibility Engine

Every constraint check returns a structured result with status, observed value,
threshold, explanation, source and suggested corrective action.

Statuses: pass | fail | warning | unverified
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Status(str, Enum):
    pass_  = "pass"
    fail   = "fail"
    warn   = "warning"
    unverf = "unverified"


@dataclass
class ConstraintCheck:
    rule_id: str
    status: Status
    observed_value: Optional[float]
    threshold: Optional[float]
    units: Optional[str]
    explanation: str
    source_assumption: str
    corrective_action: str


def _check(
    rule_id: str,
    observed: Optional[float],
    threshold: Optional[float],
    units: str,
    direction: str,          # "max" — observed <= threshold, "min" — observed >= threshold
    explanation_tmpl: str,   # may use {obs} {thr} {units}
    source: str,
    corrective: str,
) -> ConstraintCheck:
    if observed is None or threshold is None:
        return ConstraintCheck(
            rule_id=rule_id,
            status=Status.unverf,
            observed_value=observed,
            threshold=threshold,
            units=units,
            explanation=f"Insufficient data to evaluate {rule_id} — one or more required values missing.",
            source_assumption=source,
            corrective_action=corrective,
        )
    if direction == "max":
        ok = observed <= threshold
    else:
        ok = observed >= threshold

    # Small tolerance to avoid floating-point false failures
    if direction == "max":
        pct = (observed - threshold) / max(abs(threshold), 1e-9) * 100
        is_warn = ok and pct > -5  # within 5% of limit → warn
    else:
        pct = (threshold - observed) / max(abs(threshold), 1e-9) * 100
        is_warn = ok and pct > -5

    status = Status.pass_ if (ok and not is_warn) else (Status.warn if (ok and is_warn) else Status.fail)

    return ConstraintCheck(
        rule_id=rule_id,
        status=status,
        observed_value=observed,
        threshold=threshold,
        units=units,
        explanation=explanation_tmpl.format(obs=observed, thr=threshold, units=units),
        source_assumption=source,
        corrective_action=corrective,
    )


# ── Public constraint checks ──────────────────────────────────────────────────

def check_nominal_voltage(
    calc_v: Optional[float],
    target_v: Optional[float],
    tolerance_pct: float = 10.0,
) -> ConstraintCheck:
    if calc_v is None or target_v is None:
        return ConstraintCheck(
            rule_id="VOLT_NOMINAL",
            status=Status.unverf,
            observed_value=calc_v,
            threshold=target_v,
            units="V",
            explanation="Cannot verify voltage compliance — missing data.",
            source_assumption="Target voltage from project requirements.",
            corrective_action="Specify target nominal voltage in requirements.",
        )
    tol = target_v * tolerance_pct / 100.0
    ok = abs(calc_v - target_v) <= tol
    pct_err = (calc_v - target_v) / target_v * 100
    return ConstraintCheck(
        rule_id="VOLT_NOMINAL",
        status=Status.pass_ if ok else Status.fail,
        observed_value=round(calc_v, 3),
        threshold=target_v,
        units="V",
        explanation=(
            f"Calculated nominal voltage {calc_v:.2f} V is "
            f"{'within' if ok else 'outside'} ±{tolerance_pct}% of target {target_v:.2f} V "
            f"({pct_err:+.1f}%)."
        ),
        source_assumption="Ns × V_cell_nominal. See ENGINEERING_MODELS.md.",
        corrective_action="Adjust series count (Ns) to bring nominal voltage within tolerance." if not ok else "",
    )


def check_nominal_energy(
    calc_e_wh: Optional[float],
    target_e_wh: Optional[float],
    is_usable_target: bool = False,
    usable_e_wh: Optional[float] = None,
    tolerance_pct: float = 10.0,
) -> ConstraintCheck:
    compare_e = usable_e_wh if is_usable_target else calc_e_wh
    label = "usable energy" if is_usable_target else "nominal energy"
    if compare_e is None or target_e_wh is None:
        return ConstraintCheck(
            rule_id="ENERGY_TARGET",
            status=Status.unverf,
            observed_value=compare_e,
            threshold=target_e_wh,
            units="Wh",
            explanation=f"Cannot verify {label} — insufficient data.",
            source_assumption="V_nominal × Ah_pack.",
            corrective_action="Supply cell voltage limits and usable SOC window.",
        )
    tol = target_e_wh * tolerance_pct / 100.0
    ok = compare_e >= target_e_wh - tol
    return ConstraintCheck(
        rule_id="ENERGY_TARGET",
        status=Status.pass_ if ok else Status.fail,
        observed_value=round(compare_e, 1),
        threshold=target_e_wh,
        units="Wh",
        explanation=(
            f"Calculated {label} {compare_e:.0f} Wh vs target {target_e_wh:.0f} Wh "
            f"({'PASS' if ok else 'FAIL'})."
        ),
        source_assumption="V_nominal × Np × Ah_cell × SOC_window.",
        corrective_action="Increase Np or select higher-capacity cell." if not ok else "",
    )


def check_cell_mass(
    total_cells: int,
    cell_mass_kg: Optional[float],
    max_mass_kg: Optional[float],
    other_mass_kg: float = 0.0,
) -> ConstraintCheck:
    if cell_mass_kg is None:
        return ConstraintCheck(
            rule_id="MASS_LIMIT",
            status=Status.unverf,
            observed_value=None,
            threshold=max_mass_kg,
            units="kg",
            explanation="Cell mass not specified — total pack mass cannot be estimated.",
            source_assumption="Cell mass from component library.",
            corrective_action="Enter cell mass in the component library.",
        )
    total_cell_mass = total_cells * cell_mass_kg + other_mass_kg
    return _check(
        "MASS_LIMIT",
        observed=total_cell_mass,
        threshold=max_mass_kg,
        units="kg",
        direction="max",
        explanation_tmpl="Estimated cell mass {obs:.2f} kg vs limit {thr} kg.",
        source="Cell mass × total cell count. Excludes enclosure, BMS, wiring unless specified.",
        corrective="Reduce cell count, select lighter cells, or review mass limit.",
    )


def check_continuous_current(
    i_pack_a: Optional[float],
    np: int,
    cell_max_cont_a: Optional[float],
) -> ConstraintCheck:
    if i_pack_a is None:
        return ConstraintCheck(
            rule_id="CURR_CONTINUOUS",
            status=Status.unverf,
            observed_value=None,
            threshold=None,
            units="A",
            explanation="Pack continuous current not specified in requirements.",
            source_assumption="Requirement: continuous pack current.",
            corrective_action="Specify continuous current in requirements.",
        )
    if cell_max_cont_a is None:
        return ConstraintCheck(
            rule_id="CURR_CONTINUOUS",
            status=Status.unverf,
            observed_value=i_pack_a / np,
            threshold=None,
            units="A",
            explanation=f"Per-cell current {i_pack_a/np:.2f} A — cell max continuous rating not supplied.",
            source_assumption="Cell max continuous discharge current from datasheet.",
            corrective_action="Add cell continuous current rating to component library.",
        )
    i_cell = i_pack_a / np
    return _check(
        "CURR_CONTINUOUS",
        observed=i_cell,
        threshold=cell_max_cont_a,
        units="A",
        direction="max",
        explanation_tmpl="Per-cell continuous current {obs:.2f} A vs cell rating {thr} A.",
        source="I_pack / Np (equal sharing). Cell rating from datasheet.",
        corrective="Increase Np to reduce per-cell current, or select higher-rated cell.",
    )


def check_temperature(
    max_modelled_temp_c: Optional[float],
    cell_max_op_temp_c: Optional[float],
) -> ConstraintCheck:
    return _check(
        "TEMP_CELL_MAX",
        observed=max_modelled_temp_c,
        threshold=cell_max_op_temp_c,
        units="°C",
        direction="max",
        explanation_tmpl=(
            "Modelled maximum cell temperature {obs:.1f}°C vs cell limit {thr}°C. "
            "Note: this is a single-node lumped estimate."
        ),
        source="Thermal simulation output. Cell limit from datasheet/component library.",
        corrective="Improve cooling configuration (increase hA) or reduce operating current.",
    )


def check_cost(
    estimated_bom_usd: Optional[float],
    max_cost_usd: Optional[float],
) -> ConstraintCheck:
    return _check(
        "COST_BOM",
        observed=estimated_bom_usd,
        threshold=max_cost_usd,
        units="USD",
        direction="max",
        explanation_tmpl="Estimated cell BOM {obs:.2f} USD vs budget {thr:.2f} USD.",
        source="Cell unit cost × total cells. Excludes BMS, enclosure, assembly unless added.",
        corrective="Select lower-cost cell or reduce cell count.",
    )


def check_soc_bounds(min_soc: Optional[float]) -> ConstraintCheck:
    if min_soc is None:
        return ConstraintCheck(
            rule_id="SOC_FLOOR",
            status=Status.unverf,
            observed_value=None,
            threshold=0.0,
            units="",
            explanation="SOC floor not calculated — simulation not run.",
            source_assumption="SOC from coulomb counting simulation.",
            corrective_action="Run simulation.",
        )
    ok = min_soc >= 0.0
    return ConstraintCheck(
        rule_id="SOC_FLOOR",
        status=Status.pass_ if ok else Status.fail,
        observed_value=round(min_soc, 4),
        threshold=0.0,
        units="",
        explanation=(
            f"Minimum modelled SOC {min_soc*100:.1f}%. "
            "SOC reached 0% during simulation — check profile duration and capacity."
            if not ok else
            f"Minimum modelled SOC {min_soc*100:.1f}% — above floor."
        ),
        source_assumption="Coulomb counting with configured capacity and current profile.",
        corrective_action="Reduce discharge duration, increase Np, or select higher-capacity cell." if not ok else "",
    )


def run_all_checks(
    *,
    calc_v: Optional[float],
    target_v: Optional[float],
    calc_e_wh: Optional[float],
    usable_e_wh: Optional[float],
    target_e_wh: Optional[float],
    energy_is_usable: bool,
    total_cells: int,
    cell_mass_kg: Optional[float],
    max_mass_kg: Optional[float],
    i_pack_a: Optional[float],
    np: int,
    cell_max_cont_a: Optional[float],
    max_modelled_temp_c: Optional[float],
    cell_max_op_temp_c: Optional[float],
    estimated_bom_usd: Optional[float],
    max_cost_usd: Optional[float],
    min_soc: Optional[float],
) -> list[ConstraintCheck]:
    return [
        check_nominal_voltage(calc_v, target_v),
        check_nominal_energy(calc_e_wh, target_e_wh, energy_is_usable, usable_e_wh),
        check_cell_mass(total_cells, cell_mass_kg, max_mass_kg),
        check_continuous_current(i_pack_a, np, cell_max_cont_a),
        check_temperature(max_modelled_temp_c, cell_max_op_temp_c),
        check_cost(estimated_bom_usd, max_cost_usd),
        check_soc_bounds(min_soc),
    ]
