"""BattLab — API Router: Cell & Component Library"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import engine
from app.models import CellSpec, ComponentSpec, Configuration, SimulationRun
from app.schemas import (
    CellSpecCreate, CellSpecRead, CellSpecUpdate,
    ComponentSpecCreate, ComponentSpecRead,
)

router = APIRouter(prefix="/library", tags=["library"])


def get_session():
    with Session(engine) as session:
        yield session


# ── Cells ─────────────────────────────────────────────────────────────────────

@router.get("/cells", response_model=list[CellSpecRead])
def list_cells(session: Session = Depends(get_session)):
    return session.exec(select(CellSpec)).all()


@router.post("/cells", response_model=CellSpecRead, status_code=status.HTTP_201_CREATED)
def create_cell(body: CellSpecCreate, session: Session = Depends(get_session)):
    cell = CellSpec(**body.model_dump())
    session.add(cell)
    session.commit()
    session.refresh(cell)
    return cell


@router.get("/cells/{cell_id}", response_model=CellSpecRead)
def get_cell(cell_id: int, session: Session = Depends(get_session)):
    cell = session.get(CellSpec, cell_id)
    if not cell:
        raise HTTPException(404, "Cell not found")
    return cell


@router.patch("/cells/{cell_id}", response_model=CellSpecRead)
def update_cell(cell_id: int, body: CellSpecUpdate, session: Session = Depends(get_session)):
    cell = session.get(CellSpec, cell_id)
    if not cell:
        raise HTTPException(404, "Cell not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cell, k, v)
    from datetime import datetime
    cell.updated_at = datetime.utcnow()
    session.add(cell)
    session.commit()
    session.refresh(cell)
    return cell


@router.delete("/cells/{cell_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cell(
    cell_id: int,
    replacement_cell_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    cell = session.get(CellSpec, cell_id)
    if not cell:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cell not found")

    total_cells = session.exec(select(CellSpec)).all()
    if len(total_cells) <= 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot delete the last remaining cell in the library."
        )

    # Check for active configurations using this cell
    configs = session.exec(
        select(Configuration).where(Configuration.cell_spec_id == cell_id)
    ).all()

    if configs:
        if replacement_cell_id is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=(
                    f"Cell '{cell.manufacturer} {cell.model}' is actively referenced by {len(configs)} "
                    f"pack configuration(s). Silent reassignment is prohibited. Please select an explicit "
                    f"replacement cell specification to reassign these configurations."
                ),
            )
        if replacement_cell_id == cell_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Replacement cell cannot be the identical cell being deleted.",
            )
        replacement_cell = session.get(CellSpec, replacement_cell_id)
        if not replacement_cell:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Replacement cell ID {replacement_cell_id} not found.",
            )

        # Explicitly migrate configurations to the user-selected replacement
        for cfg in configs:
            cfg.cell_spec_id = replacement_cell.id
            session.add(cfg)

            # Invalidate or annotate simulation runs linked to this configuration
            sims = session.exec(
                select(SimulationRun).where(SimulationRun.configuration_id == cfg.id)
            ).all()
            for sim in sims:
                assumptions: list[str] = []
                if sim.assumptions_json:
                    try:
                        assumptions = json.loads(sim.assumptions_json)
                    except Exception:
                        assumptions = []
                assumptions.append(
                    f"SPECIFICATION CHANGED: Cell specification '{cell.model}' was deleted and replaced by '{replacement_cell.model}'. "
                    f"Simulation telemetry was executed with historical snapshot parameters; re-run required for updated design."
                )
                sim.assumptions_json = json.dumps(assumptions)
                session.add(sim)

    session.delete(cell)
    session.commit()


# ── Components ────────────────────────────────────────────────────────────────

@router.get("/components", response_model=list[ComponentSpecRead])
def list_components(session: Session = Depends(get_session)):
    return session.exec(select(ComponentSpec)).all()


@router.post("/components", response_model=ComponentSpecRead, status_code=status.HTTP_201_CREATED)
def create_component(body: ComponentSpecCreate, session: Session = Depends(get_session)):
    comp = ComponentSpec(**body.model_dump())
    session.add(comp)
    session.commit()
    session.refresh(comp)
    return comp


@router.get("/components/{comp_id}", response_model=ComponentSpecRead)
def get_component(comp_id: int, session: Session = Depends(get_session)):
    comp = session.get(ComponentSpec, comp_id)
    if not comp:
        raise HTTPException(404, "Component not found")
    return comp


@router.delete("/components/{comp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_component(comp_id: int, session: Session = Depends(get_session)):
    comp = session.get(ComponentSpec, comp_id)
    if not comp:
        raise HTTPException(404, "Component not found")
    session.delete(comp)
    session.commit()
