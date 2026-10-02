# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Amplifier PCB -- the real board, for fit checks and renders.

The populated board comes from KiCad (PCB/antenna_amplifier/fab/
antenna_amplifier.step, written by tools/fab_outputs.sh) via board_parts.py:
the board body with all its holes and every fitted part, by reference. Added
here: the exposed GND strips (35 um copper, both sides, under the walls) and
the mated plugs of the edge connectors (board_parts.plugs).
"""

import cadquery as cq

import board_parts
import params as P
from common import COPPER, PCB_GREEN, BLACK, drill, render

BOARD = "antenna_amplifier"


def _kbox(x0, y0, x1, y1, z0, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, -y1, z0)))


def gnd_strips():
    """Exposed copper strips top and bottom (35 um) -- same footprint as the walls."""
    t = P.PLATE_CU_T
    strips = None
    for (x0, y0, x1, y1) in P.wall_rects().values():
        for z0 in (0.0, -P.PCB_T - t):
            s = _kbox(x0, y0, x1, y1, z0, z0 + t)
            strips = s if strips is None else strips.union(s)
    return drill(strips, [(x, -y) for (x, y) in P.AMP_HOLES], P.M3_PCB_HOLE, -P.PCB_T - 1, 1)


_CACHE = {}


def real():
    """(board body, {ref: Shape}) from the KiCad STEP, loaded once."""
    if BOARD not in _CACHE:
        _CACHE[BOARD] = board_parts.load(BOARD, P.PCB_T)
    return _CACHE[BOARD]


def components():
    """{name: Shape} of every fitted part plus the mated plugs."""
    _, parts = real()
    out = dict(parts)
    out.update(board_parts.plugs())
    return out


def assembly(detail=False):
    """detail: real part shapes (renders); otherwise bounding-box envelopes (STEP export)."""
    body, _ = real()
    a = cq.Assembly(name="amp_pcb")
    a.add(cq.Workplane().add(body), name="pcb", color=PCB_GREEN)
    a.add(gnd_strips(), name="gnd_strips", color=COPPER)
    shapes = list(components().values())
    if not detail:
        shapes = [board_parts.envelope(s) for s in shapes]
    comp = cq.Compound.makeCompound(shapes)
    a.add(cq.Workplane().add(comp), name="parts", color=BLACK)
    return a


if __name__ == "__main__":
    # no STEP here: the populated board is PCB/antenna_amplifier/fab/antenna_amplifier.step
    print(render(assembly(detail=True), "amp_pcb_populated", direction=(0.7, -1.0, 1.0),
                 title="Antenna-amplifier PCB -- real parts from KiCad"))
