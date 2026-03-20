#!/usr/bin/env python3
"""
ELARA — Plate Capacitor Geometry Calculator

Calculates the capacitance of a square parallel-plate capacitor for the
input RF rejection filter (PLAN.md §3.0). Supports air-gap (preferred)
and PCB-substrate dielectrics.

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
    "Air gap": {
        "epsilon_r": 1.0006,
        "tan_delta": 0.0,
        "rho_volume": 1e16,  # ohm·m (air is essentially a perfect insulator)
        "thicknesses_mm": [0.2, 0.3, 0.5, 0.8, 1.0],
        "description": "Two masked PCBs facing each other with spacers, air dielectric",
    },
    "FR4": {
        "epsilon_r": 4.5,
        "tan_delta": 0.02,
        "rho_volume": 1e7,  # volume resistivity (ohm·m), typ. 10^7 to 10^9
        "thicknesses_mm": [0.2, 0.4, 0.8, 1.0, 1.6],
        "description": "Standard glass-epoxy (fallback, higher moisture absorption)",
    },
    "Rogers 4350B": {
        "epsilon_r": 3.66,
        "tan_delta": 0.0037,
        "rho_volume": 1.2e8,  # ohm·m (datasheet: 1.2e10 ohm·cm)
        "thicknesses_mm": [0.168, 0.254, 0.338, 0.508, 0.762],
        "description": "Hydrocarbon ceramic, low moisture, stable er (~50 ppm/°C)",
    },
    "Alumina (96%)": {
        "epsilon_r": 9.4,
        "tan_delta": 0.0002,
        "rho_volume": 1e12,  # ohm·m (datasheet: 10^14 ohm·cm)
        "thicknesses_mm": [0.25, 0.38, 0.50, 0.635, 1.0],
        "description": "Ceramic substrate, near-zero moisture, extremely stable er",
    },
}

# Copper properties (1 oz = 35 um)
COPPER_RESISTIVITY = 1.68e-8  # ohm·m
COPPER_THICKNESS_M = 35e-6    # 1 oz copper

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


def esr_dielectric(f_hz: float, c_pf: float, tan_delta: float) -> float:
    """
    ESR due to dielectric loss (ohms).

    ESR = tan(delta) / (2*pi*f*C)

    At ELF frequencies this can be enormous — e.g. FR4 (tan_d=0.02)
    at 7.83 Hz with 10 pF gives ~41 Mohm, comparable to the 1 Mohm
    filter resistors. This strongly favours low-loss substrates.
    """
    if f_hz <= 0 or c_pf <= 0:
        return float("inf")
    return tan_delta / (2.0 * np.pi * f_hz * c_pf * 1e-12)


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


def esr_total(f_hz: float, c_pf: float, tan_delta: float,
              side_mm: float, pullback_mm: float) -> float:
    """Total ESR = dielectric + copper (ohms)."""
    return esr_dielectric(f_hz, c_pf, tan_delta) + esr_copper(side_mm, pullback_mm)


def quality_factor(f_hz: float, c_pf: float, tan_delta: float,
                   side_mm: float, pullback_mm: float) -> float:
    """Q = 1 / (2*pi*f*C*ESR) = Xc / ESR."""
    esr = esr_total(f_hz, c_pf, tan_delta, side_mm, pullback_mm)
    if esr <= 0 or f_hz <= 0 or c_pf <= 0:
        return float("inf")
    xc = 1.0 / (2.0 * np.pi * f_hz * c_pf * 1e-12)
    return xc / esr


def dc_resistance(side_mm: float, pullback_mm: float,
                  thickness_mm: float, rho_volume: float) -> float:
    """
    DC leakage resistance through the substrate between plates (ohms).

    R = rho_v * d / A

    This resistance shunts the capacitor — leakage current flows
    through the dielectric between the two copper plates.
    """
    copper_side_m = (side_mm - 2.0 * pullback_mm) * 1e-3
    if copper_side_m <= 0:
        return float("inf")
    area = copper_side_m ** 2
    d = thickness_mm * 1e-3
    return rho_volume * d / area


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
    print("ELARA — Plate Capacitor Geometry Calculator")
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
              f"  {'C (actual)':>11}  {'R_dc':>12}  {'fc (1-stage)':>13}"
              f"  {'fc (2-stage)':>13}  {'FM @100MHz':>11}")

        for t in sub["thicknesses_mm"]:
            side = side_for_target_c(TARGET_C_PF, pullback_mm, t, sub["epsilon_r"])
            c = capacitance_pf(side, pullback_mm, t, sub["epsilon_r"])
            r_dc = dc_resistance(side, pullback_mm, t, sub["rho_volume"])
            fc1 = fc_single_khz(c)
            fc2 = fc_cascade_khz(c)
            fm_atten = attenuation_db(100e6, c, stages=2)
            copper_side = side - 2 * pullback_mm

            if r_dc > 1e12:
                r_dc_str = f"{r_dc / 1e12:.1f} Tohm"
            elif r_dc > 1e9:
                r_dc_str = f"{r_dc / 1e9:.1f} Gohm"
            elif r_dc > 1e6:
                r_dc_str = f"{r_dc / 1e6:.1f} Mohm"
            else:
                r_dc_str = f"{r_dc / 1e3:.1f} kohm"

            print(f"  {t:>8.3f} mm  {side:>12.1f} mm  {copper_side:>9.1f} mm"
                  f"  {c:>9.2f} pF  {r_dc_str:>10}  {fc1:>10.2f} kHz"
                  f"  {fc2:>10.2f} kHz  {fm_atten:>9.1f} dB")

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

    # ESR analysis — dielectric loss dominates at ELF
    print(f"\n{'=' * 95}")
    print("ESR ANALYSIS — dielectric loss vs. frequency (C = 10 pF)")
    print(f"{'=' * 95}")

    # Use representative board sizes for ESR calculation
    side_air = side_for_target_c(TARGET_C_PF, pullback_mm, 0.2, 1.0006)
    side_fr4 = side_for_target_c(TARGET_C_PF, pullback_mm, 0.8, 4.5)
    side_rog = side_for_target_c(TARGET_C_PF, pullback_mm, 0.508, 3.66)
    side_alu = side_for_target_c(TARGET_C_PF, pullback_mm, 0.50, 9.4)

    esr_configs = [
        ("Air gap", 0.0, side_air),
        ("FR4", 0.02, side_fr4),
        ("Rogers 4350B", 0.0037, side_rog),
        ("Alumina (96%)", 0.0002, side_alu),
    ]

    # Copper ESR (frequency-independent)
    print(f"\n  Copper spreading resistance (1 oz, 1 mm pad radius):")
    for name, _, side in esr_configs:
        r_cu = esr_copper(side, pullback_mm)
        print(f"    {name:<20}  {r_cu * 1e3:.3f} mohm  (negligible)")

    print(f"\n  {'Frequency':<18}", end="")
    for name, _, _ in esr_configs:
        print(f"  {name:>20}", end="")
    print(f"  {'R_filter':>12}")

    esr_freqs = [
        (7.83, "SR1"),
        (14.3, "SR2"),
        (100.0, "100 Hz"),
        (1e3, "1 kHz"),
        (10e3, "10 kHz"),
        (22e3, "22 kHz"),
    ]

    for f, label in esr_freqs:
        freq_str = f"{f:.2f} Hz" if f < 1e3 else f"{f / 1e3:.0f} kHz"
        print(f"  {freq_str:<18}", end="")
        for name, tan_d, side in esr_configs:
            esr = esr_dielectric(f, TARGET_C_PF, tan_d)
            if esr > 1e6:
                print(f"  {esr / 1e6:>17.1f} Mohm", end="")
            elif esr > 1e3:
                print(f"  {esr / 1e3:>17.1f} kohm", end="")
            else:
                print(f"  {esr:>17.1f}  ohm", end="")
        print(f"  {R_FILTER / 1e6:>10.0f} Mohm")

    print(f"\n  ** Air gap capacitor has zero dielectric ESR and infinite R_dc —")
    print(f"     the ideal choice for preserving the LMP7721's femtoampere noise.")
    print(f"     FR4 dielectric ESR at Schumann frequencies is ~40x the filter")
    print(f"     resistor and R_dc generates 2000x more current noise than the")
    print(f"     LMP7721. Two masked PCBs with spacers = dirt cheap + perfect. **")


def print_custom_sweep(pullback_mm: float = 0.5):
    """Sweep board sizes for each substrate at its most common thickness."""

    print(f"\n{'=' * 95}")
    print("CAPACITANCE SWEEP — board side length vs. capacitance")
    print(f"Pullback: {pullback_mm:.1f} mm from each edge")
    print(f"{'=' * 95}")

    sides = np.arange(5.0, 35.0, 1.0)  # 5 mm to 34 mm

    # Pick one representative thickness per substrate
    representative = {
        "Air gap": 0.2,
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
    COLORS = {
        "Air gap": "#f2cc60",
        "FR4": "#ff7b72",
        "Rogers 4350B": "#7ee787",
        "Alumina (96%)": "#79c0ff",
    }

    representative = {
        "Air gap": 0.2,
        "FR4": 0.8,
        "Rogers 4350B": 0.508,
        "Alumina (96%)": 0.50,
    }

    sides = np.linspace(3.0, 35.0, 500)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14), sharex=True)
    fig.patch.set_facecolor(BG_COLOR)

    for ax in (ax1, ax2, ax3):
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
    ax1.set_title("ELARA — Plate Capacitor: Capacitance, DC Resistance & Filter fc vs. Board Size",
                  fontsize=13, fontweight="bold", color=TEXT_COLOR,
                  fontfamily="monospace", pad=15)
    legend1 = ax1.legend(loc="upper left", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend1.get_frame().set_alpha(0.9)
    ax1.set_ylim(0, 40)

    # --- Middle: DC leakage resistance vs. side ---
    for name, sub in SUBSTRATES.items():
        t = representative[name]
        r_dc_vals = np.array([dc_resistance(s, pullback_mm, t, sub["rho_volume"])
                              for s in sides])
        r_dc_vals = np.where(r_dc_vals > 0, r_dc_vals, np.nan)
        ax2.semilogy(sides, r_dc_vals, color=COLORS[name], linewidth=2,
                     label=f"{name}")

    ax2.axhline(R_FILTER, color="#f2cc60", linewidth=1.5, linestyle="--",
                alpha=0.7, label=f"R_filter: {R_FILTER / 1e6:.0f} Mohm")
    ax2.set_ylabel("DC leakage resistance (ohm)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    legend2 = ax2.legend(loc="lower left", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend2.get_frame().set_alpha(0.9)
    ax2.set_ylim(1e3, 1e15)

    # --- Bottom: 2-stage cascade fc vs. side ---
    for name, sub in SUBSTRATES.items():
        t = representative[name]
        fc_vals = np.array([fc_cascade_khz(
            capacitance_pf(s, pullback_mm, t, sub["epsilon_r"]))
            for s in sides])
        fc_vals = np.clip(fc_vals, 0, 500)
        ax3.plot(sides, fc_vals, color=COLORS[name], linewidth=2,
                 label=f"{name}")

    ax3.axhline(22.0, color="#d2a8ff", linewidth=1.5, linestyle="--",
                alpha=0.7, label="22 kHz (VLF top)")
    ax3.axhline(15.9, color="#f2cc60", linewidth=1.5, linestyle=":",
                alpha=0.7, label="15.9 kHz (PLAN.md target fc)")
    ax3.set_ylabel("2-stage cascade fc (kHz)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax3.set_xlabel("Board side length (mm)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    legend3 = ax3.legend(loc="upper right", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend3.get_frame().set_alpha(0.9)
    ax3.set_ylim(0, 120)
    ax3.set_xlim(3, 35)

    plt.tight_layout()
    out_path = __file__.replace(".py", ".svg")
    fig.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    pullback = 0.5  # mm — copper setback from each board edge

    print_design_table(pullback)
    print_custom_sweep(pullback)
    plot_sweep(pullback)
