#!/usr/bin/env python3
"""
ELARA — 2-Stage RC Low-Pass Filter Cascade Simulation

Simulates the frequency response of the input RF rejection filter
described in PLAN.md §3.0:

    antenna ── R1 ── node1 ── R2 ── node2 ── LMP7721 IN+
                       |                |
                     C_pcb1           C_pcb2
                       |                |
                      GND              GND

Transfer function (2 identical RC stages, no interaction due to
high source impedance between stages):

    H(s) = [1 / (1 + s·R·C)]²

    |H(jw)|   = 1 / (1 + (w·R·C)²)         per stage
    phi(jw)     = -arctan(w·R·C)              per stage
    |H_total| = |H|²                         (squared for 2 stages)
    phi_total   = 2·phi                          (doubled for 2 stages)

The filter uses air-gap plate capacitors (see simulations/plate_capacitor)
and 33 kohm thin-film resistors, air-mounted outside the ALU shield.

Usage:
    python rc_filter_cascade.py                     # default: 33kohm, 50pF
    python rc_filter_cascade.py --resistance 33e3 --capacitance 50e-12
    python rc_filter_cascade.py --resistance 1e6 --capacitance 10e-12  # old design

Author: Matej + Claude, March 2026
"""

import argparse
import math

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ============================================================================
# Transfer function
# ============================================================================
def transfer_function(f, r, c, stages=2):
    """
    Complex transfer function of N cascaded identical RC low-pass stages.

    H(jw) = [1 / (1 + jw·R·C)]^N

    Args:
        f:      frequency array (Hz)
        r:      resistance (ohm)
        c:      capacitance (F)
        stages: number of cascaded stages

    Returns:
        Complex transfer function H(jw)
    """
    omega = 2.0 * np.pi * f
    h_single = 1.0 / (1.0 + 1j * omega * r * c)
    return h_single ** stages


def magnitude_db(h):
    """Magnitude in dB."""
    return 20.0 * np.log10(np.abs(h))


def phase_deg(h):
    """Phase in degrees."""
    return np.degrees(np.angle(h))


def group_delay_us(f, h):
    """
    Group delay in microseconds.

    tau_g = -dphi/dw ≈ -Δphi/Δw
    """
    phi = np.unwrap(np.angle(h))
    omega = 2.0 * np.pi * f
    dphi = np.gradient(phi, omega)
    return -dphi * 1e6


def fc_single(r, c):
    """Single-stage -3 dB cutoff frequency (Hz)."""
    return 1.0 / (2.0 * np.pi * r * c)


def fc_cascade(r, c, stages=2):
    """N-stage cascade -3 dB cutoff frequency (Hz)."""
    return fc_single(r, c) * math.sqrt(2 ** (1.0 / stages) - 1)


# ============================================================================
# Key frequencies
# ============================================================================
MARKERS = [
    (7.83,   "SR1 (7.83 Hz)"),
    (14.3,   "SR2 (14.3 Hz)"),
    (20.8,   "SR3 (20.8 Hz)"),
    (1e3,    "1 kHz"),
    (10e3,   "10 kHz"),
    (22e3,   "22 kHz (VLF top)"),
    (1e6,    "1 MHz (MF AM)"),
    (100e6,  "100 MHz (FM)"),
    (900e6,  "900 MHz (GSM)"),
]


