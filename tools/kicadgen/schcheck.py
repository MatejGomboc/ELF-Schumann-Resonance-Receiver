#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Schematic legibility check on KiCad's own rendering.

  python3 tools/kicadgen/schcheck.py PCB/antenna_amplifier/antenna_amplifier.kicad_sch [...]

Every sheet is exported to SVG with kicad-cli. In that SVG each text is a
'stroked-text' group holding the exact strokes KiCad draws, so text boxes are
real, not estimated. Reported:
  - text overlapping other text
  - text crossed by a line (wire, symbol body, pin, block border)
  - text outside the drawing frame or inside the title block
Exit status 1 if anything is found.
"""

import os
import re
import subprocess
import sys
import tempfile

NUM = r'-?\d+(?:\.\d+)?'
FRAME = 12.0                # inner drawing frame, mm from the paper edge
TITLE = (108.0, 32.0)       # title block size from the bottom-right frame corner


def _points(d):
    vals = [float(v) for v in re.findall(NUM, d)]
    return list(zip(vals[0::2], vals[1::2]))


def _arc(p0, rx, ry, phi, large, sweep, p1, n=12):
    """Sample an SVG elliptical arc (endpoint form) into n+1 points."""
    import math
    if rx == 0 or ry == 0:
        return [p0, p1]
    c, s_ = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = c * dx + s_ * dy, -s_ * dx + c * dy
    lam = (x1 / rx) ** 2 + (y1 / ry) ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    k = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        k = -k
    cx1, cy1 = k * rx * y1 / ry, -k * ry * x1 / rx
    cx = c * cx1 - s_ * cy1 + (p0[0] + p1[0]) / 2
    cy = s_ * cx1 + c * cy1 + (p0[1] + p1[1]) / 2
    ang = lambda ux, uy: math.atan2(uy, ux)
    t0 = ang((x1 - cx1) / rx, (y1 - cy1) / ry)
    t1 = ang((-x1 - cx1) / rx, (-y1 - cy1) / ry)
    dt = t1 - t0
    if sweep and dt < 0:
        dt += 2 * math.pi
    elif not sweep and dt > 0:
        dt -= 2 * math.pi
    out = []
    for i in range(n + 1):
        t = t0 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((c * x - s_ * y + cx, s_ * x + c * y + cy))
    return out


def _path_segments(d):
    """Absolute M/L/H/V/A/C/Z path data -> straight segments."""
    toks = re.findall(r'[MLHVACZmlhvacz]|' + NUM, d)
    segs, cur, start, cmd, i = [], None, None, None, 0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in 'Zz' and cur and start:
                segs.append((cur, start))
                cur = start
            continue
        if cmd in ('M', 'L'):
            p = (float(toks[i]), float(toks[i + 1]))
            i += 2
            if cmd == 'M':
                start = p
                cmd = 'L'            # implicit lineto after the first pair
            elif cur:
                segs.append((cur, p))
            cur = p
        elif cmd == 'H':
            p = (float(toks[i]), cur[1]); i += 1
            segs.append((cur, p)); cur = p
        elif cmd == 'V':
            p = (cur[0], float(toks[i])); i += 1
            segs.append((cur, p)); cur = p
        elif cmd == 'A':
            rx, ry, phi, large, sweep, x, y = (float(v) for v in toks[i:i + 7])
            i += 7
            pts = _arc(cur, rx, ry, phi, int(large), int(sweep), (x, y))
            segs += list(zip(pts, pts[1:]))
            cur = (x, y)
        elif cmd == 'C':
            p = (float(toks[i + 4]), float(toks[i + 5])); i += 6
            segs.append((cur, p)); cur = p
        else:
            i += 1
    return segs


def parse(svg):
    """-> (paper (w, h), texts [(str, box)], segments [((x0, y0), (x1, y1))])"""
    with open(svg, encoding='utf-8') as f:
        s = f.read()
    w = float(re.search(r'<svg[^>]*width="(' + NUM + ')', s).group(1))
    h = float(re.search(r'<svg[^>]*height="(' + NUM + ')', s).group(1))
    texts, segs = [], []
    # stroked text groups (no nested <g> inside them)
    for m in re.finditer(r'<g class="stroked-text"><desc>(.*?)</desc>(.*?)</g>', s, re.S):
        pts = [p for d in re.findall(r'd="([^"]*)"', m.group(2)) for p in _points(d)]
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            box = (min(xs), min(ys), max(xs), max(ys))
            t = _unescape(m.group(1))
            # KiCad sometimes plots the same text twice in the same place
            if not any(t == t2 and all(abs(a - b) < 0.05 for a, b in zip(box, b2)) for t2, b2 in texts):
                texts.append((t, box))
    rest = re.sub(r'<g class="stroked-text">.*?</g>', '', s, flags=re.S)
    rest = re.sub(r'<text.*?</text>', '', rest, flags=re.S)
    for d in re.findall(r'<path[^>]*\sd="([^"]*)"', rest):
        segs += _path_segments(d)
    for m in re.finditer(r'<rect x="(' + NUM + ')" y="(' + NUM + ')" width="(' + NUM + ')" height="(' + NUM + ')"', rest):
        x, y, rw, rh = (float(v) for v in m.groups())
        if rw >= w * 0.99:
            continue                                    # page background
        c = [(x, y), (x + rw, y), (x + rw, y + rh), (x, y + rh)]
        segs += list(zip(c, c[1:] + c[:1]))
    for m in re.finditer(r'<circle cx="(' + NUM + ')" cy="(' + NUM + ')" r="(' + NUM + ')"', rest):
        cx, cy, r = (float(v) for v in m.groups())
        if r > 0.6:                                     # junction dots are tiny; skip
            c = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
            segs += list(zip(c, c[1:] + c[:1]))
    return (w, h), texts, segs


def _unescape(t):
    return t.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')


def _overlap(a, b, m):
    return a[0] + m < b[2] and b[0] + m < a[2] and a[1] + m < b[3] and b[1] + m < a[3]


def _seg_hits_box(p, q, box, m):
    """Does the segment p-q cross the box shrunk by m (Liang-Barsky)?"""
    x0, y0, x1, y1 = box[0] + m, box[1] + m, box[2] - m, box[3] - m
    if x0 >= x1 or y0 >= y1:
        return False
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
            continue
        t = qq / pp
        if pp < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    return t0 < t1


def _pin_pair(a, b):
    """A pin number next to its own pin name is normal symbol layout."""
    return a.isdigit() != b.isdigit() and (a.isdigit() or b.isdigit()) and len(min(a, b, key=len)) <= 2


def check_page(svg, margin=0.12, gap=0.3):
    (w, h), texts, segs = parse(svg)
    problems = []
    tb = (w - FRAME - TITLE[0], h - FRAME - TITLE[1], w - FRAME, h - FRAME)
    for i, (t, b) in enumerate(texts):
        if b[0] < FRAME or b[1] < FRAME or b[2] > w - FRAME or b[3] > h - FRAME:
            problems.append(f'outside the frame: "{t}" at ({b[0]:.1f}, {b[1]:.1f})')
        elif _overlap(b, tb, 0):
            problems.append(f'in the title block: "{t}" at ({b[0]:.1f}, {b[1]:.1f})')
        for t2, b2 in texts[i + 1:]:
            if _overlap(b, b2, margin):
                problems.append(f'text over text: "{t}" / "{t2}" at ({b[0]:.1f}, {b[1]:.1f})')
            elif _overlap(b, b2, -gap) and not _pin_pair(t, t2):
                problems.append(f'texts touching: "{t}" / "{t2}" at ({b[0]:.1f}, {b[1]:.1f})')
            elif t == t2 and _overlap(b, b2, -1.0):
                problems.append(f'same text twice, close together: "{t}" at ({b[0]:.1f}, {b[1]:.1f})')
        if t.startswith('~{\u03a6') or t.startswith('\u03a6'):
            continue                  # clock-input bars drawn by the stock CD4060 symbol
        for p, q in segs:
            if _seg_hits_box(p, q, b, margin):
                problems.append(f'line through text: "{t}" at ({b[0]:.1f}, {b[1]:.1f}) '
                                f'line ({p[0]:.1f},{p[1]:.1f})-({q[0]:.1f},{q[1]:.1f})')
                break
    return problems


def check(sch):
    with tempfile.TemporaryDirectory(dir='/tmp') as d:
        subprocess.run(['kicad-cli', 'sch', 'export', 'svg', '--exclude-drawing-sheet', '-o', d,
                        os.path.abspath(sch)], check=True, capture_output=True)
        out = {}
        for f in sorted(os.listdir(d)):
            if f.endswith('.svg'):
                out[f[:-4]] = check_page(os.path.join(d, f))
        return out


def main():
    bad = 0
    for sch in sys.argv[1:]:
        for page, problems in check(sch).items():
            print(f'{page}: {len(problems)} problem(s)')
            for p in problems:
                print('   ', p)
            bad += len(problems)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
