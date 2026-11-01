"""
BattLab — Simulation Orchestration Service

Runs the full simulation pipeline:
1. Build electrical inputs from configuration + scenario.
2. Generate or use supplied current profile.
3. Run electrical time-step loop (coulomb counting, losses).
4. Run thermal time-step loop.
5. Run constraint checks.
6. Return structured results.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from app.models import (
    CellSpec, ComponentSpec, Configuration, ConstraintResult,
    ConstraintStatus, Scenario, SimulationRun, SimulationStatus,
)
from app.services.electrical import (
    ElectricalInputs, calculate_pack, generate_current_profile, soc_update,
)
from app.services.thermal import (
    ThermalInputs, thermal_step, run_thermal_simulation,
    run_multi_node_thermal_simulation, MultiNodeThermalResult,
)
from app.services.aging import evaluate_simulation_aging, AgingSimulationResult
from app.services.constraints import run_all_checks, Status
from app.services.ecm import ecm_step, TheveninRCState, is_ocv_data_available
from app.services.provenance import generate_provenance_catalog
from app.services.model_validation import run_benchmark_validation


def _ha_for_cooling(
    cooling_type: str,
    cell_count: int,
    custom_system_ha: Optional[float] = None,
) -> tuple[float, str]:
    """
    Return effective lumped pack-level heat dissipation conductance hA [W/K] and provenance note.

    Cooling physics models:
    - Passive: Natural air convection & enclosure radiation. Scaled with pack enclosure area (~0.020 W/K per cell, min 1.5 W/K).
    - Fan: Forced air circulation through ducting (~0.090 W/K per cell, min 6.0 W/K).
    - Liquid: Chilled cold plate with liquid coolant flow (~0.450 W/K per cell, min 25.0 W/K).
    - Phase Change Material (PCM): Conduction buffer matrix (~0.120 W/K per cell).
    """
    if custom_system_ha is not None and custom_system_ha > 0:
        return custom_system_ha, f"Custom cooling hardware conductance: hA = {custom_system_ha:.2f} W/K."

    ck = cooling_type.lower()
    if ck == "fan":
        ha = max(6.0, 0.090 * cell_count)
        note = f"Forced-air fan cooling: lumped hA = {ha:.2f} W/K (~0.090 W/K per cell). Engineering estimate; depends on fan CFM."
    elif ck == "liquid":
        ha = max(25.0, 0.450 * cell_count)
        note = f"Liquid cold plate cooling: lumped hA = {ha:.2f} W/K (~0.450 W/K per cell). Engineering estimate; depends on coolant flow & chiller."
    elif ck == "phase_change":
        ha = max(4.0, 0.120 * cell_count)
        note = f"PCM thermal buffer: lumped hA = {ha:.2f} W/K (~0.120 W/K per cell). Note: lumped 1st-order model does not simulate latent heat plateau."
    else:
        # passive
        ha = max(1.5, 0.020 * cell_count)
        note = f"Passive natural convection & radiation: lumped hA = {ha:.2f} W/K (~0.020 W/K per cell). Engineering estimate for sealed aluminum casing."

    return round(ha, 2), note


def run_simulation(
    configuration: Configuration,
    scenario: Scenario,
    cell_spec: CellSpec,
    requirement=None,  # Requirement model or None
    enable_thermal_coupling: bool = True,
    enable_multi_node_thermal: bool = False,
    is_committed: bool = False,
    prior_cumulative_throughput_ah: float = 0.0,
    prior_cumulative_efc: float = 0.0,
) -> dict:
    """
    Run the full simulation and return a result dict.
    Does NOT touch the database — caller persists results.
    """
    assumptions: list[str] = []
    warnings_out: list[str] = []

    # ── 1. Pack calculations ──────────────────────────────────────────────────
    ns = configuration.ns
    np_ = configuration.np
    r_cell = cell_spec.internal_resistance_ohm
    if scenario.resistance_multiplier != 1.0:
        if r_cell:
            r_cell *= scenario.resistance_multiplier
            assumptions.append(
                f"Cell resistance multiplied by {scenario.resistance_multiplier}× for sensitivity scenario."
            )

    cap_ah = cell_spec.nominal_capacity_ah
    if scenario.capacity_variation_pct != 0:
        cap_ah *= (1.0 - scenario.capacity_variation_pct / 100.0)
        assumptions.append(
            f"Capacity reduced by {scenario.capacity_variation_pct}% for sensitivity scenario."
        )

    elec_inputs = ElectricalInputs(
        ns=ns,
        np=np_,
        v_cell_nominal=cell_spec.nominal_voltage_v,
        ah_cell=cap_ah,
        r_cell_ohm=r_cell,
        v_cell_min=cell_spec.min_voltage_v,
        v_cell_max=cell_spec.max_voltage_v,
        max_continuous_a=cell_spec.max_continuous_discharge_a,
        max_peak_a=cell_spec.max_peak_discharge_a,
        usable_soc_window=configuration.usable_soc_window,
        r_interconnect_ohm=configuration.interconnect_resistance_ohm,
    )
    pack = calculate_pack(elec_inputs)
    assumptions.extend(pack.assumptions)
    warnings_out.extend(pack.warnings)

    # ── 2. Current profile ────────────────────────────────────────────────────
    duration_s = scenario.duration_s
    dt_s = max(scenario.time_step_s, 0.1)

    if scenario.current_profile_json:
        raw_profile = json.loads(scenario.current_profile_json)
        profile = [(float(p[0]), float(p[1])) for p in raw_profile]
        assumptions.append("Current profile supplied by user/seed data.")
    elif getattr(scenario, "duty_cycle_segments", None) and len(scenario.duty_cycle_segments) > 0:
        sorted_segs = sorted(scenario.duty_cycle_segments, key=lambda s: s.segment_index)
        combined_profile: list[tuple[float, float]] = []
        cur_t = 0.0
        for s_idx, seg in enumerate(sorted_segs):
            seg_dur = max(float(seg.duration_s), dt_s)
            if seg.discharge_current_a is not None:
                seg_i = float(seg.discharge_current_a)
            elif getattr(scenario, "discharge_current_a", None):
                seg_i = float(scenario.discharge_current_a)
            else:
                seg_i = pack.capacity_ah / 1.0

            sub_prof = generate_current_profile(seg.profile_type, seg_dur, dt_s, seg_i)
            for p_idx, (pt, p_curr) in enumerate(sub_prof):
                if combined_profile and p_idx == 0:
                    continue
                combined_profile.append((round(cur_t + pt, 4), float(p_curr)))
            cur_t += seg_dur

        profile = combined_profile
        duration_s = cur_t
        assumptions.append(
            f"Multi-segment duty cycle: {len(sorted_segs)} segments executed in order "
            f"(total duration {duration_s:.1f} s). Continuous SOC and thermal propagation preserved."
        )
    else:
        # Base current: use scenario's discharge_current_a if set, else fall back to 1C
        if getattr(scenario, "discharge_current_a", None):
            base_i_pack = float(scenario.discharge_current_a)
            c_rate = base_i_pack / pack.capacity_ah
            assumptions.append(
                f"Synthetic {scenario.profile_type} current profile generated at "
                f"{c_rate:.2f}C ({base_i_pack:.1f} A, user-specified). "
                f"This is illustrative data, not a real measurement."
            )
        else:
            base_i_pack = pack.capacity_ah / 1.0  # 1C fallback
            assumptions.append(
                f"Synthetic {scenario.profile_type} current profile generated at 1C rate "
                f"({base_i_pack:.1f} A, no discharge_current_a set). "
                f"This is illustrative data, not a real measurement."
            )
        profile = generate_current_profile(
            scenario.profile_type, duration_s, dt_s, base_i_pack
        )

    # Build time arrays
    times_s = [p[0] for p in profile]
    currents_a = [p[1] for p in profile]

    if not times_s:
        return {"error": "Empty current profile"}

    # ── 3. Thermal parameters & chemistry configuration ─────────────────────
    raw_chem = getattr(cell_spec, "chemistry", None)
    if hasattr(raw_chem, "value"):
        chem_str = str(raw_chem.value)
    elif raw_chem is not None:
        chem_str = str(raw_chem)
        if chem_str.upper().startswith("CHEMISTRY."):
            chem_str = chem_str.split(".", 1)[1]
    else:
        chem_str = "NMC"

    v_min_c = getattr(cell_spec, "min_voltage_v", None) or 3.0
    v_max_c = getattr(cell_spec, "max_voltage_v", None) or 4.2
    interconnect_r = float(getattr(configuration, "interconnect_resistance_ohm", 0.0) or 0.0)
    r_cell_eff = float(r_cell) if r_cell else 0.025

    # Determine thermal mass
    if cell_spec.mass_kg and cell_spec.specific_heat_j_per_kg_k:
        total_mass_kg = cell_spec.mass_kg * ns * np_
        cp = cell_spec.specific_heat_j_per_kg_k
        assumptions.append("Thermal mass from cell spec × total cell count.")
    else:
        # Provisional assumption for 21700-class cells
        total_mass_kg = 0.070 * ns * np_   # ~70 g / cell provisional
        cp = 900.0                          # J/kg/K — typical Li-ion
        assumptions.append(
            "PROVISIONAL: Cell mass assumed 70 g/cell, cp assumed 900 J/kg/K. "
            "Supply cell thermal properties for reliable thermal prediction."
        )
        warnings_out.append("Thermal simulation uses provisional cell thermal properties.")

    # Cooling conductance (scaled by pack architecture and cooling system type)
    ha, ha_note = _ha_for_cooling(
        configuration.cooling_type,
        ns * np_,
    )
    assumptions.append(f"Cooling: {ha_note}")

    # ── 4. Unified Electro-Thermal time-step loop (ECM + Thermal advance) ────
    soc = scenario.initial_soc
    soc_series = [soc]
    loss_series = []
    energy_wh = 0.0
    q_gen_series = []
    voltages_v = []

    current_temp_c = float(scenario.initial_cell_temp_c)
    temperatures_c = [current_temp_c]
    rc_state = TheveninRCState(v_rc=0.0)

    # Initial terminal voltage at t = 0
    init_res, rc_state = ecm_step(
        soc=soc,
        i_pack_a=currents_a[0] if currents_a else 0.0,
        dt_s=0.0,
        temp_c=current_temp_c,
        ns=ns,
        np_=np_,
        nominal_capacity_ah=cap_ah,
        r0_ref_ohm=r_cell_eff,
        r1_ohm=0.005,
        c1_farad=1000.0,
        rc_state=rc_state,
        r_interconnect_ohm=interconnect_r,
        chemistry=chem_str,
        v_min_cell=v_min_c,
        v_max_cell=v_max_c,
    )
    voltages_v.append(init_res.v_pack_v)

    for i in range(len(times_s) - 1):
        dt = times_s[i + 1] - times_s[i]
        i_pack = currents_a[i]
        i_cell = i_pack / np_

        # Dynamic temperature passed to ECM step
        temp_eval = current_temp_c if enable_thermal_coupling else scenario.initial_cell_temp_c

        # ECM step for dynamic terminal voltage and heat generation
        step_res, rc_state = ecm_step(
            soc=soc,
            i_pack_a=i_pack,
            dt_s=dt,
            temp_c=temp_eval,
            ns=ns,
            np_=np_,
            nominal_capacity_ah=cap_ah,
            r0_ref_ohm=r_cell_eff,
            r1_ohm=0.005,
            c1_farad=1000.0,
            rc_state=rc_state,
            r_interconnect_ohm=interconnect_r,
            chemistry=chem_str,
            v_min_cell=v_min_c,
            v_max_cell=v_max_c,
        )

        soc = soc_update(soc, i_cell, dt, cap_ah)
        soc_series.append(soc)

        # Dynamic losses tracking (temperature-derated Ohmic + RC polarization)
        r0_dyn = step_res.r0_cell_ohm
        r_pack_effective = (ns * r0_dyn / np_) + interconnect_r
        p_loss = (i_pack ** 2) * r_pack_effective + (ns * np_ * ((step_res.v_rc_v ** 2) / 0.005 if 0.005 > 1e-9 else 0.0))
        loss_series.append(round(p_loss, 2))

        # Energy delivered (using transient terminal pack voltage from ECM)
        p_delivered = step_res.p_delivered_w
        energy_wh += max(0.0, p_delivered * dt) / 3600.0

        # Heat generated per cell × total cells
        q_cell_w = step_res.q_cell_w
        q_pack_w = q_cell_w * ns * np_
        q_gen_series.append(q_pack_w)
        voltages_v.append(step_res.v_pack_v)

        # Advance lumped thermal model analytically for dt
        t_step = thermal_step(ThermalInputs(
            cell_mass_kg=total_mass_kg,
            cp_j_per_kg_k=cp,
            ha_w_per_k=ha,
            q_gen_w=q_pack_w,
            t_current_c=current_temp_c,
            t_ambient_c=scenario.ambient_temp_c,
            dt_s=dt,
        ))
        next_temp_c = t_step.t_next_c
        temperatures_c.append(next_temp_c)
        current_temp_c = next_temp_c

    max_modelled_temp = max(temperatures_c) if temperatures_c else scenario.initial_cell_temp_c
    min_modelled_temp = min(temperatures_c) if temperatures_c else scenario.initial_cell_temp_c

    if cell_spec.max_operating_temp_c and max_modelled_temp > cell_spec.max_operating_temp_c:
        warnings_out.append(
            f"Thermal limit exceeded: peak modelled temperature {max_modelled_temp:.1f}°C "
            f"exceeds cell max operating limit {cell_spec.max_operating_temp_c:.1f}°C."
        )

    if enable_thermal_coupling:
        assumptions.append(
            "Coupled Electro-Thermal Model enabled: 1-RC Thevenin ECM with dynamic Arrhenius "
            "kinetic resistance R0(T), monotonic OCV, and reversible entropic heat dynamically "
            "coupled to lumped 1st-order thermal dissipation."
        )
    else:
        assumptions.append(
            "Decoupled Open-Loop Electro-Thermal Model: Electrical ECM evaluates resistance at initial temperature."
        )

    if is_ocv_data_available(chem_str):
        assumptions.append(
            f"Calibrated Equivalent Circuit Model (ECM) enabled: 1-RC Thevenin with "
            f"Arrhenius kinetic internal resistance R0(T), monotonic OCV({chem_str}), and "
            f"reversible entropic heat coupling."
        )
    else:
        warnings_out.append(
            f"UNAVAILABLE OCV DATA: Calibrated OCV curve for chemistry '{chem_str}' is not available in library. "
            f"Voltage simulation uses approximate linear bounds."
        )
        assumptions.append(
            f"OCV curve for chemistry '{chem_str}' unavailable; terminal voltage is an uncalibrated linear approximation."
        )

    # ── Multi-Node Thermal Network Simulation ─────────────────────────────────
    multi_node_res: Optional[MultiNodeThermalResult] = None
    if enable_multi_node_thermal or getattr(scenario, "cooling_override", None) == "multi_node":
        multi_node_res = run_multi_node_thermal_simulation(
            times_s=times_s,
            q_gen_sequence_w=q_gen_series,
            t_ambient_c=scenario.ambient_temp_c,
            t_initial_c=scenario.initial_cell_temp_c,
            total_cell_mass_kg=total_mass_kg,
            cell_count=ns * np_,
            cp_j_per_kg_k=cp,
            ha_w_per_k=ha,
            t_max_limit_c=cell_spec.max_operating_temp_c,
        )
        assumptions.extend(multi_node_res.assumptions)
        warnings_out.extend(multi_node_res.warnings)
        # Peak internal core temperature governs safety verdict in multi-node mode
        max_modelled_temp = multi_node_res.max_core_temp_c

    # ── Battery Aging & Degradation Evaluation ────────────────────────────────
    mean_temp_op = (sum(temperatures_c) / len(temperatures_c)) if temperatures_c else scenario.initial_cell_temp_c
    aging_res: AgingSimulationResult = evaluate_simulation_aging(
        currents_a=currents_a,
        times_s=times_s,
        nominal_capacity_ah=pack.capacity_ah,
        initial_r0_ohm=r_cell_eff,
        mean_temp_c=mean_temp_op,
        chemistry=chem_str,
        prior_cumulative_throughput_ah=prior_cumulative_throughput_ah,
        prior_cumulative_efc=prior_cumulative_efc,
        is_committed=is_committed,
        ambient_temp_c=scenario.ambient_temp_c,
    )
    assumptions.extend(aging_res.assumptions)

    # ── 5. Constraint checks ─────────────────────────────────────────────────
    req = requirement
    checks = run_all_checks(
        calc_v=pack.nominal_voltage_v,
        target_v=req.target_voltage_v if req else None,
        calc_e_wh=pack.nominal_energy_wh,
        usable_e_wh=pack.usable_energy_wh,
        target_e_wh=req.target_energy_wh if req else None,
        energy_is_usable=req.energy_is_usable if req else False,
        total_cells=pack.total_cells,
        cell_mass_kg=cell_spec.mass_kg,
        max_mass_kg=req.max_mass_kg if req else None,
        i_pack_a=req.continuous_current_a if req else None,
        np=np_,
        cell_max_cont_a=cell_spec.max_continuous_discharge_a,
        max_modelled_temp_c=max_modelled_temp,
        cell_max_op_temp_c=cell_spec.max_operating_temp_c,
        estimated_bom_usd=pack.total_cells * cell_spec.unit_cost_usd if cell_spec.unit_cost_usd else None,
        max_cost_usd=req.max_cost_usd if req else None,
        min_soc=min(soc_series) if soc_series else None,
    )

    # ── 6. Assemble time-series output ────────────────────────────────────────
    timeseries = []
    for i, t in enumerate(times_s):
        pt: dict = {
            "t_s": t,
            "current_a": currents_a[i] if i < len(currents_a) else 0.0,
            "soc": soc_series[i] if i < len(soc_series) else 0.0,
            "temp_c": temperatures_c[i] if i < len(temperatures_c) else scenario.initial_cell_temp_c,
            "voltage_v": round(voltages_v[i], 3) if i < len(voltages_v) else None,
            "power_loss_w": loss_series[i] if i < len(loss_series) else (loss_series[-1] if loss_series else 0.0),
        }
        if multi_node_res and i < len(multi_node_res.t_core_c):
            pt["temp_core_c"] = multi_node_res.t_core_c[i]
            pt["temp_surface_c"] = multi_node_res.t_surface_c[i]
            pt["temp_plate_c"] = multi_node_res.t_plate_c[i]
        timeseries.append(pt)

    # Status tallies
    status_map = {Status.pass_: "pass", Status.fail: "fail", Status.warn: "warning", Status.unverf: "unverified"}
    n_pass = sum(1 for c in checks if c.status == Status.pass_)
    n_fail = sum(1 for c in checks if c.status == Status.fail)
    n_warn = sum(1 for c in checks if c.status == Status.warn)
    n_unv  = sum(1 for c in checks if c.status == Status.unverf)

    # Provenance Catalog and Model Validation
    prov_catalog = generate_provenance_catalog(
        cell=cell_spec,
        configuration=configuration,
        scenario=scenario,
        requirement=requirement,
    )
    val_benchmark = run_benchmark_validation(
        simulated_timeseries=timeseries,
        target_metric="voltage_v",
    )

    return {
        "nominal_voltage_v": pack.nominal_voltage_v,
        "nominal_energy_wh": pack.nominal_energy_wh,
        "usable_energy_wh": pack.usable_energy_wh,
        "max_temp_c": round(max_modelled_temp, 3),
        "min_soc": min(soc_series) if soc_series else None,
        "energy_delivered_wh": round(energy_wh, 2),
        "soh_capacity_pct": aging_res.soh_capacity_pct,
        "soh_resistance_pct": aging_res.soh_resistance_pct,
        "throughput_ah": aging_res.run_throughput_ah,
        "efc": aging_res.run_efc,
        "battery_aging": {
            "run_throughput_ah": aging_res.run_throughput_ah,
            "run_efc": aging_res.run_efc,
            "cumulative_throughput_ah": aging_res.cumulative_throughput_ah,
            "cumulative_efc": aging_res.cumulative_efc,
            "capacity_fade_pct": aging_res.capacity_fade_pct,
            "cycle_fade_pct": aging_res.cycle_fade_pct,
            "calendar_fade_pct": aging_res.calendar_fade_pct,
            "resistance_growth_pct": aging_res.resistance_growth_pct,
            "soh_capacity_pct": aging_res.soh_capacity_pct,
            "soh_resistance_pct": aging_res.soh_resistance_pct,
            "actual_capacity_ah": aging_res.actual_capacity_ah,
            "actual_r0_ohm": aging_res.actual_r0_ohm,
            "projected_cycles_to_80pct": aging_res.projected_cycles_to_80pct,
            "lifetime_trajectory": aging_res.lifetime_trajectory,
            "is_committed": aging_res.is_committed,
            "assumptions": aging_res.assumptions,
            "limitations": aging_res.limitations,
        },
        "multi_node_thermal": {
            "enabled": multi_node_res is not None,
            "max_core_temp_c": multi_node_res.max_core_temp_c if multi_node_res else None,
            "max_surface_temp_c": multi_node_res.max_surface_temp_c if multi_node_res else None,
            "max_plate_temp_c": multi_node_res.max_plate_temp_c if multi_node_res else None,
            "max_gradient_c": multi_node_res.max_gradient_c if multi_node_res else None,
            "energy_conservation_residual_j": multi_node_res.energy_conservation_residual_j if multi_node_res else None,
        } if multi_node_res else None,
        "thermal_model_type": "multi_node" if multi_node_res else "lumped",
        "constraint_pass": n_pass,
        "constraint_fail": n_fail,
        "constraint_warning": n_warn,
        "constraint_unverified": n_unv,
        "timeseries": timeseries,
        "parameter_provenance": prov_catalog,
        "model_validation": val_benchmark,
        "ecm_model_info": {
            "model_type": "1-RC Thevenin ECM",
            "chemistry": str(chem_str),
            "ocv_calibrated": is_ocv_data_available(chem_str),
            "ocv_status": "calibrated_piecewise" if is_ocv_data_available(chem_str) else "uncalibrated_linear_bounds",
            "thermal_coupling_enabled": enable_thermal_coupling,
            "r0_ref_ohm": r_cell_eff,
            "arrhenius_resistance": True,
            "polarization_relaxation": True,
            "reversible_entropic_heat": True,
        },
        "constraints": [
            {
                "rule_id": c.rule_id,
                "status": status_map[c.status],
                "observed_value": c.observed_value,
                "threshold": c.threshold,
                "units": c.units,
                "explanation": c.explanation,
                "source_assumption": c.source_assumption,
                "corrective_action": c.corrective_action,
            }
            for c in checks
        ],
        "assumptions": assumptions,
        "warnings": warnings_out,
    }
