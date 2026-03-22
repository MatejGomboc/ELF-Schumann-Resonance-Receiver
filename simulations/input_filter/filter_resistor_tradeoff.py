#!/usr/bin/env python3
"""
ELARA -- Input Filter Resistor Optimisation (ELF-focused)

The 2-stage RC input filter rejects AM/FM broadcast interference.
Air-gap capacitors are fixed at 50 pF each (100 pF total) to give
~1/2 signal division with the 140 pF antenna capacitance.

The resistor value R determines:
    - Filter cutoff: fc = 1/(2*pi*R*C) per stage
    - Thermal noise: en = sqrt(4*k*T*R) -- DOMINATES the noise budget
    - FM rejection: drops as R decreases (fc increases)

This script sweeps R to find the optimal trade-off between noise
and RF rejection.

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
C_ANT = 140e-12   # 140 pF

# Fixed capacitor value (each stage)
C_FILT = 50e-12   # 50 pF air-gap cap (x2 = 100 pF total)

# LMP7721
EN_LMP7721 = 6.5e-9
EN_1F_CORNER = 10.0
IN_LMP7721 = 0.01e-15

# AD820 (Romero reference -- no input filter)
EN_AD820 = 16.0e-9
EN_AD820_1F = 30.0
IN_AD820 = 0.8e-15

# PCB leakage (guarded)
I_PCB = 0.1e-15

# Feedback network (ELF bandpass)
R_FB = 9.1e3   # Rf
R_GND = 1.0e3  # Rg

# Air-gap capacitor geometry
AIR_GAP_MM = 0.5
PULLBACK_MM = 0.5

# Key frequencies
SCHUMANN = {"SR1": 7.83, "SR2": 14.3, "SR3": 20.8}
F_AM = 1e6       # AM broadcast
F_FM = 100e6     # FM broadcast
F_GSM = 900e6    # GSM


def thermal_noise(R):
    return np.sqrt(4.0 * k_B * T * R)


def en_1f(freq):
    return EN_LMP7721 * np.sqrt(1.0 + EN_1F_CORNER / freq)


def source_impedance(freq):
    return 1.0 / (2.0 * np.pi * freq * C_ANT)


def cap_divider():
    """Signal loss from capacitive voltage divider."""
    return C_ANT / (C_ANT + 2 * C_FILT)


def filter_rejection_db(R, f_rf, stages=2):
    """RF rejection in dB for 2-stage RC filter."""
    fc = 1.0 / (2.0 * np.pi * R * C_FILT)
    ratio = f_rf / fc
    # |H|^2 per stage = 1/(1 + (f/fc)^2)
    # 2 stages: |H|^2 = 1/(1 + (f/fc)^2)^2
    h_mag_sq = 1.0 / (1.0 + ratio**2)**stages
    return 10.0 * np.log10(h_mag_sq)


def total_noise_at_antenna(R, freq):
    """Effective noise at antenna terminals (includes cap divider loss)."""
    Z = source_impedance(freq)
    e_v = en_1f(freq)
    e_i = IN_LMP7721 * Z
    e_pcb = I_PCB * Z
    e_r = thermal_noise(R)
    e_fb = thermal_noise(R_FB)
    e_gnd = thermal_noise(R_GND)

    # Input-referred total
    e_input = np.sqrt(e_v**2 + e_i**2 + e_pcb**2 + 2 * e_r**2
                      + (e_fb / 10.1)**2 + e_gnd**2)  # Rf noise /G

    # Referred to antenna (divide by cap divider)
    return e_input / cap_divider()


def plate_side_mm(c_pf, gap_mm=AIR_GAP_MM, pullback_mm=PULLBACK_MM):
    """Plate side length for target capacitance."""
    c_f = c_pf * 1e-12
    d = gap_mm * 1e-3
    copper_side = np.sqrt(c_f * d / EPSILON_0)
    return copper_side * 1e3 + 2.0 * pullback_mm


def print_optimisation():
    print("=" * 115)
    print("ELARA -- Input Filter Resistor Optimisation")
    print(f"C_filt = {C_FILT*1e12:.0f} pF each (100 pF total), "
          f"C_ant = {C_ANT*1e12:.0f} pF")
    print(f"Cap divider: {cap_divider():.3f} ({20*np.log10(cap_divider()):.1f} dB)")
    print(f"Air-gap plate: {plate_side_mm(C_FILT*1e12):.1f} mm side "
          f"({AIR_GAP_MM} mm gap)")
    print("=" * 115)

    R_values = [10e3, 22e3, 33e3, 47e3, 68e3, 100e3, 150e3, 220e3, 330e3, 470e3, 1e6]

    # Romero reference (no filter, AD820)
    Z_sr1 = source_impedance(7.83)
    romero_noise = np.sqrt(
        (EN_AD820 * np.sqrt(1 + EN_AD820_1F / 7.83))**2
        + (IN_AD820 * Z_sr1)**2
    )

    print(f"\n  Romero AD820 noise at SR1 (no filter): {romero_noise*1e9:.1f} nV/sqrtHz")
    print(f"\n{'R_filt':>8} {'fc/stage':>10} {'R noise':>10} {'Total@ant':>12} "
          f"{'vs Romero':>10} {'FM rej':>10} {'AM rej':>10} {'GSM rej':>10}")
    print("-" * 115)

    best_R = None
    best_noise = 1e9

    for R in R_values:
        fc = 1.0 / (2.0 * np.pi * R * C_FILT)
        en_r = thermal_noise(R)
        eff_noise = total_noise_at_antenna(R, 7.83)

        improvement = romero_noise / (eff_noise * cap_divider())  # fair comparison
        # Actually compare input-referred: ELARA total at input vs Romero total at input
        e_input_elara = eff_noise * cap_divider()  # back to input-referred
        improvement = romero_noise / e_input_elara

        fm_rej = filter_rejection_db(R, F_FM)
        am_rej = filter_rejection_db(R, F_AM)
        gsm_rej = filter_rejection_db(R, F_GSM)

        R_str = f"{R/1e3:.0f}k" if R < 1e6 else f"{R/1e6:.1f}M"
        fc_str = f"{fc/1e3:.1f}kHz"

        marker = ""
        if fm_rej > -80:
            marker = " !! low FM rej"
        elif eff_noise < best_noise and fm_rej < -100:
            best_noise = eff_noise
            best_R = R
            marker = " <-- best"

        print(f"{R_str:>8} {fc_str:>10} {en_r*1e9:>8.1f}nV {eff_noise*1e9:>10.1f}nV "
              f"{improvement:>8.1f}x {fm_rej:>8.0f}dB {am_rej:>8.0f}dB "
              f"{gsm_rej:>8.0f}dB{marker}")

    if best_R:
        fc_best = 1.0 / (2.0 * np.pi * best_R * C_FILT)
        print(f"\n  OPTIMAL: R = {best_R/1e3:.0f}k")
        print(f"    fc = {fc_best/1e3:.1f} kHz per stage")
        print(f"    Thermal noise: {thermal_noise(best_R)*1e9:.1f} nV/sqrtHz each")
        print(f"    Effective noise at antenna: {best_noise*1e9:.1f} nV/sqrtHz")
        print(f"    FM rejection: {filter_rejection_db(best_R, F_FM):.0f} dB")
        print(f"    AM rejection: {filter_rejection_db(best_R, F_AM):.0f} dB")

    # Noise breakdown for optimal R
    print(f"\n{'NOISE BREAKDOWN at SR1 (7.83 Hz)':}")
    for R in [best_R or 220e3, 220e3]:
        R_str = f"{R/1e3:.0f}k"
        Z = source_impedance(7.83)
        e_v = en_1f(7.83)
        e_r = thermal_noise(R)
        e_pcb = I_PCB * Z
        e_total_inp = np.sqrt(e_v**2 + (IN_LMP7721*Z)**2 + e_pcb**2
                              + 2*e_r**2 + (thermal_noise(R_FB)/10.1)**2
                              + thermal_noise(R_GND)**2)
        print(f"\n  R = {R_str}:")
        print(f"    LMP7721 en:   {e_v*1e9:>7.2f} nV ({e_v**2/e_total_inp**2*100:>5.1f}%)")
        print(f"    PCB leakage:  {e_pcb*1e9:>7.2f} nV ({e_pcb**2/e_total_inp**2*100:>5.1f}%)")
        print(f"    R_filt (x2):  {e_r*np.sqrt(2)*1e9:>7.2f} nV "
              f"({2*e_r**2/e_total_inp**2*100:>5.1f}%)")
        print(f"    Rg (1k):      {thermal_noise(R_GND)*1e9:>7.2f} nV")
        print(f"    TOTAL input:  {e_total_inp*1e9:>7.2f} nV")
        print(f"    At antenna:   {e_total_inp/cap_divider()*1e9:>7.2f} nV")

    # FM rejection check
    print(f"\n{'FM REJECTION vs R_filt':}")
    print(f"  FM stations need at least -80 dB rejection to prevent")
    print(f"  LMP7721 intermodulation/rectification.")
    print(f"  With C={C_FILT*1e12:.0f}pF, minimum R for -80dB FM rejection:")
    # Solve: -80 = 10*log10(1/(1+(F_FM/fc)^2)^2)
    # (F_FM/fc)^4 = 10^8 → F_FM/fc = 316 → fc = F_FM/316 = 316 kHz
    # R = 1/(2pi*fc*C) = 1/(2pi*316e3*50e-12) = 10.1k
    R_min = 1.0 / (2.0 * np.pi * (F_FM / 316.0) * C_FILT)
    print(f"  R_min = {R_min/1e3:.1f}k (fc = {F_FM/316/1e3:.0f} kHz)")
    print(f"  -> Any R >= {R_min/1e3:.0f}k gives adequate FM rejection")


def plot_optimisation():
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available -- skipping plot")
        return

    BG = "#0d1117"
    TEXT = "#e6edf3"
    SUBTLE = "#7d8590"
    PANEL = "#161b22"
    BORDER = "#30363d"

    R_sweep = np.logspace(np.log10(10e3), np.log10(1e6), 200)

    noise_at_ant = np.array([total_noise_at_antenna(R, 7.83) for R in R_sweep]) * 1e9
    fm_rej = np.array([filter_rejection_db(R, F_FM) for R in R_sweep])
    fc_vals = 1.0 / (2.0 * np.pi * R_sweep * C_FILT) / 1e3  # kHz

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    fig.patch.set_facecolor(BG)

    for ax in (ax1, ax2):
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=SUBTLE, labelsize=9)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

    # Plot 1: Noise vs R
    ax1.semilogx(R_sweep / 1e3, noise_at_ant, color="#7ee787", linewidth=2.5,
                 label="ELARA effective noise @ antenna (SR1)")

    # Romero reference
    Z_sr1 = source_impedance(7.83)
    romero = np.sqrt((EN_AD820 * np.sqrt(1 + EN_AD820_1F / 7.83))**2
                     + (IN_AD820 * Z_sr1)**2) * 1e9
    ax1.axhline(romero, color="#d2a8ff", linewidth=1.5, linestyle="--",
                label=f"Romero AD820 (no filter): {romero:.0f} nV")

    # Current design
    current_noise = total_noise_at_antenna(220e3, 7.83) * 1e9
    ax1.axhline(current_noise, color="#ff7b72", linewidth=1, linestyle=":",
                alpha=0.7, label=f"Current R=220k: {current_noise:.0f} nV")

    ax1.set_ylabel("Noise at antenna (nV/sqrtHz)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    ax1.set_title("ELARA -- Filter Resistor Optimisation\n"
                  f"C_filt = {C_FILT*1e12:.0f} pF each, C_ant = {C_ANT*1e12:.0f} pF, "
                  f"cap divider = {cap_divider():.2f} ({20*np.log10(cap_divider()):.1f} dB)",
                  fontsize=12, fontweight="bold", color=TEXT,
                  fontfamily="monospace", pad=10)
    legend1 = ax1.legend(loc="upper left", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend1.get_frame().set_alpha(0.9)
    ax1.set_ylim(0, 200)

    # Plot 2: FM rejection vs R
    ax2.semilogx(R_sweep / 1e3, fm_rej, color="#79c0ff", linewidth=2.5,
                 label="FM rejection (100 MHz)")
    ax2.semilogx(R_sweep / 1e3,
                 [filter_rejection_db(R, F_AM) for R in R_sweep],
                 color="#f2cc60", linewidth=1.5, linestyle="--",
                 label="AM rejection (1 MHz)")
    ax2.axhline(-80, color="#ff7b72", linewidth=1, linestyle=":",
                label="Min acceptable (-80 dB)")
    ax2.axhline(-100, color="#ffa657", linewidth=1, linestyle=":",
                alpha=0.5, label="Comfortable (-100 dB)")

    ax2.set_xlabel("R_filt (kΩ)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax2.set_ylabel("Rejection (dB)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax2.set_ylim(-250, -20)
    legend2 = ax2.legend(loc="upper right", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend2.get_frame().set_alpha(0.9)

    # Add fc axis on top
    ax_top = ax1.twiny()
    ax_top.set_xscale("log")
    ax_top.set_xlim(ax1.get_xlim())
    # Show fc values
    tick_Rs = [10, 22, 47, 100, 220, 470, 1000]
    tick_fcs = [1/(2*np.pi*R*1e3*C_FILT)/1e3 for R in tick_Rs]
    ax_top.set_xticks(tick_Rs)
    ax_top.set_xticklabels([f"{fc:.0f}k" for fc in tick_fcs], fontsize=7)
    ax_top.tick_params(colors=SUBTLE, labelsize=7)
    ax_top.set_xlabel("fc per stage (Hz)", fontsize=9, color=SUBTLE,
                      fontfamily="monospace")

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "filter_resistor_tradeoff.svg")
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    print_optimisation()
    plot_optimisation()
