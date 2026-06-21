"""
ha-thermal-soc — passive temperature monitor
Logs indoor/outdoor temperatures every N seconds to CSV. No HVAC control.

Usage:
  HASS_TOKEN=xxx python src/monitor.py --config config/my_home.yaml
  Stop: Ctrl+C or touch /tmp/tsoc_stop
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_states(hass_url: str, headers: dict) -> dict:
    resp = requests.get(f"{hass_url}/api/states", headers=headers, timeout=15)
    resp.raise_for_status()
    return {s["entity_id"]: s for s in resp.json()}


def extract_temp(states: dict, entity_id: str) -> float | None:
    s = states.get(entity_id)
    if not s:
        return None
    try:
        return float(s["state"])
    except (ValueError, TypeError):
        return None


def extract_outdoor_temp(states: dict, weather_entity: str) -> float | None:
    s = states.get(weather_entity)
    if not s:
        return None
    try:
        return float(s["attributes"].get("temperature"))
    except (ValueError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Passive thermal monitor for HA")
    parser.add_argument("--config", default="config/example.yaml")
    parser.add_argument("--stop-flag", default="/tmp/tsoc_stop",
                        help="Touch this file to stop the monitor gracefully")
    args = parser.parse_args()

    cfg = load_config(args.config)
    hass_url = cfg["hass"]["url"]
    token = os.environ.get("HASS_TOKEN", "")
    if not token:
        print("ERROR: HASS_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    zones = cfg["zones"]
    weather_entity = cfg.get("weather_entity", "weather.home")
    interval = cfg.get("monitor", {}).get("interval_seconds", 300)
    output_csv = Path(cfg.get("monitor", {}).get("output_csv", "data/passive_log.csv"))
    stop_flag = Path(args.stop_flag)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    zone_keys = list(zones.keys())
    fieldnames = ["timestamp", "t_ext"] + zone_keys

    write_header = not output_csv.exists()
    log_file = open(output_csv, "a", newline="")
    writer = csv.DictWriter(log_file, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()

    print(f"=== ha-thermal-soc passive monitor ===")
    print(f"Config  : {args.config}")
    print(f"Output  : {output_csv}")
    print(f"Zones   : {', '.join(z['label'] for z in zones.values())}")
    print(f"Interval: {interval}s")
    print(f"Stop    : touch {stop_flag}")
    print()

    try:
        while True:
            if stop_flag.exists():
                print("Stop flag detected — exiting.")
                break

            try:
                states = get_states(hass_url, headers)
                t_ext = extract_outdoor_temp(states, weather_entity)
                row = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "t_ext": t_ext,
                }
                parts = [f"t_ext={t_ext}"]
                for key, zone in zones.items():
                    val = extract_temp(states, zone["entity_id"])
                    row[key] = val
                    parts.append(f"{zone['label']}={val}")

                writer.writerow(row)
                log_file.flush()
                print(f"[{row['timestamp']}] {' | '.join(parts)}")

            except requests.RequestException as e:
                print(f"[{datetime.now().isoformat(timespec='seconds')}] HA error: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        log_file.close()


if __name__ == "__main__":
    main()
