#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Mains copper clearance check for the PSU board (runs in KiCad's Python).

  kicad-py tools/mains_clearance.py PCB/acdc_converter/acdc_converter.kicad_pcb

Measures the smallest copper-to-copper gap on each layer (pads, tracks, vias and
filled zones) from the mains nets to:
  * each other mains net         >= 2.5 mm  (functional, L-N; the terminal's own pitch excepted)
  * PE and the PE-bonded charger >= 2.5 mm  (basic insulation, 250 V, pollution degree 2)
  * everything else              >= 6.4 mm  (buckets and receiver side: the design's own rule)
Gaps through the board (different layers) are not counted: 1.6 mm FR4 is solid insulation.
Exit status 1 if any gap is short.
"""

import sys

import pcbnew

MAINS = ('L_IN', 'AC_L', 'AC_N')
BASIC = ('PE', 'GND_C', '+15V_C')     # PE and the charger side bonded to it
LIMITS = {'mains': 2.5, 'basic': 2.5, 'other': 6.4}
SAME_PART = {'J1', 'F1', 'PS1', 'RV1'}  # pin-to-pin gaps inside one mains part are the part's own


def short(name):
    return name.rsplit('/', 1)[-1]


def items(board):
    """(net, layer, shape, owner ref or '') for every copper item."""
    out = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if pad.IsOnLayer(layer) and pad.GetNetname():
                    out.append((short(pad.GetNetname()), layer, pad.GetEffectiveShape(layer), fp.GetReference()))
    for t in board.GetTracks():
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if t.IsOnLayer(layer) and t.GetNetname():
                out.append((short(t.GetNetname()), layer, t.GetEffectiveShape(layer), ''))
    for z in board.Zones():
        if z.GetIsRuleArea() or not z.GetNetname():
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if z.IsOnLayer(layer) and z.HasFilledPolysForLayer(layer):
                out.append((short(z.GetNetname()), layer, z.GetEffectiveShape(layer), ''))
    return out


def gap(a, b, hi=8.0):
    """Smallest gap between two shapes up to hi mm (bisection on Collide)."""
    if not a.Collide(b, pcbnew.FromMM(hi)):
        return hi
    lo, h = 0.0, hi
    for _ in range(12):
        m = (lo + h) / 2
        if a.Collide(b, pcbnew.FromMM(m)):
            h = m
        else:
            lo = m
    return h


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    allitems = items(board)
    worst = {}
    for net, layer, shp, ref in allitems:
        if net not in MAINS:
            continue
        for net2, layer2, shp2, ref2 in allitems:
            if layer2 != layer or net2 == net:
                continue
            if net2 in MAINS:
                if ref and ref == ref2 and ref in SAME_PART:
                    continue
                kind = 'mains'
            else:
                kind = 'basic' if net2 in BASIC else 'other'
            g = gap(shp, shp2)
            key = (kind, net, net2)
            if g < worst.get(key, (99,))[0]:
                worst[key] = (g, pcbnew.LayerName(layer), ref, ref2)
    bad = 0
    print('mains clearance (copper to copper, same layer):')
    for (kind, net, net2), (g, layer, ref, ref2) in sorted(worst.items(), key=lambda kv: kv[1][0]):
        lim = LIMITS[kind]
        if g >= 8.0:
            continue
        flag = 'OK ' if g >= lim else 'LOW'
        bad += g < lim
        print(f'  {flag} {g:5.2f} mm  {net:5s} - {net2:22s} ({kind}, >= {lim}) {layer} {ref} {ref2}')
    print('all gaps above 8 mm otherwise;', 'PASS' if not bad else f'{bad} short gap(s)')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
