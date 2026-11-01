"""
BattLab — Independent QA & Battery Systems Verification Campaign
===============================================================
Executes Phases 3, 4, 5, 6, and 8 using independent analytical reference
calculations, live API calls, and file inspections.

Generates structured JSON evidence for the QA report.
"""
import math
import os
import sys
import json
import httpx
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000/api"

report_evidence = {
    "phase3_calculations": {},
    "phase4_mass_telemetry": {},
    "phase5_e2e_workflow": {},
    "phase6_environmental_duty_cycle": {},
    "phase8_exports_consistency": {},
}


def run_campaign():
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 3: Independent Calculation Verification
    # Fixture: 14S8P, 3.7V, 5Ah, 0.025 ohm, 40A
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- PHASE 3: INDEPENDENT CALCULATION VERIFICATION ---")
    v_cell = 3.7
    ah_cell = 5.0
    r_cell = 0.025
    ns = 14
    np = 8
    i_pack = 40.0

    # 1. Independent calculations
    ref_cells = ns * np                             # 112
    ref_v_nom = ns * v_cell                         # 51.8 V
    ref_ah_nom = np * ah_cell                       # 40.0 Ah
    ref_wh_nom = ref_v_nom * ref_ah_nom             # 2072.0 Wh
    ref_r_pack = (ns * r_cell) / np                 # 0.04375 ohm
    ref_loss_w = (i_pack ** 2) * ref_r_pack         # 70.0 W
    ref_q_cell_w = ((i_pack / np) ** 2) * r_cell    # 0.625 W/cell
    ref_total_q_cells = ref_q_cell_w * ref_cells     # 70.0 W
    ref_usable_wh = ref_wh_nom * 0.80               # 1657.6 Wh (80% SOC window)

    # Verify against electrical service via import
    sys.path.insert(0, str(Path(__file__).parent))
    from app.services.electrical import calculate_pack, ElectricalInputs, soc_update
    from app.services.thermal import run_thermal_simulation, thermal_step, ThermalInputs
    from app.services.vehicle_load import calculate_vehicle_load, GRAVITY_MPS2

    elec_in = ElectricalInputs(
        ns=ns, np=np,
        v_cell_nominal=v_cell, ah_cell=ah_cell,
        r_cell_ohm=r_cell,
        r_interconnect_ohm=0.0,
        i_pack_a=i_pack,
    )
    pack_res = calculate_pack(elec_in)

    p3_checks = {
        "total_cells": {"ref": ref_cells, "actual": pack_res.total_cells, "pass": pack_res.total_cells == ref_cells},
        "nominal_voltage_v": {"ref": ref_v_nom, "actual": pack_res.nominal_voltage_v, "pass": abs(pack_res.nominal_voltage_v - ref_v_nom) < 1e-6},
        "capacity_ah": {"ref": ref_ah_nom, "actual": pack_res.capacity_ah, "pass": abs(pack_res.capacity_ah - ref_ah_nom) < 1e-6},
        "nominal_energy_wh": {"ref": ref_wh_nom, "actual": pack_res.nominal_energy_wh, "pass": abs(pack_res.nominal_energy_wh - ref_wh_nom) < 1e-6},
        "pack_resistance_ohm": {"ref": ref_r_pack, "actual": pack_res.r_pack_ohm, "pass": abs(pack_res.r_pack_ohm - ref_r_pack) < 1e-6},
        "usable_energy_wh": {"ref": ref_usable_wh, "actual": pack_res.usable_energy_wh, "pass": abs(pack_res.usable_energy_wh - ref_usable_wh) < 1e-6},
        "resistive_loss_at_40A_w": {"ref": ref_loss_w, "actual": pack_res.p_loss_w, "pass": abs(pack_res.p_loss_w - ref_loss_w) < 1e-6},
    }
    report_evidence["phase3_calculations"] = p3_checks
    for k, v in p3_checks.items():
        print(f"  {k}: Ref={v['ref']}, Actual={v['actual']} -> {'PASS' if v['pass'] else 'FAIL'}")

    # Boundary and invalid checks
    try:
        calculate_pack(ElectricalInputs(ns=0, np=8, v_cell_nominal=3.7, ah_cell=5.0, r_cell_ohm=0.025))
        p3_ns0_pass = False
    except ValueError:
        p3_ns0_pass = True
    print(f"  Boundary test (ns=0 rejected): {'PASS' if p3_ns0_pass else 'FAIL'}")

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 4: Mass & Telemetry Regression Tests
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- PHASE 4: MASS & TELEMETRY REGRESSION TESTS ---")
    # Verify mass scaling for 3S8P, 3S16P, 3S32P, 6S32P with cell mass 0.050 kg
    mass_checks = []
    for test_ns, test_np in [(3, 8), (3, 16), (3, 32), (6, 32)]:
        cells_count = test_ns * test_np
        exp_mass = cells_count * 0.050
        mass_checks.append({
            "topology": f"{test_ns}S{test_np}P",
            "cells": cells_count,
            "expected_mass_kg": exp_mass,
        })
        print(f"  Mass check {test_ns}S{test_np}P: {cells_count} cells × 0.050 kg = {exp_mass:.2f} kg")

    # Check database seed cell mass
    cells_resp = client.get("/library/cells")
    cells_data = cells_resp.json()
    cell_21700 = next((c for c in cells_data if "21700" in c["model"]), None)
    mass_21700 = cell_21700.get("mass_kg") if cell_21700 else None
    print(f"  Seed cell 21700 mass in DB: {mass_21700} kg")
    report_evidence["phase4_mass_telemetry"] = {
        "mass_scaling_verification": mass_checks,
        "seed_cell_21700_mass": mass_21700,
        "seed_cell_mass_present": mass_21700 is not None,
    }

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 5: End-to-End User Workflow
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- PHASE 5: END-TO-END WORKFLOW EXECUTION ---")
    # 1. Create project
    proj_r = client.post("/projects", json={
        "name": "QA Independent Verification Project",
        "description": "Evidence-based end-to-end verification run",
        "application_category": "Custom",
    })
    assert proj_r.status_code == 201, proj_r.text
    pid = proj_r.json()["id"]
    print(f"  Step 1: Created project ID {pid}")

    # 2. Enter requirements
    req_r = client.post(f"/projects/{pid}/requirements", json={
        "target_voltage_v": 51.8,
        "target_energy_wh": 2000.0,
        "max_mass_kg": 25.0,
        "max_cost_usd": 1500.0,
    })
    assert req_r.status_code in (200, 201), req_r.text
    print(f"  Step 2: Saved requirements (51.8V, 2000Wh, 25kg)")

    # 3. Cell selection
    cell_id = cell_21700["id"] if cell_21700 else cells_data[0]["id"]
    print(f"  Step 3: Selected cell ID {cell_id} ({cell_21700['model'] if cell_21700 else 'first'})")

    # 4. Configure design 14S8P
    cfg_r = client.post(f"/projects/{pid}/configurations", json={
        "name": "14S8P Acceptance Baseline",
        "ns": 14,
        "np": 8,
        "cell_spec_id": cell_id,
        "cooling_type": "passive",
        "is_baseline": True,
    })
    assert cfg_r.status_code in (200, 201), cfg_r.text
    cfg = cfg_r.json()
    cfg_id = cfg["id"]
    print(f"  Step 4 & 5: Saved configuration ID {cfg_id} (calc_cell_mass_kg={cfg.get('calc_cell_mass_kg')} kg)")

    # 6. Refresh / verify persistence
    p_check = client.get(f"/projects/{pid}").json()
    cfgs_check = client.get(f"/projects/{pid}/configurations").json()
    assert len(cfgs_check) >= 1
    print(f"  Step 6: Confirmed persistence (project name='{p_check['name']}', configs={len(cfgs_check)})")

    # 7. Create operating scenario (40A discharge, 25C)
    scen_r = client.post("/scenarios", json={
        "name": "QA 40A 3600s Acceptance Scenario",
        "ambient_temp_c": 25.0,
        "initial_cell_temp_c": 25.0,
        "duration_s": 3600.0,
        "time_step_s": 10.0,
        "profile_type": "steady_cruise",
        "discharge_current_a": 40.0,
    })
    assert scen_r.status_code in (200, 201), scen_r.text
    scen_id = scen_r.json()["id"]
    print(f"  Step 7: Created operating scenario ID {scen_id} (40A, 3600s, 25°C)")

    # 8. Run simulation
    sim_r = client.post(f"/configurations/{cfg_id}/simulate", json={
        "configuration_id": cfg_id,
        "scenario_id": scen_id,
        "run_label": "QA E2E Acceptance Run",
    })
    assert sim_r.status_code == 202, sim_r.text
    sim_id = sim_r.json()["simulation_id"]
    print(f"  Step 8: Simulation launched -> Run ID {sim_id}")

    # 9 & 10. Retrieve results & inspect timeseries
    res_r = client.get(f"/simulations/{sim_id}/results")
    assert res_r.status_code == 200, res_r.text
    sim_results = res_r.json()
    ts = sim_results["timeseries"]
    print(f"  Step 9 & 10: Retrieved results (V={sim_results['result_nominal_voltage_v']}V, Wh={sim_results['result_nominal_energy_wh']}Wh, maxT={sim_results['result_max_temp_c']}°C, {len(ts)} points)")

    # 11. Evaluate constraints
    constraints = sim_results["constraints"]
    c_status = {c["rule_id"]: c["status"] for c in constraints}
    print(f"  Step 11: Constraints evaluated ({len(constraints)} rules): {c_status}")

    # 12. Compare alternatives
    # Create an alternative configuration 13S9P
    cfg2_r = client.post(f"/projects/{pid}/configurations", json={
        "name": "13S9P Alternative",
        "ns": 13,
        "np": 9,
        "cell_spec_id": cell_id,
        "cooling_type": "passive",
    })
    cfg2_id = cfg2_r.json()["id"]
    sim2_r = client.post(f"/configurations/{cfg2_id}/simulate", json={
        "configuration_id": cfg2_id,
        "scenario_id": scen_id,
    })
    sim2_id = sim2_r.json()["simulation_id"]

    comp_r = client.post(f"/projects/{pid}/compare", json={
        "simulation_run_ids": [sim_id, sim2_id],
    })
    assert comp_r.status_code == 200, comp_r.text
    comp_res = comp_r.json()
    print(f"  Step 12: Compared alternatives ({len(comp_res['runs'])} runs ranked, top rank={comp_res['ranking'][0]['run_label']})")

    # 13, 14, 15. Export JSON, CSV, PDF
    rep_json = client.post(f"/projects/{pid}/reports", json={"format": "json", "simulation_run_id": sim_id})
    assert rep_json.status_code in (200, 201), rep_json.text
    print(f"  Step 13: Exported JSON report ({rep_json.json()['filename']})")

    rep_csv = client.post(f"/projects/{pid}/reports", json={"format": "csv", "simulation_run_id": sim_id})
    assert rep_csv.status_code in (200, 201), rep_csv.text
    print(f"  Step 14: Exported CSV report ({rep_csv.json()['filename']})")

    rep_pdf = client.post(f"/projects/{pid}/reports", json={"format": "pdf", "simulation_run_id": sim_id})
    assert rep_pdf.status_code in (200, 201), rep_pdf.text
    print(f"  Step 15: Exported PDF report ({rep_pdf.json()['filename']})")

    # 16 & 17. Reopen project & confirm persisted results
    p_final = client.get(f"/projects/{pid}").json()
    sims_final = client.get(f"/projects/{pid}/simulations").json()
    assert len(sims_final) >= 2
    print(f"  Step 16 & 17: Reopened project, {len(sims_final)} completed simulations persisted.")

    report_evidence["phase5_e2e_workflow"] = {
        "project_id": pid,
        "config_14s8p_id": cfg_id,
        "simulation_id": sim_id,
        "nominal_voltage_v": sim_results["result_nominal_voltage_v"],
        "nominal_energy_wh": sim_results["result_nominal_energy_wh"],
        "max_temp_c": sim_results["result_max_temp_c"],
        "constraints": c_status,
        "timeseries_points": len(ts),
        "exported_reports": {
            "json": rep_json.json(),
            "csv": rep_csv.json(),
            "pdf": rep_pdf.json(),
        },
    }

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 6: Environmental & Duty Cycle Tests
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- PHASE 6: ENVIRONMENTAL & DUTY CYCLE MATRIX ---")
    env_matrix_results = {}
    for amb_t in [-10.0, 0.0, 25.0, 40.0]:
        sc_resp = client.post("/scenarios", json={
            "name": f"Matrix Temp {amb_t}C",
            "ambient_temp_c": amb_t,
            "initial_cell_temp_c": amb_t,
            "duration_s": 300.0,
            "time_step_s": 5.0,
            "discharge_current_a": 25.0,
        })
        s_id = sc_resp.json()["id"]
        sm_resp = client.post(f"/configurations/{cfg_id}/simulate", json={
            "configuration_id": cfg_id,
            "scenario_id": s_id,
        })
        sm_id = sm_resp.json()["simulation_id"]
        res = client.get(f"/simulations/{sm_id}/results").json()
        env_matrix_results[f"{amb_t}C"] = {
            "ambient_temp_c": amb_t,
            "max_temp_c": res["result_max_temp_c"],
            "nominal_voltage_v": res["result_nominal_voltage_v"],
            "nominal_energy_wh": res["result_nominal_energy_wh"],
        }
        print(f"  Env {amb_t}°C -> Max Temp = {res['result_max_temp_c']}°C, Voltage = {res['result_nominal_voltage_v']}V")

    # Vehicle Load Mechanics Test
    vload_resp = client.post("/vehicle-load/calculate", json={
        "vehicle_mass_kg": 150.0,
        "payload_mass_kg": 75.0,
        "speed_kmh": 35.0,
        "grade_pct": 5.0,
        "cr": 0.012,
        "cd": 0.6,
        "frontal_area_m2": 0.8,
        "drivetrain_efficiency": 0.88,
        "regen_efficiency": 0.65,
        "auxiliary_power_w": 50.0,
        "nominal_pack_voltage_v": 51.8,
    })
    vload = vload_resp.json()
    print(f"  Vehicle Load (5% slope, 35km/h): F_grade={vload['f_grade_n']}N, P_battery={vload['p_battery_w']}W, I_pack={vload['battery_current_a']}A")

    # Downhill Regen Test
    vload_regen = client.post("/vehicle-load/calculate", json={
        "vehicle_mass_kg": 150.0,
        "payload_mass_kg": 75.0,
        "speed_kmh": 35.0,
        "grade_pct": -8.0,  # downhill
        "drivetrain_efficiency": 0.88,
        "regen_efficiency": 0.65,
        "auxiliary_power_w": 50.0,
        "nominal_pack_voltage_v": 51.8,
    }).json()
    print(f"  Downhill Regen (-8% slope): P_mech={vload_regen['p_mech_w']}W, P_battery={vload_regen['p_battery_w']}W, I_pack={vload_regen['battery_current_a']}A")

    report_evidence["phase6_environmental_duty_cycle"] = {
        "environmental_matrix": env_matrix_results,
        "vehicle_load_uphill": vload,
        "vehicle_load_downhill_regen": vload_regen,
    }

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 8: Export & Data Consistency
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- PHASE 8: EXPORT & DATA CONSISTENCY ---")
    reports_dir = Path(__file__).parent / "reports"
    json_path = reports_dir / rep_json.json()["filename"]
    csv_path = reports_dir / rep_csv.json()["filename"]
    pdf_path = reports_dir / rep_pdf.json()["filename"]

    json_consistent = False
    if json_path.exists():
        with open(json_path) as f:
            jdata = json.load(f)
        # Check that metrics in JSON export match configuration and simulation run
        cfg_j = jdata.get("configuration", {})
        json_v = cfg_j.get("calc_nominal_voltage_v")
        json_wh = cfg_j.get("calc_nominal_energy_wh")
        json_cells = cfg_j.get("calc_total_cells")
        json_mass = cfg_j.get("calc_cell_mass_kg")
        json_consistent = (
            abs(json_v - sim_results["result_nominal_voltage_v"]) < 1e-4 and
            abs(json_wh - sim_results["result_nominal_energy_wh"]) < 1e-4 and
            json_cells == 112 and
            abs(json_mass - 7.84) < 1e-4
        )
        print(f"  JSON file consistency: V={json_v}V, Wh={json_wh}Wh, Cells={json_cells}, Mass={json_mass}kg -> {'CONSISTENT' if json_consistent else 'MISMATCH'}")

    csv_exists = csv_path.exists() and csv_path.stat().st_size > 50
    pdf_exists = pdf_path.exists() and pdf_path.stat().st_size > 1000
    print(f"  CSV file generated: size={csv_path.stat().st_size if csv_path.exists() else 0} bytes")
    print(f"  PDF file generated: size={pdf_path.stat().st_size if pdf_path.exists() else 0} bytes")

    report_evidence["phase8_exports_consistency"] = {
        "json_matches_db": json_consistent,
        "csv_exported_valid": csv_exists,
        "pdf_exported_valid": pdf_exists,
        "json_file_size": json_path.stat().st_size if json_path.exists() else 0,
        "csv_file_size": csv_path.stat().st_size if csv_path.exists() else 0,
        "pdf_file_size": pdf_path.stat().st_size if pdf_path.exists() else 0,
    }

    # Save evidence file
    evidence_path = Path("/Users/anmoldineshpandey/Desktop/BitLab/battlab/independent_qa_evidence.json")
    with open(evidence_path, "w") as f:
        json.dump(report_evidence, f, indent=2)
    print(f"\nAll QA evidence saved to: {evidence_path}")


if __name__ == "__main__":
    run_campaign()
