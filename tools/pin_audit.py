#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Check every IC's pins against its manufacturer datasheet.

The datasheet side comes from Adom DS2SF (https://wiki.adom.inc/adom/adom-ds2sf), which
reads the PDF and records the page every pin was read from. Its JSON lives in
datasheets/ds2sf/<MPN>/. A hand-read override (<MPN>-hardware-mode.json and the like,
key "pins") replaces the extracted names where the part runs in another pin mode.

The design side is the symbol pins embedded in the generated .kicad_sch files (so
stock KiCad symbols are covered too) and the nets in design_netlist.json.

Two checks per pin:
  name   our symbol's pin name must match the datasheet name (aliases allowed,
         op-amp symbols with unnamed pins are inferred from pin type and position);
  net    an output must not sit on a supply or ground net, a power pin must not be on
         ground or open, a ground pin must be on ground, an N/C pin is open or guard.

  python3 tools/pin_audit.py            (stdlib only; exit 1 on any ERROR)

Extract a new part (needs the DS2SF binary and the claude CLI):
  adom-ds2sf --ai-thread "elara pin audit" extract <dir> --pdf <dir>/<MPN>.pdf \\
      --mpn <MPN> --manufacturer "<maker>" --source-tier mfr --symbol-only
then copy its *.json into datasheets/ds2sf/<MPN>/ and add the parts to PARTS below.
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from kicadgen.sexpr import parse  # noqa: E402

# board -> {reference: DS2SF part directory}
PARTS = {
    'antenna_amplifier': {'U201': 'LMP7721MA', 'U202': 'LMP7715MF', 'U203': 'LMP7715MF',
                          'U301': 'LMP7715MF', 'U302': 'PCM1804DB', 'Y402': 'SIT2001B',
                          'U101': 'ADM7150ARDZ', 'U102': 'ADM7150ARDZ', 'U401': 'CS8406'},
    'acdc_converter': {'U4': 'CD4060BM'},
}

ALIAS = {'+': 'IN+', '+IN': 'IN+', '-': 'IN-', '-IN': 'IN-', 'VOUT': 'OUT', 'OUTPUT': 'OUT',
         'N/C': 'NC', 'GRD': 'NC', 'EPAD': 'EP', 'PAD': 'EP', 'V-': 'V-', 'VSS': 'GND', 'S/M': 'S/M',
         'RESET': 'RST', 'CLR': 'RST', 'MR': 'RST', 'Φ0': 'PHI_O', 'Φ1': 'PHI_I'}
GROUND = re.compile(r'(^|[^A-Z])(A|D)?GND', re.I)


def norm_tokens(name):
    """'OE/~{ST}/NC' -> {'OE', 'ST', 'NC'}; also the whole name, aliased."""
    n = (name or '').upper().replace('~', '').replace('{', '').replace('}', '').replace(' ', '')
    n = n.replace('N/C', 'NC').replace('S/M', 'S-M').replace('H/S', 'H-S').replace('COPY/C', 'COPY-C')
    out = {ALIAS.get(t, t) for t in n.split('/') if t}
    whole = ALIAS.get(n, n)
    return out | {whole}


def lib_symbols(board):
    """lib_id -> {pin number: (name, electrical type, y)} from every sheet of a board."""
    out = {}
    for f in glob.glob(os.path.join(ROOT, 'PCB', board, '*.kicad_sch')):
        tree = parse(open(f, encoding='utf-8').read())
        libs = next((n for n in tree if isinstance(n, list) and n and n[0] == 'lib_symbols'), None)
        for sym in (libs or [])[1:]:
            pins = {}

            def walk(node):
                for c in node:
                    if isinstance(c, list) and c:
                        if c[0] == 'pin':
                            at = next(x for x in c if isinstance(x, list) and x[0] == 'at')
                            nm = next(x for x in c if isinstance(x, list) and x[0] == 'name')[1]
                            num = next(x for x in c if isinstance(x, list) and x[0] == 'number')[1]
                            pins[str(num)] = (str(nm), str(c[1]), float(at[2]))
                        elif c[0] == 'symbol':
                            walk(c)
            walk(sym)
            out[str(sym[1])] = pins
    return out


