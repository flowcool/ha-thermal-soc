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
| `roof_coupling` | 0.261 °C/h | ✅ calibrated 2026-06-21 (passive nights 14–19 juin) |
| `τ_walls` | **5.2 h** | ✅ calibrated 2026-06-21 (passive nights 14–19 juin) |

**Calibration note (2026-06-21)**: previous runs hit τ lower bound (3h) due to a bug in `residual()` — the rebound formula omitted `roof_coupling` and assumed walls at equilibrium at HVAC-off. Fixed in `calibrate.py`. Rerun on 499 points from passive nights 14–19 juin (T_ext min 14°C, strong passive cooling signal) gives τ=5.2h, roof_q=0.261°C/h.

**`thermal_floor`**: in a heatwave with T_ext min ~22°C, this apartment cannot reach below 23.4°C even with continuous HVAC at setpoint 22°C. Physical limit — walls + top floor won't allow it. Knowing this changes planning.

## Current Status (as of 2026-07-01)

- Calibration complete: τ_walls=5.2h, roof_coupling=0.261°C/h — reliable
- **HA migration complete**: EWA model running natively in HA (no Python script)
  - `packages/projet_thermal_soc.yaml` — stateful EWA + forecast bridge
  - `templates/sensor_thermal_soc.yaml` — SoC sensors + predictive sensors + alarm
  - roof_q proportional to T_ext: `roof_q_eff = roof_q_base × max(0.5, T_ext / 20.0)`
  - boot_init guard: delay 30s + only resets T_walls if at default (15°C)
- **Météo France** remplace met.no comme source T_ext (met.no sous-estimait de 5-7°C)
  - entité: `weather.meteo_france_forecast_for_city_collonges_sous_saleve_rhone_alpes_74_fr_collonges_sous_saleve`
  - `sensor.t_ext_actuelle_meteo_france` — abstraction utilisée par l'EWA
- **Couche prédictive** (2026-06-21) :
  - `automation.thermal_bridge_previsions_meteo_france` — toutes les 30 min, alimente 5 helpers forecast
  - `sensor.thermal_t_walls_sejour_prevu_18h_sans_clim` — T_walls prédit à 18h sans clim (modèle EWA analytique, T_air = T_ext_max − 5°C)
  - `sensor.thermal_temps_avant_seuil_26degc_sans_clim` — dans combien d'heures T_walls dépasse 26°C sans intervention
  - `binary_sensor.thermal_alerte_canicule` — ON si purge bloquée (delta < 6°C) ET T_ext_max_demain ≥ 33°C
- `input_number.thermal_walls_*` retirés de l'exclusion recorder → historique HA disponible
- `monitor_day.sh` abandonné — ESP IR sender unreliable, fan impact negligible
- AC control automation: next step, blocked on ESP reliability

## Couche réconciliation prévision/réel (2026-07-01)

Bug trouvé en production : `forecast_t_ext_max_aujourd_hui` (extrait du forecast horaire Météo France, fenêtre "aujourd'hui 7h-22h") retombait sur un défaut arbitraire (30°C) dès que le forecast n'avait plus d'heures futures dans cette fenêtre — donc chaque soir, écrasant silencieusement la vraie valeur calculée le matin. Aucune erreur visible, juste un chiffre faux qui alimentait la reco de démarrage clim.

Fix en 2 parties :
- `thermal_forecast_bridge` : si aucune heure ne matche la fenêtre, conserve la dernière valeur connue au lieu de reset sur le défaut.
- Nouvelle couche de réconciliation, indépendante du fix ci-dessus : ne plus faire confiance à la seule prévision matinale.
  - `input_number.thermal_t_ext_max_observe_aujourd_hui` — max T_ext réel observé depuis minuit, ratchet mis à jour /10min (dans `maison_thermal_walls_update`), reset à minuit (`thermal_reset_observe_quotidien`)
  - `sensor.thermal_t_ext_max_effectif_aujourd_hui` = `max(forecast, observé)` — remplace la prévision figée dans "Heure démarrage clim recommandée" et "Temps avant seuil"
  - `binary_sensor.thermal_divergence_previsions` — on si T_ext réelle dépasse la prévision matinale de plus de `input_number.thermal_divergence_seuil` (2°C par défaut), fenêtre 9h-16h
  - Notifications (`automations.yaml`, repo HA config privé, pas ici) : alerte précoce sur divergence + alerte unique sur transition vers "maintenant"

Découverte collatérale : il existe déjà une alerte confort générique par pièce (blueprint `pattern_surveillance_th.yaml`, seuil 26°C/30min, cooldown 6h) — indépendante de TSOC, elle s'est bien déclenchée le jour de l'incident. Le vrai manque était côté couche *prédictive* (aucune notification liée à SoC/reco clim), pas côté réactif.

## Entités HA clés (entity_ids réels, auto-générés par HA)

| Entité | Entity ID | Rôle |
|---|---|---|
| T_ext actuelle | `sensor.t_ext_actuelle_meteo_france` | Source EWA (MF) |
| T_walls séjour | `input_number.thermal_walls_sejour` | État EWA |
| SoC séjour | `sensor.thermal_soc_sejour` | SoC actuel |
| Prédit 18h sans clim | `sensor.thermal_t_walls_sejour_prevu_18h_sans_clim` | Décision matin |
| Temps avant 26°C | `sensor.thermal_temps_avant_seuil_26degc_sans_clim` | Urgence |
| Alerte canicule | `binary_sensor.thermal_alerte_canicule` | Signal alarme |
| T_ext min nuit | `input_number.forecast_t_ext_min_tonuit` | Purge possible ? |
| T_ext max demain | `input_number.forecast_t_ext_max_demain` | Charge prévue |
| T_ext max effectif aujourd'hui | `sensor.thermal_t_ext_max_effectif_aujourd_hui` | max(prévu, observé réel) |
| Divergence prévision/réel | `binary_sensor.thermal_divergence_previsions` | Réel > prévu du matin ? |

## Seuil purge (calibré par modèle 2026-06-21)

Delta T_walls − T_ext_min_nuit ≥ **6°C** pour que la purge naturelle soit clairement meilleure que la clim.
En dessous : la clim (thermal floor 23.5°C) refroidit mieux que l'air extérieur.

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
