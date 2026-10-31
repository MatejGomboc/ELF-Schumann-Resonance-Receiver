#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Revert regenerated outputs whose only change is metadata, so commits show real changes.

  .venv/bin/python tools/normalise_outputs.py [--dry-run]

For every modified file in `git diff`:
  STEP          DATA section equal once entity numbers (#123) and the translator
                stamp are ignored, or equal as a multiset of entities (pure reordering)
  PNG           identical pixels, or at most 20 pixels off by <= 2 levels (render noise)
  PDF / SVG     PDF: rasterised pages identical (pdftoppm); SVG: equal once ids,
                dates and float noise in the last digit are dropped
  Gerber zip    every member equal once CreationDate / date comment lines are dropped
  DXF           equal once handles and timestamps are dropped
Anything else is left alone. Prints what it reverted and what really changed.
"""
import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True).stdout


def step_same(a, b):
    def body(t):
        t = t.decode('latin-1')
        t = t[t.find('DATA;'):] if 'DATA;' in t else t
        t = re.sub(r'Open CASCADE STEP translator [\d.]+ \d+', 'OCC', t)
        return re.sub(r'#\d+', '#', t)
    x, y = body(a), body(b)
    return x == y or sorted(x.split(';')) == sorted(y.split(';'))


def png_same(a, b):
    x = np.asarray(Image.open(io.BytesIO(a)).convert('RGB')).astype(int)
    y = np.asarray(Image.open(io.BytesIO(b)).convert('RGB')).astype(int)
    if x.shape != y.shape:
        return False
    d = np.abs(x - y).max(axis=2)
    return int((d > 0).sum()) <= 20 and int(d.max()) <= 2


def pdf_same(a, b):
    with tempfile.TemporaryDirectory() as td:
        pages = []
        for tag, data in (('a', a), ('b', b)):
            p = os.path.join(td, tag + '.pdf')
            open(p, 'wb').write(data)
            subprocess.run(['pdftoppm', '-r', '60', '-png', p, os.path.join(td, tag)], check=True)
            pages.append(sorted(f for f in os.listdir(td) if f.startswith(tag + '-')))
        if len(pages[0]) != len(pages[1]):
            return False
        return all(png_same(open(os.path.join(td, f), 'rb').read(), open(os.path.join(td, g), 'rb').read())
                   for f, g in zip(*pages))


def svg_same(a, b):
    def clean(t):
        t = t.decode('utf-8', 'replace')
        t = re.sub(r'<dc:date>.*?</dc:date>', '', t)
        t = re.sub(r'\b(id|clip-path|xlink:href|href)="[^"]*"', '', t)
        t = re.sub(r'url\(#[^)]*\)', '', t)
        return re.sub(r'(\d+\.\d{3})\d+', r'\1', t)
    return clean(a) == clean(b)


def zip_same(a, b):
    za, zb = zipfile.ZipFile(io.BytesIO(a)), zipfile.ZipFile(io.BytesIO(b))
    if sorted(za.namelist()) != sorted(zb.namelist()):
        return False
    drop = re.compile(rb'^.*(CreationDate|Created by|date|DRILL file).*$', re.M | re.I)
    return all(drop.sub(b'', za.read(n)) == drop.sub(b'', zb.read(n)) for n in za.namelist())


def dxf_same(a, b):
    def clean(t):
        lines = t.decode('latin-1').splitlines()
        out, skip = [], False
        for i, ln in enumerate(lines):
            code = ln.strip()
            if skip:
                skip = False
                continue
            if code in ('5', '105', '330', '340', '360', '390', '1071') and i % 2 == 0:
                skip = True          # handle / owner / timestamp group: drop its value
                continue
            out.append(ln)
        return [ln for ln in out if not re.match(r'^\s*\d{7}\.\d+\s*$', ln)]
    return clean(a) == clean(b)


CHECKS = {'.step': step_same, '.stp': step_same, '.png': png_same, '.pdf': pdf_same,
          '.svg': svg_same, '.zip': zip_same, '.dxf': dxf_same}


def main():
    dry = '--dry-run' in sys.argv
    files = git('diff', '--name-only').decode().split()
    reverted, real = [], []
    for f in files:
        check = CHECKS.get(os.path.splitext(f)[1].lower())
        if not check or not os.path.exists(os.path.join(ROOT, f)):
            continue
        old, new = git('show', f'HEAD:{f}'), open(os.path.join(ROOT, f), 'rb').read()
        try:
            same = check(old, new)
        except Exception as e:           # unreadable: treat as a real change
            print(f'  ({f}: {e})')
            same = False
        (reverted if same else real).append(f)
    if reverted and not dry:
        git('checkout', '--', *reverted)
    print('reverted (metadata only):' if not dry else 'would revert (metadata only):')
    print(''.join(f'  {f}\n' for f in reverted) or '  -')
    print('real changes:')
    print(''.join(f'  {f}\n' for f in real) or '  -')


if __name__ == '__main__':
    main()
