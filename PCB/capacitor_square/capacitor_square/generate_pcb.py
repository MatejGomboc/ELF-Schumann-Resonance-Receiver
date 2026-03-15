#!/usr/bin/env python3
"""
ELARA — Parametric PCB Capacitor Generator (KiCad 9.0)

Generates a .kicad_pcb file for a square parallel-plate capacitor formed
by copper pours on top and bottom of a PCB substrate.

Physical structure:
    - Square board (Edge.Cuts)
    - F.Cu: solid copper plate (top), pulled back from edges
    - B.Cu: solid copper plate (bottom), pulled back from edges
    - Solder mask covers both plates (default KiCad behaviour)
    - Small mask openings at centre of each plate for wire soldering
    - No vias, no through-holes, no traces

Usage:
    python generate_pcb.py                          # defaults: FR4, 0.8mm, 10pF
    python generate_pcb.py --thickness 0.6          # thinner FR4
    python generate_pcb.py --target-pf 5            # smaller cap
    python generate_pcb.py --side 13.5 --thickness 0.508 --epsilon-r 3.66  # Rogers

Run from the project directory. Overwrites capacitor_square.kicad_pcb.

JLCPCB constraints respected:
    - Min board size: 3x3 mm (for thickness >= 0.6 mm)
    - Copper to board edge: >= 0.2 mm
    - FR4 thicknesses: 0.4 / 0.6 / 0.8 / 1.0 / 1.2 / 1.6 / 2.0 mm
    - Dimension tolerance: +/- 0.2 mm (regular), +/- 0.1 mm (precision)
    - Thickness tolerance: +/- 0.1 mm (< 1.0 mm), +/- 10% (>= 1.0 mm)
"""

import argparse
import math
import os
import uuid


# ============================================================================
# Physical constants
# ============================================================================
EPSILON_0 = 8.854187817e-12  # vacuum permittivity (F/m)
R_FILTER = 1.0e6             # filter resistor (1 Mohm)
CASCADE_FACTOR = math.sqrt(math.sqrt(2) - 1)  # 2-stage cascade correction


# ============================================================================
# Calculations
# ============================================================================
def capacitance_pf(side_mm, pullback_mm, thickness_mm, epsilon_r):
    """Parallel-plate capacitance in pF."""
    copper_side_m = (side_mm - 2.0 * pullback_mm) * 1e-3
    if copper_side_m <= 0:
        return 0.0
    return EPSILON_0 * epsilon_r * copper_side_m ** 2 / (thickness_mm * 1e-3) * 1e12


def side_for_target_c(target_pf, pullback_mm, thickness_mm, epsilon_r):
    """Board side length (mm) for a target capacitance."""
    c_f = target_pf * 1e-12
    d_m = thickness_mm * 1e-3
    copper_side_m = math.sqrt(c_f * d_m / (EPSILON_0 * epsilon_r))
    return copper_side_m * 1e3 + 2.0 * pullback_mm


def fc_single_khz(c_pf):
    """Single-stage RC cutoff in kHz."""
    if c_pf <= 0:
        return float("inf")
    return 1.0 / (2.0 * math.pi * R_FILTER * c_pf * 1e-12) * 1e-3


def fc_cascade_khz(c_pf):
    """2-stage cascade -3 dB point in kHz."""
    return fc_single_khz(c_pf) * CASCADE_FACTOR


# ============================================================================
# UUID helper
# ============================================================================
def uid():
    return str(uuid.uuid4())