def our_name(pin, pins):
    """Symbol pin name; for unnamed op-amp pins infer OUT / V+ / V- / NC."""
    nm, et, y = pin
    if nm and nm != '~':
        return nm
    if et == 'output':
        return 'OUT'
    if et == 'power_in':
        return 'V+' if y > 0 else 'V-'
    if et in ('passive', 'no_connect'):
        return 'NC'
    return ''


def datasheet_pins(mpn):
    d = os.path.join(ROOT, 'datasheets', 'ds2sf', mpn)
    sym = json.load(open(os.path.join(d, f'{mpn}-symbol.extracted.json')))
    prov = {}
    pf = os.path.join(d, f'{mpn}-extraction.provenance.json')
    if os.path.exists(pf):
        for p in json.load(open(pf)).get('symbol', {}).get('pin_provenance', []):
            prov[str(p.get('pin_number'))] = p.get('page')
    pins = {str(p['number']): {'name': p['name'], 'type': p.get('type', ''), 'group': p.get('group', ''),
                               'page': prov.get(str(p['number']))} for p in sym['pins']}
    for f in glob.glob(os.path.join(d, f'{mpn}-*-mode.json')):        # hand-read pin-mode override
        ov = json.load(open(f))
        for num, nm in ov['pins'].items():
            pins.setdefault(num, {'type': '', 'group': ''})
            pins[num].update(name=nm, page=ov.get('page'), override=os.path.basename(f))
    return pins


def is_ground(net):
    return bool(net) and bool(GROUND.search(net))


def is_supply(net):
    return bool(net) and (net.startswith('+') or net.startswith('VIN') or net in ('VREG', 'LOAD_P'))


def audit(board, refs):
    syms = lib_symbols(board)
    comps = {c['ref']: c for c in json.load(open(os.path.join(ROOT, 'PCB', board, 'design_netlist.json')))['components']}
    errors = warnings = 0
    for ref, mpn in refs.items():
        c = comps[ref]
        ours = syms.get(c['lib_id'], {})
        ds = datasheet_pins(mpn)
        print(f'\n{board} {ref} ({c["value"]}) vs {mpn}')
        for num in sorted(set(ds) | set(ours), key=lambda n: (len(n), n)):
            d = ds.get(num)
            o = ours.get(num)
            net = c['pins'].get(num)
            msgs = []
            if d is None:
                msgs.append(('WARN', 'pin not in the datasheet extraction'))
            elif o is None:
                msgs.append(('ERROR', 'datasheet pin missing from our symbol'))
            else:
                on = our_name(o, ours)
                if on and not (norm_tokens(on) & norm_tokens(d['name'])):
                    msgs.append(('ERROR', f'name: symbol says {on!r}'))
                ty, grp = d['type'], d['group']
                if ty == 'output' and (is_ground(net) or is_supply(net)):
                    msgs.append(('ERROR', f'output pin on {net}'))
                negative = bool(norm_tokens(d['name']) & {'V-', 'VEE', 'GND'})   # single-supply V- on GND
                if grp == 'POWER' and ty == 'power_in' and (net is None or (is_ground(net) and not negative)):
                    msgs.append(('ERROR', f'power pin on {net}'))
                if grp == 'GROUND' and net is not None and not is_ground(net):
                    msgs.append(('WARN', f'ground pin on {net}'))
                if grp == 'NC' and net not in (None, 'GUARD') and not is_ground(net):
                    msgs.append(('WARN', f'N/C pin on {net}'))
            page = f'p.{d["page"]}' if d and d.get('page') else ''
            dname = d['name'] if d else '-'
            oname = our_name(o, ours) if o else '-'
            flag = ' '.join(f'{lvl}: {m}' for lvl, m in msgs) or 'ok'
            print(f'  {num:>3}  {dname:<14} {page:<6} symbol {oname:<18} net {str(net):<22} {flag}')
            errors += sum(lvl == 'ERROR' for lvl, _ in msgs)
            warnings += sum(lvl == 'WARN' for lvl, _ in msgs)
    return errors, warnings


def main():
    e = w = 0
    for board, refs in PARTS.items():
        de, dw = audit(board, refs)
        e, w = e + de, w + dw
    print(f'\npin audit: {e} errors, {w} warnings')
    sys.exit(1 if e else 0)


if __name__ == '__main__':
    main()
