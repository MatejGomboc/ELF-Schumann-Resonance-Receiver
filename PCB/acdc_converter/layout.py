#!/usr/bin/env python3
"""ELARA two-bucket PSU -- PCB layout generator (runs in KiCad's Python).

  kicad-py layout.py place    -> acdc_converter.kicad_pcb + .dsn
  kicad-py layout.py finish   -> rebuilds the placement, imports acdc_converter.ses,
                                 pours, fills (safe to re-run; the SES is reused)

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
    'C1': (40.0, 8.0, 0), 'C2': (41.25, 14.0, 0), 'U3': (41.25, 20.5, 0),     # one column (C1's can centre)
    'C4': (37.5, 26.5, 90), 'C5': (41.0, 26.5, 90), 'R5': (45.0, 26.5, 90), 'D2': (48.5, 26.5, 90),
    # LM317s tab-down (tab towards the top edge), pins on y = 25
    'U1': (58.0, 25.0, 0), 'R2': (60.5, 29.5, 0),
    'U2': (72.0, 25.0, 0), 'R4': (70.5, 29.5, 0), 'R3': (74.5, 29.5, 0), 'C3': (78.5, 29.5, 0),
    'D1': (85.0, 16.0, 90), 'R10': (90.0, 16.0, 90), 'R11': (94.5, 16.0, 90),
    # swap timer
    'U4': (86.0, 36.0, 0), 'C7': (80.5, 36.0, 90),
    'R7': (92.5, 31.0, 90), 'R6': (92.5, 36.0, 90), 'C6': (92.5, 41.0, 90),   # same order as U4 pins 11, 10, 9
    # relay drivers, one row per bucket: gate R, driver, gate C, coil resistor
    'R8': (97.0, 32.5, 90), 'D3': (101.0, 32.5, 0), 'D4': (106.0, 32.5, 0),
    'R9': (97.0, 37.5, 90), 'Q1': (101.0, 37.5, 0), 'C20': (105.0, 37.5, 90), 'R24': (109.0, 37.5, 90),
    'R23': (97.0, 42.5, 90), 'Q2': (101.0, 42.5, 0), 'C21': (105.0, 42.5, 90), 'R25': (109.0, 42.5, 90),
    # reed relays, pin 1 at the right: bucket A (K1 P, K2 N) left, bucket B (K3, K4) right
    'K1': (88.0, 50.0, 180), 'K2': (88.0, 56.0, 180), 'K3': (111.0, 50.0, 180), 'K4': (111.0, 56.0, 180),
    # load paths (receiver side): SS34 diode-OR and series resistor per bucket
    'D6': (116.0, 52.0, 90), 'D7': (120.5, 52.0, 90), 'R12': (116.0, 60.0, 270), 'R13': (120.5, 60.0, 270),
    'C8': (58.0, 67.0, 0), 'C9': (71.5, 67.0, 0), 'C10': (85.0, 67.0, 0), 'C11': (98.5, 67.0, 0),
    'C12': (58.0, 81.0, 0), 'C13': (71.5, 81.0, 0), 'C14': (85.0, 81.0, 0), 'C15': (98.5, 81.0, 0),
    # receiver side: J2 faces +x (towards the output gland) across the plug channel
    'J2': (119.5, 18.0, 270), 'D5': (124.0, 31.0, 0), 'L1': (134.0, 40.0, 0),
    'C16': (122.5, 71.0, 0),
    # LT3045: input cap left of IN (pins 1-3), output cap right of OUT (11, 12), SET parts below it
    'U5': (132.0, 60.0, 0), 'C17': (126.5, 60.0, 90), 'C19': (137.5, 57.0, 90),
    'R22': (137.5, 62.5, 90), 'C18': (140.5, 62.5, 90), 'R28': (134.0, 64.5, 0),
    # 0.4 A load-path limiter (OR_P -> R26 -> Q3 -> LOAD_P) below the reservoir
    'R26': (125.0, 80.0, 0), 'Q3': (125.0, 84.0, 0), 'Q4': (121.0, 84.0, 0), 'R27': (130.0, 83.5, 0),
    'C22': (77.0, 32.0, 0),
    # test points: charger side (CHG_D, +12V_C, SWAP, GND_C) and receiver side
    'TP1': (88.0, 22.0, 0), 'TP2': (47.0, 30.5, 0), 'TP3': (95.0, 25.0, 0), 'TP4': (52.0, 33.0, 0),
    'TP5': (134.0, 70.0, 0), 'TP6': (141.0, 52.0, 0), 'TP7': (138.0, 70.0, 0),
    # EDLC overvoltage crowbar on CHG, in the free corner right of D1 (charger pour)
    'Q6': (104.0, 5.0, 0),
    'R29': (99.5, 9.5, 0), 'R30': (103.5, 9.5, 0), 'C23': (107.5, 9.5, 0),
    'U6': (100.0, 14.0, 0), 'R32': (104.0, 14.0, 0), 'R31': (108.0, 14.0, 0),
    'Q5': (100.0, 19.0, 0), 'R33': (104.0, 19.0, 0), 'C24': (108.0, 19.0, 0), 'R34': (111.0, 23.5, 90),
    # GDT across the barrier gap between the charger (GND_C) and receiver (GND) pours
    'GDT1': (115.5, 7.0, 0),
}
# Charger / receiver barrier: copper of the two sides keeps 1 mm apart (custom DRC
# rule, also honoured by the pour fill). The buckets are not on either side: the
# relays connect each to one side at a time. In the SIL reed relay the NO and NC
# pins sit 2.54 mm apart (1.14 mm between pads), the closest charger/receiver pair.
CHARGER_NETS = ('GND_C', 'A_NC', 'B_NC', '+15V_C', '+12V_C', 'CHG', 'CHG_D', 'CHG_A', 'CHG_B', 'CC_SET', 'CC_OUT',
                'CV_ADJ', 'LED_C', 'OSC_C', 'OSC_R', 'OSC_I', 'OSC_X', 'SWAP', 'SW_R', 'GATE_A', 'GATE_B',
                'COIL_A', 'COIL_B', 'COIL_A1', 'COIL_A2', 'COIL_B1', 'COIL_B2', 'PE',
                'CB_REF', 'CB_K', 'CB_B', 'CB_C', 'CB_G')
RECEIVER_NETS = ('GND', 'A_NL', 'B_NL', 'LOAD_A', 'LOAD_B', 'LA_D', 'LB_D', 'OR_P', 'LIM_S', 'LIM_G', 'LOAD_P',
                 'VREG', 'SET', 'ILIM', '+9V_OUT', 'OUT_N')
BARRIER = 1.0
CHG_POUR_Y = 46.0          # just inside the charger pour's lower edge (y = 47)


def barrier_rule():
    """KiCad custom rule: charger-side copper at least BARRIER mm from receiver-side
    copper (net names may carry the sheet path, hence the wildcards)."""
    side = lambda s, nets: '(' + ' || '.join(f"{s}.NetName == '{n}' || {s}.NetName == '*/{n}'" for n in nets) + ')'
    cond = (f"({side('A', CHARGER_NETS)} && {side('B', RECEIVER_NETS)}) || "
            f"({side('B', CHARGER_NETS)} && {side('A', RECEIVER_NETS)})")
    return (f'(rule "Charger / receiver barrier"\n\t(condition "{cond}")\n'
            f'\t(constraint clearance (min {BARRIER}mm)))\n')


# parts-free cable bays (rule areas: no footprints)
BAYS = {'mains bay': (0.5, 57.0, 16.5, 81.5), 'output bay': (129.5, 12.0, 149.5, 27.0)}
ISO_HOLES = ('H2', 'H4')          # receiver side: standoffs are on PE, keep copper 5 mm away
ISO_R = 5.0
# balancing resistors on the bottom side, under their cells
BOTTOM = {f'R{14 + i}': (60.5 + (i % 4) * 13.5, 67.0 if i < 4 else 81.0, 90) for i in range(8)}
# bucket negative-leg Schottkys (one way only), bottom side in the strip between the
# relay row and the cells: charger legs D8 (K2) / D10 (K4), receiver legs D9 / D11
BOTTOM.update({'D8': (82.0, 60.6, 0), 'D9': (91.0, 60.6, 0), 'D11': (105.5, 60.6, 180),
               'D10': (113.8, 60.6, 180)})
NLEG_Y = 63.6              # receiver GND trunk under the cells, bottom side


def build():
    """The placed board with its hand-routed tracks and rule areas (no autorouting)."""
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
    # bucket negative legs: each relay contact to its Schottky (bottom side, below the
    # relays), then receiver legs to a GND trunk under the cells and into the receiver
    # pour, charger legs up into the charger pour; every receiver/charger pair keeps
    # the barrier distance (the contact pins sit 2.54 mm apart)
    k21, k22, k41, k42 = b.pad_xy('K2', '1'), b.pad_xy('K2', '2'), b.pad_xy('K4', '1'), b.pad_xy('K4', '2')
    for k, d, net in ((k21, 'D9', 'A_NL'), (k22, 'D8', 'A_NC'), (k41, 'D10', 'B_NC'), (k42, 'D11', 'B_NL')):
        pin = '1' if net.endswith('NL') else '2'          # receiver legs: cathode on the contact
        q = b.pad_xy(d, pin)
        b.track(net, [k, (k[0], q[1]), q], width=0.5, layer=B)
    a9, a11 = b.pad_xy('D9', '2'), b.pad_xy('D11', '2')
    b.track('GND', [a9, (a9[0], NLEG_Y), (123.5, NLEG_Y)], width=0.5, layer=B)
    b.track('GND', [a11, (a11[0], NLEG_Y)], width=0.5, layer=B)
    b.via('GND', 123.5, NLEG_Y)
    c8, c10 = b.pad_xy('D8', '1'), b.pad_xy('D10', '1')
    xl = 69.0
    b.track('GND_C', [c8, (c8[0] - 1.8, c8[1])], width=0.5, layer=B)
    b.via('GND_C', c8[0] - 1.8, c8[1])
    b.track('GND_C', [(c8[0] - 1.8, c8[1]), (xl, c8[1]), (xl, CHG_POUR_Y)], width=0.4, layer=F)
    b.via('GND_C', xl, CHG_POUR_Y)
    xr = 113.0
    b.track('GND_C', [c10, (xr, c10[1] - 2.2), (xr, CHG_POUR_Y)], width=0.4, layer=B)
    b.via('GND_C', xr, CHG_POUR_Y)
    for ref in ISO_HOLES:
        x, y = PLACE[ref][:2]
        b.keepout([F, B], circle(x, y, ISO_R), tracks=True, vias=True, pour=True,
                  name=f'iso {ref} PE standoff')
    for name, r in BAYS.items():
        b.keepout([F, B], rect_pts(*r), tracks=False, vias=False, fps=True, name=name)
    b.extra_rules = barrier_rule()
    return b


def stage_place():
    b = build()
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


# heat-spreading copper of each LM317 tab, grown to the board's top edge and sideways
# up to the neighbours (simulations/thermal: the charger cluster is the hottest spot)
TAB_GROW = {'U1': (3.0, 1.0), 'U2': (1.0, 2.5)}       # extra mm to the left, right


def tab_rect(ref):
    """Copper area under a tab-down TO-220 (pin 1 = footprint origin, tab towards -y)."""
    x, y = PLACE[ref][:2]
    gl, gr = TAB_GROW.get(ref, (0.0, 0.0))
    return (x - 2.4 - gl, 1.5, x + 7.5 + gr, y - 1.6)


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
    b.text_free('ELARA TWO-BUCKET PSU  REV ${REVISION}  ${GIT_HASH}', [(112.0, 22.0), (112.0, 18.0)], size=1.8, thick=0.35, **bs)
    b.text_free('CERN-OHL-W-2.0', [(112.0, 25.5), (112.0, 28.0)], size=1.2, thick=0.25, **bs)
    hidden = b.tidy_refs()
    print('references hidden (no room on silk, still on F.Fab):', hidden)
    for r in hidden:                 # named beside the part in the assembly drawing
        b.fab_ref_beside(r)


# charger-ground pour: charger area plus the strip above the module's DC pins,
# stopping 25 mm clear of its mains pins
CHG_POUR = [(20.0, 1.0), (113.0, 1.0), (113.0, 47.0), (56.0, 47.0), (56.0, 30.0), (20.0, 30.0)]


def stage_finish():
    # rebuilt from scratch (so finish can be re-run), saved and reloaded so the pour
    # fill sees the project's rules and the .kicad_dru (the barrier rule)
    path = os.path.join(HERE, f'{NAME}.kicad_pcb')
    build().save()
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
        # thermal vias on a ~3 mm grid round the tab, both layers carry the heat
        n = b.stitch([(x0 + 1.2 + 3.0 * i, y0 + 1.2 + 3.0 * j)
                      for i in range(int((x1 - x0 - 2.4) // 3.0) + 1)
                      for j in range(int((y1 - y0 - 2.4) // 3.0) + 1)], net=net, avoid_courtyards=False)
        print(f'{ref} tab: {n} thermal vias')
    for layer in (F, B):
        b.zone('GND_C', layer, CHG_POUR, clearance=0.4, name='charger ground')
        b.zone('GND', layer, rect_pts(*RX_ZONE), clearance=0.4, name='receiver ground')
    tabs = [tab_rect(r) for r in ('U1', 'U2')]
    off_tabs = lambda x, y: not any(t[0] - 1.0 <= x <= t[2] + 1.0 and t[1] - 1.0 <= y <= t[3] + 2.6 for t in tabs)
    n = b.stitch([(x, y) for x in [60.0 + 5 * i for i in range(11)] for y in [4.0 + 5 * j for j in range(9)]
                  if off_tabs(x, y)], net='GND_C')
    n += b.stitch([(x, y) for x in (121.0, 126.0, 131.0, 136.0, 141.0, 146.0) for y in [10.0 + 5 * j for j in range(15)]],
                  net='GND', clearance=BARRIER + 0.05)   # charger tracks may pass through the area
    print('footprint silk widened / cut clear of pads:', b.silk_for_fab())
    silkscreen(b)
    # C4's ground pad sits on the edge of the charger pour, where only one thermal
    # spoke lands: connect that pad solidly instead
    c4 = next(f for f in b.board.GetFootprints() if f.GetReference() == 'C4')
    for pad in c4.Pads():
        if pad.GetNetname() == 'GND_C':
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    print('fab-layer values hidden:', b.hide_fab_values())
    print('fab-layer reference copies hidden (silk reference shown):', b.hide_fab_refs())
    print('nets renamed to schematic names:', b.rename_nets_to_schematic(os.path.join(HERE, 'design_netlist.json')))
    b.fill()
    b.extra_rules = barrier_rule()
    b.save()
    print('finished: stitching vias', n)


if __name__ == '__main__':
    {'place': stage_place, 'finish': stage_finish}[sys.argv[1] if len(sys.argv) > 1 else 'place']()
