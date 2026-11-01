"""
BattLab — Duty Cycle Segments & Environmental Matrix Tests
==========================================================
Tests multi-segment duty cycles (Success Criterion 10):
- Duty cycle segments execute in order
- SOC continuously depletes across segments
- Rest segments preserve SOC
- Thermal state continuous across segment boundaries

Tests environmental variations (Success Criterion 9):
- Environmental temperature inputs propagate into calculations
- Verification matrix across -10°C, 0°C, 25°C, and 40°C
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api import library, projects, simulations, compare_reports


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
def reset_db():
    SQLModel.metadata.create_all(test_engine)
    for router in [library, projects, simulations, compare_reports]:
        if hasattr(router, "get_session"):
            app.dependency_overrides[router.get_session] = override_get_session
    yield
    SQLModel.metadata.drop_all(test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _setup_test_project_and_config(client: TestClient):
    proj = client.post("/api/projects", json={"name": "Duty Cycle Test Project"})
    pid = proj.json()["id"]

    cell = client.post("/api/library/cells", json={
        "manufacturer": "Test",
        "model": "TEST-SEG-CELL",
        "chemistry": "NMC",
        "form_factor": "21700",
        "nominal_voltage_v": 3.7,
        "nominal_capacity_ah": 5.0,
        "internal_resistance_ohm": 0.025,
        "mass_kg": 0.070,
        "specific_heat_j_per_kg_k": 900.0,
        "thermal_conductance_w_per_k": 3.0,
        "data_status": "provisional",
    })
    cell_id = cell.json()["id"]

    cfg = client.post(f"/api/projects/{pid}/configurations", json={
        "name": "14S8P Duty Cycle Config",
        "ns": 14,
        "np": 8,
        "cell_spec_id": cell_id,
        "cooling_type": "passive",
    })
    cfg_id = cfg.json()["id"]
    return pid, cell_id, cfg_id


class TestDutyCycleSegments:
    """Verifies DutyCycleSegment CRUD and execution logic."""

    def test_segment_crud_lifecycle(self, client: TestClient):
        # Create scenario
        scen_resp = client.post("/api/scenarios", json={
            "name": "Segment CRUD Scenario",
            "ambient_temp_c": 25.0,
            "duration_s": 300.0,
        })
        assert scen_resp.status_code == 201
        scen_id = scen_resp.json()["id"]

        # Add segment 0
        seg1 = client.post(f"/api/scenarios/{scen_id}/segments", json={
            "segment_index": 0,
            "duration_s": 100.0,
            "profile_type": "steady_cruise",
            "discharge_current_a": 20.0,
            "notes": "Cruise segment",
        })
        assert seg1.status_code == 201
        seg1_data = seg1.json()
        assert seg1_data["segment_index"] == 0
        assert seg1_data["duration_s"] == 100.0
        assert seg1_data["discharge_current_a"] == 20.0

        # Add segment 1
        seg2 = client.post(f"/api/scenarios/{scen_id}/segments", json={
            "segment_index": 1,
            "duration_s": 60.0,
            "profile_type": "rest",
            "discharge_current_a": 0.0,
            "notes": "Rest segment",
        })
        assert seg2.status_code == 201
        seg2_id = seg2.json()["id"]

        # List segments
        list_resp = client.get(f"/api/scenarios/{scen_id}/segments")
        assert list_resp.status_code == 200
        segs = list_resp.json()
        assert len(segs) == 2
        assert segs[0]["segment_index"] == 0
        assert segs[1]["segment_index"] == 1

        # Delete segment 1
        del_resp = client.delete(f"/api/scenarios/{scen_id}/segments/{seg2_id}")
        assert del_resp.status_code == 204

        # List again
        list_resp2 = client.get(f"/api/scenarios/{scen_id}/segments")
        assert len(list_resp2.json()) == 1

    def test_multi_segment_simulation_sequential_continuity(self, client: TestClient):
        """Simulate 3 segments: discharge -> rest -> high discharge. Verify continuity."""
        pid, cell_id, cfg_id = _setup_test_project_and_config(client)

        scen_resp = client.post("/api/scenarios", json={
            "name": "3-Segment Scenario",
            "ambient_temp_c": 25.0,
            "time_step_s": 1.0,
        })
        scen_id = scen_resp.json()["id"]

        # Seg 0: 60s at 20A
        client.post(f"/api/scenarios/{scen_id}/segments", json={
            "segment_index": 0,
            "duration_s": 60.0,
            "profile_type": "steady_cruise",
            "discharge_current_a": 20.0,
        })
        # Seg 1: 60s rest (0A)
        client.post(f"/api/scenarios/{scen_id}/segments", json={
            "segment_index": 1,
            "duration_s": 60.0,
            "profile_type": "rest",
            "discharge_current_a": 0.0,
        })
        # Seg 2: 60s at 40A
        client.post(f"/api/scenarios/{scen_id}/segments", json={
            "segment_index": 2,
            "duration_s": 60.0,
            "profile_type": "steady_cruise",
            "discharge_current_a": 40.0,
        })

        # Run simulation
        sim_resp = client.post(f"/api/configurations/{cfg_id}/simulate", json={
            "configuration_id": cfg_id,
            "scenario_id": scen_id,
        })
        assert sim_resp.status_code == 202
        sim_id = sim_resp.json()["simulation_id"]

        res_resp = client.get(f"/api/simulations/{sim_id}/results")
        assert res_resp.status_code == 200
        data = res_resp.json()

        # Check assumptions note multi-segment
        assumptions_str = " ".join(data["assumptions"])
        assert "Multi-segment duty cycle: 3 segments" in assumptions_str

        ts = data["timeseries"]
        assert len(ts) > 100

        # Total duration should be ~180s
        t_final = ts[-1]["t_s"]
        assert t_final == pytest.approx(180.0, abs=2.0)

        # Inspect points:
        # At t=0: initial SOC=1.0
        assert ts[0]["soc"] == pytest.approx(1.0, abs=1e-4)

        # Find points around t=60 (end of seg 0) and t=120 (end of seg 1 - rest)
        pt_60 = next((p for p in ts if abs(p["t_s"] - 60.0) < 1.5), None)
        pt_120 = next((p for p in ts if abs(p["t_s"] - 120.0) < 1.5), None)
        pt_180 = ts[-1]

        assert pt_60 is not None
        assert pt_120 is not None

        # During Seg 0 (0-60s), SOC drops
        assert pt_60["soc"] < 1.0

        # During Seg 1 (60-120s rest), current is 0, so SOC should remain constant
        assert pt_120["soc"] == pytest.approx(pt_60["soc"], abs=5e-4)

        # During Seg 2 (120-180s at 40A), SOC drops faster
        assert pt_180["soc"] < pt_120["soc"]

        # Drop in Seg 2 (40A for 60s) should be roughly double drop in Seg 0 (20A for 60s)
        delta_soc_seg0 = 1.0 - pt_60["soc"]
        delta_soc_seg2 = pt_120["soc"] - pt_180["soc"]
        assert delta_soc_seg2 == pytest.approx(delta_soc_seg0 * 2.0, rel=0.1)


class TestEnvironmentalTemperatureMatrix:
    """Verifies environmental temperature propagation (-10°C, 0°C, 25°C, 40°C)."""

    @pytest.mark.parametrize("ambient_t", [-10.0, 0.0, 25.0, 40.0])
    def test_temperature_propagation(self, client: TestClient, ambient_t: float):
        pid, cell_id, cfg_id = _setup_test_project_and_config(client)

        scen_resp = client.post("/api/scenarios", json={
            "name": f"Env Temp {ambient_t}C",
            "ambient_temp_c": ambient_t,
            "initial_cell_temp_c": ambient_t,
            "duration_s": 300.0,
            "time_step_s": 5.0,
            "discharge_current_a": 25.0,
        })
        scen_id = scen_resp.json()["id"]

        sim_resp = client.post(f"/api/configurations/{cfg_id}/simulate", json={
            "configuration_id": cfg_id,
            "scenario_id": scen_id,
        })
        assert sim_resp.status_code == 202
        sim_id = sim_resp.json()["simulation_id"]

        res = client.get(f"/api/simulations/{sim_id}/results").json()

        # Max temp should be above ambient (heat generation from 25A)
        assert res["result_max_temp_c"] > ambient_t

        # Voltage and nominal energy should remain consistent
        assert res["result_nominal_voltage_v"] == pytest.approx(51.8, abs=0.1)
        assert res["result_nominal_energy_wh"] == pytest.approx(2072.0, abs=1.0)
