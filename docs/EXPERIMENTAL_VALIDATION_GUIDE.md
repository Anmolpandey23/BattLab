# BattLab Experimental Validation Guide

This document defines the protocols, requirements, statistical formulation, and acceptance gates for validating BattLab electro-thermal simulation predictions against physical testbench cycler data.

---

## 1. Overview & Acceptance Gates

BattLab enforces a strict separation between **Software Correctness** and **Physical Model Validity**:
- **Software Integration Acceptance**: Confirms that solvers, conservation laws, data pipelines, APIs, and UI layers execute without crashes, NaN corruption, memory leaks, or numerical divergence.
- **Physical Model Validation**: Requires direct, empirical alignment between simulation predictions and measured experimental data recorded from physical hardware cyclers (e.g., Arbin, Maccor, BioLogic, Neware) under certified thermal chamber environments.

> [!IMPORTANT]
> A simulation model can NEVER be declared "experimentally validated" using synthetic, self-generated, or literature-assumed benchmark data. If no physical hardware testbench datasets are present, BattLab's official validation status is strictly:
> **`PHYSICAL EXPERIMENTAL VALIDATION: BLOCKED — MEASURED DATA REQUIRED`**.

---

## 2. Ingestion Specifications & Data Formats

BattLab accepts testbench cycler data via CSV files through the API endpoints:
- Ingestion verification: `POST /api/validation/ingest-check`
- Simulation alignment: `POST /api/simulations/{id}/validate-dataset`

### Required Columns & Canonical Aliases

| Canonical Field | Units | Accepted Aliases | Description |
| :--- | :--- | :--- | :--- |
| `t_s` | Seconds | `time`, `time_s`, `timestamp_s`, `t_s`, `t` | Elapsed simulation/test time |
| `current_a` | Amperes | `current_a`, `i_a`, `current`, `pack_current_a`, `i_pack_a` | Terminal pack current ($I > 0$: discharge) |
| `voltage_v` | Volts | `voltage_v`, `v_v`, `voltage`, `pack_voltage_v`, `v_pack_v` | Terminal pack voltage |

### Optional Columns & Canonical Aliases

| Canonical Field | Units | Accepted Aliases | Description |
| :--- | :--- | :--- | :--- |
| `temp_c` | °C | `temp_c`, `temperature_c`, `temp`, `temperature`, `t_c` | Measured cell/pack surface temperature |
| `soc` | 0.0 – 1.0 | `soc`, `state_of_charge` | Measured or cycler-integrated SOC |

### Ingestion Validation Constraints
1. **Monotonicity**: The time series must be strictly monotonically increasing ($\Delta t > 0$).
2. **Value Sanity**: No `NaN`, `null`, `inf`, or empty strings in required numeric fields.
3. **Physical Limits**:
   - Voltage: $0\text{ V} \le V_{\text{pack}} \le 1200\text{ V}$.
   - Current: $|I_{\text{pack}}| \le 2000\text{ A}$.
   - Temperature: $-50\text{°C} \le T \le 150\text{°C}$.
   - State of Charge: $0.0 \le \text{SOC} \le 1.0$.

---

## 3. Temporal Alignment & Resampling

When comparing experimental cycler data to numerical simulation results:
1. **Time Offset Alignment**: The initial experimental timestamp is zero-referenced ($t_0 = 0\text{ s}$).
2. **Linear Interpolation**: Experimental measurements are linearly interpolated onto the exact time-step grid of the simulation model ($t_k$).
3. **Coverage Check**: The testbench dataset must cover at least $90\%$ of the simulation duration.

---

## 4. Statistical Validation Metrics

For simulated signal $\hat{y}_k$ and experimental signal $y_k$ across $N$ synchronized points:

### Mean Absolute Error (MAE)
$$\text{MAE} = \frac{1}{N} \sum_{k=1}^N |\hat{y}_k - y_k|$$

### Root Mean Square Error (RMSE)
$$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{k=1}^N (\hat{y}_k - y_k)^2}$$

### Mean Bias Error (MBE)
$$\text{MBE} = \frac{1}{N} \sum_{k=1}^N (\hat{y}_k - y_k)$$

### Coefficient of Determination ($R^2$)
$$R^2 = 1 - \frac{\sum_{k=1}^N (y_k - \hat{y}_k)^2}{\sum_{k=1}^N (y_k - \bar{y})^2}$$
where $\bar{y} = \frac{1}{N}\sum_{k=1}^N y_k$.

### Delivered Capacity Error
$$\Delta Q_{\%} = \frac{|\hat{Q}_{\text{delivered}} - Q_{\text{meas}}|}{Q_{\text{meas}}} \times 100\%$$

---

## 5. Separation of Calibration and Held-Out Validation

To prevent overfitting and misleading statistical correlations:
- **Calibration Sub-dataset ($70\%$)**: Used exclusively to estimate equivalent circuit parameters ($R_0, R_1, C_1$) and convective heat transfer coefficient ($h$).
- **Held-Out Validation Sub-dataset ($30\%$)**: Evaluated independently under dynamic driving cycles (e.g., WLTP, US06) without modifying fitted parameters.

---

## 6. Physical Validation Acceptance Criteria

| Metric | Target Passing Threshold | Warning Threshold | Failure Threshold |
| :--- | :--- | :--- | :--- |
| **Voltage RMSE** | $\le 15\text{ mV/cell}$ | $15 - 30\text{ mV/cell}$ | $> 30\text{ mV/cell}$ |
| **Voltage Max Error** | $\le 45\text{ mV/cell}$ | $45 - 75\text{ mV/cell}$ | $> 75\text{ mV/cell}$ |
| **Temperature RMSE**| $\le 1.5\text{°C}$ | $1.5 - 2.5\text{°C}$ | $> 2.5\text{°C}$ |
| **Capacity Error** | $\le 1.5\%$ | $1.5 - 3.0\%$ | $> 3.0\%$ |
| **$R^2$ Goodness of Fit** | $\ge 0.98$ | $0.95 - 0.98$ | $< 0.95$ |
| **Data Provenance** | Physical Hardware Cycler | Certified Laboratory | Synthetic / Assumed (BLOCKED) |

