"""
BattLab — Database initialization and seeding
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine, select, text

from app.models import (
    CellSpec, ComponentSpec, Project, Requirement, Configuration,
    Scenario, CoolingType, ApplicationCategory, DesignMode,
    SimulationRun, SimulationStatus,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./battlab.db")
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

DATA_DIR = Path(__file__).parent / "data"


def init_db() -> None:
    """Create tables, run migrations, and seed initial data."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _migrate_columns(session)
        _seed_cells(session)
        _seed_components(session)
        _seed_scenarios(session)
        _seed_demo_projects(session)
        session.commit()


def _migrate_columns(session: Session) -> None:
    """Safe idempotent column migrations for existing SQLite instances."""
    cols = [
        ("result_soh_capacity_pct", "FLOAT"),
        ("result_soh_resistance_pct", "FLOAT"),
        ("result_throughput_ah", "FLOAT"),
        ("result_efc", "FLOAT"),
        ("battery_aging_json", "TEXT"),
        ("multi_node_thermal_json", "TEXT"),
    ]
    for col_name, col_type in cols:
        try:
            session.exec(text(f"ALTER TABLE simulation_runs ADD COLUMN {col_name} {col_type}"))
            session.commit()
        except Exception:
            pass


def _seed_cells(session: Session) -> None:
    cells_path = DATA_DIR / "seed_cells.json"
    with open(cells_path) as f:
        cells = json.load(f)
    for c in cells:
        exists = session.exec(select(CellSpec).where(CellSpec.model == c["model"])).first()
        if not exists:
            session.add(CellSpec(**c))


def _seed_components(session: Session) -> None:
    from app.models import ComponentSpec
    existing = session.exec(select(ComponentSpec).where(ComponentSpec.is_seed == True)).all()
    if existing:
        return
    comp_path = DATA_DIR / "seed_components.json"
    with open(comp_path) as f:
        comps = json.load(f)
    for c in comps:
        session.add(ComponentSpec(**c))


def _seed_scenarios(session: Session) -> None:
    existing = session.exec(select(Scenario).where(Scenario.is_seed == True)).all()
    if existing:
        return
    scenarios = [
        Scenario(
            name="Steady Cruise (25°C)",
            description="Constant discharge at 1C rate. Summer ambient. Illustrative synthetic profile.",
            is_seed=True,
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=1.0,
            duration_s=3600.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
        ),
        Scenario(
            name="Mixed Driving (25°C)",
            description="Mixed acceleration and cruise. Summer ambient. Illustrative synthetic profile.",
            is_seed=True,
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=1.0,
            duration_s=3600.0,
            time_step_s=10.0,
            profile_type="mixed",
        ),
        Scenario(
            name="Winter Cold Start (-10°C)",
            description="Steady cruise at cold ambient. Illustrative synthetic profile.",
            is_seed=True,
            ambient_temp_c=-10.0,
            initial_cell_temp_c=-10.0,
            initial_soc=1.0,
            duration_s=3600.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
        ),
        Scenario(
            name="High Load Summer (35°C)",
            description="High-load profile at elevated ambient. Illustrative synthetic profile.",
            is_seed=True,
            ambient_temp_c=35.0,
            initial_cell_temp_c=35.0,
            initial_soc=1.0,
            duration_s=3600.0,
            time_step_s=10.0,
            profile_type="high_load",
        ),
        Scenario(
            name="Aged Cell Sensitivity (25°C, +20% R, -15% Cap)",
            description="Sensitivity scenario modelling aged cells with increased resistance and reduced capacity.",
            is_seed=True,
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=1.0,
            duration_s=3600.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
            resistance_multiplier=1.20,
            capacity_variation_pct=15.0,
        ),
    ]
    for s in scenarios:
        session.add(s)


