# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
PSU aluminium enclosure (separate, removable unit).

Same construction language as the amplifier shield, but from STOCK sizes
only, so that it needs nothing more than a saw, a drill press and taps:

* 4 x wall bar from 50 x 6 mm aluminium flat bar (inner height = 50 mm)
    2 x long  168 x 6 x 40   (own the corners)
    2 x short  96 x 6 x 40   (M16 mains gland / M12 output gland)
* base 3 mm plate with two mounting ears (carries the PE stud)
* lid  2 mm plate
* 6 x M3x8 button per plate into tapped bar edges, 8 x M3x12 socket
  corner-joint screws, 4 x M3x10 hex standoffs under the PCB: metal at the
  mains end (H1/H3, the PCB's PE holes), NYLON at the receiver end (H2/H4,
  in 5 mm copper keep-outs) so the receiver side never touches PE.
* M16 mains gland in line with J1, M12 output gland in line with J2, and
  the M4 PE stud through the mains-end bar above the IRM-05.

The board is the real KiCad model (board_parts.py), top edge towards +Y.

Local frame: inner cavity X 0..156, Y 0..96, Z 0..50 (Z = 0 is the top
face of the base plate).  Commercial alternative: Hammond 1590E die-cast
(see README) -- the PCB, standoffs and gland positions carry over.
"""

import cadquery as cq

import board_parts
import params as P
from common import (ALU, ALU_DARK, BLACK, COPPER, NYLON, PCB_GREEN, STEEL, button_screw,
                    drill, export_dxf, export_step, hex_nut, render, socket_screw)

T = P.PSU_BAR_T
IW, ID, IH = P.PSU_INNER_W, P.PSU_INNER_D, P.PSU_INNER_H
OW, OD = IW + 2 * T, ID + 2 * T          # 168 x 108


def _box(x0, y0, z0, x1, y1, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _cyl(d, pnt, direction, length):
    return cq.Workplane("XY").add(
        cq.Solid.makeCylinder(d / 2, length, cq.Vector(*pnt), cq.Vector(*direction)))


def plate_screw_points():
    """Lid/base screw positions (XY) on the bar centre lines."""
    c = T / 2
    return [(-c, -c), (IW / 2, -c), (IW + c, -c),
            (-c, ID + c), (IW / 2, ID + c), (IW + c, ID + c)]
    # no screws mid-way along the short bars: the gland holes live there


def bars():
    out = {}
    out["long_front"] = _box(-T, -T, 0, IW + T, 0, IH)
    out["long_back"] = _box(-T, ID, 0, IW + T, ID + T, IH)
    out["short_mains"] = _box(-T, 0, 0, 0, ID, IH)
    out["short_output"] = _box(IW, 0, 0, IW + T, ID, IH)
    pts = plate_screw_points()
    for n, b in out.items():
        bb = b.val().BoundingBox()
        mine = [(x, y) for (x, y) in pts if bb.xmin < x < bb.xmax and bb.ymin < y < bb.ymax]
        for (x, y) in mine:
            b = b.cut(_cyl(P.M3_TAP_DRILL, (x, y, 0), (0, 0, 1), P.PSU_LIDSCREW_TAP))
            b = b.cut(_cyl(P.M3_TAP_DRILL, (x, y, IH), (0, 0, -1), P.PSU_LIDSCREW_TAP))
        for jz in P.PSU_JOINT_Z:
            for jx in (-T / 2, IW + T / 2):
                if n.startswith("long"):
                    y0 = -T - 1 if n == "long_front" else ID - 1
                    b = b.cut(_cyl(P.M3_CLEAR, (jx, y0, jz), (0, 1, 0), T + 2))
                elif (n == "short_mains") == (jx < 0):
                    b = b.cut(_cyl(P.M3_TAP_DRILL, (jx, 0, jz), (0, 1, 0), 10))
                    b = b.cut(_cyl(P.M3_TAP_DRILL, (jx, ID, jz), (0, -1, 0), 10))
        out[n] = b
    g_m, g_o = P.PSU_GLAND_MAINS, P.PSU_GLAND_OUT
    pe = P.PSU_PE_STUD
    out["short_mains"] = (out["short_mains"]
                          .cut(_cyl(g_m["hole"], (-T - 1, P.PSU_GLAND_MAINS_Y, P.PSU_GLAND_Z), (1, 0, 0), T + 2))
                          .cut(_cyl(P.M4_CLEAR, (-T - 1, pe["y"], pe["z"]), (1, 0, 0), T + 2)))
    out["short_output"] = out["short_output"].cut(
        _cyl(g_o["hole"], (IW - 1, P.PSU_GLAND_OUT_Y, P.PSU_GLAND_OUT_Z), (1, 0, 0), T + 2))
    return out


def ear_holes():
    xe = (-T - P.PSU_EAR / 2, IW + T + P.PSU_EAR / 2)
    return [(x, y) for x in xe for y in (18.0, ID - 18.0)]


def pcb_holes():
    i = P.PSU_CLEAR + P.PSU_PCB_HOLE_INSET
    return [(i, i), (IW - i, i), (i, ID - i), (IW - i, ID - i)]


def base():
    b = _box(-T - P.PSU_EAR, -T, -P.PSU_BASE_T, IW + T + P.PSU_EAR, ID + T, 0)
    b = drill(b, plate_screw_points(), P.M3_CLEAR, -5, 1)
    b = drill(b, ear_holes(), P.M4_CLEAR, -5, 1)
    return drill(b, pcb_holes(), P.M3_CLEAR, -5, 1)


def lid():
    b = _box(-T, -T, IH, IW + T, ID + T, IH + P.PSU_LID_T)
    return drill(b, plate_screw_points(), P.M3_CLEAR, IH - 1, IH + 5)


BOARD_LOC = cq.Location(cq.Vector(P.PSU_CLEAR, P.PSU_CLEAR + P.PSU_PCB_H, P.PSU_STANDOFF_H + P.PSU_PCB_T))
_CACHE = {}


def real():
    """(board body, {ref: Shape}) of the KiCad PSU board in the box frame."""
    if "psu" not in _CACHE:
        body, parts = board_parts.load("acdc_converter", P.PSU_PCB_T)
        _CACHE["psu"] = (body.moved(BOARD_LOC), {r: s.moved(BOARD_LOC) for r, s in parts.items()})
    return _CACHE["psu"]


def pcb():
    return cq.Workplane().add(real()[0])


def pcb_parts():
    return {r: cq.Workplane().add(s) for r, s in real()[1].items()}


def plug_and_cables():
    """Mated Micro-Fit plug on J2 with its cable to the output gland, and the mains
    cores from the gland to J1's wire entry (envelopes for the fit check)."""
    z_pcb = P.PSU_STANDOFF_H + P.PSU_PCB_T
    x_face = P.PSU_CLEAR + 128.5                     # J2 mating face (KiCad x)
    yo = P.PSU_GLAND_OUT_Y
    plug = _box(x_face - 5.0, yo - 4.5, z_pcb + 0.6, x_face + 9.0, yo + 4.5, z_pcb + 8.1)
    out_cable = _cyl(5.0, (x_face + 9.0, yo, z_pcb + 4.0), (1, 0, 0), IW - (x_face + 9.0))
    ym = P.PSU_GLAND_MAINS_Y
    x_entry = P.PSU_CLEAR + 17.4                     # J1 wire-entry face (KiCad x)
    cores = _box(0.0, ym - 7.0, z_pcb + 2.0, x_entry, ym + 7.0, P.PSU_GLAND_Z + 4.0)
    return {"J2 plug": plug, "DC cable": out_cable, "mains cores": cores}


