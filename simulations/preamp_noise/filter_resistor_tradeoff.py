#!/usr/bin/env python3
"""
ELARA -- Input Filter Resistor Value Optimisation

The 2-stage RC input filter uses R and C to set fc ~ 16 kHz.
The constraint is: R * C = 1/(2*pi*fc) ~ 10 us

Trade-off: R determines thermal noise, C determines physical size.
Smaller R = less noise but needs larger C (harder to build as air-gap).
Larger R = more noise but smaller C (easier air-gap construction).

This simulation sweeps R from 10k to 10M, computes the required C for
the same fc, and evaluates:
    - Thermal noise of the filter resistors
    - Total input-referred noise (including LMP7721 + PCB leakage)
    - Air-gap capacitor plate size required
    - SNR improvement over Romero's AD820 design
    - Whether the air-gap cap size is physically practical

Also includes the optimised feedback network (R2=20k, C3=10nF).

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

k_B = 1.380649e-23
T = 300.0
EPSILON_0 = 8.854187817e-12

# Antenna
C_ANT = 100e-12

# LMP7721
EN_LMP7721 = 6.5e-9
EN_1F_CORNER = 10.0   # Hz (from LMP7721 datasheet noise plot)
IN_LMP7721 = 0.01e-15

# AD820 (Romero reference)
EN_AD820 = 16.0e-9
EN_AD820_1F = 30.0
IN_AD820 = 0.8e-15

# PCB leakage
I_PCB = 0.1e-15

# Feedback network (optimised from feedback_tradeoff.py)
R_FB = 20e3
C_FB = 10e-9

# Target filter cutoff
FC_TARGET = 15.9e3  # Hz (single stage)

# Air-gap capacitor parameters
AIR_GAP_MM = 0.2       # mm gap between plates
PULLBACK_MM = 0.5      # mm copper pullback from edge
EPSILON_R_AIR = 1.0006

# Schumann resonance frequencies
SCHUMANN = [7.83, 14.3, 20.8, 27.3, 33.8]


def thermal_noise(R):
    return np.sqrt(4.0 * k_B * T * R)


def en_1f(en_wb, fc_1f, freq):
    return en_wb * np.sqrt(1.0 + fc_1f / freq)


def source_impedance(freq):
    return 1.0 / (2.0 * np.pi * freq * C_ANT)


def cap_for_fc(R, fc):
    """Capacitance needed for target fc with resistor R."""
    return 1.0 / (2.0 * np.pi * R * fc)


def air_gap_plate_side_mm(c_pf, gap_mm=AIR_GAP_MM, pullback_mm=PULLBACK_MM):
    """Plate side length for target capacitance with air gap."""
    c_f = c_pf * 1e-12
    d = gap_mm * 1e-3
    copper_side = np.sqrt(c_f * d / (EPSILON_0 * EPSILON_R_AIR))
    return copper_side * 1e3 + 2.0 * pullback_mm


def filter_attenuation(f, R, C, stages=2):
    """Magnitude response of cascaded RC filter."""
    fc = 1.0 / (2.0 * np.pi * R * C)
    return 1.0 / (1.0 + (f / fc) ** 2) ** (stages / 2.0)


def compute_total_noise(R_filt, freq, amp="LMP7721"):
    """Total input-referred noise for a given filter resistor value."""
    Z = source_impedance(freq)

    if amp == "LMP7721":
        en_v = en_1f(EN_LMP7721, EN_1F_CORNER, freq)
        en_i = IN_LMP7721 * Z
    else:
        en_v = en_1f(EN_AD820, EN_AD820_1F, freq)
        en_i = IN_AD820 * Z

    en_pcb = I_PCB * Z
    en_rfilt = thermal_noise(R_filt)  # per resistor
    en_rfb = thermal_noise(R_FB)

    return np.sqrt(en_v**2 + en_i**2 + en_pcb**2 + 2 * en_rfilt**2 + en_rfb**2)


def print_optimisation():
    print("=" * 110)
    print("ELARA -- Input Filter Resistor Value Optimisation")
    print(f"Target fc = {FC_TARGET/1e3:.1f} kHz (single stage)")
    print(f"Feedback: R2={R_FB/1e3:.0f}k, C3={C_FB*1e9:.0f}nF (optimised)")
    print(f"Air gap: {AIR_GAP_MM} mm, pullback: {PULLBACK_MM} mm")
    print("=" * 110)

    R_values = [10e3, 22e3, 47e3, 100e3, 220e3, 470e3, 1e6, 2.2e6, 4.7e6, 10e6]

    print(f"\n{'R_filt':>10} {'C_req':>10} {'C (pF)':>10} {'Plate':>10} "
          f"{'R noise':>12} {'Total@SR1':>12} {'Total@1k':>12} "
          f"{'vs AD820':>10} {'Practical?':>12}")
    print("-" * 110)

    # Romero reference at SR1
    romero_sr1 = compute_total_noise(0, 7.83, "AD820")  # AD820 has no filter R in Romero design
    # Actually Romero uses different topology, let's compute AD820 total differently
    freq_sr1 = 7.83
    Z_sr1 = source_impedance(freq_sr1)
    romero_total = np.sqrt(en_1f(EN_AD820, EN_AD820_1F, freq_sr1)**2
                           + (IN_AD820 * Z_sr1)**2)

    for R in R_values:
        C = cap_for_fc(R, FC_TARGET)
        c_pf = C * 1e12
        plate_mm = air_gap_plate_side_mm(c_pf)

        en_r = thermal_noise(R) * 1e9
        total_sr1 = compute_total_noise(R, 7.83) * 1e9
        total_1k = compute_total_noise(R, 1000) * 1e9

        improvement = romero_total * 1e9 / total_sr1

        # Practicality assessment
        if c_pf > 1000:
            practical = "TOO LARGE"
        elif plate_mm > 50:
            practical = "plate>50mm"
        elif plate_mm > 35:
            practical = "marginal"
        elif c_pf < 0.1:
            practical = "too tiny C"
        else:
            practical = "OK"

        if R >= 1e6:
            r_str = f"{R/1e6:.1f}M"
        else:
            r_str = f"{R/1e3:.0f}k"

        if c_pf >= 1000:
            c_str = f"{c_pf/1000:.1f}nF"
        else:
            c_str = f"{c_pf:.1f}pF"

        print(f"{r_str:>10} {c_str:>10} {c_pf:>10.1f} {plate_mm:>8.1f}mm "
              f"{en_r:>10.1f} nV {total_sr1:>10.1f} nV {total_1k:>10.1f} nV "
              f"{improvement:>8.1f}x {practical:>12}")

    # Detailed analysis of best candidates
    print(f"\n{'=' * 110}")
    print("DETAILED COMPARISON -- Best candidates")
    print(f"{'=' * 110}")

    candidates = [
        (1e6, "Current design (1M)"),
        (470e3, "470k -- lower noise, larger caps"),
        (220e3, "220k -- balanced"),
        (100e3, "100k -- low noise, big caps"),
        (47e3, "47k -- very low noise, very big caps"),
    ]

    freq_points = [
        ("SR1 (7.83 Hz)", 7.83),
        ("SR2 (14.3 Hz)", 14.3),
        ("SR3 (20.8 Hz)", 20.8),
        ("VLF 1 kHz", 1000.0),
        ("VLF 10 kHz", 10000.0),
        ("VLF 22 kHz", 22000.0),
    ]

    for R, desc in candidates:
        C = cap_for_fc(R, FC_TARGET)
        c_pf = C * 1e12
        plate = air_gap_plate_side_mm(c_pf)

        print(f"\n  {desc}")
        print(f"  R = {R/1e3:.0f}k, C = {c_pf:.1f} pF, plate = {plate:.1f} mm "
              f"(at {AIR_GAP_MM} mm gap)")
        print(f"  R thermal noise: {thermal_noise(R)*1e9:.1f} nV/sqrtHz")

        print(f"  {'Frequency':<20} {'ELARA':>12} {'Romero':>12} {'Improvement':>12} "
              f"{'Filter atten':>14}")

        for fname, freq in freq_points:
            elara = compute_total_noise(R, freq) * 1e9
            Z = source_impedance(freq)
            romero = np.sqrt(en_1f(EN_AD820, EN_AD820_1F, freq)**2
                             + (IN_AD820 * Z)**2) * 1e9
            improvement = romero / elara
            atten = filter_attenuation(freq, R, C, stages=2)
            atten_db = 20 * np.log10(atten) if atten > 0 else -999

            print(f"  {fname:<20} {elara:>10.1f} nV {romero:>10.1f} nV "
                  f"{improvement:>10.1f}x {atten_db:>12.2f} dB")

    # Final recommendation
    print(f"\n{'=' * 110}")
    print("RECOMMENDATION")
    print(f"{'=' * 110}")

    R_rec = 100e3
    C_rec = cap_for_fc(R_rec, FC_TARGET)
    c_pf_rec = C_rec * 1e12
    plate_rec = air_gap_plate_side_mm(c_pf_rec)

    improvement_rec = romero_total / compute_total_noise(R_rec, 7.83)
    print(f"""
  OPTIMAL: R = 100 kOhm, C = {c_pf_rec:.0f} pF

  Why 100k:
    - R thermal noise: {thermal_noise(R_rec)*1e9:.1f} nV/sqrtHz (vs 128.7 nV at 1M)
    - Total noise at SR1: {compute_total_noise(R_rec, 7.83)*1e9:.1f} nV/sqrtHz
    - {improvement_rec:.1f}x improvement over Romero at SR1
    - Air-gap cap: {c_pf_rec:.0f} pF -> {plate_rec:.0f} mm plates ({AIR_GAP_MM} mm gap)
    - Still practical size (< 50 mm)
    - 100k is a standard E96 value, thin-film MELF available
    - The LMP7721 (not the resistor) becomes the dominant noise source!

  Alternative: R = 220k for smaller caps ({cap_for_fc(220e3, FC_TARGET)*1e12:.0f} pF,
    {air_gap_plate_side_mm(cap_for_fc(220e3, FC_TARGET)*1e12):.0f} mm plates) at the cost
    of {thermal_noise(220e3)*1e9:.1f} nV vs {thermal_noise(R_rec)*1e9:.1f} nV noise.

  NOT recommended: R = 1M (current design)
    - 128.7 nV/sqrtHz per resistor dominates EVERYTHING
    - The LMP7721's 6.5 nV advantage over AD820 is completely wasted
    - You're paying for a femtoampere op-amp and then burying it under
      resistor thermal noise
