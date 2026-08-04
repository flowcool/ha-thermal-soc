# Run Calibration

Run EWA calibration or passive monitor on the NAS.

The system `python3` lacks required modules. Use the pipx venv.

## Setup

```bash
PYTHON=/home/flow/.local/pipx/venvs/homeassistant-cli/bin/python3
HASS_TOKEN=$(grep HASS_TOKEN ~/.bashrc | cut -d'"' -f2)
```

Dependencies installed in this venv (2026-06-21): scipy, matplotlib, pyyaml.

## Calibration from HA live

```bash
HASS_TOKEN=$HASS_TOKEN $PYTHON src/calibrate.py --config config/my_collonges.yaml
```

## Calibration from local CSV

```bash
$PYTHON src/calibrate.py --config config/my_collonges.yaml --csv data/passive_collonges.csv
```

## Passive monitor

```bash
HASS_TOKEN=$HASS_TOKEN nohup $PYTHON src/monitor.py --config config/my_collonges.yaml >> /tmp/tsoc_monitor.log 2>&1 &
```

Stop signal: `touch /tmp/tsoc_stop`