# ============================================================================
# KiCad 9.0 PCB generation
# ============================================================================
def generate_pcb(side, pullback, pad_size, thickness, epsilon_r, substrate):
    """Return KiCad 9.0 .kicad_pcb S-expression string."""

    half = side / 2.0
    cu_half = half - pullback
    pad_half = pad_size / 2.0
    cap_pf = capacitance_pf(side, pullback, thickness, epsilon_r)
    copper_side = side - 2 * pullback

    # Validate JLCPCB constraints
    if side < 3.0:
        raise ValueError(f"Board side {side:.1f} mm < JLCPCB minimum 3 mm")
    if pullback < 0.2:
        raise ValueError(f"Pullback {pullback:.1f} mm < JLCPCB minimum 0.2 mm "
                         f"copper-to-edge clearance")
    if pad_size > copper_side:
        raise ValueError(f"Pad size {pad_size:.1f} mm > copper area {copper_side:.1f} mm")

    # Format values for silkscreen
    cap_str = f"{cap_pf:.1f}pF" if cap_pf >= 1.0 else f"{cap_pf * 1000:.0f}fF"
    fc_str = f"fc={fc_cascade_khz(cap_pf):.1f}kHz"

    # Silkscreen text size scales with board
    text_size = min(1.2, side / 12.0)
    text_thickness = text_size * 0.15

    lines = []
    lines.append(f'(kicad_pcb')
    lines.append(f'  (version 20241229)')
    lines.append(f'  (generator "generate_pcb.py")')
    lines.append(f'  (generator_version "9.0")')
    lines.append(f'  (general')
    lines.append(f'    (thickness {thickness})')
    lines.append(f'    (legacy_teardrops no)')
    lines.append(f'  )')
    lines.append(f'  (paper "A4")')
    lines.append(f'  (layers')
    lines.append(f'    (0 "F.Cu" signal)')
    lines.append(f'    (31 "B.Cu" signal)')
    lines.append(f'    (32 "B.Adhes" user "B.Adhesive")')
    lines.append(f'    (33 "F.Adhes" user "F.Adhesive")')
    lines.append(f'    (34 "B.Paste" user)')
    lines.append(f'    (35 "F.Paste" user)')
    lines.append(f'    (36 "B.SilkS" user "B.Silkscreen")')
    lines.append(f'    (37 "F.SilkS" user "F.Silkscreen")')
    lines.append(f'    (38 "B.Mask" user "B.Mask")')
    lines.append(f'    (39 "F.Mask" user "F.Mask")')
    lines.append(f'    (40 "Dwgs.User" user "User.Drawings")')
    lines.append(f'    (41 "Cmts.User" user "User.Comments")')
    lines.append(f'    (42 "Eco1.User" user "User.Eco1")')
    lines.append(f'    (43 "Eco2.User" user "User.Eco2")')
    lines.append(f'    (44 "Edge.Cuts" user)')
    lines.append(f'    (45 "Margin" user)')
    lines.append(f'    (46 "B.CrtYd" user "B.Courtyard")')
    lines.append(f'    (47 "F.CrtYd" user "F.Courtyard")')
    lines.append(f'    (48 "B.Fab" user "B.Fabrication")')
    lines.append(f'    (49 "F.Fab" user "F.Fabrication")')
    lines.append(f'  )')

    # Setup with design rules
    lines.append(f'  (setup')
    lines.append(f'    (pad_to_mask_clearance 0)')
    lines.append(f'    (allow_soldermask_bridges_in_footprints no)')
    lines.append(f'    (pcbplotparams')
    lines.append(f'      (layerselection 0x00010fc_ffffffff)')
    lines.append(f'      (plot_on_all_layers_selection 0x0000000_00000000)')
    lines.append(f'      (disableapertmacros no)')
    lines.append(f'      (usegerberextensions no)')
    lines.append(f'      (usegerberattributes yes)')
    lines.append(f'      (usegerberadvancedattributes yes)')
    lines.append(f'      (creategerberjobfile yes)')
    lines.append(f'      (dashed_line_dash_ratio 12.000000)')
    lines.append(f'      (dashed_line_gap_ratio 3.000000)')
    lines.append(f'      (svgprecision 4)')
    lines.append(f'      (plotframeref no)')
    lines.append(f'      (viasonmask no)')
    lines.append(f'      (mode 1)')
    lines.append(f'      (useauxorigin no)')
    lines.append(f'      (hpglpennumber 1)')
    lines.append(f'      (hpglpenspeed 20)')
    lines.append(f'      (hpglpendiameter 15.000000)')
    lines.append(f'      (pdf_front_fp_property_popups yes)')
    lines.append(f'      (pdf_back_fp_property_popups yes)')
    lines.append(f'      (dxfpolygonmode yes)')
    lines.append(f'      (dxfimperialunits yes)')
    lines.append(f'      (dxfusepcbnewfont yes)')
    lines.append(f'      (psnegative no)')
    lines.append(f'      (psa4output no)')
    lines.append(f'      (plotreference yes)')
    lines.append(f'      (plotvalue yes)')
    lines.append(f'      (plotfptext yes)')
    lines.append(f'      (plotinvisibletext no)')
    lines.append(f'      (sketchpadsonfab no)')
    lines.append(f'      (subtractmaskfromsilk no)')
    lines.append(f'      (outputformat 1)')
    lines.append(f'      (mirror no)')
    lines.append(f'      (drillshape 1)')
    lines.append(f'      (scaleselection 1)')
    lines.append(f'      (outputdirectory "")')
    lines.append(f'    )')
    lines.append(f'  )')

    # Nets (none needed — graphical copper only)
    lines.append(f'  (net 0 "")')

    # ---- Board outline (Edge.Cuts) ----
    lines.append(f'')
    lines.append(f'  ; Board outline — {side:.2f} x {side:.2f} mm')
    lines.append(f'  (gr_rect')
    lines.append(f'    (start {-half:.4f} {-half:.4f})')
    lines.append(f'    (end {half:.4f} {half:.4f})')
    lines.append(f'    (stroke (width 0.05) (type solid))')
    lines.append(f'    (fill none)')
    lines.append(f'    (layer "Edge.Cuts")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'  )')

    # ---- Top copper plate (F.Cu) ----
    lines.append(f'')
    lines.append(f'  ; Top capacitor plate — {copper_side:.2f} x {copper_side:.2f} mm '
                 f'(pullback {pullback:.2f} mm)')
    lines.append(f'  (gr_rect')
    lines.append(f'    (start {-cu_half:.4f} {-cu_half:.4f})')
    lines.append(f'    (end {cu_half:.4f} {cu_half:.4f})')
    lines.append(f'    (stroke (width 0) (type solid))')
    lines.append(f'    (fill solid)')
    lines.append(f'    (layer "F.Cu")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'  )')

    # ---- Bottom copper plate (B.Cu) ----
    lines.append(f'')
    lines.append(f'  ; Bottom capacitor plate — {copper_side:.2f} x {copper_side:.2f} mm')
    lines.append(f'  (gr_rect')
    lines.append(f'    (start {-cu_half:.4f} {-cu_half:.4f})')
    lines.append(f'    (end {cu_half:.4f} {cu_half:.4f})')
    lines.append(f'    (stroke (width 0) (type solid))')
    lines.append(f'    (fill solid)')
    lines.append(f'    (layer "B.Cu")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'  )')

    # ---- Solder mask opening on top (F.Mask) — wire solder pad ----
    lines.append(f'')
    lines.append(f'  ; Top solder mask opening — {pad_size:.1f} x {pad_size:.1f} mm '
                 f'(wire attachment point)')
    lines.append(f'  (gr_rect')
    lines.append(f'    (start {-pad_half:.4f} {-pad_half:.4f})')
    lines.append(f'    (end {pad_half:.4f} {pad_half:.4f})')
    lines.append(f'    (stroke (width 0) (type solid))')
    lines.append(f'    (fill solid)')
    lines.append(f'    (layer "F.Mask")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'  )')

    # ---- Solder mask opening on bottom (B.Mask) — wire solder pad ----
    lines.append(f'')
    lines.append(f'  ; Bottom solder mask opening — {pad_size:.1f} x {pad_size:.1f} mm')
    lines.append(f'  (gr_rect')
    lines.append(f'    (start {-pad_half:.4f} {-pad_half:.4f})')
    lines.append(f'    (end {pad_half:.4f} {pad_half:.4f})')
    lines.append(f'    (stroke (width 0) (type solid))')
    lines.append(f'    (fill solid)')
    lines.append(f'    (layer "B.Mask")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'  )')

    # ---- Front silkscreen labels ----
    lines.append(f'')
    lines.append(f'  ; Front silkscreen — capacitor value and project')
    lines.append(f'  (gr_text "ELARA"')
    lines.append(f'    (at 0 {-cu_half + text_size:.4f})')
    lines.append(f'    (layer "F.SilkS")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'    (effects')
    lines.append(f'      (font (size {text_size:.2f} {text_size:.2f}) '
                 f'(thickness {text_thickness:.3f}))')
    lines.append(f'      (justify center)')
    lines.append(f'    )')
    lines.append(f'  )')

    lines.append(f'  (gr_text "{cap_str}"')
    lines.append(f'    (at 0 {cu_half - text_size:.4f})')
    lines.append(f'    (layer "F.SilkS")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'    (effects')
    lines.append(f'      (font (size {text_size:.2f} {text_size:.2f}) '
                 f'(thickness {text_thickness:.3f}))')
    lines.append(f'      (justify center)')
    lines.append(f'    )')
    lines.append(f'  )')

    # ---- Back silkscreen ----
    lines.append(f'')
    lines.append(f'  ; Back silkscreen')
    lines.append(f'  (gr_text "GND"')
    lines.append(f'    (at 0 0)')
    lines.append(f'    (layer "B.SilkS")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'    (effects')
    lines.append(f'      (font (size {text_size:.2f} {text_size:.2f}) '
                 f'(thickness {text_thickness:.3f}))')
    lines.append(f'      (justify center mirror)')
    lines.append(f'    )')
    lines.append(f'  )')

    # ---- Fabrication layer — board dimensions ----
    lines.append(f'')
    lines.append(f'  ; Fabrication notes')
    fab_text = (f"{side:.2f} x {side:.2f} mm, {substrate} {thickness:.2f} mm, "
                f"{cap_str}")
    lines.append(f'  (gr_text "{fab_text}"')
    lines.append(f'    (at 0 {half + 2:.4f})')
    lines.append(f'    (layer "F.Fab")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'    (effects')
    lines.append(f'      (font (size 1.0 1.0) (thickness 0.15))')
    lines.append(f'      (justify center)')
    lines.append(f'    )')
    lines.append(f'  )')

    # ---- Courtyard ----
    margin = 0.25
    lines.append(f'')
    lines.append(f'  ; Courtyard')
    lines.append(f'  (gr_rect')
    lines.append(f'    (start {-half - margin:.4f} {-half - margin:.4f})')
    lines.append(f'    (end {half + margin:.4f} {half + margin:.4f})')
    lines.append(f'    (stroke (width 0.05) (type solid))')
    lines.append(f'    (fill none)')
    lines.append(f'    (layer "F.CrtYd")')
    lines.append(f'    (uuid "{uid()}")')
    lines.append(f'  )')

    lines.append(f')')
    return "\n".join(lines)


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="ELARA — Parametric PCB Capacitor Generator (KiCad 9.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_pcb.py                                    # FR4 0.8mm, 10pF
  python generate_pcb.py --thickness 0.6                    # thinner FR4
  python generate_pcb.py --target-pf 5                      # 5 pF cap
  python generate_pcb.py --side 13.5 --thickness 0.508 \\
         --epsilon-r 3.66 --substrate "Rogers 4350B"        # Rogers
  python generate_pcb.py --side 8.8 --thickness 0.5 \\
         --epsilon-r 9.4 --substrate "Alumina"              # Alumina

JLCPCB standard FR4 thicknesses: 0.4 / 0.6 / 0.8 / 1.0 / 1.2 / 1.6 / 2.0 mm
        """,
    )
    parser.add_argument("--side", type=float, default=None,
                        help="Board side length in mm (auto-calculated if omitted)")
    parser.add_argument("--pullback", type=float, default=0.5,
                        help="Copper setback from board edge in mm (default: 0.5, "
                             "JLCPCB min: 0.2)")
    parser.add_argument("--pad-size", type=float, default=2.0,
                        help="Exposed solder pad size in mm (default: 2.0)")
    parser.add_argument("--thickness", type=float, default=0.8,
                        help="Substrate thickness in mm (default: 0.8)")
    parser.add_argument("--epsilon-r", type=float, default=4.5,
                        help="Relative permittivity (default: 4.5 for FR4)")
    parser.add_argument("--target-pf", type=float, default=10.0,
                        help="Target capacitance in pF (default: 10.0, used when "
                             "--side is not specified)")
    parser.add_argument("--substrate", type=str, default="FR4",
                        help="Substrate name for labelling (default: FR4)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output .kicad_pcb path (default: capacitor_square.kicad_pcb)")
    args = parser.parse_args()

    # Auto-calculate side if not specified
    if args.side is None:
        args.side = side_for_target_c(
            args.target_pf, args.pullback, args.thickness, args.epsilon_r
        )
        # Round up to nearest 0.1 mm for manufacturability
        args.side = math.ceil(args.side * 10) / 10.0
        print(f"Auto-calculated board side: {args.side:.1f} mm "
              f"(for {args.target_pf:.1f} pF target)")

    # Compute actual capacitance
    cap_pf = capacitance_pf(args.side, args.pullback, args.thickness, args.epsilon_r)
    copper_side = args.side - 2 * args.pullback
    fc1 = fc_single_khz(cap_pf)
    fc2 = fc_cascade_khz(cap_pf)

    # Print summary
    print(f"")
    print(f"  Substrate:       {args.substrate} (er = {args.epsilon_r})")
    print(f"  Thickness:       {args.thickness} mm")
    print(f"  Board side:      {args.side:.2f} mm")
    print(f"  Copper pullback: {args.pullback} mm")
    print(f"  Copper area:     {copper_side:.2f} x {copper_side:.2f} mm")
    print(f"  Solder pad:      {args.pad_size} x {args.pad_size} mm (centred)")
    print(f"  Capacitance:     {cap_pf:.2f} pF")
    print(f"  fc (1-stage):    {fc1:.2f} kHz")
    print(f"  fc (2-stage):    {fc2:.2f} kHz")

    # Thickness tolerance (JLCPCB)
    if args.thickness >= 1.0:
        tol = args.thickness * 0.1
        cap_min = capacitance_pf(args.side, args.pullback,
                                 args.thickness + tol, args.epsilon_r)
        cap_max = capacitance_pf(args.side, args.pullback,
                                 args.thickness - tol, args.epsilon_r)
    else:
        tol = 0.1
        cap_min = capacitance_pf(args.side, args.pullback,
                                 args.thickness + tol, args.epsilon_r)
        cap_max = capacitance_pf(args.side, args.pullback,
                                 args.thickness - tol, args.epsilon_r)
    dim_tol = 0.2  # JLCPCB regular routing tolerance
    cap_dim_min = capacitance_pf(args.side - dim_tol, args.pullback,
                                 args.thickness, args.epsilon_r)
    cap_dim_max = capacitance_pf(args.side + dim_tol, args.pullback,
                                 args.thickness, args.epsilon_r)

    print(f"")
    print(f"  JLCPCB tolerances:")
    print(f"    Thickness +/-{tol:.1f} mm:   {cap_min:.2f} .. {cap_max:.2f} pF")
    print(f"    Dimensions +/-{dim_tol:.1f} mm: {cap_dim_min:.2f} .. {cap_dim_max:.2f} pF")
    print(f"    Combined worst case:  {min(cap_min, cap_dim_min):.2f} .. "
          f"{max(cap_max, cap_dim_max):.2f} pF")

    # Generate PCB
    pcb_content = generate_pcb(
        args.side, args.pullback, args.pad_size,
        args.thickness, args.epsilon_r, args.substrate,
    )

    # Write output
    if args.output is None:
        args.output = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "capacitor_square.kicad_pcb",
        )
    with open(args.output, "w", newline="\n") as f:
        f.write(pcb_content)

    print(f"")
    print(f"  Written: {args.output}")
    print(f"  Open in KiCad to verify.")


if __name__ == "__main__":
    main()