def gland(spec, x_wall, outward, yc, zc):
    """Simplified nylon cable gland: hex body + dome outside, locknut inside."""
    s = 1 if outward > 0 else -1
    hexb = (cq.Workplane("YZ").polygon(6, spec["af"] / 0.866).extrude(5 * s)
            .translate((x_wall, yc, zc)))
    dome = _cyl(spec["body_d"] * 0.85, (x_wall + 5 * s, yc, zc), (s, 0, 0), spec["dome_l"] - 5)
    thread = _cyl(spec["thread"], (x_wall, yc, zc), (-s, 0, 0), T + spec["nut_t"])
    nut = (cq.Workplane("YZ").polygon(6, spec["af"] / 0.866).extrude(spec["nut_t"])
           .translate((x_wall - s * (T + spec["nut_t"]) if s > 0 else x_wall + T, yc, zc)))
    g = hexb.union(dome).union(thread).union(nut)
    cable = _cyl(spec["thread"] * 0.55, (x_wall + s * spec["dome_l"], yc, zc), (s, 0, 0), 25)
    return g, cable


def fasteners(lid_on=True):
    out = []
    bs = button_screw(8.0)
    for (x, y) in plate_screw_points():
        if lid_on:
            out.append(bs.translate((x, y, IH + P.PSU_LID_T)))
        out.append(bs.rotate((0, 0, 0), (1, 0, 0), 180).translate((x, y, -P.PSU_BASE_T)))
    for (x, y) in pcb_holes():                        # (nylon ones: see standoffs())
        if x < IW / 2:
            out.append(standoff(x, y))
        out.append(button_screw(6.0).rotate((0, 0, 0), (1, 0, 0), 180).translate((x, y, -P.PSU_BASE_T)))
        out.append(button_screw(6.0).translate((x, y, P.PSU_STANDOFF_H + P.PSU_PCB_T)))
    ss = socket_screw(12.0)
    for jz in P.PSU_JOINT_Z:
        for jx in (-T / 2, IW + T / 2):
            out.append(ss.rotate((0, 0, 0), (1, 0, 0), 90).translate((jx, -T, jz)))
            out.append(ss.rotate((0, 0, 0), (1, 0, 0), -90).translate((jx, ID + T, jz)))
    out += pe_stud()
    return out


