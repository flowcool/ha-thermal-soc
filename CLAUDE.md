# CLAUDE.md — ha-thermal-soc

## Project Overview

Open-source Python project: **Thermal State of Charge (TSOC)** for buildings.

Core idea: a building stores heat like a battery. This project exposes its state of charge as a Home Assistant virtual sensor (`sensor.thermal_soc`, 0–100%), enabling predictive HVAC decisions instead of reactive thermostat control.

GitHub: https://github.com/flowcool/ha-thermal-soc  
Local path: `/home/flow/ha-thermal-soc/`

## Architecture

```
src/
  monitor.py      # Passive temperature logger — CSV, no HVAC control
  calibrate.py    # EWA parameter fitting (HA history API or local CSV)
  visualize.py    # Wall charge/discharge simulation (1D finite diff)
config/
  example.yaml    # Config template — entity IDs, calibration observables
data/
  buildings/      # Anonymized per-building calibration results (PRs)
```

**No hardcoded values** — everything configurable via YAML. Entity IDs, thresholds, building parameters all live in `config/my_home.yaml` (gitignored).

## The EWA Model

```
T_walls(t) = T_walls(t-1) + (dt / τ) × (T_air(t-1) - T_walls(t-1)) + roof_q × dt
```

Two free parameters per building:
- **`τ_walls`** (hours) — thermal time constant. How slowly walls respond to air temperature changes.
- **`roof_coupling`** (°C/h) — constant heat flux from roof or top floor. Zero for ground/middle floors.

SoC normalization:
```
SoC = clip((T_walls - T_comfort) / (T_walls_max - T_comfort), 0, 100)
```

## Calibrated Building: Apartment A

*Concrete, 4th/5th floor, Alpine foothills. Calibration: summer 2026.*

| Parameter | Value | Status |
|---|---|---|
| `base_heating_rate` | +0.22 °C/h | ✅ measured |
| `hvac_rate` (evening, T_ext 22°C) | −2.5 °C/h | ✅ measured |
| `hvac_rate` (heatwave, sun SW) | −0.84 °C/h → plateau | ✅ measured |
| `hvac_rebound_rate` | +0.7 °C/h | ✅ measured |
| `solar_gain` (NE bedroom, direct) | +0.55 °C/h | ✅ measured |
| `thermal_floor` (heatwave, HVAC 22°C) | 23.4–23.6 °C | ✅ measured |
| `morning_purge_rate` (fan, T_ext 21.7°C) | −1.2 °C/h | ✅ measured |
| `coupling_bedroom_passive` | −0.075 to −0.11 °C/h | ✅ measured |
| `roof_coupling` | ~0.45 °C/h | ⚠️ EWA on contaminated window |
| `τ_walls` | TBD | ⏳ passive overnight experiment in progress |

**Critical note on `roof_coupling` and `τ_walls`**: calibration run on 2026-06-21 04:33 used a 48h window dominated by HVAC-on periods. `τ_walls` hit the optimizer lower bound (3h) — not physically reliable. A clean passive overnight run (no HVAC/fan/open windows) is required to properly identify τ.

**`thermal_floor`**: in a heatwave with T_ext min ~22°C, this apartment cannot reach below 23.4°C even with continuous HVAC at setpoint 22°C. Physical limit — walls + top floor won't allow it. Knowing this changes planning.

## Current Status (as of 2026-06-21)

- Passive overnight experiment running: `monitor_passive.sh` → `/tmp/monitor_passive.log` (on the NAS, separate from this repo)
- Next step after passive data: rerun `calibrate.py` on clean window to get reliable τ_walls
- Optimizer bounds in `calibrate.py`: `tau_walls_min=3` — if result hits this bound, data window is contaminated

## Topology — Apartment A (orientation confirmed by compass)

| Room | Orientation | Solar window |
|---|---|---|
| Living room / balcony | 236° SW | 12h30 → ~21h (peak 16h–17h) |
| Main bedroom | 48° NE | ~5h15 → 12h30 (morning direct sun) |
| Hugo's bedroom | 336° NNW | Never direct sun — structurally coolest |

Top floor (5th) neighbors above → contributes constant heat flux (roof_coupling). Not controllable.

## Safety Rules

- **Never commit credentials** — HASS_TOKEN via env var only, never in YAML or code
- **Never hardcode entity IDs** — always via config YAML
- **`config/my_*.yaml` is gitignored** — only `example.yaml` is tracked
- **`data/*.csv` is gitignored** — raw logs stay local (privacy)
- **`plots/*.png` is gitignored** — generated, not tracked

## Known Shell Pitfalls (NAS environment)

- `rm` and `cp` are aliased to `rm -i` / `cp -i` — interactive prompts break `&&` chains silently. Always use `\rm -f` and `\cp`.
- Python heredocs (`python3 - <<'EOF'`) inside `&&` chains produce empty output. Always save scripts to `.py` files and run them directly.
- `monitor_passive.sh` writes to a file via nohup fd — never `mv` that file while the process runs. Use `cp` to a new path, then replace after stopping the process.

## Git Workflow

```
Branch : feature/<short-name>
Main   : main
Commit : conventional commits (feat/fix/docs/refactor)
```

Contributors add buildings via PR to `data/buildings/`.

## Key Open Questions (research)

1. **Does TSOC predict comfort better than raw temperature?** — validation experiment needed
2. **Is roof_coupling universal for top-floor apartments?** — need more calibrations
3. **Layer 1 (HA templates only, no Python)** — design needed, first deliverable for community
4. **τ_walls for different construction types** — the community contribution is the core value

## Runtime NAS (Collonges / UGreen DXP4800PLUS)

Le `python3` système n'a pas les modules nécessaires. Utiliser le venv pipx :

```bash
PYTHON=/home/flow/.local/pipx/venvs/homeassistant-cli/bin/python3

# Calibration depuis HA live
HASS_TOKEN=$(grep HASS_TOKEN ~/.bashrc | cut -d'"' -f2) \
  $PYTHON src/calibrate.py --config config/my_collonges.yaml

# Calibration depuis CSV local
$PYTHON src/calibrate.py --config config/my_collonges.yaml --csv data/passive_collonges.csv

# Monitor passif
HASS_TOKEN=$(grep HASS_TOKEN ~/.bashrc | cut -d'"' -f2) \
  nohup $PYTHON src/monitor.py --config config/my_collonges.yaml >> /tmp/tsoc_monitor.log 2>&1 &
# Arrêt : touch /tmp/tsoc_stop
```

scipy/matplotlib/pyyaml installés dans ce venv le 2026-06-21.

## Context: why this project exists separately from the HA config repo

This is a standalone open-source Python project, not a HA configuration. The HA config repo (`flowcool/homeassistant-config`) has its own CLAUDE.md with Z2M conventions, Alarmo rules, Fairway project constraints, etc. — none of that applies here.

This project uses HA as a *data source* (API) but is otherwise independent.
