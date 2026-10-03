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

import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))

from kicadgen.pcb import Board, near, rect_pts  # noqa: E402

NAME = 'antenna_amplifier'
W, H = 200.0, 100.0
STRIP = 7.0
WALLS = (45.0, 120.0)                 # wall centre lines
HOLES = ([(x, y) for y in (3.5, 96.5) for x in (3.5, 45.0, 82.5, 120.0, 158.0, 196.5)] +
         [(x, y) for x in (3.5, 196.5) for y in (15.0, 50.0, 85.0)] +
         [(x, y) for x in WALLS for y in (15.0, 50.0, 85.0)])
# frame cut-outs where connectors pass the perimeter wall: (x0, y0, x1, y1)
CUTOUTS = [(178.0, 0.0, 192.0, STRIP), (W - STRIP, 23.0, W, 43.0)]

# guard island (C1): IN_P lives only inside this rectangle; the polygon notches out
# U201 pins 3 (V-) and 4 (OUT), which must stay routable
ISLAND = (15.5, 36.4, 33.0, 54.6)
ISLAND_POLY = [(15.5, 36.4), (33.0, 36.4), (33.0, 51.95), (27.6, 51.95), (27.6, 54.6), (15.5, 54.6)]

F, B, IN1, IN2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu

# ref: (x, y, rotation) -- board mm. Parts sit in aligned rows and columns on a
# 0.5 mm grid (IPC-1902), same-type parts share one orientation, and each IC's
# capacitors form a tidy cell around it (smallest value nearest its pin).


def row(refs, x0, y, dx, rot=0):
    """Parts in a row at a fixed pitch: {ref: (x, y, rot)}."""
    return {r: (x0 + i * dx, y, rot) for i, r in enumerate(refs)}


def ldo_cell(u, x0, y0, left, right):
    """ADM7150 with its capacitors: VREG/VOUT/BYP in a column on the left (pad 1
    towards the pins, 4 mm apart so each has room for its label), VIN/REF on the
    right."""
    out = {u: (x0, y0, 0)}
    for ref, y in zip(left, (y0 - 4.0, y0, y0 + 4.0)):
        out[ref] = (x0 - 6.8, y, 180)
    for ref, y in zip(right, (y0 - 2.8, y0 + 2.8)):
        out[ref] = (x0 + 6.8, y, 0)
    return out


