# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Full outdoor-unit assembly: generic IP66 box, mounting plate, amplifier
shield (lid-down), PSU box, air-gap plate capacitors, cable glands and
the main cable runs.  Exports STEP (lid on) and preview renders (lid off).
"""

import cadquery as cq

import params as P
import amp_assembly
import outer_box as OB
import platecap
import psu_box
from common import (BLACK, PE_WHITE, PLASTIC_GREY, STEEL, export_step, render)


def _cable(points, d):
    ws = None
    for a, b in zip(points[:-1], points[1:]):
        va, vb = cq.Vector(*a), cq.Vector(*b)
        L = (vb - va).Length
        if L < 1e-6:
            continue
        seg = cq.Workplane("XY").add(cq.Solid.makeCylinder(d / 2, L, va, (vb - va).normalized()))
        seg = seg.union(cq.Workplane("XY").add(cq.Solid.makeSphere(d / 2, vb)))
        ws = seg if ws is None else ws.union(seg)
    return ws


def cables():
    """Indicative cable runs (fit check only)."""
    out = {}
    pcx, pcy = P.LAYOUT["platecap"]
    zb = OB.Z_PLATE_TOP + P.PLATECAP_BASE_T
    post_x = platecap.POST_X
    zt = zb + P.TERMINAL_POST["h"] + 3.0
    g_ant = next(g for g in P.BOX_GLANDS if g["name"] == "Antenna")
    # antenna: gland -> ANT turret (single insulated wire, PTFE)
    out["wire_antenna"] = (_cable([(g_ant["x"], P.BOX_INNER_H / 2 - 4, g_ant["z"]),
                                   (g_ant["x"], pcy + 20, g_ant["z"]),
                                   (pcx + post_x, pcy, zt + 8), (pcx + post_x, pcy, zt)], 1.6),
                           cq.Color(0.9, 0.9, 0.85))
    # node2 -> PTFE feed-through -> J1 (bare/PTFE wire, kept >= 10 mm from metal)
    fx, fy = P.FEEDTHROUGH_XY
    ft = OB.amp_to_global(fx, fy, -P.PCB_T - P.TRAY_T - P.FEEDTHROUGH_FLANGE_T)
    z_run = ft[2] + 12.0
    out["wire_node2_to_IN+"] = (_cable([(pcx - post_x, pcy, zt), (pcx - post_x, pcy, z_run),
                                        (ft[0], ft[1], z_run), (ft[0], ft[1], ft[2])], 0.8),
                                cq.Color(0.9, 0.9, 0.85))
    # DC: amp Micro-Fit (y = 0 edge, x = 185) -> PSU M12 gland
    pw = next(c for c in P.CUTOUTS if c["name"].startswith("J_PWR"))
    j = OB.amp_to_global(pw["pos"], -9.0, 4.35)       # rear of the mated plug, outside the y = 0 edge
    px, py = P.LAYOUT["psu"]
    g_out = (px + P.PSU_INNER_W / 2 + P.PSU_BAR_T + P.PSU_GLAND_OUT["dome_l"],
             py - P.PSU_INNER_D / 2 + P.PSU_GLAND_OUT_Y,
             OB.Z_PLATE_TOP + P.MOUNT_SPACER_H + P.PSU_BASE_T + P.PSU_GLAND_OUT_Z)
    xr = g_out[0] + 5.0      # runs between the PSU gland and the AES3 cable
    out["cable_dc"] = (_cable([j, (j[0], j[1] - 12, j[2]), (xr, j[1] - 12, j[2]),
                               (xr, g_out[1], g_out[2]), g_out], 5.0), BLACK)
    # mains: bottom gland -> PSU M16 gland
    g_m = next(g for g in P.BOX_GLANDS if g["name"] == "Mains")
    g_in = (px - P.PSU_INNER_W / 2 - P.PSU_BAR_T - P.PSU_GLAND_MAINS["dome_l"],
            py - P.PSU_INNER_D / 2 + P.PSU_GLAND_MAINS_Y,
            OB.Z_PLATE_TOP + P.MOUNT_SPACER_H + P.PSU_BASE_T + P.PSU_GLAND_Z)
    out["cable_mains"] = (_cable([(g_m["x"], -P.BOX_INNER_H / 2 + 4, g_m["z"]),
                                  (g_m["x"], g_in[1], g_m["z"]),
                                  (g_in[0] - 6, g_in[1], g_in[2]), g_in], 9.0),
                          cq.Color(0.15, 0.15, 0.15))
    # AES3: the STP cable from the amp's RJ45 (right edge) -> bottom gland
    aes = next(c for c in P.CUTOUTS if c["name"].startswith("J_AES3"))
    a0 = OB.amp_to_global(215.8 + 3.0, aes["pos"], 7.0)    # out of the rear of the RJ45 plug's boot
    g_a = next(g for g in P.BOX_GLANDS if g["name"] == "AES3")
    out["cable_aes3"] = (_cable([a0, (g_a["x"], a0[1], a0[2]), (g_a["x"], a0[1] - 30, g_a["z"]),
                                 (g_a["x"], -P.BOX_INNER_H / 2 + 4, g_a["z"])], 7.0),
                         cq.Color(0.55, 0.1, 0.45))
    return out


def clash_check():
    """Pairwise solid intersection of the major items; prints overlaps > 1 mm^3."""
    def solid_of(assy_or_wp, loc=None):
        c = assy_or_wp.toCompound() if isinstance(assy_or_wp, cq.Assembly) else \
            cq.Compound.makeCompound(assy_or_wp.vals())
        return c.moved(loc) if loc is not None else c

    items = {
        "box_body": solid_of(OB.box_body()),
        "mounting_plate": solid_of(OB.mounting_plate()),
        "amp_shield": solid_of(amp_assembly.build(), OB.amp_location()),
        "psu": solid_of(psu_box.assembly(), OB.psu_location()),
        "platecap": solid_of(platecap.assembly(), OB.platecap_location()),
    }
    for n, (wp, _) in cables().items():
        items[n] = solid_of(wp)
    # cables legitimately end inside glands / on terminals: only check them
    # against the unit bodies they must NOT cross
    allowed = {("cable_dc", "psu"), ("cable_dc", "amp_shield"), ("cable_mains", "psu"),
               ("cable_mains", "box_body"), ("cable_aes3", "box_body"),
               ("cable_aes3", "amp_shield"), ("wire_antenna", "box_body"),
               ("wire_antenna", "platecap"), ("wire_node2_to_IN+", "platecap"),
               ("wire_node2_to_IN+", "amp_shield")}
    names = list(items)
    problems = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if (a, b) in allowed or (b, a) in allowed:
                continue
            bba, bbb = items[a].BoundingBox(), items[b].BoundingBox()
            if (bba.xmax < bbb.xmin or bbb.xmax < bba.xmin or bba.ymax < bbb.ymin or
                    bbb.ymax < bba.ymin or bba.zmax < bbb.zmin or bbb.zmax < bba.zmin):
                continue
            v = items[a].intersect(items[b]).Volume()
            if v > 1.0:
                problems.append((a, b, v))
    print("clash check:", "OK -- no overlaps" if not problems else "")
    for a, b, v in problems:
        print(f"  CLASH {a} x {b}: {v:.1f} mm^3")
    return problems


def build(lid=True, box=True, detail=False):
    a = cq.Assembly(name="elara_outdoor_unit")
    if box:
        a.add(OB.box_body(), name="box_body", color=PLASTIC_GREY)
        if lid:
            a.add(OB.box_lid(), name="box_lid", color=PLASTIC_GREY)
        for n, g in OB.box_glands():
            a.add(g, name=f"gland_{n}", color=BLACK)
    a.add(OB.mounting_plate(), name="mounting_plate", color=PE_WHITE)
    a.add(OB._compound(OB.studs()), name="studs_spacers_nuts", color=STEEL)
    a.add(amp_assembly.build(detail=detail), name="amp_shield", loc=OB.amp_location())
    a.add(psu_box.assembly(detail=detail), name="psu", loc=OB.psu_location())
    a.add(platecap.assembly(), name="platecap", loc=OB.platecap_location())
    for n, (wp, col) in cables().items():
        a.add(wp, name=n, color=col)
    return a


if __name__ == "__main__":
    import sys
    if "--clash" in sys.argv:
        clash_check()
    export_step(build(), "elara_outdoor_unit_full")
    open_box = build(lid=False, detail=True)
    print(render(open_box, "outer_box_layout_front", direction=(0.0, 0.0, 1.0), up=(0, 1, 0),
                 width=1100, height=1400, title="Outdoor unit -- door removed, front view"))
    print(render(open_box, "outer_box_layout_iso", direction=(0.3, -0.45, 1.0), up=(0, 1, 0),
                 width=1300, height=1500, title="Outdoor unit -- door removed"))
