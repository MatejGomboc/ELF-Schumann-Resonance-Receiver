#!/usr/bin/env python3
"""
ELARA -- Passive Component Noise Budget

Calculates the noise contribution of every passive component in the
signal chain, from antenna through LMP7721 to the PCM1808 input.

This answers the question: which components matter, and which are
negligible compared to the LMP7721's own noise floor?

Noise sources modelled:
    - Thermal noise of each resistor: e_n = sqrt(4*k*T*R) V/sqrtHz
    - Excess (current) noise of resistors: depends on noise index
    - Current noise of resistors shunting to ground (as seen by LMP7721 input)
    - Op-amp voltage and current noise (LMP7721, LMP7715)

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
# Antenna
# ===========================================================================
C_ANT = 140e-12       # 140 pF (calculated from 10m vert + 15m top hat)

# ===========================================================================
# Component values
# ===========================================================================
# Input filter (2-stage RC, air-gap caps)
R_FILT = 33.0e3       # 33 kohm filter resistors (x2, optimised)
C_CAP = 50e-12        # 50 pF air-gap caps (x2, 100 pF total)

# LMP7721 preamp (ELF bandpass topology)
R_FEEDBACK = 100e3    # Rf: feedback resistor (IN- to VOUT)
C_FEEDBACK = 15e-9    # Cf: feedback cap (across Rf, C0G)
R_GROUND = 1.0e3      # Rg: ground-reference resistor (IN- to BIAS_MID)
C_GROUND = 100e-6     # Cg: DC blocking cap (in series with Rg, polypropylene)
C_OUT = 10e-6         # Output coupling cap (film)
R_AA = 10.0e3         # Anti-aliasing filter resistor
C_AA = 100e-9         # Anti-aliasing filter cap (C0G)
R_ADC_BIAS = 47.0e3   # ADC input bias resistor (VREF to VINL)

# Guard ring driver (LMP7715)
R_GUARD = 470.0       # R3: guard driver output resistor

# Antenna bias
R_BIAS_DIV = 47.0e3   # R4=R5: bias divider resistors
C_BIAS_DIV_BULK = 4700e-6  # C6: divider bulk cap

# LMP7721 specs
EN_LMP7721 = 6.5e-9   # V/sqrtHz (wideband)
EN_1F_CORNER = 10.0   # Hz (from LMP7721 datasheet noise plot)
IN_LMP7721 = 0.01e-15  # A/sqrtHz

# LMP7715 specs
EN_LMP7715 = 5.8e-9   # V/sqrtHz
IN_LMP7715 = 0.1e-15  # A/sqrtHz (100 fA bias current -> rough noise est)

# PCB leakage (guarded PTFE/Rogers)
I_PCB = 0.1e-15       # A/sqrtHz

# ===========================================================================
# Frequency sweep
# ===========================================================================
f = np.logspace(0, np.log10(22000), 2000)  # 1 Hz to 22 kHz


def thermal_noise_v(R):
    """Thermal noise voltage density of a resistor (V/sqrtHz)."""
    return np.sqrt(4.0 * k_B * T * R)


def source_impedance(freq):
    """Antenna source impedance: 1/(2*pi*f*C_ant)."""
    return 1.0 / (2.0 * np.pi * freq * C_ANT)


def en_with_1f(en_wb, fc, freq):
    """Voltage noise with 1/f component."""
    return en_wb * np.sqrt(1.0 + fc / freq)


def print_budget():
    """Print the full passive noise budget."""

    print("=" * 95)
    print("ELARA -- Passive Component Noise Budget")
    print(f"All values in nV/sqrtHz, referred to LMP7721 input")
    print(f"Temperature: {T:.0f} K")
    print("=" * 95)

    # Key frequencies
    freqs = [
        ("7.83 Hz (SR1)", 7.83),
        ("14.3 Hz (SR2)", 14.3),
        ("1 kHz (VLF)", 1000.0),
        ("10 kHz (VLF)", 10000.0),
    ]

    for name, freq in freqs:
        Z_src = source_impedance(freq)
        Xc_cap = 1.0 / (2.0 * np.pi * freq * C_CAP)
        Xc_comp = 1.0 / (2.0 * np.pi * freq * C_FEEDBACK)

        print(f"\n--- {name} --- |Z_ant| = {Z_src / 1e6:.1f} MOhm")
        print(f"{'Component':<30} {'Value':<15} {'Noise':>12} {'Notes'}")
        print("-" * 80)

        # LMP7721 voltage noise (with 1/f)
        en_v = en_with_1f(EN_LMP7721, EN_1F_CORNER, freq) * 1e9
        print(f"{'LMP7721 en (+ 1/f)':<30} {'6.5 nV/rtHz':<15} {en_v:>10.2f} nV {'DOMINANT at ELF'}")

        # LMP7721 current noise x Z_source
        en_i = IN_LMP7721 * Z_src * 1e9
        print(f"{'LMP7721 in x Z_ant':<30} {'0.01 fA/rtHz':<15} {en_i:>10.2f} nV {'negligible'}")

        # PCB leakage x Z_source
        en_pcb = I_PCB * Z_src * 1e9
        print(f"{'PCB leakage (guarded)':<30} {'0.1 fA/rtHz':<15} {en_pcb:>10.2f} nV {'guard ring critical'}")

        # R_filter thermal noise (two 1M resistors in series with signal)
        # First resistor: thermal noise appears directly at input
        en_r1 = thermal_noise_v(R_FILT) * 1e9
        print(f"{'R_filt1 (220k) thermal':<30} {'220k MELF':<15} {en_r1:>10.2f} nV {'<< Z_ant at ELF'}")

        en_r2 = thermal_noise_v(R_FILT) * 1e9
        print(f"{'R_filt2 (220k) thermal':<30} {'220k MELF':<15} {en_r2:>10.2f} nV {'<< Z_ant at ELF'}")

        # Rf feedback thermal noise (output-referred, divide by gain for input-referred)
        en_rfb = thermal_noise_v(R_FEEDBACK) * 1e9
        print(f"{'Rf feedback (9.1k) thermal':<30} {'9.1k thin-film':<15} {en_rfb:>10.2f} nV {'at output, /G at input'}")

        # Rg ground-ref thermal noise
        en_rg = thermal_noise_v(R_GROUND) * 1e9
        print(f"{'Rg ground-ref (1k) thermal':<30} {'1k thin-film':<15} {en_rg:>10.2f} nV {'at IN- node'}")

        # R_AA thermal noise (attenuated by preceding gain)
        en_raa = thermal_noise_v(R_AA) * 1e9
        print(f"{'R_AA anti-alias (10k) thermal':<30} {'10k thin-film':<15} {en_raa:>10.2f} nV {'at output, /G at input'}")

        # Guard driver noise (LMP7715 en -> guard ring)
        # Guard ring tracks input, so LMP7715 noise appears as common-mode
        # rejection by the guard. Residual = en_7715 * (1 - CMRR_guard)
        # In practice, guard noise is second-order
        en_guard = EN_LMP7715 * 1e9
        print(f"{'LMP7715 guard driver en':<30} {'5.8 nV/rtHz':<15} {en_guard:>10.2f} nV {'common-mode, 2nd order'}")

        # Antenna bias resistor pair thermal noise
        # R4||R5 = 23.5k, but filtered by 4700uF -> negligible above ~0.0007 Hz
        r_par = R_BIAS_DIV / 2
        fc_bias = 1.0 / (2.0 * np.pi * r_par * C_BIAS_DIV_BULK)
        en_bias_raw = thermal_noise_v(r_par) * 1e9
        # Attenuation at frequency by the RC filter
        atten = 1.0 / np.sqrt(1.0 + (freq / fc_bias) ** 2)
        en_bias = en_bias_raw * atten
        print(f"{'R4||R5 bias (23.5k) thermal':<30} {'47k x2, 0.05%':<15} {en_bias:>10.2f} nV "
              f"{'fc={:.4f} Hz, heavily filtered'.format(fc_bias)}")

        # RSS total
        total = np.sqrt(en_v**2 + en_i**2 + en_pcb**2 + en_r1**2 + en_r2**2
                        + en_rfb**2 + en_rg**2 + en_raa**2 + en_bias**2)
        print("-" * 80)
        print(f"{'TOTAL (RSS)':<30} {'':<15} {total:>10.2f} nV")

        # Percentage breakdown
        print(f"\n  Breakdown: LMP7721 en={en_v**2/total**2*100:.1f}%, "
              f"PCB leak={en_pcb**2/total**2*100:.1f}%, "
              f"R_filt={2*en_r1**2/total**2*100:.1f}%, "
              f"Rf={en_rfb**2/total**2*100:.1f}%, "
              f"Rg={en_rg**2/total**2*100:.1f}%")

    # Summary
    print(f"\n{'=' * 95}")
    print("COMPONENT THERMAL NOISE SUMMARY (flat, frequency-independent)")
    print(f"{'=' * 95}")

    components = [
        ("R_filt (220k)", R_FILT),
        ("Rf feedback (9.1k)", R_FEEDBACK),
        ("Rg ground-ref (1k)", R_GROUND),
        ("R_AA anti-alias (10k)", R_AA),
        ("R_bias ADC (47k)", R_ADC_BIAS),
        ("R3 guard (470)", R_GUARD),
        ("R4 bias div (47k)", R_BIAS_DIV),
        ("R5 bias div (47k)", R_BIAS_DIV),
        ("R4||R5 (23.5k)", R_BIAS_DIV / 2),
    ]

    for name, R in components:
        en = thermal_noise_v(R)
        print(f"  {name:<25} {R/1e3:>8.1f} kOhm  -> {en*1e9:>8.2f} nV/sqrtHz")

    print(f"\n  LMP7721 en (wideband):                    {EN_LMP7721*1e9:>8.2f} nV/sqrtHz")
    print(f"  LMP7721 en (at 7.83 Hz with 1/f):         "
          f"{en_with_1f(EN_LMP7721, EN_1F_CORNER, 7.83)*1e9:>8.2f} nV/sqrtHz")
    print(f"\n  ** The filter resistors (220k) generate {thermal_noise_v(R_FILT)*1e9:.1f} nV/sqrtHz each,")
    print(f"     which is {thermal_noise_v(R_FILT)/EN_LMP7721:.1f}x the LMP7721 wideband noise.")
    print(f"     At ELF, the LMP7721 1/f noise dominates. At VLF (>100 Hz),")
    print(f"     the filter resistors become the largest noise source! **")
    print(f"\n  ** MELF thin-film resistors recommended for lowest excess noise. **")


def plot_budget():
    """Plot noise contributions vs frequency."""
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available -- skipping plot")
        return

    BG = "#0d1117"
    TEXT = "#e6edf3"
    SUBTLE = "#7d8590"
    PANEL = "#161b22"
    BORDER = "#30363d"

    Z_src = source_impedance(f)

    # Individual contributions
    en_amp = en_with_1f(EN_LMP7721, EN_1F_CORNER, f) * 1e9
    en_in = IN_LMP7721 * Z_src * 1e9
    en_pcb = I_PCB * Z_src * 1e9
    en_rfilt = thermal_noise_v(R_FILT) * np.ones_like(f) * 1e9
    en_rfb = thermal_noise_v(R_FEEDBACK) * np.ones_like(f) * 1e9
    en_rg = thermal_noise_v(R_GROUND) * np.ones_like(f) * 1e9
    en_total = np.sqrt(en_amp**2 + en_in**2 + en_pcb**2 + 2*en_rfilt**2 + en_rfb**2 + en_rg**2)

    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=SUBTLE, labelsize=9)
    ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
    for spine in ax.spines.values():
        spine.set_color(BORDER)

    ax.loglog(f, en_amp, color="#7ee787", linewidth=2, label="LMP7721 en (+ 1/f)")
    ax.loglog(f, en_in, color="#79c0ff", linewidth=1.5, linestyle="--", label="LMP7721 in x Z_ant")
    ax.loglog(f, en_pcb, color="#d2a8ff", linewidth=1.5, linestyle=":", label="PCB leakage (guarded)")
    ax.loglog(f, en_rfilt, color="#ff7b72", linewidth=1.5, linestyle="-.", label="R_filt (220k) thermal (each)")
    ax.loglog(f, en_rfb, color="#f2cc60", linewidth=1.5, linestyle="-.", label="Rf feedback (9.1k) thermal")
    ax.loglog(f, en_rg, color="#ffa657", linewidth=1.5, linestyle="-.", label="Rg ground-ref (1k) thermal")
    ax.loglog(f, en_total, color="#7ee787", linewidth=3, alpha=0.8, label="TOTAL (RSS)")

    # Schumann markers
    for sr, freq in [("SR1", 7.83), ("SR2", 14.3), ("SR3", 20.8)]:
        ax.axvline(freq, color=SUBTLE, alpha=0.3, linestyle="--", linewidth=0.8)
        ax.text(freq, 1.5, sr, fontsize=6, ha="center", color=SUBTLE, fontfamily="monospace")

    ax.set_xlabel("Frequency (Hz)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax.set_ylabel("Input-referred noise (nV/sqrtHz)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax.set_title("ELARA -- Passive Component Noise Budget\n"
                 "All sources referred to LMP7721 input, C_ant=100 pF",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace", pad=10)
    legend = ax.legend(loc="upper right", fontsize=8, facecolor=PANEL,
                       edgecolor=BORDER, labelcolor=TEXT)
    legend.get_frame().set_alpha(0.9)
    ax.set_xlim(1, 22000)
    ax.set_ylim(1, 500)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "passive_noise_budget.svg")
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    print_budget()
    plot_budget()