PLACE = {
    # ---- C1 INPUT: island parts fixed by the feed-through. The LMP7721 has both inputs
    # at its pin 1/8 end; IN- (pin 8) stays outside the island, and its parts (Rf, Cf, Rg
    # and the guard buffer that senses it) form one column north-east of U201, fed by a
    # single spine from pin 8. The guard drive (R203, C205) enters the ring at its
    # north-east corner; the V+ decoupling sits beside pin 6.
    'J201': (20.0, 50.1, 0), 'J202': (20.0, 40.0, 0), 'U201': (32.0, 52.0, 0),
    'R201': (37.4, 49.5, 0), 'C201': (37.4, 47.1, 0), 'R202': (37.6, 44.7, 0),
    'U202': (37.5, 40.5, 0), 'C206': (40.4, 38.6, 90),
    'R203': (35.4, 37.5, 180), 'C205': (34.2, 34.5, 0), 'TP203': (36.5, 30.0, 0),
    'C203': (37.2, 53.4, 0), 'C204': (37.6, 56.4, 0),
    # ---- C2 ANALOG, band 1: ADC driver chain, left to right
    'C301': (52.5, 15.0, 0), 'R302': (81.0, 13.0, 0), 'R301': (81.0, 17.0, 0),
    'C302': (86.0, 15.0, 270), 'U301': (92.0, 14.0, 0), 'C304': (96.5, 13.5, 90),
    'TP201': (52.5, 23.5, 0),
    # band 2: antenna bias (left), preamp supply filter and 5 V LDO (right); the
    # bias buffer's test point sits next to a GND test point for the meter
    'C207': (55.5, 36.0, 0), 'R204': (71.0, 33.5, 270), 'R205': (71.0, 38.5, 270),
    'U203': (76.5, 36.0, 0), 'C208': (80.5, 35.5, 90), 'R206': (76.5, 40.5, 180),
    'TP202': (80.5, 41.0, 0), 'TP204': (85.0, 41.0, 0),
    'C114': (85.0, 35.0, 90), 'C113': (87.5, 35.0, 90), 'R101': (91.5, 34.0, 180),
    **ldo_cell('U101', 104.0, 34.0, ('C104', 'C105', 'C106'), ('C103', 'C107')),
    # band 3: Cg
    'C202': (52.5, 80.0, 0),
    # ---- C3 DIGITAL, top band: CS8406 mode switches with their pull-downs in line
    # with the switched pins (labels in the channel between), 3.3 V LDO, power entry
    **row(['R404', 'R405', 'R406', 'R407', 'R408', 'R409', 'R410', 'R411'], 126.5, 9.0, 2.54, 90),
    'SW401': (126.5, 24.0, 90),
    **ldo_cell('U102', 158.0, 14.0, ('C109', 'C110', 'C111'), ('C108', 'C112')),
    'C102': (170.0, 15.0, 90), 'D101': (176.0, 13.0, 0), 'D102': (176.0, 17.0, 0),
    'J101': (183.5, 9.5, 0), 'C101': (183.5, 16.0, 0),
    # middle band: PCM1804 and CS8406 side by side at the same height, so the I2S
    # lines (pins 15-17 / 12-14) run straight across; their capacitors in one row
    # above; AES3 out to the right wall
    **row(['C305', 'C306', 'C307', 'C308', 'C309', 'C310', 'C311', 'C312', 'C313', 'C314'], 125.0, 32.0, 2.4, 90),
    'U302': (136.0, 40.0, 0), 'U401': (152.0, 40.0, 0),
    'R303': (127.0, 37.3, 0), 'C303': (130.0, 38.05, 270),
    'C315': (128.0, 46.5, 90), 'C316': (130.5, 46.5, 90),
    'C404': (146.3, 39.0, 90), 'C403': (157.5, 41.5, 90), 'C402': (157.5, 46.0, 90),
    'R412': (157.0, 31.5, 0), 'C405': (160.5, 31.5, 0), 'R413': (160.5, 39.12, 180),
    'TR401': (164.9, 31.5, 0), 'J401': (183.5, 29.5, 270), 'C406': (182.5, 45.0, 0),
    # clock below the CS8406, reset and overflow test point between the chips
    'Y402': (161.5, 51.5, 0), 'C407': (161.5, 54.5, 0), 'Y401': (161.5, 58.0, 0), 'C401': (161.5, 61.0, 0),
    'R401': (157.0, 50.5, 180), 'R402': (166.0, 50.5, 0),
    'R304': (142.5, 48.5, 90), 'C317': (145.0, 48.5, 90), 'R403': (152.0, 48.5, 0),
    'SW301': (144.0, 59.5, 0), 'TP301': (136.0, 55.5, 0),
    # bottom band: PCM1804 mode switches (internal pull-downs; BYPAS has R305)
    'R305': (141.74, 70.0, 90), 'SW302': (126.5, 81.5, 90),
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
    # ANT_BIAS leaves the island through the gap in the top-side ring (it sits at
    # guard potential, 2.5 V); the router continues from the stub end
    j1 = b.pad_xy('J202', 1)
    b.track('ANT_BIAS', [j1, (j1[0], ISLAND[1] - 1.0)], width=0.3, layer=F)
    b.via('ANT_BIAS', j1[0], ISLAND[1] - 1.0)          # lets the router leave on In2 (under the walls)
    x0, y0, x1, y1 = ISLAND
    L, T, Bm = x0 + 1.0, y0 + 1.0, y1 - 1.0          # ring centre lines
    xr = (g2[0] + g7[0]) / 2                           # under the body, between pin 1 and pin 8
    xb = t[0] + 2.6
    # top-side ring: pin 2 -> around the island -> down between pins 1/8 -> pin 7
    b.track('GUARD', [g2, (xb, g2[1]), (xb, Bm), (L, Bm), (L, T), (t[0] - 1.1, T)], width=0.5)
    b.track('GUARD', [(t[0] + 1.1, T), (xr, T), (xr, g7[1]), g7], width=0.5)
    b.track('GUARD', [g2, (xr, g2[1])], width=0.5)
    for x in (t[0] - 1.1, t[0] + 1.1):
        b.via('GUARD', x, T)
    # guard drive, hand-routed so the ring and its driver form one piece of copper:
    # from the ring's north-east corner straight out to R203 pad 2 (470 R from the
    # buffer), with the 220 pF stability cap (C205 pad 1) tapped off on the way
    r2, c1 = b.pad_xy('R203', 2), b.pad_xy('C205', 1)
    b.track('GUARD', [(xr, T), (r2[0], T), r2], width=0.4)
    b.track('GUARD', [c1, (c1[0], T)], width=0.4)
    # IN- (pin 8, just outside the island): one spine up the column of its parts,
    # Rf, Cf and Rg tapped off on the way, ending at the guard buffer's input
    p8, u3 = b.pad_xy('U201', 8), b.pad_xy('U202', 3)
    xs = p8[0] + 0.85
    b.track('IN_N', [p8, (xs, p8[1]), (xs, u3[1]), u3], width=0.3)
    for ref in ('R201', 'C201', 'R202'):
        x1, y1 = b.pad_xy(ref, 1)
        b.track('IN_N', [(xs, y1), (x1, y1)], width=0.3)
    # bottom-side ring: closed around the turret and the bias link
    xbb = t[0] + 3.8
    b.track('GUARD', [(L, T), (xbb, T), (xbb, Bm), (L, Bm), (L, T)], width=0.5, layer=B)
    for y in [T + i * 2.0 for i in range(int((Bm - T) / 2.0) + 1)]:
        b.via('GUARD', L, y)
    for x in [L + 2.0 * i for i in range(1, int((xb - L) / 2.0) + 1)]:
        b.via('GUARD', x, Bm)
    # guard planes under the island on both inner layers
    for layer in (IN1, IN2):
        b.zone('GUARD', layer, ISLAND_POLY, priority=10, clearance=0.3, name='guard plane')
    # no pours and no solder mask on the island
    b.keepout([F, B], ISLAND_POLY, tracks=False, vias=False, pour=True, name='island no pour')
    for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
        b.poly(layer, ISLAND_POLY)


def mechanics(b):
    b.outline(W, H)
    b.title_block('ELARA antenna amplifier', '0.2', date='2026-09-30')
    for x, y in HOLES:
        b.hole(x, y)
    for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
        for r in strips():
            b.rect(layer, *r)


def island_rects():
    """The island mask opening (ISLAND_POLY) as two rectangles."""
    (x0, y0), (x1, _), (_, yn), (xn, _), _, (_, y1) = ISLAND_POLY
    return [(x0, y0, x1, yn), (x0, yn, xn, y1)]


def compartment_labels(b, big, avoid_tracks=False):
    b.text_free('02 ANALOG', near((50.5, 90.0), (49.0, 9.0, 92.0, 91.0)), avoid_tracks=avoid_tracks, **big)
    b.text_free('03 DIGITAL', near((125.5, 90.0), (124.0, 9.0, 190.0, 91.0), 0.5), avoid_tracks=avoid_tracks, **big)


def silkscreen(b):
    """Board texts; each goes to the first candidate spot clear of parts and copper."""
    clear = strips() + [ISLAND]
    big = dict(size=3.0, thick=0.6, keep_clear=clear)
    b.text('01 INPUT', 9.0, 11.0, size=3.0, thick=0.6)
    compartment_labels(b, big)
    b.text('IN', 20.0, 56.8, size=1.5, thick=0.3, justify='center')
    b.text('GUARDED - NO MASK', 9.0, 31.4, size=1.0, thick=0.2)
    b.text('DO NOT TOUCH', 9.0, 32.9, size=1.0, thick=0.2)
    b.text('ELARA', 9.0, 85.0, size=4.0, thick=0.8)
    b.text('ANTENNA AMPLIFIER  REV 0.2', 9.0, 89.5, size=1.2, thick=0.25)
    # back: mirrored, so 'left' justification runs towards smaller x
    bs = dict(layer=pcbnew.B_SilkS, mirror=True, justify='left', keep_clear=clear)
    b.text_block_free([('ELARA', 0.0, 4.0, 0.8),
                       ('ELF ATMOSPHERIC RADIO ANALYSER', 5.0, 1.5, 0.3),
                       ('ANTENNA AMPLIFIER  REV 0.2', 8.0, 1.5, 0.3),
                       ('4 LAYER  1.6 MM  CERN-OHL-W-2.0', 11.0, 1.2, 0.25)],
                      near((95.0, 64.0), (60.0, 12.0, 115.0, 80.0)), **bs)
    b.text_free('ANTENNA FROM BELOW', near((33.0, 58.5), (25.0, 56.0, 40.0, 70.0), 0.5), size=1.2, thick=0.25,
                avoid_tracks=True, **bs)


def routing_keepouts(b):
    """Temporary rule areas that steer Freerouting (removed in 'finish')."""
    for r in strips():
        b.keepout([F, B], rect_pts(*r), name='ko wall')
        b.keepout([IN1, IN2], rect_pts(*r), tracks=False, vias=True, name='ko wall vias')
    b.keepout([F, B, IN1, IN2], ISLAND_POLY, name='ko island')
    # nothing routed on top under the LMP7721 between its pad rows (only the guard bar
    # and the V- via live there), so OUT leaves pin 4 southwards
    x, y = PLACE['U201'][:2]
    b.keepout([F], rect_pts(x - 1.4, y - 2.45, x + 1.4, y + 2.45), name='ko U201 body')


def hwck1(b):
    """HWCK1 (SW401 pin 15 -> U401 pin 27), fixed on the path Freerouting 1.9 found
    before the input compartment was re-placed; since then it walls this one line in
    behind SFMT0/SFMT1 and leaves it open."""
    s, e, v = b.pad_xy('SW401', 15), b.pad_xy('U401', 27), (154.06, 33.67)
    b.track('HWCK1', [s, (130.14, 17.48), (132.05, 17.48), (132.85, 16.68), (132.85, 16.09),
                      (134.51, 14.43), (143.33, 14.43), (143.9, 15.0), (144.47, 15.0),
                      (154.27, 24.8), (154.27, 33.47), v], width=0.2, layer=IN2)
    b.via('HWCK1', *v)
    b.track('HWCK1', [v, (155.15, 33.67), (157.01, 35.53), (157.01, 36.03), (156.61, e[1]), e], width=0.2)


def dip_buses(b):
    """Pre-route the +3V3 side of each DIP switch as a straight bus along its pin row."""
    for ref, n in (('SW302', 7), ('SW401', 8)):
        pts = [b.pad_xy(ref, i) for i in range(1, n + 1)]
        b.track('+3V3', pts, width=0.4, layer=B)


def build(keepouts):
    """Deterministic board build shared by both stages."""
    b = Board(os.path.join(HERE, 'design_netlist.json'),
              {'elara': os.path.join(HERE, '..', 'elara.pretty')}, os.path.join(HERE, f'{NAME}.kicad_pcb'))
    mechanics(b)
    place(b)
    guard_island(b)
    dip_buses(b)
    hwck1(b)
    # every SMD GND pad gets its own via to the planes BEFORE routing, so the
    # router works around them (standard fan-out-first practice)
    nf = b.fanout('GND', exclude=lambda x, y: ISLAND[0] - 1 < x < ISLAND[2] + 1 and ISLAND[1] - 1 < y < ISLAND[3] + 1)
    print('GND fan-out vias', nf, 'failed:', b.fanout_failed)
    # LMP7721 V- (pin 3) sits in the island notch, outside the fan-out: its own via
    # under the package body, south of the guard bar (OUT, pin 4, leaves southwards)
    x, y = b.pad_xy('U201', '3')
    v = next((x + d, y) for d in (2.2, 2.0, 2.4, 1.8) if b.free_for_via(x + d, y, avoid_courtyards=False))
    b.track('GND', [(x, y), v], width=0.4)
    b.via('GND', *v)
    # ADM7150 exposed pads: three vias in the pad to the plane (also lets the EP be
    # soldered by hand from the back)
    for ref in ('U101', 'U102'):
        x, y = b.pad_xy(ref, '9')
        for dy in (-0.9, 0.0, 0.9):
            b.via('GND', x, y + dy)
    silkscreen(b)
    if keepouts:
        routing_keepouts(b)
    b.board.SetLayerType(IN1, pcbnew.LT_POWER)          # solid GND plane, never routed
    b.zone('GND', IN1, rect_pts(0.3, 0.3, W - 0.3, H - 0.3), priority=0, name='GND plane')
    return b


def stage_place():
    b = build(keepouts=True)
    b.save()
    # GND stays in the router's copy: every GND pad already has its fan-out via to
    # the In1 plane (built before routing), so Freerouting sees GND as connected and
    # keeps clear of the fan-out copper. The outer-layer pours come in 'finish'.
    dsn = os.path.join(HERE, f'{NAME}.dsn')
    if not pcbnew.ExportSpecctraDSN(b.board, dsn):
        raise SystemExit('DSN export failed')
    print('placed', len(b.fps), 'footprints; wrote', os.path.basename(dsn))


def stage_finish():
    b = build(keepouts=False)          # same board, without the routing keep-outs
    ses = os.path.join(HERE, f'{NAME}.ses')
    if not pcbnew.ImportSpecctraSES(b.board, ses):
        raise SystemExit('SES import failed')
    print('dangling router stubs removed:', b.remove_dangling())
    # compartment labels again, now clear of the routed tracks too (before the
    # stitching vias, which then keep clear of the lettering)
    b.remove_texts(('02 ANALOG', '03 DIGITAL'))
    compartment_labels(b, dict(size=3.0, thick=0.6, keep_clear=strips() + [ISLAND]), avoid_tracks=True)
    # exposed wall strips: solid GND copper on both outer layers
    for i, r in enumerate(strips()):
        for layer in (F, B):
            b.zone('GND', layer, rect_pts(*r), priority=5 + i, clearance=0.3, thermal=False, name='wall strip')
    # keep every pour clear of unplated holes (connector locating pegs)
    for fp in b.board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH and not fp.GetReference().startswith('H'):
                p = pad.GetPosition()
                cx, cy = pcbnew.ToMM(p.x) - 50.0, pcbnew.ToMM(p.y) - 50.0
                r = pcbnew.ToMM(pad.GetDrillSize().x) / 2 + 0.5
                b.keepout([F, IN1, IN2, B], [(cx + r * math.cos(a / 8 * math.pi), cy + r * math.sin(a / 8 * math.pi))
                                             for a in range(16)], tracks=False, vias=False, pour=True,
                          name='npth no pour')

    # GND pours on every copper layer (the In1 plane already exists)
    full = rect_pts(0.3, 0.3, W - 0.3, H - 0.3)
    for layer in (F, IN2, B):
        b.zone('GND', layer, full, priority=0, clearance=0.3, name='GND pour')
    n = 0
    for x0, y0, x1, y1 in strips():
        if x1 - x0 > y1 - y0:
            pts = [(x0 + 2.0 + i * 3.0, (y0 + y1) / 2 + dy) for i in range(int((x1 - x0 - 4) / 3) + 1) for dy in (-2, 2)]
        else:
            pts = [((x0 + x1) / 2 + dx, y0 + 2.0 + i * 3.0) for i in range(int((y1 - y0 - 4) / 3) + 1) for dx in (-2, 2)]
        pts = [p for p in pts if all((p[0] - hx) ** 2 + (p[1] - hy) ** 2 > 16 for hx, hy in HOLES)]
        n += b.stitch(pts, avoid_courtyards=False)
    grid = [(x, y) for x in [9.0 + 5.0 * i for i in range(37)] for y in [9.0 + 5.0 * j for j in range(17)]]
    grid = [p for p in grid if not (ISLAND[0] - 1 < p[0] < ISLAND[2] + 1 and ISLAND[1] - 1 < p[1] < ISLAND[3] + 1)]
    n += b.stitch(grid)
    # no silkscreen ink on the bare island or on the wall contact strips
    print('silk items clipped:', b.clip_silk(strips() + island_rects()))
    print('footprint silk widened / cut clear of pads:', b.silk_for_fab())
    hidden = b.tidy_refs(keep_clear=strips() + [ISLAND])
    print('references hidden (no room on silk, still on F.Fab):', hidden)
    for r in hidden:                 # named beside the part in the assembly drawing
        b.fab_ref_beside(r)
    print('fab-layer values hidden:', b.hide_fab_values())
    print('fab-layer reference copies hidden (silk reference shown):', b.hide_fab_refs())
    print('nets renamed to schematic names:', b.rename_nets_to_schematic(os.path.join(HERE, 'design_netlist.json')))
    b.fill()
    b.save()
    set_rule_severity(os.path.join(HERE, f'{NAME}.kicad_pro'), solder_mask_bridge='warning')
    print('finished: stitching vias', n)


def set_rule_severity(pro, **rules):
    """The guard island and wall strips are deliberately unmasked, so mask bridges there
    are expected: report them as warnings (the rule table lives in the project file)."""
    import json
    with open(pro, encoding='utf-8') as f:
        d = json.load(f)
    d.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rule_severities', {}).update(rules)
    with open(pro, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=2)


if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'place'
    {'place': stage_place, 'finish': stage_finish}[stage]()
