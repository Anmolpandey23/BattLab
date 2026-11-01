"""BattLab — API Router: Comparison & Reports"""
from __future__ import annotations

import json
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    CellSpec, Configuration, ConstraintResult,
    Report, SimulationRun,
)
from app.schemas import CompareRequest
from app.services.comparison import compare_runs
from app.services.reports import (
    generate_csv_timeseries, generate_json_config, generate_pdf_report,
)

router = APIRouter(tags=["compare_reports"])


def get_session():
    with Session(engine) as session:
        yield session


# ── Compare ───────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/compare")
def compare_configurations(
    project_id: int,
    body: CompareRequest,
    session: Session = Depends(get_session),
):
    runs_data = []
    for run_id in body.simulation_run_ids:
        run = session.get(SimulationRun, run_id)
        if not run:
            raise HTTPException(404, f"Simulation run {run_id} not found")
        if run.project_id != project_id:
            raise HTTPException(400, f"Run {run_id} does not belong to project {project_id}")
        cfg = session.get(Configuration, run.configuration_id)
        runs_data.append({
            "run_id": run.id,
            "run_label": run.run_label or f"Run {run.id}",
            "config_label": cfg.label if cfg else "?",
            "nominal_voltage_v": run.result_nominal_voltage_v,
            "nominal_energy_wh": run.result_nominal_energy_wh,
            "usable_energy_wh": run.result_usable_energy_wh,
            "max_temp_c": run.result_max_temp_c,
            "min_soc": run.result_min_soc,
            "energy_delivered_wh": run.result_energy_delivered_wh,
            "constraint_pass": run.constraint_pass,
            "constraint_fail": run.constraint_fail,
            "constraint_warning": run.constraint_warning,
            "constraint_unverified": run.constraint_unverified,
            "cell_mass_kg": cfg.calc_cell_mass_kg if cfg else None,
            "bom_cost_usd": cfg.calc_bom_cost_usd if cfg else None,
            "ns": cfg.ns if cfg else None,
            "np": cfg.np if cfg else None,
            "total_cells": cfg.calc_total_cells if cfg else None,
        })
    # Ensure run labels are unique across compare set to avoid metrics key collisions
    labels_seen: dict[str, int] = {}
    for r in runs_data:
        lbl = str(r["run_label"])
        labels_seen[lbl] = labels_seen.get(lbl, 0) + 1
    if any(count > 1 for count in labels_seen.values()):
        for r in runs_data:
            r["run_label"] = f"Run #{r['run_id']}: {r['run_label']}"
    return compare_runs(runs_data, body.weights)


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/reports")
def list_project_reports(project_id: int, session: Session = Depends(get_session)):
    """List all reports generated for a project."""
    reports = session.exec(
        select(Report).where(Report.project_id == project_id)
    ).all()
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "format": r.format,
            "filename": r.filename,
            "created_at": r.created_at,
            "simulation_run_ids": json.loads(r.simulation_run_ids_json) if r.simulation_run_ids_json else [],
        }
        for r in reports
    ]


