#!/usr/bin/env python3
"""
ELARA -- LMP7721 Feedback Network Analysis (ELF-optimised)

Models the bandpass gain topology:
    Rf (100k) + Cf (15nF) in parallel: IN- to VOUT (feedback)
    Rg (1k) + Cg (100uF) in series:   IN- to BIAS_MID (ground ref)

Transfer function:
    G(f) = 1 + Zf/Zg
    where Zf = Rf / (1 + jwRfCf)
          Zg = Rg + 1/(jwCg) = (1 + jwRgCg) / (jwCg)

    G(f) = 1 + jwRfCg / ((1 + jwRfCf)(1 + jwRgCg))

Gain profile:
    DC:           0 dB  (Cg blocks DC)
    ~1.6-117 Hz: 20 dB  (flat across Schumann band)
    Above 117 Hz: rolls off -20 dB/dec (Cf shorts Rf)

Also models output coupling (C_out) and AA filter (R_AA + C_AA).

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

# ===========================================================================
# New ELF-optimised design
# ===========================================================================
RF = 100e3        # Feedback resistor (IN- to VOUT)
CF = 15e-9        # Feedback cap (across Rf) — C0G/NP0
RG = 1.0e3        # Ground-reference resistor (IN- to BIAS_MID)
CG = 100e-6       # DC blocking cap (in series with Rg) — polypropylene film
C_OUT = 10e-6     # Output coupling cap — film
R_AA = 10e3       # Anti-aliasing filter resistor
C_AA = 100e-9     # Anti-aliasing filter cap — C0G/NP0

# Input filter
R_FILT = 33e3     # Two 33k filter resistors (optimised for noise vs AM rejection)
C_FILT = 50e-12   # Two 50 pF air-gap caps (100 pF total)

# Antenna
C_ANT = 140e-12   # Antenna capacitance

# LMP7721 specs
EN_LMP7721 = 6.5e-9
EN_1F_CORNER = 10.0
IN_LMP7721 = 0.01e-15
I_PCB = 0.1e-15

# PCM1804 specs
ADC_FS_VPP = 5.0       # ±2.5V differential input
ADC_SNR_DB = 111.0     # 111 dB SNR (A-weighted)
ADC_SAMPLE_RATE = 192000  # 192 kHz quad-rate

# Schumann resonances
SCHUMANN = {"SR1": 7.83, "SR2": 14.3, "SR3": 20.8, "SR4": 27.3,
            "SR5": 33.8, "SR6": 39.0, "SR7": 45.0}

f = np.logspace(-1, np.log10(ADC_SAMPLE_RATE / 2), 4000)  # 0.1 Hz to Nyquist


def thermal_noise(R):
    return np.sqrt(4.0 * k_B * T * R)


def en_1f(freq):
    return EN_LMP7721 * np.sqrt(1.0 + EN_1F_CORNER / freq)


def source_impedance(freq):
    return 1.0 / (2.0 * np.pi * freq * C_ANT)


def preamp_gain(freq):
    """Preamp voltage gain G(f) with bandpass topology."""
    w = 2.0 * np.pi * freq
    # Zf = Rf / (1 + jwRfCf)
    # Zg = (1 + jwRgCg) / (jwCg)
    # G = 1 + Zf/Zg = 1 + jwRfCg / ((1+jwRfCf)(1+jwRgCg))
    a = 1j * w * RF * CF  # high-freq parameter
    b = 1j * w * RG * CG  # low-freq parameter
    G = 1.0 + 1j * w * RF * CG / ((1.0 + a) * (1.0 + b))
    return G


def output_coupling(freq):
    """High-pass from C_out + R_AA."""
    w = 2.0 * np.pi * freq
    # C_out in series with R_AA forms HP: H = jwC_out*R_AA / (1 + jwC_out*R_AA)
    s = 1j * w * C_OUT * R_AA
    return s / (1.0 + s)


def aa_filter(freq):
    """Low-pass from R_AA + C_AA."""
    w = 2.0 * np.pi * freq
    return 1.0 / (1.0 + 1j * w * R_AA * C_AA)


def input_filter(freq):
    """2-stage RC low-pass input filter."""
    w = 2.0 * np.pi * freq
    fc = 1.0 / (2.0 * np.pi * R_FILT * C_FILT)
    H_one = 1.0 / (1.0 + 1j * w * R_FILT * C_FILT)
    return H_one ** 2  # 2 stages


def cap_divider_loss():
    """Signal loss from capacitive voltage divider (frequency-independent at ELF)."""
    return C_ANT / (C_ANT + 2 * C_FILT)


def system_transfer(freq):
    """Complete system transfer function: antenna to ADC input."""
    H_div = cap_divider_loss()
    H_filt = input_filter(freq)
    G_preamp = preamp_gain(freq)
    H_cout = output_coupling(freq)
    H_aa = aa_filter(freq)
    return H_div * H_filt * G_preamp * H_cout * H_aa


def print_analysis():
    print("=" * 100)
    print("ELARA -- ELF Preamp Gain & Noise Analysis (Bandpass Topology)")
    print("=" * 100)

    # Component values
    f_low = 1.0 / (2.0 * np.pi * RG * CG)
    f_high = 1.0 / (2.0 * np.pi * RF * CF)
    G_mid = 1.0 + RF / RG
    f_hp_out = 1.0 / (2.0 * np.pi * C_OUT * R_AA)
    f_lp_aa = 1.0 / (2.0 * np.pi * R_AA * C_AA)

    print(f"\n  Feedback: Rf={RF/1e3:.1f}k, Cf={CF*1e9:.0f}nF, Rg={RG/1e3:.1f}k, Cg={CG*1e6:.0f}uF")
    print(f"  Midband gain: {G_mid:.1f} ({20*np.log10(G_mid):.1f} dB)")
    print(f"  Low corner (Cg): f_low = {f_low:.2f} Hz")
    print(f"  High corner (Cf): f_high = {f_high:.1f} Hz")
    print(f"  Output HP (C_out+R_AA): f_hp = {f_hp_out:.2f} Hz")
    print(f"  AA LP (R_AA+C_AA): f_lp = {f_lp_aa:.1f} Hz")

    # Gain at Schumann frequencies
    print(f"\n{'PREAMP GAIN at Schumann resonances':}")
    print(f"  {'Freq':>8}  {'|G| (dB)':>10}  {'|G| (lin)':>10}")
    print(f"  {'-'*35}")
    for name, freq in SCHUMANN.items():
        G = preamp_gain(np.array([freq]))
        G_mag = np.abs(G[0])
        G_db = 20.0 * np.log10(G_mag)
        print(f"  {freq:>6.2f} Hz  {G_db:>8.2f} dB  {G_mag:>8.2f}x   {name}")

    # System transfer at key frequencies
    print(f"\n{'SYSTEM TRANSFER (antenna to ADC) at key frequencies':}")
    print(f"  {'Freq':>8}  {'Preamp':>10}  {'Input filt':>10}  {'Cap div':>10}  "
          f"{'Out+AA':>10}  {'TOTAL':>10}")
    print(f"  {'-'*65}")
    for freq_val in [1.0, 7.83, 14.3, 45.0, 100.0, 1000.0, 10000.0]:
        fv = np.array([freq_val])
        g_pre = np.abs(preamp_gain(fv)[0])
        h_filt = np.abs(input_filter(fv)[0])
        h_div = cap_divider_loss()
        h_out = np.abs(output_coupling(fv)[0]) * np.abs(aa_filter(fv)[0])
        h_total = np.abs(system_transfer(fv)[0])
        print(f"  {freq_val:>7.1f}Hz  {20*np.log10(g_pre):>8.1f}dB  "
              f"{20*np.log10(h_filt):>8.1f}dB  {20*np.log10(h_div):>8.1f}dB  "
              f"{20*np.log10(h_out):>8.1f}dB  {20*np.log10(h_total):>8.1f}dB")

    # Noise analysis
    print(f"\n{'NOISE BUDGET (input-referred, nV/sqrtHz)':}")
    print(f"  {'Freq':>8}  {'en(1/f)':>8}  {'in*Z':>8}  {'PCB':>8}  "
          f"{'Rf':>8}  {'Rg':>8}  {'R_filt':>8}  {'TOTAL':>8}")
    print(f"  {'-'*70}")

    for freq_val in [7.83, 14.3, 45.0, 100.0]:
        fv = np.array([freq_val])
        Z = source_impedance(fv)[0]
        e_v = en_1f(fv)[0]
        e_i = IN_LMP7721 * Z
        e_pcb = I_PCB * Z
        e_rf = thermal_noise(RF)
        e_rg = thermal_noise(RG)
        e_rfilt = thermal_noise(R_FILT)
        # Rf and Rg noise referred to input: divide by gain
        G_mag = np.abs(preamp_gain(fv)[0])
        e_rf_inp = e_rf / G_mag  # Rf noise at output, referred back to input
        e_rg_inp = e_rg  # Rg noise appears at IN-, same as input
        e_total = np.sqrt(e_v**2 + e_i**2 + e_pcb**2 + e_rf_inp**2
                          + e_rg_inp**2 + 2 * e_rfilt**2)
        print(f"  {freq_val:>6.1f}Hz  {e_v*1e9:>7.2f}  {e_i*1e9:>7.2f}  {e_pcb*1e9:>7.2f}  "
              f"{e_rf_inp*1e9:>7.2f}  {e_rg_inp*1e9:>7.2f}  {e_rfilt*1e9:>7.2f}  {e_total*1e9:>7.2f}")

    # Output noise and ADC comparison
    v_fs_rms = ADC_FS_VPP / (2 * np.sqrt(2))
    adc_noise_density = v_fs_rms / 10**(ADC_SNR_DB / 20) / np.sqrt(ADC_SAMPLE_RATE / 2)

    print(f"\n  PCM1804 noise floor: {adc_noise_density*1e9:.1f} nV/sqrtHz "
          f"(at {ADC_SAMPLE_RATE} SPS, {ADC_SNR_DB} dB SNR)")

    # Signal levels
    print(f"\n{'SIGNAL LEVELS (1 mV at antenna, typical Schumann)':}")
    for name, freq in list(SCHUMANN.items())[:3]:
        fv = np.array([freq])
        H = np.abs(system_transfer(fv)[0])
        v_out = 1e-3 * H  # 1 mV at antenna
        print(f"  {name} ({freq:.2f} Hz): V_out = {v_out*1e6:.1f} uV "
              f"(system gain = {20*np.log10(H):.1f} dB)")

    headroom = ADC_FS_VPP / 2 / (np.abs(preamp_gain(np.array([7.83]))[0]))
    print(f"\n  Max input before clipping (at SR1): {headroom*1e3:.1f} mV peak")
    print(f"  Schumann signals are ~0.1-1 mV -> plenty of headroom")


def plot_analysis():
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available -- skipping plot")
        return

    BG = "#0d1117"
    TEXT = "#e6edf3"
    SUBTLE = "#7d8590"
    PANEL = "#161b22"
    BORDER = "#30363d"

    fig, axes = plt.subplots(3, 1, figsize=(14, 16), sharex=True)
    fig.patch.set_facecolor(BG)

    for ax in axes:
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=SUBTLE, labelsize=9)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

    # ===== Plot 1: Gain curves =====
    ax1 = axes[0]
    G_preamp = np.abs(preamp_gain(f))
    H_system = np.abs(system_transfer(f))
    H_filt = np.abs(input_filter(f))

    ax1.semilogx(f, 20 * np.log10(G_preamp), color="#7ee787", linewidth=2.5,
                 label="Preamp gain G(f)")
    ax1.semilogx(f, 20 * np.log10(H_system), color="#79c0ff", linewidth=2,
                 label="System transfer (ant to ADC)")
    ax1.semilogx(f, 20 * np.log10(H_filt * cap_divider_loss()),
                 color="#ff7b72", linewidth=1.5, linestyle="--",
                 label="Input filter + cap divider")

    ax1.set_ylabel("Gain (dB)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax1.set_title("ELARA -- ELF Bandpass Gain Analysis\n"
                  f"Rf={RF/1e3:.1f}k, Cf={CF*1e9:.0f}nF, Rg={RG/1e3:.1f}k, "
                  f"Cg={CG*1e6:.0f}uF | DC=0dB, ELF=20dB",
                  fontsize=12, fontweight="bold", color=TEXT,
                  fontfamily="monospace", pad=10)
    ax1.set_ylim(-40, 25)
    legend1 = ax1.legend(loc="upper right", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend1.get_frame().set_alpha(0.9)

    # ===== Plot 2: Noise =====
    ax2 = axes[1]
    Z_src = source_impedance(f)
    e_amp = en_1f(f)
    e_current = IN_LMP7721 * Z_src
    e_pcb = I_PCB * Z_src
    e_rfilt = thermal_noise(R_FILT) * np.ones_like(f)
    e_rg = thermal_noise(RG) * np.ones_like(f)
    e_total_input = np.sqrt(e_amp**2 + e_current**2 + e_pcb**2
                            + 2 * e_rfilt**2 + e_rg**2)

    ax2.loglog(f, e_amp * 1e9, color="#7ee787", linewidth=1.5, linestyle="--",
               label="LMP7721 en (+ 1/f)")
    ax2.loglog(f, e_pcb * 1e9, color="#d2a8ff", linewidth=1.5, linestyle=":",
               label="PCB leakage (0.1 fA, guarded)")
    ax2.loglog(f, e_rfilt * 1e9, color="#ff7b72", linewidth=1.5, linestyle="-.",
               label="R_filt (220k) thermal")
    ax2.loglog(f, e_total_input * 1e9, color="#7ee787", linewidth=2.5,
               label="TOTAL input-referred")

    ax2.set_ylabel("Noise (nV/sqrtHz)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax2.set_ylim(1, 500)
    legend2 = ax2.legend(loc="upper right", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend2.get_frame().set_alpha(0.9)

    # ===== Plot 3: Output noise vs ADC floor =====
    ax3 = axes[2]
    e_output = e_total_input * G_preamp
    v_fs_rms = ADC_FS_VPP / (2 * np.sqrt(2))
    adc_nf = v_fs_rms / 10**(ADC_SNR_DB / 20) / np.sqrt(ADC_SAMPLE_RATE / 2)

    ax3.loglog(f, e_output * 1e9, color="#7ee787", linewidth=2.5,
               label="Output noise (preamp)")
    ax3.axhline(adc_nf * 1e9, color="#d2a8ff", linewidth=1.5, linestyle="--",
                alpha=0.7, label=f"PCM1804 floor ({adc_nf*1e9:.0f} nV/sqrtHz)")

    ax3.set_xlabel("Frequency (Hz)", fontsize=11, color=TEXT, fontfamily="monospace")
    ax3.set_ylabel("Output noise (nV/sqrtHz)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    ax3.set_ylim(1, 10000)
    ax3.set_xlim(0.1, ADC_SAMPLE_RATE / 2)
    legend3 = ax3.legend(loc="upper left", fontsize=8, facecolor=PANEL,
                         edgecolor=BORDER, labelcolor=TEXT)
    legend3.get_frame().set_alpha(0.9)

    # Schumann markers on all axes
    for ax in axes:
        for sr, freq in SCHUMANN.items():
            ax.axvline(freq, color=SUBTLE, alpha=0.3, linestyle="--", linewidth=0.8)
        # ELF band shading
        ax.axvspan(3, 50, alpha=0.05, color="#7ee787")

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "feedback_tradeoff.svg")
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    print_analysis()
    plot_analysis()
