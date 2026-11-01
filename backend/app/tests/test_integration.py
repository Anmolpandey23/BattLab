"""
BattLab — Integration tests using TestClient
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import engine as prod_engine

# Override engine with in-memory SQLite for tests
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
    SQLModel.metadata.create_all(test_engine)
    # Seed minimal data
    from app.models import CellSpec, Scenario
    with Session(test_engine) as session:
        cell = CellSpec(
            manufacturer="Test", model="Test-Cell",
            nominal_voltage_v=3.7, nominal_capacity_ah=5.0,
            internal_resistance_ohm=0.025,
            min_voltage_v=2.5, max_voltage_v=4.2,
            is_seed=True,
        )
        session.add(cell)
        sc = Scenario(
            name="Test Scenario",
            is_seed=True,
            ambient_temp_c=25.0,
            initial_cell_temp_c=25.0,
            initial_soc=1.0,
            duration_s=360.0,
            time_step_s=10.0,
            profile_type="steady_cruise",
        )
        session.add(sc)
        session.commit()
    yield
    SQLModel.metadata.drop_all(test_engine)


# Override dependency
from app.api import library, projects, simulations, compare_reports
for router in [library, projects, simulations, compare_reports]:
    if hasattr(router, "get_session"):
        app.dependency_overrides[router.get_session] = override_get_session


client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_project():
    r = client.post("/api/projects", json={
        "name": "Integration Test Project",
        "application_category": "Custom",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Integration Test Project"
    assert data["id"] > 0


def test_list_projects():
    # Create first
    client.post("/api/projects", json={"name": "Listed Project"})
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_cells():
    r = client.get("/api/library/cells")
    assert r.status_code == 200
    cells = r.json()
    assert len(cells) >= 1
    assert cells[0]["nominal_voltage_v"] == 3.7


def test_create_requirement():
    proj_r = client.post("/api/projects", json={"name": "Req Test Project"})
    pid = proj_r.json()["id"]
    r = client.post(f"/api/projects/{pid}/requirements", json={
        "target_voltage_v": 51.8,
        "target_energy_wh": 4000.0,
        "max_mass_kg": 25.0,
    })
    assert r.status_code == 201
    assert r.json()["target_voltage_v"] == 51.8


def test_create_configuration():
    proj_r = client.post("/api/projects", json={"name": "Config Test"})
    pid = proj_r.json()["id"]
    cell_r = client.get("/api/library/cells")
    cell_id = cell_r.json()[0]["id"]
    r = client.post(f"/api/projects/{pid}/configurations", json={
        "label": "Test Config",
        "ns": 14,
        "np": 8,
        "cell_spec_id": cell_id,
        "cooling_type": "passive",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["calc_nominal_voltage_v"] == pytest.approx(51.8, rel=1e-3)
    assert data["calc_total_cells"] == 112


def test_candidate_generation():
    proj_r = client.post("/api/projects", json={"name": "Candidate Test"})
    pid = proj_r.json()["id"]
    cell_r = client.get("/api/library/cells")
    cell_id = cell_r.json()[0]["id"]
    r = client.post(f"/api/projects/{pid}/candidates", json={
        "cell_spec_id": cell_id,
        "target_voltage_v": 51.8,
        "target_energy_wh": 4000.0,
        "max_candidates": 5,
    })
    assert r.status_code == 200
    candidates = r.json()
    assert len(candidates) > 0
    assert candidates[0]["ns"] > 0


def test_run_simulation():
    # Setup
    proj_r = client.post("/api/projects", json={"name": "Sim Test"})
    pid = proj_r.json()["id"]
    cell_id = client.get("/api/library/cells").json()[0]["id"]
    cfg_r = client.post(f"/api/projects/{pid}/configurations", json={
        "label": "Sim Config", "ns": 14, "np": 8,
        "cell_spec_id": cell_id, "cooling_type": "passive",
    })
    cfg_id = cfg_r.json()["id"]
    sc_id = client.get("/api/scenarios").json()[0]["id"]

    r = client.post(f"/api/configurations/{cfg_id}/simulate", json={
        "configuration_id": cfg_id,
        "scenario_id": sc_id,
        "run_label": "Test Run",
    })
    assert r.status_code == 202
    sim_id = r.json()["simulation_id"]

    # Get results
    results_r = client.get(f"/api/simulations/{sim_id}/results")
    assert results_r.status_code == 200
    results = results_r.json()
    assert results["result_nominal_voltage_v"] == pytest.approx(51.8, rel=1e-3)
    assert len(results["constraints"]) > 0
    assert len(results["timeseries"]) > 0


def test_report_generation_and_download(setup_db):
    # Create project and run a simulation
    proj_resp = client.post("/api/projects", json={"name": "Report Test Project"})
    pid = proj_resp.json()["id"]

    cells_resp = client.get("/api/library/cells")
    cid = cells_resp.json()[0]["id"]

    cfg_resp = client.post(
        f"/api/projects/{pid}/configurations",
        json={"label": "Report Test Config", "cell_spec_id": cid, "ns": 14, "np": 16, "cooling_type": "passive"},
    )
    cfg_id = cfg_resp.json()["id"]

    sc_resp = client.get("/api/scenarios")
    sc_id = sc_resp.json()[0]["id"]

    sim_resp = client.post(
        f"/api/configurations/{cfg_id}/simulate",
        json={"configuration_id": cfg_id, "scenario_id": sc_id},
    )
    run_id = sim_resp.json()["simulation_id"]

    # 1. JSON Report
    rep_json = client.post(f"/api/projects/{pid}/reports", json={"format": "json", "simulation_run_id": run_id})
    assert rep_json.status_code == 200
    r_id_json = rep_json.json()["report_id"]
    dl_json = client.get(f"/api/reports/{r_id_json}/download")
    assert dl_json.status_code == 200
    assert dl_json.json()["configuration"]["ns"] == 14

    # 2. CSV Report
    rep_csv = client.post(f"/api/projects/{pid}/reports", json={"format": "csv", "simulation_run_id": run_id})
    assert rep_csv.status_code == 200
    r_id_csv = rep_csv.json()["report_id"]
    dl_csv = client.get(f"/api/reports/{r_id_csv}/download")
    assert dl_csv.status_code == 200
    assert "t_s" in dl_csv.text

    # 3. PDF Report
    rep_pdf = client.post(f"/api/projects/{pid}/reports", json={"format": "pdf", "simulation_run_id": run_id})
    assert rep_pdf.status_code == 200
    r_id_pdf = rep_pdf.json()["report_id"]
    dl_pdf = client.get(f"/api/reports/{r_id_pdf}/download")
    assert dl_pdf.status_code == 200
    assert dl_pdf.content.startswith(b"%PDF")


def test_empty_timeseries_csv_generation():
    from app.services.reports import generate_csv_timeseries
    import os
    file_path = generate_csv_timeseries([], 99999)
    assert os.path.exists(file_path)
    with open(file_path, "r") as f:
        content = f.read()
    assert "t_s" in content
    assert "No time-series data recorded" in content

