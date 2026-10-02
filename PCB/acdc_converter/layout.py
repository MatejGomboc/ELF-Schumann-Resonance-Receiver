#!/usr/bin/env python3
"""ELARA two-bucket PSU -- PCB layout generator (runs in KiCad's Python).

  kicad-py layout.py place    -> acdc_converter.kicad_pcb + .dsn
  kicad-py layout.py finish   -> imports acdc_converter.ses, pours, fills

Board 150 x 90 mm, 2 layers, left to right:
  MAINS (primary, >= 6.4 mm creepage) | CHARGER + TIMER (GND_C pour)
  | RELAYS + BUCKETS (no copper pour: minimum capacitance across the barrier)
  | RECEIVER SIDE (GND pour), output at the right.
Cable bays: J1's wire entry faces the mains gland across a 17 mm parts-free bay,
and J2's mating face looks at the output gland across a 24 mm free channel, so
both cables can be fitted inside the 3 mm wall clearance of the PSU box.
The LM317s lie tab-down on copper areas of their OUT nets (no heatsinks).
H2/H4 (receiver side) sit in 5 mm copper keep-outs: their standoffs are on PE.
"""

import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))

import json  # noqa: E402
import math  # noqa: E402

from kicadgen.pcb import Board, near, rect_pts  # noqa: E402

NAME = 'acdc_converter'
W, H = 150.0, 90.0
F, B = pcbnew.F_Cu, pcbnew.B_Cu
CHG_ZONE = (56.0, 1.0, 113.0, 47.0)
RX_ZONE = (118.0, 1.0, 149.0, 89.0)
PRIMARY = (1.0, 1.0, 50.0, 89.0)

PLACE = {
    'H1': (4.0, 4.0, 0), 'H2': (146.0, 4.0, 0), 'H3': (4.0, 86.0, 0), 'H4': (146.0, 86.0, 0),
    # primary: J1's wire entry faces -x (towards the mains gland) across the bay
    'J1': (22.0, 65.0, 270), 'F1': (35.0, 80.0, 90), 'RV1': (29.0, 59.7, 180),
    'PS1': (20.0, 52.0, 90), 'R1': (13.0, 4.5, 180),
    # charger: input caps and the 12 V rail above the module's DC end
    'C1': (40.0, 8.0, 0), 'C2': (40.5, 14.0, 0), 'U3': (42.0, 20.5, 0),
    'C4': (37.5, 26.5, 90), 'C5': (41.0, 26.5, 90), 'R5': (45.0, 26.5, 90), 'D2': (48.5, 26.5, 90),
    # LM317s tab-down (tab towards the top edge), pins on y = 25
    'U1': (58.0, 25.0, 0), 'R2': (60.5, 29.5, 0),
    'U2': (72.0, 25.0, 0), 'R4': (70.5, 29.5, 0), 'R3': (74.5, 29.5, 0), 'C3': (78.5, 29.5, 0),
    'D1': (85.0, 16.0, 90), 'R10': (90.0, 16.0, 90), 'R11': (94.5, 16.0, 90),
    # swap timer
    'U4': (86.0, 36.0, 0), 'C7': (80.5, 36.0, 90),
    'R7': (92.5, 31.0, 90), 'R6': (92.5, 36.0, 90), 'C6': (92.5, 41.0, 90),   # same order as U4 pins 11, 10, 9
    'R8': (97.0, 33.0, 0), 'R9': (97.0, 37.5, 90), 'Q1': (101.0, 40.0, 0),
    'D3': (74.0, 45.5, 0), 'D4': (104.0, 44.5, 0),
    # relays + buckets
    'K1': (82.0, 52.0, 0), 'K2': (99.0, 52.0, 0),
    'R12': (112.0, 52.0, 90), 'R13': (115.5, 58.0, 0),
    'C8': (58.0, 67.0, 0), 'C9': (71.5, 67.0, 0), 'C10': (85.0, 67.0, 0), 'C11': (98.5, 67.0, 0),
    'C12': (58.0, 81.0, 0), 'C13': (71.5, 81.0, 0), 'C14': (85.0, 81.0, 0), 'C15': (98.5, 81.0, 0),
    # receiver side: J2 faces +x (towards the output gland) across the plug channel
    'J2': (119.5, 18.0, 270), 'D5': (124.0, 31.0, 0), 'L1': (134.0, 40.0, 0),
    'C16': (122.5, 70.0, 0), 'C17': (131.0, 80.5, 90),
    'U5': (132.0, 60.0, 0), 'R22': (127.0, 52.0, 90), 'C18': (131.0, 52.0, 90), 'C19': (138.0, 60.0, 90),
}
# parts-free cable bays (rule areas: no footprints)
BAYS = {'mains bay': (0.5, 57.0, 16.5, 81.5), 'output bay': (129.5, 12.0, 149.5, 27.0)}
ISO_HOLES = ('H2', 'H4')          # receiver side: standoffs are on PE, keep copper 5 mm away
ISO_R = 5.0
# balancing resistors on the bottom side, under their cells
BOTTOM = {f'R{14 + i}': (60.5 + (i % 4) * 13.5, 67.0 if i < 4 else 81.0, 90) for i in range(8)}


