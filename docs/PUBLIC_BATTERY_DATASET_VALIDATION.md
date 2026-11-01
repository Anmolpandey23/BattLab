# BattLab — Public Battery Dataset Validation Report

## 1. Overview & Evaluation Scope

BattLab's Equivalent Circuit Model (ECM), Lumped Thermal Simulation Engine, and Semi-Empirical Aging Service were benchmarked against genuine measured battery testbench data from the **NASA Ames Prognostics Center of Excellence (PCoE)** repository.

This independent evaluation rigorously verifies:
1. **Electrical Voltage Dynamics:** Terminal voltage tracking under constant-current (CC) discharge.
2. **Held-Out Generalizability:** Prediction accuracy across subsequent cycles and an unseen physical cell without parameter retuning.
3. **Thermal Model Validity:** Surface temperature tracking against casing thermocouple telemetry.
4. **Degradation & Aging:** Long-term capacity fade tracking across 168 repeated discharge cycles.

---

## 2. Experimental Data vs. BattLab Model Formulation

### A. Electrical Model Formulation
BattLab simulates cell terminal voltage $V_{\text{term}}(t)$ using a discrete-time Thevenin 1-RC equivalent circuit network coupled with chemistry-specific open-circuit voltage curves $V_{\text{ocv}}(\text{SOC})$:

$$V_{\text{term}}(t) = V_{\text{ocv}}(\text{SOC}(t)) - I_{\text{cell}}(t) R_0(T) - V_{\text{rc}}(t)$$

$$V_{\text{rc}}(t + \Delta t) = V_{\text{rc}}(t) e^{-\Delta t / \tau} + I_{\text{cell}}(t) R_1 (1 - e^{-\Delta t / \tau}), \quad \tau = R_1 C_1$$

### B. Calibration Parameters (Derived solely from B0005 Cycle 1)
- Ohmic Resistance ($R_0$): $0.09739\ \Omega$
- Polarization Resistance ($R_1$): $0.04530\ \Omega$
- Polarization Capacitance ($C_1$): $1500.0\text{ F}$ ($\tau = 67.95\text{ s}$)
- Effective Capacity Scale: $1.0181 \times Q_{\text{meas}}$

---

## 3. Quantitative Results & Evaluation Summary

| Dataset Partition | Target Signal | Samples | MAE | RMSE | MBE | Max Error | $R^2$ Score | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B0005 Cycle 1** (Calibration) | Terminal Voltage | 197 | **$37.57\text{ mV}$** | **$48.27\text{ mV}$** | $-2.61\text{ mV}$ | $287.3\text{ mV}$ | **$0.9582$** | PASSED |
| **B0005 Cycle 2** (Held-Out) | Terminal Voltage | 196 | **$39.55\text{ mV}$** | **$52.25\text{ mV}$** | $-10.26\text{ mV}$ | $312.3\text{ mV}$ | **$0.9505$** | PASSED |
| **B0005 Cycle 10** (Held-Out) | Terminal Voltage | 190 | **$38.48\text{ mV}$** | **$54.21\text{ mV}$** | $-17.28\text{ mV}$ | $346.3\text{ mV}$ | **$0.9476$** | PASSED |
| **B0006 Cycle 1** (Unseen Physical Cell) | Terminal Voltage | 197 | **$37.56\text{ mV}$** | **$50.29\text{ mV}$** | $+1.69\text{ mV}$ | $358.9\text{ mV}$ | **$0.9505$** | PASSED |
| **B0005 Cycle 1** (Thermal Surface) | Casing Temp | 197 | **$0.77^\circ\text{C}$** | **$0.89^\circ\text{C}$** | $+0.03^\circ\text{C}$ | $2.37^\circ\text{C}$ | **$0.9346$** | PASSED |
| **Internal Core Temperature** | Core Temp | — | — | — | — | — | — | **BLOCKED** |
| **B0005 Cycles 1–168** (Aging Fade) | Discharge Capacity | 168 | **$0.0823\text{ Ah}$** | **$0.0945\text{ Ah}$** | $-0.0259\text{ Ah}$ | $0.1941\text{ Ah}$ | **$0.7524$** | PARTIAL |

---

## 4. Key Findings & Physical Insights

### 1. Robust Generalizability with Zero Retuning
On an entirely unseen physical specimen (cell `B0006`), the model achieved an $R^2$ of **$0.9505$** and an RMSE of **$50.29\text{ mV}$** without altering any calibrated parameters. This confirms that BattLab's 1-RC ECM architecture captures physical polarization and ohmic dynamics across manufacturing unit variations.

### 2. Surface Temperature vs. Core Temperature Blocking
- **Surface Validation:** Modelled casing temperature closely followed thermocouple measurements ($R^2 = 0.9346$, MAE = $0.77^\circ\text{C}$, RMSE = $0.89^\circ\text{C}$).
- **Core Blocking:** In compliance with strict engineering integrity standards, internal core temperature validation is marked **BLOCKED**. Commercial 18650 cells have no internal sensors. Estimating multi-node core temperature without destructive sensor instrumentation is unverified.

### 3. Aging Model Scope & Knee-Point Nonlinearity
Across all 168 cycles, the semi-empirical parabolic diffusional model ($\Delta C \propto \text{EFC}^{0.5}$) captured the general degradation trend ($R^2 = 0.7524$, MAE = $0.0823\text{ Ah}$ or $4.43\%$). However, the NASA cell experienced accelerated fade after cycle 90 (lithium plating / active material isolation). This confirms BattLab's stated limitation: the semi-empirical model is suitable for early-to-mid lifecycle wear, not sudden catastrophic end-of-life knee behavior.

---

## 5. Artifact Figures

High-resolution validation figures are preserved in `battlab/validation_artifacts/figures/`:
1. `fig1_b0005_cycle1_calibration_fit.png`: Terminal voltage and residuals over time.
2. `fig2_b0005_cycle2_heldout_voltage.png`: Held-out Cycle 2 prediction and residuals.
3. `fig3_b0006_independent_cell_heldout.png`: Independent physical cell B0006 held-out evaluation.
4. `fig4_thermal_surface_temp_comparison.png`: Casing surface thermocouple vs. lumped thermal model.
5. `fig5_b0005_168_cycles_capacity_fade_aging.png`: 168-cycle capacity fade trajectory.

