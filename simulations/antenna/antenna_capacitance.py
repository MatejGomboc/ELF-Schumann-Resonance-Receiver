#!/usr/bin/env python3
"""
ELARA -- Antenna Capacitance Calculator & Signal Loss Tradeoff

Calculates the capacitance of a Marconi T-antenna from physical dimensions,
then evaluates the signal loss from the capacitive voltage divider formed
by the antenna capacitance and the filter capacitors.

CRITICAL CONSTRAINT: C_filter << C_ant, otherwise the filter caps
attenuate the signal before it even reaches the preamp!

    V_preamp = V_antenna * C_ant / (C_ant + C_filter)

Antenna model (NBS/Grover formulas):
    Vertical wire: C = 2*pi*e0*h / ln(2*h/a)
    Top hat wire:  C = 2*pi*e0*L / ln(2*h/a)
    Total:         C = C_vert + C_tophat

Reference: Renato Romero's antenna at vlf.it:
    13 m vertical + 3x24 m top hat = ~350 pF measured

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

# LMP7721
EN_LMP7721 = 6.5e-9
EN_1F_CORNER = 10.0   # Hz (from LMP7721 datasheet noise plot)
IN_LMP7721 = 0.01e-15
I_PCB = 0.1e-15

# Feedback (ELF bandpass)
R_FB = 9.1e3
R_GND = 1.0e3

# Target filter fc (with R=33k, C=50pF)
FC_TARGET = 1.0 / (2.0 * 3.14159265 * 33e3 * 50e-12)  # ~96.5 kHz

# Air-gap cap
EPSILON_R_AIR = 1.0006


def antenna_capacitance_pf(h_vert_m, l_tophat_m, wire_dia_mm=2.0,
                           n_tophat_wires=1):
    """
    Capacitance of a Marconi T-antenna.

    Args:
        h_vert_m:        vertical wire height (m)
        l_tophat_m:      horizontal top-hat wire length (m)
        wire_dia_mm:     wire diameter (mm)
        n_tophat_wires:  number of parallel top-hat wires
    """
    a = wire_dia_mm * 0.5e-3  # wire radius in meters

    # Vertical wire: C = 2*pi*e0*h / ln(2*h/a)
    c_vert = 2 * np.pi * EPSILON_0 * h_vert_m / np.log(2 * h_vert_m / a)

    # Top hat: each wire at height h
    # C = 2*pi*e0*L / ln(2*h/a)
    c_tophat = (n_tophat_wires * 2 * np.pi * EPSILON_0 * l_tophat_m
                / np.log(2 * h_vert_m / a))

    c_total = c_vert + c_tophat
    return c_total * 1e12  # pF


def transfer_function(freq, c_ant_pf, R_filt, c_filt_pf):
    """
    Full complex transfer function of the 2-stage RC filter
    with capacitive antenna source.

    Circuit:
        V_oc --[C_ant]-- node_a --[R1]-- node1 --[R2]-- node2 --> LMP7721 (inf Z)
                                           |                |
                                          [C1]             [C2]
                                           |                |
                                          GND              GND

    Returns magnitude ratio |V_node2 / V_oc| at each frequency.
    """
    w = 2 * np.pi * freq
    C_a = c_ant_pf * 1e-12
    C_f = c_filt_pf * 1e-12
    R = R_filt

    # Impedances (complex)
    Z_cant = 1.0 / (1j * w * C_a)
    Z_r = R + 0j
    Z_c = 1.0 / (1j * w * C_f)

    # Work backwards from output:
    # Z_load2 = Z_c2 (C2 to ground, LMP7721 is infinite Z)
    Z_load2 = Z_c

    # At node1: Z_c1 in parallel with (R2 + Z_load2)
    Z_branch2 = Z_r + Z_load2
    Z_node1 = (Z_c * Z_branch2) / (Z_c + Z_branch2)

    # Transfer from node_a to node2:
    # V_node1 = V_node_a * Z_node1 / (R1 + Z_node1)
    # V_node2 = V_node1 * Z_load2 / (R2 + Z_load2)
    H_r1 = Z_node1 / (Z_r + Z_node1)
    H_r2 = Z_load2 / (Z_r + Z_load2)

    # Transfer from V_oc to node_a:
    # Z_total_load = R1 + Z_node1
    Z_total_load = Z_r + Z_node1
    H_ant = Z_total_load / (Z_cant + Z_total_load)

    H_total = H_ant * H_r1 * H_r2
    return np.abs(H_total)


def signal_loss_db(c_ant_pf, c_filt_pf, R_filt=None, freq=7.83):
    """
    Signal loss at a given frequency using full complex transfer function.
    If R_filt is None, uses the capacitive divider approximation.
    """
    if c_ant_pf <= 0:
        return -999.0

    if R_filt is not None:
        mag = transfer_function(np.array([freq]), c_ant_pf, R_filt, c_filt_pf)
        return 20 * np.log10(mag[0]) if mag[0] > 0 else -999.0
    else:
        # Low-frequency approximation: C_ant / (C_ant + 2*C_filt)
        ratio = c_ant_pf / (c_ant_pf + 2 * c_filt_pf)
        return 20 * np.log10(ratio)


def thermal_noise(R):
    return np.sqrt(4.0 * k_B * T * R)


def en_1f(freq):
    return EN_LMP7721 * np.sqrt(1.0 + EN_1F_CORNER / freq)


def total_noise_at_freq(R_filt, freq, c_ant_pf):
    """Total input-referred noise including signal loss."""
    Z = 1.0 / (2.0 * np.pi * freq * c_ant_pf * 1e-12)
    en_v = en_1f(freq)
    en_i = IN_LMP7721 * Z
    en_pcb = I_PCB * Z
    en_r = thermal_noise(R_filt)
    en_rfb = thermal_noise(R_FB)
    return np.sqrt(en_v**2 + en_i**2 + en_pcb**2 + 2 * en_r**2 + en_rfb**2)


def effective_noise(R_filt, freq, c_ant_pf):
    """
    Effective noise: input-referred noise divided by signal transfer ratio.
    This is the noise referred to the ANTENNA terminal, accounting for
    signal loss through the capacitive divider.
    """
    c_filt_pf = 1.0 / (2.0 * np.pi * R_filt * FC_TARGET) * 1e12
    mag = transfer_function(np.array([freq]), c_ant_pf, R_filt, c_filt_pf)
    noise = total_noise_at_freq(R_filt, freq, c_ant_pf)
    return noise / mag[0] if mag[0] > 0 else float("inf")


def air_gap_plate_mm(c_pf, gap_mm=0.5):
    c_f = c_pf * 1e-12
    d = gap_mm * 1e-3
    side = np.sqrt(c_f * d / (EPSILON_0 * EPSILON_R_AIR))
    return side * 1e3 + 1.0  # + 2*0.5mm pullback


def print_analysis():
    print("=" * 110)
    print("ELARA -- Antenna Capacitance & Signal Loss Tradeoff")
    print("=" * 110)

    # Antenna capacitance calculations
    antennas = [
        ("ELARA design (10m vert, 15m top, 1 wire)", 10, 15, 2.0, 1),
        ("Romero-style (13m vert, 24m top, 3 wires)", 13, 24, 2.0, 3),
        ("Small (5m vert, 10m top, 1 wire)", 5, 10, 2.0, 1),
        ("Minimal (3m vert, 5m top, 1 wire)", 3, 5, 2.0, 1),
    ]

    print(f"\nANTENNA CAPACITANCE FROM DIMENSIONS:")
    print(f"{'Antenna':<50} {'C_vert':>8} {'C_top':>8} {'C_total':>8}")
    print("-" * 80)

    for desc, h, l, d, n in antennas:
        c_v = antenna_capacitance_pf(h, 0, d, 0)
        c_t = antenna_capacitance_pf(h, l, d, n) - c_v
        c_total = c_v + c_t
        print(f"{desc:<50} {c_v:>6.0f}pF {c_t:>6.0f}pF {c_total:>6.0f}pF")

    print(f"\n  Romero measured: ~350 pF (13m vert + 3x24m top hat)")
    print(f"  Our formula gives: {antenna_capacitance_pf(13, 24, 2.0, 3):.0f} pF")
    print(f"  Discrepancy is expected -- formula assumes ideal ground plane")

    # ELARA antenna capacitance
    c_ant = antenna_capacitance_pf(10, 15, 2.0, 1)
    print(f"\n  ELARA antenna: {c_ant:.0f} pF (calculated)")
    print(f"  Using {c_ant:.0f} pF for all further calculations")

    # Signal loss tradeoff
    print(f"\n{'=' * 110}")
    print(f"SIGNAL LOSS + NOISE TRADEOFF (C_ant = {c_ant:.0f} pF)")
    print(f"{'=' * 110}")

    R_values = [10e3, 22e3, 47e3, 100e3, 220e3, 470e3, 1e6]

    print(f"\n{'R_filt':>8} {'C_filt':>8} {'Plate':>8} {'Sig loss':>10} "
          f"{'Noise@SR1':>12} {'Eff noise':>12} {'vs 1M':>8} {'Verdict':>15}")
    print("-" * 110)

    results = []
    for R in R_values:
        C = 1.0 / (2.0 * np.pi * R * FC_TARGET)
        c_pf = C * 1e12
        plate = air_gap_plate_mm(c_pf, 0.5)
        loss = signal_loss_db(c_ant, c_pf, R, 7.83)
        noise = total_noise_at_freq(R, 7.83, c_ant) * 1e9
        eff = effective_noise(R, 7.83, c_ant) * 1e9

        results.append((R, c_pf, plate, loss, noise, eff))

        if R >= 1e6:
            r_str = f"{R/1e6:.0f}M"
        else:
            r_str = f"{R/1e3:.0f}k"

        # Verdict
        if abs(loss) > 6:
            verdict = "TOO MUCH LOSS"
        elif abs(loss) > 3:
            verdict = "significant"
        elif abs(loss) > 1:
            verdict = "acceptable"
        else:
            verdict = "excellent"

        print(f"{r_str:>8} {c_pf:>6.0f}pF {plate:>6.0f}mm {loss:>8.1f} dB "
              f"{noise:>10.1f} nV {eff:>10.1f} nV "
              f"{results[-1][5]/results[-1][5]:>6.1f}x {verdict:>15}")

    # Recalculate vs column relative to 1M baseline
    eff_1m = [r for r in results if r[0] == 1e6][0][5]
    print(f"\n  Relative to R=1M baseline ({eff_1m:.1f} nV effective noise at SR1):")
    for R, c_pf, plate, loss, noise, eff in results:
        r_str = f"{R/1e3:.0f}k" if R < 1e6 else f"{R/1e6:.0f}M"
        improvement = eff_1m / eff
        better = "BETTER" if improvement > 1 else "WORSE"
        print(f"    R={r_str:<6}: eff noise = {eff:.1f} nV -> {improvement:.2f}x {better}")

    # Optimal point
    print(f"\n{'=' * 110}")
    print("FINDING THE OPTIMAL R")
    print(f"{'=' * 110}")

    R_sweep = np.logspace(3.5, 7, 1000)
    eff_sweep = np.array([effective_noise(R, 7.83, c_ant) * 1e9 for R in R_sweep])
    optimal_idx = np.argmin(eff_sweep)
    R_opt = R_sweep[optimal_idx]
    C_opt = 1.0 / (2.0 * np.pi * R_opt * FC_TARGET) * 1e12

    print(f"\n  Optimal R = {R_opt/1e3:.1f} kOhm")
    print(f"  Required C = {C_opt:.0f} pF")
    print(f"  Plate size (0.5mm gap) = {air_gap_plate_mm(C_opt, 0.5):.0f} mm")
    print(f"  Signal loss = {signal_loss_db(c_ant, C_opt, R_opt, 7.83):.1f} dB")
    print(f"  Input noise = {total_noise_at_freq(R_opt, 7.83, c_ant)*1e9:.1f} nV/sqrtHz")
    print(f"  Effective noise = {eff_sweep[optimal_idx]:.1f} nV/sqrtHz")

    # Nearest standard values
    standard_R = [10e3, 22e3, 33e3, 47e3, 68e3, 100e3]
    print(f"\n  Nearest standard E24 values:")
    for R in standard_R:
        C = 1.0 / (2.0 * np.pi * R * FC_TARGET) * 1e12
        eff = effective_noise(R, 7.83, c_ant) * 1e9
        loss = signal_loss_db(c_ant, C, R, 7.83)
        plate = air_gap_plate_mm(C, 0.5)
        r_str = f"{R/1e3:.0f}k"
        print(f"    R={r_str:<6} C={C:.0f}pF  plate={plate:.0f}mm  "
              f"loss={loss:.1f}dB  eff_noise={eff:.1f}nV")

    # Romero comparison at optimal
    Z_sr1 = 1.0 / (2.0 * np.pi * 7.83 * c_ant * 1e-12)
    romero = np.sqrt((16e-9 * np.sqrt(1 + 30/7.83))**2
                     + (0.8e-15 * Z_sr1)**2) * 1e9
    R_best = 33e3  # optimised for noise vs AM rejection
    eff_best = effective_noise(R_best, 7.83, c_ant) * 1e9
    print(f"\n  Romero AD820 noise at SR1: {romero:.1f} nV/sqrtHz")
    print(f"  ELARA with R=33k: {eff_best:.1f} nV/sqrtHz")
    print(f"  Improvement: {romero/eff_best:.1f}x voltage, "
          f"{(romero/eff_best)**2:.0f}x power")


def plot_tradeoff():
    if not HAS_MATPLOTLIB:
        return

    BG = "#0d1117"
    TEXT = "#e6edf3"
    SUBTLE = "#7d8590"
    PANEL = "#161b22"
    BORDER = "#30363d"

    c_ant = antenna_capacitance_pf(10, 15, 2.0, 1)
    R_sweep = np.logspace(3.5, 7, 500)

    noise_raw = np.array([total_noise_at_freq(R, 7.83, c_ant) * 1e9
                          for R in R_sweep])
    noise_eff = np.array([effective_noise(R, 7.83, c_ant) * 1e9
                          for R in R_sweep])
    c_filt = np.array([1.0 / (2 * np.pi * R * FC_TARGET) * 1e12
                       for R in R_sweep])
    sig_loss = np.array([signal_loss_db(c_ant, c, R, 7.83)
                         for R, c in zip(R_sweep, c_filt)])
    plate_mm = np.array([air_gap_plate_mm(c, 0.5) for c in c_filt])

    # Romero reference
    Z_sr1 = 1.0 / (2 * np.pi * 7.83 * c_ant * 1e-12)
    romero = np.sqrt((16e-9 * np.sqrt(1 + 30/7.83))**2
                     + (0.8e-15 * Z_sr1)**2) * 1e9

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 16), sharex=True)
    fig.patch.set_facecolor(BG)

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=SUBTLE, labelsize=9)
        ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
        for spine in ax.spines.values():
            spine.set_color(BORDER)

    # Plot 1: Effective noise (the one that matters!)
    ax1.semilogx(R_sweep / 1e3, noise_raw, color="#79c0ff", linewidth=1.5,
                 linestyle="--", label="Raw input noise (ignoring signal loss)")
    ax1.semilogx(R_sweep / 1e3, noise_eff, color="#7ee787", linewidth=2.5,
                 label="Effective noise (including signal loss)")
    ax1.axhline(romero, color="#ff7b72", linewidth=1.5, linestyle="--",
                label=f"Romero AD820 ({romero:.0f} nV)")

    opt_idx = np.argmin(noise_eff)
    ax1.plot(R_sweep[opt_idx] / 1e3, noise_eff[opt_idx], 'o',
             color="#f2cc60", markersize=10, zorder=5)
    ax1.annotate(f"Optimal: {R_sweep[opt_idx]/1e3:.0f}k\n{noise_eff[opt_idx]:.0f} nV",
                 xy=(R_sweep[opt_idx] / 1e3, noise_eff[opt_idx]),
                 xytext=(R_sweep[opt_idx] / 1e3 * 3, noise_eff[opt_idx] + 30),
                 fontsize=9, color="#f2cc60", fontfamily="monospace",
                 arrowprops=dict(arrowstyle="->", color="#f2cc60"))

    ax1.set_ylabel("Noise at SR1 (nV/sqrtHz)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    ax1.set_title(f"ELARA -- Filter Resistor Optimisation with Signal Loss\n"
                  f"C_ant = {c_ant:.0f} pF, fc = 15.9 kHz, 0.5 mm air gap",
                  fontsize=13, fontweight="bold", color=TEXT,
                  fontfamily="monospace", pad=10)
    ax1.legend(loc="upper left", fontsize=8, facecolor=PANEL,
               edgecolor=BORDER, labelcolor=TEXT).get_frame().set_alpha(0.9)

    # Plot 2: Signal loss
    ax2.semilogx(R_sweep / 1e3, sig_loss, color="#ff7b72", linewidth=2.5)
    ax2.axhline(-3, color=SUBTLE, linewidth=1, linestyle="--", alpha=0.5,
                label="-3 dB")
    ax2.axhline(-1, color=SUBTLE, linewidth=1, linestyle=":", alpha=0.5,
                label="-1 dB")
    ax2.set_ylabel("Signal loss (dB)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    ax2.legend(loc="lower left", fontsize=8, facecolor=PANEL,
               edgecolor=BORDER, labelcolor=TEXT).get_frame().set_alpha(0.9)

    # Plot 3: Cap value and plate size
    ax3.semilogx(R_sweep / 1e3, c_filt, color="#79c0ff", linewidth=2,
                 label="C_filter (pF)")
    ax3.semilogx(R_sweep / 1e3, plate_mm, color="#f2cc60", linewidth=2,
                 linestyle="--", label="Plate side (mm, 0.5mm gap)")
    ax3.axhline(c_ant, color="#ff7b72", linewidth=1.5, linestyle="--",
                alpha=0.7, label=f"C_ant = {c_ant:.0f} pF (must stay below!)")
    ax3.axhline(100, color=SUBTLE, linewidth=1, linestyle=":", alpha=0.5,
                label="100 mm max plate")

    ax3.set_xlabel("Filter resistor R (kOhm)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    ax3.set_ylabel("Capacitance (pF) / Plate size (mm)", fontsize=11, color=TEXT,
                   fontfamily="monospace")
    ax3.legend(loc="upper left", fontsize=7, facecolor=PANEL,
               edgecolor=BORDER, labelcolor=TEXT).get_frame().set_alpha(0.9)
    ax3.set_ylim(0, 500)

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "antenna_capacitance.svg")
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(f"\nPlot saved: {out_path}")


if __name__ == "__main__":
    print_analysis()
    plot_tradeoff()
