"""BattLab — API Router: Projects"""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    Configuration, Project, Requirement, SimulationRun, CellSpec,
    ConstraintResult, ConstraintStatus, Report, ConfigurationComponent,
)
from app.schemas import (
    ProjectCreate, ProjectRead, ProjectSummary, ProjectUpdate,
    RequirementCreate, RequirementRead,
    ConfigurationCreate, ConfigurationRead, ConfigurationUpdate,
    CandidateRequest, CandidateSummary,
)
from app.services.candidate_generator import generate_candidates
from app.services.electrical import ElectricalInputs, calculate_pack

router = APIRouter(prefix="/projects", tags=["projects"])


def get_session():
    with Session(engine) as session:
        yield session


# ── Projects ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ProjectSummary])
def list_projects(session: Session = Depends(get_session)):
    projects = session.exec(select(Project)).all()
    result = []
    for p in projects:
        runs = session.exec(
            select(SimulationRun).where(SimulationRun.project_id == p.id)
        ).all()
        latest = max(runs, key=lambda r: r.created_at, default=None) if runs else None
        w = sum(r.constraint_warning + r.constraint_fail for r in runs)
        cfgs = session.exec(
            select(Configuration).where(Configuration.project_id == p.id)
        ).all()
        summary = ProjectSummary(
            **ProjectRead.model_validate(p).model_dump(),
            latest_sim_status=latest.status.value if latest else None,
            warning_count=w,
            configuration_count=len(cfgs),
        )
        result.append(summary)
    return result


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)):
    project = Project(**body.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: Session = Depends(get_session)):
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, body: ProjectUpdate, session: Session = Depends(get_session)):
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, session: Session = Depends(get_session)):
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    # Cascade delete all dependent children in child-to-parent order
    reports = session.exec(select(Report).where(Report.project_id == p.id)).all()
    for rep in reports:
        session.delete(rep)

    sims = session.exec(select(SimulationRun).where(SimulationRun.project_id == p.id)).all()
    for sim in sims:
        crs = session.exec(select(ConstraintResult).where(ConstraintResult.simulation_run_id == sim.id)).all()
        for cr in crs:
            session.delete(cr)
        session.delete(sim)

    configs = session.exec(select(Configuration).where(Configuration.project_id == p.id)).all()
    for cfg in configs:
        comps = session.exec(select(ConfigurationComponent).where(ConfigurationComponent.configuration_id == cfg.id)).all()
        for c in comps:
            session.delete(c)
        session.delete(cfg)

    reqs = session.exec(select(Requirement).where(Requirement.project_id == p.id)).all()
    for r in reqs:
        session.delete(r)

    session.delete(p)
    session.commit()


