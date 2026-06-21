# ha-thermal-soc

**Thermal State of Charge (TSOC) for Home Assistant**

> A building stores heat like a battery. Why don't we expose its state of charge?

---

## The problem

It's a heatwave. You turn on the AC at noon and it runs for hours. The bedroom still feels hot at midnight.

The issue isn't the AC. It's the walls.

A concrete apartment that's been baking since 6am has walls at 29°C — even if the air reads 23°C. The AC cools the air. The walls keep radiating heat back. You're fighting inertia you can't see.

What's missing from every smart home setup today:

- **How thermally loaded are my walls right now?**
- **Will the AC actually make a dent tonight, or has the building already absorbed too much?**
- **Should I start pre-cooling at 10am before the sun hits the west facade?**

Current thermostats react to air temperature. But comfort is governed by wall temperature — and walls respond on a timescale of hours, not minutes.

---

## The concept: Thermal State of Charge

Borrowed directly from battery management systems:

```
SoC = 0%   → walls cold, comfortable day ahead without HVAC
SoC = 50%  → walls loaded, HVAC needed but manageable
SoC = 100% → walls saturated, HVAC alone won't recover in time
```

This gives you three new virtual sensors:

```yaml
sensor.thermal_soc          # 0–100% — how charged are the walls right now?
sensor.thermal_decay_rate   # °C/h  — how fast does the building cool naturally?
sensor.hours_to_target      # hours — how long until comfort target is reached?
```

And enables automations that were previously impossible:

```yaml
- if: sensor.thermal_soc > 80
  and: weather.forecast_tomorrow > 35°C
  then: start pre-cooling at 06:00
```

---

## Why this matters more than you'd think

The battery analogy runs surprisingly deep:

| Battery concept | Building equivalent |
|---|---|
| State of Charge (%) | Thermal SoC (%) |
| Capacity (Wh) | Thermal capacity (°C × thermal mass) |
| Discharge rate | Thermal decay rate (°C/h overnight) |
| Charging (solar, grid) | Solar gain, internal loads, outdoor heat |
| Discharging (load) | Night flushing, HVAC, ventilation |
| Resting voltage | Indoor equilibrium temperature |

Battery management systems expose SoC as a first-class value. No building management system does this — yet the concept maps perfectly.

---

## How it works

**Layer 1 — No Python required (native HA templates)**

Computable from sensors you already have:

```yaml
sensor.t_indoor_mean_24h:     # 24h indoor average — proxy for wall load
sensor.night_cooling_delta:   # °C drop between 2am and 7am
sensor.thermal_soc:           # empirical combination → 0–100%
```

**Layer 2 — EWA estimator (more accurate)**

An Exponentially Weighted Average tracks estimated wall temperature:

```
T_walls(t) = T_walls(t-1) + (dt / τ) × (T_air(t-1) - T_walls(t-1))
```

Two parameters, calibrated once per building:
- **`τ_walls`** — thermal time constant (hours). How slowly do your walls respond?
- **`roof_coupling`** — constant heat flux from top floor or roof (°C/h). Zero for ground/middle floors.

**Layer 3 — Predictive script**

Solves the inverse problem: *"when do I need to start HVAC to reach comfort by my deadline?"*

---

## Current status

- [x] Concept validated
- [x] EWA calibrator (`src/calibrate.py`)
- [x] Passive monitor (`src/monitor.py`)
- [x] Wall simulation plots (`src/visualize.py`)
- [x] Calibrated on one apartment (concrete, top floor, Alpine foothills)
- [ ] Passive calibration experiment in progress (first clean overnight run)
- [ ] Validated on multiple building types
- [ ] Layer 1 HA template sensors (YAML)
- [ ] HA custom component (HACS)

**This is early-stage research.** We have one calibrated building and a working calibration pipeline. We need more buildings to validate the concept.

---

## Calibrated building: Apartment A

*Concrete construction, 4th/5th floor, Alpine foothills. Summer 2026.*

| Parameter | Value | How measured |
|---|---|---|
| `base_heating_rate` | +0.22 °C/h | Passive drift, windows closed, no HVAC |
| `hvac_rate` (favourable evening) | −2.5 °C/h | HVAC at 22°C setpoint, T_ext ~22°C |
| `hvac_rate` (heatwave, sun on facade) | −0.84 °C/h → plateau | HVAC at 22°C, T_ext 31°C, afternoon sun |
| `solar_gain` (NE bedroom, direct) | +0.55 °C/h | Morning sun, door closed |
| `thermal_floor` (heatwave, HVAC on) | 23.4–23.6 °C | Minimum reachable with HVAC at 22°C, T_ext min 22°C |
| `roof_coupling` | ~0.45 °C/h | EWA calibration (top-floor heat flux) |
| `τ_walls` | TBD | Passive overnight experiment in progress |

The `thermal_floor` finding is key: in a heatwave with T_ext minimum 22°C, this apartment cannot reach below 23.4°C even with continuous HVAC. The walls — and the floor above — won't allow it. Knowing this in advance changes how you plan.

---

## Contribute your building

The best thermal model won't come from physics textbooks. It will come from **observing many real buildings**.

To contribute your building's calibration data:

1. Run `src/monitor.py` for 48h — passive, no HVAC intervention
2. Run `src/calibrate.py` to extract your parameters
3. Open a PR adding your results to `data/buildings/`

Useful metadata (no personal data required):
- Building type: concrete / timber frame / stone / brick
- Construction year
- Floor position (ground / middle / top)
- Orientation of main rooms (N/S/E/W)
- External insulation? (yes/no, approx thickness)
- Climate zone (Köppen: Cfb, Csa, Dfb…)

Each calibration makes the collective model stronger.

---

## Quick start

```bash
git clone https://github.com/flowcool/ha-thermal-soc
cd ha-thermal-soc
pip install -r requirements.txt

cp config/example.yaml config/my_home.yaml
# Edit config/my_home.yaml with your entity IDs

# Run passive monitor (logs to data/passive_log.csv)
HASS_TOKEN=xxx python src/monitor.py --config config/my_home.yaml

# After 24-48h of passive data, calibrate
HASS_TOKEN=xxx python src/calibrate.py --config config/my_home.yaml

# Or calibrate from local CSV
python src/calibrate.py --config config/my_home.yaml --csv data/passive_log.csv
```

---

## Repository structure

```
src/
  monitor.py      # Passive temperature logger — CSV output, no HVAC control
  calibrate.py    # EWA parameter fitting from HA history or CSV
  visualize.py    # Wall charge/discharge simulation plots
config/
  example.yaml    # Configuration template — copy and adapt
data/
  buildings/      # Anonymized calibration results per building (PRs welcome)
```

---

## Requirements

- Python ≥ 3.10
- Home Assistant instance with per-room temperature sensors + outdoor temperature
- `requests`, `numpy`, `scipy`, `matplotlib`, `pyyaml`

---

## License

MIT — use freely, contribute back.
