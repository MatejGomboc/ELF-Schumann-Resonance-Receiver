#!/usr/bin/env python3
"""
ELARA — PCB Capacitor Geometry Calculator

Calculates the capacitance of a square parallel-plate capacitor formed by
copper pours on the top and bottom of a PCB substrate. Used for the input
RF rejection filter (PLAN.md §3.0).

Physical model:
    C = e₀ · er · A / d

    where:
        A  = (side - 2·pullback)²   effective copper area
        d  = substrate thickness
        er = relative permittivity of the substrate

The copper is pulled back from the board edges to maximise the air-gap
leakage path between plates (minimise surface leakage current).

The 2-stage RC filter uses two of these capacitors with 1 Mohm resistors:

    antenna -- 1Mohm -- node1 -- 1Mohm -- node2 -- LMP7721 IN+
                        |                |
                      C_pcb1           C_pcb2
                        |                |
                       GND              GND

    fc_single = 1 / (2pi · R · C)       per stage
    fc_cascade ≈ fc_single · 0.6436     for 2 identical RC stages (-3 dB)

Author: Matej + Claude, March 2026
"""

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ===========================================================================
# Physical constants
# ===========================================================================
EPSILON_0 = 8.854187817e-12  # vacuum permittivity (F/m)

# ===========================================================================
# Substrate materials
# ===========================================================================
SUBSTRATES = {
    "FR4": {
        "epsilon_r": 4.5,
        "thicknesses_mm": [0.2, 0.4, 0.8, 1.0, 1.6],
        "description": "Standard glass-epoxy (fallback, higher moisture absorption)",
    },
    "Rogers 4350B": {
        "epsilon_r": 3.66,
        "thicknesses_mm": [0.168, 0.254, 0.338, 0.508, 0.762],
        "description": "Hydrocarbon ceramic, low moisture, stable er (~50 ppm/°C)",
    },
    "Alumina (96%)": {
        "epsilon_r": 9.4,
        "thicknesses_mm": [0.25, 0.38, 0.50, 0.635, 1.0],
        "description": "Ceramic substrate, near-zero moisture, extremely stable er",
    },
}

# ===========================================================================
# Design parameters
# ===========================================================================
R_FILTER = 1.0e6  # filter resistor value (1 Mohm)
TARGET_C_PF = 10.0  # target capacitance (pF)

# Cascade correction factor: for 2 identical RC stages, the -3 dB point
# drops to fc_single × sqrt(2^(1/2) - 1) ≈ 0.6436 × fc_single
CASCADE_FACTOR = np.sqrt(np.sqrt(2) - 1)


# ===========================================================================
# Core calculations
# ===========================================================================
def capacitance_pf(side_mm: float, pullback_mm: float,
                   thickness_mm: float, epsilon_r: float) -> float:
    """
    Parallel-plate capacitance in picofarads.

    Args:
        side_mm:       board edge length (mm)
        pullback_mm:   copper pulled back from each edge (mm)
        thickness_mm:  substrate thickness (mm)
        epsilon_r:     relative permittivity
    """
    copper_side_m = (side_mm - 2.0 * pullback_mm) * 1e-3
    if copper_side_m <= 0:
        return 0.0
    area = copper_side_m ** 2
    d = thickness_mm * 1e-3
    c = EPSILON_0 * epsilon_r * area / d
    return c * 1e12  # convert to pF


def fc_single_khz(c_pf: float) -> float:
    """Single-stage RC cutoff frequency in kHz."""
    if c_pf <= 0:
        return float("inf")
    return 1.0 / (2.0 * np.pi * R_FILTER * c_pf * 1e-12) * 1e-3


def fc_cascade_khz(c_pf: float) -> float:
    """2-stage cascaded RC cutoff frequency in kHz (-3 dB point)."""
    return fc_single_khz(c_pf) * CASCADE_FACTOR


def attenuation_db(f_hz: float, c_pf: float, stages: int = 2) -> float:
    """
    Attenuation of cascaded RC low-pass at a given frequency.

    Each stage: H(f) = 1 / (1 + j·2pi·f·R·C)
    |H|² = 1 / (1 + (f/fc)²)
    For N stages: |H_total|² = |H|^(2N)
    """
    if c_pf <= 0:
        return 0.0
    fc = 1.0 / (2.0 * np.pi * R_FILTER * c_pf * 1e-12)
    ratio = f_hz / fc
    return -10.0 * stages * np.log10(1.0 + ratio ** 2)


