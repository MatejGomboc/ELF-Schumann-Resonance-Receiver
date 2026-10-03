# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Mounting-plate layout drawing (2D, front view, 1:1 coordinates in mm).

Shows the box inner outline, the mounting plate with every hole, the
footprint of each unit, the cable glands and a stud coordinate table.
Output: renders/mounting_plate_layout.svg + .png.  The machinable outline
is in dxf/mounting_plate.dxf (from outer_box.py).
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                          # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle   # noqa: E402

import params as P                                       # noqa: E402
import outer_box as OB                                   # noqa: E402
import platecap                                          # noqa: E402
from common import RENDER_DIR                            # noqa: E402

INK = "#1a1a1a"
MUTED = "#8a8a8a"
PLATE_BG = "#f4f4f2"
UNIT = {"platecap": "#3b6ea5", "amp": "#b5542b", "psu": "#2f7d4f"}
# a text that has to sit on a centre line breaks it (drafting practice): the label
# gets a patch of the plate colour behind it; every other label is placed clear of lines
MASK = dict(fc=PLATE_BG, ec="none", pad=0.6)


def rect(ax, x0, y0, w, h, **kw):
    kw.setdefault("fill", False)
    kw.setdefault("lw", 1.0)
    kw.setdefault("ec", INK)
    ax.add_patch(Rectangle((x0, y0), w, h, **kw))


def dim(ax, p0, p1, text, off=(0, 0), vertical=False):
    ax.annotate("", xy=p0, xytext=p1, arrowprops=dict(arrowstyle="<->", lw=0.8, color=INK))
    mx, my = (p0[0] + p1[0]) / 2 + off[0], (p0[1] + p1[1]) / 2 + off[1]
    ax.text(mx, my, text, ha="center", va="center", fontsize=8, color=INK,
            rotation=90 if vertical else 0,
            bbox=dict(fc="white", ec="none", pad=1.0))


