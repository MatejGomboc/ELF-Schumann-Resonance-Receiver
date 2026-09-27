# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Amplifier shield -- complete assembly (PCB + frame + lid + tray + fasteners).

Also produces the preview renders: isometric with the lid off, and an
exploded view.  Frame: X = x_kicad, Y = -y_kicad, Z = 0 at the PCB top.

Fastener count
  24 x M3x25 ISO 7380 button (A2)  tray -> PCB -> tapped wall bottoms
  24 x M3x8  ISO 7380 button (A2)  lid  -> tapped wall tops
  16 x M3x16 DIN 912 socket  (A2)  frame corner / tee joints
"""

import cadquery as cq

import params as P
import amp_frame
import amp_lid
import amp_pcb
import amp_tray
from common import (ALU, ALU_DARK, PTFE, STEEL, button_screw, export_step, render,
                    socket_screw)

Z_TRAY_BOTTOM = -P.PCB_T - P.TRAY_T
Z_LID_TOP = P.FRAME_H + P.LID_T


def tray_screws():
    s = button_screw(P.TRAY_SCREW_L).rotate((0, 0, 0), (1, 0, 0), 180)
    return [s.translate((x, -y, Z_TRAY_BOTTOM)) for (x, y) in P.AMP_HOLES]


def lid_screws():
    s = button_screw(P.LID_SCREW_L)
    return [s.translate((x, -y, Z_LID_TOP)) for (x, y) in P.AMP_HOLES]


def joint_screws():
    out = []
    base = socket_screw(P.JOINT_SCREW_L)
    for (x, y, z, d) in amp_frame.joint_screw_positions():
        ang = -90 if d == (0, 1, 0) else 90
        out.append(base.rotate((0, 0, 0), (1, 0, 0), ang).translate((x, y, z)))
    return out


def _compound(ws):
    return cq.Workplane().add(cq.Compound.makeCompound([v for w in ws for v in w.vals()]))


def build(explode=0.0, lid=True, pcb=True):
    """explode: scale factor for the exploded view (0 = assembled)."""
    e = explode
    a = cq.Assembly(name="amp_shield")
    for n, bar in amp_frame.build().items():
        a.add(bar, name=f"frame_{n}", color=ALU)
    a.add(_compound(joint_screws()), name="joint_screws_M3x16", color=STEEL)
    if lid:
        a.add(amp_lid.build(), name="lid", color=ALU_DARK, loc=cq.Location((0, 0, 60 * e)))
        a.add(_compound(lid_screws()), name="lid_screws_M3x8", color=STEEL,
              loc=cq.Location((0, 0, 95 * e)))
    if pcb:
        pa = amp_pcb.assembly()
        a.add(pa, name="pcb", loc=cq.Location((0, 0, -30 * e)))
    a.add(amp_tray.build(), name="tray", color=ALU, loc=cq.Location((0, 0, -60 * e)))
    a.add(amp_tray.feedthrough(), name="feedthrough_ptfe", color=PTFE,
          loc=cq.Location((0, 0, -85 * e)))
    a.add(_compound(tray_screws()), name="tray_screws_M3x25", color=STEEL,
          loc=cq.Location((0, 0, -110 * e)))
    return a


if __name__ == "__main__":
    export_step(build(), "amp_shield_assembly")
    print(render(build(lid=False), "amp_shield_iso_lid_off", direction=(0.9, 1.0, 1.1),
                 title="Antenna-amplifier shield -- lid removed"))
    print(render(build(explode=1.0), "amp_shield_exploded", direction=(0.8, -1.2, 0.55),
                 width=1400, height=1600, title="Antenna-amplifier shield -- exploded"))
    print(render(build(), "amp_shield_underside", direction=(0.75, -1.1, -1.0),
                 title="Antenna-amplifier shield -- tray side, PTFE feed-through"))
