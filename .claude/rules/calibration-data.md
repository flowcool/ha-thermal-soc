---
paths:
  - src/calibrate.py
  - src/visualize.py
  - config/*
---

# Calibrated Building: Apartment A

Concrete, 4th/5th floor, Alpine foothills (Collonges-sous-Salève). Calibration: summer 2026.

## Core parameters

| Parameter | Value | Notes |
|---|---|---|
| τ_walls | 5.2 h | Calibrated 2026-06-21, passive nights 14–19 juin, 499 points |
| roof_coupling | 0.261 °C/h | Same calibration run |
| base_heating_rate | +0.22 °C/h | Measured |
| hvac_rate (evening, T_ext 22°C) | −2.5 °C/h | Measured |
| hvac_rate (heatwave, sun SW) | −0.84 °C/h → plateau | Measured |
| hvac_rebound_rate | +0.7 °C/h | Measured |
| solar_gain (NE bedroom, direct) | +0.55 °C/h | Measured |
| thermal_floor (heatwave, HVAC 22°C) | 23.4–23.6 °C | Physical limit — walls + top floor |
| morning_purge_rate (fan, T_ext 21.7°C) | −1.2 °C/h | Measured |
| coupling_bedroom_passive | −0.075 to −0.11 °C/h | Measured |

## Calibration note

Previous runs hit τ lower bound (3h) due to bug in `residual()` — rebound formula omitted `roof_coupling` and assumed walls at equilibrium at HVAC-off. Fixed in `calibrate.py`.