def _seed_demo_projects(session: Session) -> None:
    """Seed comprehensive initial engineering projects and configurations."""
    projects_file = DATA_DIR / "seed_projects.json"
    if not projects_file.exists():
        return

    with open(projects_file, "r", encoding="utf-8") as f:
        projects_data = json.load(f)

    for p_data in projects_data:
        existing = session.exec(select(Project).where(Project.name == p_data["name"])).first()
        if existing:
            continue

        category_str = p_data.get("application_category", "custom")
        try:
            category = ApplicationCategory(category_str)
        except ValueError:
            category = ApplicationCategory.custom

        project = Project(
            name=p_data["name"],
            description=p_data.get("description", ""),
            application_category=category,
            engineer_label=p_data.get("engineer_label", "BattLab Engineer"),
            design_version=p_data.get("design_version", "1.0"),
            units=p_data.get("units", "SI"),
            is_demo=p_data.get("is_demo", True),
        )
        session.add(project)
        session.flush()

        req_data = p_data.get("requirement")
        if req_data:
            try:
                cooling_pref = CoolingType(req_data.get("cooling_preference", "passive"))
            except ValueError:
                cooling_pref = CoolingType.passive

            req = Requirement(
                project_id=project.id,
                target_voltage_v=float(req_data.get("target_voltage_v", 48.0)),
                target_energy_wh=float(req_data.get("target_energy_wh", 2000.0)),
                energy_is_usable=bool(req_data.get("energy_is_usable", True)),
                continuous_current_a=float(req_data.get("continuous_current_a", 20.0)),
                peak_current_a=float(req_data.get("peak_current_a", 50.0)),
                peak_duration_s=float(req_data.get("peak_duration_s", 10.0)),
                max_mass_kg=float(req_data.get("max_mass_kg", 25.0)) if req_data.get("max_mass_kg") else None,
                min_ambient_temp_c=float(req_data.get("min_ambient_temp_c", -10.0)),
                max_ambient_temp_c=float(req_data.get("max_ambient_temp_c", 45.0)),
                cooling_preference=cooling_pref,
                design_notes=req_data.get("design_notes", ""),
            )
            session.add(req)

        for cfg_data in p_data.get("configurations", []):
            cell_model = cfg_data.get("cell_model")
            cell = session.exec(select(CellSpec).where(CellSpec.model == cell_model)).first()
            if not cell:
                cell = session.exec(select(CellSpec)).first()
            if not cell:
                continue

            try:
                cooling_t = CoolingType(cfg_data.get("cooling_type", "passive"))
            except ValueError:
                cooling_t = CoolingType.passive

            try:
                design_m = DesignMode(cfg_data.get("design_mode", "requirements_first"))
            except ValueError:
                design_m = DesignMode.requirements_first

            ns = int(cfg_data.get("ns", 14))
            np = int(cfg_data.get("np", 16))
            total_cells = ns * np
            v_nom = round(ns * cell.nominal_voltage_v, 2)
            e_nom = round(total_cells * cell.nominal_voltage_v * cell.nominal_capacity_ah, 1)
            cell_mass = round(total_cells * cell.mass_kg, 2) if cell.mass_kg else None
            cell_cost = round(total_cells * cell.unit_cost_usd, 2) if cell.unit_cost_usd else None

            cfg = Configuration(
                project_id=project.id,
                cell_spec_id=cell.id,
                label=cfg_data.get("label", f"Configuration {ns}S{np}P"),
                design_mode=design_m,
                ns=ns,
                np=np,
                cooling_type=cooling_t,
                usable_soc_window=float(cfg_data.get("usable_soc_window", 0.85)),
                notes=cfg_data.get("notes", ""),
                is_baseline=bool(cfg_data.get("is_baseline", False)),
                calc_nominal_voltage_v=v_nom,
                calc_nominal_energy_wh=e_nom,
                calc_total_cells=total_cells,
                calc_cell_mass_kg=cell_mass,
                calc_bom_cost_usd=cell_cost,
            )
            session.add(cfg)
            session.flush()

            if cfg.is_baseline:
                sim_run = SimulationRun(
                    project_id=project.id,
                    configuration_id=cfg.id,
                    run_label=f"Baseline Verification — {cfg.label}",
                    status=SimulationStatus.completed,
                    constraint_pass=12,
                    constraint_fail=0,
                    constraint_warning=0,
                    constraint_unverified=0,
                    result_nominal_voltage_v=v_nom,
                    result_nominal_energy_wh=e_nom,
                    result_usable_energy_wh=round(e_nom * cfg.usable_soc_window, 1),
                    result_max_temp_c=34.8,
                    result_min_soc=round(1.0 - cfg.usable_soc_window, 2),
                    result_soh_capacity_pct=99.8,
                    result_soh_resistance_pct=100.2,
                )
                session.add(sim_run)

    session.flush()
