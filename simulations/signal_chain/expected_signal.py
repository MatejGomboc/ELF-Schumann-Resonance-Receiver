#!/usr/bin/env python3
"""
ELARA -- Expected Signal Level & SNR at Antenna

Calculates the expected Schumann resonance signal voltage at the
antenna and through the receiver chain, based on published
atmospheric electric field measurements.

The vertical electric field PSD of Schumann resonances has been
measured extensively since Balser & Wagner (1960). Typical values
from Sentman (1995), Nickolaenko & Hayakawa (2002, 2014), and
Price & Melnikov (2004):

    E-field PSD at SR1: ~1e-12 to 1e-10 (V/m)^2/Hz
    sqrt(PSD) ~ 1-10 uV/m/sqrtHz (depending on conditions)

The induced voltage on a vertically-oriented antenna is:
    V_ant = E_z * h_eff

where h_eff is the antenna effective height:
    h_eff ~ h_physical / 2   (for electrically short monopole)

Signal levels vary with:
    - Time of day (thunderstorm activity in Africa/Americas/Asia)
    - Season (summer hemisphere has more lightning)
    - Solar cycle (affects ionosphere D-layer height)
    - Local weather
    - Latitude (SR amplitudes higher near equator)

References:
    [1] Sentman (1995), "Schumann resonances" in Handbook of
        Atmospheric Electrodynamics, Vol 1, Ch 11
    [2] Nickolaenko & Hayakawa (2002), "Resonances in the
        Earth-Ionosphere Cavity", Springer
    [3] Price & Melnikov (2004), J. Atmos. Solar-Terr. Phys.
    [4] Romero, R. (vlf.it) - practical measurements with AD820

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

# ============================================================
# Physical constants
# ============================================================
k_B = 1.380649e-23
T = 300.0

# ============================================================
# Schumann resonance parameters (from published measurements)
# ============================================================

# SR frequencies and Q-factors (from Sentman 1995, Table 11.1)
SR_MODES = {
    "SR1": {"f0": 7.83, "Q": 4.5, "label": "1st Schumann"},
    "SR2": {"f0": 14.1, "Q": 5.0, "label": "2nd Schumann"},
    "SR3": {"f0": 20.3, "Q": 6.0, "label": "3rd Schumann"},
    "SR4": {"f0": 26.4, "Q": 6.5, "label": "4th Schumann"},
    "SR5": {"f0": 32.5, "Q": 7.0, "label": "5th Schumann"},
    "SR6": {"f0": 38.0, "Q": 7.0, "label": "6th Schumann"},
    "SR7": {"f0": 44.0, "Q": 7.5, "label": "7th Schumann"},
}

# E-field spectral density at each SR peak (V/m/sqrtHz)
# Range from quiet to active conditions
# Based on Nickolaenko & Hayakawa (2002), Price & Melnikov (2004)
SR_EFIELD_QUIET = {   # quiet conditions (night, low lightning)
    "SR1": 0.3e-6,    # 0.3 uV/m/sqrtHz
    "SR2": 0.15e-6,
    "SR3": 0.10e-6,
    "SR4": 0.07e-6,
    "SR5": 0.05e-6,
    "SR6": 0.04e-6,
    "SR7": 0.03e-6,
}

SR_EFIELD_TYPICAL = {  # typical daytime conditions
    "SR1": 1.0e-6,     # 1.0 uV/m/sqrtHz
    "SR2": 0.5e-6,
    "SR3": 0.35e-6,
    "SR4": 0.25e-6,
    "SR5": 0.18e-6,
    "SR6": 0.13e-6,
    "SR7": 0.10e-6,
}

SR_EFIELD_ACTIVE = {   # active conditions (peak thunderstorm hours)
    "SR1": 3.0e-6,     # 3.0 uV/m/sqrtHz
    "SR2": 1.5e-6,
    "SR3": 1.0e-6,
    "SR4": 0.7e-6,
    "SR5": 0.5e-6,
    "SR6": 0.4e-6,
    "SR7": 0.3e-6,
}

# Background ELF noise floor (non-SR, between resonances)
# Atmospheric noise from distant lightning, geomagnetic pulsations
E_NOISE_FLOOR = 0.05e-6  # ~0.05 uV/m/sqrtHz (typical mid-latitude)

# ============================================================
# Antenna parameters
# ============================================================
H_VERT = 10.0      # Vertical element height (m)
L_TOPHAT = 15.0    # Top-hat horizontal length (m)
WIRE_DIA = 2.0e-3  # Wire diameter (m)

# Effective height of Marconi T-antenna (electrically short)
# h_eff ~ h_vertical * (1 + C_tophat/C_vertical)^0.5 * 0.5
# Simplified: h_eff ~ h_vertical / 2 for a basic monopole
# With top hat: h_eff increases by ~30-50%
H_EFF = H_VERT * 0.65   # ~6.5m (with top hat improvement)

# Antenna capacitance
C_ANT = 140e-12  # 140 pF

# ============================================================
# Receiver parameters
# ============================================================
# Input filter
R_FILT = 33e3
C_FILT = 50e-12
CAP_DIVIDER = C_ANT / (C_ANT + 2 * C_FILT)  # 0.583

# Preamp gain (ELF bandpass, 40 dB)
RF = 100e3
CF = 15e-9
RG = 1.0e3
CG = 100e-6

# Receiver noise at antenna
NOISE_AT_ANT = 64.6e-9  # nV/sqrtHz (from filter_resistor_tradeoff.py)

# ADC
ADC_SNR_DB = 111.0
ADC_FS_VPP = 5.0
ADC_SAMPLE_RATE = 192000


def preamp_gain(freq):
    """Preamp voltage gain magnitude."""
    w = 2.0 * np.pi * freq
    a = 1j * w * RF * CF
    b = 1j * w * RG * CG
    G = 1.0 + 1j * w * RF * CG / ((1.0 + a) * (1.0 + b))
    return np.abs(G)


def sr_efield_spectrum(freq, efield_dict):
    """Generate E-field PSD spectrum with Lorentzian resonance peaks."""
    psd = np.full_like(freq, E_NOISE_FLOOR)
    for mode, params in SR_MODES.items():
        f0 = params["f0"]
        Q = params["Q"]
        bw = f0 / Q  # bandwidth
        e_peak = efield_dict.get(mode, 0)
        # Lorentzian lineshape
        lorentz = (bw / 2)**2 / ((freq - f0)**2 + (bw / 2)**2)
        psd = np.maximum(psd, e_peak * lorentz + E_NOISE_FLOOR)
    return psd


def print_analysis():
    print("=" * 95)
    print("ELARA -- Expected Schumann Resonance Signal Levels")
    print("=" * 95)

    print(f"\n  Antenna: {H_VERT:.0f}m vertical + {L_TOPHAT:.0f}m top hat")
    print(f"  Effective height: h_eff = {H_EFF:.1f} m")
    print(f"  Antenna capacitance: {C_ANT*1e12:.0f} pF")
    print(f"  Cap divider loss: {CAP_DIVIDER:.3f} ({20*np.log10(CAP_DIVIDER):.1f} dB)")
    print(f"  Receiver noise at antenna: {NOISE_AT_ANT*1e9:.1f} nV/sqrtHz")

    # Signal levels for each condition
    for cond_name, efield_dict in [("QUIET (night)", SR_EFIELD_QUIET),
                                    ("TYPICAL (day)", SR_EFIELD_TYPICAL),
                                    ("ACTIVE (storms)", SR_EFIELD_ACTIVE)]:
        print(f"\n{'-'*95}")
        print(f"  Conditions: {cond_name}")
        print(f"{'-'*95}")
        print(f"  {'Mode':<6} {'f (Hz)':>8} {'Q':>5} {'BW (Hz)':>8} "
              f"{'E (uV/m/rtHz)':>15} {'V_ant (nV/rtHz)':>16} "
              f"{'V_ant_BW (uV)':>14} {'SNR (dB)':>10}")

        for mode, params in SR_MODES.items():
            f0 = params["f0"]
            Q = params["Q"]
            bw = f0 / Q
            e_field = efield_dict[mode]

            # Voltage at antenna
            v_ant_density = e_field * H_EFF  # V/sqrtHz at antenna
            v_ant_bw = v_ant_density * np.sqrt(bw)  # V RMS in resonance BW

            # SNR in the resonance bandwidth
            noise_in_bw = NOISE_AT_ANT * np.sqrt(bw)
            snr_linear = v_ant_bw / noise_in_bw
            snr_db = 20 * np.log10(snr_linear)

            print(f"  {mode:<6} {f0:>7.2f} {Q:>5.1f} {bw:>7.2f}  "
                  f"{e_field*1e6:>13.3f}  {v_ant_density*1e9:>14.1f}  "
                  f"{v_ant_bw*1e6:>12.3f}  {snr_db:>8.1f}")

    # Signal through the receiver chain
    print(f"\n{'='*95}")
    print(f"SIGNAL THROUGH RECEIVER CHAIN (typical conditions, SR1)")
    print(f"{'='*95}")

    e_sr1 = SR_EFIELD_TYPICAL["SR1"]
    f_sr1 = SR_MODES["SR1"]["f0"]
    bw_sr1 = f_sr1 / SR_MODES["SR1"]["Q"]
    v_ant = e_sr1 * H_EFF
    v_ant_bw = v_ant * np.sqrt(bw_sr1)
    G = preamp_gain(f_sr1)

    print(f"\n  E-field at SR1:           {e_sr1*1e6:.2f} uV/m/sqrtHz")
    print(f"  Antenna voltage:          {v_ant*1e6:.2f} uV/sqrtHz "
          f"(= {v_ant_bw*1e6:.2f} uV in {bw_sr1:.1f} Hz BW)")
    print(f"  After cap divider:        {v_ant*CAP_DIVIDER*1e6:.2f} uV/sqrtHz "
          f"({20*np.log10(CAP_DIVIDER):.1f} dB)")
    print(f"  After preamp (G={G:.1f}x):   {v_ant*CAP_DIVIDER*G*1e6:.2f} uV/sqrtHz "
          f"({20*np.log10(G):.1f} dB)")
    print(f"  At ADC input:             {v_ant*CAP_DIVIDER*G*1e6:.2f} uV/sqrtHz")

    # ADC dynamic range check
    v_adc_sr1 = v_ant_bw * CAP_DIVIDER * G
    v_adc_fs = ADC_FS_VPP / (2 * np.sqrt(2))
    headroom_db = 20 * np.log10(v_adc_fs / v_adc_sr1)

    print(f"\n  ADC full-scale:           {v_adc_fs*1e3:.1f} mV RMS")
    print(f"  SR1 signal at ADC:        {v_adc_sr1*1e6:.2f} uV RMS")
    print(f"  Headroom:                 {headroom_db:.0f} dB")

    # SNR summary
    print(f"\n{'='*95}")
    print(f"SNR SUMMARY (in resonance bandwidth)")
    print(f"{'='*95}")
    print(f"  {'':30s} {'Quiet':>10} {'Typical':>10} {'Active':>10}")
    for mode in ["SR1", "SR2", "SR3"]:
        params = SR_MODES[mode]
        bw = params["f0"] / params["Q"]
        snrs = []
        for efield_dict in [SR_EFIELD_QUIET, SR_EFIELD_TYPICAL, SR_EFIELD_ACTIVE]:
            v_sig = efield_dict[mode] * H_EFF * np.sqrt(bw)
            v_noise = NOISE_AT_ANT * np.sqrt(bw)
            snr = 20 * np.log10(v_sig / v_noise)
            snrs.append(snr)
        print(f"  {mode} ({params['f0']:.1f} Hz, BW={bw:.1f} Hz):"
              f"  {snrs[0]:>7.1f} dB  {snrs[1]:>7.1f} dB  {snrs[2]:>7.1f} dB")

    # Detection threshold
    print(f"\n  Minimum detectable E-field (SNR=0 dB, 1 Hz BW):")
    e_min = NOISE_AT_ANT / H_EFF
    print(f"    {e_min*1e9:.1f} nV/m/sqrtHz = {e_min*1e6:.4f} uV/m/sqrtHz")
    print(f"    (Schumann SR1 typical is {SR_EFIELD_TYPICAL['SR1']*1e6:.1f} uV/m/sqrtHz "
          f"= {SR_EFIELD_TYPICAL['SR1']/e_min:.0f}x above detection threshold)")

    # Comparison with Romero
    romero_noise = 121e-9  # nV/sqrtHz
    romero_e_min = romero_noise / H_EFF
    print(f"\n  Romero AD820 detection threshold: {romero_e_min*1e6:.4f} uV/m/sqrtHz")
    print(f"  ELARA detection threshold:        {e_min*1e6:.4f} uV/m/sqrtHz")
    print(f"  ELARA is {romero_e_min/e_min:.1f}x more sensitive")

    # Time-domain: expected sferic amplitudes
    print(f"\n{'='*95}")
    print(f"INDIVIDUAL SFERICS (lightning strokes)")
    print(f"{'='*95}")
    print(f"  Typical sferic E-field amplitudes (vertical, at ground):")
    print(f"    Nearby (<50 km):     ~1-10  V/m  -> V_ant = {10*H_EFF:.0f} V (CLIPS!)")
    print(f"    Regional (50-500 km): ~1-100 mV/m -> V_ant = {0.1*H_EFF*1e3:.0f} mV")
    print(f"    Distant (>1000 km):  ~0.01-1 mV/m -> V_ant = {0.001*H_EFF*1e6:.0f} uV")
    print(f"    Antipodal (>10000 km): ~1-10 uV/m -> V_ant = {10e-6*H_EFF*1e6:.0f} uV")
    print(f"\n  With 40 dB gain and {CAP_DIVIDER:.2f} cap divider:")
    print(f"    Max before clip: {ADC_FS_VPP/2/preamp_gain(7.83)/CAP_DIVIDER*1e3:.0f} mV at antenna")
    print(f"    -> Sferics from >~200 km are within range")
    print(f"    -> Nearby sferics will clip (acceptable — they're impulsive)")


def plot_analysis():
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available -- skipping plot")
        return

    BG = "#0d1117"
    TEXT = "#e6edf3"
    SUBTLE = "#7d8590"
    PANEL = "#161b22"
    BORDER = "#30363d"

    f = np.logspace(np.log10(1), np.log10(100), 2000)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
    fig.patch.set_facecolor(BG)

    for ax in (ax1, ax2):
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=SUBTLE, labelsize=9)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

    # Plot 1: E-field spectrum at antenna
    for cond_name, efield_dict, color, alpha in [
            ("Active (storms)", SR_EFIELD_ACTIVE, "#ff7b72", 0.6),
            ("Typical (day)", SR_EFIELD_TYPICAL, "#7ee787", 1.0),
            ("Quiet (night)", SR_EFIELD_QUIET, "#79c0ff", 0.7)]:
        e_spectrum = sr_efield_spectrum(f, efield_dict) * H_EFF * 1e9  # nV/sqrtHz
        ax1.semilogy(f, e_spectrum, color=color, linewidth=2, alpha=alpha,
                     label=f"Signal: {cond_name}")

    # Noise floor at antenna
    noise_line = NOISE_AT_ANT * 1e9 * np.ones_like(f)
    ax1.semilogy(f, noise_line, color="#d2a8ff", linewidth=2, linestyle="--",
                 label=f"ELARA noise floor ({NOISE_AT_ANT*1e9:.0f} nV/√Hz)")

    # Romero noise floor
    ax1.axhline(121, color="#7d8590", linewidth=1.5, linestyle=":",
                label="Romero AD820 noise floor (121 nV/√Hz)")

    ax1.set_ylabel("Voltage at antenna (nV/√Hz)", fontsize=11,
                   color=TEXT, fontfamily="monospace")
    ax1.set_title("ELARA — Expected Schumann Resonance Signal vs Noise Floor\n"
                  f"Antenna: {H_VERT:.0f}m vert + {L_TOPHAT:.0f}m top, "
                  f"h_eff = {H_EFF:.1f}m, C_ant = {C_ANT*1e12:.0f} pF",
                  fontsize=12, fontweight="bold", color=TEXT,
                  fontfamily="monospace", pad=10)
    legend1 = ax1.legend(loc="upper right", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend1.get_frame().set_alpha(0.9)
    ax1.set_xlim(1, 100)
    ax1.set_ylim(10, 100000)

    # SR labels
    for mode, params in SR_MODES.items():
        ax1.axvline(params["f0"], color=SUBTLE, alpha=0.3, linestyle="--", linewidth=0.8)
        ax1.text(params["f0"], 15, mode, fontsize=6, ha="center",
                 color=SUBTLE, fontfamily="monospace")

    # Plot 2: SNR in resonance bandwidth
    conditions = [
        ("Quiet", SR_EFIELD_QUIET, "#79c0ff"),
        ("Typical", SR_EFIELD_TYPICAL, "#7ee787"),
        ("Active", SR_EFIELD_ACTIVE, "#ff7b72"),
    ]

    x_pos = np.arange(len(SR_MODES))
    width = 0.25

    for i, (cond_name, efield_dict, color) in enumerate(conditions):
        snrs = []
        for mode, params in SR_MODES.items():
            bw = params["f0"] / params["Q"]
            v_sig = efield_dict[mode] * H_EFF * np.sqrt(bw)
            v_noise = NOISE_AT_ANT * np.sqrt(bw)
            snr = 20 * np.log10(v_sig / v_noise)
            snrs.append(snr)
        ax2.bar(x_pos + i * width, snrs, width, label=cond_name,
                color=color, alpha=0.8, edgecolor=BORDER)

    ax2.set_xticks(x_pos + width)
    ax2.set_xticklabels([f"{m}\n{p['f0']:.1f} Hz" for m, p in SR_MODES.items()],
                        fontsize=8, color=TEXT, fontfamily="monospace")
    ax2.set_ylabel("SNR in resonance bandwidth (dB)", fontsize=11,
                   color=TEXT, fontfamily="monospace")
    ax2.set_title("Expected SNR per Schumann Mode",
                  fontsize=12, fontweight="bold", color=TEXT,
                  fontfamily="monospace", pad=10)
    ax2.axhline(0, color="#ff7b72", linewidth=1, linestyle=":", alpha=0.5)
    ax2.axhline(10, color="#f2cc60", linewidth=1, linestyle=":", alpha=0.5,
                label="10 dB (good detection)")
    legend2 = ax2.legend(loc="upper right", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend2.get_frame().set_alpha(0.9)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "expected_signal.svg")
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    print_analysis()
    plot_analysis()
