#!/usr/bin/env python3
"""
ELARA — Plate Capacitor Geometry Calculator

Calculates the capacitance of a square air-gap parallel-plate capacitor
for the input RF rejection filter (PLAN.md §3.0).

Physical model:
    C = e₀ · er · A / d

    where:
        A  = (side - 2·pullback)²   effective copper area
        d  = air gap between plates
        er ≈ 1.0 (air dielectric)

Construction: two solder-masked PCBs facing each other with precision
spacers (ceramic or PTFE). Air dielectric gives infinite R_dc, zero ESR,
zero dielectric loss — preserving the LMP7721's femtoampere noise floor.

The 2-stage RC filter uses two of these capacitors with 1 Mohm resistors:

    antenna -- 1Mohm -- node1 -- 1Mohm -- node2 -- LMP7721 IN+
                        |                |
                      C_air1           C_air2
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
EPSILON_R_AIR = 1.0006        # relative permittivity of air

# Copper properties (1 oz = 35 um)
COPPER_RESISTIVITY = 1.68e-8  # ohm·m
COPPER_THICKNESS_M = 35e-6    # 1 oz copper

# ===========================================================================
# Design parameters
# ===========================================================================
R_FILTER = 220.0e3  # filter resistor value (220 kohm)
TARGET_C_PF = 45.0  # target capacitance (pF)

# Available air gap spacer thicknesses (mm)
GAP_THICKNESSES_MM = [0.2, 0.3, 0.5, 0.8, 1.0]

# Cascade correction factor: for 2 identical RC stages, the -3 dB point
# drops to fc_single × sqrt(2^(1/2) - 1) ≈ 0.6436 × fc_single
CASCADE_FACTOR = np.sqrt(np.sqrt(2) - 1)


# ===========================================================================
# Core calculations
# ===========================================================================
def capacitance_pf(side_mm: float, pullback_mm: float,
                   gap_mm: float) -> float:
    """
    Air-gap parallel-plate capacitance in picofarads.

    Args:
        side_mm:       plate edge length (mm)
        pullback_mm:   copper pulled back from each edge (mm)
        gap_mm:        air gap between plates (mm)
    """
    copper_side_m = (side_mm - 2.0 * pullback_mm) * 1e-3
    if copper_side_m <= 0:
        return 0.0
    area = copper_side_m ** 2
    d = gap_mm * 1e-3
    c = EPSILON_0 * EPSILON_R_AIR * area / d
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


def esr_copper(side_mm: float, pullback_mm: float,
               pad_radius_mm: float = 1.0) -> float:
    """
    Spreading resistance of a square copper plate with a centre pad (ohms).

    R ≈ R_sheet / (2*pi) * ln(a / r_pad)

    where a = half-side of copper area, r_pad = radius of solder pad.
    Both plates contribute, so total copper ESR = 2 * R_spread.
    """
    copper_half = (side_mm - 2.0 * pullback_mm) / 2.0
    if copper_half <= 0 or pad_radius_mm <= 0 or pad_radius_mm >= copper_half:
        return 0.0
    r_sheet = COPPER_RESISTIVITY / COPPER_THICKNESS_M  # ohm/square
    r_spread = r_sheet / (2.0 * np.pi) * np.log(copper_half / pad_radius_mm)
    return 2.0 * r_spread  # top + bottom plates


def side_for_target_c(target_pf: float, pullback_mm: float,
                      gap_mm: float) -> float:
    """
    Solve for plate side length (mm) given a target capacitance.

    C = e₀·er·(side - 2·pullback)² / d
    → side = 2·pullback + sqrt(C·d / (e₀·er))
    """
    c_f = target_pf * 1e-12
    d = gap_mm * 1e-3
    copper_side = np.sqrt(c_f * d / (EPSILON_0 * EPSILON_R_AIR))
    return copper_side * 1e3 + 2.0 * pullback_mm


# ===========================================================================
# Output
# ===========================================================================
def print_design_table(pullback_mm: float = 0.5):
    """Print capacitance and filter cutoff for all gap thicknesses."""

    print("=" * 90)
    print("ELARA — Air-Gap Plate Capacitor Geometry Calculator")
    print(f"Target capacitance: {TARGET_C_PF:.1f} pF")
    print(f"Filter resistor: {R_FILTER / 1e6:.0f} Mohm")
    print(f"Copper pullback from edge: {pullback_mm:.1f} mm")
    print(f"Dielectric: air (er = {EPSILON_R_AIR}, tan d = 0, R_dc = infinite)")
    print("=" * 90)

    print(f"\n  {'Gap':>8}  {'Plate side':>12}  {'Copper area':>12}"
          f"  {'C (actual)':>11}  {'fc (1-stage)':>13}  {'fc (2-stage)':>13}"
          f"  {'FM @100MHz':>11}")

    for gap in GAP_THICKNESSES_MM:
        side = side_for_target_c(TARGET_C_PF, pullback_mm, gap)
        c = capacitance_pf(side, pullback_mm, gap)
        fc1 = fc_single_khz(c)
        fc2 = fc_cascade_khz(c)
        fm_atten = attenuation_db(100e6, c, stages=2)
        copper_side = side - 2 * pullback_mm

        print(f"  {gap:>6.1f} mm  {side:>10.1f} mm  {copper_side:>9.1f} mm"
              f"  {c:>9.2f} pF  {fc1:>10.2f} kHz  {fc2:>10.2f} kHz"
              f"  {fm_atten:>9.1f} dB")

    r_cu = esr_copper(
        side_for_target_c(TARGET_C_PF, pullback_mm, 0.2), pullback_mm)
    print(f"\n  Copper spreading resistance: {r_cu * 1e3:.3f} mohm (negligible)")
    print(f"  Dielectric ESR: 0 (air has zero loss tangent)")
    print(f"  DC leakage resistance: >10^16 ohm (air is a perfect insulator)")

    # Key frequencies of interest
    print(f"\n{'=' * 90}")
    print(f"ATTENUATION AT KEY FREQUENCIES (for C = {TARGET_C_PF:.0f} pF, 2 stages)")
    print(f"{'=' * 90}")
    print(f"  {'Frequency':<25}  {'Attenuation':>12}  {'Notes'}")

    key_freqs = [
        (7.83, "1st Schumann resonance"),
        (14.3, "2nd Schumann resonance"),
        (20.8, "3rd Schumann resonance"),
        (1e3, "VLF mid-band"),
        (10e3, "VLF upper band"),
        (22e3, "VLF top (Nyquist @ 48 kSPS)"),
        (1e6, "MF AM broadcast (~15 km away)"),
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
    """Sweep plate sizes for representative gap thickness."""

    print(f"\n{'=' * 90}")
    print("CAPACITANCE SWEEP — plate side length vs. capacitance")
    print(f"Pullback: {pullback_mm:.1f} mm from each edge")
    print(f"{'=' * 90}")

    sides = np.arange(5.0, 40.0, 1.0)

    for gap in [0.2, 0.5, 1.0]:
        print(f"\n  Air gap = {gap:.1f} mm  (er = {EPSILON_R_AIR})")
        print(f"  {'Side':>8}  {'Copper':>8}  {'C':>9}  {'fc(1)':>10}  {'fc(2)':>10}")

        for s in sides:
            c = capacitance_pf(s, pullback_mm, gap)
            if c <= 0:
                continue
            fc1 = fc_single_khz(c)
            fc2 = fc_cascade_khz(c)
            marker = f" <-- closest to {TARGET_C_PF:.0f} pF" if abs(c - TARGET_C_PF) < 0.5 else ""
            print(f"  {s:>6.1f} mm  {s - 2 * pullback_mm:>6.1f} mm"
                  f"  {c:>7.2f} pF  {fc1:>8.2f} kHz  {fc2:>8.2f} kHz{marker}")


def plot_sweep(pullback_mm: float = 0.5):
    """Generate plot of capacitance and fc vs. plate side for various gaps."""
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available — skipping plot")
        return

    BG_COLOR = "#0d1117"
    TEXT_COLOR = "#e6edf3"
    SUBTLE_COLOR = "#7d8590"
    PANEL_COLOR = "#161b22"
    BORDER_COLOR = "#30363d"
    COLORS = {0.2: "#f2cc60", 0.3: "#ff7b72", 0.5: "#7ee787",
              0.8: "#79c0ff", 1.0: "#d2a8ff"}

    sides = np.linspace(3.0, 45.0, 500)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    fig.patch.set_facecolor(BG_COLOR)

    for ax in (ax1, ax2):
        ax.set_facecolor(PANEL_COLOR)
        ax.tick_params(colors=SUBTLE_COLOR)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE_COLOR)
        for spine in ax.spines.values():
            spine.set_color(BORDER_COLOR)

    # --- Top: Capacitance vs. side ---
    for gap in GAP_THICKNESSES_MM:
        c_vals = np.array([capacitance_pf(s, pullback_mm, gap)
                           for s in sides])
        ax1.plot(sides, c_vals, color=COLORS[gap], linewidth=2,
                 label=f"gap = {gap:.1f} mm")

    ax1.axhline(TARGET_C_PF, color=TEXT_COLOR, linewidth=1.5, linestyle="--",
                alpha=0.5, label=f"Target: {TARGET_C_PF:.0f} pF")
    ax1.set_ylabel("Capacitance (pF)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax1.set_title("ELARA — Air-Gap Plate Capacitor: Capacitance & Filter fc vs. Plate Size",
                  fontsize=13, fontweight="bold", color=TEXT_COLOR,
                  fontfamily="monospace", pad=15)
    legend1 = ax1.legend(loc="upper left", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend1.get_frame().set_alpha(0.9)
    ax1.set_ylim(0, 40)

    # --- Bottom: 2-stage cascade fc vs. side ---
    for gap in GAP_THICKNESSES_MM:
        fc_vals = np.array([fc_cascade_khz(capacitance_pf(s, pullback_mm, gap))
                            for s in sides])
        fc_vals = np.clip(fc_vals, 0, 500)
        ax2.plot(sides, fc_vals, color=COLORS[gap], linewidth=2,
                 label=f"gap = {gap:.1f} mm")

    ax2.axhline(22.0, color="#d2a8ff", linewidth=1.5, linestyle="--",
                alpha=0.7, label="22 kHz (VLF top)")
    ax2.axhline(15.9, color=TEXT_COLOR, linewidth=1.5, linestyle=":",
                alpha=0.5, label="15.9 kHz (target fc)")
    ax2.set_ylabel("2-stage cascade fc (kHz)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax2.set_xlabel("Plate side length (mm)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    legend2 = ax2.legend(loc="upper right", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend2.get_frame().set_alpha(0.9)
    ax2.set_ylim(0, 120)
    ax2.set_xlim(3, 45)

    plt.tight_layout()
    out_path = __file__.replace(".py", ".svg")
    fig.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    pullback = 0.5  # mm — copper setback from each plate edge

    print_design_table(pullback)
    print_custom_sweep(pullback)
    plot_sweep(pullback)
