# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Shared helpers: output paths, simple fastener models, STEP/SVG/PNG export."""

import os
import subprocess

import cadquery as cq

import params as P

HERE = os.path.dirname(os.path.abspath(__file__))
STEP_DIR = os.path.join(HERE, "step")
RENDER_DIR = os.path.join(HERE, "renders")
DXF_DIR = os.path.join(HERE, "dxf")
for _d in (STEP_DIR, RENDER_DIR, DXF_DIR):
    os.makedirs(_d, exist_ok=True)

# Colours for assemblies (STEP carries them; SVG previews are line drawings)
ALU = cq.Color(0.78, 0.79, 0.80)
ALU_DARK = cq.Color(0.62, 0.63, 0.65)
PCB_GREEN = cq.Color(0.10, 0.35, 0.18)
COPPER = cq.Color(0.80, 0.50, 0.25)
PTFE = cq.Color(0.95, 0.95, 0.93)
POM = cq.Color(0.15, 0.15, 0.15)
NYLON = cq.Color(0.92, 0.90, 0.82)
STEEL = cq.Color(0.45, 0.46, 0.48)
BLACK = cq.Color(0.08, 0.08, 0.08)
PLASTIC_GREY = cq.Color(0.72, 0.73, 0.72)
PE_WHITE = cq.Color(0.90, 0.90, 0.88)
RESISTOR_BLUE = cq.Color(0.35, 0.55, 0.80)


# ---------------------------------------------------------------------------
# Fasteners (simplified but dimensionally honest)
# ---------------------------------------------------------------------------
def button_screw(length, spec=P.BUTTON_M3):
    """ISO 7380-style button head screw, head on +Z at z=0, shank into -Z."""
    head = (cq.Workplane("XY").circle(spec["head_d"] / 2).extrude(spec["head_h"])
            .faces(">Z").edges().chamfer(spec["head_h"] * 0.45))
    head = head.faces(">Z").workplane().polygon(6, spec["hex"] / 0.866).cutBlind(-spec["head_h"] * 0.6)
    shank = cq.Workplane("XY").circle(spec["d"] / 2).extrude(-length)
    return head.union(shank)


def socket_screw(length, spec=P.SOCKET_M3):
    head = cq.Workplane("XY").circle(spec["head_d"] / 2).extrude(spec["head_h"])
    head = head.faces(">Z").workplane().polygon(6, spec["hex"] / 0.866).cutBlind(-spec["head_h"] * 0.6)
    shank = cq.Workplane("XY").circle(spec["d"] / 2).extrude(-length)
    return head.union(shank)


def cheese_screw(length, d=3.0, head_d=5.5, head_h=2.0):
    """DIN 84 slotted cheese head (nylon)."""
    head = cq.Workplane("XY").circle(head_d / 2).extrude(head_h)
    head = head.cut(cq.Workplane("XY").box(head_d, 0.8, 0.9, centered=(True, True, False))
                    .translate((0, 0, head_h - 0.9)))
    return head.union(cq.Workplane("XY").circle(d / 2).extrude(-length))


def hex_nut(d=3.0, af=5.5, t=2.4):
    return (cq.Workplane("XY").polygon(6, af / 0.866).extrude(t)
            .faces(">Z").workplane().hole(d))


def drill(wp, pts, d, z0, z1):
    """Cut vertical through-holes of diameter d at CQ XY points between z0 and z1."""
    cyls = [cq.Solid.makeCylinder(d / 2, z1 - z0, cq.Vector(x, y, z0)) for (x, y) in pts]
    return wp.cut(cq.Workplane("XY").add(cq.Compound.makeCompound(cyls)))


def place(shape, x, y, z, rot=None):
    """Translate (and optionally rotate: rot = (axis_tuple, angle)) a Workplane."""
    s = shape
    if rot is not None:
        s = s.rotate((0, 0, 0), rot[0], rot[1])
    return s.translate((x, y, z))


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_step(obj, name):
    path = os.path.join(STEP_DIR, name + ".step")
    if isinstance(obj, cq.Assembly):
        obj.export(path)
    else:
        cq.exporters.export(obj, path)
    return path


