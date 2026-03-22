#!/usr/bin/env python3
"""
KiCad Schematic Auto-Wirer

Parses a KiCad 9.x .kicad_sch file, computes absolute pin positions
for all placed components, and generates wire segments to connect
pins to net labels and power symbols.

Algorithm:
  1. Parse S-expression schematic
  2. Extract lib_symbols → pin offsets for each symbol type
  3. Extract placed symbols → position, rotation, reference
  4. Compute absolute pin positions using rotation transform
  5. Extract existing labels and power symbols
  6. For each label/power: find the nearest unconnected matching pin
  7. Generate orthogonal wire segments (L-route or straight)
  8. Remove old dangling wires, insert new clean wires

Usage:
  python kicad_wirer.py <schematic.kicad_sch> [--dry-run] [--report]

Author: Matej + Claude, March 2026
"""

import re
import math
import uuid
import copy
import sys
import os


# ============================================================
# S-expression parser
# ============================================================

def parse_sexpr(text):
    """Parse KiCad S-expression into nested lists."""
    tokens = _tokenize(text)
    result, _ = _parse_tokens(tokens, 0)
    return result


def _tokenize(text):
    tokens = []
    i = 0
    while i < len(text):
        c = text[i]
        if c in ' \t\n\r':
            i += 1
        elif c == '(':
            tokens.append('(')
            i += 1
        elif c == ')':
            tokens.append(')')
            i += 1
        elif c == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
            tokens.append(text[i:j+1])
            i = j + 1
        else:
            j = i
            while j < len(text) and text[j] not in ' \t\n\r()':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def _parse_tokens(tokens, pos):
    if tokens[pos] == '(':
        lst = []
        pos += 1
        while pos < len(tokens) and tokens[pos] != ')':
            if tokens[pos] == '(':
                child, pos = _parse_tokens(tokens, pos)
                lst.append(child)
            else:
                lst.append(tokens[pos])
                pos += 1
        return lst, pos + 1  # skip ')'
    else:
        return tokens[pos], pos + 1


def sexpr_find(node, tag):
    """Find all child nodes with given tag."""
    if not isinstance(node, list):
        return []
    return [child for child in node if isinstance(child, list)
            and len(child) > 0 and child[0] == tag]


def sexpr_find_one(node, tag):
    """Find first child node with given tag."""
    results = sexpr_find(node, tag)
    return results[0] if results else None


def sexpr_get_value(node, tag, default=None):
    """Get the string value of a tagged child: (tag "value") -> "value"."""
    child = sexpr_find_one(node, tag)
    if child and len(child) > 1:
        val = child[1]
        if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
            return val[1:-1]
        return val
    return default


# ============================================================
# Pin position computation
# ============================================================

def extract_lib_symbol_pins(lib_sym_node):
    """Extract pin offsets from a lib_symbol definition.

    Returns dict: pin_number -> (dx, dy, pin_angle)
    where dx, dy are in symbol-local coordinates (Y-up).
    """
    pins = {}
    # Pins are in sub-symbols like SymName_1_1
    for child in lib_sym_node:
        if isinstance(child, list) and child[0] == 'symbol':
            sym_name = child[1].strip('"') if len(child) > 1 else ""
            if '_1_1' in sym_name:  # pins are in unit 1, variant 1
                for pin_node in sexpr_find(child, 'pin'):
                    at_node = sexpr_find_one(pin_node, 'at')
                    num_node = sexpr_find_one(pin_node, 'number')
                    if at_node and num_node:
                        dx = float(at_node[1])
                        dy = float(at_node[2])
                        pin_angle = float(at_node[3]) if len(at_node) > 3 else 0
                        pin_num = num_node[1].strip('"')
                        pins[pin_num] = (dx, dy, pin_angle)
    return pins


def compute_pin_abs_position(dx, dy, sx, sy, angle_deg):
    """Compute absolute schematic position of a pin.

    dx, dy: pin offset in symbol space (Y-up)
    sx, sy: symbol placement in schematic (Y-down)
    angle_deg: symbol rotation in degrees
    """
    a = math.radians(angle_deg)
    cos_a = round(math.cos(a), 10)
    sin_a = round(math.sin(a), 10)
    abs_x = sx + (dx * cos_a - dy * sin_a)
    abs_y = sy - (dx * sin_a + dy * cos_a)
    return round(abs_x, 4), round(abs_y, 4)


