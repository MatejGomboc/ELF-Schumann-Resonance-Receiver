"""Compare KiCad's exported net list with the intended connectivity."""

import os
import subprocess
import tempfile

from .sexpr import find, find1, parse


def export_netlist(sch_path, kicad_cli='kicad-cli'):
    with tempfile.TemporaryDirectory(dir='/tmp') as d:
        out = os.path.join(d, 'net.net')
        subprocess.run([kicad_cli, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                        '-o', out, os.path.abspath(sch_path)], check=True, capture_output=True)
        with open(out, encoding='utf-8') as f:
            return parse(f.read())


def exported_nets(tree):
    nets = {}
    for n in find(find1(tree, 'nets'), 'net'):
        name = str(find1(n, 'name')[1])
        nodes = {(str(find1(nd, 'ref')[1]), str(find1(nd, 'pin')[1])) for nd in find(n, 'node')}
        nets[name] = nodes
    return nets


def kicad_names(intended, exported):
    """Map each intended net to the name KiCad gives it (local nets carry the sheet path)."""
    pin_to_net = {node: name for name, nodes in exported.items() for node in nodes}
    out = {}
    for net, nodes in intended.items():
        got = {pin_to_net.get(n) for n in nodes} - {None}
        if len(got) == 1:
            out[net] = got.pop()
    return out


def record_kicad_names(json_path, intended, exported):
    """Store the design -> KiCad net-name map in design_netlist.json for the board builder."""
    import json
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    data['kicad_net_names'] = kicad_names(intended, exported)
    # pins left open on purpose: KiCad gives each its own 'unconnected-(...)' net
    data['kicad_unconnected'] = {f'{r}.{p}': name for name, nodes in exported.items()
                                 if name.startswith('unconnected-') for r, p in nodes}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)


def compare(intended, exported):
    """Return a list of human-readable problems (empty list == match)."""
    problems = []
    pin_to_net = {}
    for name, nodes in exported.items():
        for node in nodes:
            pin_to_net[node] = name
    for net, nodes in sorted(intended.items()):
        got = {pin_to_net.get(n) for n in nodes}
        if None in got:
            missing = sorted(n for n in nodes if n not in pin_to_net)
            problems.append(f'{net}: pins missing from KiCad netlist: {missing}')
            got.discard(None)
        if len(got) > 1:
            problems.append(f'{net}: split across KiCad nets {sorted(got)}')
            continue
        if not got:
            continue
        kname = got.pop()
        extra = exported[kname] - nodes
        if extra:
            problems.append(f'{net}: KiCad net {kname} has extra pins {sorted(extra)}')
        if kname.rsplit('/', 1)[-1] != net:
            problems.append(f'{net}: named "{kname}" in KiCad')
    return problems
