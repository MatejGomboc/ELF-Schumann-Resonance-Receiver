#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Derive project footprint variants (elara.pretty) from KiCad stock footprints.

  python3 tools/fp_variants.py <stock footprints dir>
  (in the cloud: docker run --rm -u 0 -v $PWD:$PWD -w $PWD kicad/kicad:9.0-full \\
   python3 tools/fp_variants.py /usr/share/kicad/footprints)

Only silkscreen is removed; pads, courtyard, fab layer and 3D model are unchanged.
- LMP7721 (U201) sits half on the bare guard island: no silk on the pin 1-4 half
  (it would be ink on the femtoamp surface); pin 1 is marked on the fab layer.
- J202 (bias link) sits wholly on the island: no silkscreen at all.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'PCB', 'elara.pretty')


def blocks(text):
    """Split the footprint body into top-level child blocks (text spans)."""
    depth, start, out = 0, None, []
    body = text[text.index('\n'):]            # skip '(footprint "name"'
    for i, ch in enumerate(body):
        if ch == '(':
            depth += 1
            if depth == 1:
                start = i
        elif ch == ')':
            if depth == 1:
                out.append(body[start:i + 1])
            depth -= 1
    return out


def ys(block):
    return [float(y) for y in re.findall(r'\((?:start|end|xy) [-\d.]+ ([-\d.]+)\)', block)]


def derive(src, name, drop, descr):
    with open(src, encoding='utf-8') as f:
        text = f.read()
    keep = []
    for b in blocks(text):
        head = b[1:].split(None, 1)[0]
        if head in ('fp_line', 'fp_poly', 'fp_rect', 'fp_circle', 'fp_arc') and '"F.SilkS"' in b and drop(b):
            continue
        if head == 'descr':
            b = f'(descr "{descr}")'
        keep.append(b)
    out = f'(footprint "{name}"\n\t' + '\n\t'.join(keep) + '\n)\n'
    with open(os.path.join(OUT, f'{name}.kicad_mod'), 'w', encoding='utf-8') as f:
        f.write(out)
    print('wrote', name)


def main():
    root = sys.argv[1]
    derive(os.path.join(root, 'Package_SO.pretty', 'SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod'),
           'SOIC-8_3.9x4.9mm_P1.27mm_GuardIsland',
           lambda b: max(ys(b)) < 0,               # top edge and pin-1 mark: over the island
           'SOIC-8 for an op-amp whose pin 1-4 side sits on a bare guard island: no silkscreen '
           'on that side (pin 1 on the fab layer)')
    derive(os.path.join(root, 'Connector_PinHeader_2.54mm.pretty', 'PinHeader_1x02_P2.54mm_Vertical.kicad_mod'),
           'PinHeader_1x02_P2.54mm_Vertical_NoSilk',
           lambda b: True,
           '2-pin 2.54 mm header / link on a bare guard island: no silkscreen')


if __name__ == '__main__':
    main()