GRID = 1.27  # KiCad default grid


def snap_to_grid(v, grid=GRID):
    return round(round(v / grid) * grid, 4)


# ============================================================
# Schematic analysis
# ============================================================

class SchematicAnalyzer:
    """Analyzes a KiCad schematic for pin positions and connectivity."""

    def __init__(self, sch_path):
        self.sch_path = sch_path
        with open(sch_path, 'r') as f:
            self.text = f.read()
        self.tree = parse_sexpr(self.text)
        self._parse()

    def _parse(self):
        """Parse lib_symbols, placed components, labels, power symbols."""
        self.lib_pins = {}      # lib_id -> {pin_num: (dx, dy, angle)}
        self.components = []     # [{ref, lib_id, x, y, angle, pins: {num: (ax,ay)}}]
        self.labels = []         # [{name, x, y, angle}]
        self.power_syms = []     # [{name, ref, x, y, angle}]
        self.wires = []          # [{x1, y1, x2, y2, uuid}]

        # Parse lib_symbols
        lib_syms_node = sexpr_find_one(self.tree, 'lib_symbols')
        if lib_syms_node:
            for sym_node in sexpr_find(lib_syms_node, 'symbol'):
                lib_id = sym_node[1].strip('"')
                pins = extract_lib_symbol_pins(sym_node)
                if pins:
                    self.lib_pins[lib_id] = pins

        # Parse placed symbols
        for sym_node in sexpr_find(self.tree, 'symbol'):
            lib_id_node = sexpr_find_one(sym_node, 'lib_id')
            at_node = sexpr_find_one(sym_node, 'at')
            if not lib_id_node or not at_node:
                continue

            lib_id = lib_id_node[1].strip('"')
            sx = float(at_node[1])
            sy = float(at_node[2])
            angle = float(at_node[3]) if len(at_node) > 3 else 0

            # Get reference
            ref = "?"
            for prop in sexpr_find(sym_node, 'property'):
                if len(prop) > 1 and prop[1].strip('"') == 'Reference':
                    ref = prop[2].strip('"') if len(prop) > 2 else "?"
                    break

            # Get value
            value = "?"
            for prop in sexpr_find(sym_node, 'property'):
                if len(prop) > 1 and prop[1].strip('"') == 'Value':
                    value = prop[2].strip('"') if len(prop) > 2 else "?"
                    break

            # Check if power symbol
            is_power = lib_id.startswith('power:')

            if is_power:
                self.power_syms.append({
                    'name': value,
                    'ref': ref,
                    'lib_id': lib_id,
                    'x': sx, 'y': sy, 'angle': angle,
                })
            else:
                # Compute absolute pin positions
                pins_abs = {}
                if lib_id in self.lib_pins:
                    for pin_num, (dx, dy, pa) in self.lib_pins[lib_id].items():
                        ax, ay = compute_pin_abs_position(dx, dy, sx, sy, angle)
                        pins_abs[pin_num] = (ax, ay)

                self.components.append({
                    'ref': ref,
                    'lib_id': lib_id,
                    'value': value,
                    'x': sx, 'y': sy, 'angle': angle,
                    'pins': pins_abs,
                })

        # Parse labels
        for label_node in sexpr_find(self.tree, 'label'):
            name = label_node[1].strip('"') if len(label_node) > 1 else ""
            at_node = sexpr_find_one(label_node, 'at')
            if at_node:
                lx = float(at_node[1])
                ly = float(at_node[2])
                la = float(at_node[3]) if len(at_node) > 3 else 0
                self.labels.append({'name': name, 'x': lx, 'y': ly, 'angle': la})

        # Parse wires
        for wire_node in sexpr_find(self.tree, 'wire'):
            pts_node = sexpr_find_one(wire_node, 'pts')
            if pts_node:
                xys = sexpr_find(pts_node, 'xy')
                if len(xys) >= 2:
                    x1, y1 = float(xys[0][1]), float(xys[0][2])
                    x2, y2 = float(xys[1][1]), float(xys[1][2])
                    uuid_node = sexpr_find_one(wire_node, 'uuid')
                    uid = uuid_node[1].strip('"') if uuid_node else ""
                    self.wires.append({
                        'x1': x1, 'y1': y1,
                        'x2': x2, 'y2': y2,
                        'uuid': uid,
                    })

    def print_report(self):
        """Print a human-readable report of all pin positions."""
        print(f"Schematic: {self.sch_path}")
        print(f"  Lib symbols: {len(self.lib_pins)}")
        print(f"  Components:  {len(self.components)}")
        print(f"  Labels:      {len(self.labels)}")
        print(f"  Power syms:  {len(self.power_syms)}")
        print(f"  Wires:       {len(self.wires)}")

        print(f"\n{'='*80}")
        print("COMPONENT PIN POSITIONS")
        print(f"{'='*80}")
        for comp in sorted(self.components, key=lambda c: c['ref']):
            print(f"\n  {comp['ref']} ({comp['value']}) at ({comp['x']}, {comp['y']}) "
                  f"angle={comp['angle']}°")
            print(f"  lib_id: {comp['lib_id']}")
            if comp['pins']:
                for pin_num in sorted(comp['pins'].keys(), key=lambda x: int(x) if x.isdigit() else 999):
                    ax, ay = comp['pins'][pin_num]
                    # Find pin name from lib_symbols
                    pin_name = f"pin {pin_num}"
                    print(f"    Pin {pin_num:>3s}: ({ax:>8.2f}, {ay:>8.2f})")
            else:
                print(f"    (no pins found in lib_symbols for {comp['lib_id']})")

        print(f"\n{'='*80}")
        print("LABELS")
        print(f"{'='*80}")
        for lab in sorted(self.labels, key=lambda l: l['name']):
            print(f"  {lab['name']:<20s} at ({lab['x']:>8.2f}, {lab['y']:>8.2f}) "
                  f"angle={lab['angle']}°")

        print(f"\n{'='*80}")
        print("POWER SYMBOLS")
        print(f"{'='*80}")
        for ps in sorted(self.power_syms, key=lambda p: p['name']):
            print(f"  {ps['name']:<10s} {ps['ref']:<10s} at ({ps['x']:>8.2f}, {ps['y']:>8.2f})")

    def find_component(self, ref):
        """Find a component by reference designator."""
        for comp in self.components:
            if comp['ref'] == ref:
                return comp
        return None

    def find_pin(self, ref, pin_num):
        """Get absolute position of a specific pin."""
        comp = self.find_component(ref)
        if comp and str(pin_num) in comp['pins']:
            return comp['pins'][str(pin_num)]
        return None

    def find_labels_by_name(self, name):
        """Find all labels with a given net name."""
        return [l for l in self.labels if l['name'] == name]

    def check_connectivity(self):
        """Check which pins have wires touching them and which don't."""
        print(f"\n{'='*80}")
        print("CONNECTIVITY CHECK")
        print(f"{'='*80}")

        wire_endpoints = set()
        for w in self.wires:
            wire_endpoints.add((round(w['x1'], 2), round(w['y1'], 2)))
            wire_endpoints.add((round(w['x2'], 2), round(w['y2'], 2)))

        # Also add label positions and power symbol positions
        label_points = set()
        for l in self.labels:
            label_points.add((round(l['x'], 2), round(l['y'], 2)))
        for ps in self.power_syms:
            label_points.add((round(ps['x'], 2), round(ps['y'], 2)))

        all_connection_points = wire_endpoints | label_points

        for comp in sorted(self.components, key=lambda c: c['ref']):
            if comp['ref'].startswith('#'):
                continue  # skip power refs
            unconnected = []
            connected = []
            for pin_num, (ax, ay) in comp['pins'].items():
                pt = (round(ax, 2), round(ay, 2))
                if pt in all_connection_points:
                    connected.append(pin_num)
                else:
                    unconnected.append((pin_num, ax, ay))

            if unconnected:
                print(f"\n  {comp['ref']} ({comp['value']}): "
                      f"{len(connected)} connected, {len(unconnected)} UNCONNECTED")
                for pin_num, ax, ay in unconnected:
                    print(f"    Pin {pin_num:>3s}: ({ax:>8.2f}, {ay:>8.2f}) -- NO WIRE")
            else:
                print(f"  {comp['ref']} ({comp['value']}): "
                      f"all {len(connected)} pins connected")


