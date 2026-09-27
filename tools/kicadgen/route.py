#!/usr/bin/env python3
"""Autoroute a KiCad-exported Specctra DSN with Freerouting (headless).

  route.py board.dsn board.ses --power +9V,+5VA,... [--passes 60] [--jar freerouting.jar]

Supply nets are moved into a 'power' class (0.4 mm tracks). GND is left to
the inner-layer plane: Freerouting drops vias to it.
"""

import argparse
import re
import subprocess


def split_classes(dsn, power, width_um=400, clearance_um=200):
    m = re.search(r'\(class kicad_default (.*?)\n\s*\(circuit', dsn, re.S)
    if not m:
        raise SystemExit('no kicad_default class in DSN')
    nets = m.group(1).split()
    keep = [n for n in nets if n not in power]
    pw = [n for n in nets if n in power]
    head = dsn[:m.start()]
    tail = dsn[m.end():]
    default = '(class kicad_default ' + ' '.join(keep) + '\n      (circuit'
    via = re.search(r'\(use_via "([^"]+)"\)', tail).group(1)
    power_cls = (f'(class power {" ".join(pw)}\n      (circuit\n        (use_via "{via}")\n      )\n'
                 f'      (rule\n        (width {width_um})\n        (clearance {clearance_um})\n      )\n    )\n    ')
    return head + power_cls + default + tail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dsn')
    ap.add_argument('ses')
    ap.add_argument('--power', default='')
    ap.add_argument('--passes', type=int, default=60)
    ap.add_argument('--jar', default='/root/tools/freerouting.jar')
    a = ap.parse_args()
    with open(a.dsn, encoding='utf-8') as f:
        dsn = f.read()
    if a.power:
        dsn = split_classes(dsn, set(a.power.split(',')))
        with open(a.dsn, 'w', encoding='utf-8') as f:
            f.write(dsn)
    cmd = ['java', '-jar', a.jar, '-de', a.dsn, '-do', a.ses, '-mp', str(a.passes),
           '--gui.enabled=false']
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    for line in log.splitlines():
        if any(k in line for k in ('pass', 'unrouted', 'completed', 'ERROR', 'Saving')):
            print(line[-160:])
    if r.returncode:
        raise SystemExit(r.returncode)


if __name__ == '__main__':
    main()
