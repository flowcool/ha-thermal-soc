# CLAUDE.md — ha-thermal-soc

## Project

**Thermal State of Charge (TSOC)** — building heat as a battery. `sensor.thermal_soc` (0–100%) in HA for predictive HVAC.
GitHub: `flowcool/ha-thermal-soc` | Local: `/home/flow/claude_project/ha-thermal-soc/`

## Architecture

`src/monitor.py` (CSV logger) | `src/calibrate.py` (EWA fitting) | `src/visualize.py` (1D sim) | `config/example.yaml` (template) | `data/buildings/` (community PRs)

## EWA Model

`T_walls(t) = T_walls(t-1) + (dt/τ) × (T_air(t-1) - T_walls(t-1)) + roof_q × dt` — two params: **τ_walls** (hours) + **roof_coupling** (°C/h).
`SoC = clip((T_walls - T_comfort) / (T_walls_max - T_comfort), 0, 100)`

## Status

- HA migration complete — EWA native in HA templates/packages (no Python runtime)
- Météo France replaces met.no as T_ext source
- Predictive layer deployed (forecast bridge, T_walls prediction, heatwave alert)
- Reconciliation layer deployed (observed vs forecast T_ext_max, divergence alert)
- AC control automation: blocked on ESP IR hardware

## Key Thresholds

- **Purge**: T_walls − T_ext_min_nuit ≥ 6°C for natural ventilation to beat HVAC
- **Thermal floor**: 23.4–23.6°C (physical limit with HVAC 22°C, T_ext_min ~22°C)
- **Heatwave alert**: purge blocked (delta < 6°C) AND T_ext_max_demain ≥ 33°C

## Topology — Apartment A

| Room | Orientation | Solar |
|---|---|---|
| Living / balcony | 236° SW | 12h30–21h (peak 16–17h) |
| Main bedroom | 48° NE | 5h15–12h30 |
| Hugo's bedroom | 336° NNW | Never direct |

Top floor (5th) — constant heat flux from above (roof_coupling).

## Safety

- Never commit credentials — HASS_TOKEN via env var only
- Never hardcode entity IDs — always via config YAML
- `config/my_*.yaml`, `data/*.csv`, `plots/*.png` — all gitignored

## Git

Branch: `feature/<short-name>` | Main: `main` | Style: conventional commits

## Skills & Rules

| Name | Type | Scope |
|---|---|---|
| `/run-calibration` | skill | NAS venv setup + calibrate/monitor commands |
| `calibration-data` | rule | Apartment A measured parameters (loads on `src/calibrate.py`, `config/*`) |
| `shell-pitfalls` | rule | NAS shell traps (`rm -i`, heredocs, nohup) — always loaded |
| `ha-cross-repo` | rule | HA config lives in separate repo — commit workflow — always loaded |
| `ha-cross-repo-warning` | hook | PostToolUse reminder when editing HA config files |
