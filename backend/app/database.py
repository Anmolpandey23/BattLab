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
        _seed_demo_project(session)
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


def _seed_demo_project(session: Session) -> None:
    existing = session.exec(select(Project).where(Project.is_demo == True)).all()
    if existing:
        return

    # Get the illustrative cell
    cell = session.exec(select(CellSpec).where(CellSpec.model == "ILL-21700-5P")).first()
    if not cell:
        return

    project = Project(
        name="Illustrative 48V-Class EV Battery Prototype",
        description=(
            "Demo project: electric scooter-style battery design exercise. "
            "All specifications and results are illustrative only. "
            "Target: ~51.8V nominal, ~4000 Wh nominal energy, ≤25 kg."
        ),
        application_category=ApplicationCategory.ev_scooter,
        engineer_label="BattLab Demo",
        design_version="0.1",
        units="SI",
        is_demo=True,
    )
    session.add(project)
    session.flush()

    req = Requirement(
        project_id=project.id,
        target_voltage_v=51.8,
        target_energy_wh=4000.0,
        energy_is_usable=False,
        continuous_current_a=40.0,
        peak_current_a=80.0,
        peak_duration_s=30.0,
        max_mass_kg=25.0,
        min_ambient_temp_c=-10.0,
        max_ambient_temp_c=40.0,
        cooling_preference=CoolingType.passive,
        design_notes=(
            "Illustrative demo requirements only. "
            "14S8P per module (112 cells), two modules in parallel for 14S16P. "
            "Mass target is aspirational and unverified without cell mass data."
        ),
    )
    session.add(req)

    # Baseline: 14S16P (224 cells)
    baseline = Configuration(
        project_id=project.id,
        cell_spec_id=cell.id,
        label="Baseline — 14S16P Passive",
        design_mode=DesignMode.requirements_first,
        ns=14,
        np=16,
        cooling_type=CoolingType.passive,
        usable_soc_window=0.80,
        notes=(
            "14S16P configuration. Two 14S8P modules in parallel. "
            "Nominal: 14×3.7=51.8V, 16×5=80Ah, 4144Wh nominal. "
            "All values calculated from illustrative provisional cell data."
        ),
        is_baseline=True,
        calc_nominal_voltage_v=51.8,
        calc_nominal_energy_wh=4144.0,
        calc_total_cells=224,
        calc_cell_mass_kg=None,
        calc_bom_cost_usd=None,
    )
    session.add(baseline)

    # Alternative A: 14S16P Fan-Assisted
    alt_a = Configuration(
        project_id=project.id,
        cell_spec_id=cell.id,
        label="Alternative A — 14S16P Fan-Assisted",
        design_mode=DesignMode.manual,
        ns=14,
        np=16,
        cooling_type=CoolingType.fan,
        usable_soc_window=0.80,
        notes=(
            "Same 14S16P topology but with fan-assisted cooling. "
            "Expected lower peak temperatures under the provisional thermal model."
        ),
        is_baseline=False,
        calc_nominal_voltage_v=51.8,
        calc_nominal_energy_wh=4144.0,
        calc_total_cells=224,
    )
    session.add(alt_a)

    # Alternative B: 13S17P (reduced voltage, more energy)
    alt_b = Configuration(
        project_id=project.id,
        cell_spec_id=cell.id,
        label="Alternative B — 13S17P (Reduced Voltage)",
        design_mode=DesignMode.manual,
        ns=13,
        np=17,
        cooling_type=CoolingType.passive,
        usable_soc_window=0.80,
        notes=(
            "13S17P: nominally 48.1V, 85Ah, 4089Wh. "
            "Voltage slightly below target. More parallel cells increases current capability."
        ),
        is_baseline=False,
        calc_nominal_voltage_v=round(13 * 3.7, 2),
        calc_nominal_energy_wh=round(13 * 17 * 3.7 * 5.0, 1),
        calc_total_cells=221,
    )
    session.add(alt_b)

    session.flush()