def generate_wire_sexpr(x1, y1, x2, y2):
    """Generate a wire S-expression string."""
    uid = str(uuid.uuid4())
    def fmt(v):
        if v == int(v):
            return str(int(v))
        return f"{v:.4f}".rstrip('0').rstrip('.')
    return (f'\t(wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}))\n'
            f'\t\t(stroke (width 0) (type solid))\n'
            f'\t\t(uuid "{uid}"))\n')


def generate_label_sexpr(name, x, y, angle=0):
    """Generate a label S-expression string."""
    uid = str(uuid.uuid4())
    def fmt(v):
        if v == int(v):
            return str(int(v))
        return f"{v:.4f}".rstrip('0').rstrip('.')
    return (f'\t(label "{name}" (at {fmt(x)} {fmt(y)} {fmt(angle)})\n'
            f'\t\t(effects (font (size 1.27 1.27)))\n'
            f'\t\t(uuid "{uid}"))\n')


def generate_power_sexpr(name, ref, x, y):
    """Generate a power symbol S-expression string."""
    uid = str(uuid.uuid4())
    def fmt(v):
        if v == int(v):
            return str(int(v))
        return f"{v:.4f}".rstrip('0').rstrip('.')
    sch_uuid = "09f45598-3e76-49a4-ba12-a3a92a2874f1"
    return (f'\t(symbol\n'
            f'\t\t(lib_id "power:{name}")\n'
            f'\t\t(at {fmt(x)} {fmt(y)} 0)\n'
            f'\t\t(unit 1)\n'
            f'\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)\n'
            f'\t\t(uuid "{uid}")\n'
            f'\t\t(property "Reference" "{ref}" (at {fmt(x)} {fmt(y-2)} 0)\n'
            f'\t\t\t(effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'\t\t(property "Value" "{name}" (at {fmt(x)} {fmt(y+3)} 0)\n'
            f'\t\t\t(effects (font (size 1.27 1.27))))\n'
            f'\t\t(instances (project "antenna_amplifier"\n'
            f'\t\t\t(path "/{sch_uuid}" (reference "{ref}") (unit 1)))))\n')


# ============================================================
# Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KiCad Schematic Analyzer / Auto-Wirer")
    parser.add_argument("schematic", help="Path to .kicad_sch file")
    parser.add_argument("--report", action="store_true",
                        help="Print full pin position report")
    parser.add_argument("--connectivity", action="store_true",
                        help="Check pin connectivity")
    parser.add_argument("--component", "-c", type=str,
                        help="Show pins for specific component (e.g. U3)")
    args = parser.parse_args()

    analyzer = SchematicAnalyzer(args.schematic)

    if args.report:
        analyzer.print_report()
    elif args.connectivity:
        analyzer.check_connectivity()
    elif args.component:
        comp = analyzer.find_component(args.component)
        if comp:
            print(f"{comp['ref']} ({comp['value']}) at ({comp['x']}, {comp['y']}) "
                  f"angle={comp['angle']}°")
            print(f"lib_id: {comp['lib_id']}")
            for pin_num in sorted(comp['pins'].keys(),
                                  key=lambda x: int(x) if x.isdigit() else 999):
                ax, ay = comp['pins'][pin_num]
                print(f"  Pin {pin_num:>3s}: ({ax:>8.2f}, {ay:>8.2f})")
        else:
            print(f"Component {args.component} not found")
    else:
        # Default: summary
        analyzer.print_report()
        analyzer.check_connectivity()


if __name__ == "__main__":
    main()
