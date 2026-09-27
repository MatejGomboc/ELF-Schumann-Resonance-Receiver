# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Outdoor IP65/IP66 plastic enclosure (generic) and the mounting plate.

Global frame of the outdoor unit (used by full_assembly.py):
    origin = centre of the box's inner floor
    X right, Y UP (box wall-mounted, antenna gland on top), Z out of the
    wall towards the door.

The box is a generic polycarbonate/GRP enclosure with the inner size in
params.BOX_INNER_*, 4 mm walls and four 10 mm floor bosses carrying the
mounting plate.  Commercial candidates are listed in README.md.

Mounting plate: 8 mm PE-HD (or 3 mm aluminium), countersunk M4 studs
pressed in from the back; each unit drops onto its studs and is held by
M4 nyloc/knurled nuts, so every unit can be lifted out on its own.
"""

import cadquery as cq

import params as P
import amp_lid
import psu_box
from common import (BLACK, PE_WHITE, PLASTIC_GREY, STEEL, drill, export_dxf, export_step,
                    render)

IW, IH, ID = P.BOX_INNER_W, P.BOX_INNER_H, P.BOX_INNER_D
WALL = P.BOX_WALL
Z_PLATE_TOP = P.BOX_BOSS_H + P.MOUNT_PLATE_T


def _box(x0, y0, z0, x1, y1, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _cyl(d, p, direction, length):
    return cq.Workplane("XY").add(
        cq.Solid.makeCylinder(d / 2, length, cq.Vector(*p), cq.Vector(*direction)))


# ---------------------------------------------------------------------------
# Placement of the three units (plate coordinates = global XY)
# ---------------------------------------------------------------------------
def amp_location():
    cx, cy = P.LAYOUT["amp"]
    z = Z_PLATE_TOP + P.MOUNT_SPACER_H + P.FRAME_H + P.LID_T
    return cq.Location(cq.Vector(cx - P.PCB_W / 2, cy - P.PCB_H / 2, z), cq.Vector(1, 0, 0), 180)


def amp_to_global(x_k, y_k, z_local):
    """KiCad xy + local Z of the amplifier -> global coordinates."""
    cx, cy = P.LAYOUT["amp"]
    zt = Z_PLATE_TOP + P.MOUNT_SPACER_H + P.FRAME_H + P.LID_T
    return (cx - P.PCB_W / 2 + x_k, cy - P.PCB_H / 2 + y_k, zt - z_local)


def platecap_location():
    cx, cy = P.LAYOUT["platecap"]
    return cq.Location(cq.Vector(cx, cy, Z_PLATE_TOP + P.PLATECAP_BASE_T))


def psu_location():
    cx, cy = P.LAYOUT["psu"]
    return cq.Location(cq.Vector(cx - P.PSU_INNER_W / 2, cy - P.PSU_INNER_D / 2,
                                 Z_PLATE_TOP + P.MOUNT_SPACER_H + P.PSU_BASE_T))


def stud_points():
    """dict unit -> list of (x, y) of the M4 studs in the mounting plate."""
    pc = P.LAYOUT["platecap"]
    i = P.PLATECAP_BASE_HOLE_INSET
    hw, hd = P.PLATECAP_BASE_W / 2 - i, P.PLATECAP_BASE_D / 2 - i
    out = {"platecap": [(pc[0] + sx * hw, pc[1] + sy * hd) for sx in (-1, 1) for sy in (-1, 1)]}
    ax, ay = P.LAYOUT["amp"]
    out["amp"] = [(ax - P.PCB_W / 2 + x, ay - P.PCB_H / 2 - y) for (x, y) in amp_lid.ear_holes()]
    px, py = P.LAYOUT["psu"]
    out["psu"] = [(px - P.PSU_INNER_W / 2 + x, py - P.PSU_INNER_D / 2 + y)
                  for (x, y) in psu_box.ear_holes()]
    return out


def plate_fixing_points():
    i = P.MOUNT_PLATE_HOLE_INSET
    return [(sx * (P.MOUNT_PLATE_W / 2 - i), sy * (P.MOUNT_PLATE_H / 2 - i))
            for sx in (-1, 1) for sy in (-1, 1)]


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------
def mounting_plate():
    W, H = P.MOUNT_PLATE_W, P.MOUNT_PLATE_H
    p = _box(-W / 2, -H / 2, P.BOX_BOSS_H, W / 2, H / 2, Z_PLATE_TOP)
    studs = [pt for v in stud_points().values() for pt in v]
    p = drill(p, studs, P.M4_CLEAR, 0, 30)
    p = drill(p, plate_fixing_points(), P.M4_CLEAR, 0, 30)
    # cable pass slots? none needed -- all cables run on the component side
    return p


def box_body():
    ow, oh = IW + 2 * WALL, IH + 2 * WALL
    body = _box(-ow / 2, -oh / 2, -WALL, ow / 2, oh / 2, ID)
    body = body.edges("|Z").fillet(8.0)
    cav = _box(-IW / 2, -IH / 2, 0, IW / 2, IH / 2, ID + 1).edges("|Z").fillet(4.0)
    body = body.cut(cav)
    for (x, y) in plate_fixing_points():
        body = body.union(_cyl(P.BOX_BOSS_D, (x, y, 0), (0, 0, 1), P.BOX_BOSS_H)
                          .cut(_cyl(3.5, (x, y, 1), (0, 0, 1), P.BOX_BOSS_H)))
    for g in P.BOX_GLANDS:
        y0 = IH / 2 - 1 if g["wall"] == "top" else -IH / 2 - WALL - 1
        body = body.cut(_cyl(g["thread"] + 0.3, (g["x"], y0, g["z"]), (0, 1, 0), WALL + 2))
    return body


def box_lid():
    ow, oh = IW + 2 * WALL, IH + 2 * WALL
    return _box(-ow / 2, -oh / 2, ID, ow / 2, oh / 2, ID + P.BOX_LID_T).edges("|Z").fillet(8.0)


def box_glands():
    out = []
    for g in P.BOX_GLANDS:
        s = 1 if g["wall"] == "top" else -1
        y_out = s * (IH / 2 + WALL)
        y_in = s * IH / 2
        hexb = (cq.Workplane("XZ").polygon(6, g["af"] / 0.866).extrude(-5 * s)
                .translate((g["x"], y_out, g["z"])))
        dome = _cyl(g["af"] * 0.8, (g["x"], y_out + 5 * s, g["z"]), (0, s, 0), g["dome"] - 5)
        thread = _cyl(g["thread"], (g["x"], y_out, g["z"]), (0, -s, 0), WALL + 5)
        nut = (cq.Workplane("XZ").polygon(6, g["af"] / 0.866).extrude(-4 * s)
               .translate((g["x"], y_in - 4 * s, g["z"])))
        out.append((g["name"], hexb.union(dome).union(thread).union(nut)))
    return out


def studs():
    """M4 countersunk studs from the plate back + spacers + nuts (simplified)."""
    parts = []
    for unit, pts in stud_points().items():
        spacer = 0.0 if unit == "platecap" else P.MOUNT_SPACER_H
        clamp = {"platecap": P.PLATECAP_BASE_T, "amp": P.LID_T, "psu": P.PSU_BASE_T}[unit]
        for (x, y) in pts:
            L = P.MOUNT_PLATE_T + spacer + clamp + 5.0
            parts.append(_cyl(4.0, (x, y, P.BOX_BOSS_H), (0, 0, 1), L))
            if spacer:
                parts.append(_cyl(8.0, (x, y, Z_PLATE_TOP), (0, 0, 1), spacer)
                             .cut(_cyl(4.4, (x, y, Z_PLATE_TOP - 1), (0, 0, 1), spacer + 2)))
            zn = Z_PLATE_TOP + spacer + clamp
            parts.append(cq.Workplane("XY").polygon(6, 7.0 / 0.866).extrude(4.0)
                         .translate((x, y, zn)))
    return parts


def _compound(ws):
    return cq.Workplane().add(cq.Compound.makeCompound([v for w in ws for v in w.vals()]))


if __name__ == "__main__":
    export_step(box_body(), "outer_box_body_generic")
    export_step(box_lid(), "outer_box_lid_generic")
    mp = mounting_plate()
    export_step(mp, "mounting_plate")
    export_dxf(mp.translate((0, 0, -P.BOX_BOSS_H - P.MOUNT_PLATE_T / 2)), "mounting_plate")
    a = cq.Assembly(name="outer_box")
    a.add(box_body(), name="body", color=PLASTIC_GREY)
    a.add(mp, name="mounting_plate", color=PE_WHITE)
    a.add(_compound(studs()), name="studs", color=STEEL)
    for n, g in box_glands():
        a.add(g, name=f"gland_{n}", color=BLACK)
    print(render(a, "outer_box_empty", direction=(0.5, -0.6, 1.0), up=(0, 1, 0)))
