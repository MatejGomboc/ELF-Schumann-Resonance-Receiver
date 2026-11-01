# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
JLCCNC order package for the amplifier shield (bom/CNC_ORDER.md).

JLCCNC machines from a STEP file per part, and needs a 2D drawing for anything a STEP
cannot say: threads, depths, tolerances, finish. This script writes both, in each
part's own corner-origin frame, from the same functions and parameters that build
the shield (amp_frame / amp_tray / amp_lid, params.py):

    mechanical/jlccnc/ELARA-SH-xx_<name>.step   one per distinct part
    mechanical/jlccnc/ELARA-SH-xx_<name>.pdf    its drawing: views + feature table
    mechanical/jlccnc/ELARA-SH-06_lid.dxf       the lid's flat pattern (sheet metal)

The six frame bars are five shapes: the left end bar and both internal walls are the
same part (x3). Before writing, every feature in the tables is probed against its STEP
solid (a point inside each hole must be outside the material, a point beside it inside),
so a drawing cannot drift from its model.

    .venv/bin/python mechanical/jlccnc.py
"""

import math
import os
import sys

os.environ.setdefault("SOURCE_DATE_EPOCH", "0")   # fixed PDF dates: no churn on re-runs
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
matplotlib.rc_file(os.path.join(HERE, "..", "matplotlibrc"))
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

import cadquery as cq  # noqa: E402

import amp_frame  # noqa: E402
import amp_lid  # noqa: E402
import amp_tray  # noqa: E402
import params as P  # noqa: E402

OUT = os.path.join(HERE, "jlccnc")
INK, MUTED, RED = "#1a1a1a", "#8a8a8a", "#b02020"

# thread callouts (thread depth = full thread; drill depth = tap-drill hole as modelled)
TAP_BOTTOM = dict(thread="M3x0.5 - 6H", thread_depth=10.0, drill=P.M3_TAP_DRILL, drill_depth=P.FRAME_TAP_DEPTH_BOTTOM)
TAP_TOP = dict(thread="M3x0.5 - 6H", thread_depth=8.0, drill=P.M3_TAP_DRILL, drill_depth=P.FRAME_TAP_DEPTH_TOP)
TAP_JOINT = dict(thread="M3x0.5 - 6H", thread_depth=10.0, drill=P.M3_TAP_DRILL, drill_depth=P.JOINT_TAP_DEPTH)

GENERAL_NOTES = [
    "Finish: bead blast (fine glass bead) or as machined. DO NOT ANODISE: the contact faces must",
    "conduct (they clamp the PCB's ground strips). Conductive chromate (chemical film) is welcome.",
    "General tolerances ISO 2768-mK. Break sharp edges 0.2-0.5 mm, except on the contact faces.",
    "All units mm. Origin = the marked corner (u, v, w as drawn). Holes not listed: none.",
]


# ---------------------------------------------------------------------------
# Parts in their local frames
# ---------------------------------------------------------------------------
def bar_frame(name):
    """(to_local(x_kicad, y_kicad, z) -> (u, v, w), CQ transform) for a wall bar:
    u along the bar, v across its 7 mm, w up from the PCB face (0) to the lid (52)."""
    x0, y0, x1, y1 = P.wall_rects()[name]
    if name.startswith("long"):
        def to_local(x, y, z):
            return (x - x0, y1 - y, z)

        def place(wp):
            return wp.translate((-x0, y1, 0))
        length = x1 - x0
    else:
        def to_local(x, y, z):
            return (y1 - y, x1 - x, z)

        def place(wp):
            return (wp.translate((-x0, y1, 0)).rotate((0, 0, 0), (0, 0, 1), -90)
                    .translate((0, x1 - x0, 0)))
        length = y1 - y0
    return to_local, place, length


def bar_features(name):
    """Every machined feature of a bar, local coordinates. Mirrors amp_frame.make_bar."""
    x0, y0, x1, y1 = P.wall_rects()[name]
    to_local, _, length = bar_frame(name)
    f = []
    for hx, hy in P.AMP_HOLES:
        if x0 < hx < x1 and y0 < hy < y1:
            u, v, _ = to_local(hx, hy, 0)
            f.append(dict(kind="tap", face="bottom (w = 0)", u=u, v=v, w=0.0, axis=(0, 0, 1), **TAP_BOTTOM))
            f.append(dict(kind="tap", face=f"top (w = {P.FRAME_H:g})", u=u, v=v, w=P.FRAME_H, axis=(0, 0, -1), **TAP_TOP))
    if name.startswith("long"):
        for jx in amp_frame._joint_xs():
            for jz in P.JOINT_Z:
                u, _, _ = to_local(jx, y0, 0)
                f.append(dict(kind="through", face="v = 0 to v = 7 (through)", u=u, v=None, w=jz,
                              axis=(0, 1, 0), d=P.M3_CLEAR, note="clearance for the M3x16 joint screw"))
    else:
        for jz in P.JOINT_Z:
            f.append(dict(kind="tap", face="end u = 0", u=0.0, v=P.WALL_T / 2, w=jz, axis=(1, 0, 0), **TAP_JOINT))
            f.append(dict(kind="tap", face=f"end u = {length:g}", u=length, v=P.WALL_T / 2, w=jz, axis=(-1, 0, 0), **TAP_JOINT))
    edge_bar = {"top": "long_top", "bottom": "long_bottom", "left": "end_left", "right": "end_right"}
    for c in P.CUTOUTS:
        if edge_bar[c["edge"]] != name:
            continue
        lo, hi = c["pos"] - c["w"] / 2, c["pos"] + c["w"] / 2
        if c["edge"] in ("top", "bottom"):
            ua, ub = to_local(lo, y0, 0)[0], to_local(hi, y0, 0)[0]
        else:
            ua, ub = to_local(x0, lo, 0)[0], to_local(x0, hi, 0)[0]
        f.append(dict(kind="notch", face="bottom, through v", u0=min(ua, ub), u1=max(ua, ub), h=c["h"],
                      note=c["name"].split()[0] + " connector notch"))
    return f


def bar_part(name):
    _, place, _ = bar_frame(name)
    return place(amp_frame.make_bar(name))


def tray_part():
    """Tray: x, y as KiCad (CQ y flipped back), z = 0 at the outside floor face."""
    t = amp_tray.build()
    z0 = -P.PCB_T - P.TRAY_T
    return t.mirror("XZ").translate((0, 0, -z0))


def tray_features():
    f = []
    for name, c in P.COMPARTMENTS.items():
        f.append(dict(kind="pocket", x0=c["x0"], y0=c["y0"], x1=c["x1"], y1=c["y1"], depth=P.TRAY_DEPTH,
                      r=P.TRAY_POCKET_R, note=f"pocket {name.split()[0]}"))
    for x, y in P.AMP_HOLES:
        f.append(dict(kind="through", x=x, y=y, d=P.M3_CLEAR, note="M3 clearance"))
    for x, y in (P.FEEDTHROUGH_XY, P.FEEDTHROUGH2_XY):
        f.append(dict(kind="bore", x=x, y=y, d=P.FEEDTHROUGH_HOLE_D,
                      note="PTFE bush, +0.1/0"))
    for x, y, d, depth in P.TRAY_RELIEFS:
        f.append(dict(kind="blind", x=x, y=y, d=d, depth=depth, note="relief, from top"))
    return f


def lid_part():
    return amp_lid.build(z0=0).translate((P.LID_EAR, 0, 0)).mirror("XZ")


def lid_features():
    f = [dict(kind="through", x=x + P.LID_EAR, y=y, d=P.M3_CLEAR, note="M3 clearance") for x, y in P.AMP_HOLES]
    for x, y in amp_lid.ear_holes():
        f.append(dict(kind="through", x=x + P.LID_EAR, y=-y, d=P.M4_CLEAR, note="M4 clear., ear"))
    return f


# ---------------------------------------------------------------------------
# Self-check: probe every listed feature in the solid
# ---------------------------------------------------------------------------
def _inside(solid, p):
    return solid.isInside(cq.Vector(*p), 1e-3)


def probe_bar(solid, feats, length):
    bad = []
    for f in feats:
        if f["kind"] == "tap":
            a = f["axis"]

            def at(d):
                return (f["u"] + a[0] * d, f["v"] + a[1] * d, f["w"] + a[2] * d)
            p, p_deep = at(1.0), at(f["drill_depth"] + 0.5)
            side = (p[0] + 2.2, p[1], p[2]) if a[0] == 0 else (p[0], p[1], p[2] + 2.2)
            if _inside(solid, p) or not _inside(solid, p_deep) or not _inside(solid, side):
                bad.append(f)
        elif f["kind"] == "through":
            p = (f["u"], P.WALL_T / 2, f["w"])
            if _inside(solid, p) or not _inside(solid, (f["u"] + 2.5, P.WALL_T / 2, f["w"])):
                bad.append(f)
        elif f["kind"] == "notch":
            p = ((f["u0"] + f["u1"]) / 2, P.WALL_T / 2, f["h"] / 2)
            q = ((f["u0"] + f["u1"]) / 2, P.WALL_T / 2, f["h"] + 1.0)
            if _inside(solid, p) or not _inside(solid, q):
                bad.append(f)
    return bad


def probe_flat(solid, feats, t):
    bad = []
    for f in feats:
        if f["kind"] in ("through", "bore"):
            if _inside(solid, (f["x"], f["y"], 1.0)) or not _inside(solid, (f["x"] + f["d"] / 2 + 0.6, f["y"], 1.0)):
                bad.append(f)
        elif f["kind"] == "blind":
            if _inside(solid, (f["x"], f["y"], t - 0.5)) or not _inside(solid, (f["x"], f["y"], t - f["depth"] - 0.5)):
                bad.append(f)
        elif f["kind"] == "pocket":
            cx, cy = f["x0"] + 6.0, f["y0"] + 6.0          # off-centre: clear of the feed-through bores
            if _inside(solid, (cx, cy, t - 1.0)) or not _inside(solid, (cx, cy, t - f["depth"] - 0.5)):
                bad.append(f)
    return bad


# ---------------------------------------------------------------------------
# Drawings
# ---------------------------------------------------------------------------
def _sheet(title, part_no, qty, material, extra_notes):
    fig = plt.figure(figsize=(16.54, 11.69))          # A3 landscape
    fig.patch.set_facecolor("white")
    fig.add_artist(Rectangle((0.015, 0.015), 0.97, 0.97, transform=fig.transFigure, fill=False, lw=1.2, color=INK))
    fig.text(0.03, 0.955, f"{part_no}  {title}", fontsize=17, weight="bold", color=INK)
    fig.text(0.03, 0.93, f"Quantity per shield: {qty}    Material: {material}    "
                         f"ELARA antenna-amplifier shield, rev 0.2 (generated by mechanical/jlccnc.py)",
             fontsize=10, color=INK)
    notes = [f"Material: {material}."] + GENERAL_NOTES + extra_notes
    fig.text(0.03, 0.035 + 0.016 * len(notes), "NOTES", fontsize=10, weight="bold", color=INK)
    for i, n in enumerate(notes):
        fig.text(0.03, 0.035 + 0.016 * (len(notes) - 1 - i), n, fontsize=9, color=INK)
    return fig


def _table(fig, rect, header, rows, fs=8.5):
    ax = fig.add_axes(rect)
    ax.axis("off")
    tb = ax.table(cellText=rows, colLabels=header, cellLoc="left", colLoc="left", bbox=[0, 0, 1, 1])
    tb.auto_set_font_size(False)
    tb.set_fontsize(fs)
    for (r, _), cell in tb.get_celld().items():
        cell.set_edgecolor(MUTED)
        if r == 0:
            cell.set_text_props(weight="bold")
    return ax


def _view(fig, rect, xlim, ylim, xlabel, ylabel, title):
    ax = fig.add_axes(rect)
    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_title(title, fontsize=10, loc="left")
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.25, lw=0.5)
    return ax


def draw_bar(name, part_no, title, qty, path):
    feats = bar_features(name)
    _, _, L = bar_frame(name)
    H, T = P.FRAME_H, P.WALL_T
    taps = [f for f in feats if f["kind"] == "tap"]
    extra = ["Contact faces w = 0 and w = 52: flatness 0.05; height 52 +/-0.05 (all bars alike, so the lid",
             "and the PCB seat on every bar). Thread depths are full-thread depths; drill depths as listed.",
             "Taps: M3 x 0.5, class 6H, with a 90 deg x 0.3 countersink at the entry."]
    fig = _sheet(title, part_no, qty, "aluminium 6061-T6 bar (EN AW-6082-T6 is fine too)", extra)
    m = 0.06 * L
    # front view (u-w), looking at face v = 0
    ax = _view(fig, [0.04, 0.63, 0.58, 0.27], (-m, L + m), (-6, H + 6), "u (mm)", "w (mm)",
               "FRONT  (looking at face v = 0; PCB face w = 0 at the bottom)")
    ax.add_patch(Rectangle((0, 0), L, H, fill=False, lw=1.4, color=INK))
    for f in feats:
        if f["kind"] == "notch":
            ax.add_patch(Rectangle((f["u0"], 0), f["u1"] - f["u0"], f["h"], fc="white", ec=RED, lw=1.2, hatch="//"))
            ax.annotate(f"notch {f['u0']:.1f}..{f['u1']:.1f}, h {f['h']:g}", (f["u1"], f["h"]), (f["u1"] + 2, f["h"] + 6),
                        fontsize=7, color=RED, arrowprops=dict(arrowstyle="-", color=RED, lw=0.6))
        elif f["kind"] == "through":
            ax.add_patch(Circle((f["u"], f["w"]), f["d"] / 2, fill=False, color=INK, lw=1.0))
        elif f["kind"] == "tap" and f["axis"][2] != 0:
            d0 = f["w"]
            d1 = f["w"] + f["axis"][2] * f["drill_depth"]
            ax.plot([f["u"] - 1.25, f["u"] - 1.25], [d0, d1], color=MUTED, lw=0.6, ls="--")
            ax.plot([f["u"] + 1.25, f["u"] + 1.25], [d0, d1], color=MUTED, lw=0.6, ls="--")
        elif f["kind"] == "tap":
            u0 = f["u"]
            u1 = f["u"] + f["axis"][0] * f["drill_depth"]
            for dw in (-1.25, 1.25):
                ax.plot([u0, u1], [f["w"] + dw, f["w"] + dw], color=MUTED, lw=0.6, ls="--")
    ax.plot(0, 0, "o", color=RED, ms=5)
    ax.annotate("origin (0, 0, 0)", (0, 0), (2, -5), fontsize=7, color=RED)
    # top view (u-v)
    ax2 = _view(fig, [0.04, 0.515, 0.58, 0.06], (-m, L + m), (-3, T + 3), "u (mm)", "v (mm)",
                "TOP / BOTTOM  (vertical taps from both faces at the same u, v)")
    ax2.add_patch(Rectangle((0, 0), L, T, fill=False, lw=1.4, color=INK))
    for f in taps:
        if f["axis"][2] != 0:
            ax2.add_patch(Circle((f["u"], f["v"]), 1.5, fill=False, color=INK, lw=1.0))
            ax2.add_patch(Circle((f["u"], f["v"]), 1.25, fill=False, color=INK, lw=0.5, ls=":"))
    # end view (v-w) for end taps
    ax3 = _view(fig, [0.66, 0.53, 0.12, 0.37], (-4, T + 4), (-6, H + 6), "v (mm)", "w (mm)", "END  (face u = 0)")
    ax3.add_patch(Rectangle((0, 0), T, H, fill=False, lw=1.4, color=INK))
    for f in taps:
        if f["axis"][0] == 1:
            ax3.add_patch(Circle((f["v"], f["w"]), 1.5, fill=False, color=INK, lw=1.0))
    # feature table
    rows = []
    for i, f in enumerate(feats, 1):
        if f["kind"] == "tap":
            rows.append([str(i), f["thread"], f["face"], f"{f['u']:.2f}", f"{f['v']:.2f}", f"{f['w']:.2f}",
                         f"{f['thread_depth']:g}", f"Ø{f['drill']:g} x {f['drill_depth']:g}"])
        elif f["kind"] == "through":
            rows.append([str(i), f"Ø{f['d']:g} through", f["face"], f"{f['u']:.2f}", "-", f"{f['w']:.2f}", "-",
                         f["note"]])
        else:
            rows.append([str(i), "notch", f["face"], f"{f['u0']:.2f}..{f['u1']:.2f}", "0..7", f"0..{f['h']:g}", "-",
                         f["note"]])
    _table(fig, [0.04, 0.215, 0.92, 0.012 * (len(rows) + 1)],
           ["#", "Feature", "Face / direction", "u", "v", "w", "Thread depth", "Drill / note"], rows, fs=7.5)
    fig.text(0.80, 0.87, f"Stock size {L:g} x {T:g} x {H:g}", fontsize=10, color=INK)
    fig.text(0.80, 0.84, f"{len(taps)} tapped holes M3", fontsize=10, color=INK)
    fig.savefig(path, metadata={"Creator": "ELARA mechanical/jlccnc.py", "Producer": None})
    plt.close(fig)


def draw_flat(feats, part_no, title, qty, size, t, material, extra, path):
    W, Hh = size
    fig = _sheet(title, part_no, qty, material, extra)
    ax = _view(fig, [0.04, 0.25, 0.62, 0.63], (-8, W + 8), (Hh + 8, -8), "x (mm)", "y (mm)",
               "TOP  (y downwards; origin at the marked corner)")
    ax.add_patch(Rectangle((0, 0), W, Hh, fill=False, lw=1.4, color=INK))
    for f in feats:
        if f["kind"] == "pocket":
            ax.add_patch(FancyBboxPatch((f["x0"] + f["r"], f["y0"] + f["r"]), f["x1"] - f["x0"] - 2 * f["r"],
                                        f["y1"] - f["y0"] - 2 * f["r"], boxstyle=f"round,pad={f['r']}",
                                        fill=False, ec=INK, lw=1.0))
        elif f["kind"] in ("through", "bore", "blind"):
            ax.add_patch(Circle((f["x"], f["y"]), f["d"] / 2, fill=False, ec=RED if f["kind"] != "through" else INK,
                                lw=1.0, ls="--" if f["kind"] == "blind" else "-"))
    ax.plot(0, 0, "o", color=RED, ms=5)
    ax.annotate("origin", (0, 0), (2, -3), fontsize=7, color=RED)
    rows = []
    for i, f in enumerate(feats, 1):
        if f["kind"] == "pocket":
            rows.append([str(i), f"pocket {f['depth']:g} deep R{f['r']:g}", f"x {f['x0']:g}..{f['x1']:g}",
                         f"y {f['y0']:g}..{f['y1']:g}", f["note"]])
        elif f["kind"] == "blind":
            rows.append([str(i), f"Ø{f['d']:g} x {f['depth']:g} blind", f"x {f['x']:g}", f"y {f['y']:g}", f["note"]])
        else:
            rows.append([str(i), f"Ø{f['d']:g} through", f"x {f['x']:g}", f"y {f['y']:g}", f["note"]])
    half = (len(rows) + 1) // 2
    _table(fig, [0.68, 0.88 - 0.016 * (half + 1), 0.30, 0.016 * (half + 1)], ["#", "Feature", "x", "y", "Note"],
           rows[:half], fs=7)
    _table(fig, [0.68, 0.86 - 0.016 * (2 * half + 2), 0.30, 0.016 * (len(rows) - half + 1)],
           ["#", "Feature", "x", "y", "Note"], rows[half:], fs=7)
    fig.text(0.04, 0.90, f"Size {W:g} x {Hh:g} x {t:g}", fontsize=10, color=INK)
    fig.savefig(path, metadata={"Creator": "ELARA mechanical/jlccnc.py", "Producer": None})
    plt.close(fig)


# ---------------------------------------------------------------------------
BARS = [  # part no, name in amp_frame, title, quantity (identical shapes share a part)
    ("ELARA-SH-01", "long_top", "Long wall bar, DC-input notch", 1, []),
    ("ELARA-SH-02", "long_bottom", "Long wall bar", 1, []),
    ("ELARA-SH-03", "end_left", "Short wall bar (end and internal walls)", 3, ["internal_1", "internal_2"]),
    ("ELARA-SH-04", "end_right", "Short wall bar, RJ45 (AES3) notch", 1, []),
]


def _same(a, b):
    """True when two solids occupy the same volume (symmetric difference ~0)."""
    va, vb = a.val(), b.val()
    return abs(va.Volume() - vb.Volume()) < 1e-3 and va.cut(vb).Volume() < 1e-3 and vb.cut(va).Volume() < 1e-3


def main():
    os.makedirs(OUT, exist_ok=True)
    problems = []
    for part_no, name, title, qty, twins in BARS:
        solid = bar_part(name)
        for t in twins:
            if not _same(solid, bar_part(t)):
                problems.append(f"{part_no}: {t} differs from {name} (cannot share a part number)")
        feats = bar_features(name)
        bad = probe_bar(solid.val(), feats, bar_frame(name)[2])
        problems += [f"{part_no} {name}: feature not found in the solid: {f}" for f in bad]
        base = f"{part_no}_{name if not twins else 'short_bar'}"
        cq.exporters.export(solid, os.path.join(OUT, base + ".step"))
        draw_bar(name, part_no, title, qty, os.path.join(OUT, base + ".pdf"))
        print(f"{base}: {len(feats)} features, qty {qty}")
    tray = tray_part()
    tf = tray_features()
    problems += [f"ELARA-SH-05 tray: feature not found: {f}" for f in probe_flat(tray.val(), tf, P.TRAY_T)]
    cq.exporters.export(tray, os.path.join(OUT, "ELARA-SH-05_tray.step"))
    draw_flat(tf, "ELARA-SH-05", "Bottom tray (pocket-milled)", 1, (P.PCB_W, P.PCB_H), P.TRAY_T,
              "aluminium 6061-T6 plate, 15 mm, faced to 14 (EN AW-6082-T651 is fine too)",
              ["Top face (z = 14, against the PCB): flatness 0.05. Thickness 14 +/-0.1. Pockets from the top face,",
               "inside corners R3 (Ø6 end mill) or smaller. No threads in this part."],
              os.path.join(OUT, "ELARA-SH-05_tray.pdf"))
    print(f"ELARA-SH-05_tray: {len(tf)} features")
    lid = lid_part()
    lf = lid_features()
    problems += [f"ELARA-SH-06 lid: feature not found: {f}" for f in probe_flat(lid.val(), lf, P.LID_T)]
    cq.exporters.export(lid, os.path.join(OUT, "ELARA-SH-06_lid.step"))
    cq.exporters.export(lid.section(P.LID_T / 2), os.path.join(OUT, "ELARA-SH-06_lid.dxf"), "DXF")
    draw_flat(lf, "ELARA-SH-06", "Lid (sheet metal, laser cut, flat)", 1, (P.PCB_W + 2 * P.LID_EAR, P.PCB_H), P.LID_T,
              "aluminium 5052 sheet, 2 mm, laser cut (EN AW-5754 is fine too)",
              ["Flat part, no bends, no threads. Hole positions +/-0.1."], os.path.join(OUT, "ELARA-SH-06_lid.pdf"))
    print(f"ELARA-SH-06_lid: {len(lf)} features")
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("all features found in their solids; twins identical")


if __name__ == "__main__":
    main()