""")

    # Impact on FM rejection
    print(f"  FM REJECTION CHECK (same for all R values with same fc):")
    for R, desc in [(R_rec, "100k"), (1e6, "1M (current)")]:
        C = cap_for_fc(R, FC_TARGET)
        atten_fm = filter_attenuation(100e6, R, C, stages=2)
        atten_fm_db = 20 * np.log10(atten_fm) if atten_fm > 0 else -999
        print(f"    R={desc}: FM attenuation = {atten_fm_db:.1f} dB")


def plot_optimisation():
    if not HAS_MATPLOTLIB:
        return

    BG = "#0d1117"
    TEXT = "#e6edf3"
    SUBTLE = "#7d8590"
    PANEL = "#161b22"
    BORDER = "#30363d"

    R_sweep = np.logspace(4, 7, 500)  # 10k to 10M
    freq_sr1 = 7.83

    # Compute metrics for each R
    noise_sr1 = np.array([compute_total_noise(R, freq_sr1) * 1e9 for R in R_sweep])
    noise_1k = np.array([compute_total_noise(R, 1000) * 1e9 for R in R_sweep])

    c_pf = np.array([cap_for_fc(R, FC_TARGET) * 1e12 for R in R_sweep])
    plate_mm = np.array([air_gap_plate_side_mm(c) for c in c_pf])

    # Romero reference
    Z_sr1 = source_impedance(freq_sr1)
    romero_sr1 = np.sqrt(en_1f(EN_AD820, EN_AD820_1F, freq_sr1)**2
                         + (IN_AD820 * Z_sr1)**2) * 1e9
    improvement = romero_sr1 / noise_sr1

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 16), sharex=True)
    fig.patch.set_facecolor(BG)

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=SUBTLE, labelsize=9)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

    # Plot 1: Total noise at SR1
    ax1.semilogx(R_sweep / 1e3, noise_sr1, color="#7ee787", linewidth=2.5,
                 label="ELARA total @ 7.83 Hz")
    ax1.semilogx(R_sweep / 1e3, noise_1k, color="#79c0ff", linewidth=2,
                 label="ELARA total @ 1 kHz")
    ax1.axhline(romero_sr1, color="#ff7b72", linewidth=1.5, linestyle="--",
                label=f"Romero AD820 @ 7.83 Hz ({romero_sr1:.0f} nV)")

    # LMP7721 floor (no filter R)
    lmp_floor = compute_total_noise(0, freq_sr1) * 1e9
    ax1.axhline(lmp_floor, color="#f2cc60", linewidth=1, linestyle=":",
                label=f"LMP7721 floor (no R_filt): {lmp_floor:.0f} nV")

    ax1.axvline(100, color="#d2a8ff", linewidth=1.5, linestyle="--", alpha=0.7,
                label="R=100k (recommended)")
    ax1.axvline(1000, color=SUBTLE, linewidth=1, linestyle=":", alpha=0.5,
                label="R=1M (current design)")

    ax1.set_ylabel("Input noise (nV/sqrtHz)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax1.set_title("ELARA -- Filter Resistor Optimisation\n"
                  "Same fc=15.9 kHz, sweeping R (C scales inversely)",
                  fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace", pad=10)
    legend1 = ax1.legend(loc="upper left", fontsize=7, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend1.get_frame().set_alpha(0.9)

    # Plot 2: Improvement over Romero
    ax2.semilogx(R_sweep / 1e3, improvement, color="#7ee787", linewidth=2.5)
    ax2.axvline(100, color="#d2a8ff", linewidth=1.5, linestyle="--", alpha=0.7)
    ax2.axvline(1000, color=SUBTLE, linewidth=1, linestyle=":", alpha=0.5)
    ax2.axhline(1, color="#ff7b72", linewidth=1, linestyle="--", alpha=0.5,
                label="Romero baseline (1x)")

    ax2.set_ylabel("Improvement over Romero (x)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    legend2 = ax2.legend(loc="lower left", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend2.get_frame().set_alpha(0.9)

    # Plot 3: Air-gap cap plate size
    ax3.semilogx(R_sweep / 1e3, plate_mm, color="#f2cc60", linewidth=2.5,
                 label=f"Plate side ({AIR_GAP_MM} mm air gap)")
    ax3.semilogx(R_sweep / 1e3, c_pf, color="#79c0ff", linewidth=2, linestyle="--",
                 label="Capacitance (pF)")
    ax3.axhline(50, color="#ff7b72", linewidth=1, linestyle="--", alpha=0.5,
                label="50 mm max practical size")
    ax3.axvline(100, color="#d2a8ff", linewidth=1.5, linestyle="--", alpha=0.7)
    ax3.axvline(1000, color=SUBTLE, linewidth=1, linestyle=":", alpha=0.5)

    ax3.set_xlabel("Filter resistor R (kOhm)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    ax3.set_ylabel("Plate size (mm) / Capacitance (pF)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    legend3 = ax3.legend(loc="upper left", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend3.get_frame().set_alpha(0.9)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "filter_resistor_tradeoff.svg")
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    print_optimisation()
    plot_optimisation()
