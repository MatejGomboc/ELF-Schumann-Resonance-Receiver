# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Fit check of the REAL boards inside their enclosures.

    .venv/bin/python mechanical/fit_check.py

The populated boards come from KiCad (board_parts.py). Checked:
  amplifier shield  every part and mated plug against the six wall bars, the
                    lid, the tray, the PTFE feed-through and all screws
                    (overlap), the edge connectors' clearance to the walls,
                    and the feed-through axis against the J201 input turret
  PSU box           every part against the bars, base, lid, glands, PE stud,
                    standoffs and screws; the J2 plug + DC cable and the mains
                    cores (gland -> J1) against every part and the box
Exit status 1 on any clash or short clearance.
"""

import sys

import cadquery as cq

import amp_assembly
import amp_frame
import amp_lid
import amp_pcb
import amp_tray
import params as P
import psu_box

MIN_GAP = 0.5        # mm, connector body / plug to wall


def _shapes(x):
    if isinstance(x, cq.Assembly):
        return [x.toCompound()]
    if isinstance(x, cq.Workplane):
        return [cq.Compound.makeCompound(x.vals())]
    if isinstance(x, list):
        return [s for w in x for s in _shapes(w)]
    return [x]


def _bb_hit(a, b, m=0.0):
    a, b = a.BoundingBox(), b.BoundingBox()
    return not (a.xmax + m < b.xmin or b.xmax + m < a.xmin or a.ymax + m < b.ymin or
                b.ymax + m < a.ymin or a.zmax + m < b.zmin or b.zmax + m < a.zmin)


def overlaps(parts, solids, tol=0.01):
    """[(part, solid, mm^3)] for every part/solid pair that intersects."""
    out = []
    for pn, ps in parts.items():
        ps = _shapes(ps)[0]
        for sn, ss in solids.items():
            for s in _shapes(ss):
                if _bb_hit(ps, s):
                    v = ps.intersect(s).Volume()
                    if v > tol:
                        out.append((pn, sn, v))
    return out


def clearances(parts, solids, names, limit=MIN_GAP):
    """{(part, solid): gap} for the named parts against every solid nearer than 3 mm."""
    out = {}
    for pn in names:
        ps = parts[pn]
        for sn, ss in solids.items():
            for s in _shapes(ss):
                if _bb_hit(ps, s, 3.0):
                    out[(pn, sn)] = min(out.get((pn, sn), 99.0), ps.distance(s))
    return out


def amp():
    print("== amplifier shield")
    parts = amp_pcb.components()
    metal = {f"wall {n}": b for n, b in amp_frame.build().items()}
    metal["lid"] = amp_lid.build()
    metal["tray"] = amp_tray.build()
    metal["feed-through"] = amp_tray.feedthrough()
    metal["tray screws"] = amp_assembly.tray_screws()
    metal["lid screws"] = amp_assembly.lid_screws()
    metal["joint screws"] = amp_assembly.joint_screws()
    problems = []
    for pn, sn, v in overlaps(parts, metal):
        problems.append(f"CLASH {pn} x {sn}: {v:.2f} mm^3")
    edge = ["J101", "J401", "J402", "AES3 plug", "Micro-Fit plug"]
    walls = {n: s for n, s in metal.items() if n.startswith("wall")}
    for (pn, sn), g in sorted(clearances(parts, walls, edge).items(), key=lambda kv: kv[1]):
        flag = "OK " if g >= MIN_GAP else "LOW"
        print(f"  {flag} {pn:15s} to {sn:18s} {g:5.2f} mm")
        if g < MIN_GAP:
            problems.append(f"clearance {pn} to {sn} {g:.2f} mm")
    # feed-through axis vs the input turret
    bb = parts["J201"].BoundingBox()
    jx, jy = (bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2
    fx, fy = P.FEEDTHROUGH_XY
    off = ((jx - fx) ** 2 + (jy - fy) ** 2) ** 0.5
    print(f"  feed-through axis to J201: {off:.2f} mm")
    if off > 0.2:
        problems.append(f"feed-through {off:.2f} mm off the J201 axis")
    top = max(s.BoundingBox().zmax for s in parts.values())
    print(f"  tallest part {top:.1f} mm, lid underside at {P.FRAME_H:.1f} mm")
    return problems


def psu():
    print("== PSU box")
    _, parts = psu_box.real()
    metal = {f"bar {n}": b for n, b in psu_box.bars().items()}
    metal["base"] = psu_box.base()
    metal["lid"] = psu_box.lid()
    g_m, _ = psu_box.gland(P.PSU_GLAND_MAINS, -psu_box.T, -1, P.PSU_GLAND_MAINS_Y, P.PSU_GLAND_Z)
    g_o, _ = psu_box.gland(P.PSU_GLAND_OUT, psu_box.IW + psu_box.T, +1, P.PSU_GLAND_OUT_Y, P.PSU_GLAND_OUT_Z)
    metal["mains gland"] = g_m
    metal["output gland"] = g_o
    metal["PE stud"] = psu_box.pe_stud()
    metal["fasteners"] = psu_box.fasteners(lid_on=True)
    metal["nylon standoffs"] = psu_box.nylon_standoffs()
    problems = [f"CLASH {pn} x {sn}: {v:.2f} mm^3" for pn, sn, v in overlaps(parts, metal)]
    body = psu_box.real()[0]
    near_pcb = {k: metal[k] for k in ("mains gland", "output gland", "PE stud", "lid")}
    problems += [f"CLASH PSU board x {sn}: {v:.2f} mm^3" for _, sn, v in overlaps({"PCB": body}, near_pcb)]
    cables = psu_box.plug_and_cables()
    for pn, sn, v in overlaps(cables, parts):
        if (pn, sn) != ("J2 plug", "J2"):           # the plug sits in its own header
            problems.append(f"CLASH {pn} x part {sn}: {v:.2f} mm^3")
    for pn, sn, v in overlaps(cables, {k: v for k, v in metal.items() if "gland" not in k}):
        problems.append(f"CLASH {pn} x {sn}: {v:.2f} mm^3")
    tops = {r: s.BoundingBox().zmax for r, s in parts.items()}
    r = max(tops, key=tops.get)
    print(f"  tallest part {r} at {tops[r]:.1f} mm, lid underside at {P.PSU_INNER_H:.1f} mm")
    print("  J2 plug + DC cable and the mains cores checked against every part")
    return problems


def main():
    problems = amp() + psu()
    print("fit check:", "OK -- no clashes" if not problems else f"{len(problems)} problem(s)")
    for p in problems:
        print("  ", p)
    return problems


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
