# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Air-gap plate capacitor assembly (PLAN.md section 3.0).

Two independent 50 pF air capacitors side by side on a POM-C base plate:

    ANT --R1 33k-- node1 --R2 33k-- node2 ---- flying lead --> LMP7721 IN+
                    |                 |
                  C_A 50 pF         C_B 50 pF      (air, 0.5 mm)
                    |                 |
                   GND               GND

Each capacitor = two 64 x 64 x 1.6 mm FR4 plates, copper facing copper,
0.5 mm apart.  Lower plate (copper up) = GND, upper plate (copper down) =
node; the node plate's copper is brought to a solder pad on its outer face
by a via at each side edge, so the resistors are air-wired pad to pad.
The gap is set by 0.5 mm PTFE washers on four M3 nylon screws at (5, 5)
from each corner and one loose 0.5 mm PTFE disc at the centre.
Each capacitor stands on four PTFE rod standoffs (Z 0..15 above the base).

Local frame: base top face at Z = 0, base centred on X/Y, chain runs from
ANT at +X to node2 / OUT at -X (so node2 ends up next to compartment 1 of
the amplifier in the outer-box layout).
"""

import cadquery as cq

import params as P
from common import (COPPER, NYLON, PCB_GREEN, POM, PTFE, RESISTOR_BLUE, STEEL,
                    cheese_screw, drill, export_step, render)

S = P.PLATE_SIZE
HALF_GAP = P.PLATECAP_SPACING / 2
CAP_CX = {"C_A": HALF_GAP + S / 2, "C_B": -(HALF_GAP + S / 2)}   # node1 cap at +X
Z_LOW_BOT = P.PLATE_STANDOFF["h"]
Z_LOW_TOP = Z_LOW_BOT + P.PLATE_T
Z_CU_LOW = Z_LOW_TOP + P.PLATE_CU_T                 # lower copper top
Z_CU_UP = Z_CU_LOW + P.PLATE_GAP                     # upper copper bottom
Z_UP_BOT = Z_CU_UP + P.PLATE_CU_T
Z_UP_TOP = Z_UP_BOT + P.PLATE_T
POST_X = S + HALF_GAP + P.PLATECAP_POST_MARGIN       # ANT post at +POST_X, OUT at -POST_X
PAD_INSET = 3.5


def _box(x0, y0, z0, x1, y1, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _cyl(d, p, direction, length):
    return cq.Workplane("XY").add(
        cq.Solid.makeCylinder(d / 2, length, cq.Vector(*p), cq.Vector(*direction)))


def _wire(points, d=0.6):
    """Polyline of round wire through 3D points."""
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


def hole_points(cx):
    i = S / 2 - P.PLATE_HOLE_INSET
    return [(cx + sx * i, sy * i) for sx in (-1, 1) for sy in (-1, 1)]


def plate(cx, z0):
    p = _box(cx - S / 2, -S / 2, z0, cx + S / 2, S / 2, z0 + P.PLATE_T)
    return drill(p, hole_points(cx), P.M3_PCB_HOLE, z0 - 1, z0 + P.PLATE_T + 1)


def copper(cx, z0):
    """Copper square with corner reliefs + isolated landing rings under the washers."""
    c = P.PLATE_CU
    t = P.PLATE_CU_T
    cu = _box(cx - c / 2, -c / 2, z0, cx + c / 2, c / 2, z0 + t)
    for (x, y) in hole_points(cx):
        cu = cu.cut(_cyl(2 * P.PLATE_CU_KEEPOUT_R, (x, y, z0 - 1), (0, 0, 1), 3))
        ring = _cyl(P.PLATE_LAND_OD, (x, y, z0), (0, 0, 1), t).cut(
            _cyl(P.M3_PCB_HOLE, (x, y, z0 - 1), (0, 0, 1), 3))
        cu = cu.union(ring)
    return cu


def base():
    W, D = P.PLATECAP_BASE_W, P.PLATECAP_BASE_D
    b = _box(-W / 2, -D / 2, -P.PLATECAP_BASE_T, W / 2, D / 2, 0)
    i = P.PLATECAP_BASE_HOLE_INSET
    b = drill(b, [(sx * (W / 2 - i), sy * (D / 2 - i)) for sx in (-1, 1) for sy in (-1, 1)],
              P.M4_CLEAR, -P.PLATECAP_BASE_T - 1, 1)
    taps = [pt for cx in CAP_CX.values() for pt in hole_points(cx)]
    taps += [(POST_X, 0), (-POST_X, 0), (P.GND_POST["x"], P.GND_POST["y"])]
    b = drill(b, taps, P.M3_TAP_DRILL, -P.PLATECAP_BASE_T - 1, 1)
    # engraved labels (0.6 mm deep) -- node names and part values
    yf, yb = -P.PLATECAP_BASE_D / 2 + 7, P.PLATECAP_BASE_D / 2 - 7
    labels = [
        ("ANT", POST_X, -12, 5.0), ("IN+", -POST_X, -12, 5.0),
        ("R1 33k", POST_X - 1, 13, 3.5),
        ("NODE1", CAP_CX["C_A"], yf, 5.0), ("NODE2", CAP_CX["C_B"], yf, 5.0),
        ("GND", P.GND_POST["x"] + 13, yf, 4.0),
        ("R2 33k", 0, yb, 4.0),
        ("C_A 50p", CAP_CX["C_A"], yb, 5.0), ("C_B 50p", CAP_CX["C_B"], yb, 5.0),
    ]
    for (txt, x, y, size) in labels:
        t = (cq.Workplane("XY").text(txt, size, -0.6, halign="center", valign="center",
                                     kind="bold").translate((x, y, 0)))
        b = b.cut(t)
    return b


def standoffs():
    sd = P.PLATE_STANDOFF
    out = []
    for cx in CAP_CX.values():
        for (x, y) in hole_points(cx):
            out.append(_cyl(sd["d"], (x, y, 0), (0, 0, 1), sd["h"])
                       .cut(_cyl(sd["bore"], (x, y, -1), (0, 0, 1), sd["h"] + 2)))
    return out


def washers():
    w = P.PTFE_WASHER
    out = []
    for cx in CAP_CX.values():
        for (x, y) in hole_points(cx):
            out.append(_cyl(w["od"], (x, y, Z_CU_LOW), (0, 0, 1), w["t"])
                       .cut(_cyl(w["id"], (x, y, Z_CU_LOW - 1), (0, 0, 1), 3)))
        out.append(_cyl(P.PTFE_CENTRE_SPACER_D, (cx, 0, Z_CU_LOW), (0, 0, 1), P.PLATE_GAP))
    return out


def nylon_screws():
    s = cheese_screw(P.NYLON_SCREW_L)
    return [s.translate((x, y, Z_UP_TOP)) for cx in CAP_CX.values() for (x, y) in hole_points(cx)]


def pads():
    """Solder pads on the outer faces: node pads on top of the upper plates at the
    +X/-X edges, GND pad under each lower plate at the front edge."""
    out = []
    for cx in CAP_CX.values():
        for sx in (-1, 1):
            x = cx + sx * (S / 2 - PAD_INSET)
            out.append(_box(x - 2, -2, Z_UP_TOP, x + 2, 2, Z_UP_TOP + P.PLATE_CU_T))
        out.append(_box(cx - 2, -S / 2 + 1.5, Z_LOW_BOT - P.PLATE_CU_T, cx + 2,
                        -S / 2 + 5.5, Z_LOW_BOT))
    return out


def posts():
    tp = P.TERMINAL_POST
    out = []
    for x in (POST_X, -POST_X):
        out.append(("post_ptfe", _cyl(tp["d"], (x, 0, 0), (0, 0, 1), tp["h"]), PTFE))
        out.append(("turret", _cyl(tp["pin_d"] * 1.8, (x, 0, tp["h"]), (0, 0, 1), 1.0)
                    .union(_cyl(tp["pin_d"], (x, 0, tp["h"]), (0, 0, 1), tp["pin_h"])), STEEL))
    g = P.GND_POST
    out.append(("gnd_post", _cyl(g["d"], (g["x"], g["y"], 0), (0, 0, 1), g["h"]), STEEL))
    return out


def resistor(x_a, x_b, z, y=0.0):
    """Axial resistor body centred between x_a and x_b at height z."""
    r = P.RESISTOR
    xm = (x_a + x_b) / 2
    return _cyl(r["d"], (xm - r["l"] / 2, y, z), (1, 0, 0), r["l"])


def wiring():
    """Resistor leads, node2 lead, GND wires -- dict name -> Workplane."""
    zr1, zr2 = P.RES_Z["r1"], P.RES_Z["r2"]
    xa_out = CAP_CX["C_A"] + S / 2 - PAD_INSET        # node1 pad, +X edge
    xa_in = CAP_CX["C_A"] - S / 2 + PAD_INSET         # node1 pad, -X edge
    xb_in = CAP_CX["C_B"] + S / 2 - PAD_INSET         # node2 pad, +X edge
    xb_out = CAP_CX["C_B"] - S / 2 + PAD_INSET        # node2 pad, -X edge
    tp = P.TERMINAL_POST
    zt = tp["h"] + 3.0
    w = {}
    w["R1_leads"] = _wire([(xa_out, 0, Z_UP_TOP), (xa_out, 0, zr1), (POST_X, 0, zr1),
                           (POST_X, 0, zt)])
    w["R2_leads"] = _wire([(xa_in, 0, Z_UP_TOP), (xa_in, 0, zr2), (xb_in, 0, zr2),
                           (xb_in, 0, Z_UP_TOP)])
    w["node2_lead"] = _wire([(xb_out, 0, Z_UP_TOP), (xb_out, 0, zr1), (-POST_X, 0, zr1),
                             (-POST_X, 0, zt)], d=0.8)
    g = P.GND_POST
    gw = None
    for cx in CAP_CX.values():
        seg = _wire([(cx, -S / 2 + 3.5, Z_LOW_BOT), (cx, -S / 2 + 3.5, 6.0),
                     (g["x"] + (2 if cx > 0 else -2), g["y"], 6.0),
                     (g["x"] + (2 if cx > 0 else -2), g["y"], g["h"])], d=0.8)
        gw = seg if gw is None else gw.union(seg)
    w["gnd_wires"] = gw
    return w


def resistors():
    zr1, zr2 = P.RES_Z["r1"], P.RES_Z["r2"]
    xa_out = CAP_CX["C_A"] + S / 2 - PAD_INSET
    return {"R1_33k": resistor(xa_out, POST_X, zr1),
            "R2_33k": resistor(CAP_CX["C_A"] - S / 2 + PAD_INSET,
                               CAP_CX["C_B"] + S / 2 - PAD_INSET, zr2)}


def _compound(ws):
    return cq.Workplane().add(cq.Compound.makeCompound([v for w in ws for v in w.vals()]))


def assembly():
    a = cq.Assembly(name="platecap")
    a.add(base(), name="base_POM", color=POM)
    a.add(_compound(standoffs()), name="standoffs_PTFE", color=PTFE)
    for name, cx in CAP_CX.items():
        a.add(plate(cx, Z_LOW_BOT), name=f"{name}_plate_GND", color=PCB_GREEN)
        a.add(copper(cx, Z_LOW_TOP), name=f"{name}_copper_GND", color=COPPER)
        a.add(copper(cx, Z_CU_UP), name=f"{name}_copper_node", color=COPPER)
        a.add(plate(cx, Z_UP_BOT), name=f"{name}_plate_node", color=PCB_GREEN)
    a.add(_compound(washers()), name="washers_PTFE", color=PTFE)
    a.add(_compound(nylon_screws()), name="screws_nylon_M3x25", color=NYLON)
    a.add(_compound(pads()), name="pads", color=COPPER)
    for i, (n, wp, col) in enumerate(posts()):
        a.add(wp, name=f"{n}_{i}", color=col)
    for n, wp in resistors().items():
        a.add(wp, name=n, color=RESISTOR_BLUE)
    for n, wp in wiring().items():
        a.add(wp, name=n, color=STEEL)
    return a


def footprint():
    """(W, D, H) of the assembly for the outer-box layout."""
    return (P.PLATECAP_BASE_W, P.PLATECAP_BASE_D,
            P.PLATECAP_BASE_T + P.TERMINAL_POST["h"] + P.TERMINAL_POST["pin_h"])


if __name__ == "__main__":
    export_step(base(), "platecap_base_POM")
    export_step(plate(0, 0), "platecap_plate_FR4_64x64")
    export_step(assembly(), "platecap_assembly")
    print(render(assembly(), "platecap_assembly", direction=(0.55, -1.0, 0.85),
                 title="Air-gap plate capacitors -- ANT > R1 > node1 > R2 > node2 > IN+"))
