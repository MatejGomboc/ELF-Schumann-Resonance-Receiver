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

from kicadgen.pcb import Board, rect_pts  # noqa: E402

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
    'PS1': (20.0, 52.0, 90), 'R1': (60.0, 44.0, 0),
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
    for ref, (x, y, r) in PLACE.items():
        b.place(ref, x, y, r)
    for ref, (x, y, r) in BOTTOM.items():
        b.place(ref, x, y, r, side='B')
    missing = b.unplaced()
    if missing:
        raise SystemExit(f'unplaced: {missing}')
    big = dict(size=2.5, thick=0.5)
    b.text('MAINS 230 V', 14.0, 60.0, **big)
    b.text('!! PRIMARY !!', 14.0, 64.0, size=1.5, thick=0.3)
    b.text('CHARGER', 58.0, 3.0 + 1.5, size=1.5, thick=0.3)
    b.text('BUCKET A', 52.0, 60.5, size=1.2, thick=0.25)
    b.text('BUCKET B', 52.0, 88.6, size=1.2, thick=0.25)
    b.text('RECEIVER', 120.0, 87.0, size=2.0, thick=0.4)
    bs = dict(layer=pcbnew.B_SilkS, mirror=True, justify='left')
    b.text('ELARA TWO-BUCKET PSU  REV 0.2', 112.0, 22.0, size=1.8, thick=0.35, **bs)
    b.text('CERN-OHL-W-2.0', 112.0, 25.5, size=1.2, thick=0.25, **bs)
    b.save()
    dsn = os.path.join(HERE, f'{NAME}.dsn')
    if not pcbnew.ExportSpecctraDSN(b.board, dsn):
        raise SystemExit('DSN export failed')
    print('placed', len(b.fps), 'footprints; wrote', os.path.basename(dsn))


if __name__ == '__main__':
    {'place': stage_place}[sys.argv[1] if len(sys.argv) > 1 else 'place']()
