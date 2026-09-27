# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Amplifier shield -- bottom tray.

One piece, pocket-milled from 15 mm aluminium plate (faced to 14 mm):
three 12 mm deep pockets that mirror the compartments above the PCB, leaving
7 mm walls under the GND strips and a 2 mm floor.  Long M3x25 button heads
go through the tray and the PCB into the tapped wall bottoms, clamping the
PCB's exposed GND strips between aluminium on both faces.

A 10 mm hole under compartment 1 carries the PTFE input feed-through.

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
    fx, fy = P.FEEDTHROUGH_XY
    tray = tray.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(
        P.FEEDTHROUGH_HOLE_D / 2, P.TRAY_T + 2, cq.Vector(fx, -fy, z_top - P.TRAY_T - 1))))
    return tray


def feedthrough():
    """Machined PTFE bush: flange outside the floor, spigot through it."""
    fx, fy = P.FEEDTHROUGH_XY
    z_floor_out = -P.PCB_T - P.TRAY_T
    flange = (cq.Workplane("XY").circle(P.FEEDTHROUGH_FLANGE_D / 2)
              .extrude(P.FEEDTHROUGH_FLANGE_T).translate((0, 0, -P.FEEDTHROUGH_FLANGE_T)))
    spigot = (cq.Workplane("XY").circle(P.FEEDTHROUGH_HOLE_D / 2 - 0.05)
              .extrude(P.TRAY_FLOOR_T + P.FEEDTHROUGH_SPIGOT_L))
    bush = flange.union(spigot)
    bore = cq.Workplane("XY").circle(P.FEEDTHROUGH_BORE / 2).extrude(60).translate((0, 0, -20))
    return bush.cut(bore).translate((fx, -fy, z_floor_out))


if __name__ == "__main__":
    t = build()
    export_step(t, "amp_tray")
    export_step(feedthrough(), "amp_feedthrough_ptfe")
    print(render(t, "amp_tray", direction=(0.7, -1.0, 1.0)))
