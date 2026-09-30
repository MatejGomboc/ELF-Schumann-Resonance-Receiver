"""Load KiCad 9 symbol libraries and expose pin geometry."""

import copy
import os
from dataclasses import dataclass

from .sexpr import Q, find, find1, parse

STOCK_DIR = os.environ.get('KICAD9_SYMBOL_DIR', '/usr/share/kicad/symbols')


@dataclass
class Pin:
    number: str
    name: str
    etype: str
    x: float
    y: float
    angle: int      # direction from the connection point into the body
    unit: int


class Symbol:
    def __init__(self, lib, name, node):
        self.lib = lib
        self.name = name
        self.node = node          # flattened (no 'extends') symbol s-expr
        self.pins = self._pins()
        self.is_power = bool(find(node, 'power'))

    @property
    def lib_id(self):
        return f'{self.lib}:{self.name}'

    def _pins(self):
        pins = []
        for sub in find(self.node, 'symbol'):
            # sub-symbol name: <name>_<unit>_<style>
            unit, style = (int(v) for v in sub[1].rsplit('_', 2)[-2:])
            if style not in (0, 1):
                continue
            for p in find(sub, 'pin'):
                at = find1(p, 'at')
                pins.append(Pin(
                    number=str(find1(p, 'number')[1]),
                    name=str(find1(p, 'name')[1]),
                    etype=p[1],
                    x=float(at[1]), y=float(at[2]),
                    angle=int(float(at[3])) if len(at) > 3 else 0,
                    unit=unit))
        return pins

    def pin(self, number):
        for p in self.pins:
            if p.number == str(number):
                return p
        raise KeyError(f'{self.lib_id}: no pin {number}')

    def bbox(self):
        """Rough body+pin bounding box in symbol coordinates (y up)."""
        xs, ys = [], []
        for p in self.pins:
            xs.append(p.x)
            ys.append(p.y)
        for sub in find(self.node, 'symbol'):
            for g in sub:
                if not isinstance(g, list):
                    continue
                if g[0] == 'rectangle':
                    for k in ('start', 'end'):
                        v = find1(g, k)
                        xs.append(float(v[1]))
                        ys.append(float(v[2]))
                elif g[0] == 'polyline':
                    for xy in find(find1(g, 'pts'), 'xy'):
                        xs.append(float(xy[1]))
                        ys.append(float(xy[2]))
                elif g[0] == 'circle':
                    c = find1(g, 'center')
                    r = float(find1(g, 'radius')[1])
                    xs += [float(c[1]) - r, float(c[1]) + r]
                    ys += [float(c[2]) - r, float(c[2]) + r]
        if not xs:
            return (0, 0, 0, 0)
        return (min(xs), min(ys), max(xs), max(ys))

    def embedded(self):
        """Symbol node as it must appear in a schematic's lib_symbols."""
        node = copy.deepcopy(self.node)
        node[1] = Q(self.lib_id)
        return node


class Library:
    def __init__(self, name, path=None, node=None):
        self.name = name
        if node is None:
            with open(path, encoding='utf-8') as f:
                node = parse(f.read())
        self.raw = {str(s[1]): s for s in find(node, 'symbol')}
        self._cache = {}

    def get(self, name):
        if name not in self._cache:
            self._cache[name] = Symbol(self.name, name, self._flatten(name))
        return self._cache[name]

    def _flatten(self, name):
        node = copy.deepcopy(self.raw[name])
        ext = find1(node, 'extends')
        if ext is None:
            return node
        parent = self._flatten(str(ext[1]))
        out = [x for x in parent if not (isinstance(x, list) and x[0] in ('property', 'symbol'))]
        out[1] = Q(name)
        props = {str(p[1]): p for p in find(parent, 'property')}
        for p in find(node, 'property'):
            props[str(p[1])] = p
        out += list(props.values())
        pname = str(parent[1])
        for sub in find(parent, 'symbol'):
            sub = copy.deepcopy(sub)
            sub[1] = Q(name + str(sub[1])[len(pname):])
            out.append(sub)
        return out


def derived(lib_id, new_name, pin_types, description=None, stock_dir=STOCK_DIR):
    """A stock symbol copied under a new name for the project library, with some
    pins' electrical types changed (e.g. a strap pin that is bidirectional only in
    another operating mode). Graphics and pin positions are unchanged."""
    lib, name = lib_id.split(':', 1)
    node = Library(lib, os.path.join(stock_dir, f'{lib}.kicad_sym'))._flatten(name)
    node[1] = Q(new_name)
    for sub in find(node, 'symbol'):
        sub[1] = Q(new_name + str(sub[1])[len(name):])
        for p in find(sub, 'pin'):
            if str(find1(p, 'number')[1]) in pin_types:
                p[1] = pin_types[str(find1(p, 'number')[1])]
    if description:
        for prop in find(node, 'property'):
            if str(prop[1]) == 'Description':
                prop[2] = Q(description)
    return node


class Libraries:
    """Resolves 'Lib:Name' against stock libraries plus project libraries."""

    def __init__(self, stock_dir=STOCK_DIR):
        self.stock_dir = stock_dir
        self.libs = {}

    def add(self, name, path=None, node=None):
        self.libs[name] = Library(name, path, node)

    def get(self, lib_id):
        lib, name = lib_id.split(':', 1)
        if lib not in self.libs:
            self.add(lib, os.path.join(self.stock_dir, f'{lib}.kicad_sym'))
        return self.libs[lib].get(name)
