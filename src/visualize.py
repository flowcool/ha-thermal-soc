"""
ha-thermal-soc — wall thermal simulation and visualization
Educational plots: charge / discharge curves for concrete walls with insulation.
No calibration data required — uses physical parameters only.

Usage: python src/visualize.py [--out plots/]
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Physical parameters (concrete + external insulation) ──────────────────────
ALPHA   = 7e-7    # m²/s  thermal diffusivity of dense concrete
K_BETON = 1.45    # W/(m·K)
L       = 0.20    # m     wall thickness (20 cm standard)
R_ITE   = 2.5     # m²K/W external insulation resistance (~10 cm EPS)
H_CONV  = 8.0     # W/(m²·K) indoor convection

N  = 20
dx = L / N
dt = 45           # s

Fo     = ALPHA * dt / dx**2
Bi_int = H_CONV * dx / K_BETON
Bi_ext = dx / (K_BETON * R_ITE)
assert Fo < 0.5
assert 2 * Fo * (1 + Bi_int) <= 1.0


def simulate(T_int_arr, T_ext, T_init, dt_h=1.0):
    T = np.full(N, float(T_init))
    record_every = max(1, int(dt_h * 3600 / dt))
    t_list, Ts_int_list, Tc_list = [], [], []
    for step, T_int in enumerate(T_int_arr):
        T_new = T.copy()
        T_new[0]    = T[0] + 2 * Fo * (Bi_int * (T_int - T[0]) + (T[1] - T[0]))
        T_new[1:N-1] = T[1:N-1] + Fo * (T[2:N] - 2 * T[1:N-1] + T[0:N-2])
        T_new[N-1]  = T[N-1] + 2 * Fo * ((T[N-2] - T[N-1]) + Bi_ext * (T_ext - T[N-1]))
        T = T_new
        if step % record_every == 0:
            t_list.append(step * dt / 3600)
            Ts_int_list.append(T[0])
            Tc_list.append(T[N // 2])
    return np.array(t_list), np.array(Ts_int_list), np.array(Tc_list)


def step(T_val, duration_h):
    return np.full(int(duration_h * 3600 / dt), float(T_val))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="plots")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    T_ext_ref = 22.0
    T_init    = 22.0
    DAYS      = 5

    # ── Figure 1: charging curves (no HVAC) ──────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        "Wall thermal charging — concrete 20cm + 10cm insulation\n"
        "No HVAC: walls absorb heat from sustained indoor temperature",
        fontsize=12, fontweight="bold",
    )

    ax = axes[0]
    ax.set_title("Indoor surface temperature vs days of heat")
    colors = ["#2196F3", "#FF9800", "#F44336", "#9C27B0"]
    for T_val, color in zip([25, 28, 30, 32], colors):
        t, Ts, _ = simulate(step(T_val, DAYS * 24), T_ext_ref, T_init, dt_h=0.5)
        ax.plot(t / 24, Ts, color=color, linewidth=2, label=f"T_indoor = {T_val}°C")
    ax.axhline(24.0, color="red",   linestyle="--", linewidth=1.5, alpha=0.7, label="Discomfort (24°C)")
    ax.axhline(22.0, color="green", linestyle="--", linewidth=1.5, alpha=0.7, label="HVAC setpoint (22°C)")
    ax.set_xlabel("Days")
    ax.set_ylabel("Indoor wall surface temperature (°C)")
    ax.set_xlim(0, DAYS)
    ax.set_ylim(20, 34)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)

    ax = axes[1]
    ax.set_title("Effect of top-floor / roof heat flux\n(roof_coupling parameter)")
    arr_base = step(28.0, DAYS * 24)
    t, Ts_base, _ = simulate(arr_base, T_ext_ref, T_init, dt_h=0.5)
    ax.plot(t / 24, Ts_base, color="#2196F3", linewidth=2, label="No roof coupling")
    for q, color, lbl in [(0.3, "#FF9800", "+0.3°C/h"), (0.6, "#F44336", "+0.6°C/h")]:
        T_eff = np.minimum(28.0 + q * t, 31.0)
        t2, Ts2, _ = simulate(T_eff, T_ext_ref, T_init, dt_h=0.5)
        ax.plot(t2 / 24, Ts2, color=color, linewidth=2, label=f"roof_coupling = {lbl}")
    ax.axhline(24.0, color="red", linestyle="--", linewidth=1.5, alpha=0.7, label="Discomfort (24°C)")
    ax.set_xlabel("Days")
    ax.set_ylabel("Indoor wall surface temperature (°C)")
    ax.set_xlim(0, DAYS)
    ax.set_ylim(20, 34)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)

    plt.tight_layout()
    out = out_dir / "charge_curves.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✓ {out}")

    # ── Figure 2: discharging curves (HVAC on) ───────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        "Wall thermal discharge — HVAC active (setpoint 22°C)\n"
        "How long until walls reach comfort temperature?",
        fontsize=12, fontweight="bold",
    )

    ax = axes[0]
    ax.set_title("Discharge time vs initial wall charge")
    for T_charged, color in zip([30, 28, 26, 24], ["#F44336", "#FF9800", "#9C27B0", "#2196F3"]):
        t, Ts, _ = simulate(step(22.0, 24), T_ext_ref, T_charged, dt_h=0.25)
        ax.plot(t, Ts, color=color, linewidth=2, label=f"T_walls start = {T_charged}°C")
        below = np.where(Ts <= 24.0)[0]
        if len(below):
            ax.axvline(t[below[0]], color=color, linestyle=":", alpha=0.5)
    ax.axhline(24.0, color="red",   linestyle="--", linewidth=1.5, alpha=0.8, label="Discomfort threshold (24°C)")
    ax.axhline(22.0, color="green", linestyle="--", linewidth=1.5, alpha=0.8, label="HVAC setpoint (22°C)")
    ax.set_xlabel("Hours of HVAC active")
    ax.set_ylabel("Indoor wall surface temperature (°C)")
    ax.set_xlim(0, 24)
    ax.set_ylim(21, 32)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)

    ax = axes[1]
    ax.set_title("HVAC strategy comparison (walls start at 28°C)")
    T_charged = 28.0
    t, Ts, _ = simulate(step(22.0, 48), T_ext_ref, T_charged, dt_h=0.25)
    ax.plot(t, Ts, color="#2196F3", linewidth=2.5, label="Continuous HVAC")
    step_arr = np.arange(int(48 * 3600 / dt))
    t_mod = (step_arr * dt) % 86400
    arr_night = np.where((t_mod >= 11 * 3600) | (t_mod < 4 * 3600), 22.0, 28.0).astype(float)
    t2, Ts2, _ = simulate(arr_night, T_ext_ref, T_charged, dt_h=0.25)
    ax.plot(t2, Ts2, color="#4CAF50", linewidth=2.5, label="HVAC 11h→4h (pre-cool strategy)")
    arr_8h = np.where((t_mod % 86400) < 8 * 3600, 22.0, 28.0).astype(float)
    t3, Ts3, _ = simulate(arr_8h, T_ext_ref, T_charged, dt_h=0.25)
    ax.plot(t3, Ts3, color="#FF9800", linewidth=2.5, label="HVAC night only (8h/day)")
    ax.axhline(24.0, color="red", linestyle="--", linewidth=1.5, alpha=0.8, label="Discomfort threshold (24°C)")
    ax.set_xlabel("Hours")
    ax.set_ylabel("Indoor wall surface temperature (°C)")
    ax.set_xlim(0, 48)
    ax.set_ylim(21, 30)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)

    plt.tight_layout()
    out = out_dir / "discharge_hvac.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✓ {out}")

    # ── Figure 3: tau reference ───────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title(
        "Thermal time constant τ = L²/α vs wall thickness\n"
        "(time for indoor surface to feel an outdoor temperature change)",
        fontsize=11,
    )
    L_arr = np.linspace(0.05, 0.40, 200)
    tau_arr = L_arr ** 2 / ALPHA / 3600
    ax.plot(L_arr * 100, tau_arr, color="#2196F3", linewidth=2.5)
    ax.fill_between(L_arr * 100, tau_arr, alpha=0.15, color="#2196F3")
    tau_ref = L ** 2 / ALPHA / 3600
    ax.axvline(20, color="#F44336", linestyle="--", linewidth=2, label="L=20cm (standard)")
    ax.axhline(tau_ref, color="#F44336", linestyle=":", linewidth=1.5, label=f"τ={tau_ref:.0f}h for L=20cm")
    ax.axhspan(0,  12, alpha=0.08, color="green",  label="< 12h: reacts within a day")
    ax.axhspan(12, 48, alpha=0.08, color="orange", label="12–48h: multi-day inertia")
    ax.annotate(f"  τ ≈ {tau_ref:.0f}h\n  (20cm concrete)",
                xy=(20, tau_ref), xytext=(25, tau_ref + 5),
                arrowprops=dict(arrowstyle="->", color="#333"), fontsize=10, color="#F44336")
    ax.set_xlabel("Concrete thickness (cm)")
    ax.set_ylabel("Thermal time constant τ (hours)")
    ax.set_xlim(5, 40)
    ax.set_ylim(0, 65)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    plt.tight_layout()
    out = out_dir / "tau_reference.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✓ {out}")


if __name__ == "__main__":
    main()