@router.delete("/{project_id}/configurations/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_configuration(project_id: int, config_id: int, session: Session = Depends(get_session)):
    _require_project(project_id, session)
    cfg = session.exec(
        select(Configuration).where(
            Configuration.id == config_id,
            Configuration.project_id == project_id
        )
    ).first()
    if not cfg:
        raise HTTPException(404, "Configuration not found")

    sims = session.exec(select(SimulationRun).where(SimulationRun.configuration_id == config_id)).all()
    for sim in sims:
        crs = session.exec(select(ConstraintResult).where(ConstraintResult.simulation_run_id == sim.id)).all()
        for cr in crs:
            session.delete(cr)
        session.delete(sim)

    comps = session.exec(select(ConfigurationComponent).where(ConfigurationComponent.configuration_id == config_id)).all()
    for c in comps:
        session.delete(c)

    session.delete(cfg)
    session.commit()


# ── Requirements ──────────────────────────────────────────────────────────────

@router.get("/{project_id}/requirements", response_model=list[RequirementRead])
def list_requirements(project_id: int, session: Session = Depends(get_session)):
    _require_project(project_id, session)
    reqs = session.exec(
        select(Requirement).where(Requirement.project_id == project_id)
    ).all()
    result = []
    for r in reqs:
        import json
        hc = json.loads(r.hard_constraints_json) if r.hard_constraints_json else None
        rr = RequirementRead.model_validate(r)
        rr.hard_constraints = hc
        result.append(rr)
    return result


@router.post("/{project_id}/requirements", response_model=RequirementRead, status_code=201)
def create_requirement(project_id: int, body: RequirementCreate, session: Session = Depends(get_session)):
    _require_project(project_id, session)
    import json
    data = body.model_dump(exclude={"hard_constraints"})
    data["project_id"] = project_id
    if body.hard_constraints:
        data["hard_constraints_json"] = json.dumps(body.hard_constraints)
    req = Requirement(**data)
    session.add(req)
    session.commit()
    session.refresh(req)
    rr = RequirementRead.model_validate(req)
    rr.hard_constraints = body.hard_constraints
    return rr


# ── Configurations ────────────────────────────────────────────────────────────

@router.get("/{project_id}/configurations", response_model=list[ConfigurationRead])
def list_configurations(project_id: int, session: Session = Depends(get_session)):
    _require_project(project_id, session)
    cfgs = session.exec(
        select(Configuration).where(Configuration.project_id == project_id)
    ).all()
    result = []
    for cfg in cfgs:
        cr = ConfigurationRead.model_validate(cfg)
        if cfg.cell_spec_id:
            from app.schemas import CellSpecRead
            cell = session.get(CellSpec, cfg.cell_spec_id)
            if cell:
                cr.cell_spec = CellSpecRead.model_validate(cell)
        result.append(cr)
    return result


@router.post("/{project_id}/configurations", response_model=ConfigurationRead, status_code=201)
def create_configuration(project_id: int, body: ConfigurationCreate, session: Session = Depends(get_session)):
    _require_project(project_id, session)
    data = body.model_dump()
    data["project_id"] = project_id
    cfg = Configuration(**data)
    _recalculate_config(cfg, session)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return _cfg_with_cell(cfg, session)


@router.get("/configurations/{configuration_id}", response_model=ConfigurationRead)
def get_configuration(configuration_id: int, session: Session = Depends(get_session)):
    cfg = session.get(Configuration, configuration_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    return _cfg_with_cell(cfg, session)


@router.patch("/configurations/{configuration_id}", response_model=ConfigurationRead)
def update_configuration(configuration_id: int, body: ConfigurationUpdate, session: Session = Depends(get_session)):
    cfg = session.get(Configuration, configuration_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cfg, k, v)
    cfg.updated_at = datetime.utcnow()
    _recalculate_config(cfg, session)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return _cfg_with_cell(cfg, session)


@router.get("/configurations/{configuration_id}/mass-breakdown")
def get_configuration_mass_breakdown(
    configuration_id: int,
    session: Session = Depends(get_session),
):
    cfg = session.get(Configuration, configuration_id)
    if not cfg:
        raise HTTPException(404, "Configuration not found")
    cell = session.get(CellSpec, cfg.cell_spec_id) if cfg.cell_spec_id else None

    from app.services.mass_model import calculate_pack_mass_breakdown
    breakdown = calculate_pack_mass_breakdown(
        ns=cfg.ns,
        np_=cfg.np,
        cell_mass_kg=cell.mass_kg if cell else None,
        cooling_type=cfg.cooling_type,
        form_factor=cell.form_factor if cell else "21700",
        nominal_energy_wh=cfg.calc_nominal_energy_wh,
    )
    return breakdown



# ── Candidate Generation ──────────────────────────────────────────────────────

@router.post("/{project_id}/candidates", response_model=list[CandidateSummary])
def generate_candidates_endpoint(
    project_id: int,
    body: CandidateRequest,
    session: Session = Depends(get_session),
):
    _require_project(project_id, session)
    cell = session.get(CellSpec, body.cell_spec_id)
    if not cell:
        raise HTTPException(404, "Cell not found")

    candidates = generate_candidates(
        target_voltage_v=body.target_voltage_v,
        target_energy_wh=body.target_energy_wh,
        energy_is_usable=body.energy_is_usable,
        v_cell_nominal=cell.nominal_voltage_v,
        ah_cell=cell.nominal_capacity_ah,
        v_cell_min=cell.min_voltage_v,
        v_cell_max=cell.max_voltage_v,
        r_cell_ohm=cell.internal_resistance_ohm,
        cell_mass_kg=cell.mass_kg,
        unit_cost_usd=cell.unit_cost_usd,
        max_continuous_cell_a=cell.max_continuous_discharge_a,
        max_mass_kg=body.max_mass_kg,
        max_cost_usd=body.max_cost_usd,
        continuous_pack_a=body.continuous_current_a,
        max_candidates=body.max_candidates,
    )
    return [CandidateSummary(**vars(c)) for c in candidates]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_project(project_id: int, session: Session) -> Project:
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _recalculate_config(cfg: Configuration, session: Session) -> None:
    """Update calculated cache fields."""
    if not cfg.cell_spec_id:
        return
    cell = session.get(CellSpec, cfg.cell_spec_id)
    if not cell:
        return
    inputs = ElectricalInputs(
        ns=cfg.ns,
        np=cfg.np,
        v_cell_nominal=cell.nominal_voltage_v,
        ah_cell=cell.nominal_capacity_ah,
        r_cell_ohm=cell.internal_resistance_ohm,
        usable_soc_window=cfg.usable_soc_window,
        v_cell_min=cell.min_voltage_v,
        v_cell_max=cell.max_voltage_v,
    )
    try:
        pack = calculate_pack(inputs)
        cfg.calc_nominal_voltage_v = pack.nominal_voltage_v
        cfg.calc_nominal_energy_wh = pack.nominal_energy_wh
        cfg.calc_total_cells = pack.total_cells
        cfg.calc_cell_mass_kg = (pack.total_cells * cell.mass_kg) if cell.mass_kg else None
        cfg.calc_bom_cost_usd = (pack.total_cells * cell.unit_cost_usd) if cell.unit_cost_usd else None
    except Exception:
        pass


def _cfg_with_cell(cfg: Configuration, session: Session) -> ConfigurationRead:
    cr = ConfigurationRead.model_validate(cfg)
    if cfg.cell_spec_id:
        from app.schemas import CellSpecRead
        cell = session.get(CellSpec, cfg.cell_spec_id)
        if cell:
            cr.cell_spec = CellSpecRead.model_validate(cell)
    return cr