# ============================================================================
# Text output
# ============================================================================
def print_table(r, c, stages=2):
    """Print frequency response at key frequencies."""
    fc1 = fc_single(r, c)
    fcN = fc_cascade(r, c, stages)

    print("=" * 80)
    print("ELARA — 2-Stage RC Low-Pass Filter Cascade")
    print("=" * 80)
    print(f"  R = {r / 1e3:.0f} kohm")
    print(f"  C = {c * 1e12:.2f} pF")
    print(f"  Stages = {stages}")
    print(f"  fc (single stage) = {fc1:.2f} Hz ({fc1 / 1e3:.2f} kHz)")
    print(f"  fc ({stages}-stage cascade) = {fcN:.2f} Hz ({fcN / 1e3:.2f} kHz)")
    print()
    print(f"  {'Frequency':<22}  {'Magnitude':>12}  {'Phase':>10}  {'Notes'}")
    print(f"  {'-' * 22}  {'-' * 12}  {'-' * 10}  {'-' * 20}")

    for freq, desc in MARKERS:
        h = transfer_function(np.array([freq]), r, c, stages)
        mag = magnitude_db(h)[0]
        phi = phase_deg(h)[0]
        freq_str = format_freq(freq)
        print(f"  {freq_str:<22}  {mag:>10.2f} dB  {phi:>8.1f}°  {desc}")

    print()

    # Passband flatness
    print("  Passband flatness (Schumann band, 1-50 Hz):")
    f_pb = np.array([1, 7.83, 14.3, 20.8, 33.0, 50.0])
    h_pb = transfer_function(f_pb, r, c, stages)
    for freq, h_val in zip(f_pb, h_pb):
        mag = magnitude_db(np.array([h_val]))[0]
        print(f"    {freq:>6.1f} Hz: {mag:>10.6f} dB")

    print()


def format_freq(f):
    """Format frequency with appropriate unit."""
    if f < 1e3:
        return f"{f:.2f} Hz"
    elif f < 1e6:
        return f"{f / 1e3:.1f} kHz"
    elif f < 1e9:
        return f"{f / 1e6:.0f} MHz"
    else:
        return f"{f / 1e9:.1f} GHz"