def stage_place():
    b = Board(os.path.join(HERE, 'design_netlist.json'), {'elara': os.path.join(HERE, '..', 'elara.pretty')},
              os.path.join(HERE, f'{NAME}.kicad_pcb'), layers=2)
    b.outline(W, H)
    b.title_block('ELARA two-bucket PSU', '0.2', date='2026-09-30')
    for ref, (x, y, r) in PLACE.items():
        b.place(ref, x, y, r)
    for ref, (x, y, r) in BOTTOM.items():
        b.place(ref, x, y, r, side='B')
    missing = b.unplaced()
    if missing:
        raise SystemExit(f'unplaced: {missing}')
    # PE: a hand-routed 1 mm rail along the left edge (terminal PE pin, both PE
    # holes, the GND_C bond resistor)
    pe, h1, h3, r1 = b.pad_xy('J1', 3), b.pad_xy('H1', 1), b.pad_xy('H3', 1), b.pad_xy('R1', 2)
    b.track('PE', [h3, (2.5, h3[1] - 3.0), (2.5, h1[1] + 3.0), h1], width=1.0, layer=B)
    b.track('PE', [pe, (2.5, pe[1])], width=1.0, layer=B)
    b.track('PE', [r1, (h1[0], r1[1])], width=1.0, layer=F)
    # mains, hand-routed on B.Cu so L and N never cross and keep >= 2.5 mm apart:
    # L_IN round the back of J1 to the fuse's lower clip; fused AC_L from the upper
    # clip over the MOV to the module; N in front of J1 to the MOV and the module
    jl, jn = b.pad_xy('J1', 1), b.pad_xy('J1', 2)
    fl = sorted(p for p in pads(b, 'F1', '1'))          # lower clip (L_IN), two pads
    fa = sorted(p for p in pads(b, 'F1', '2'))          # upper clip (AC_L)
    rl, rn = b.pad_xy('RV1', 1), b.pad_xy('RV1', 2)
    pl, pn = b.pad_xy('PS1', 2), b.pad_xy('PS1', 1)
    xr = jl[0] + 7.8                                    # between J1's rear and the fuse
    b.track('L_IN', [jl, (xr, jl[1]), (xr, fl[0][1]), fl[0], fl[1]], width=1.0, layer=B)
    b.track('AC_L', [fa[1], fa[0], rl, (pl[0], pl[1] + 3.0), pl], width=1.0, layer=B)
    b.track('AC_N', [jn, (jn[0] - 4.3, jn[1]), (jn[0] - 4.3, rn[1] + 0.8), rn, pn], width=1.0, layer=B)
    for ref in ISO_HOLES:
        x, y = PLACE[ref][:2]
        b.keepout([F, B], circle(x, y, ISO_R), tracks=True, vias=True, pour=True,
                  name=f'iso {ref} PE standoff')
    for name, r in BAYS.items():
        b.keepout([F, B], rect_pts(*r), tracks=False, vias=False, fps=True, name=name)
    b.save()
    # nothing routed under the LM317 tabs (the tab copper goes there in 'finish'):
    # these rule areas go into the router's DSN only, not into the saved board
    for ref in ('U1', 'U2'):
        b.keepout([F, B], rect_pts(*tab_rect(ref)), name=f'ko tab {ref}')
    # grounds are routed here too: the relay contacts switch bucket current in the
    # unpoured bucket area
    dsn = os.path.join(HERE, f'{NAME}.dsn')
    if not pcbnew.ExportSpecctraDSN(b.board, dsn):
        raise SystemExit('DSN export failed')
    print('placed', len(b.fps), 'footprints; wrote', os.path.basename(dsn))


def pads(b, ref, num):
    """All pad positions of a footprint with this pad number (fuse clips have two)."""
    out = []
    for pad in b.fps[ref].Pads():
        if pad.GetNumber() == num:
            q = pad.GetPosition()
            out.append((pcbnew.ToMM(q.x) - 50.0, pcbnew.ToMM(q.y) - 50.0))
    return out


def circle(cx, cy, r, n=32):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def tab_rect(ref):
    """Copper area under a tab-down TO-220 (pin 1 = footprint origin, tab towards -y)."""
    x, y = PLACE[ref][:2]
    return (x - 2.4, y - 19.4, x + 7.5, y - 1.6)


