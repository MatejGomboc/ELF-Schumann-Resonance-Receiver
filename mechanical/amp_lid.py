# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Amplifier shield -- lid.

2 mm aluminium sheet (EN AW-5754 H22 or 6082 plate), bead-blasted.
Screwed to the tops of all six wall bars with 24 exposed M3x8 button heads
at the PCB hole positions.  The lid is also the mounting face of the whole
shield: two ears (one at each short end) carry 2 x M4 holes each for the
studs on the mounting plate.  Flat part -> DXF exported for waterjet/laser
or hand marking-out.
"""

import cadquery as cq

import params as P
from common import drill, export_dxf, export_step, render


def ear_holes():
    """M4 ear hole centres, CQ XY."""
    out = []
    for yk in P.LID_EAR_HOLES_Y:
        out.append((-P.LID_EAR_HOLE_X_OFF, -yk))
        out.append((P.PCB_W + P.LID_EAR_HOLE_X_OFF, -yk))
    return out


def build(z0=P.FRAME_H):
    w = P.PCB_W + 2 * P.LID_EAR
    lid = (cq.Workplane("XY").box(w, P.PCB_H, P.LID_T, centered=False)
           .translate((-P.LID_EAR, -P.PCB_H, 0)))
    pts = [(x, -y) for (x, y) in P.AMP_HOLES]
    lid = drill(lid, pts, P.M3_CLEAR, -1, P.LID_T + 1)
    lid = drill(lid, ear_holes(), P.M4_CLEAR, -1, P.LID_T + 1)
    return lid.translate((0, 0, z0))


if __name__ == "__main__":
    lid = build()
    export_step(lid, "amp_lid")
    export_dxf(build(z0=0).translate((0, 0, -P.LID_T / 2)), "amp_lid")
    print(render(lid, "amp_lid", direction=(0.6, -0.8, 1.0),
                 title="Antenna-amplifier shield -- lid with M4 mounting ears"))
