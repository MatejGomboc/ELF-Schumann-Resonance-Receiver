# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Amplifier PCB -- placeholder model for fit checks.

200 x 100 x 1.6 mm board with the 24 M3 holes from params.AMP_HOLES, the
exposed GND strips (both sides, modelled as 35 um copper) and simple blocks
for the parts that matter mechanically: the 49 mm tall 100 uF film cap, the
three edge connectors and the input terminal (J1) on the board underside.
The real board comes from PCB/antenna_amplifier (KiCad); this model is only
used to check clearances.
"""

import cadquery as cq

import params as P
from common import COPPER, PCB_GREEN, STEEL, BLACK, PTFE, drill, export_step, render


def _kbox(x0, y0, x1, y1, z0, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, -y1, z0)))


def board():
    b = _kbox(0, 0, P.PCB_W, P.PCB_H, -P.PCB_T, 0)
    return drill(b, [(x, -y) for (x, y) in P.AMP_HOLES], P.M3_PCB_HOLE, -P.PCB_T - 1, 1)


def gnd_strips():
    """Exposed copper strips top and bottom (35 um) -- same footprint as the walls."""
    t = P.PLATE_CU_T
    strips = None
    for (x0, y0, x1, y1) in P.wall_rects().values():
        for z0 in (0.0, -P.PCB_T - t):
            s = _kbox(x0, y0, x1, y1, z0, z0 + t)
            strips = s if strips is None else strips.union(s)
    return drill(strips, [(x, -y) for (x, y) in P.AMP_HOLES], P.M3_PCB_HOLE, -P.PCB_T - 1, 1)


def components():
    """Dict name -> (Workplane, colour) of placeholder components."""
    out = {}
    fc = P.FILM_CAP
    out["C_film_100u"] = (_kbox(fc["x"], fc["y"], fc["x"] + fc["w"], fc["y"] + fc["d"], 0, fc["h"]),
                          cq.Color(0.85, 0.75, 0.25))
    # ICs (SOIC / SSOP bodies)
    for name, (x, y, w, d) in {
        "U_LMP7721": (20, 36, 5, 4), "U_LMP7715": (70, 70, 3, 3),
        "U_PCM1804": (130, 40, 10.2, 5.3), "U_CS8406": (150, 60, 7.8, 5.3),
        "X_MEMS_24M576": (170, 30, 3.2, 2.5),
    }.items():
        out[name] = (_kbox(x, y, x + w, y + d, 0, 1.6), BLACK)
    out["T_AES3_xfmr"] = (_kbox(160, 70, 173, 83, 0, 10), BLACK)

    for c in P.CUTOUTS:
        if c["name"].startswith("J_PWR"):
            m = P.MICROFIT
            out["J_PWR"] = (_kbox(c["pos"] - m["w"] / 2, 0, c["pos"] + m["w"] / 2, m["d"], 0, m["h"]),
                            BLACK)
        elif c["name"].startswith("J_AES3"):
            t = P.TERMBLOCK
            x1 = P.PCB_W + t["overhang"]
            out["J_AES3"] = (_kbox(x1 - t["d"], c["pos"] - t["w"] / 2, x1, c["pos"] + t["w"] / 2,
                                   0, t["h"]), cq.Color(0.1, 0.45, 0.2))
        elif c["name"].startswith("J_BNC"):
            b = P.BNC
            x_body1 = P.PCB_W - P.WALL_T - 0.5            # body stops at the wall inner face
            body = _kbox(x_body1 - b["body"], c["pos"] - b["body"] / 2, x_body1,
                         c["pos"] + b["body"] / 2, 0, b["body_h"])
            barrel = cq.Workplane("XY").add(cq.Solid.makeCylinder(
                b["barrel_d"] / 2, b["barrel_l"] + P.WALL_T,
                cq.Vector(x_body1, -c["pos"], b["zc"]), cq.Vector(1, 0, 0)))
            out["J_BNC"] = (body.union(barrel), STEEL)
    # J1 input turret on the board underside, above the PTFE feed-through
    fx, fy = P.FEEDTHROUGH_XY
    out["J1_input_turret"] = (cq.Workplane("XY").add(cq.Solid.makeCylinder(
        1.5, 3.0, cq.Vector(fx, -fy, -P.PCB_T - 3.0))), PTFE)
    return out


def assembly():
    a = cq.Assembly(name="amp_pcb")
    a.add(board(), name="pcb", color=PCB_GREEN)
    a.add(gnd_strips(), name="gnd_strips", color=COPPER)
    for n, (wp, col) in components().items():
        a.add(wp, name=n, color=col)
    return a


if __name__ == "__main__":
    a = assembly()
    export_step(a, "amp_pcb_placeholder")
    print(render(a, "amp_pcb_placeholder", direction=(0.7, -1.0, 1.0)))
