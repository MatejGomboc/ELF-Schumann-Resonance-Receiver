# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Amplifier shield -- top frame and compartment walls.

Six aluminium bars (EN AW-6082 / 6060 flat bar, 60 x 8 cut and faced to
52 x 7), butt-jointed and held with exposed M3 socket caps:

* 2 x long bar     200 x 7 x 52   (y = 0 and y = 100 edges, own the corners)
* 2 x end bar       86 x 7 x 52   (x = 0 and x = 200 edges)
* 2 x internal wall 86 x 7 x 52   (centred on x = 45 and x = 120)

Every PCB hole position gets a tapped M3 hole from the bottom (tray screws)
and from the top (lid screws).  Connector cut-outs are milled into the bar
bottoms.  CadQuery frame: X = x_kicad, Y = -y_kicad, Z = 0 at PCB top.
"""

import cadquery as cq

import params as P
from common import export_step, render


def _cyl(d, pnt, direction, length):
    return cq.Workplane("XY").add(
        cq.Solid.makeCylinder(d / 2, length, cq.Vector(*pnt), cq.Vector(*direction)))


def _box(x0, y0, x1, y1, z0, z1):
    """Box from KiCad xy rectangle and z range -> CadQuery solid."""
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, -y1, z0)))


def _joint_xs():
    """x positions (KiCad) of bars that butt into the long bars."""
    return [P.WALL_T / 2, P.PCB_W - P.WALL_T / 2] + list(P.INTERNAL_WALL_X)


def make_bar(name):
    x0, y0, x1, y1 = P.wall_rects()[name]
    bar = _box(x0, y0, x1, y1, 0.0, P.FRAME_H)

    # vertical tapped holes (modelled at tap-drill size)
    for (hx, hy) in P.AMP_HOLES:
        if x0 < hx < x1 and y0 < hy < y1:
            bar = bar.cut(_cyl(P.M3_TAP_DRILL, (hx, -hy, 0), (0, 0, 1), P.FRAME_TAP_DEPTH_BOTTOM))
            bar = bar.cut(_cyl(P.M3_TAP_DRILL, (hx, -hy, P.FRAME_H), (0, 0, -1), P.FRAME_TAP_DEPTH_TOP))

    # joints
    if name.startswith("long"):
        for jx in _joint_xs():
            for jz in P.JOINT_Z:
                bar = bar.cut(_cyl(P.M3_CLEAR, (jx, -y0 + 1, jz), (0, -1, 0), (y1 - y0) + 2))
    else:
        xc = (x0 + x1) / 2
        for jz in P.JOINT_Z:
            bar = bar.cut(_cyl(P.M3_TAP_DRILL, (xc, -y0, jz), (0, -1, 0), P.JOINT_TAP_DEPTH))
            bar = bar.cut(_cyl(P.M3_TAP_DRILL, (xc, -y1, jz), (0, 1, 0), P.JOINT_TAP_DEPTH))

    # connector cut-outs
    edge_bar = {"top": "long_top", "bottom": "long_bottom",
                "left": "end_left", "right": "end_right"}
    for c in P.CUTOUTS:
        if edge_bar[c["edge"]] != name:
            continue
        e = c["edge"]
        if c["shape"] == "rect":
            lo, hi = c["pos"] - c["w"] / 2, c["pos"] + c["w"] / 2
            if e in ("top", "bottom"):
                bar = bar.cut(_box(lo, y0 - 1, hi, y1 + 1, -1, c["h"]))
            else:
                bar = bar.cut(_box(x0 - 1, lo, x1 + 1, hi, -1, c["h"]))
        else:
            if e in ("left", "right"):
                bar = bar.cut(_cyl(c["d"], (x0 - 1, -c["pos"], c["zc"]), (1, 0, 0), (x1 - x0) + 2))
            else:
                bar = bar.cut(_cyl(c["d"], (c["pos"], -y0 + 1, c["zc"]), (0, -1, 0), (y1 - y0) + 2))
    return bar


def build():
    """Return dict name -> Workplane for all six bars."""
    return {n: make_bar(n) for n in P.wall_rects()}


def joint_screw_positions():
    """(x, y, z, direction) of the 16 corner/tee joint screws (CQ coords)."""
    out = []
    for jx in _joint_xs():
        for jz in P.JOINT_Z:
            out.append((jx, 0.0, jz, (0, 1, 0)))            # head on the y = 0 face
            out.append((jx, -P.PCB_H, jz, (0, -1, 0)))      # head on the y = 100 face
    return out


if __name__ == "__main__":
    bars = build()
    frame = cq.Workplane("XY")
    for n, b in bars.items():
        export_step(b, f"amp_frame_{n}")
        frame = frame.add(b.vals())
    comp = cq.Compound.makeCompound([v for b in bars.values() for v in b.vals()])
    export_step(cq.Workplane().add(comp), "amp_frame")
    print(render(cq.Workplane().add(comp), "amp_frame_iso", direction=(1, -1.3, -0.8)))
