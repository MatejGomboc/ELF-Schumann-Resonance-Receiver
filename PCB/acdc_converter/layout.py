#!/usr/bin/env python3
"""ELARA two-bucket PSU -- PCB layout generator (runs in KiCad's Python).

  kicad-py layout.py place    -> acdc_converter.kicad_pcb + .dsn
  kicad-py layout.py finish   -> imports acdc_converter.ses, pours, fills

Board 150 x 90 mm, 2 layers, left to right:
  MAINS (primary, >= 6.4 mm creepage) | CHARGER + TIMER (GND_C pour)
  | RELAYS + BUCKETS (no copper pour: minimum capacitance across the barrier)
  | RECEIVER SIDE (GND pour), output at the right edge.
A milled slot separates the receiver side from the charger side.
"""

import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))

from kicadgen.pcb import Board, near, rect_pts  # noqa: E402

NAME = 'acdc_converter'
W, H = 150.0, 90.0
F, B = pcbnew.F_Cu, pcbnew.B_Cu
CHG_ZONE = (56.0, 1.0, 113.0, 47.0)
RX_ZONE = (118.0, 1.0, 149.0, 89.0)
PRIMARY = (1.0, 1.0, 50.0, 89.0)

PLACE = {
    'H1': (4.0, 4.0, 0), 'H2': (146.0, 4.0, 0), 'H3': (4.0, 86.0, 0), 'H4': (146.0, 86.0, 0),
    # primary
    'J1': (8.0, 75.0, 90), 'F1': (18.0, 68.0, 0), 'RV1': (22.0, 80.0, 0),
    'PS1': (20.0, 52.0, 90), 'R1': (13.0, 4.5, 180),
    # charger
    'C1': (58.0, 12.0, 0), 'C2': (61.0, 19.5, 90),
    'U1': (70.0, 10.0, 0), 'R2': (78.0, 18.5, 0), 'U2': (90.0, 10.0, 0),
    'R3': (98.0, 18.5, 90), 'R4': (98.0, 23.0, 90), 'C3': (101.5, 20.0, 90), 'D1': (107.0, 12.0, 90),
    'U3': (60.0, 27.5, 0), 'C4': (57.0, 34.0, 90), 'C5': (63.0, 34.0, 90),
    'R5': (67.0, 34.0, 90), 'D2': (67.0, 40.0, 90),
    'U4': (80.0, 33.0, 0), 'C6': (88.5, 28.0, 90), 'R6': (88.5, 33.0, 90), 'R7': (88.5, 38.0, 90),
    'C7': (74.0, 28.0, 90),
    'R8': (94.0, 33.0, 0), 'R9': (94.0, 37.0, 90), 'Q1': (98.0, 40.0, 0),
    'D3': (74.0, 45.5, 0), 'D4': (104.0, 44.5, 0),
    'R10': (107.0, 26.0, 90), 'R11': (111.0, 26.0, 90),
    # relays + buckets
    'K1': (82.0, 52.0, 0), 'K2': (99.0, 52.0, 0),
    'R12': (112.0, 52.0, 90), 'R13': (115.5, 58.0, 0),
    'C8': (58.0, 67.0, 0), 'C9': (71.5, 67.0, 0), 'C10': (85.0, 67.0, 0), 'C11': (98.5, 67.0, 0),
    'C12': (58.0, 81.0, 0), 'C13': (71.5, 81.0, 0), 'C14': (85.0, 81.0, 0), 'C15': (98.5, 81.0, 0),
    # receiver side
    'C16': (122.5, 70.0, 0), 'C17': (131.0, 78.0, 90),
    'U5': (132.0, 60.0, 0), 'R22': (127.0, 52.0, 90), 'C18': (131.0, 52.0, 90), 'C19': (138.0, 60.0, 90),
    'L1': (134.0, 38.0, 0), 'D5': (128.0, 24.0, 90), 'J2': (138.0, 18.0, 270),
}
# balancing resistors on the bottom side, under their cells
BOTTOM = {f'R{14 + i}': (60.5 + (i % 4) * 13.5, 67.0 if i < 4 else 81.0, 90) for i in range(8)}


def stage_place():
    b = Board(os.path.join(HERE, 'design_netlist.json'), {}, os.path.join(HERE, f'{NAME}.kicad_pcb'), layers=2)
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
    b.save()
    # grounds are routed here too: the relay contacts switch bucket current in the
    # unpoured bucket area
    dsn = os.path.join(HERE, f'{NAME}.dsn')
    if not pcbnew.ExportSpecctraDSN(b.board, dsn):
        raise SystemExit('DSN export failed')
    print('placed', len(b.fps), 'footprints; wrote', os.path.basename(dsn))


def silkscreen(b):
    """Board texts at the first spot clear of parts, then tidy the references."""
    big = dict(size=2.5, thick=0.5)
    b.text_free('MAINS 230 V', near((14.0, 60.0), (3.0, 55.0, 20.0, 70.0), 0.5), **big)
    b.text_free('!! PRIMARY !!', near((14.0, 64.0), (3.0, 55.0, 40.0, 95.0), 0.5), size=1.2, thick=0.25)
    b.text_free('CHARGER', [(58.0, 4.5), (58.0, 3.0)], size=1.5, thick=0.3)
    # bucket A is the top row of cells, bucket B the bottom row
    b.text_free('BUCKET A', near((45.0, 68.0), (39.0, 60.0, 53.0, 75.0), 0.5), size=1.2, thick=0.25)
    b.text_free('BUCKET B', near((45.0, 82.0), (39.0, 76.0, 53.0, 89.0), 0.5), size=1.2, thick=0.25)
    b.text_free('RECEIVER', near((120.0, 87.0), (100.0, 55.0, 140.0, 89.0), 0.5), size=2.0, thick=0.4)
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
    b.fill()
    b.save()
    print('finished: stitching vias', n)


if __name__ == '__main__':
    {'place': stage_place, 'finish': stage_finish}[sys.argv[1] if len(sys.argv) > 1 else 'place']()