@router.post("/projects/{project_id}/reports")
def generate_report(
    project_id: int,
    body: dict,
    session: Session = Depends(get_session),
):
    from app.models import Project, Requirement
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    fmt = body.get("format", "pdf")
    run_id = body.get("simulation_run_id")

    # Validate format before touching the database
    supported_formats = {"pdf", "csv", "json"}
    if fmt not in supported_formats:
        raise HTTPException(400, f"Unsupported format '{fmt}'. Supported: {sorted(supported_formats)}")

    if not run_id:
        raise HTTPException(400, "simulation_run_id required")

    run = session.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(404, "Simulation run not found")

    cfg = session.get(Configuration, run.configuration_id)
    cell = session.get(CellSpec, cfg.cell_spec_id) if cfg and cfg.cell_spec_id else None
    req = session.exec(
        select(Requirement).where(Requirement.project_id == project_id)
    ).first()
    constraints = session.exec(
        select(ConstraintResult).where(ConstraintResult.simulation_run_id == run_id)
    ).all()
    timeseries = json.loads(run.timeseries_json) if run.timeseries_json else []

    # Create Report record
    report = Report(
        project_id=project_id,
        format=fmt,
        filename="pending",
        file_path="pending",
        simulation_run_ids_json=json.dumps([run_id]),
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    try:
        if fmt == "pdf":
            path = generate_pdf_report(
                project={"name": project.name, "application_category": project.application_category,
                          "engineer_label": project.engineer_label, "design_version": project.design_version},
                requirement={"target_voltage_v": req.target_voltage_v,
                              "target_energy_wh": req.target_energy_wh,
                              "energy_is_usable": req.energy_is_usable,
                              "max_mass_kg": req.max_mass_kg,
                              "max_cost_usd": req.max_cost_usd,
                              "min_ambient_temp_c": req.min_ambient_temp_c,
                              "max_ambient_temp_c": req.max_ambient_temp_c,
                              "cooling_preference": req.cooling_preference,
                              "hard_constraints": json.loads(req.hard_constraints_json) if req.hard_constraints_json else [],
                             } if req else None,
                configuration={"label": cfg.label, "ns": cfg.ns, "np": cfg.np,
                               "calc_total_cells": cfg.calc_total_cells,
                               "calc_nominal_voltage_v": cfg.calc_nominal_voltage_v,
                               "calc_nominal_energy_wh": cfg.calc_nominal_energy_wh,
                               "cooling_type": cfg.cooling_type,
                               "usable_soc_window": cfg.usable_soc_window,
                              } if cfg else {},
                simulation_run={"id": run.id, "model_version": run.model_version,
                                "result_nominal_voltage_v": run.result_nominal_voltage_v,
                                "result_nominal_energy_wh": run.result_nominal_energy_wh,
                                "result_usable_energy_wh": run.result_usable_energy_wh,
                                "result_max_temp_c": run.result_max_temp_c,
                                "result_min_soc": run.result_min_soc,
                                "result_energy_delivered_wh": run.result_energy_delivered_wh,
                               },
                timeseries=timeseries,
                constraints=[{"rule_id": c.rule_id, "status": c.status.value,
                              "observed_value": c.observed_value, "threshold": c.threshold,
                              "units": c.units, "explanation": c.explanation} for c in constraints],
                assumptions=[],
                report_id=report.id,
            )
        elif fmt == "csv":
            path = generate_csv_timeseries(timeseries, report.id)
        elif fmt == "json":
            path = generate_json_config(
                configuration={
                    "id": cfg.id,
                    "label": cfg.label,
                    "ns": cfg.ns,
                    "np": cfg.np,
                    "cooling_type": cfg.cooling_type,
                    "usable_soc_window": cfg.usable_soc_window,
                    "interconnect_resistance_ohm": cfg.interconnect_resistance_ohm,
                    "calc_nominal_voltage_v": cfg.calc_nominal_voltage_v,
                    "calc_nominal_energy_wh": cfg.calc_nominal_energy_wh,
                    "calc_total_cells": cfg.calc_total_cells,
                    "calc_cell_mass_kg": cfg.calc_cell_mass_kg,
                    "calc_bom_cost_usd": cfg.calc_bom_cost_usd,
                } if cfg else {},
                cell_spec={
                    "id": cell.id,
                    "manufacturer": cell.manufacturer,
                    "model": cell.model,
                    "chemistry": cell.chemistry,
                    "form_factor": cell.form_factor,
                    "nominal_voltage_v": cell.nominal_voltage_v,
                    "min_voltage_v": cell.min_voltage_v,
                    "max_voltage_v": cell.max_voltage_v,
                    "nominal_capacity_ah": cell.nominal_capacity_ah,
                    "internal_resistance_ohm": cell.internal_resistance_ohm,
                    "mass_kg": cell.mass_kg,
                    "max_continuous_discharge_a": cell.max_continuous_discharge_a,
                    "max_operating_temp_c": cell.max_operating_temp_c,
                    "min_operating_temp_c": cell.min_operating_temp_c,
                    "unit_cost_usd": cell.unit_cost_usd,
                    "data_status": cell.data_status,
                    "source_notes": cell.source_notes,
                } if cell else {},
                report_id=report.id,
            )
        else:
            raise HTTPException(400, f"Unsupported format: {fmt}")

        report.filename = os.path.basename(path)
        report.file_path = path
        session.add(report)
        session.commit()
        return {"report_id": report.id, "filename": report.filename}

    except Exception as e:
        raise HTTPException(500, f"Report generation failed: {str(e)[:200]}")


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, session: Session = Depends(get_session)):
    report = session.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    if not os.path.exists(report.file_path):
        raise HTTPException(404, "Report file not found on disk")
    media_types = {"pdf": "application/pdf", "csv": "text/csv", "json": "application/json"}
    return FileResponse(
        report.file_path,
        media_type=media_types.get(report.format, "application/octet-stream"),
        filename=report.filename,
    )
