#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Fit-check 3D models for parts that KiCad 9's library has no model for.

  .venv/bin/python tools/models3d.py        -> PCB/elara.3dshapes/*.step

Each model is built in footprint coordinates (mm, x right, y down, z up from
the board surface) from the footprint's own pads and fab outline plus the
datasheet body size, then mirrored into KiCad's model space (Y up). They are
envelope models for clash checks and renders, not detailed artwork: the
outside dimensions are what matter.

Sources for the body sizes (distributor/manufacturer data, see bom/README.md):
  Molex 43650-0200     9.76 x 10.0 footprint body, 6.1 mm housing, latch to 6.98 mm
  Keystone 5000/5001   4.57 mm above the board
  Newava S22083        12.7 x 8.89 x 6.35 mm
  Mean Well IRM-05     45.7 x 25.4 x 21.5 mm
  Bel FC-203-22        5 x 20 mm fuse clips (height estimated: fuse axis 7 mm)
  SiTime PQFN 3.2x2.5  0.75 mm
"""

import os

import sys

import cadquery as cq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicadgen.models import MODELS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'PCB', 'elara.3dshapes')

BLACK = cq.Color(0.08, 0.08, 0.08)
METAL = cq.Color(0.78, 0.78, 0.76)
GOLD = cq.Color(0.85, 0.68, 0.25)
RED = cq.Color(0.75, 0.1, 0.1)
WHITE = cq.Color(0.92, 0.92, 0.9)
GREY = cq.Color(0.35, 0.35, 0.37)
GLASS = cq.Color(0.8, 0.85, 0.9)


def box(x0, y0, z0, x1, y1, z1):
    """Axis-aligned box from footprint coordinates."""
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl(d, x, y, z0, z1):
    return cq.Workplane('XY').circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def hcyl(d, y, z, x0, x1):
    """Cylinder along x."""
    return cq.Workplane('YZ').circle(d / 2).extrude(x1 - x0).translate((x0, y, z))


def pin(x, y, d=0.64, below=3.0, above=0.5):
    return box(x - d / 2, y - d / 2, -below, x + d / 2, y + d / 2, above)


def save(name, parts):
    """parts: [(Workplane, colour)] in footprint coordinates -> STEP in model space."""
    a = cq.Assembly(name=name)
    for i, (wp, col) in enumerate(parts):
        a.add(wp.mirror('XZ'), name=f'{name}_{i}', color=col)
    path = os.path.join(OUT, f'{name}.step')
    a.save(path, exportType='STEP')
    return path


def microfit_43650_0200():
    """Right-angle Micro-Fit 3.0 header, 2 circuits: pins at y = 0, mating face at y = -9.03."""
    x0, x1, yf, yr = -3.44, 6.33, -9.03, 0.98
    body = box(x0, yf, 0.0, x1, yr, 6.1)
    body = body.cut(box(x0 + 1.0, yf - 0.1, 0.8, x1 - 1.0, yf + 7.0, 5.3))       # mating cavity
    latch = box(0.0, yf, 6.1, 3.0, yf + 3.5, 6.98)
    peg = cyl(2.9, 1.5, -4.32, -2.6, 0.0)
    parts = [(body.union(latch), BLACK), (peg, BLACK)]
    for x in (0.0, 3.0):
        parts.append((pin(x, 0.0, below=3.2, above=3.0), GOLD))
        parts.append((box(x - 0.32, yf + 1.5, 2.7, x + 0.32, 0.32, 3.34), GOLD))   # contact run
    return save('Molex_Micro-Fit_3.0_43650-0200_Horizontal', parts)


def keystone_5000(colour=RED, name='Keystone_5000_TestPoint'):
    """Miniature test point: insulated base, wire loop 4.57 mm above the board."""
    base = cyl(2.4, 0, 0, 0.0, 1.6)
    loop = (cq.Workplane('XZ').center(0, 3.4).circle(1.15).circle(0.85).extrude(0.25, both=True))
    leg = cyl(0.5, 0, 0, -2.5, 2.3)
    return save(name, [(base, colour), (loop.union(leg), METAL)])


def s22083():
    """Newava S22083 pulse transformer, 12.7 x 8.89 x 6.35 mm on the elara footprint."""
    body = box(-0.64, -1.27, 0.3, 8.26, 11.43, 6.35)
    parts = [(body, BLACK)]
    for x, y in ((0.0, 0.0), (7.62, 0.0), (0.0, 7.62), (7.62, 7.62)):
        parts.append((pin(x, y, d=0.6, below=3.0, above=0.6), METAL))
    return save('Newava_S22083', parts)


def turret_ptfe():
    """J201: PTFE stand-off bush with a brass pin, the node-2 lead enters from below."""
    bush = cyl(3.0, 0, 0, 0.0, 2.0)
    pin_ = cyl(1.2, 0, 0, -4.0, 4.5)
    return save('Turret_PTFE_D3.0mm', [(bush, WHITE), (pin_, GOLD)])


def irm05():
    """Mean Well IRM-05-xx: 45.7 x 25.4 x 21.5 mm, placed on the KiCad fab outline."""
    x0, y0 = -4.0, -11.2
    body = box(x0, y0, 0.0, x0 + 45.7, y0 + 25.4, 21.5)
    body = body.edges('|Z').fillet(1.0)
    parts = [(body, BLACK)]
    for x, y in ((0, 0), (0, 10.75), (38.5, 10.75), (38.5, 2.75)):
        parts.append((pin(x, y, d=1.0, below=3.5, above=0.5), METAL))
    return save('MeanWell_IRM-05-xx_THT', parts)


def fuse_clips():
    """Two Bel FC-203-22 clips with a 5 x 20 mm glass fuse, axis along x at y = 2.5."""
    zc = 7.0
    parts = []
    for xc in (0.0, 17.8):
        clip = box(xc - 2.0, -0.6, 0.0, xc + 2.0, 5.6, zc + 2.6)
        clip = clip.cut(hcyl(5.3, 2.5, zc, xc - 3, xc + 3)).cut(box(xc - 3, 0.6, zc, xc + 3, 4.4, zc + 4))
        parts.append((clip, METAL))
        for y in (0.0, 5.0):
            parts.append((pin(xc, y, d=0.9, below=3.0, above=0.5), METAL))
    parts.append((hcyl(5.2, 2.5, zc, -1.1, 18.9), GLASS))
    for xa in (-1.1, 13.1):
        parts.append((hcyl(5.3, 2.5, zc, xa, xa + 5.8), METAL))
    return save('Fuse_5x20_Bel_FC-203-22_pair', parts)


def sit_pqfn():
    return save('Oscillator_SiT_PQFN-4Pin_3.2x2.5mm', [(box(-1.6, -1.25, 0, 1.6, 1.25, 0.75), GREY)])


def main():
    os.makedirs(OUT, exist_ok=True)
    made = {os.path.basename(f()) for f in (microfit_43650_0200, keystone_5000, s22083, turret_ptfe, irm05,
                                             fuse_clips, sit_pqfn)}
    missing = set(MODELS.values()) - made
    if missing:
        raise SystemExit(f'kicadgen.models lists models that are not built: {sorted(missing)}')
    print(f'{len(made)} models -> {os.path.relpath(OUT, os.path.join(HERE, ".."))}')


if __name__ == '__main__':
    main()
