"""
ha-thermal-soc — EWA calibration
Fits [tau_walls, roof_coupling] from HA history data.

Usage:
  HASS_TOKEN=xxx python src/calibrate.py --config config/my_home.yaml
  HASS_TOKEN=xxx python src/calibrate.py --csv data/passive_log.csv --config config/my_home.yaml

Outputs:
  plots/ewa_fit_<zone>.png
  plots/calibration_results.txt
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests
import yaml
from scipy.optimize import minimize


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_history(hass_url: str, headers: dict, entity_id: str, hours: int) -> list:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    url = (f"{hass_url}/api/history/period/{start.strftime('%Y-%m-%dT%H:%M:%S')}"
           f"?filter_entity_id={entity_id}"
           f"&end_time={end.strftime('%Y-%m-%dT%H:%M:%S')}")
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data or not data[0]:
        return []
    result = []
    for entry in data[0]:
        try:
            val = float(entry["state"])
            ts = datetime.fromisoformat(entry["last_changed"].replace("Z", "+00:00"))
            result.append((ts, val))
        except (ValueError, KeyError):
            pass
    return sorted(result, key=lambda x: x[0])


def load_csv(csv_path: str, zone_key: str) -> list:
    result = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = datetime.fromisoformat(row["timestamp"]).replace(tzinfo=timezone.utc)
                val = float(row[zone_key])
                result.append((ts, val))
            except (ValueError, KeyError):
                pass
    return result


# ── Resampling ────────────────────────────────────────────────────────────────

def resample_to_5min(points: list, hours: int) -> tuple:
    if not points:
        return None, None
    t0 = points[0][0]
    dt_step = 300
    n_steps = int(hours * 3600 / dt_step)
    t_grid = np.arange(n_steps) * dt_step / 3600
    pts_s = np.array([(p[0] - t0).total_seconds() for p in points])
    pts_v = np.array([p[1] for p in points])
    T_grid = np.interp(t_grid * 3600, pts_s, pts_v)
    return t_grid, T_grid


# ── EWA model ─────────────────────────────────────────────────────────────────

def run_ewa(T_air: np.ndarray, t_h: np.ndarray, tau: float,
            roof_q: float, T_murs_init: float | None = None) -> np.ndarray:
    """
    Exponentially Weighted Average wall temperature estimator.

    T_murs(t) = T_murs(t-1) + (dt/tau) * (T_air(t-1) - T_murs(t-1)) + roof_q * dt

    Parameters
    ----------
    T_air       indoor air temperature array (°C, 5-min grid)
    t_h         time array in hours
    tau         wall thermal time constant (hours)
    roof_q      constant heat flux from roof/top floor (°C/h), 0 if not applicable
    T_murs_init initial wall temperature (defaults to mean of first 6h)
    """
    dt_h = t_h[1] - t_h[0] if len(t_h) > 1 else 1 / 12
    if T_murs_init is None:
        T_murs_init = float(np.mean(T_air[:max(1, int(6 / dt_h))]))
    T_murs = np.zeros(len(T_air))
    T_murs[0] = T_murs_init
    for i in range(1, len(T_air)):
        T_murs[i] = T_murs[i - 1] + (dt_h / tau) * (T_air[i - 1] - T_murs[i - 1]) + roof_q * dt_h
    return T_murs


def soc_percent(T_murs: np.ndarray, t_comfort: float, t_walls_max: float) -> np.ndarray:
    """Normalize wall temperature to 0–100% SoC."""
    return np.clip(100 * (T_murs - t_comfort) / (t_walls_max - t_comfort), 0, 100)


# ── Calibration ───────────────────────────────────────────────────────────────

def calibrate(T_air: np.ndarray, t_h: np.ndarray, cfg: dict, zone_label: str) -> tuple:
    obs = cfg["observables"]
    cal = cfg["calibration"]

    hvac_setpoint  = obs["hvac_setpoint"]
    thermal_floor  = obs["thermal_floor"]
    rebound_rate   = obs["rebound_rate"]

    tau_min = cal.get("tau_walls_min", 3)
    tau_max = cal.get("tau_walls_max", 80)
    roof_max = cal.get("roof_coupling_max", 2.0)

    spinup_idx = int(24 / (t_h[1] - t_h[0]))

    def residual(params):
        tau, roof_q = params
        if tau < tau_min or tau > tau_max or roof_q < 0 or roof_q > roof_max:
            return 1e6
        # Observable 1: thermal plateau = hvac_setpoint + roof_q * tau
        plateau_pred = hvac_setpoint + roof_q * tau
        r1 = (plateau_pred - thermal_floor) ** 2
        # Observable 2: rebound rate = (thermal_floor - hvac_setpoint) / tau
        rebound_pred = (thermal_floor - hvac_setpoint) / tau
        r2 = (rebound_pred - rebound_rate) ** 2 * 10
        # Observable 3: data likelihood (post spin-up)
        if len(T_air) > spinup_idx + 10:
            T_murs = run_ewa(T_air, t_h, tau, roof_q)
            r3 = float(np.mean((T_murs[spinup_idx:] - T_air[spinup_idx:]) ** 2)) * 0.1
        else:
            r3 = 0
        return r1 + r2 + r3

    result = minimize(residual, x0=[12.0, 0.1], method="L-BFGS-B",
                      bounds=[(tau_min, tau_max), (0.0, roof_max)],
                      options={"ftol": 1e-9, "maxiter": 500})
    tau, roof_q = result.x

    print(f"\n[{zone_label}]")
    print(f"  tau_walls     = {tau:.1f} h")
    print(f"  roof_coupling = {roof_q:.3f} °C/h")
    print(f"  plateau pred  = {hvac_setpoint + roof_q * tau:.1f}°C  (observed: {thermal_floor}°C)")
    print(f"  rebound pred  = +{(thermal_floor - hvac_setpoint) / tau:.2f}°C/h  (observed: +{rebound_rate}°C/h)")
    if abs(tau - tau_min) < 0.1:
        print(f"  ⚠  tau hit lower bound ({tau_min}h) — passive data window may be too short or contaminated")

    return tau, roof_q


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_fit(t_h, T_air, T_murs, zone_label, tau, roof_q, soc, out_path):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(
        f"EWA calibration — {zone_label}\n"
        f"τ_walls = {tau:.1f}h  |  roof_coupling = {roof_q:.3f} °C/h",
        fontsize=12, fontweight="bold",
    )

    ax = axes[0]
    ax.plot(t_h, T_air, color="#2196F3", linewidth=1.5, label="T_air (measured)")
    ax.plot(t_h, T_murs, color="#F44336", linewidth=2, label="T_walls (EWA estimate)")
    ax.axhline(24.0, color="orange", linestyle="--", linewidth=1, alpha=0.7, label="Discomfort threshold (24°C)")
    ax.set_ylabel("Temperature (°C)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.fill_between(t_h, soc, alpha=0.3, color="#FF5722")
    ax.plot(t_h, soc, color="#FF5722", linewidth=2)
    ax.axhline(50, color="orange", linestyle="--", linewidth=1, alpha=0.6, label="SoC = 50%")
    ax.axhline(80, color="red", linestyle="--", linewidth=1, alpha=0.6, label="SoC = 80% (pre-cool threshold)")
    ax.set_title(f"Thermal SoC (current: {soc[-1]:.0f}%)", fontsize=10)
    ax.set_ylabel("Thermal SoC (%)")
    ax.set_xlabel("Time (hours from start)")
    ax.set_ylim(0, 105)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  plot → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/example.yaml")
    parser.add_argument("--csv", default=None,
                        help="Use a local CSV log instead of fetching from HA")
    parser.add_argument("--out", default="plots", help="Output directory for plots")
    args = parser.parse_args()

    cfg = load_config(args.config)
    token = os.environ.get("HASS_TOKEN", "")
    hass_url = cfg["hass"]["url"]
    hours = cfg.get("history_hours", 48)
    soc_cfg = cfg.get("soc", {})
    t_comfort = soc_cfg.get("t_comfort", 22.0)
    t_walls_max = soc_cfg.get("t_walls_max", 30.0)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.csv is None and not token:
        print("ERROR: set HASS_TOKEN or use --csv.", file=sys.stderr)
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    results = {}

    print(f"=== ha-thermal-soc calibration ===")
    print(f"Config : {args.config}")
    print(f"Window : {hours}h")

    for key, zone in cfg["zones"].items():
        label = zone["label"]
        entity_id = zone["entity_id"]

        if args.csv:
            points = load_csv(args.csv, key)
        else:
            print(f"\nFetching {label} ({entity_id})…")
            points = fetch_history(hass_url, headers, entity_id, hours)

        print(f"  {len(points)} data points")
        if len(points) < 10:
            print(f"  ⚠  insufficient data — skipping")
            continue

        t_h, T_air = resample_to_5min(points, hours)
        tau, roof_q = calibrate(T_air, t_h, cfg, label)
        T_murs = run_ewa(T_air, t_h, tau, roof_q)
        soc = soc_percent(T_murs, t_comfort, t_walls_max)

        out_path = out_dir / f"ewa_fit_{key}.png"
        plot_fit(t_h, T_air, T_murs, label, tau, roof_q, soc, out_path)

        results[label] = {
            "tau_walls_h": round(tau, 1),
            "roof_coupling_dCph": round(roof_q, 3),
            "T_walls_now_C": round(float(T_murs[-1]), 1),
            "soc_pct": round(float(soc[-1]), 0),
        }

    if not results:
        print("\n⚠  No zones calibrated.")
        sys.exit(1)

    # Summary
    print(f"\n{'='*40}")
    print("CALIBRATION RESULTS")
    print(f"{'='*40}")
    out_txt = out_dir / "calibration_results.txt"
    with open(out_txt, "w") as f:
        f.write(f"ha-thermal-soc calibration — {datetime.now():%Y-%m-%d %H:%M}\n\n")
        for zone, r in results.items():
            print(f"\n{zone}")
            f.write(f"[{zone}]\n")
            for k, v in r.items():
                line = f"  {k} = {v}"
                print(line)
                f.write(line + "\n")
            f.write("\n")
    print(f"\n→ {out_txt}")


if __name__ == "__main__":
    main()
