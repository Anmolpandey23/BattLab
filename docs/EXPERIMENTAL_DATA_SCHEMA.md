# BattLab Experimental Data Schema Specification

This document provides the formal JSON/CSV schema specification for ingesting battery testbench cycler data into BattLab, accompanied by a synthetic reference dataset.

---

## 1. CSV Schema Specification

```csv
t_s,current_a,voltage_v,temp_c,soc
```

### Field Definitions

| Header | Type | Nullable | Canonical Units | Bounds | Remarks |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `t_s` | Float | No | Seconds | $[0, 10^7]$ | Monotonically increasing |
| `current_a` | Float | No | Amperes | $[-2000, 2000]$ | Pack current ($+$ discharge, $-$ charge) |
| `voltage_v` | Float | No | Volts | $[0, 1200]$ | Pack terminal voltage |
| `temp_c` | Float | Yes | Celsius | $[-50, 150]$ | Pack surface temperature |
| `soc` | Float | Yes | Unitless (0-1) | $[0.0, 1.0]$ | Cycler coulomb-counted SOC |

---

## 2. Synthetic Reference Benchmark (CSV)

> [!WARNING]
> The dataset below is **SYNTHETIC BENCHMARK DATA** generated analytically for software pipeline testing.
> It does **NOT** represent physical testbench cycler measurements and will produce the status:
> `PHYSICAL EXPERIMENTAL VALIDATION: BLOCKED — MEASURED DATA REQUIRED`.

```csv
t_s,current_a,voltage_v,temp_c,soc
0.0,40.0,51.800,25.00,1.0000
10.0,40.0,51.520,25.12,0.9972
20.0,40.0,51.480,25.28,0.9944
30.0,40.0,51.450,25.46,0.9917
40.0,40.0,51.420,25.66,0.9889
50.0,40.0,51.390,25.88,0.9861
60.0,40.0,51.360,26.11,0.9833
70.0,40.0,51.330,26.35,0.9806
80.0,40.0,51.300,26.60,0.9778
90.0,40.0,51.270,26.86,0.9750
100.0,40.0,51.240,27.12,0.9722
```

---

## 3. Real Hardware Cycler Ingestion Mapping

Commercial cyclers export proprietary column headers. BattLab automatically normalizes the following headers:

### Arbin Instruments
- `Test_Time(s)` $\to$ `t_s`
- `Current(A)` $\to$ `current_a`
- `Voltage(V)` $\to$ `voltage_v`
- `Aux_Temperature_1(C)` $\to$ `temp_c`

### Maccor Series 4000
- `TestTime` $\to$ `t_s`
- `Amps` $\to$ `current_a`
- `Volts` $\to$ `voltage_v`
- `TC1` $\to$ `temp_c`

### Neware BTS4000
- `Time` $\to$ `t_s`
- `Current(mA)` $\to$ converted to Amperes $\to$ `current_a`
- `Voltage(V)` $\to$ `voltage_v`
- `T1(℃)` $\to$ `temp_c`

