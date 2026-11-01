"""
BattLab — Seed Cell Migration Script
=====================================
Updates existing seed cells with provisional mass/thermal/current data
and adds new seed cells that are missing from the database.

Run once:
    cd battlab/backend && python migrate_seed_cells.py

PROVISIONAL DATA — All values are assumed illustrative figures.
Not from any real manufacturer datasheet. Do not use for safety decisions.
"""
import json
import sys
from pathlib import Path

# Ensure the app package is importable
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, select
from app.database import engine, DATA_DIR
from app.models import CellSpec


PROVISIONAL_NOTE = (
    "PROVISIONAL ILLUSTRATIVE DATA — values are assumed typical figures. "
    "Not from any real manufacturer datasheet. Do not use for safety decisions."
)

# Patches to apply to existing seed cells (matched by model name)
CELL_PATCHES: dict[str, dict] = {
    "ILL-21700-5P": {
        "mass_kg": 0.070,
        "specific_heat_j_per_kg_k": 900.0,
        "thermal_conductance_w_per_k": 3.0,
        "max_continuous_discharge_a": 10.0,
        "max_peak_discharge_a": 15.0,
        "max_charge_current_a": 5.0,
        "source_notes": (
            "PROVISIONAL ILLUSTRATIVE DATA — mass, thermal, and current limits are assumed "
            "typical values for a 21700 NMC cell. "
            "Not from any real manufacturer datasheet. Do not use for safety decisions."
        ),
    },
    "ILL-18650-3P": {
        "mass_kg": 0.045,
        "specific_heat_j_per_kg_k": 900.0,
        "thermal_conductance_w_per_k": 2.5,
        "max_continuous_discharge_a": 8.0,
        "max_peak_discharge_a": 12.0,
        "max_charge_current_a": 3.0,
        "source_notes": (
            "PROVISIONAL ILLUSTRATIVE DATA — mass, thermal, and current limits are assumed "
            "typical values for an 18650 NMC cell. "
            "Not from any real manufacturer datasheet."
        ),
    },
    "ILL-LFP-26650-3P": {
        "mass_kg": 0.090,
        "specific_heat_j_per_kg_k": 1050.0,
        "thermal_conductance_w_per_k": 2.0,
        "max_continuous_discharge_a": 6.0,
        "max_peak_discharge_a": 9.0,
        "max_charge_current_a": 3.0,
        "source_notes": (
            "PROVISIONAL ILLUSTRATIVE DATA — mass, thermal, and current limits are assumed "
            "typical values for a 26650 LFP cell. "
            "Not from any real manufacturer datasheet."
        ),
    },
}

# New seed cells to insert if not already present
NEW_CELLS = [
    {
        "manufacturer": "Illustrative Cells (Provisional)",
        "model": "ILL-NCA-18650",
        "chemistry": "NCA",
        "form_factor": "18650",
        "nominal_voltage_v": 3.6,
        "min_voltage_v": 2.75,
        "max_voltage_v": 4.2,
        "nominal_capacity_ah": 3.5,
        "internal_resistance_ohm": 0.022,
        "max_continuous_discharge_a": 10.0,
        "max_peak_discharge_a": 15.0,
        "max_charge_current_a": 3.5,
        "mass_kg": 0.048,
        "specific_heat_j_per_kg_k": 880.0,
        "thermal_conductance_w_per_k": 2.5,
        "min_operating_temp_c": -20.0,
        "max_operating_temp_c": 60.0,
        "unit_cost_usd": None,
        "source_notes": (
            "PROVISIONAL ILLUSTRATIVE DATA — NCA chemistry demo cell. "
            "Values assumed typical for 18650 NCA format. "
            "Not from any real manufacturer datasheet."
        ),
        "data_status": "provisional",
        "is_seed": True,
    },
    {
        "manufacturer": "Illustrative Cells (Provisional)",
        "model": "ILL-LFP-POUCH-50",
        "chemistry": "LFP",
        "form_factor": "pouch",
        "nominal_voltage_v": 3.2,
        "min_voltage_v": 2.5,
        "max_voltage_v": 3.65,
        "nominal_capacity_ah": 50.0,
        "internal_resistance_ohm": 0.008,
        "max_continuous_discharge_a": 100.0,
        "max_peak_discharge_a": 200.0,
        "max_charge_current_a": 50.0,
        "mass_kg": 0.850,
        "specific_heat_j_per_kg_k": 1100.0,
        "thermal_conductance_w_per_k": 5.0,
        "min_operating_temp_c": -20.0,
        "max_operating_temp_c": 55.0,
        "unit_cost_usd": None,
        "source_notes": (
            "PROVISIONAL ILLUSTRATIVE DATA — large-format LFP pouch cell. "
            "Values assumed. Not from any real manufacturer datasheet."
        ),
        "data_status": "provisional",
        "is_seed": True,
    },
]


def run_migration() -> None:
    with Session(engine) as session:
        # 1. Patch existing seed cells
        updated = 0
        for model_name, patches in CELL_PATCHES.items():
            cell = session.exec(
                select(CellSpec).where(CellSpec.model == model_name)
            ).first()
            if cell is None:
                print(f"  [SKIP] Cell not found in DB: {model_name}")
                continue
            for field, value in patches.items():
                setattr(cell, field, value)
            session.add(cell)
            updated += 1
            print(f"  [UPDATE] {model_name} — patched {list(patches.keys())}")

        # 2. Insert new seed cells (skip if model already exists)
        inserted = 0
        for cell_data in NEW_CELLS:
            existing = session.exec(
                select(CellSpec).where(CellSpec.model == cell_data["model"])
            ).first()
            if existing is not None:
                print(f"  [SKIP] New cell already in DB: {cell_data['model']}")
                continue
            session.add(CellSpec(**cell_data))
            inserted += 1
            print(f"  [INSERT] {cell_data['model']}")

        session.commit()
        print(f"\nMigration complete — {updated} cells updated, {inserted} cells inserted.")


if __name__ == "__main__":
    print("Running BattLab seed cell migration...")
    run_migration()

