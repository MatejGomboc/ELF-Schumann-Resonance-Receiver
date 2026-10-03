"""JLCPCB standard-process limits as KiCad design rules.

Board.save() writes them on every generated board: the board minimums go into
the project file (Board Setup > Constraints) and the rules KiCad cannot express
there go into <board>.kicad_dru next to it. Every DRC run (tools/check_all.sh,
kicad-cli, the GUI) then checks the copper, holes, mask and silkscreen against
what JLCPCB builds without a surcharge.

Figures: JLCPCB "PCB Manufacturing & Assembly Capabilities", standard FR4,
1 oz outer and 0.5 oz inner copper, as published in October 2026 (via search
snippets of jlcpcb.com/capabilities/pcb-capabilities and the JLCPCB blog pages
on solder mask, silkscreen and slots):

  track / gap            0.10 / 0.10 mm (1-2 layers), 0.09 / 0.09 mm (4+ layers)
  drill                  0.15-6.3 mm; 0.3 mm is the no-surcharge via drill used here
  via ring               via pad 0.1 mm (0.15 preferred) larger than the drill
  PTH annular ring       0.18 mm (2 layers), 0.15 mm (multilayer) absolute minimum
  NPTH                   0.5 mm minimum
  hole to hole           0.5 mm (different nets), 0.254 mm (same net)
  inner hole to copper   0.2 mm (via), 0.3 mm (PTH pad)
  copper to routed edge  0.2 mm (0.4 mm V-cut)
  mask dam               0.10 mm (green, red, yellow, blue, purple), 0.13 mm (black,
                         white), 1 oz; openings 1:1 with the pads (LDI)
  silkscreen             lines and text strokes 6 mil (0.15 mm), text 1.0 mm high
                         (0.8 mm absolute); 0.15 mm clear of the mask openings

The rules below use the 0.13 mm dam so that any mask colour can be ordered, and
keep the 0.5 mm copper-to-edge distance the boards were laid out with (the
router tolerance is +-0.2 mm). KiCad has no DRC rule for the width of silkscreen
lines: Board.silk_for_fab() widens the footprint outlines to 0.15 mm and cuts them
back from the pads, and the board texts are made at 0.15 mm stroke or more.
"""

import json
import os

MASK_DAM = 0.13          # mm, any colour; 0.10 for green
EDGE = 0.5               # mm, copper to the routed outline (JLCPCB: 0.2)
SILK_W = 0.15            # mm, legend lines (JLCPCB: 6 mil; KiCad's library draws 0.12)
SILK_GAP = 0.15          # mm, legend to mask openings


def board_minimums(layers):
    """Board Setup > Constraints, in mm (the project file's 'rules' table)."""
    return {
        'min_clearance': 0.10 if layers <= 2 else 0.09,
        'min_track_width': 0.10 if layers <= 2 else 0.09,
        'min_connection': 0.10,
        'min_copper_edge_clearance': EDGE,
        'min_through_hole_diameter': 0.3,
        'min_hole_to_hole': 0.254,
        'min_hole_clearance': 0.2,
        'min_via_diameter': 0.5,
        'min_via_annular_width': 0.075,
        'min_microvia_diameter': 0.2,
        'min_microvia_drill': 0.1,
        'min_silk_clearance': 0.0,          # silk-to-pad is in the custom rules
        'min_text_height': 1.0,
        'min_text_thickness': 0.15,
    }


def custom_rules(layers):
    """Rules for the .kicad_dru file (KiCad custom rule syntax)."""
    ring = 0.18 if layers <= 2 else 0.15
    rules = [
        ('PTH pad annular ring (JLCPCB %d-layer)' % layers,
         None, "A.Type == 'Pad' && A.isPlated()",
         '(constraint annular_width (min %.3fmm))' % ring),
        ('Via annular ring, 0.15 mm larger pad preferred',
         None, "A.Type == 'Via'",
         '(constraint annular_width (min 0.075mm))'),
        ('Drill range', None, "A.Type == 'Pad' || A.Type == 'Via'",
         '(constraint hole_size (min 0.3mm) (max 6.3mm))'),
        ('NPTH minimum', None, "A.Type == 'Pad' && !A.isPlated()",
         '(constraint hole_size (min 0.5mm))'),
        ('Hole to hole, different nets', None, 'A.Net != B.Net',
         '(constraint hole_to_hole (min 0.5mm))'),
        # KiCad tests silk against the mask openings on the mask layer, so the rule is
        # scoped there; scoped to the silk layer it would also space silk from silk
        ('Silkscreen clear of mask openings', '"?.Mask"', None,
         '(constraint silk_clearance (min 0.15mm))'),
        ('Silkscreen text', '"?.Silkscreen"', "A.Type == 'Text' || A.Type == 'Text Box'",
         '(constraint text_height (min 1.0mm)) (constraint text_thickness (min 0.15mm))'),
    ]
    if layers > 2:
        rules.append(('Inner layers: PTH pad hole to copper', 'inner',
                      "A.Type == 'Pad' && A.isPlated() && A.Net != B.Net",
                      '(constraint hole_clearance (min 0.3mm))'))
    out = ['(version 1)',
           '# JLCPCB standard-process limits, written by tools/kicadgen/fabrules.py on every',
           '# board save. Do not edit: change fabrules.py and re-run the layout script.']
    for name, layer, cond, cons in rules:
        out.append(f'(rule "{name}"')
        if layer:
            out.append(f'\t(layer {layer})')
        if cond:
            out.append(f'\t(condition "{cond}")')
        out.append(f'\t{cons})')
    return '\n'.join(out) + '\n'


# The generator adapts library footprints to these limits (silk widened and cut back
# from the pads, kicadgen.pcb.Board.silk_for_fab), so "footprint differs from the
# library" is expected on every board and is not reported. Pads always come from the
# library or from the elara variants (tools/fp_variants.py), never from hand edits.
SEVERITIES = {'lib_footprint_mismatch': 'ignore'}


def write(pcb_path, layers, severities=None, extra_rules=''):
    """Write the project-file minimums (and any rule severities) and the .kicad_dru
    (the fab rules, then any board-specific rules)."""
    base = os.path.splitext(pcb_path)[0]
    pro = base + '.kicad_pro'
    with open(pro, encoding='utf-8') as f:
        d = json.load(f)
    ds = d.setdefault('board', {}).setdefault('design_settings', {})
    ds.setdefault('rules', {}).update(board_minimums(layers))
    ds.setdefault('rule_severities', {}).update(dict(SEVERITIES, **(severities or {})))
    with open(pro, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=2)
    with open(base + '.kicad_dru', 'w', encoding='utf-8') as f:
        f.write(custom_rules(layers) + extra_rules)
