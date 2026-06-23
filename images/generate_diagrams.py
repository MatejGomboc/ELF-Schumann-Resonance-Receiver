#!/usr/bin/env python3
"""
ELARA — System Diagrams Generator
Generates technical illustrations for the project documentation.

Author: Matej + Claude, March 2026
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import numpy as np
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
BG_COLOR = '#0d1117'
TEXT_COLOR = '#e6edf3'
SUBTLE_COLOR = '#7d8590'
ACCENT_RED = '#ff7b72'
ACCENT_ORANGE = '#ffa657'
ACCENT_GREEN = '#7ee787'
ACCENT_BLUE = '#79c0ff'
ACCENT_PURPLE = '#d2a8ff'
ACCENT_YELLOW = '#f2cc60'
PANEL_COLOR = '#161b22'
BORDER_COLOR = '#30363d'


def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=200, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {name}")


def draw_system_overview():
    """Full system overview: antenna -> outdoor unit -> cables -> indoor -> spectrum."""
    fig, ax = plt.subplots(figsize=(18, 24))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 24)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor(BG_COLOR)

    # Title
    ax.text(9, 23.3, 'ELARA', fontsize=28, fontweight='bold',
            ha='center', color=TEXT_COLOR, fontfamily='monospace')
    ax.text(9, 22.7, 'ELF Atmospheric Radio Analyser — System Overview',
            fontsize=11, ha='center', color=SUBTLE_COLOR, fontfamily='monospace')

    # ===== T-ANTENNA =====
    ax.plot([9, 9], [20.5, 22.0], color=ACCENT_ORANGE, linewidth=3.5,
            solid_capstyle='round')
    ax.plot([6, 12], [22.0, 22.0], color=ACCENT_ORANGE, linewidth=3.5,
            solid_capstyle='round')
    ax.plot([6, 6], [22.0, 21.7], color=ACCENT_ORANGE, linewidth=2)
    ax.plot([12, 12], [22.0, 21.7], color=ACCENT_ORANGE, linewidth=2)
    ax.text(9, 22.35, 'Marconi T-Antenna', fontsize=9, fontweight='bold',
            ha='center', color=ACCENT_ORANGE, fontfamily='monospace')
    ax.text(9, 21.4, '~10m vertical  ·  ~15m capacitive top  ·  ~140pF',
            fontsize=7, ha='center', color=ACCENT_ORANGE, fontfamily='monospace',
            alpha=0.7)

    # Antenna wire down
    ax.annotate('', xy=(9, 20.0), xytext=(9, 20.5),
                arrowprops=dict(arrowstyle='->', color=ACCENT_ORANGE, lw=2))
    ax.text(9.3, 20.2, 'antenna wire', fontsize=7, color=ACCENT_ORANGE,
            fontfamily='monospace', alpha=0.6)

    # ===== PLASTIC ENCLOSURE =====
    plastic = FancyBboxPatch((2.0, 11.0), 14.0, 9.0, boxstyle='round,pad=0.3',
                              facecolor='none', edgecolor=SUBTLE_COLOR,
                              linewidth=2, linestyle=(0, (5, 3)))
    ax.add_patch(plastic)
    ax.text(15.5, 19.7, 'PLASTIC ENCLOSURE', fontsize=8, ha='right',
            color=SUBTLE_COLOR, fontfamily='monospace', fontweight='bold')
    ax.text(15.5, 19.3, 'IP65 weatherproof', fontsize=7, ha='right',
            color=SUBTLE_COLOR, fontfamily='monospace')

    # ===== INPUT FILTER (in air) =====
    filter_bg = FancyBboxPatch((3.0, 17.5), 12.0, 2.3, boxstyle='round,pad=0.15',
                                facecolor=PANEL_COLOR, edgecolor=ACCENT_BLUE,
                                linewidth=1.5, alpha=0.8)
    ax.add_patch(filter_bg)
    ax.text(9, 19.55, 'INPUT RF FILTER — suspended in air, unshielded',
            fontsize=8, fontweight='bold', ha='center', color=ACCENT_BLUE,
            fontfamily='monospace')

    # Filter schematic
    y_filt = 18.5
    # Antenna in
    ax.plot([3.5, 4.5], [y_filt, y_filt], color=ACCENT_ORANGE, linewidth=2)

    # R1
    r1 = FancyBboxPatch((4.5, y_filt - 0.25), 1.5, 0.5,
                          boxstyle='round,pad=0.05',
                          facecolor='#1a2b15', edgecolor=ACCENT_GREEN, linewidth=1.5)
    ax.add_patch(r1)
    ax.text(5.25, y_filt, '33kΩ', fontsize=8, ha='center', va='center',
            color=ACCENT_GREEN, fontweight='bold', fontfamily='monospace')

    # Wire
    ax.plot([6.0, 6.8], [y_filt, y_filt], color=TEXT_COLOR, linewidth=1.5)

    # Air Cap 1
    cap1 = FancyBboxPatch((6.8, y_filt - 0.5), 1.2, 1.0,
                            boxstyle='round,pad=0.05',
                            facecolor='#2a1800', edgecolor=ACCENT_ORANGE, linewidth=2)
    ax.add_patch(cap1)
    ax.text(7.4, y_filt + 0.15, 'Air', fontsize=7, ha='center', va='center',
            color=ACCENT_ORANGE, fontweight='bold', fontfamily='monospace')
    ax.text(7.4, y_filt - 0.15, 'Cap1', fontsize=7, ha='center', va='center',
            color=ACCENT_ORANGE, fontfamily='monospace')
    # GND symbol
    ax.plot([7.4, 7.4], [y_filt - 0.5, y_filt - 0.75], color=SUBTLE_COLOR, lw=1.2)
    ax.plot([7.1, 7.7], [y_filt - 0.75, y_filt - 0.75], color=SUBTLE_COLOR, lw=2)
    ax.plot([7.2, 7.6], [y_filt - 0.85, y_filt - 0.85], color=SUBTLE_COLOR, lw=1.5)
    ax.plot([7.3, 7.5], [y_filt - 0.95, y_filt - 0.95], color=SUBTLE_COLOR, lw=1)

    # Wire
    ax.plot([8.0, 8.8], [y_filt, y_filt], color=TEXT_COLOR, linewidth=1.5)

    # R2
    r2 = FancyBboxPatch((8.8, y_filt - 0.25), 1.5, 0.5,
                          boxstyle='round,pad=0.05',
                          facecolor='#1a2b15', edgecolor=ACCENT_GREEN, linewidth=1.5)
    ax.add_patch(r2)
    ax.text(9.55, y_filt, '33kΩ', fontsize=8, ha='center', va='center',
            color=ACCENT_GREEN, fontweight='bold', fontfamily='monospace')

    # Wire
    ax.plot([10.3, 11.1], [y_filt, y_filt], color=TEXT_COLOR, linewidth=1.5)

    # Air Cap 2
    cap2 = FancyBboxPatch((11.1, y_filt - 0.5), 1.2, 1.0,
                            boxstyle='round,pad=0.05',
                            facecolor='#2a1800', edgecolor=ACCENT_ORANGE, linewidth=2)
    ax.add_patch(cap2)
    ax.text(11.7, y_filt + 0.15, 'Air', fontsize=7, ha='center', va='center',
            color=ACCENT_ORANGE, fontweight='bold', fontfamily='monospace')
    ax.text(11.7, y_filt - 0.15, 'Cap2', fontsize=7, ha='center', va='center',
            color=ACCENT_ORANGE, fontfamily='monospace')
    # GND symbol
    ax.plot([11.7, 11.7], [y_filt - 0.5, y_filt - 0.75], color=SUBTLE_COLOR, lw=1.2)
    ax.plot([11.4, 12.0], [y_filt - 0.75, y_filt - 0.75], color=SUBTLE_COLOR, lw=2)
    ax.plot([11.5, 11.9], [y_filt - 0.85, y_filt - 0.85], color=SUBTLE_COLOR, lw=1.5)
    ax.plot([11.6, 11.8], [y_filt - 0.95, y_filt - 0.95], color=SUBTLE_COLOR, lw=1)

    # Wire out to ALU
    ax.plot([12.3, 13.5], [y_filt, y_filt], color=TEXT_COLOR, linewidth=1.5)
    ax.annotate('', xy=(13.8, y_filt), xytext=(13.5, y_filt),
                arrowprops=dict(arrowstyle='->', color=ACCENT_BLUE, lw=2))

    # Labels
    ax.text(7.4, y_filt + 0.7, '~50pF', fontsize=6, ha='center',
            color=ACCENT_ORANGE, fontfamily='monospace', alpha=0.7)
    ax.text(11.7, y_filt + 0.7, '~50pF', fontsize=6, ha='center',
            color=ACCENT_ORANGE, fontfamily='monospace', alpha=0.7)
    ax.text(9.55, y_filt - 1.1, 'Two air-gap plate capacitors (PCB + spacers)',
            fontsize=6, ha='center', color=SUBTLE_COLOR, fontfamily='monospace')
    ax.text(9.55, y_filt - 1.4, 'Air gap between them — no shared substrate',
            fontsize=6, ha='center', color=SUBTLE_COLOR, fontfamily='monospace')

    # ===== ANTENNA AMP ALU SHIELD (compartmentalised) =====
    alu = FancyBboxPatch((3.0, 11.5), 9.0, 5.5, boxstyle='round,pad=0.15',
                          facecolor=PANEL_COLOR, edgecolor='#8b949e',
                          linewidth=3)
    ax.add_patch(alu)
    ax.text(7.5, 16.75, 'ANTENNA AMPLIFIER — ALU enclosure',
            fontsize=8, fontweight='bold', ha='center', color='#8b949e',
            fontfamily='monospace')
    ax.text(7.5, 16.35, 'RF tuner-style compartments  ·  M3 bolts to PCB copper',
            fontsize=7, ha='center', color=SUBTLE_COLOR, fontfamily='monospace')

    # Compartment 1
    c1 = FancyBboxPatch((3.4, 11.8), 2.7, 4.2, boxstyle='round,pad=0.1',
                          facecolor='#1a0505', edgecolor=ACCENT_RED, linewidth=2)
    ax.add_patch(c1)
    ax.text(4.75, 15.7, 'COMP. 1', fontsize=7, fontweight='bold',
            ha='center', color=ACCENT_RED, fontfamily='monospace')
    ax.text(4.75, 15.3, 'INPUT', fontsize=9, fontweight='bold',
            ha='center', color=ACCENT_RED, fontfamily='monospace')
    ax.text(4.75, 14.0, 'LMP7721\nelectrometer\nbuffer\n\nguard ring\nbias jumper',
            fontsize=7, ha='center', color=TEXT_COLOR, fontfamily='monospace',
            linespacing=1.4)
    ax.text(4.75, 12.1, 'femtoampere\nsensitive',
            fontsize=6, ha='center', color=ACCENT_RED, fontfamily='monospace',
            alpha=0.6, style='italic')

    # Compartment 2
    c2 = FancyBboxPatch((6.3, 11.8), 3.0, 4.2, boxstyle='round,pad=0.1',
                          facecolor='#1a1200', edgecolor=ACCENT_YELLOW, linewidth=2)
    ax.add_patch(c2)
    ax.text(7.8, 15.7, 'COMP. 2', fontsize=7, fontweight='bold',
            ha='center', color=ACCENT_YELLOW, fontfamily='monospace')
    ax.text(7.8, 15.3, 'ANALOG', fontsize=9, fontweight='bold',
            ha='center', color=ACCENT_YELLOW, fontfamily='monospace')
    ax.text(7.8, 13.8, 'LMP7715\nguard driver\n\nanti-alias LPF\n\nPCM1804\nanalog in',
            fontsize=7, ha='center', color=TEXT_COLOR, fontfamily='monospace',
            linespacing=1.4)

    # Compartment 3
    c3 = FancyBboxPatch((9.5, 11.8), 2.3, 4.2, boxstyle='round,pad=0.1',
                          facecolor='#051a05', edgecolor=ACCENT_GREEN, linewidth=2)
    ax.add_patch(c3)
    ax.text(10.65, 15.7, 'COMP. 3', fontsize=7, fontweight='bold',
            ha='center', color=ACCENT_GREEN, fontfamily='monospace')
    ax.text(10.65, 15.3, 'DIGITAL', fontsize=9, fontweight='bold',
            ha='center', color=ACCENT_GREEN, fontfamily='monospace')
    ax.text(10.65, 13.8, 'CS8406\nSPDIF TX\ncrystal osc\naudio xfmr\nPCM1804\ndigital',
            fontsize=7, ha='center', color=TEXT_COLOR, fontfamily='monospace',
            linespacing=1.4)

    # PCB bar (antenna amp)
    pcb_bar = FancyBboxPatch((3.0, 11.0), 9.0, 0.5, boxstyle='round,pad=0.05',
                              facecolor='#1a3a1a', edgecolor=ACCENT_GREEN,
                              linewidth=1, alpha=0.5)
    ax.add_patch(pcb_bar)
    ax.text(7.5, 11.25, 'PCB (PTFE/Rogers) — J1 on BOTTOM',
            fontsize=7, ha='center', color=ACCENT_GREEN, fontfamily='monospace')

    # ===== PSU ALU ENCLOSURE (separate) =====
    psu = FancyBboxPatch((12.5, 11.5), 2.8, 5.5, boxstyle='round,pad=0.15',
                          facecolor=PANEL_COLOR, edgecolor=ACCENT_PURPLE,
                          linewidth=3, linestyle=(0, (4, 2)))
    ax.add_patch(psu)
    ax.text(13.9, 16.75, 'PSU — separate', fontsize=8, fontweight='bold',
            ha='center', color=ACCENT_PURPLE, fontfamily='monospace')
    ax.text(13.9, 16.35, 'ALU enclosure', fontsize=7,
            ha='center', color=ACCENT_PURPLE, fontfamily='monospace')
    ax.text(13.9, 14.5, 'AC-DC\nconverter\n(two-bucket)\n\nADM7150\nLDOs',
            fontsize=7, ha='center', color=TEXT_COLOR, fontfamily='monospace',
            linespacing=1.4)
    ax.text(13.9, 12.1, 'REMOVABLE\nswap for\nbattery',
            fontsize=7, ha='center', color=ACCENT_PURPLE, fontfamily='monospace',
            fontweight='bold', alpha=0.7)

    # DC cable between PSU and amp
    ax.annotate('', xy=(12.0, 13.5), xytext=(12.5, 13.5),
                arrowprops=dict(arrowstyle='<->', color=ACCENT_PURPLE, lw=2))
    ax.text(12.25, 13.1, 'DC', fontsize=6, ha='center', color=ACCENT_PURPLE,
            fontfamily='monospace', rotation=90)

    # ===== CABLES =====
    cable_y_start = 11.5
    cable_y_end = 7.5

    # AES/EBU
    ax.plot([12.0, 12.0, 15.0, 15.0], [cable_y_start, 10.5, 10.5, cable_y_end],
            color=ACCENT_GREEN, linewidth=3, solid_capstyle='round')
    ax.text(15.3, 9.5, 'AES/EBU', fontsize=8, fontweight='bold',
            color=ACCENT_GREEN, fontfamily='monospace')
    ax.text(15.3, 9.1, '110Ω STP', fontsize=7,
            color=ACCENT_GREEN, fontfamily='monospace', alpha=0.7)
    ax.text(15.3, 8.7, 'containment', fontsize=6,
            color=ACCENT_GREEN, fontfamily='monospace', alpha=0.5)
    ax.text(15.3, 8.4, 'shielded', fontsize=6,
            color=ACCENT_GREEN, fontfamily='monospace', alpha=0.5)

    # 230V mains
    ax.plot([13.0, 13.0, 16.0, 16.0], [cable_y_start, 10.0, 10.0, cable_y_end],
            color=ACCENT_RED, linewidth=3, solid_capstyle='round')
    ax.text(16.3, 9.5, '230V AC', fontsize=8, fontweight='bold',
            color=ACCENT_RED, fontfamily='monospace')
    ax.text(16.3, 9.1, 'STP mains', fontsize=7,
            color=ACCENT_RED, fontfamily='monospace', alpha=0.7)
    ax.text(16.3, 8.7, 'containment', fontsize=6,
            color=ACCENT_RED, fontfamily='monospace', alpha=0.5)
    ax.text(16.3, 8.4, 'shielded', fontsize=6,
            color=ACCENT_RED, fontfamily='monospace', alpha=0.5)

    # Distance
    ax.annotate('', xy=(14.0, cable_y_end + 0.2), xytext=(14.0, cable_y_start - 0.2),
                arrowprops=dict(arrowstyle='<->', color=SUBTLE_COLOR, lw=1.5))
    ax.text(14.0, 9.3, '~100m', fontsize=10, ha='center', color=SUBTLE_COLOR,
            fontweight='bold', fontfamily='monospace')

    # Reverse shielding note
    ax.text(9, 10.2, '"Reverse shielding" — cables are shielded to contain',
            fontsize=7, ha='center', color=ACCENT_PURPLE, fontfamily='monospace',
            style='italic')
    ax.text(9, 9.8, 'their OWN emissions, not to protect from the environment',
            fontsize=7, ha='center', color=ACCENT_PURPLE, fontfamily='monospace',
            style='italic')

    # ===== INDOOR UNIT =====
    indoor = FancyBboxPatch((3.0, 5.5), 12.0, 2.0, boxstyle='round,pad=0.2',
                             facecolor='#0d1b2a', edgecolor=ACCENT_BLUE, linewidth=2)
    ax.add_patch(indoor)
    ax.text(9, 7.1, 'INDOOR — OFF THE SHELF', fontsize=12, fontweight='bold',
            ha='center', color=TEXT_COLOR, fontfamily='monospace')
    ax.text(9, 6.55, 'USB Audio Card (SPDIF input)  →  PC', fontsize=10,
            ha='center', color=ACCENT_BLUE, fontfamily='monospace')
    ax.text(9, 6.0, 'adaptive 50Hz notch  ·  FFT spectrograms  ·  data logging',
            fontsize=7, ha='center', color=SUBTLE_COLOR, fontfamily='monospace')

    # Cables to indoor
    ax.plot([15.0, 15.0, 14.5], [cable_y_end, 6.8, 6.8],
            color=ACCENT_GREEN, linewidth=3, solid_capstyle='round')
    ax.plot([16.0, 16.0, 14.5], [cable_y_end, 6.2, 6.2],
            color=ACCENT_RED, linewidth=3, solid_capstyle='round')

    # ===== SCHUMANN SPECTRUM =====
    freqs = np.linspace(1, 50, 500)
    spectrum = np.zeros_like(freqs)
    for f0, amp in [(7.83, 1.0), (14.3, 0.7), (20.8, 0.45), (27.3, 0.28), (33.8, 0.18)]:
        spectrum += amp * np.exp(-0.5 * ((freqs - f0) / 0.9) ** 2)
    np.random.seed(42)
    spectrum += 0.03 * np.random.randn(len(freqs)) + 0.08

    spec_x = 3.0 + (freqs - 1) / 49 * 12
    spec_y = 1.5 + spectrum / spectrum.max() * 3.2

    ax.fill_between(spec_x, 1.5, spec_y, alpha=0.2, color=ACCENT_BLUE)
    ax.plot(spec_x, spec_y, color=ACCENT_BLUE, linewidth=1.5, alpha=0.8)

    ax.text(9, 5.0, 'TARGET: Schumann Resonances', fontsize=10, fontweight='bold',
            ha='center', color=ACCENT_BLUE, fontfamily='monospace')

    for f0, name in [(7.83, 'SR1\n7.83 Hz'), (14.3, 'SR2\n14.3 Hz'),
                      (20.8, 'SR3\n20.8 Hz'), (27.3, 'SR4\n27.3'), (33.8, 'SR5\n33.8')]:
        x = 3.0 + (f0 - 1) / 49 * 12
        ax.plot([x, x], [1.5, 4.5], color=ACCENT_BLUE, alpha=0.15, linewidth=0.8,
                linestyle='--')
        ax.text(x, 1.1, name, fontsize=6, ha='center', color=ACCENT_BLUE,
                fontfamily='monospace', alpha=0.6)

    ax.plot([3.0, 15.0], [1.5, 1.5], color=BORDER_COLOR, linewidth=1)
    ax.text(3.0, 0.7, '1 Hz', fontsize=7, color=SUBTLE_COLOR, fontfamily='monospace')
    ax.text(15.0, 0.7, '50 Hz', fontsize=7, ha='right', color=SUBTLE_COLOR,
            fontfamily='monospace')

    save(fig, '01_system_overview.svg')


def draw_pcb_cross_section():
    """Cross-section showing PCB, ALU shield compartments, antenna on bottom."""
    fig, ax = plt.subplots(figsize=(22, 14))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 14)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor(BG_COLOR)

    # Center of the diagram
    cx = 11.0

    ax.text(cx, 13.5, 'ELARA — PCB & Shield Cross-Section', fontsize=16,
            fontweight='bold', ha='center', color=TEXT_COLOR, fontfamily='monospace')

    # ===== PLASTIC ENCLOSURE =====
    enc_x = 1.5
    enc_w = 19.0
    enc_y = 0.5
    enc_h = 12.3
    plastic = FancyBboxPatch((enc_x, enc_y), enc_w, enc_h,
                              boxstyle='round,pad=0.2',
                              facecolor='none', edgecolor=SUBTLE_COLOR,
                              linewidth=2, linestyle=(0, (5, 3)))
    ax.add_patch(plastic)
    ax.text(enc_x + enc_w - 0.3, enc_y + enc_h - 0.3, 'PLASTIC ENCLOSURE  ·  IP65',
            fontsize=7, ha='right', color=SUBTLE_COLOR, fontfamily='monospace')

    # (Input filter drawn below the PCB — see after J1 section)

    # ===== ALU SHIELD (antenna amplifier) =====
    alu_x = 2.5
    alu_w = 12.0
    alu_y = 6.0
    alu_h = 5.0

    # ALU top plate
    alu_top = patches.Rectangle((alu_x, alu_y + alu_h), alu_w, 0.3,
                                 facecolor='#4a4a4a', edgecolor='#8b949e',
                                 linewidth=1.5)
    ax.add_patch(alu_top)
    ax.text(alu_x + alu_w / 2, alu_y + alu_h + 0.5, 'ALU shield top plate',
            fontsize=7, ha='center', color='#8b949e', fontfamily='monospace')

    # ALU walls
    wall_xs = [alu_x, alu_x + 3.5, alu_x + 7.5, alu_x + alu_w - 0.2]
    for wx in wall_xs:
        wall = patches.Rectangle((wx, alu_y), 0.2, alu_h,
                                  facecolor='#4a4a4a', edgecolor='#8b949e',
                                  linewidth=1)
        ax.add_patch(wall)

    # Compartment backgrounds
    comp_data = [
        (alu_x + 0.2, 3.1, ACCENT_RED, '#1a0505',
         'COMP. 1', 'INPUT',
         'LMP7721\ninput node\nguard ring\nbias jumper'),
        (alu_x + 3.7, 3.6, ACCENT_YELLOW, '#1a1200',
         'COMP. 2', 'ANALOG',
         'LMP7715\nguard driver\nanti-alias LPF\nPCM1804 analog'),
        (alu_x + 7.7, 4.1, ACCENT_GREEN, '#051a05',
         'COMP. 3', 'DIGITAL',
         'CS8406\nSPDIF TX\ncrystal osc\naudio xfmr'),
    ]
    for bx, bw, color, bg, comp_name, comp_title, comp_desc in comp_data:
        bg_rect = FancyBboxPatch((bx, alu_y + 0.2), bw, alu_h - 0.4,
                                  boxstyle='round,pad=0.08',
                                  facecolor=bg, edgecolor=color, linewidth=1.5,
                                  alpha=0.8)
        ax.add_patch(bg_rect)
        ax.text(bx + bw / 2, alu_y + alu_h - 0.7, comp_name, fontsize=8,
                fontweight='bold', ha='center', color=color, fontfamily='monospace')
        ax.text(bx + bw / 2, alu_y + alu_h - 1.3, comp_title, fontsize=10,
                fontweight='bold', ha='center', color=color, fontfamily='monospace')
        ax.text(bx + bw / 2, alu_y + 1.8, comp_desc, fontsize=7,
                ha='center', va='center', color=TEXT_COLOR, fontfamily='monospace',
                linespacing=1.5)

    # ===== PSU ALU ENCLOSURE (separate unit) =====
    psu_x = 15.5
    psu_w = 3.0
    psu_box = FancyBboxPatch((psu_x, alu_y), psu_w, alu_h + 0.3,
                              boxstyle='round,pad=0.1',
                              facecolor=PANEL_COLOR, edgecolor=ACCENT_PURPLE,
                              linewidth=2.5, linestyle=(0, (4, 2)))
    ax.add_patch(psu_box)
    ax.text(psu_x + psu_w / 2, alu_y + alu_h - 0.4, 'SEPARATE',
            fontsize=7, fontweight='bold', ha='center',
            color=ACCENT_PURPLE, fontfamily='monospace')
    ax.text(psu_x + psu_w / 2, alu_y + alu_h - 1.0, 'PSU ALU',
            fontsize=9, fontweight='bold', ha='center',
            color=ACCENT_PURPLE, fontfamily='monospace')
    ax.text(psu_x + psu_w / 2, alu_y + 2.5, 'AC-DC\nconverter\n\nADM7150\nLDOs',
            fontsize=7, ha='center', color=TEXT_COLOR, fontfamily='monospace',
            linespacing=1.4)
    ax.text(psu_x + psu_w / 2, alu_y + 0.5, 'REMOVABLE\nswap for battery',
            fontsize=6, ha='center', color=ACCENT_PURPLE, fontfamily='monospace',
            fontweight='bold', alpha=0.7)

    # DC cable between PSU and amp ALU
    ax.annotate('', xy=(alu_x + alu_w, alu_y + alu_h / 2),
                xytext=(psu_x, alu_y + alu_h / 2),
                arrowprops=dict(arrowstyle='<->', color=ACCENT_PURPLE, lw=2))
    ax.text((alu_x + alu_w + psu_x) / 2, alu_y + alu_h / 2 + 0.4,
            'DC cable', fontsize=7, ha='center',
            color=ACCENT_PURPLE, fontfamily='monospace')

    # ===== PCB SUBSTRATE (antenna amp only) =====
    pcb_y = 4.5
    pcb_h = 1.3
    pcb_x = alu_x
    pcb_w = alu_w  # same width as antenna amp ALU

    # Copper top
    cu_top = patches.Rectangle((pcb_x, pcb_y + pcb_h), pcb_w, 0.15,
                                facecolor=ACCENT_ORANGE, edgecolor='none', alpha=0.6)
    ax.add_patch(cu_top)

    # Substrate
    pcb_sub = patches.Rectangle((pcb_x, pcb_y + 0.3), pcb_w, pcb_h - 0.3,
                                 facecolor='#1a3a1a', edgecolor=ACCENT_GREEN,
                                 linewidth=2)
    ax.add_patch(pcb_sub)
    ax.text(pcb_x + pcb_w / 2, pcb_y + 0.75, 'PCB  —  PTFE / Rogers 4350B',
            fontsize=9, ha='center', va='center', color=ACCENT_GREEN,
            fontweight='bold', fontfamily='monospace')

    # GND plane
    gnd = patches.Rectangle((pcb_x, pcb_y + 0.5), pcb_w, 0.1,
                              facecolor=ACCENT_YELLOW, edgecolor='none', alpha=0.4)
    ax.add_patch(gnd)

    # Copper bottom
    cu_bot = patches.Rectangle((pcb_x, pcb_y + 0.15), pcb_w, 0.15,
                                facecolor=ACCENT_ORANGE, edgecolor='none', alpha=0.6)
    ax.add_patch(cu_bot)

    # M3 bolt markers
    for wx in wall_xs:
        ax.plot(wx + 0.1, pcb_y + pcb_h + 0.15, 'v',
                color=ACCENT_YELLOW, markersize=7)

    # Layer labels (to the right of PCB, tightly stacked within PCB height)
    lbl_x = pcb_x + pcb_w + 0.8
    ax.annotate('Cu top', xy=(pcb_x + pcb_w, pcb_y + pcb_h + 0.08),
                xytext=(lbl_x, pcb_y + 0.9), fontsize=7,
                color=ACCENT_ORANGE, fontfamily='monospace',
                arrowprops=dict(arrowstyle='->', color=ACCENT_ORANGE, lw=0.8))
    ax.annotate('GND plane', xy=(pcb_x + pcb_w, pcb_y + 0.55),
                xytext=(lbl_x, pcb_y + 0.55), fontsize=7,
                color=ACCENT_YELLOW, fontfamily='monospace',
                arrowprops=dict(arrowstyle='->', color=ACCENT_YELLOW, lw=0.8))
    ax.annotate('Cu bottom', xy=(pcb_x + pcb_w, pcb_y + 0.22),
                xytext=(lbl_x, pcb_y + 0.1), fontsize=7,
                color=ACCENT_ORANGE, fontfamily='monospace',
                arrowprops=dict(arrowstyle='->', color=ACCENT_ORANGE, lw=0.8))

    # (J1 connector removed — antenna symbol at end of filter chain represents it)

    # ===== INPUT FILTER (below PCB, suspended in air, outside ALU shield) =====
    # Chain flows RIGHT to LEFT: antenna(right) → C2 → R2 → C1 → R1 → output(left)
    # Output on left goes up through PCB into Comp 1 (INPUT)
    filt_y = 2.0
    ax.text(pcb_x + pcb_w / 2, filt_y + 1.3,
            'INPUT FILTER  —  suspended in air, outside ALU shield',
            fontsize=8, fontweight='bold', ha='center', color=ACCENT_BLUE,
            fontfamily='monospace')

    # Components positioned right-to-left (antenna→C2→R2→C1→R1→output)
    r1_x = pcb_x + 2.0       # R1 (closest to output/LMP7721)
    c1_x = pcb_x + 4.5       # C1
    r2_x = pcb_x + 7.0       # R2
    c2_x = pcb_x + 9.5       # C2 (closest to antenna)

    for rx in [r1_x, r2_x]:
        r = FancyBboxPatch((rx - 0.5, filt_y - 0.3), 1.0, 0.6,
                            boxstyle='round,pad=0.03',
                            facecolor='#1a2b15', edgecolor=ACCENT_GREEN, linewidth=1.5)
        ax.add_patch(r)
        ax.text(rx, filt_y, '33k', fontsize=7, ha='center', va='center',
                color=ACCENT_GREEN, fontweight='bold', fontfamily='monospace')

    for capx, label in [(c1_x, 'Air Cap 1'), (c2_x, 'Air Cap 2')]:
        cap = FancyBboxPatch((capx - 0.7, filt_y - 0.35), 1.4, 0.7,
                              boxstyle='round,pad=0.03',
                              facecolor='#2a1800', edgecolor=ACCENT_ORANGE, linewidth=1.5)
        ax.add_patch(cap)
        ax.text(capx, filt_y, label, fontsize=6, ha='center', va='center',
                color=ACCENT_ORANGE, fontfamily='monospace')

    # Wires connecting filter components (left to right)
    # output ← R1 ← C1 ← R2 ← C2 ← antenna
    filt_out_x = pcb_x + 0.8
    ax.plot([filt_out_x, r1_x - 0.5], [filt_y, filt_y], color=TEXT_COLOR, linewidth=1)
    ax.plot([r1_x + 0.5, c1_x - 0.7], [filt_y, filt_y], color=TEXT_COLOR, linewidth=1)
    ax.plot([c1_x + 0.7, r2_x - 0.5], [filt_y, filt_y], color=TEXT_COLOR, linewidth=1)
    ax.plot([r2_x + 0.5, c2_x - 0.7], [filt_y, filt_y], color=TEXT_COLOR, linewidth=1)
    ax.plot([c2_x + 0.7, pcb_x + 11.0], [filt_y, filt_y], color=TEXT_COLOR, linewidth=1)

    # Filter output wire goes UP through PCB into Comp 1 (left side)
    ax.plot([filt_out_x, filt_out_x], [filt_y, pcb_y + 0.15],
            color=TEXT_COLOR, linewidth=1)
    ax.annotate('', xy=(filt_out_x, pcb_y + pcb_h + 0.15),
                xytext=(filt_out_x, pcb_y + 0.15),
                arrowprops=dict(arrowstyle='->', color=ACCENT_BLUE, lw=1.5,
                                linestyle='--'))
    ax.text(filt_out_x + 0.3, pcb_y - 0.3, 'to LMP7721', fontsize=6,
            color=ACCENT_BLUE, fontfamily='monospace', alpha=0.7)

    # Antenna symbol (Y shape) at the right end of the filter chain
    ant_x = pcb_x + 11.0
    ant_base = filt_y + 0.1
    ant_mid = ant_base + 0.8
    ant_top = ant_base + 1.5
    ax.plot([ant_x, ant_x], [ant_base, ant_mid], color=TEXT_COLOR, linewidth=1.5)
    ax.plot([ant_x, ant_x], [ant_mid, ant_top], color=TEXT_COLOR, linewidth=1.5)
    ax.plot([ant_x, ant_x - 0.5], [ant_mid, ant_top], color=TEXT_COLOR, linewidth=1.5)
    ax.plot([ant_x, ant_x + 0.5], [ant_mid, ant_top], color=TEXT_COLOR, linewidth=1.5)

    save(fig, '02_pcb_cross_section.svg')


def draw_signal_chain():
    """Signal chain block diagram with noise figures."""
    fig, ax = plt.subplots(figsize=(18, 6))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 6)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor(BG_COLOR)

    ax.text(9, 5.5, 'ELARA — Signal Chain', fontsize=16, fontweight='bold',
            ha='center', color=TEXT_COLOR, fontfamily='monospace')

    blocks = [
        ('T-Antenna\n~140pF', ACCENT_ORANGE, 0.5, 'E-field\ncoupling'),
        ('RC Filter\n2×33kΩ+50pF', ACCENT_BLUE, 3.0, 'fc~96.5kHz\nFM: -121dB'),
        ('LMP7721\nBuffer', ACCENT_RED, 5.5, '6.5 nV/√Hz\n0.01 fA/√Hz'),
        ('Anti-alias\nLPF', ACCENT_YELLOW, 8.0, 'passive RC\nfc=159Hz'),
        ('PCM1804\n24-bit ADC', ACCENT_GREEN, 10.5, '112dB DR\n192kSPS'),
        ('CS8406\nSPDIF TX', ACCENT_GREEN, 13.0, 'AES/EBU\n110Ω bal.'),
        ('USB Audio\nCard (PC)', ACCENT_BLUE, 15.5, 'off the\nshelf'),
    ]

    for i, (label, color, x, note) in enumerate(blocks):
        box = FancyBboxPatch((x, 2.2), 2.0, 1.6, boxstyle='round,pad=0.1',
                              facecolor=PANEL_COLOR, edgecolor=color, linewidth=2)
        ax.add_patch(box)
        ax.text(x + 1.0, 3.3, label, fontsize=7, ha='center', va='center',
                color=color, fontweight='bold', fontfamily='monospace')
        ax.text(x + 1.0, 1.7, note, fontsize=6, ha='center',
                color=SUBTLE_COLOR, fontfamily='monospace')

        if i < len(blocks) - 1:
            next_x = blocks[i + 1][2]
            ax.annotate('', xy=(next_x, 3.0), xytext=(x + 2.0, 3.0),
                        arrowprops=dict(arrowstyle='->', color=SUBTLE_COLOR, lw=1.5))

    # Zone labels
    ax.plot([0.3, 5.3], [4.5, 4.5], color=ACCENT_ORANGE, linewidth=1, alpha=0.3)
    ax.text(2.8, 4.7, 'IN AIR (unshielded)', fontsize=7, ha='center',
            color=ACCENT_ORANGE, fontfamily='monospace', alpha=0.6)

    ax.plot([5.3, 8.5], [4.5, 4.5], color=ACCENT_RED, linewidth=1, alpha=0.3)
    ax.text(6.9, 4.7, 'COMP.1+2 (analog)', fontsize=7, ha='center',
            color=ACCENT_RED, fontfamily='monospace', alpha=0.6)

    ax.plot([8.5, 14.8], [4.5, 4.5], color=ACCENT_GREEN, linewidth=1, alpha=0.3)
    ax.text(11.6, 4.7, 'COMP.3 (digital)', fontsize=7, ha='center',
            color=ACCENT_GREEN, fontfamily='monospace', alpha=0.6)

    ax.plot([14.8, 17.7], [4.5, 4.5], color=ACCENT_BLUE, linewidth=1, alpha=0.3)
    ax.text(16.2, 4.7, 'INDOOR', fontsize=7, ha='center',
            color=ACCENT_BLUE, fontfamily='monospace', alpha=0.6)

    # Cable annotation
    ax.text(14.6, 3.0, '~100m STP cable', fontsize=7, ha='center',
            color=SUBTLE_COLOR, fontfamily='monospace')

    save(fig, '03_signal_chain.svg')


def draw_noise_comparison():
    """Noise comparison: ELARA vs Romero."""
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(PANEL_COLOR)

    C_ant = 140e-12
    f = np.logspace(0, np.log10(22000), 2000)
    Z_ant = 1.0 / (2.0 * np.pi * f * C_ant)

    amps = {
        'LMP7721 (ELARA)': {'en': 6.5e-9, 'in': 0.01e-15, 'color': ACCENT_GREEN, 'lw': 3},
        'ADA4530-1': {'en': 14e-9, 'in': 0.02e-15, 'color': ACCENT_BLUE, 'lw': 1.5},
        'AD820 (Romero)': {'en': 16e-9, 'in': 0.8e-15, 'color': ACCENT_PURPLE, 'lw': 2},
        'OP27 (BJT — wrong!)': {'en': 3e-9, 'in': 1000e-15, 'color': ACCENT_RED, 'lw': 1.5},
    }

    i_pcb = 0.1e-15

    for name, amp in amps.items():
        e_total = np.sqrt(amp['en'] ** 2 + (amp['in'] * Z_ant) ** 2 + (i_pcb * Z_ant) ** 2)
        ax.loglog(f, e_total * 1e9, label=name, color=amp['color'],
                  linewidth=amp['lw'])

    schumann = [(7.83, 'SR1'), (14.3, 'SR2'), (20.8, 'SR3'), (27.3, 'SR4'), (33.8, 'SR5')]
    for freq, name in schumann:
        ax.axvline(freq, color=ACCENT_BLUE, alpha=0.15, linewidth=0.8, linestyle='--')
        ax.text(freq, 0.8, name, fontsize=7, ha='center', color=ACCENT_BLUE,
                fontfamily='monospace', alpha=0.5)

    ax.set_xlabel('Frequency (Hz)', fontsize=11, color=TEXT_COLOR, fontfamily='monospace')
    ax.set_ylabel('Input-referred noise (nV/√Hz)', fontsize=11, color=TEXT_COLOR,
                  fontfamily='monospace')
    ax.set_title('ELARA — Noise Floor Comparison (C_ant = 140 pF, guarded PCB)',
                 fontsize=13, fontweight='bold', color=TEXT_COLOR, fontfamily='monospace',
                 pad=15)
    ax.set_xlim(1, 22000)
    ax.set_ylim(0.5, 50000)

    legend = ax.legend(loc='upper right', fontsize=9, facecolor=PANEL_COLOR,
                       edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR)
    legend.get_frame().set_alpha(0.9)

    ax.tick_params(colors=SUBTLE_COLOR)
    ax.grid(True, which='both', alpha=0.15, color=SUBTLE_COLOR)
    for spine in ax.spines.values():
        spine.set_color(BORDER_COLOR)

    # Improvement annotation (computed at SR1 from the plotted model)
    idx = int(np.argmin(np.abs(f - 7.83)))
    e_lmp = np.sqrt(amps['LMP7721 (ELARA)']['en'] ** 2
                    + (amps['LMP7721 (ELARA)']['in'] * Z_ant[idx]) ** 2
                    + (i_pcb * Z_ant[idx]) ** 2)
    e_820 = np.sqrt(amps['AD820 (Romero)']['en'] ** 2
                    + (amps['AD820 (Romero)']['in'] * Z_ant[idx]) ** 2
                    + (i_pcb * Z_ant[idx]) ** 2)
    ratio = e_820 / e_lmp
    ax.annotate(f'~{ratio:.0f}× improvement\nat 7.83 Hz',
                xy=(7.83, e_lmp * 1e9), xytext=(40, 200),
                fontsize=9, color=ACCENT_GREEN, fontfamily='monospace',
                fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=ACCENT_GREEN, lw=1.5))

    plt.tight_layout()
    save(fig, '04_noise_comparison.svg')


if __name__ == '__main__':
    print('Generating ELARA diagrams...')
    draw_system_overview()
    draw_pcb_cross_section()
    draw_signal_chain()
    draw_noise_comparison()
    print('Done!')
