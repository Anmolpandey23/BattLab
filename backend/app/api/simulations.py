"""BattLab — API Router: Simulations"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    CellSpec, Configuration, ConstraintResult, ConstraintStatus,
    Scenario, SimulationRun, SimulationStatus, DutyCycleSegment,
)
from app.schemas import (
    SimulationRequest, SimulationResultRead, ScenarioCreate, ScenarioRead,
    DutyCycleSegmentCreate, DutyCycleSegmentRead,
    VehicleLoadRequest, VehicleLoadResponse, UncertaintyRequest,
    DriveCycleRequest, DriveCycleExportScenarioRequest,
    ExperimentalValidationRequest,
)
from app.services.simulation import run_simulation
from app.services.vehicle_load import calculate_vehicle_load
from app.services.drive_cycle import simulate_drive_cycle
from app.services.provenance import generate_provenance_catalog
from app.services.model_validation import run_benchmark_validation
from app.services.uncertainty import run_monte_carlo_uncertainty
from app.services.experimental_validation import (
    parse_and_validate_csv_dataset,
    align_and_evaluate_validation,
)

router = APIRouter(tags=["simulations"])


def get_session():
    with Session(engine) as session:
        yield session


# ── Scenarios ─────────────────────────────────────────────────────────────────

@router.get("/scenarios", response_model=list[ScenarioRead])
def list_scenarios(session: Session = Depends(get_session)):
    return session.exec(select(Scenario)).all()


@router.get("/scenarios/{scenario_id}", response_model=ScenarioRead)
def get_scenario(scenario_id: int, session: Session = Depends(get_session)):
    sc = session.get(Scenario, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return sc


@router.post("/scenarios", response_model=ScenarioRead, status_code=201)
def create_scenario(body: ScenarioCreate, session: Session = Depends(get_session)):
    import json as _json
    data = body.model_dump(exclude={"current_profile"})
    if body.current_profile:
        data["current_profile_json"] = _json.dumps(body.current_profile)
    sc = Scenario(**data)
    session.add(sc)
    session.commit()
    session.refresh(sc)
    return sc


# ── Simulate ──────────────────────────────────────────────────────────────────

@router.post("/configurations/{configuration_id}/simulate", status_code=202)
def run_simulation_endpoint(
    configuration_id: int,
    body: SimulationRequest,
    session: Session = Depends(get_session),
):
    cfg = session.get(Configuration, configuration_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    if not cfg.cell_spec_id:
        raise HTTPException(400, "Configuration has no cell selected. Add a cell before simulating.")
    cell = session.get(CellSpec, cfg.cell_spec_id)
    if not cell:
        raise HTTPException(404, "Cell spec not found")
    scenario = session.get(Scenario, body.scenario_id)
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    # Fetch requirement
    from app.models import Requirement
    req = session.exec(
        select(Requirement).where(Requirement.project_id == cfg.project_id)
    ).first()

    # Create SimulationRun record
    run = SimulationRun(
        project_id=cfg.project_id,
        configuration_id=configuration_id,
        scenario_id=body.scenario_id,
        run_label=body.run_label or f"{cfg.label} / {scenario.name}",
        status=SimulationStatus.running,
    )
    # Snapshot inputs
    run.inputs_snapshot_json = json.dumps({
        "configuration": {
            "ns": cfg.ns,
            "np": cfg.np,
            "cooling_type": cfg.cooling_type,
            "usable_soc_window": cfg.usable_soc_window,
            "interconnect_resistance_ohm": cfg.interconnect_resistance_ohm,
        },
        "cell": {
            "model": cell.model,
            "nominal_voltage_v": cell.nominal_voltage_v,
            "nominal_capacity_ah": cell.nominal_capacity_ah,
            "internal_resistance_ohm": cell.internal_resistance_ohm,
            "data_status": cell.data_status,
        },
        "scenario": {
            "name": scenario.name,
            "ambient_temp_c": scenario.ambient_temp_c,
            "initial_soc": scenario.initial_soc,
            "duration_s": scenario.duration_s,
            "resistance_multiplier": scenario.resistance_multiplier,
            "capacity_variation_pct": scenario.capacity_variation_pct,
        },
    }, default=str)
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        results = run_simulation(
            cfg, scenario, cell, req,
            enable_multi_node_thermal=getattr(body, "enable_multi_node_thermal", False),
            is_committed=getattr(body, "is_committed", False),
        )

        # Persist results
        run.status = SimulationStatus.completed
        run.completed_at = datetime.utcnow()
        run.result_nominal_voltage_v = results.get("nominal_voltage_v")
        run.result_nominal_energy_wh = results.get("nominal_energy_wh")
        run.result_usable_energy_wh = results.get("usable_energy_wh")
        run.result_max_temp_c = results.get("max_temp_c")
        run.result_min_soc = results.get("min_soc")
        run.result_energy_delivered_wh = results.get("energy_delivered_wh")
        run.result_soh_capacity_pct = results.get("soh_capacity_pct")
        run.result_soh_resistance_pct = results.get("soh_resistance_pct")
        run.result_throughput_ah = results.get("throughput_ah")
        run.result_efc = results.get("efc")
        run.battery_aging_json = json.dumps(results.get("battery_aging")) if results.get("battery_aging") else None
        run.multi_node_thermal_json = json.dumps(results.get("multi_node_thermal")) if results.get("multi_node_thermal") else None
        run.constraint_pass = results.get("constraint_pass", 0)
        run.constraint_fail = results.get("constraint_fail", 0)
        run.constraint_warning = results.get("constraint_warning", 0)
        run.constraint_unverified = results.get("constraint_unverified", 0)

        # Store timeseries (capped to avoid huge blobs)
        ts = results.get("timeseries", [])
        # Downsample if > 500 points
        if len(ts) > 500:
            step = len(ts) // 500
            ts = ts[::step]
        run.timeseries_json = json.dumps(ts)
        run.assumptions_json = json.dumps(results.get("assumptions", []))

        session.add(run)

        # Persist constraints
        for c in results.get("constraints", []):
            cr = ConstraintResult(
                simulation_run_id=run.id,
                rule_id=c["rule_id"],
                status=ConstraintStatus(c["status"]),
                observed_value=c.get("observed_value"),
                threshold=c.get("threshold"),
                units=c.get("units"),
                explanation=c["explanation"],
                source_assumption=c.get("source_assumption"),
                corrective_action=c.get("corrective_action"),
            )
            session.add(cr)

        session.commit()
        return {"simulation_id": run.id, "status": "completed"}

    except Exception as e:
        run.status = SimulationStatus.failed
        run.error_message = str(e)[:500]
        session.add(run)
        session.commit()
        raise HTTPException(500, f"Simulation failed: {str(e)[:200]}")


# ── Results ───────────────────────────────────────────────────────────────────

@router.get("/simulations/{simulation_id}", response_model=dict)
def get_simulation(simulation_id: int, session: Session = Depends(get_session)):
    run = session.get(SimulationRun, simulation_id)
    if not run:
        raise HTTPException(404, "Simulation run not found")
    return {
        "id": run.id,
        "run_label": run.run_label,
        "status": run.status,
        "model_version": run.model_version,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "project_id": run.project_id,
        "configuration_id": run.configuration_id,
        "scenario_id": run.scenario_id,
        "result_nominal_voltage_v": run.result_nominal_voltage_v,
        "result_nominal_energy_wh": run.result_nominal_energy_wh,
        "result_usable_energy_wh": run.result_usable_energy_wh,
        "result_max_temp_c": run.result_max_temp_c,
        "result_min_soc": run.result_min_soc,
        "result_energy_delivered_wh": run.result_energy_delivered_wh,
        "result_soh_capacity_pct": getattr(run, "result_soh_capacity_pct", None),
        "result_soh_resistance_pct": getattr(run, "result_soh_resistance_pct", None),
        "result_throughput_ah": getattr(run, "result_throughput_ah", None),
        "result_efc": getattr(run, "result_efc", None),
        "battery_aging": json.loads(run.battery_aging_json) if getattr(run, "battery_aging_json", None) else None,
        "multi_node_thermal": json.loads(run.multi_node_thermal_json) if getattr(run, "multi_node_thermal_json", None) else None,
        "constraint_pass": run.constraint_pass,
        "constraint_fail": run.constraint_fail,
        "constraint_warning": run.constraint_warning,
        "constraint_unverified": run.constraint_unverified,
        "inputs_snapshot": json.loads(run.inputs_snapshot_json) if run.inputs_snapshot_json else None,
    }


@router.get("/simulations/{simulation_id}/results")
def get_simulation_results(simulation_id: int, session: Session = Depends(get_session)):
    run = session.get(SimulationRun, simulation_id)
    if not run:
        raise HTTPException(404, "Simulation run not found")
    constraints = session.exec(
        select(ConstraintResult).where(ConstraintResult.simulation_run_id == simulation_id)
    ).all()
    timeseries = json.loads(run.timeseries_json) if run.timeseries_json else []
    assumptions = json.loads(run.assumptions_json) if run.assumptions_json else []

    cfg = run.configuration
    cfg_ns = cfg.ns if cfg else 14
    cfg_np = cfg.np if cfg else 8
    cfg_cooling = (cfg.cooling_type.value if hasattr(cfg.cooling_type, "value") else str(cfg.cooling_type)) if cfg else "passive"

    return {
        "simulation_run_id": simulation_id,
        "configuration_id": run.configuration_id,
        "configuration_ns": cfg_ns,
        "configuration_np": cfg_np,
        "cooling_type": cfg_cooling,
        "status": run.status,
        "assumptions": assumptions,
        "result_nominal_voltage_v": run.result_nominal_voltage_v,
        "result_nominal_energy_wh": run.result_nominal_energy_wh,
        "result_usable_energy_wh": run.result_usable_energy_wh,
        "result_max_temp_c": run.result_max_temp_c,
        "result_min_soc": run.result_min_soc,
        "result_energy_delivered_wh": run.result_energy_delivered_wh,
        "result_soh_capacity_pct": getattr(run, "result_soh_capacity_pct", None),
        "result_soh_resistance_pct": getattr(run, "result_soh_resistance_pct", None),
        "result_throughput_ah": getattr(run, "result_throughput_ah", None),
        "result_efc": getattr(run, "result_efc", None),
        "battery_aging": json.loads(run.battery_aging_json) if getattr(run, "battery_aging_json", None) else None,
        "multi_node_thermal": json.loads(run.multi_node_thermal_json) if getattr(run, "multi_node_thermal_json", None) else None,
        "constraint_pass": run.constraint_pass,
        "constraint_fail": run.constraint_fail,
        "constraint_warning": run.constraint_warning,
        "constraint_unverified": run.constraint_unverified,
        "constraints": [
            {
                "id": c.id,
                "rule_id": c.rule_id,
                "status": c.status.value,
                "observed_value": c.observed_value,
                "threshold": c.threshold,
                "units": c.units,
                "explanation": c.explanation,
                "source_assumption": c.source_assumption,
                "corrective_action": c.corrective_action,
            }
            for c in constraints
        ],
        "timeseries": timeseries,
        "model_version": run.model_version,
        "completed_at": run.completed_at,
    }


@router.get("/projects/{project_id}/simulations")
def list_project_simulations(project_id: int, session: Session = Depends(get_session)):
    runs = session.exec(
        select(SimulationRun).where(SimulationRun.project_id == project_id)
    ).all()
    return [
        {
            "id": r.id,
            "run_label": r.run_label,
            "status": r.status,
            "created_at": r.created_at,
            "completed_at": r.completed_at,
            "constraint_pass": r.constraint_pass,
            "constraint_fail": r.constraint_fail,
            "constraint_warning": r.constraint_warning,
            "result_nominal_energy_wh": r.result_nominal_energy_wh,
            "result_max_temp_c": r.result_max_temp_c,
        }
        for r in runs
    ]


# ── Duty Cycle Segments ───────────────────────────────────────────────────────

@router.get("/scenarios/{scenario_id}/segments", response_model=list[DutyCycleSegmentRead])
def list_scenario_segments(scenario_id: int, session: Session = Depends(get_session)):
    scenario = session.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    segments = session.exec(
        select(DutyCycleSegment)
        .where(DutyCycleSegment.scenario_id == scenario_id)
        .order_by(DutyCycleSegment.segment_index)
    ).all()
    return segments


@router.post("/scenarios/{scenario_id}/segments", response_model=DutyCycleSegmentRead, status_code=201)
def add_scenario_segment(
    scenario_id: int,
    body: DutyCycleSegmentCreate,
    session: Session = Depends(get_session),
):
    scenario = session.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    segment = DutyCycleSegment(
        scenario_id=scenario_id,
        segment_index=body.segment_index,
        duration_s=body.duration_s,
        profile_type=body.profile_type,
        discharge_current_a=body.discharge_current_a,
        ambient_temp_c=body.ambient_temp_c,
        notes=body.notes,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)
    return segment


@router.delete("/scenarios/{scenario_id}/segments/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario_segment(
    scenario_id: int,
    segment_id: int,
    session: Session = Depends(get_session),
):
    seg = session.get(DutyCycleSegment, segment_id)
    if not seg or seg.scenario_id != scenario_id:
        raise HTTPException(404, "Duty cycle segment not found")
    session.delete(seg)
    session.commit()
    return None


# ── Vehicle Load Analysis Endpoint ───────────────────────────────────────────

@router.post("/vehicle-load/calculate", response_model=VehicleLoadResponse)
def calculate_vehicle_load_endpoint(body: VehicleLoadRequest):
    try:
        result = calculate_vehicle_load(
            vehicle_mass_kg=body.vehicle_mass_kg,
            payload_mass_kg=body.payload_mass_kg,
            speed_kmh=body.speed_kmh,
            speed_mps=body.speed_mps,
            grade_pct=body.grade_pct,
            cr=body.cr,
            cd=body.cd,
            frontal_area_m2=body.frontal_area_m2,
            air_density_kg_per_m3=body.air_density_kg_per_m3,
            acceleration_mps2=body.acceleration_mps2,
            drivetrain_efficiency=body.drivetrain_efficiency,
            regen_efficiency=body.regen_efficiency,
            auxiliary_power_w=body.auxiliary_power_w,
            nominal_pack_voltage_v=body.nominal_pack_voltage_v,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/vehicle-load/drive-cycle/simulate")
def simulate_drive_cycle_endpoint(body: DriveCycleRequest):
    try:
        custom_pts = None
        if body.custom_points:
            custom_pts = [(float(p[0]), float(p[1]), float(p[2])) for p in body.custom_points]
        result = simulate_drive_cycle(
            cycle_type=body.cycle_type,
            vehicle_mass_kg=body.vehicle_mass_kg,
            payload_mass_kg=body.payload_mass_kg,
            cr=body.cr,
            cd=body.cd,
            frontal_area_m2=body.frontal_area_m2,
            air_density_kg_per_m3=body.air_density_kg_per_m3,
            drivetrain_efficiency=body.drivetrain_efficiency,
            regen_efficiency=body.regen_efficiency,
            auxiliary_power_w=body.auxiliary_power_w,
            nominal_pack_voltage_v=body.nominal_pack_voltage_v,
            road_surface=body.road_surface,
            custom_points=custom_pts,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/vehicle-load/drive-cycle/export-scenario", response_model=ScenarioRead, status_code=201)
def export_drive_cycle_scenario_endpoint(
    body: DriveCycleExportScenarioRequest,
    session: Session = Depends(get_session),
):
    try:
        res = simulate_drive_cycle(
            cycle_type=body.cycle_type,
            vehicle_mass_kg=body.vehicle_mass_kg,
            payload_mass_kg=body.payload_mass_kg,
            cr=body.cr,
            cd=body.cd,
            frontal_area_m2=body.frontal_area_m2,
            drivetrain_efficiency=body.drivetrain_efficiency,
            regen_efficiency=body.regen_efficiency,
            auxiliary_power_w=body.auxiliary_power_w,
            nominal_pack_voltage_v=body.nominal_pack_voltage_v,
            road_surface=body.road_surface,
        )

        name = body.scenario_name or f"Route: {res['title']}"
        desc = (
            f"Generated from dynamic drive cycle ({res['title']}). "
            f"Distance: {res['total_distance_km']} km, Net Energy: {res['net_energy_consumed_wh']} Wh "
            f"({res['specific_consumption_wh_per_km']} Wh/km), Peak current: {res['peak_discharge_current_a']} A."
        )

        avg_discharge_a = max(1.0, res["peak_discharge_current_a"] * 0.45)
        scenario = Scenario(
            project_id=body.project_id,
            name=name,
            description=desc,
            duration_s=min(3600.0, res["duration_s"]),
            time_step_s=1.0,
            profile_type="mixed",
            discharge_current_a=round(avg_discharge_a, 2),
            ambient_temp_c=body.ambient_temp_c,
            initial_cell_temp_c=body.ambient_temp_c,
        )
        session.add(scenario)
        session.commit()
        session.refresh(scenario)

        # Create multi-segment breakdown from drive cycle phases
        seg_duration = max(30.0, scenario.duration_s / 4.0)
        phases = [
            ("Urban Low-Speed / Flat", avg_discharge_a * 0.6, "steady_cruise"),
            ("Hill Climb / Acceleration", res["peak_discharge_current_a"], "high_load"),
            ("Downhill Regenerative Braking", -abs(res["peak_regen_current_a"]), "regen"),
            ("Suburban Return Cruise", avg_discharge_a * 0.8, "steady_cruise"),
        ]
        for idx, (note, current_val, ptype) in enumerate(phases):
            seg = DutyCycleSegment(
                scenario_id=scenario.id,
                segment_index=idx,
                duration_s=round(seg_duration, 1),
                profile_type=ptype,
                discharge_current_a=round(current_val, 2),
                ambient_temp_c=body.ambient_temp_c,
                notes=note,
            )
            session.add(seg)
        session.commit()

        return scenario
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── Provenance, Validation, and Uncertainty Endpoints ─────────────────────────

@router.get("/simulations/{simulation_id}/provenance")
def get_simulation_provenance(simulation_id: int, session: Session = Depends(get_session)):
    run = session.get(SimulationRun, simulation_id)
    if not run:
        raise HTTPException(404, "Simulation run not found")
    cfg = session.get(Configuration, run.configuration_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    cell = session.get(CellSpec, cfg.cell_spec_id) if cfg.cell_spec_id else None
    scenario = session.get(Scenario, run.scenario_id) if run.scenario_id else None

    from app.models import Requirement
    req = session.exec(select(Requirement).where(Requirement.project_id == run.project_id)).first()

    catalog = generate_provenance_catalog(
        cell=cell,
        configuration=cfg,
        scenario=scenario,
        requirement=req,
    )
    return catalog


@router.get("/simulations/{simulation_id}/validation")
def get_simulation_validation(
    simulation_id: int,
    target_metric: str = "voltage_v",
    session: Session = Depends(get_session),
):
    run = session.get(SimulationRun, simulation_id)
    if not run:
        raise HTTPException(404, "Simulation run not found")
    ts = json.loads(run.timeseries_json) if run.timeseries_json else []
    validation_report = run_benchmark_validation(
        simulated_timeseries=ts,
        target_metric=target_metric,
    )
    return validation_report


@router.post("/simulations/{simulation_id}/uncertainty")
def run_simulation_uncertainty(
    simulation_id: int,
    body: UncertaintyRequest = UncertaintyRequest(),
    session: Session = Depends(get_session),
):
    run = session.get(SimulationRun, simulation_id)
    if not run:
        raise HTTPException(404, "Simulation run not found")
    cfg = session.get(Configuration, run.configuration_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    cell = session.get(CellSpec, cfg.cell_spec_id) if cfg.cell_spec_id else None
    if not cell:
        raise HTTPException(400, "Cell spec missing for uncertainty analysis")
    scenario = session.get(Scenario, run.scenario_id) if run.scenario_id else None
    if not scenario:
        raise HTTPException(400, "Scenario missing for uncertainty analysis")

    uncertainty_results = run_monte_carlo_uncertainty(
        cell=cell,
        configuration=cfg,
        scenario=scenario,
        n_iterations=body.n_iterations,
        random_seed=body.random_seed,
        capacity_sigma_pct=body.capacity_sigma_pct,
        resistance_sigma_pct=body.resistance_sigma_pct,
        mass_sigma_pct=body.mass_sigma_pct,
        temp_sigma_c=body.temp_sigma_c,
    )
    return uncertainty_results


@router.post("/validation/ingest-check")
def validate_dataset_ingestion(
    body: ExperimentalValidationRequest,
):
    report, records = parse_and_validate_csv_dataset(
        csv_content=body.csv_content,
        custom_mapping=body.custom_mapping,
        is_physical_data=body.is_physical_laboratory_data,
        dataset_name=body.dataset_name,
    )
    return {
        "report": dataclasses.asdict(report),
        "record_count": len(records),
        "sample_records": records[:5],
    }


@router.post("/simulations/{simulation_id}/validate-dataset")
def validate_simulation_against_dataset(
    simulation_id: int,
    body: ExperimentalValidationRequest,
    session: Session = Depends(get_session),
):
    run = session.get(SimulationRun, simulation_id)
    if not run:
        raise HTTPException(404, "Simulation run not found")

    report, records = parse_and_validate_csv_dataset(
        csv_content=body.csv_content,
        custom_mapping=body.custom_mapping,
        is_physical_data=body.is_physical_laboratory_data,
        dataset_name=body.dataset_name,
    )
    if not report.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Dataset validation rejected: CSV violates schema or physical bounds.",
                "errors": report.errors,
                "warnings": report.warnings,
                "report": dataclasses.asdict(report),
            },
        )

    sim_timeseries = json.loads(run.timeseries_json) if run.timeseries_json else []
    validation_eval = align_and_evaluate_validation(
        simulated_timeseries=sim_timeseries,
        measured_timeseries=records,
        is_physical_laboratory_data=body.is_physical_laboratory_data,
        dataset_name=body.dataset_name,
        split_ratio_calibration=body.split_ratio_calibration,
        split_mode=body.split_mode,
        voltage_rmse_threshold_v=body.voltage_rmse_threshold_v if body.voltage_rmse_threshold_v is not None else 0.050,
        temp_rmse_threshold_c=body.temp_rmse_threshold_c if body.temp_rmse_threshold_c is not None else 2.5,
        min_r2_threshold=body.min_r2_threshold if body.min_r2_threshold is not None else 0.95,
        min_aligned_samples=body.min_aligned_samples if body.min_aligned_samples is not None else 10,
    )

    return {
        "dataset_report": dataclasses.asdict(report),
        "validation_result": dataclasses.asdict(validation_eval),
    }


# ── Public Dataset Benchmark Endpoints ────────────────────────────────────────

@router.get("/validation/public-dataset-evaluation")
def get_public_dataset_evaluation():
    """
    Returns empirical validation metrics and model evaluation results against
    the official NASA Ames Prognostics Center of Excellence (PCoE) battery dataset.
    """
    from pathlib import Path
    import json
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    summary_path = base_dir / "validation_artifacts" / "validation_summary.json"
    
    if not summary_path.exists():
        from app.services.nasa_dataset_adapter import run_nasa_validation_pipeline
        return run_nasa_validation_pipeline()

    with open(summary_path, "r") as f:
        return json.load(f)


@router.get("/validation/dataset-manifest")
def get_dataset_manifest():
    """
    Returns the cryptographic provenance manifest, SHA-256 hashes, source URLs,
    and signal schemas for public datasets ingested into BattLab.
    """
    from pathlib import Path
    import json
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    manifest_path = base_dir / "validation_artifacts" / "dataset_manifest.json"

    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Dataset manifest has not been generated.")

    with open(manifest_path, "r") as f:
        return json.load(f)




