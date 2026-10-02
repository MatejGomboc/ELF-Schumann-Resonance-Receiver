# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Real board geometry for the mechanical models and fit checks.

The populated STEP models written by ``tools/fab_outputs.sh`` (KiCad export,
origin at the board's top-left corner, X right, Y up, board bottom at Z = 0)
are imported as named assemblies: every fitted part is a child named by its
reference designator. Here they are moved into the mechanical frame used by
the CadQuery scripts: X = x_kicad, Y = -y_kicad, Z = 0 at the PCB TOP face.

The connector plugs and the cable ends are not on the board, so they are
added as simple bodies from their datasheet sizes (see ``plugs``).
"""

import os

import cadquery as cq

import params as P

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def step_path(board):
    return os.path.join(ROOT, "PCB", board, "fab", f"{board}.step")


def load(board, pcb_t=1.6):
    """-> (pcb_body Shape, {ref: Shape}) in the mechanical frame."""
    path = step_path(board)
    if not os.path.exists(path):
        raise SystemExit(f"{path} missing: run tools/fab_outputs.sh on the board first")
    a = cq.Assembly.importStep(path)
    down = cq.Location((0, 0, -pcb_t))
    body, parts = None, {}
    for c in a.children:
        shape = c.toCompound().moved(down)
        if c.name.startswith("=>") or c.name.upper().endswith("PCB"):
            body = shape                       # the board itself
        else:
            parts[c.name] = shape
    return body, parts


def envelope(shape):
    """Bounding-box stand-in for a part (small STEP exports; the detailed boards are
    in PCB/*/fab/*.step)."""
    b = shape.BoundingBox()
    return cq.Solid.makeBox(b.xlen, b.ylen, b.zlen, cq.Vector(b.xmin, b.ymin, b.zmin))


def box(x0, y0, z0, x1, y1, z1):
    """Box from KiCad xy (y down) and mechanical z."""
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, -y1, z0)).val())


def plugs():
    """Mated plugs on the amplifier's edge connectors (datasheet envelopes)."""
    out = {}
    # Phoenix MC 1,5/3-ST-3,81 (12.22 W x 11.1 H x 16.1 L), about 6 mm inside the header
    yc = P.CUTOUTS_BY_NAME["J_AES3"]["pos"]
    out["AES3 plug"] = box(193.0, yc - 6.11, 0.4, 209.1, yc + 6.11, 11.5)
    # Molex 43645-0200 Micro-Fit plug, about 9 x 7.5 mm with the latch, 5 mm inside the header
    xc = P.CUTOUTS_BY_NAME["J_PWR"]["pos"]
    out["Micro-Fit plug"] = box(xc - 4.5, -9.0, 0.6, xc + 4.5, 5.5, 8.1)
    return out
