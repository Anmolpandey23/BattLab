"""
BattLab — Cell Deletion & Data Integrity Test Suite
===================================================
Verifies:
1. Prevention of silent reassignment of referenced cell specifications.
2. Explicit replacement migration required when configurations reference a cell.
3. Invalidation/annotation of historical simulations when referenced cell is migrated.
4. Integrity against orphaned records.
5. Guards against deleting the last remaining cell in the library.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
import app.api.projects as _projects_router
import app.api.library as _library_router
import app.api.simulations as _simulations_router
import app.api.compare_reports as _compare_router
from app.models import CellSpec, Project, Configuration, Scenario, SimulationRun, SimulationStatus

TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_session():
    with Session(test_engine) as session:
        yield session


@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides[_projects_router.get_session] = override_get_session
    app.dependency_overrides[_library_router.get_session] = override_get_session
    app.dependency_overrides[_simulations_router.get_session] = override_get_session
    app.dependency_overrides[_compare_router.get_session] = override_get_session

    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_delete_unreferenced_cell_succeeds(client):
    """An unreferenced cell can be deleted cleanly without needing replacement."""
    with Session(test_engine) as session:
        c1 = CellSpec(manufacturer="MakerA", model="CellA", nominal_voltage_v=3.7, nominal_capacity_ah=5.0)
        c2 = CellSpec(manufacturer="MakerB", model="CellB", nominal_voltage_v=3.2, nominal_capacity_ah=3.0)
        session.add(c1)
        session.add(c2)
        session.commit()
        session.refresh(c1)
        session.refresh(c2)
        c2_id = c2.id

    r = client.delete(f"/api/library/cells/{c2_id}")
    assert r.status_code == 204

    # Verify c2 is deleted and c1 remains
    r_list = client.get("/api/library/cells")
    cells = r_list.json()
    assert len(cells) == 1
    assert cells[0]["model"] == "CellA"


def test_delete_referenced_cell_without_replacement_prohibited(client):
    """Silent reassignment is prevented: 409 Conflict if configurations use the cell."""
    with Session(test_engine) as session:
        c1 = CellSpec(manufacturer="MakerA", model="CellA", nominal_voltage_v=3.7, nominal_capacity_ah=5.0)
        c2 = CellSpec(manufacturer="MakerB", model="CellB", nominal_voltage_v=3.2, nominal_capacity_ah=3.0)
        session.add(c1)
        session.add(c2)
        session.commit()
        session.refresh(c1)
        session.refresh(c2)

        proj = Project(name="Pack Alpha")
        session.add(proj)
        session.commit()
        session.refresh(proj)

        cfg = Configuration(project_id=proj.id, cell_spec_id=c1.id, label="14S8P Design", ns=14, np=8)
        session.add(cfg)
        session.commit()

        c1_id = c1.id

    # Attempt delete without replacement query param
    r = client.delete(f"/api/library/cells/{c1_id}")
    assert r.status_code == 409
    data = r.json()
    assert "actively referenced" in data["detail"]
    assert "Silent reassignment is prohibited" in data["detail"]


def test_delete_referenced_cell_with_identical_replacement_fails(client):
    """Attempting to specify the cell being deleted as its own replacement fails with 400."""
    with Session(test_engine) as session:
        c1 = CellSpec(manufacturer="MakerA", model="CellA", nominal_voltage_v=3.7, nominal_capacity_ah=5.0)
        c2 = CellSpec(manufacturer="MakerB", model="CellB", nominal_voltage_v=3.2, nominal_capacity_ah=3.0)
        session.add(c1)
        session.add(c2)
        session.commit()
        session.refresh(c1)

        proj = Project(name="Pack Beta")
        session.add(proj)
        session.commit()
        session.refresh(proj)

        cfg = Configuration(project_id=proj.id, cell_spec_id=c1.id, label="14S8P Design", ns=14, np=8)
        session.add(cfg)
        session.commit()
        c1_id = c1.id

    r = client.delete(f"/api/library/cells/{c1_id}?replacement_cell_id={c1_id}")
    assert r.status_code == 400
    assert "identical" in r.json()["detail"]


def test_delete_referenced_cell_with_valid_replacement_migrates_and_annotates(client):
    """Providing explicit replacement migrates configuration and marks historical simulation runs."""
    with Session(test_engine) as session:
        c1 = CellSpec(manufacturer="MakerA", model="CellA", nominal_voltage_v=3.7, nominal_capacity_ah=5.0)
        c2 = CellSpec(manufacturer="MakerB", model="CellB", nominal_voltage_v=3.2, nominal_capacity_ah=3.0)
        session.add(c1)
        session.add(c2)
        session.commit()
        session.refresh(c1)
        session.refresh(c2)

        proj = Project(name="Pack Gamma")
        session.add(proj)
        session.commit()
        session.refresh(proj)

        cfg = Configuration(project_id=proj.id, cell_spec_id=c1.id, label="14S8P Design", ns=14, np=8)
        session.add(cfg)
        session.commit()
        session.refresh(cfg)

        sc = Scenario(name="Standard Test", ambient_temp_c=25.0)
        session.add(sc)
        session.commit()
        session.refresh(sc)

        # Simulation run executed with c1
        run = SimulationRun(
            project_id=proj.id,
            configuration_id=cfg.id,
            scenario_id=sc.id,
            run_label="Run 1",
            status=SimulationStatus.completed,
            inputs_snapshot_json=json.dumps({"cell": {"model": "CellA", "nominal_voltage_v": 3.7}}),
            assumptions_json=json.dumps(["Initial assumption"]),
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        c1_id = c1.id
        c2_id = c2.id
        cfg_id = cfg.id
        run_id = run.id

    # Delete with explicit replacement
    r = client.delete(f"/api/library/cells/{c1_id}?replacement_cell_id={c2_id}")
    assert r.status_code == 204

    # Verify configuration was explicitly migrated to c2
    with Session(test_engine) as session:
        updated_cfg = session.get(Configuration, cfg_id)
        assert updated_cfg.cell_spec_id == c2_id

        # Verify historical simulation run retains its execution snapshot and has invalidation annotation
        updated_run = session.get(SimulationRun, run_id)
        snapshot = json.loads(updated_run.inputs_snapshot_json)
        assert snapshot["cell"]["model"] == "CellA"  # Exact execution snapshot preserved!

        assumptions = json.loads(updated_run.assumptions_json)
        assert any("SPECIFICATION CHANGED" in a for a in assumptions)
        assert any("CellA" in a and "CellB" in a for a in assumptions)


def test_delete_last_remaining_cell_prohibited(client):
    """Deleting the only remaining cell in the library is prohibited (400)."""
    with Session(test_engine) as session:
        c1 = CellSpec(manufacturer="MakerA", model="CellA", nominal_voltage_v=3.7, nominal_capacity_ah=5.0)
        session.add(c1)
        session.commit()
        session.refresh(c1)
        c1_id = c1.id

    r = client.delete(f"/api/library/cells/{c1_id}")
    assert r.status_code == 400
    assert "last remaining" in r.json()["detail"]

