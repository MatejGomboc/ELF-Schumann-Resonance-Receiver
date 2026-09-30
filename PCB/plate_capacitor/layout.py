#!/usr/bin/env python3
"""ELARA air-gap plate capacitor plate (PLAN 3.0) -- PCB generator (KiCad Python).

  kicad-py PCB/plate_capacitor/layout.py   -> plate_capacitor.kicad_pcb

One design is used four times: each capacitor is two identical plates placed
copper face to copper face, the second one flipped about the vertical axis,
with 0.5 mm PTFE washers on four nylon M3 screws setting the air gap.

- 64 x 64 mm FR4, 1.6 mm, copper on F.Cu only (the inner, facing side),
  solder mask over the plate copper (moisture barrier, no bare metal in the gap).
- 53.1 mm copper square centred -> ~49 pF bare / ~52 pF with mask at 0.5 mm.
- Corner M3 holes 5 mm in from the corners, copper relief R4.8 around each,
  and an isolated, unmasked 7 mm copper landing ring under each washer so the
  washer sits on copper exactly like the plate surface.
- Connection: a tab from the copper square to a plated hole outside the facing
  area, offset from the centre line, so the two tabs of a pair never overlap.
  Solder the wire / 33 k resistor lead from the back only.
Dimensions mirror mechanical/params.py.
"""

import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))

from kicadgen.pcb import Board, mm, pt, rect_pts  # noqa: E402

NAME = 'plate_capacitor'
SIZE, CU, INSET, RELIEF, LAND_OD = 64.0, 53.1, 5.0, 4.8, 7.0
GAP = 0.5
TAB_X = 20.0                  # tab centre (offset from the 32 mm centre line)
PAD = (TAB_X, 61.0)


def circle(cx, cy, r, n=40):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def capacitance_pf(mask_um=20.0, mask_er=3.5):
    area = CU ** 2 - 4 * _relief_area()
    gap = (GAP - 2 * mask_um / 1000) + 2 * (mask_um / 1000) / mask_er
    return 8.854e-12 * area * 1e-6 / (gap * 1e-3) * 1e12, 8.854e-12 * area * 1e-6 / (GAP * 1e-3) * 1e12


def _relief_area(n=400):
    # area of the relief circle that lies inside the copper square (numeric)
    c0 = (SIZE - CU) / 2
    tot = 0.0
    step = 2 * RELIEF / n
    for i in range(n):
        for j in range(n):
            x, y = INSET - RELIEF + (i + 0.5) * step, INSET - RELIEF + (j + 0.5) * step
            if (x - INSET) ** 2 + (y - INSET) ** 2 < RELIEF ** 2 and x > c0 and y > c0:
                tot += step * step
    return tot


def main():
    path = os.path.join(HERE, f'{NAME}.kicad_pcb')
    b = Board(None, {}, path, layers=2)
    b.outline(SIZE, SIZE)
    for hx, hy in ((INSET, INSET), (SIZE - INSET, INSET), (SIZE - INSET, SIZE - INSET), (INSET, SIZE - INSET)):
        b.npth(hx, hy)
        # isolated landing ring under the PTFE washer (no net), unmasked
        b.zone('', pcbnew.F_Cu, circle(hx, hy, LAND_OD / 2), priority=2, clearance=0.3, name='washer land',
               holes=[circle(hx, hy, 1.9)[::-1]])
        mk = pcbnew.PCB_SHAPE(b.board, pcbnew.SHAPE_T_CIRCLE)
        mk.SetCenter(pt(hx, hy))
        mk.SetEnd(pt(hx + LAND_OD / 2 + 0.2, hy))
        mk.SetLayer(pcbnew.F_Mask)
        mk.SetFilled(True)
        mk.SetWidth(0)
        b.board.Add(mk)
    # plate copper + tab to the solder pad (net PLATE)
    b.zone('PLATE', pcbnew.F_Cu, _walk(_arcs()), priority=1, clearance=0.3, name='plate', thermal=False)
    c1 = (SIZE + CU) / 2
    b.zone('PLATE', pcbnew.F_Cu, rect_pts(PAD[0] - 2.0, c1 - 0.5, PAD[0] + 2.0, PAD[1] + 1.5), priority=3,
           clearance=0.3, name='tab', thermal=False)
    fp = pcbnew.FOOTPRINT(b.board)
    fp.SetReference('J1')
    fp.SetValue('PLATE')
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY)
    pad = pcbnew.PAD(fp)
    pad.SetNumber('1')
    pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(pcbnew.VECTOR2I(mm(3.0), mm(3.0)))
    pad.SetDrillSize(pcbnew.VECTOR2I(mm(1.3), mm(1.3)))
    pad.SetLayerSet(pad.PTHMask())
    pad.SetNet(b.net('PLATE'))
    fp.Add(pad)
    b.board.Add(fp)
    fp.SetPosition(pt(*PAD))
    cmask, cbare = capacitance_pf()
    bs = dict(layer=pcbnew.B_SilkS, mirror=True, justify='left')
    b.text('ELARA  AIR-GAP PLATE', 58.0, 12.0, size=2.5, thick=0.5, **bs)
    b.text(f'53.1 MM CU, 0.5 MM AIR: {cbare:.0f} PF BARE / {cmask:.0f} PF MASKED', 58.0, 17.0, size=1.2, thick=0.25, **bs)
    b.text('COPPER FACE IS THE OTHER SIDE', 58.0, 20.5, size=1.2, thick=0.25, **bs)
    b.text('PAIR: FLIP ONE PLATE, TABS MUST NOT OVERLAP', 58.0, 24.0, size=1.2, thick=0.25, **bs)
    b.text('SOLDER THE TAB FROM THIS SIDE ONLY', 58.0, 54.0, size=1.2, thick=0.25, **bs)
    b.text('CERN-OHL-W-2.0', 58.0, 50.0, size=1.2, thick=0.25, **bs)
    b.fill()
    b.save()
    print(f'plate written: C = {cbare:.1f} pF bare, {cmask:.1f} pF with 20 um mask each side')


def _arcs():
    """Relief arcs at the four square corners, ordered for a clockwise outline."""
    c0, c1 = (SIZE - CU) / 2, (SIZE + CU) / 2
    arcs = []
    # clockwise in board coordinates (y down): TL, TR, BR, BL
    for k, (hx, hy, sx, sy) in enumerate(((INSET, INSET, c0, c0), (SIZE - INSET, INSET, c1, c0),
                                          (SIZE - INSET, SIZE - INSET, c1, c1), (INSET, SIZE - INSET, c0, c1))):
        # where the relief circle crosses the horizontal (y = sy) and vertical (x = sx) square edges
        ph = (hx + math.copysign(math.sqrt(RELIEF ** 2 - (sy - hy) ** 2), SIZE / 2 - hx), sy)
        pv = (sx, hy + math.copysign(math.sqrt(RELIEF ** 2 - (sx - hx) ** 2), SIZE / 2 - hy))
        start, end = (pv, ph) if k % 2 == 0 else (ph, pv)
        arcs.append((hx, hy, math.atan2(start[1] - hy, start[0] - hx), math.atan2(end[1] - hy, end[0] - hx)))
    return arcs


def _walk(arcs):
    out = []
    for hx, hy, a0, a1 in arcs:
        d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi     # short arc: the one inside the square
        for k in range(13):
            a = a0 + d * k / 12
            out.append((hx + RELIEF * math.cos(a), hy + RELIEF * math.sin(a)))
    return out


if __name__ == '__main__':
    main()
