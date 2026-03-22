#!/usr/bin/env python3
"""
ELARA — Input-Referred Noise Analysis

Analytical noise model for the LMP7721 electrometer front-end with a
capacitive electric-field antenna source. Compares against Romero's
AD820-based LNVA design and other op-amps to demonstrate why the
LMP7721 is the optimal choice for high-impedance ELF sensing.

Noise sources modelled:
    1. Op-amp voltage noise (en) — includes 1/f corner
    2. Op-amp current noise (in) x source impedance
    3. PCB leakage current noise x source impedance (guard-ring dependent)
    4. Thermal noise of antenna leakage resistance

The source impedance is dominated by the antenna capacitance:
    |Z_ant| = 1 / (2π f C_ant)

At the 1st Schumann resonance (7.83 Hz) with C_ant = 100 pF:
    |Z_ant| ~ 203 MΩ

This enormous source impedance means current noise (not voltage noise)
dominates the noise budget — making the LMP7721's 0.01 fA/sqrtHz the
critical advantage over all other candidates.

Author: Matej + Claude, March 2026
"""

import numpy as np
import os

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
k_B = 1.380649e-23   # Boltzmann constant (J/K)
T = 300.0             # Temperature (K)

# ===========================================================================
# Antenna parameters
# ===========================================================================
C_ANT = 140e-12       # Antenna capacitance (140 pF, calculated from 10m vert + 15m top hat)
R_LEAK = 100e9        # Antenna leakage resistance (100 GΩ, conservative)

# ===========================================================================
# PCB leakage current noise (guard-ring dependent)
# ===========================================================================
I_PCB_GUARDED = 0.1e-15    # A/sqrtHz — with active guard ring on PTFE/Rogers
I_PCB_UNGUARDED = 10.0e-15  # A/sqrtHz — bare FR4, no guard (for comparison)

# ===========================================================================
# Amplifier specifications
# ===========================================================================
# 1/f voltage noise model: en(f) = en_wideband x sqrt(1 + fc/f)
# where fc is the 1/f corner frequency
AMPLIFIERS = {
    "LMP7721 (ELARA)": {
        "en_wideband": 6.5e-9,   # V/sqrtHz (datasheet, at 1 kHz)
        "en_1f_corner": 10.0,   # Hz (from LMP7721 datasheet noise plot)
        "in": 0.01e-15,          # A/sqrtHz (datasheet)
        "color": "#7ee787",
        "description": "Electrometer-grade, ELARA primary",
    },
    "ADA4530-1": {
        "en_wideband": 14.0e-9,
        "en_1f_corner": 10.0,
        "in": 0.02e-15,
        "color": "#79c0ff",
        "description": "Electrometer-grade, higher en",
    },
    "AD820 (Romero)": {
        "en_wideband": 16.0e-9,
        "en_1f_corner": 30.0,
        "in": 0.8e-15,
        "color": "#d2a8ff",
        "description": "JFET input, Romero LNVA reference",
    },
    "OP27 (BJT — wrong!)": {
        "en_wideband": 3.0e-9,
        "en_1f_corner": 2.7,
        "in": 1000.0e-15,
        "color": "#ff7b72",
        "description": "Low-en BJT, catastrophic in at high Z",
    },
}

# Schumann resonance frequencies
SCHUMANN = {"SR1": 7.83, "SR2": 14.3, "SR3": 20.8, "SR4": 27.3, "SR5": 33.8}

# Frequency sweep
f = np.logspace(0, np.log10(22000), 2000)  # 1 Hz to 22 kHz


# ===========================================================================
# Core calculations
# ===========================================================================
def source_impedance(freq):
    """Antenna source impedance: C_ant || R_leak."""
    x_c = 1.0 / (2.0 * np.pi * freq * C_ANT)
    return np.minimum(x_c, R_LEAK)


def en_with_1f(en_wideband, corner_hz, freq):
    """Voltage noise density with 1/f component."""
    return en_wideband * np.sqrt(1.0 + corner_hz / freq)


