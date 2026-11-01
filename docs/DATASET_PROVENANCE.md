# BattLab — Experimental Battery Dataset Provenance & Cryptographic Manifest

This document records the exact provenance, acquisition methodology, licensing, and cryptographic integrity of public experimental datasets ingested into BattLab for physical model validation.

---

## 1. Primary Benchmark Repository

| Property | Value |
| :--- | :--- |
| **Dataset Source** | NASA Ames Prognostics Center of Excellence (PCoE) Data Repository |
| **Dataset Title** | Battery Data Set (Li-ion 18650 Cycling) |
| **Authors** | Bhaskar Saha and Kai Goebel |
| **Institution** | NASA Ames Research Center, Moffett Field, CA |
| **Year of Publication** | 2007 |
| **Dataset Landing Page** | [NASA PCoE Repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) |
| **Official Archive Download** | `https://phm-datasets.s3.amazonaws.com/NASA/5.+Battery+Data+Set.zip` |
| **License / Terms of Use** | NASA Open Source Agreement / Public Domain Research Data |

---

## 2. Experimental Hardware & Protocol Description

- **Specimen Type:** Commercial cylindrical Gen-2 18650 Lithium-ion cell.
- **Cathode Chemistry:** Standard commercial metal-oxide ($\text{LiCoO}_2$ / NMC baseline).
- **Rated Nominal Capacity:** $2.0 \text{ Ah}$.
- **Voltage Operational Limits:** $4.2 \text{ V}$ (charge cutoff) to $2.7 \text{ V}$ (discharge cutoff; some deep discharges terminate at $2.5\text{–}2.0\text{ V}$).
- **Charging Protocol:** Constant Current (CC) at $1.5 \text{ A}$ until terminal voltage reaches $4.2 \text{ V}$, followed by Constant Voltage (CV) hold until charge current drops below $20 \text{ mA}$.
- **Discharge Protocol:** Constant Current (CC) discharge at $2.0 \text{ A}$ until terminal voltage cutoff.
- **Environmental Boundary:** Ambient temperature controlled at $24^\circ\text{C}$ in a thermal test chamber.
- **Instrumentation:**
  - Automated battery testbench (precision 4-wire voltage Kelvin sense, current shunt).
  - External thermocouple affixed to cell casing exterior to measure casing surface temperature.
  - **Sensor Limitation:** No internal core thermocouple exists inside commercial sealed cylindrical 18650 cells. Internal core temperature is physically inaccessible.

---

## 3. Cryptographic Hashes & File Manifest

All files are stored in `battlab/data/nasa_pcoe/`:

| File Name | File Size (Bytes) | SHA-256 Checksum | Role in Evaluation |
| :--- | :--- | :--- | :--- |
| `B0005.mat` | 15,956,874 | `0eae4585baf3f200c09fe24c5ab884f1889679fc75206ca1aa19da704104f0b0` | Calibration cell & multi-cycle aging benchmark (168 discharge cycles) |
| `B0006.mat` | 16,028,159 | `fa818ab4db5db8ab21e910b6dd6c3e20d3761bb9672089e1a4de8f96074616c5` | Independent physical cell for unseen generalization testing |
| `README.txt` | 2,834 | `2b0614ccfdde3ca9c0466ad3e0c03903a1dbe98aec22dbe7ea410219cde51f90` | NASA PCoE experiment documentation and field guide |

### Canonical CSV Exports

Extracted directly by `app.services.nasa_dataset_adapter`:

| Export File | Rows | SHA-256 Checksum | Partition Type |
| :--- | :--- | :--- | :--- |
| `nasa_b0005_cycle01_calibration.csv` | 197 | `c4ce56c70817ea0dcfcfaee7e62d64024b07f8b9e693158c5a2c1f0169300645` | **Calibration Only** (Fitted $R_0, R_1, C_1$) |
| `nasa_b0005_cycle02_heldout.csv` | 196 | `f994ddf234bf9bf85e9fb8d975e5f354f1659f8151f8933b93ee9393a61ba9eb` | **Held-Out** (Same cell, subsequent cycle) |
| `nasa_b0005_cycle10_heldout.csv` | 190 | `d690a6ea5d63f0340cff8533dc27263309a47a118d3ce9d40cbfe7aeec19fb82` | **Held-Out** (Same cell, aged cycle) |
| `nasa_b0006_cycle01_heldout_cell.csv` | 197 | `7d73981881ef106ceca94892c9f538350aa8fa9449f2b87fcf96d833a6b32df2` | **Held-Out** (Completely unseen physical cell) |
| `nasa_b0005_aging_capacity_trajectory.csv` | 169 | `96a2ca695326779430c6a51205374b3017a5823dd774f20dc00a5d207ecda11a` | Multi-cycle empirical capacity fade benchmark |

---

## 4. Anti-Leakage Protocol

To ensure strict scientific integrity:
1. **Zero Data Leakage:** Optimization routines operated exclusively on `nasa_b0005_cycle01_calibration.csv`.
2. Parameters derived during calibration ($R_0 = 0.09739\ \Omega$, $R_1 = 0.04530\ \Omega$, $C_1 = 1500.0\text{ F}$, $Q_{\text{scale}} = 1.0181$) were frozen and evaluated without modification across the held-out datasets.
3. No training, hyperparameter tuning, or recalibration was performed on `B0005` Cycle 2, `B0005` Cycle 10, or `B0006` Cycle 1.

