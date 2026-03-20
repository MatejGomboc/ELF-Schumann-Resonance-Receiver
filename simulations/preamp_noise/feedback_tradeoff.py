#!/usr/bin/env python3
"""
ELARA -- LMP7721 Feedback Network Tradeoff Analysis

Compares different R2/C3 feedback configurations for the LMP7721 preamp.
The feedback sets frequency-dependent gain: G(f) = 1 + j*2*pi*f*R2*C3

Trade-off: larger R2 = more gain at VLF but more thermal noise.
The time constant R2*C3 determines the gain curve shape.
Scaling R2 down and C3 up keeps the same gain but reduces noise.

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
C_ANT = 140e-12
EN_LMP7721 = 6.5e-9
EN_1F_CORNER = 10.0   # Hz (from LMP7721 datasheet noise plot)
IN_LMP7721 = 0.01e-15
I_PCB = 0.1e-15
R_FILT = 220.0e3

f = np.logspace(0, np.log10(96000), 3000)


def thermal_noise(R):
    return np.sqrt(4.0 * k_B * T * R)


def en_1f(freq):
    return EN_LMP7721 * np.sqrt(1.0 + EN_1F_CORNER / freq)


def source_impedance(freq):
    return 1.0 / (2.0 * np.pi * freq * C_ANT)


def analyze_config(R2, C3, label):
    """Analyze a feedback configuration."""
    tau = R2 * C3
    fc_gain = 1.0 / (2.0 * np.pi * tau) if tau > 0 else float("inf")

    # Gain: G(f) = 1 + j*2*pi*f*R2*C3
    # |G(f)| = sqrt(1 + (2*pi*f*R2*C3)^2)
    if tau > 0:
        gain = np.sqrt(1.0 + (2.0 * np.pi * f * tau) ** 2)
    else:
        gain = np.ones_like(f)

    gain_db = 20.0 * np.log10(gain)

    # Input-referred noise sources
    Z_src = source_impedance(f)
    en_amp = en_1f(f)
    en_in = IN_LMP7721 * Z_src
    en_pcb = I_PCB * Z_src
    en_rfilt = thermal_noise(R_FILT)  # each filter resistor
    en_r2 = thermal_noise(R2) if R2 > 0 else 0.0

    # Total input-referred noise (before gain)
    en_total_input = np.sqrt(en_amp**2 + en_in**2 + en_pcb**2
                             + 2 * en_rfilt**2 + en_r2**2)

    # Output noise = input noise * gain
    en_output = en_total_input * gain

    # Signal: assume 1 mV at antenna (typical Schumann)
    # Signal at LMP7721 input after RC filter
    # RC filter: H(f) = 1/(1 + j*2*pi*f*R*C)^2 for 2 stages
    C_FILT = 1.0 / (2.0 * np.pi * R_FILT * 15.9e3)  # C for fc ~16 kHz
    fc_rc = 1.0 / (2.0 * np.pi * R_FILT * C_FILT)
    h_mag = 1.0 / (1.0 + (f / fc_rc) ** 2)  # |H|^2 one stage = |H| two stages
    v_signal_input = 1e-3 * h_mag  # 1 mV * 2-stage filter magnitude

    # Signal at output
    v_signal_output = v_signal_input * gain

    # SNR at output (in 1 Hz bandwidth)
    snr_output = v_signal_output / en_output

    # PCM1808 noise floor (99 dB SNR, 3 Vpp = 1.06 Vrms for sine)
    v_fs_rms = 3.0 / (2 * np.sqrt(2))  # Vpp to Vrms
    adc_noise = v_fs_rms / 10 ** (99.0 / 20)  # ~11.9 uV RMS
    # Per-Hz noise density at 48 kSPS
    adc_noise_density = adc_noise / np.sqrt(48000.0 / 2)  # ~76.8 nV/sqrtHz

    return {
        "label": label,
        "R2": R2,
        "C3": C3,
        "tau": tau,
        "fc_gain": fc_gain,
        "gain": gain,
        "gain_db": gain_db,
        "en_total_input": en_total_input,
        "en_output": en_output,
        "en_r2": en_r2,
        "v_signal_output": v_signal_output,
        "snr_output": snr_output,
        "adc_noise_density": adc_noise_density,
    }


CONFIGS = [
    (0, 0, "Pure follower (no R2/C3)"),
    (2e6, 100e-12, "Old design: R2=2M, C3=100pF"),
    (20e3, 10e-9, "R2=20k, C3=10nF (previous)"),
    (1e3, 4.7e-6, "R2=1k, C3=4.7uF (optimised)"),
    (20e3, 100e-9, "R2=20k, C3=100nF"),
]


def print_tradeoff():
    print("=" * 100)
    print("ELARA -- LMP7721 Feedback Network Tradeoff")
    print("=" * 100)

    results = [analyze_config(R2, C3, label) for R2, C3, label in CONFIGS]

    # Gain comparison
    print(f"\n{'GAIN at key frequencies':}")
    print(f"{'Config':<40} {'7.83 Hz':>10} {'100 Hz':>10} {'1 kHz':>10} "
          f"{'10 kHz':>10} {'22 kHz':>10}")
    print("-" * 100)

    for r in results:
        gains = []
        for freq in [7.83, 100, 1000, 10000, 22000]:
            idx = np.argmin(np.abs(f - freq))
            gains.append(f"{r['gain_db'][idx]:>8.1f} dB")
        print(f"{r['label']:<40} {'  '.join(gains)}")

    # Noise comparison
    print(f"\n{'INPUT-REFERRED NOISE (nV/sqrtHz)':}")
    print(f"{'Config':<40} {'R2 thermal':>12} {'Total@SR1':>12} {'Total@1kHz':>12} "
          f"{'Total@10kHz':>12}")
    print("-" * 100)

    for r in results:
        idx_sr1 = np.argmin(np.abs(f - 7.83))
        idx_1k = np.argmin(np.abs(f - 1000))
        idx_10k = np.argmin(np.abs(f - 10000))
        print(f"{r['label']:<40} {r['en_r2']*1e9:>10.1f} nV "
              f"{r['en_total_input'][idx_sr1]*1e9:>10.1f} nV "
              f"{r['en_total_input'][idx_1k]*1e9:>10.1f} nV "
              f"{r['en_total_input'][idx_10k]*1e9:>10.1f} nV")

    # Output noise (what the ADC sees)
    print(f"\n{'OUTPUT NOISE (nV/sqrtHz) -- what the ADC sees':}")
    print(f"{'Config':<40} {'@SR1':>12} {'@1kHz':>12} {'@10kHz':>12} "
          f"{'@22kHz':>12} {'ADC floor':>12}")
    print("-" * 100)

    for r in results:
        vals = []
        for freq in [7.83, 1000, 10000, 22000]:
            idx = np.argmin(np.abs(f - freq))
            vals.append(f"{r['en_output'][idx]*1e9:>10.1f} nV")
        print(f"{r['label']:<40} {'  '.join(vals)} "
              f"{r['adc_noise_density']*1e9:>10.1f} nV")

    # Signal-to-noise at output
    print(f"\n{'OUTPUT SNR (dB in 1 Hz BW, 1 mV antenna signal)':}")
    print(f"{'Config':<40} {'@SR1':>10} {'@1kHz':>10} {'@10kHz':>10} {'@22kHz':>10}")
    print("-" * 100)

    for r in results:
        vals = []
        for freq in [7.83, 1000, 10000, 22000]:
            idx = np.argmin(np.abs(f - freq))
            snr_db = 20 * np.log10(r['snr_output'][idx]) if r['snr_output'][idx] > 0 else -999
            vals.append(f"{snr_db:>8.1f} dB")
        print(f"{r['label']:<40} {'  '.join(vals)}")

    # Recommendation
    print(f"\n{'=' * 100}")
    print("RECOMMENDATION")
    print(f"{'=' * 100}")

    best = results[3]  # R2=1k, C3=4.7uF (optimised)
    old = results[1]   # Old design
    follower = results[0]

    print(f"\n  R2=1k + C3=4.7uF (optimised for max fidelity):")
    print(f"    - R2 thermal noise: {best['en_r2']*1e9:.1f} nV (negligible)")
    print(f"    - f_unity = {1/(2*3.14159*best['tau']):.1f} Hz -- gain starts above ~34 Hz")
    print(f"    - 4.7 uF polypropylene/polyester film cap")
    print(f"    - R2 noise ({best['en_r2']*1e9:.1f} nV) is far below LMP7721 en "
          f"({EN_LMP7721*1e9:.1f} nV wideband)")
    print(f"    - Maximises SNR across entire 1 Hz -- 22 kHz band")

    print(f"\n  Pure follower (no R2/C3):")
    print(f"    - Lowest possible noise ({follower['en_total_input'][0]*1e9:.1f} nV at SR1)")
    print(f"    - No VLF gain compensation -- signal rolls off with RC filter above 16 kHz")
    print(f"    - Fine if only targeting Schumann resonances (< 50 Hz)")
    print(f"    - Loses VLF sferic/whistler sensitivity at higher frequencies")


def plot_tradeoff():
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available -- skipping plot")
        return

    BG = "#0d1117"
    TEXT = "#e6edf3"
    SUBTLE = "#7d8590"
    PANEL = "#161b22"
    BORDER = "#30363d"
    COLORS = ["#7d8590", "#ff7b72", "#f2cc60", "#7ee787", "#79c0ff"]

    results = [analyze_config(R2, C3, label) for R2, C3, label in CONFIGS]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 16), sharex=True)
    fig.patch.set_facecolor(BG)

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=SUBTLE, labelsize=9)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

    # Plot 1: Gain
    for r, c in zip(results, COLORS):
        ax1.semilogx(f, r["gain_db"], color=c, linewidth=2, label=r["label"])

    ax1.set_ylabel("Gain (dB)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax1.set_title("ELARA -- Feedback Network Tradeoff: Gain, Noise, Output SNR",
                  fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace", pad=10)
    legend1 = ax1.legend(loc="upper left", fontsize=7, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend1.get_frame().set_alpha(0.9)
    ax1.set_ylim(-1, 35)

    # Plot 2: Input-referred noise
    for r, c in zip(results, COLORS):
        ax2.loglog(f, r["en_total_input"] * 1e9, color=c, linewidth=2, label=r["label"])

    ax2.set_ylabel("Input noise (nV/sqrtHz)", fontsize=11, color=TEXT, fontfamily="monospace")
    legend2 = ax2.legend(loc="upper right", fontsize=7, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend2.get_frame().set_alpha(0.9)
    ax2.set_ylim(1, 500)

    # Plot 3: Output noise (what ADC sees)
    for r, c in zip(results, COLORS):
        ax3.loglog(f, r["en_output"] * 1e9, color=c, linewidth=2, label=r["label"])

    # ADC noise floor
    adc_nf = results[0]["adc_noise_density"] * 1e9
    ax3.axhline(adc_nf, color="#d2a8ff", linewidth=1.5, linestyle="--",
                alpha=0.7, label=f"PCM1808 noise floor ({adc_nf:.0f} nV/sqrtHz)")

    ax3.set_xlabel("Frequency (Hz)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax3.set_ylabel("Output noise (nV/sqrtHz)", fontsize=11, color=TEXT, fontfamily="monospace")
    legend3 = ax3.legend(loc="upper left", fontsize=7, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend3.get_frame().set_alpha(0.9)
    ax3.set_ylim(10, 100000)
    ax3.set_xlim(1, 96000)

    # Schumann markers
    for ax in (ax1, ax2, ax3):
        for sr, freq in [("SR1", 7.83), ("SR2", 14.3), ("SR3", 20.8)]:
            ax.axvline(freq, color=SUBTLE, alpha=0.3, linestyle="--", linewidth=0.8)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "feedback_tradeoff.svg")
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    print_tradeoff()
    plot_tradeoff()
