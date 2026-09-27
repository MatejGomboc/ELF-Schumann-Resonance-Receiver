#!/usr/bin/env python3
"""ELARA antenna amplifier -- PCB layout generator (runs in KiCad's Python).

Stages (run with KiCad 9's python3, e.g. `kicad-py layout.py place`):
  place   footprints, outline, holes, wall strips, guard island, silkscreen
          -> antenna_amplifier.kicad_pcb + antenna_amplifier.dsn (with routing keep-outs)
  finish  import antenna_amplifier.ses (Freerouting), drop routing keep-outs,
          add planes/pours, stitching vias, fill zones -> antenna_amplifier.kicad_pcb

Board: 200 x 100 mm, 4 layers (F.Cu signal | In1.Cu GND plane | In2.Cu signal/power |
B.Cu signal + GND pour). Origin at the top-left corner, y down.
Three compartments (tuner-style ALU walls bolted to exposed GND strips):
  C1 INPUT x 7..41.5 | wall x 41.5..48.5 | C2 ANALOG 48.5..116.5 | wall 116.5..123.5 | C3 DIGITAL 123.5..193
Signals cross under the walls on In2.Cu only.
"""

import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))

from kicadgen.pcb import Board, rect_pts  # noqa: E402

NAME = 'antenna_amplifier'
W, H = 200.0, 100.0
STRIP = 7.0
WALLS = (45.0, 120.0)                 # wall centre lines
HOLES = ([(x, y) for y in (3.5, 96.5) for x in (3.5, 45.0, 82.5, 120.0, 158.0, 196.5)] +
         [(x, y) for x in (3.5, 196.5) for y in (15.0, 50.0, 85.0)] +
         [(x, y) for x in WALLS for y in (15.0, 50.0, 85.0)])
# frame cut-outs where connectors pass the perimeter wall: (x0, y0, x1, y1)
CUTOUTS = [(179.0, 0.0, 191.0, STRIP), (W - STRIP, 21.0, W, 39.0), (W - STRIP, 63.75, W, 76.25)]

# guard island (C1): IN_P lives only inside this rectangle
ISLAND = (15.5, 36.4, 33.0, 54.6)

F, B, IN1, IN2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu

# ref: (x, y, rotation) -- board mm
PLACE = {
    # ---- C1 INPUT ----------------------------------------------------------
    'J201': (20.0, 50.1, 0), 'J202': (20.0, 40.0, 0), 'U201': (32.0, 52.0, 0),
    'R201': (32.0, 57.5, 0), 'C201': (32.0, 60.5, 0), 'R202': (27.0, 60.5, 90),
    'C203': (37.5, 49.0, 90), 'C204': (38.5, 43.5, 90),
    'R203': (38.0, 55.0, 0), 'U202': (36.5, 66.0, 0), 'C205': (36.5, 71.0, 0),
    'TP203': (28.0, 72.0, 0),
    # ---- C2 ANALOG -----------------------------------------------------------
    'C301': (54.0, 16.0, 0), 'R302': (85.0, 13.5, 0), 'R301': (85.0, 19.5, 90),
    'C302': (90.5, 16.5, 90), 'U301': (97.0, 15.0, 0), 'C304': (97.0, 20.5, 0),
    'TP201': (60.0, 29.0, 0),
    'U101': (102.0, 36.0, 0), 'C103': (109.0, 33.0, 90), 'C104': (95.5, 31.5, 90),
    'C105': (92.5, 35.5, 90), 'C106': (98.0, 41.0, 0), 'C107': (106.5, 41.0, 0),
    'R101': (86.0, 41.0, 0), 'C113': (81.5, 44.5, 90), 'C114': (78.0, 45.0, 90),
    'C202': (69.0, 88.0, 90),
    'C206': (100.5, 82.0, 0), 'R204': (96.0, 66.0, 90), 'R205': (99.0, 66.0, 90),
    'U203': (104.0, 62.0, 0), 'C207': (108.5, 62.0, 90), 'R206': (99.0, 58.5, 0),
    'TP202': (110.0, 55.0, 0), 'TP204': (110.0, 70.0, 0),
    # ---- C3 DIGITAL ----------------------------------------------------------
    'U102': (160.0, 16.0, 0), 'C108': (166.5, 13.0, 90), 'C109': (153.5, 12.5, 90),
    'C110': (153.5, 18.5, 90), 'C111': (157.0, 21.5, 0), 'C112': (163.0, 21.5, 0),
    'J101': (185.0, 9.5, 0), 'D101': (177.0, 13.5, 0), 'D102': (177.0, 19.0, 0),
    'C101': (188.5, 17.0, 0), 'C102': (171.0, 16.0, 90),
    'SW401': (128.0, 17.5, 90),
    'R404': (128.0, 25.5, 90), 'R405': (130.8, 25.5, 90), 'R406': (133.6, 25.5, 90),
    'R407': (136.4, 25.5, 90), 'R408': (139.2, 25.5, 90), 'R409': (142.0, 25.5, 90),
    'R410': (144.8, 25.5, 90), 'R411': (147.6, 25.5, 90),
    'U302': (142.0, 50.0, 90),
    'C309': (133.0, 42.0, 90), 'C310': (136.5, 43.0, 90), 'C311': (139.5, 41.5, 90),
    'C312': (142.5, 43.0, 90), 'C313': (145.5, 41.5, 90), 'C314': (148.0, 43.0, 90),
    'C305': (133.0, 58.0, 90), 'C306': (136.5, 57.0, 90), 'C307': (139.5, 58.5, 90),
    'C308': (142.5, 57.0, 90), 'C315': (148.5, 58.5, 90), 'C316': (151.0, 57.0, 90),
    'R303': (127.5, 53.6, 0), 'C303': (130.5, 50.0, 90),
    'Y401': (158.0, 44.0, 0), 'C401': (158.0, 40.0, 0), 'R401': (154.0, 47.5, 90),
    'R402': (162.0, 47.5, 90),
    'U401': (170.0, 52.0, 0), 'C402': (165.0, 42.0, 0), 'C403': (176.0, 44.5, 90),
    'C404': (164.0, 58.0, 90), 'R403': (170.0, 60.5, 0),
    'TR401': (178.0, 27.0, 0), 'J401': (194.0, 35.08, 90),
    'R412': (174.0, 24.0, 90), 'C405': (174.0, 28.5, 90), 'R413': (174.0, 33.0, 90),
    'C406': (186.0, 40.5, 0), 'R414': (189.5, 40.5, 0),
    'TR402': (172.0, 80.0, 0), 'J402': (182.0, 70.0, 270),
    'R415': (166.0, 66.0, 90), 'C407': (166.0, 70.5, 90), 'R416': (166.0, 75.0, 90),
    'R417': (170.0, 75.0, 0),
    'SW302': (128.0, 88.0, 90),
    'R306': (129.0, 68.5, 90), 'R307': (131.8, 68.5, 90), 'R308': (134.6, 68.5, 90),
    'R309': (137.4, 68.5, 90), 'R310': (140.2, 68.5, 90), 'R311': (143.0, 68.5, 90),
    'R312': (145.8, 68.5, 90),
    'R305': (157.0, 68.0, 0), 'C317': (157.0, 71.5, 0), 'SW301': (158.0, 84.0, 0),
    'R304': (152.0, 75.5, 90), 'D301': (152.0, 81.0, 90),
}


def strips():
    """Wall strip rectangles (board mm), split around the connector cut-outs."""
    rects = [(0, 0, W, STRIP), (0, H - STRIP, W, H), (0, 0, STRIP, H), (W - STRIP, 0, W, H)]
    rects += [(x - STRIP / 2, 0, x + STRIP / 2, H) for x in WALLS]
    for cx0, cy0, cx1, cy1 in CUTOUTS:
        out = []
        for r in rects:
            x0, y0, x1, y1 = r
            if cx1 <= x0 or cx0 >= x1 or cy1 <= y0 or cy0 >= y1:
                out.append(r)
            elif x1 - x0 > y1 - y0:          # horizontal strip: split in x
                out += [q for q in ((x0, y0, cx0, y1), (cx1, y0, x1, y1)) if q[2] > q[0]]
            else:                            # vertical strip: split in y
                out += [q for q in ((x0, y0, x1, cy0), (x0, cy1, x1, y1)) if q[3] > q[1]]
        rects = out
    return rects


def place(b):
    for ref, (x, y, r) in PLACE.items():
        b.place(ref, x, y, r)
    missing = b.unplaced()
    if missing:
        raise SystemExit(f'unplaced: {missing}')