def export_dxf(wp, name):
    """Export a planar section (XY) of a flat part for waterjet/laser/hand layout."""
    path = os.path.join(DXF_DIR, name + ".dxf")
    cq.exporters.export(wp.section(), path, "DXF")
    return path


def assembly_compound(assy):
    """Flatten an Assembly into a single Compound (for SVG line renders)."""
    return assy.toCompound()


def _camera_transform(shape, direction, up=(0.0, 0.0, 1.0)):
    """Rotate a shape so that `direction` (target -> camera) becomes +Z and the
    projected `up` becomes +Y.  The SVG exporter can then project along +Z with
    a predictable in-plane orientation."""
    import numpy as np
    from OCP.gp import gp_Trsf

    back = np.array(direction, float)
    back /= np.linalg.norm(back)
    right = np.cross(np.array(up, float), back)
    if np.linalg.norm(right) < 1e-9:
        right = np.array([1.0, 0.0, 0.0])
    right /= np.linalg.norm(right)
    upv = np.cross(back, right)
    t = gp_Trsf()
    t.SetValues(right[0], right[1], right[2], 0.0,
                upv[0], upv[1], upv[2], 0.0,
                back[0], back[1], back[2], 0.0)
    return shape.transformShape(cq.Matrix(t))


def _finish_png(png, title=None, margin=40):
    """Crop surplus white space and add an optional title strip."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    im = Image.open(png).convert("RGB")
    bbox = ImageOps.invert(im).getbbox()
    if bbox:
        im = im.crop((max(bbox[0] - margin, 0), max(bbox[1] - margin, 0),
                      min(bbox[2] + margin, im.width), min(bbox[3] + margin, im.height)))
    if title:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
            small = ImageFont.truetype("DejaVuSans.ttf", 16)
        except OSError:
            font = small = ImageFont.load_default()
        band = 70
        out = Image.new("RGB", (max(im.width, 900), im.height + band), "white")
        out.paste(im, (0, band))
        d = ImageDraw.Draw(out)
        d.text((margin, 14), title, fill=(20, 20, 20), font=font)
        d.text((margin, 46), "ELARA  |  mechanical/  |  CERN-OHL-W-2.0", fill=(110, 110, 110), font=small)
        d.line((margin, band - 4, out.width - margin, band - 4), fill=(20, 20, 20), width=2)
        im = out
    im.save(png)


def render(obj, name, direction=(1.0, -1.2, 0.9), up=(0.0, 0.0, 1.0),
           width=1400, height=1000, hidden=False, stroke=0.35, title=None):
    """SVG line projection + PNG via rsvg-convert.  Returns the PNG path.

    direction: vector from the model towards the camera (world coordinates).
    """
    if isinstance(obj, cq.Assembly):
        shape = assembly_compound(obj)
    elif isinstance(obj, cq.Workplane):
        vals = [v for v in obj.vals() if isinstance(v, cq.Shape)]
        shape = vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
    else:
        shape = obj
    shape = _camera_transform(shape, direction, up)
    svg = os.path.join(RENDER_DIR, name + ".svg")
    png = os.path.join(RENDER_DIR, name + ".png")
    cq.exporters.export(
        cq.Workplane().add(shape), svg,
        opt={
            "width": width, "height": height,
            "marginLeft": 30, "marginTop": 30,
            "showAxes": False,
            "projectionDir": (0.0, 0.0, 1.0),
            "strokeWidth": stroke,
            "strokeColor": (30, 30, 30),
            "hiddenColor": (175, 175, 175),
            "showHidden": hidden,
        },
    )
    subprocess.run(["rsvg-convert", "-b", "white", svg, "-o", png], check=True)
    _finish_png(png, title)
    return png