def draw():
    fig, ax = plt.subplots(figsize=(11, 13.5))
    ax.set_aspect("equal")
    ax.axis("off")

    # box inner outline + walls
    IW, IH, Wl = P.BOX_INNER_W, P.BOX_INNER_H, P.BOX_WALL
    ax.add_patch(FancyBboxPatch((-IW / 2 - Wl, -IH / 2 - Wl), IW + 2 * Wl, IH + 2 * Wl,
                                boxstyle="round,pad=0,rounding_size=8", fill=False, ec=MUTED, lw=1.2))
    ax.add_patch(FancyBboxPatch((-IW / 2, -IH / 2), IW, IH, boxstyle="round,pad=0,rounding_size=4",
                                fill=False, ec=MUTED, lw=0.8, ls="--"))
    # mounting plate
    MW, MH = P.MOUNT_PLATE_W, P.MOUNT_PLATE_H
    rect(ax, -MW / 2, -MH / 2, MW, MH, lw=1.6, fc=PLATE_BG, fill=True)
    for (x, y) in OB.plate_fixing_points():
        ax.add_patch(Circle((x, y), P.M4_CLEAR / 2, fill=False, ec=INK, lw=1.0))
        ax.plot([x - 5, x + 5], [y, y], color=INK, lw=0.4)
        ax.plot([x, x], [y - 5, y + 5], color=INK, lw=0.4)

    # --- plate capacitor assembly
    cx, cy = P.LAYOUT["platecap"]
    c = UNIT["platecap"]
    rect(ax, cx - P.PLATECAP_BASE_W / 2, cy - P.PLATECAP_BASE_D / 2, P.PLATECAP_BASE_W,
         P.PLATECAP_BASE_D, ec=c, lw=1.4)
    for name, pcx in platecap.CAP_CX.items():
        rect(ax, cx + pcx - P.PLATE_SIZE / 2, cy - P.PLATE_SIZE / 2, P.PLATE_SIZE, P.PLATE_SIZE,
             ec=c, lw=0.9)
        cu = P.PLATE_CU
        rect(ax, cx + pcx - cu / 2, cy - cu / 2, cu, cu, ec=c, lw=0.5, ls=":")
        ax.text(cx + pcx, cy, f"{name}\n50 pF air\n0.5 mm", ha="center", va="center", fontsize=8,
                color=c)
    for sx, lab in ((1, "ANT"), (-1, "IN+")):
        ax.add_patch(Circle((cx + sx * platecap.POST_X, cy), P.TERMINAL_POST["d"] / 2,
                            fill=False, ec=c))
        ax.text(cx + sx * platecap.POST_X, cy - 11, lab, ha="center", fontsize=7, color=c)
    ax.text(cx, cy - P.PLATECAP_BASE_D / 2 + 5, "AIR-GAP CAPS -- POM base 184 x 92 x 8",
            ha="center", va="bottom", fontsize=7, color=c, weight="bold", bbox=MASK)

    # --- amplifier shield (lid-down, tray towards the door)
    ax_, ay_ = P.LAYOUT["amp"]
    c = UNIT["amp"]
    x0, y0 = ax_ - P.PCB_W / 2, ay_ - P.PCB_H / 2
    rect(ax, x0 - P.LID_EAR, y0, P.PCB_W + 2 * P.LID_EAR, P.PCB_H, ec=c, lw=0.8, ls="--")
    rect(ax, x0, y0, P.PCB_W, P.PCB_H, ec=c, lw=1.4)
    for xw in P.INTERNAL_WALL_X:
        ax.plot([x0 + xw] * 2, [y0, y0 + P.PCB_H], color=c, lw=0.6, ls="-.")
    # KiCad y maps to +Y here (shield rotated 180 deg about X)
    for (name, (xa, xb)) in (("C1 INPUT", (7, 41.5)), ("C2 ANALOG", (48.5, 116.5)),
                             ("C3 DIGITAL", (123.5, 193))):
        ax.text(x0 + (xa + xb) / 2, y0 + 88, name, ha="center", fontsize=8, color=c)
    fx, fy = P.FEEDTHROUGH_XY
    ax.add_patch(Circle((x0 + fx, y0 + fy), P.FEEDTHROUGH_FLANGE_D / 2, fill=False, ec=c))
    ax.text(x0 + fx, y0 + fy + P.FEEDTHROUGH_FLANGE_D / 2 + 2, "PTFE feed-\nthrough", ha="center",
            va="bottom", fontsize=7, color=c)
    for cut in P.CUTOUTS:
        if cut["edge"] == "top":
            ax.add_patch(Rectangle((x0 + cut["pos"] - cut["w"] / 2, y0 - 2), cut["w"], 4, fc=c, ec=c))
            ax.text(x0 + cut["pos"], y0 - 7, "DC in", ha="center", fontsize=7, color=c)
        else:
            w = cut.get("w", cut.get("d"))
            ax.add_patch(Rectangle((x0 + P.PCB_W - 2, y0 + cut["pos"] - w / 2), 4, w, fc=c, ec=c))
            # inside the shield, clear of the lid-ear outline
            ax.text(x0 + P.PCB_W - 4, y0 + cut["pos"], cut["name"].split()[0][2:], fontsize=7,
                    color=c, ha="right", va="center", bbox=MASK)
    # title in the gap between the shield and the PSU, clear of the compartment walls
    ax.text(x0 + P.PCB_W / 2, y0 - 3, "ANTENNA-AMPLIFIER SHIELD\n200 x 100 x 69.6 (tray faces door)",
            ha="center", va="top", fontsize=8, color=c, weight="bold", bbox=MASK)

    # --- PSU box
    px, py = P.LAYOUT["psu"]
    c = UNIT["psu"]
    T = P.PSU_BAR_T
    bx0, by0 = px - P.PSU_INNER_W / 2 - T, py - P.PSU_INNER_D / 2 - T
    bw, bh = P.PSU_INNER_W + 2 * T, P.PSU_INNER_D + 2 * T
    rect(ax, bx0 - P.PSU_EAR, by0, bw + 2 * P.PSU_EAR, bh, ec=c, lw=0.8, ls="--")
    rect(ax, bx0, by0, bw, bh, ec=c, lw=1.4)
    gm, go = P.PSU_GLAND_MAINS, P.PSU_GLAND_OUT
    ym, yo = by0 + T + P.PSU_GLAND_MAINS_Y, by0 + T + P.PSU_GLAND_OUT_Y      # in line with J1 / J2
    rect(ax, bx0 - gm["dome_l"], ym - gm["body_d"] / 2, gm["dome_l"], gm["body_d"], ec=c, lw=0.8)
    rect(ax, bx0 + bw, yo - go["body_d"] / 2, go["dome_l"], go["body_d"], ec=c, lw=0.8)
    height = P.PSU_BASE_T + P.PSU_INNER_H + P.PSU_LID_T
    ax.text(px, py, f"PSU ENCLOSURE\n168 x 108 x {height:.0f}\n(two-bucket supply)", ha="center", va="center",
            fontsize=9, color=c, weight="bold", bbox=MASK)
    # gland labels inside the box, in line with their gland
    ax.text(bx0 + T + 3, ym, "M16 mains", ha="left", va="center", fontsize=7, color=c)
    ax.text(bx0 + bw - T - 3, yo, "M12 DC out", ha="right", va="center", fontsize=7, color=c)

    # --- studs
    for unit, pts in OB.stud_points().items():
        for (x, y) in pts:
            ax.add_patch(Circle((x, y), P.M4_CLEAR / 2, fc=UNIT[unit], ec=INK, lw=0.6))

    # --- glands in the box
    for g in P.BOX_GLANDS:
        s = 1 if g["wall"] == "top" else -1
        yw = s * (IH / 2 + Wl)
        ax.add_patch(Rectangle((g["x"] - g["af"] / 2, yw if s > 0 else yw - g["dome"]),
                               g["af"], g["dome"], fc="#333333", ec=INK))
        ax.text(g["x"], yw + s * (g["dome"] + 6), f"M{g['thread']:.0f}  {g['name']}",
                ha="center", va="center", fontsize=8, color=INK)

    # --- dimensions
    dim(ax, (-MW / 2, -MH / 2 - 52), (MW / 2, -MH / 2 - 52), f"plate {MW:.0f}", off=(0, 0))
    dim(ax, (-MW / 2 - 22, -MH / 2), (-MW / 2 - 22, MH / 2), f"plate {MH:.0f}", vertical=True)
    dim(ax, (-IW / 2, IH / 2 + 38), (IW / 2, IH / 2 + 38), f"box inner {IW:.0f}")
    dim(ax, (IW / 2 + 22, -IH / 2), (IW / 2 + 22, IH / 2), f"box inner {IH:.0f}", vertical=True)
    ax.plot([0, 0], [-MH / 2 - 8, MH / 2 + 8], color=MUTED, lw=0.4, ls=(0, (8, 3, 2, 3)))
    ax.plot([-MW / 2 - 8, MW / 2 + 8], [0, 0], color=MUTED, lw=0.4, ls=(0, (8, 3, 2, 3)))

    # stud table
    rows = []
    for unit, pts in OB.stud_points().items():
        for (x, y) in pts:
            rows.append(f"{unit:9s} X{x:+7.1f} Y{y:+7.1f}")
    for (x, y) in OB.plate_fixing_points():
        rows.append(f"{'fixing':9s} X{x:+7.1f} Y{y:+7.1f}")
    txt = "HOLE TABLE  (all 4.5 mm, csk from back for M4 studs;\n" \
          "origin = plate centre, X right, Y up)\n" + "\n".join(rows)
    ax.text(IW / 2 + 45, IH / 2, txt, fontsize=7, family="monospace", va="top", color=INK)

    ax.set_xlim(-IW / 2 - 50, IW / 2 + 250)
    ax.set_ylim(-IH / 2 - 70, IH / 2 + 55)
    ax.set_title("ELARA outdoor unit -- mounting-plate layout (front view, door removed)\n"
                 "8 mm PE-HD plate on the box bosses; units on M4 studs, "
                 "5 mm spacers under amplifier and PSU ears", fontsize=11, loc="left")
    svg = os.path.join(RENDER_DIR, "mounting_plate_layout.svg")
    png = os.path.join(RENDER_DIR, "mounting_plate_layout.png")
    fig.savefig(svg, bbox_inches="tight")
    fig.savefig(png, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png


if __name__ == "__main__":
    print(draw())