def standoff(x, y):
    return cq.Workplane("XY").polygon(6, 5.5 / 0.866).extrude(P.PSU_STANDOFF_H).translate((x, y, 0))


def nylon_standoffs():
    """H2/H4 (receiver side): nylon standoffs and screws."""
    return [standoff(x, y) for (x, y) in pcb_holes() if x > IW / 2]


def pe_stud():
    """M4 x 20 button head from outside through the mains-end bar; inside: serrated
    washer + nut (stud), then the ring terminals, washer, nut and lock nut."""
    pe = P.PSU_PE_STUD
    out = [button_screw(pe["l"], P.BUTTON_M4).rotate((0, 0, 0), (0, 1, 0), -90)
           .translate((-T, pe["y"], pe["z"]))]
    for x in (0.8, 5.0, 8.2):
        out.append(hex_nut(4.0, 7.0, 3.2).rotate((0, 0, 0), (0, 1, 0), 90).translate((x, pe["y"], pe["z"])))
    return out


def _compound(ws):
    return cq.Workplane().add(cq.Compound.makeCompound([v for w in ws for v in w.vals()]))


def assembly(lid_on=True, explode=0.0, detail=False):
    a = cq.Assembly(name="psu_box")
    for n, b in bars().items():
        a.add(b, name=f"bar_{n}", color=ALU)
    a.add(base(), name="base_3mm", color=ALU_DARK)
    if lid_on:
        a.add(lid(), name="lid_2mm", color=ALU_DARK, loc=cq.Location((0, 0, 50 * explode)))
    a.add(pcb(), name="psu_pcb", color=PCB_GREEN)
    shapes = list(real()[1].values())
    if not detail:                                  # STEP export: bounding-box envelopes
        shapes = [board_parts.envelope(s) for s in shapes]
    a.add(cq.Workplane().add(cq.Compound.makeCompound(shapes)), name="psu_parts", color=BLACK)
    a.add(_compound(nylon_standoffs()), name="standoffs_nylon_H2_H4", color=NYLON)
    gm, cm = gland(P.PSU_GLAND_MAINS, -T, -1, P.PSU_GLAND_MAINS_Y, P.PSU_GLAND_Z)
    go, co = gland(P.PSU_GLAND_OUT, IW + T, +1, P.PSU_GLAND_OUT_Y, P.PSU_GLAND_OUT_Z)
    a.add(gm, name="gland_M16_mains", color=BLACK)
    a.add(go, name="gland_M12_output", color=BLACK)
    a.add(cm, name="cable_mains", color=cq.Color(0.2, 0.2, 0.2))
    a.add(co, name="cable_dc_out", color=cq.Color(0.2, 0.2, 0.2))
    a.add(_compound(fasteners(lid_on)), name="fasteners", color=STEEL)
    return a


def outer_bbox():
    """(xmin, xmax, ymin, ymax, zmin, zmax) incl. ears and glands -- for layout."""
    xmin = -T - max(P.PSU_EAR, P.PSU_GLAND_MAINS["dome_l"])
    xmax = IW + T + max(P.PSU_EAR, P.PSU_GLAND_OUT["dome_l"])
    return (xmin, xmax, -T, ID + T, -P.PSU_BASE_T - 2.2, IH + P.PSU_LID_T + 1.65)


if __name__ == "__main__":
    for n, b in bars().items():
        export_step(b, f"psu_bar_{n}")
    export_step(base(), "psu_base")
    export_step(lid(), "psu_lid")
    export_dxf(base().translate((0, 0, P.PSU_BASE_T / 2)), "psu_base")
    export_dxf(lid().translate((0, 0, -IH - P.PSU_LID_T / 2)), "psu_lid")
    export_step(assembly(), "psu_box_assembly")
    print(render(assembly(lid_on=False, detail=True), "psu_box_lid_off", direction=(0.8, -1.1, 1.1),
                 title="PSU enclosure -- lid removed"))