def side_for_target_c(target_pf: float, pullback_mm: float,
                      thickness_mm: float, epsilon_r: float) -> float:
    """
    Solve for board side length (mm) given a target capacitance.

    C = e₀·er·(side - 2·pullback)² / d
    → side = 2·pullback + sqrt(C·d / (e₀·er))
    """
    c_f = target_pf * 1e-12
    d = thickness_mm * 1e-3
    copper_side = np.sqrt(c_f * d / (EPSILON_0 * epsilon_r))
    return copper_side * 1e3 + 2.0 * pullback_mm


# ===========================================================================
# Output
# ===========================================================================
def print_design_table(pullback_mm: float = 0.5):
    """Print capacitance and filter cutoff for all substrate/thickness combos."""

    print("=" * 95)
    print("ELARA — PCB Capacitor Geometry Calculator")
    print(f"Target capacitance: {TARGET_C_PF:.1f} pF")
    print(f"Filter resistor: {R_FILTER / 1e6:.0f} Mohm")
    print(f"Copper pullback from edge: {pullback_mm:.1f} mm")
    print("=" * 95)

    for name, sub in SUBSTRATES.items():
        print(f"\n{'-' * 95}")
        print(f"  {name}  (er = {sub['epsilon_r']:.2f})")
        print(f"  {sub['description']}")
        print(f"{'-' * 95}")
        print(f"  {'Thickness':>10}  {'Side for 10pF':>14}  {'Copper area':>12}"
              f"  {'C (actual)':>11}  {'fc (1-stage)':>13}  {'fc (2-stage)':>13}"
              f"  {'FM @100MHz':>11}")

        for t in sub["thicknesses_mm"]:
            side = side_for_target_c(TARGET_C_PF, pullback_mm, t, sub["epsilon_r"])
            c = capacitance_pf(side, pullback_mm, t, sub["epsilon_r"])
            fc1 = fc_single_khz(c)
            fc2 = fc_cascade_khz(c)
            fm_atten = attenuation_db(100e6, c, stages=2)
            copper_side = side - 2 * pullback_mm

            print(f"  {t:>8.3f} mm  {side:>12.1f} mm  {copper_side:>9.1f} mm"
                  f"  {c:>9.2f} pF  {fc1:>10.2f} kHz  {fc2:>10.2f} kHz"
                  f"  {fm_atten:>9.1f} dB")

    # Key frequencies of interest
    print(f"\n{'=' * 95}")
    print("ATTENUATION AT KEY FREQUENCIES (for C = 10 pF, 2 stages)")
    print(f"{'=' * 95}")
    print(f"  {'Frequency':<25}  {'Attenuation':>12}  {'Notes'}")

    key_freqs = [
        (7.83, "1st Schumann resonance"),
        (14.3, "2nd Schumann resonance"),
        (20.8, "3rd Schumann resonance"),
        (1e3, "VLF mid-band"),
        (10e3, "VLF upper band"),
        (22e3, "VLF top (Nyquist @ 48 kSPS)"),
        (100e6, "FM broadcast band"),
        (900e6, "GSM 900"),
    ]

    for f, desc in key_freqs:
        atten = attenuation_db(f, TARGET_C_PF, stages=2)
        freq_str = f"{f:.2f} Hz" if f < 1e3 else (
            f"{f / 1e3:.1f} kHz" if f < 1e6 else f"{f / 1e6:.0f} MHz"
        )
        print(f"  {freq_str:<25}  {atten:>10.2f} dB  {desc}")


