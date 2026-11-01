# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Amplifier shield -- bottom tray.

One piece, pocket-milled from 15 mm aluminium plate (faced to 14 mm):
three 12 mm deep pockets that mirror the compartments above the PCB, leaving
7 mm walls under the GND strips and a 2 mm floor.  Long M3x25 button heads
go through the tray and the PCB into the tapped wall bottoms, clamping the
PCB's exposed GND strips between aluminium on both faces.

Two 3.45 mm press-fit holes (in 8 mm spot-faces from outside, leaving the 1.6 mm
panel the part is rated for) under compartment 1 carry the Keystone 11157 PTFE
feed-through terminals (J201 input, J203 plate return), and
blind relief pockets in the rim clear parts that stick out under the board
(the Micro-Fit's PCB-lock peg).

Manual-shop alternative (no CNC): a 12 x 7 bar frame (same layout as the
top frame) screwed onto a 2 mm floor plate -- the hole pattern is identical.
"""

import cadquery as cq

import params as P
from common import drill, export_step, render


def build():
    z_top = -P.PCB_T                     # tray top face touches the PCB bottom
    tray = (cq.Workplane("XY").box(P.PCB_W, P.PCB_H, P.TRAY_T, centered=False)
            .translate((0, -P.PCB_H, z_top - P.TRAY_T)))
    for c in P.COMPARTMENTS.values():
        w, h = c["x1"] - c["x0"], c["y1"] - c["y0"]
        pocket = (cq.Workplane("XY").box(w, h, P.TRAY_DEPTH + 1, centered=False)
                  .edges("|Z").fillet(P.TRAY_POCKET_R)
                  .translate((c["x0"], -c["y1"], z_top - P.TRAY_DEPTH)))
        tray = tray.cut(pocket)
    pts = [(x, -y) for (x, y) in P.AMP_HOLES]
    tray = drill(tray, pts, P.M3_CLEAR, z_top - P.TRAY_T - 1, z_top + 1)
    z_out = z_top - P.TRAY_T
    for fx, fy in (P.FEEDTHROUGH_XY, P.FEEDTHROUGH2_XY):
        # press-fit hole for the Keystone 11157, in a spot-face from outside that leaves
        # the 1.6 mm panel the terminal is rated for
        tray = tray.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(
            P.FEEDTHROUGH_HOLE_D / 2, P.TRAY_T + 2, cq.Vector(fx, -fy, z_out - 1))))
        tray = tray.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(
            P.FEEDTHROUGH_SPOTFACE_D / 2, P.FEEDTHROUGH_SPOTFACE_DEPTH + 1, cq.Vector(fx, -fy, z_out - 1))))
    for (x, y, d, depth) in P.TRAY_RELIEFS:          # blind pockets in the rim for pegs under the board
        tray = tray.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(
            d / 2, depth + 1, cq.Vector(x, -y, z_top - depth))))
    return tray


def feedthrough(xy=None):
    """Keystone 11157 PTFE press-fit feed-through (J201 input; xy=P.FEEDTHROUGH2_XY for
    the identical plate-return terminal under J203): PTFE flange seated in the
    spot-face, PTFE body through the 1.6 mm panel, tinned brass pin through both.
    Envelope model: the flange thickness is assumed (params)."""
    fx, fy = xy or P.FEEDTHROUGH_XY
    z_seat = -P.PCB_T - P.TRAY_T + P.FEEDTHROUGH_SPOTFACE_DEPTH     # flange's inner face
    flange = (cq.Workplane("XY").circle(P.FEEDTHROUGH_FLANGE_D / 2)
              .extrude(P.FEEDTHROUGH_FLANGE_T).translate((0, 0, -P.FEEDTHROUGH_FLANGE_T)))
    body = cq.Workplane("XY").circle(P.FEEDTHROUGH_HOLE_D / 2 - 0.02).extrude(P.FEEDTHROUGH_PANEL_T)
    pin = (cq.Workplane("XY").circle(P.FEEDTHROUGH_PIN_D / 2)
           .extrude(P.FEEDTHROUGH_PIN_OUT + P.FEEDTHROUGH_PIN_IN).translate((0, 0, -P.FEEDTHROUGH_PIN_OUT)))
    return flange.union(body).union(pin).translate((fx, -fy, z_seat))


if __name__ == "__main__":
    t = build()
    export_step(t, "amp_tray")
    export_step(feedthrough(), "amp_feedthrough_ptfe")
    print(render(t, "amp_tray", direction=(0.7, -1.0, 1.0),
                 title="Antenna-amplifier shield -- milled tray, PTFE bush hole"))