def guard_island(b):
    """Hand-routed femtoampere node and its driven guard (see PLAN 4.3)."""
    t, p1 = b.pad_xy('J201', 1), b.pad_xy('U201', 1)
    j2 = b.pad_xy('J202', 2)
    g2, g7 = b.pad_xy('U201', 2), b.pad_xy('U201', 7)
    b.track('IN_P', [t, (p1[0], t[1]), p1], width=0.3)
    b.track('IN_P', [j2, t], width=0.3, layer=F)
    x0, y0, x1, y1 = ISLAND
    L, T, Bm = x0 + 1.0, y0 + 1.0, y1 - 1.0          # ring centre lines
    xr = (g2[0] + g7[0]) / 2                           # under the body, between pin 1 and pin 8
    xb = t[0] + 2.6
    # top-side ring: pin 2 -> around the island -> down between pins 1/8 -> pin 7
    b.track('GUARD', [g2, (xb, g2[1]), (xb, Bm), (L, Bm), (L, T), (t[0] - 1.1, T)], width=0.5)
    b.track('GUARD', [(t[0] + 1.1, T), (xr, T), (xr, g7[1]), g7], width=0.5)
    b.track('GUARD', [g2, (xr, g2[1])], width=0.5)
    # bottom-side ring: closed around the turret and the bias link
    xbb = t[0] + 3.8
    b.track('GUARD', [(L, T), (xbb, T), (xbb, Bm), (L, Bm), (L, T)], width=0.5, layer=B)
    for y in [T + i * 2.0 for i in range(int((Bm - T) / 2.0) + 1)]:
        b.via('GUARD', L, y)
    for x in [L + 2.0 * i for i in range(1, int((xb - L) / 2.0) + 1)]:
        b.via('GUARD', x, Bm)
    # guard planes under the island on both inner layers
    for layer in (IN1, IN2):
        b.zone('GUARD', layer, rect_pts(*ISLAND), priority=10, clearance=0.3, name='guard plane')
    # no pours and no solder mask on the island
    b.keepout([F, B], rect_pts(*ISLAND), tracks=False, vias=False, pour=True, name='island no pour')
    for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
        b.rect(layer, *ISLAND)


def mechanics(b):
    b.outline(W, H)
    for x, y in HOLES:
        b.hole(x, y)
    for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
        for r in strips():
            b.rect(layer, *r)


def silkscreen(b):
    big = dict(size=3.0, thick=0.6)
    b.text('01 INPUT', 9.0, 11.0, **big)
    b.text('02 ANALOG', 89.0, 91.0, **big)
    b.text('03 DIGITAL', 152.0, 91.5, **big)
    b.text('IN', 20.0, 56.8, size=1.5, thick=0.3, justify='center')
    b.text('GUARDED - NO MASK - DO NOT TOUCH', 9.0, 34.0, size=1.0, thick=0.2)
    b.text('ELARA', 9.0, 85.0, size=4.0, thick=0.8)
    b.text('ANTENNA AMPLIFIER  REV 0.2', 9.0, 89.5, size=1.2, thick=0.25)
    bs = dict(layer=pcbnew.B_SilkS, mirror=True, justify='right')
    b.text('ELARA  ELF ATMOSPHERIC RADIO ANALYSER', 191.0, 12.0, size=2.5, thick=0.5, **bs)
    b.text('ANTENNA AMPLIFIER  REV 0.2  4 LAYER  1.6 MM', 191.0, 16.5, size=1.5, thick=0.3, **bs)
    b.text('CERN-OHL-W-2.0', 191.0, 20.0, size=1.5, thick=0.3, **bs)
    b.text('ANTENNA INPUT FROM BELOW', 38.0, 60.0, size=1.2, thick=0.25, **bs)


def routing_keepouts(b):
    """Temporary rule areas that steer Freerouting (removed in 'finish')."""
    for r in strips():
        b.keepout([F, B], rect_pts(*r), name='ko wall')
        b.keepout([IN1, IN2], rect_pts(*r), tracks=False, vias=True, name='ko wall vias')
    b.keepout([F, B, IN1, IN2], rect_pts(*ISLAND), name='ko island')


def stage_place():
    b = Board(os.path.join(HERE, 'design_netlist.json'),
              {'elara': os.path.join(HERE, '..', 'elara.pretty')}, os.path.join(HERE, f'{NAME}.kicad_pcb'))
    mechanics(b)
    place(b)
    guard_island(b)
    silkscreen(b)
    routing_keepouts(b)
    b.board.SetLayerType(IN1, pcbnew.LT_POWER)          # solid GND plane, never routed
    b.zone('GND', IN1, rect_pts(0.3, 0.3, W - 0.3, H - 0.3), priority=0, name='GND plane')
    b.save()
    dsn = os.path.join(HERE, f'{NAME}.dsn')
    if not pcbnew.ExportSpecctraDSN(b.board, dsn):
        raise SystemExit('DSN export failed')
    print('placed', len(b.fps), 'footprints; wrote', os.path.basename(dsn))


if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'place'
    {'place': stage_place}[stage]()