# ============================================================================
# Plot
# ============================================================================
def plot_response(r, c, stages=2):
    """Generate Bode plot of the filter cascade."""
    if not HAS_MATPLOTLIB:
        print("matplotlib not available — skipping plot")
        return

    BG_COLOR = "#0d1117"
    TEXT_COLOR = "#e6edf3"
    SUBTLE_COLOR = "#7d8590"
    PANEL_COLOR = "#161b22"
    BORDER_COLOR = "#30363d"
    SIGNAL_COLOR = "#7ee787"
    PHASE_COLOR = "#79c0ff"
    DELAY_COLOR = "#d2a8ff"

    # Frequency range: 1 Hz to 1 GHz
    f = np.logspace(0, 9, 10000)
    h = transfer_function(f, r, c, stages)
    mag = magnitude_db(h)
    phi = phase_deg(h)
    tau = group_delay_us(f, h)

    fc1 = fc_single(r, c)
    fcN = fc_cascade(r, c, stages)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    fig.patch.set_facecolor(BG_COLOR)

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor(PANEL_COLOR)
        ax.tick_params(colors=SUBTLE_COLOR, labelsize=9)
        ax.grid(True, which="both", alpha=0.12, color=SUBTLE_COLOR)
        for spine in ax.spines.values():
            spine.set_color(BORDER_COLOR)

    # ---- Magnitude ----
    ax1.semilogx(f, mag, color=SIGNAL_COLOR, linewidth=1.5)
    ax1.axvline(fc1, color="#f2cc60", linewidth=1, linestyle="--", alpha=0.6)
    ax1.axvline(fcN, color="#ff7b72", linewidth=1, linestyle="--", alpha=0.6)
    ax1.set_ylabel("Magnitude (dB)", fontsize=10, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax1.set_ylim(-200, 5)
    ax1.set_title(
        f"ELARA — {stages}-Stage RC Filter Cascade  "
        f"(R = {r / 1e3:.0f} kohm,  C = {c * 1e12:.1f} pF,  "
        f"fc = {fcN / 1e3:.1f} kHz)",
        fontsize=12, fontweight="bold", color=TEXT_COLOR,
        fontfamily="monospace", pad=15,
    )

    # Mark key frequencies on magnitude plot
    marker_freqs = [7.83, 22e3, 1e6, 100e6]
    marker_labels = ["SR1", "VLF top", "MF AM", "FM"]
    marker_colors = ["#7ee787", "#f2cc60", "#79c0ff", "#ff7b72"]
    for mf, ml, mc in zip(marker_freqs, marker_labels, marker_colors):
        h_m = transfer_function(np.array([mf]), r, c, stages)
        m_db = magnitude_db(h_m)[0]
        ax1.plot(mf, m_db, "o", color=mc, markersize=5, zorder=5)
        y_off = 8 if m_db > -150 else -12
        ax1.annotate(f"{ml}\n{m_db:.1f} dB", xy=(mf, m_db),
                     fontsize=7, color=mc, fontfamily="monospace",
                     ha="center", va="bottom" if y_off > 0 else "top",
                     xytext=(0, y_off), textcoords="offset points")

    # fc labels
    ax1.annotate(f"fc single = {fc1 / 1e3:.1f} kHz", xy=(fc1, -3),
                 fontsize=7, color="#f2cc60", fontfamily="monospace",
                 ha="left", va="bottom", xytext=(5, 5),
                 textcoords="offset points")
    ax1.annotate(f"fc cascade = {fcN / 1e3:.1f} kHz", xy=(fcN, -3),
                 fontsize=7, color="#ff7b72", fontfamily="monospace",
                 ha="left", va="top", xytext=(5, -10),
                 textcoords="offset points")

    # Slope annotation
    ax1.annotate("-40 dB/decade", xy=(1e7, -105), fontsize=8,
                 color=SUBTLE_COLOR, fontfamily="monospace",
                 ha="center", style="italic")

    legend1 = ax1.legend(
        [f"fc single = {fc1 / 1e3:.1f} kHz",
         f"fc cascade = {fcN / 1e3:.1f} kHz"],
        loc="lower left", fontsize=7, facecolor=PANEL_COLOR,
        edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR,
    )
    legend1.get_frame().set_alpha(0.9)

    # ---- Phase ----
    ax2.semilogx(f, phi, color=PHASE_COLOR, linewidth=1.5)
    ax2.axvline(fcN, color="#ff7b72", linewidth=1, linestyle="--", alpha=0.6)
    ax2.set_ylabel("Phase (degrees)", fontsize=10, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax2.set_ylim(-185, 5)
    ax2.axhline(-90, color=SUBTLE_COLOR, linewidth=0.5, linestyle=":",
                alpha=0.4)
    ax2.axhline(-180, color=SUBTLE_COLOR, linewidth=0.5, linestyle=":",
                alpha=0.4)

    # ---- Group delay ----
    ax3.semilogx(f, tau, color=DELAY_COLOR, linewidth=1.5)
    ax3.axvline(fcN, color="#ff7b72", linewidth=1, linestyle="--", alpha=0.6)
    ax3.set_ylabel("Group delay (us)", fontsize=10, color=TEXT_COLOR,
                   fontfamily="monospace")
    ax3.set_xlabel("Frequency (Hz)", fontsize=10, color=TEXT_COLOR,
                   fontfamily="monospace")
    # Limit group delay y-axis to something readable
    # Analytical group delay at DC: tau_g = N * R * C
    tau_dc = stages * r * c * 1e6  # in us
    ax3.set_ylim(0, tau_dc * 1.2)

    # Frequency band shading
    for ax in (ax1, ax2, ax3):
        ax.axvspan(1, 300, alpha=0.04, color="#7ee787", zorder=0)      # ELF
        ax.axvspan(3e3, 30e3, alpha=0.04, color="#f2cc60", zorder=0)    # VLF
        ax.axvspan(300e3, 3e6, alpha=0.04, color="#79c0ff", zorder=0)   # MF
        ax.axvspan(88e6, 108e6, alpha=0.04, color="#ff7b72", zorder=0)  # FM

    # Band labels on top plot
    ax1.text(30, 2, "ELF", fontsize=7, color="#7ee787", fontfamily="monospace",
             alpha=0.6)
    ax1.text(8e3, 2, "VLF", fontsize=7, color="#f2cc60", fontfamily="monospace",
             alpha=0.6)
    ax1.text(800e3, 2, "MF", fontsize=7, color="#79c0ff", fontfamily="monospace",
             alpha=0.6)
    ax1.text(95e6, 2, "FM", fontsize=7, color="#ff7b72", fontfamily="monospace",
             alpha=0.6)

    plt.tight_layout()
    out_path = __file__.replace(".py", ".svg")
    fig.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Plot saved: {out_path}")


# ============================================================================
# Comparison: different capacitance values
# ============================================================================
def plot_comparison(r, stages=2):
    """Compare filter response for different capacitance values."""
    if not HAS_MATPLOTLIB:
        return

    BG_COLOR = "#0d1117"
    TEXT_COLOR = "#e6edf3"
    SUBTLE_COLOR = "#7d8590"
    PANEL_COLOR = "#161b22"
    BORDER_COLOR = "#30363d"
    COLORS = ["#ff7b72", "#f2cc60", "#7ee787", "#79c0ff", "#d2a8ff"]

    caps_pf = [5, 8, 10, 15, 20]
    f = np.logspace(0, 9, 10000)

    fig, ax = plt.subplots(1, 1, figsize=(14, 6))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(PANEL_COLOR)
    ax.tick_params(colors=SUBTLE_COLOR, labelsize=9)
    ax.grid(True, which="both", alpha=0.12, color=SUBTLE_COLOR)
    for spine in ax.spines.values():
        spine.set_color(BORDER_COLOR)

    for c_pf, color in zip(caps_pf, COLORS):
        c = c_pf * 1e-12
        h = transfer_function(f, r, c, stages)
        mag = magnitude_db(h)
        fcN = fc_cascade(r, c, stages)
        label = (f"C = {c_pf} pF  (fc = {fcN / 1e3:.1f} kHz, "
                 f"{magnitude_db(transfer_function(np.array([22e3]), r, c, stages))[0]:.1f} dB @ 22 kHz, "
                 f"{magnitude_db(transfer_function(np.array([100e6]), r, c, stages))[0]:.0f} dB @ FM)")
        ax.semilogx(f, mag, color=color, linewidth=1.5, label=label)

    ax.axvline(22e3, color=SUBTLE_COLOR, linewidth=1, linestyle=":",
               alpha=0.4)
    ax.annotate("22 kHz\n(VLF top)", xy=(22e3, -5), fontsize=7,
                color=SUBTLE_COLOR, fontfamily="monospace", ha="left",
                xytext=(5, 0), textcoords="offset points")

    ax.set_ylabel("Magnitude (dB)", fontsize=10, color=TEXT_COLOR,
                  fontfamily="monospace")
    ax.set_xlabel("Frequency (Hz)", fontsize=10, color=TEXT_COLOR,
                  fontfamily="monospace")
    ax.set_title(
        f"ELARA — Filter Cascade Comparison: Capacitance Sweep  "
        f"(R = {r / 1e3:.0f} kohm, {stages} stages)",
        fontsize=12, fontweight="bold", color=TEXT_COLOR,
        fontfamily="monospace", pad=15,
    )
    ax.set_ylim(-200, 5)

    legend = ax.legend(loc="lower left", fontsize=8, facecolor=PANEL_COLOR,
                       edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend.get_frame().set_alpha(0.9)

    # Band shading
    ax.axvspan(1, 300, alpha=0.04, color="#7ee787", zorder=0)
    ax.axvspan(3e3, 30e3, alpha=0.04, color="#f2cc60", zorder=0)
    ax.axvspan(300e3, 3e6, alpha=0.04, color="#79c0ff", zorder=0)
    ax.axvspan(88e6, 108e6, alpha=0.04, color="#ff7b72", zorder=0)

    plt.tight_layout()
    out_path = __file__.replace(".py", "_comparison.svg")
    fig.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Comparison plot saved: {out_path}")


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="ELARA — 2-Stage RC Filter Cascade Simulation",
    )
    parser.add_argument("-r", "--resistance", type=float, default=33e3,
                        help="Filter resistance in ohm (default: 33e3 = 33 kohm)")
    parser.add_argument("-c", "--capacitance", type=float, default=50e-12,
                        help="Filter capacitance in F (default: 50e-12 = 50 pF)")
    parser.add_argument("-n", "--stages", type=int, default=2,
                        help="Number of cascaded stages (default: 2)")
    parser.add_argument("--no-plot", action="store_true",
                        help="Skip plot generation")
    parser.add_argument("--comparison", action="store_true",
                        help="Also generate capacitance comparison plot")
    args = parser.parse_args()

    print_table(args.resistance, args.capacitance, args.stages)

    if not args.no_plot:
        plot_response(args.resistance, args.capacitance, args.stages)

        if args.comparison:
            plot_comparison(args.resistance, args.stages)


if __name__ == "__main__":
    main()