def print_custom_sweep(pullback_mm: float = 0.5):
    """Sweep board sizes for each substrate at its most common thickness."""

    print(f"\n{'=' * 95}")
    print("CAPACITANCE SWEEP — board side length vs. capacitance")
    print(f"Pullback: {pullback_mm:.1f} mm from each edge")
    print(f"{'=' * 95}")

    sides = np.arange(5.0, 35.0, 1.0)  # 5 mm to 34 mm

    # Pick one representative thickness per substrate
    representative = {
        "FR4": 0.8,
        "Rogers 4350B": 0.508,
        "Alumina (96%)": 0.50,
    }

    for name, sub in SUBSTRATES.items():
        t = representative[name]
        print(f"\n  {name}  (er = {sub['epsilon_r']:.2f}, t = {t:.3f} mm)")
        print(f"  {'Side':>8}  {'Copper':>8}  {'C':>9}  {'fc(1)':>10}  {'fc(2)':>10}")

        for s in sides:
            c = capacitance_pf(s, pullback_mm, t, sub["epsilon_r"])
            if c <= 0:
                continue
            fc1 = fc_single_khz(c)
            fc2 = fc_cascade_khz(c)
            marker = " <-- closest to 10 pF" if abs(c - TARGET_C_PF) < 0.5 else ""
            print(f"  {s:>6.1f} mm  {s - 2 * pullback_mm:>6.1f} mm"
                  f"  {c:>7.2f} pF  {fc1:>8.2f} kHz  {fc2:>8.2f} kHz{marker}")


def plot_sweep(pullback_mm: float = 0.5):
    """Generate plot of capacitance vs. board side for all substrates."""
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available — skipping plot")
        return

    BG_COLOR = "#0d1117"
    TEXT_COLOR = "#e6edf3"
    SUBTLE_COLOR = "#7d8590"
    PANEL_COLOR = "#161b22"
    BORDER_COLOR = "#30363d"
    COLORS = {"FR4": "#ff7b72", "Rogers 4350B": "#7ee787", "Alumina (96%)": "#79c0ff"}

    representative = {
        "FR4": 0.8,
        "Rogers 4350B": 0.508,
        "Alumina (96%)": 0.50,
    }

    sides = np.linspace(3.0, 35.0, 500)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    fig.patch.set_facecolor(BG_COLOR)

    for ax in (ax1, ax2):
        ax.set_facecolor(PANEL_COLOR)
        ax.tick_params(colors=SUBTLE_COLOR)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE_COLOR)
        for spine in ax.spines.values():
            spine.set_color(BORDER_COLOR)

    # --- Top: Capacitance vs. side ---
    for name, sub in SUBSTRATES.items():
        t = representative[name]
        c_vals = np.array([capacitance_pf(s, pullback_mm, t, sub["epsilon_r"])
                           for s in sides])
        ax1.plot(sides, c_vals, color=COLORS[name], linewidth=2,
                 label=f"{name} (er={sub['epsilon_r']:.2f}, t={t:.3f} mm)")

    ax1.axhline(TARGET_C_PF, color="#f2cc60", linewidth=1.5, linestyle="--",
                alpha=0.7, label=f"Target: {TARGET_C_PF:.0f} pF")
    ax1.set_ylabel("Capacitance (pF)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax1.set_title("ELARA — PCB Capacitor: Capacitance vs. Board Size",
                  fontsize=13, fontweight="bold", color=TEXT_COLOR,
                  fontfamily="monospace", pad=15)
    legend1 = ax1.legend(loc="upper left", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend1.get_frame().set_alpha(0.9)
    ax1.set_ylim(0, 40)

    # --- Bottom: 2-stage cascade fc vs. side ---
    for name, sub in SUBSTRATES.items():
        t = representative[name]
        fc_vals = np.array([fc_cascade_khz(
            capacitance_pf(s, pullback_mm, t, sub["epsilon_r"]))
            for s in sides])
        # Clip infinities for plotting
        fc_vals = np.clip(fc_vals, 0, 500)
        ax2.plot(sides, fc_vals, color=COLORS[name], linewidth=2,
                 label=f"{name}")

    ax2.axhline(22.0, color="#d2a8ff", linewidth=1.5, linestyle="--",
                alpha=0.7, label="22 kHz (VLF top)")
    ax2.axhline(15.9, color="#f2cc60", linewidth=1.5, linestyle=":",
                alpha=0.7, label="15.9 kHz (PLAN.md target fc)")
    ax2.set_ylabel("2-stage cascade fc (kHz)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax2.set_xlabel("Board side length (mm)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    legend2 = ax2.legend(loc="upper right", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend2.get_frame().set_alpha(0.9)
    ax2.set_ylim(0, 120)
    ax2.set_xlim(3, 35)

    plt.tight_layout()
    out_path = __file__.replace(".py", ".png")
    fig.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    pullback = 0.5  # mm — copper setback from each board edge

    print_design_table(pullback)
    print_custom_sweep(pullback)
    plot_sweep(pullback)