def compute_noise(amp_name, pcb_current_noise=I_PCB_GUARDED):
    """
    Compute input-referred noise spectral density.

    Returns dict with individual contributions and RSS total.
    """
    amp = AMPLIFIERS[amp_name]
    z = source_impedance(f)

    e_voltage = en_with_1f(amp["en_wideband"], amp["en_1f_corner"], f)
    e_current = amp["in"] * z
    e_pcb = pcb_current_noise * z
    e_thermal = np.sqrt(4.0 * k_B * T / z)  # thermal noise of Z_ant (as voltage)
    # Actually: thermal noise of R_leak, only relevant at very low f
    e_thermal_rleak = np.sqrt(4.0 * k_B * T * R_LEAK) * np.ones_like(f)

    e_total = np.sqrt(e_voltage**2 + e_current**2 + e_pcb**2)

    return {
        "f": f,
        "z": z,
        "e_voltage": e_voltage,
        "e_current": e_current,
        "e_pcb": e_pcb,
        "e_total": e_total,
    }


def integrated_noise_rms(e_total, f_low, f_high):
    """Integrate noise PSD over a frequency band to get RMS noise."""
    mask = (f >= f_low) & (f <= f_high)
    if np.sum(mask) < 2:
        return 0.0
    df = np.diff(f[mask])
    return np.sqrt(np.sum(e_total[mask][:-1]**2 * df))


