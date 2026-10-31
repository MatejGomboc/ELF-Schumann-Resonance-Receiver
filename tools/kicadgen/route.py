#!/usr/bin/env python3
"""Autoroute a KiCad-exported Specctra DSN with Freerouting (headless).

  route.py board.dsn board.ses --power +9V,+5VA,... [--passes 60] [--jar freerouting.jar]

Supply nets are moved into a 'power' class (0.4 mm tracks). GND is left to
the inner-layer plane: Freerouting drops vias to it.

  --barrier "1000:GND,LOAD_A,...:GND_C,CHG_A,..."
      keeps the first net list at least 1000 um from the second (an isolation
      barrier), as Freerouting class-to-class rules: every class holding nets of
      both sides is split per side, then each side-A class gets a class_class
      clearance against each side-B class. KiCad custom DRC rules do not reach the
      DSN, so without this the router breaks them.
"""

import argparse
import os
import re
import subprocess


def split_classes(dsn, power, width_um=400, clearance_um=200, name='power'):
    """Move the given nets out of kicad_default into their own class."""
    m = re.search(r'\(class kicad_default (.*?)\n\s*\(circuit', dsn, re.S)
    if not m:
        raise SystemExit('no kicad_default class in DSN')
    nets = m.group(1).split()
    keep = [n for n in nets if n not in power]
    pw = [n for n in nets if n in power]
    if not pw:
        return dsn
    head = dsn[:m.start()]
    tail = dsn[m.end():]
    default = '(class kicad_default ' + ' '.join(keep) + '\n      (circuit'
    via = re.search(r'\(use_via "([^"]+)"\)', tail).group(1)
    power_cls = (f'(class {name} {" ".join(pw)}\n      (circuit\n        (use_via "{via}")\n      )\n'
                 f'      (rule\n        (width {width_um})\n        (clearance {clearance_um})\n      )\n    )\n    ')
    return head + power_cls + default + tail


def classes(dsn):
    """{class name: [nets]} of the DSN's network section."""
    return {m.group(1): m.group(2).split()
            for m in re.finditer(r'\(class (\S+) (.*?)\n\s*\(circuit', dsn, re.S)}


def split_side(dsn, cls, nets, suffix):
    """Move `nets` out of class `cls` into a copy of it named cls+suffix (same rules)."""
    m = re.search(r'\(class ' + re.escape(cls) + r' (.*?)\n(\s*\(circuit.*?\n    \))', dsn, re.S)
    if not m:                    # the whole class already moved to the other side
        return dsn, None
    members = m.group(1).split()
    keep = [n for n in members if n not in nets]
    move = [n for n in members if n in nets]
    if not move:
        return dsn, None
    body = m.group(2)
    new = f'(class {cls}{suffix} {" ".join(move)}\n{body}\n    '
    old = f'(class {cls} {" ".join(keep)}\n{body}' if keep else ''
    return dsn[:m.start()] + new + old + dsn[m.end():], cls + suffix


def barrier(dsn, spec):
    clr, side_a, side_b = spec.split(':', 2)
    a_nets, b_nets = set(side_a.split(',')), set(side_b.split(','))
    a_cls, b_cls = [], []
    for cls in list(classes(dsn)):
        dsn, na = split_side(dsn, cls, a_nets, '_sa')
        if na:
            a_cls.append(na)
        dsn, nb = split_side(dsn, cls, b_nets, '_sb')
        if nb:
            b_cls.append(nb)
    rules = ''.join(f'    (class_class (classes {x} {y})\n      (rule (clearance {clr}))\n    )\n'
                    for x in a_cls for y in b_cls)
    i = dsn.index('\n  (wiring')
    j = dsn.rindex('\n  )', 0, i)            # end of the network section
    return dsn[:j] + '\n' + rules.rstrip('\n') + dsn[j:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dsn')
    ap.add_argument('ses')
    ap.add_argument('--power', default='')
    ap.add_argument('--cls', action='append', default=[],
                    help='extra class name:width_um:clearance_um:net1,net2,...')
    ap.add_argument('--barrier', action='append', default=[],
                    help='clearance_um:side A nets:side B nets (isolation barrier)')
    ap.add_argument('--passes', type=int, default=60)
    ap.add_argument('--jar', default='/root/tools/fr19.jar',
                    help='Freerouting jar; 1.9 routes and saves reliably in batch mode (needs a display)')
    a = ap.parse_args()
    with open(a.dsn, encoding='utf-8') as f:
        dsn = f.read()
    if a.power:
        dsn = split_classes(dsn, set(a.power.split(',')))
    for spec in a.cls:
        name, w, c, nets = spec.split(':', 3)
        dsn = split_classes(dsn, set(nets.split(',')), int(w), int(c), name)
    for spec in a.barrier:
        dsn = barrier(dsn, spec)
    with open(a.dsn, 'w', encoding='utf-8') as f:
        f.write(dsn)
    if 'fr19' in a.jar or '1.9' in a.jar:
        cmd = ['java', '-jar', a.jar, '-de', a.dsn, '-do', a.ses, '-mp', str(a.passes), '-mt', '1']
        os.environ.setdefault('DISPLAY', ':99')      # 1.9 opens a (virtual) window
    else:
        cmd = ['java', '-jar', a.jar, '-de', a.dsn, '-do', a.ses, '-mp', str(a.passes),
               '--gui.enabled=false']
    # stream progress (Freerouting can take many minutes on a dense board)
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        for line in proc.stdout:
            if any(k in line for k in ('pass', 'unrouted', 'ompleted', 'ERROR', 'aving', 'score')):
                print(line.rstrip()[-160:], flush=True)
    if proc.returncode:
        raise SystemExit(proc.returncode)


if __name__ == '__main__':
    main()