def silkscreen(b):
    """Board texts at the first spot clear of parts, then tidy the references."""
    big = dict(size=2.5, thick=0.5)
    b.text_free('MAINS 230 V', near((10.0, 86.0), (8.0, 83.0, 47.0, 88.5), 0.5), avoid_tracks=True, size=2.0, thick=0.4)
    b.text_free('!! PRIMARY !!', near((4.0, 60.0), (1.0, 57.0, 16.0, 81.0), 0.5), size=1.2, thick=0.25, avoid_tracks=True)
    b.text_free('CHARGER', near((44.0, 3.0), (36.0, 1.5, 110.0, 5.0), 0.5), size=1.5, thick=0.3, avoid_tracks=True)
    # bucket A is the top row of cells, bucket B the bottom row
    b.text_free('BUCKET A', near((45.0, 68.0), (39.0, 60.0, 53.0, 75.0), 0.5), size=1.2, thick=0.25, avoid_tracks=True)
    b.text_free('BUCKET B', near((45.0, 82.0), (39.0, 76.0, 53.0, 89.0), 0.5), size=1.2, thick=0.25, avoid_tracks=True)
    b.text_free('RECEIVER', near((120.0, 87.0), (100.0, 55.0, 140.0, 89.0), 0.5), size=2.0, thick=0.4, avoid_tracks=True)
    bs = dict(layer=pcbnew.B_SilkS, mirror=True, justify='left')
    b.text_free('ELARA TWO-BUCKET PSU  REV 0.2', [(112.0, 22.0), (112.0, 18.0)], size=1.8, thick=0.35, **bs)
    b.text_free('CERN-OHL-W-2.0', [(112.0, 25.5), (112.0, 28.0)], size=1.2, thick=0.25, **bs)
    hidden = b.tidy_refs()
    print('references hidden (no room on silk, still on F.Fab):', hidden)


# charger-ground pour: charger area plus the strip above the module's DC pins,
# stopping 25 mm clear of its mains pins
CHG_POUR = [(20.0, 1.0), (113.0, 1.0), (113.0, 47.0), (56.0, 47.0), (56.0, 30.0), (20.0, 30.0)]


def stage_finish():
    path = os.path.join(HERE, f'{NAME}.kicad_pcb')
    b = Board.load(path)
    if not pcbnew.ImportSpecctraSES(b.board, os.path.join(HERE, f'{NAME}.ses')):
        raise SystemExit('SES import failed')
    with open(os.path.join(HERE, 'design_netlist.json'), encoding='utf-8') as f:
        pins = {c['ref']: c['pins'] for c in json.load(f)['components']}
    # LM317 tabs: solid copper of the tab (OUT) net on both layers, stitched
    for ref in ('U1', 'U2'):
        net = pins[ref]['2']                     # LM317 pin 2 = OUT = tab
        x0, y0, x1, y1 = tab_rect(ref)
        for layer in (F, B):
            b.zone(net, layer, rect_pts(x0, y0, x1, y1 + 1.6), priority=10, clearance=0.4, thermal=False,
                   name=f'{ref} tab')
        for vx in (x0 + 1.2, x1 - 1.2):
            for vy in (y0 + 1.5, y0 + 9.0, y1 - 1.5):
                b.via(net, vx, vy)
    for layer in (F, B):
        b.zone('GND_C', layer, CHG_POUR, clearance=0.4, name='charger ground')
        b.zone('GND', layer, rect_pts(*RX_ZONE), clearance=0.4, name='receiver ground')
    n = b.stitch([(x, y) for x in [60.0 + 5 * i for i in range(11)] for y in [4.0 + 5 * j for j in range(9)]],
                 net='GND_C')
    n += b.stitch([(x, y) for x in (121.0, 126.0, 131.0, 136.0, 141.0, 146.0) for y in [10.0 + 5 * j for j in range(15)]],
                  net='GND')
    silkscreen(b)
    # C4's ground pad sits on the edge of the charger pour, where only one thermal
    # spoke lands: connect that pad solidly instead
    c4 = next(f for f in b.board.GetFootprints() if f.GetReference() == 'C4')
    for pad in c4.Pads():
        if pad.GetNetname() == 'GND_C':
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    print('fab-layer values hidden:', b.hide_fab_values())
    print('nets renamed to schematic names:', b.rename_nets_to_schematic(os.path.join(HERE, 'design_netlist.json')))
    b.fill()
    b.save()
    print('finished: stitching vias', n)


if __name__ == '__main__':
    {'place': stage_place, 'finish': stage_finish}[sys.argv[1] if len(sys.argv) > 1 else 'place']()