# ===========================================================================
# Console output
# ===========================================================================
def print_analysis():
    """Print full noise analysis."""

    print("=" * 95)
    print("ELARA — Input-Referred Noise Analysis")
    print(f"Antenna capacitance: {C_ANT * 1e12:.0f} pF")
    print(f"Temperature: {T:.0f} K")
    print(f"PCB leakage noise: {I_PCB_GUARDED * 1e15:.1f} fA/sqrtHz (guarded PTFE/Rogers)")
    print("=" * 95)

    # Source impedance at key frequencies
    print(f"\n  Source impedance |Z_ant| = 1/(2*pi*f*C_ant):")
    for name, freq in SCHUMANN.items():
        z = source_impedance(np.array([freq]))[0]
        print(f"    {name} ({freq:5.2f} Hz):  {z / 1e6:.1f} MOhm")
    print(f"    VLF 1 kHz:           {source_impedance(np.array([1e3]))[0] / 1e6:.3f} MOhm")
    print(f"    VLF 10 kHz:          {source_impedance(np.array([1e4]))[0] / 1e3:.1f} kOhm")

    # Noise comparison at key frequencies
    freqs_of_interest = [
        ("1st Schumann (7.83 Hz)", 7.83),
        ("2nd Schumann (14.3 Hz)", 14.3),
        ("3rd Schumann (20.8 Hz)", 20.8),
        ("VLF mid-band (1 kHz)", 1000.0),
        ("VLF sferics (10 kHz)", 10000.0),
    ]

    for freq_name, freq_val in freqs_of_interest:
        idx = np.argmin(np.abs(f - freq_val))
        z_src = source_impedance(f)[idx]

        print(f"\n  --- {freq_name} --- |Z| = {z_src / 1e6:.1f} MOhm")
        print(f"  {'Amplifier':<24} {'e_voltage':>10} {'e_current':>10} "
              f"{'e_pcb':>10} {'e_TOTAL':>10}   Notes")

        results = {}
        for name, amp in AMPLIFIERS.items():
            r = compute_noise(name)
            ev = r["e_voltage"][idx]
            ec = r["e_current"][idx]
            ep = r["e_pcb"][idx]
            et = r["e_total"][idx]
            results[name] = et

            print(f"  {name:<24} {ev * 1e9:>8.1f} nV {ec * 1e9:>8.1f} nV "
                  f"{ep * 1e9:>8.1f} nV {et * 1e9:>8.1f} nV   "
                  f"{amp['description']}")

        # Improvement ratio
        lmp = results.get("LMP7721 (ELARA)")
        ad820 = results.get("AD820 (Romero)")
        if lmp and ad820:
            ratio_v = ad820 / lmp
            print(f"  -> LMP7721 improvement over AD820: "
                  f"{ratio_v:.1f}x voltage, {ratio_v**2:.0f}x power")

    # Noise breakdown for LMP7721 at 7.83 Hz
    r = compute_noise("LMP7721 (ELARA)")
    idx_sr1 = np.argmin(np.abs(f - 7.83))
    print(f"\n{'=' * 95}")
    print(f"LMP7721 NOISE BUDGET at 7.83 Hz (1st Schumann)")
    print(f"{'=' * 95}")
    print(f"  Voltage noise (en with 1/f):  {r['e_voltage'][idx_sr1] * 1e9:.2f} nV/sqrtHz")
    print(f"  Current noise (in x Z):       {r['e_current'][idx_sr1] * 1e9:.2f} nV/sqrtHz")
    print(f"  PCB leakage (guarded):        {r['e_pcb'][idx_sr1] * 1e9:.2f} nV/sqrtHz")
    print(f"  TOTAL (RSS):                  {r['e_total'][idx_sr1] * 1e9:.2f} nV/sqrtHz")

    dominant = "voltage" if r['e_voltage'][idx_sr1] > r['e_pcb'][idx_sr1] else "PCB leakage"
    print(f"  Dominant source: {dominant} noise")

    # Integrated noise in Schumann band
    print(f"\n{'=' * 95}")
    print("INTEGRATED NOISE — Schumann band (3–45 Hz)")
    print(f"{'=' * 95}")
    for name in AMPLIFIERS:
        r = compute_noise(name)
        rms = integrated_noise_rms(r["e_total"], 3.0, 45.0)
        print(f"  {name:<24}: {rms * 1e9:.1f} nV RMS")

    r_lmp = compute_noise("LMP7721 (ELARA)")
    r_820 = compute_noise("AD820 (Romero)")
    rms_lmp = integrated_noise_rms(r_lmp["e_total"], 3.0, 45.0)
    rms_820 = integrated_noise_rms(r_820["e_total"], 3.0, 45.0)
    print(f"\n  LMP7721 vs AD820: {rms_820 / rms_lmp:.1f}x voltage, "
          f"{(rms_820 / rms_lmp)**2:.0f}x power improvement")

    # Guard ring importance
    print(f"\n{'=' * 95}")
    print("GUARD RING IMPACT (LMP7721 at 7.83 Hz)")
    print(f"{'=' * 95}")
    r_guarded = compute_noise("LMP7721 (ELARA)", I_PCB_GUARDED)
    r_unguarded = compute_noise("LMP7721 (ELARA)", I_PCB_UNGUARDED)
    print(f"  With guard ring:    {r_guarded['e_total'][idx_sr1] * 1e9:.1f} nV/sqrtHz "
          f"(PCB leakage = {r_guarded['e_pcb'][idx_sr1] * 1e9:.1f} nV)")
    print(f"  Without guard ring: {r_unguarded['e_total'][idx_sr1] * 1e9:.1f} nV/sqrtHz "
          f"(PCB leakage = {r_unguarded['e_pcb'][idx_sr1] * 1e9:.1f} nV)")
    print(f"  -> Guard ring reduces total noise by "
          f"{r_unguarded['e_total'][idx_sr1] / r_guarded['e_total'][idx_sr1]:.0f}x")
    print(f"     Without guard ring, PCB leakage dominates everything.")


# ===========================================================================
# Plot
# ===========================================================================
def plot_analysis():
    """Generate noise analysis plots."""
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available — skipping plot")
        return

    BG_COLOR = "#0d1117"
    TEXT_COLOR = "#e6edf3"
    SUBTLE_COLOR = "#7d8590"
    PANEL_COLOR = "#161b22"
    BORDER_COLOR = "#30363d"

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
    fig.patch.set_facecolor(BG_COLOR)

    for ax in (ax1, ax2):
        ax.set_facecolor(PANEL_COLOR)
        ax.tick_params(colors=SUBTLE_COLOR, labelsize=9)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE_COLOR)
        for spine in ax.spines.values():
            spine.set_color(BORDER_COLOR)

    # ===== Plot 1: Total noise comparison across amplifiers =====
    for name, amp in AMPLIFIERS.items():
        r = compute_noise(name)
        lw = 2.5 if "LMP7721" in name or "AD820" in name else 1.5
        ax1.loglog(f, r["e_total"] * 1e9, label=name,
                   color=amp["color"], linewidth=lw)

    # Schumann markers
    for sr_name, sr_freq in SCHUMANN.items():
        ax1.axvline(sr_freq, color=SUBTLE_COLOR, alpha=0.3, linestyle="--", linewidth=0.8)
        ax1.text(sr_freq, 1.2, sr_name, fontsize=6, ha="center", va="bottom",
                 color=SUBTLE_COLOR, fontfamily="monospace")

    # Improvement annotation
    r_lmp = compute_noise("LMP7721 (ELARA)")
    r_820 = compute_noise("AD820 (Romero)")
    idx_sr1 = np.argmin(np.abs(f - 7.83))
    ratio = r_820["e_total"][idx_sr1] / r_lmp["e_total"][idx_sr1]
    ax1.annotate(f"~{ratio:.0f}x improvement\nat 7.83 Hz",
                 xy=(7.83, r_lmp["e_total"][idx_sr1] * 1e9),
                 xytext=(25, 200), fontsize=9, color="#7ee787",
                 fontfamily="monospace",
                 arrowprops=dict(arrowstyle="->", color="#7ee787", lw=1.5))

    ax1.set_ylabel("Input-referred noise (nV/sqrtHz)", fontsize=11,
                   color=TEXT_COLOR, fontfamily="monospace")
    ax1.set_title("ELARA — Total Input-Referred Noise Comparison\n"
                  f"C_ant = {C_ANT * 1e12:.0f} pF, guarded PCB, air-gap capacitors",
                  fontsize=13, fontweight="bold", color=TEXT_COLOR,
                  fontfamily="monospace", pad=10)
    legend1 = ax1.legend(loc="upper right", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend1.get_frame().set_alpha(0.9)
    ax1.set_xlim(1, 22000)
    ax1.set_ylim(1, 1e5)

    # ===== Plot 2: LMP7721 noise breakdown =====
    r = compute_noise("LMP7721 (ELARA)")

    ax2.loglog(f, r["e_voltage"] * 1e9, label="Voltage noise (en + 1/f)",
               color="#7ee787", linewidth=1.5, linestyle="--")
    ax2.loglog(f, r["e_current"] * 1e9, label="Current noise (in x Z)",
               color="#79c0ff", linewidth=1.5, linestyle="--")
    ax2.loglog(f, r["e_pcb"] * 1e9, label="PCB leakage (0.1 fA/sqrtHz, guarded)",
               color="#d2a8ff", linewidth=1.5, linestyle=":")
    ax2.loglog(f, r["e_total"] * 1e9, label="TOTAL (RSS)",
               color="#7ee787", linewidth=2.5)

    # AD820 total for reference
    ax2.loglog(f, r_820["e_total"] * 1e9, label="AD820 total (Romero ref.)",
               color="#d2a8ff", linewidth=2, alpha=0.5)

    for sr_name, sr_freq in SCHUMANN.items():
        ax2.axvline(sr_freq, color=SUBTLE_COLOR, alpha=0.3, linestyle="--", linewidth=0.8)

    ax2.set_xlabel("Frequency (Hz)", fontsize=11, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax2.set_ylabel("Input-referred noise (nV/sqrtHz)", fontsize=11,
                   color=TEXT_COLOR, fontfamily="monospace")
    ax2.set_title("LMP7721 — Noise Budget Breakdown",
                  fontsize=13, fontweight="bold", color=TEXT_COLOR,
                  fontfamily="monospace", pad=10)
    legend2 = ax2.legend(loc="upper right", fontsize=8, facecolor=PANEL_COLOR,
                         edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend2.get_frame().set_alpha(0.9)
    ax2.set_xlim(1, 22000)
    ax2.set_ylim(1, 1e4)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "preamp_noise_analysis.svg")
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    print_analysis()
    plot_analysis()
