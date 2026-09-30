"""Generate KiCad 9 hierarchical schematics from a net-list description.

Every symbol pin gets a short wire stub ending in a power symbol, a local
label (net used on one sheet) or a global label (net used on several
sheets). Connectivity is therefore exact by construction and can be
checked against the intended net list with :mod:`kicadgen.netcheck`.
"""

import math
import os
import uuid

from .sexpr import Q, dumps
from .symlib import Libraries

G = 2.54
NS = uuid.UUID('6f1c1d2e-5a1b-4c5e-9a57-e1a8a0000000')

# net name -> stock power symbol used to draw it
POWER_SYMBOLS = {
    'GND': 'power:GND',
    'PE': 'power:Earth_Protective',
}
GROUND_SYMBOLS = {'power:GND', 'power:GNDD', 'power:GNDA', 'power:Earth_Protective'}


def _uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(str(p) for p in parts)))


def _font(size=1.27, justify=None, hide=False, bold=False):
    f = ['font', ['size', size, size]]
    if bold:
        f.append(['bold', 'yes'])
    eff = ['effects', f]
    if justify:
        eff.append(['justify', *justify.split()])
    if hide:
        eff.append(['hide', 'yes'])
    return eff


def _snap(v, g=1.27):
    return round(round(v / g) * g, 4)


def is_power_net(net):
    return net in POWER_SYMBOLS or net.startswith('+') or net.startswith('-')


def is_ground_net(net):
    return is_power_net(net) and power_lib_id(net) in GROUND_SYMBOLS


def power_lib_id(net):
    if net in POWER_SYMBOLS:
        return POWER_SYMBOLS[net]
    return 'power:+5V' if not net.startswith('-') else 'power:-5V'


class Placed:
    def __init__(self, sheet, ref, sym, value, pos, rot, nets, footprint, fields, dnp,
                 stub, in_bom, on_board, unit, mirror):
        self.sheet, self.ref, self.sym, self.value = sheet, ref, sym, value
        self.pos, self.rot, self.nets = pos, rot, nets
        self.footprint, self.fields, self.dnp = footprint, fields, dnp
        self.stub, self.in_bom, self.on_board, self.unit = stub, in_bom, on_board, unit
        self.mirror = mirror
        self.uuid = _uid(sheet.project.name, 'sym', ref)

    def xform(self, x, y):
        """Symbol coordinates (y up) -> schematic coordinates (y down)."""
        if self.mirror == 'y':
            x = -x
        a = math.radians(self.rot)
        xr = x * math.cos(a) - y * math.sin(a)
        yr = x * math.sin(a) + y * math.cos(a)
        return (_snap(self.pos[0] + xr, 0.0001), _snap(self.pos[1] - yr, 0.0001))

    def pin_point(self, pin):
        return self.xform(pin.x, pin.y)

    def pin_outward(self, pin):
        """Outward direction (degrees, CCW, y up) of a pin after placement."""
        a = pin.angle + 180
        if self.mirror == 'y':
            a = 180 - a
        return (a + self.rot) % 360

    def screen_bbox(self):
        x0, y0, x1, y1 = self.sym.bbox()
        pts = [self.xform(x, y) for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)


class Sheet:
    def __init__(self, project, name, filename, title, paper='A3'):
        self.project, self.name, self.filename = project, name, filename
        self.title, self.paper = title, paper
        self.uuid = _uid(project.name, 'sheet', name)
        self.symbols = []
        self.extra = []          # free items (text, graphics)
        self.flags = []
        self.wires = []          # explicit wires: (a, b)

    # --- building -------------------------------------------------------
    def add(self, ref, lib_id, value, pos, nets, rot=0, footprint='', fields=None,
            dnp=False, stub=G, in_bom=True, on_board=True, unit=1, mirror=None, labels_only=False,
            fields_at=None, stubs=None):
        """fields_at: optional {'Reference' | 'Value': (dx, dy, justify)} relative to pos,
        for the few places where the automatic field spot collides with a neighbour."""
        sym = self.project.libs.get(lib_id)
        pins = [p for p in sym.pins if p.unit in (0, unit)]
        nets = {str(k): v for k, v in nets.items()}
        for p in pins:
            if p.number not in nets:
                if p.etype == 'no_connect':
                    nets[p.number] = None
                else:
                    raise ValueError(f'{ref}: pin {p.number} ({p.name}) not assigned')
        unknown = set(nets) - {p.number for p in pins}
        if unknown:
            raise ValueError(f'{ref}: unknown pins {sorted(unknown)}')
        pl = Placed(self, ref, sym, value, (_snap(pos[0]), _snap(pos[1])), rot, nets,
                    footprint, fields or {}, dnp, stub, in_bom, on_board, unit, mirror)
        pl.labels_only = labels_only
        pl.fields_at = fields_at or {}
        pl.bare = set()
        pl.stubs = {str(k): v for k, v in (stubs or {}).items()}   # per-pin stub length
        self.symbols.append(pl)
        return pl

    def join(self, a, pin_a, b, pin_b, label_at=None):
        """Wire two pins of the same net directly (stub end to stub end, with one bend
        if they are not aligned) and name the net once, with a horizontal label on the
        wire, instead of a label at each pin."""
        pa, pb = a.sym.pin(pin_a), b.sym.pin(pin_b)
        net = a.nets[str(pin_a)]
        if b.nets[str(pin_b)] != net:
            raise ValueError(f'join {a.ref}.{pin_a} / {b.ref}.{pin_b}: different nets')
        a.bare.add(str(pin_a))
        b.bare.add(str(pin_b))
        ea, eb = self._stub_end(a, pa), self._stub_end(b, pb)
        if ea[0] == eb[0] or ea[1] == eb[1]:
            path = [ea, eb]
        else:
            path = [ea, (ea[0], eb[1]), eb]
        for u, v in zip(path, path[1:]):
            self.wire(u, v)
        if label_at is None:
            u, v = path[0], path[1]
            label_at = (_snap((u[0] + v[0]) / 2), _snap((u[1] + v[1]) / 2))
        self.label(net, label_at, 0)

    def label(self, net, pos, angle=0):
        """Local label on an existing wire (names a net drawn with explicit wires)."""
        self.extra.append(['label', Q(net), ['at', _snap(pos[0]), _snap(pos[1]), angle], ['fields_autoplaced', 'yes'],
                           _font(1.27, 'left bottom'), ['uuid', _uid(self.uuid, 'lbl', net, pos)]])

    def wire(self, a, b):
        """Explicit wire between two points (pin points or stub ends)."""
        self.wires.append(((_snap(a[0]), _snap(a[1])), (_snap(b[0]), _snap(b[1]))))

    def flag(self, net, pos):
        """PWR_FLAG on a net (for rails fed through passives or connectors)."""
        self.flags.append((net, (_snap(pos[0]), _snap(pos[1]))))

    def text(self, s, pos, size=1.8, bold=False):
        self.extra.append(['text', Q(s), ['exclude_from_sim', 'no'], ['at', pos[0], pos[1], 0],
                           _font(size, 'left bottom', bold=bold), ['uuid', _uid(self.uuid, 'txt', s[:40], pos)]])

    def box(self, x0, y0, x1, y1, label=None):
        self.extra.append(['rectangle', ['start', x0, y0], ['end', x1, y1],
                           ['stroke', ['width', 0.2], ['type', 'dash']], ['fill', ['type', 'none']],
                           ['uuid', _uid(self.uuid, 'rect', x0, y0)]])
        if label:
            self.text(label, (x0 + 1.27, y0 + 3.2), size=2.2, bold=True)

    # --- rendering -------------------------------------------------------
    def nets_used(self):
        s = set()
        for pl in self.symbols:
            s |= {n for n in pl.nets.values() if n}
        s |= {n for n, _ in self.flags}
        return s

    def render(self, global_nets):
        proj = self.project
        items = []
        lib_ids = {}
        for pl in self.symbols:
            lib_ids[pl.sym.lib_id] = pl.sym
        # pins that land exactly on another symbol's pin connect directly
        at = {}
        for pl in self.symbols:
            for pin in pl.sym.pins:
                if pin.unit in (0, pl.unit):
                    at.setdefault(pl.pin_point(pin), []).append((pl, pin))
        touching = set()
        for pt, lst in at.items():
            if len({id(pl) for pl, _ in lst}) == 1:
                # stacked pins inside one symbol: the first gets the stub
                touching |= {(pl.ref, pin.number) for pl, pin in lst[1:]}
                continue
            if len(lst) > 1:
                nets = {pl.nets[pin.number] for pl, pin in lst}
                if len(nets) != 1 or None in nets:
                    raise ValueError(f'pins {[(pl.ref, pin.number) for pl, pin in lst]} touch at {pt} '
                                     f'but carry nets {nets}')
                touching |= {(pl.ref, pin.number) for pl, pin in lst}
        for pl in self.symbols:
            items.append(self._symbol(pl))
            bussed = set() if pl.labels_only else self._rail_buses(pl, items, global_nets, lib_ids)
            for pin in pl.sym.pins:
                if pin.unit not in (0, pl.unit) or pin.number in bussed or (pl.ref, pin.number) in touching:
                    continue
                net = pl.nets[pin.number]
                p = pl.pin_point(pin)
                if net is None:
                    items.append(['no_connect', ['at', *p], ['uuid', _uid(pl.uuid, 'nc', pin.number)]])
                    continue
                d = pl.pin_outward(pin)
                e = self._stub_end(pl, pin)
                items.append(self._wire(p, e, pl.uuid, pin.number))
                if pin.number in pl.bare:
                    continue            # joined by an explicit wire (Sheet.join)
                items += self._terminal(net, e, d, global_nets, lib_ids, f'{pl.ref}.{pin.number}',
                                        force_label=pl.labels_only)
        for a, b in self.wires:
            items.append(self._wire(a, b, 'explicit', a, b))
        for net, pos in self.flags:
            flag = proj.libs.get('power:PWR_FLAG')
            lib_ids[flag.lib_id] = flag
            ref = proj.next_ref('#FLG')
            if is_power_net(net) and not is_ground_net(net):
                # rail: symbol above, flag hanging below the wire
                items.append(self._power_inst(flag, 'PWR_FLAG', pos, 180, ref, 270))
                e, d = (pos[0], pos[1] - G), 90
            else:
                items.append(self._power_inst(flag, 'PWR_FLAG', pos, 0, ref))
                e, d = (pos[0], pos[1] + G), 270
            items.append(self._wire(pos, e, 'flag', net, pos))
            items += self._terminal(net, e, d, global_nets, lib_ids, f'flag.{net}.{pos}')
        lib_symbols = ['lib_symbols'] + [s.embedded() for _, s in sorted(lib_ids.items())]
        return self._file(lib_symbols, items + self.extra)

    def _stub_end(self, pl, pin):
        p = pl.pin_point(pin)
        d = pl.pin_outward(pin)
        dx, dy = round(math.cos(math.radians(d))), -round(math.sin(math.radians(d)))
        n = getattr(pl, 'stubs', {}).get(pin.number, pl.stub)
        return (_snap(p[0] + dx * n, 0.0001), _snap(p[1] + dy * n, 0.0001))

    def _rail_buses(self, pl, items, global_nets, lib_ids):
        """Adjacent side-facing pins on the same rail share one power symbol.

        Stub ends are joined by wire segments (with junctions), and the run is
        extended up (rails) or down (GND) to a single power symbol.
        """
        runs = {}
        for pin in pl.sym.pins:
            net = pl.nets.get(pin.number)
            if pin.unit not in (0, pl.unit) or not net or not is_power_net(net):
                continue
            d = pl.pin_outward(pin)
            if d not in (0, 180):
                continue
            e = self._stub_end(pl, pin)
            runs.setdefault((net, d, e[0]), []).append((e[1], pin))
        # every connection point of this symbol: a bus must never land on one
        occupied = set()
        for pin in pl.sym.pins:
            if pin.unit in (0, pl.unit):
                occupied.add(pl.pin_point(pin))
                occupied.add(self._stub_end(pl, pin))
        done = set()
        for (net, d, x), pts in runs.items():
            pts.sort(key=lambda t: t[0])
            # split into contiguous runs (2.54 mm pitch)
            groups, cur = [], [pts[0]]
            for a, b in zip(pts, pts[1:]):
                if abs(b[0] - a[0] - G) < 0.01:
                    cur.append(b)
                else:
                    groups.append(cur)
                    cur = [b]
            groups.append(cur)
            for grp in groups:
                if len(grp) < 2:
                    continue
                ys = [y for y, _ in grp]
                up = not is_ground_net(net)
                y_end, y_term = (ys[0], ys[0] - G) if up else (ys[-1], ys[-1] + G)
                # the power symbol needs ~2 pitches of free column beyond the run: any other
                # pin (or its stub end) of this symbol in that stretch means no room
                far = y_term - G if up else y_term + G
                own = {(x, yy) for yy in ys}
                crowded = any(abs(o[0] - x) < 6 * G and o not in own and
                              (far - 0.01 <= o[1] < y_end - 0.01 if up else y_end + 0.01 < o[1] <= far + 0.01)
                              for o in occupied)
                if crowded:
                    # joined run, one label on the first pin: no symbol dropped onto the next pins
                    for y, pin in grp:
                        items.append(self._wire(pl.pin_point(pin), (x, y), pl.uuid, pin.number))
                        done.add(pin.number)
                    for a, b in zip(ys, ys[1:]):
                        items.append(self._wire((x, a), (x, b), pl.uuid, 'bus', net, a))
                    for y in ys[1:]:
                        items.append(['junction', ['at', x, y], ['diameter', 0], ['color', 0, 0, 0, 0],
                                      ['uuid', _uid(pl.uuid, 'jc', net, y)]])
                    items += self._terminal(net, (x, ys[0]), d, global_nets, lib_ids,
                                            f'{pl.ref}.busl.{net}.{ys[0]}')
                    continue
                if any(abs(o[0] - x) < 0.01 and abs(o[1] - y_term) < 0.01 for o in occupied):
                    continue    # would land on another pin: fall back to labels
                for y, pin in grp:
                    items.append(self._wire(pl.pin_point(pin), (x, y), pl.uuid, pin.number))
                    done.add(pin.number)
                for a, b in zip(ys, ys[1:]):
                    items.append(self._wire((x, a), (x, b), pl.uuid, 'bus', net, a))
                for y in ys[1:-1]:
                    items.append(['junction', ['at', x, y], ['diameter', 0], ['color', 0, 0, 0, 0],
                                  ['uuid', _uid(pl.uuid, 'j', net, y)]])
                items.append(['junction', ['at', x, y_end], ['diameter', 0], ['color', 0, 0, 0, 0],
                              ['uuid', _uid(pl.uuid, 'je', net, y_end)]])
                items.append(self._wire((x, y_end), (x, y_term), pl.uuid, 'busend', net, y_end))
                items += self._terminal(net, (x, y_term), 90 if up else 270, global_nets, lib_ids,
                                        f'{pl.ref}.bus.{net}.{y_end}')
        # top / bottom pins on the same rail: join the stub ends with one horizontal
        # wire and give the row a single power symbol (no crowded twin symbols)
        rows = {}
        for pin in pl.sym.pins:
            net = pl.nets.get(pin.number)
            if pin.unit not in (0, pl.unit) or not net or not is_power_net(net) or pin.number in done:
                continue
            d = pl.pin_outward(pin)
            if d in (90, 270):
                e = self._stub_end(pl, pin)
                rows.setdefault((net, d, e[1]), []).append((e[0], pin))
        for (net, d, y), pts in rows.items():
            if len(pts) < 2:
                continue
            pts.sort(key=lambda t: t[0])
            xs = [x for x, _ in pts]
            between = [o for o in occupied if abs(o[1] - y) < 0.01 and xs[0] < o[0] < xs[-1]
                       and all(abs(o[0] - x) > 0.01 for x in xs)]
            if between:
                continue        # another pin's stub on the way: keep separate symbols
            for x, pin in pts:
                items.append(self._wire(pl.pin_point(pin), (x, y), pl.uuid, pin.number))
                done.add(pin.number)
            for a, b in zip(xs, xs[1:]):
                items.append(self._wire((a, y), (b, y), pl.uuid, 'row', net, a))
            for x in xs[1:-1]:
                items.append(['junction', ['at', x, y], ['diameter', 0], ['color', 0, 0, 0, 0],
                              ['uuid', _uid(pl.uuid, 'jr', net, x)]])
            xm = xs[0]
            items.append(['junction', ['at', xm, y], ['diameter', 0], ['color', 0, 0, 0, 0],
                          ['uuid', _uid(pl.uuid, 'jre', net, xm)]])
            y_term = y - G if d == 90 else y + G
            items.append(self._wire((xm, y), (xm, y_term), pl.uuid, 'rowend', net, xm))
            items += self._terminal(net, (xm, y_term), d, global_nets, lib_ids, f'{pl.ref}.row.{net}.{xm}')
        return done

    def _terminal(self, net, e, d, global_nets, lib_ids, key, force_label=False):
        proj = self.project
        if is_power_net(net) and d in (90, 270) and not force_label:
            sym = proj.libs.get(power_lib_id(net))
            lib_ids[sym.lib_id] = sym
            # GND-style symbols hang downwards (270), rails point upwards (90)
            default = 270 if sym.lib_id in GROUND_SYMBOLS else 90
            rot = (d - default) % 360
            return [self._power_inst(sym, net, e, rot, proj.next_ref('#PWR'), d)]
        angle = {0: 0, 90: 90, 180: 180, 270: 270}[d]
        just = 'left' if angle in (0, 90) else 'right'
        if net in global_nets or is_power_net(net):
            # rails on side-facing pins: a global label joins the power net cleanly
            return [['global_label', Q(net), ['shape', 'passive'], ['at', *e, angle],
                     ['fields_autoplaced', 'yes'], _font(1.27, just),
                     ['uuid', _uid(self.uuid, 'gl', key)],
                     ['property', Q('Intersheetrefs'), Q('${INTERSHEET_REFS}'), ['at', *e, angle],
                      _font(1.27, just, hide=True)]]]
        return [['label', Q(net), ['at', *e, angle], ['fields_autoplaced', 'yes'],
                 _font(1.27, f'{just} bottom'), ['uuid', _uid(self.uuid, 'lb', key)]]]

    def _wire(self, a, b, *key):
        return ['wire', ['pts', ['xy', *a], ['xy', *b]], ['stroke', ['width', 0], ['type', 'default']],
                ['uuid', _uid(self.uuid, 'w', *key)]]

    def _instances(self, ref, unit=1):
        return ['instances', ['project', Q(self.project.name),
                              ['path', Q(f'/{self.project.root_uuid}/{self.uuid}'),
                               ['reference', Q(ref)], ['unit', unit]]]]

    def _power_inst(self, sym, value, pos, rot, ref, d=90):
        uid = _uid(self.uuid, 'pwr', ref)
        # value text sits beyond the symbol graphic, along the stub direction
        # the protective-earth symbol is taller than GND: push its value clear of it
        off = 7.4 if sym.lib_id == 'power:Earth_Protective' else 4.3
        vpos = (_snap(pos[0] + off * math.cos(math.radians(d)), 0.01),
                _snap(pos[1] - off * math.sin(math.radians(d)), 0.01))
        hide_val = value == 'PWR_FLAG'
        node = ['symbol', ['lib_id', Q(sym.lib_id)], ['at', *pos, rot], ['unit', 1],
                ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
                ['uuid', uid],
                ['property', Q('Reference'), Q(ref), ['at', *pos, 0], _font(hide=True)],
                ['property', Q('Value'), Q(value), ['at', *vpos, 0], _font(hide=hide_val)],
                ['property', Q('Footprint'), Q(''), ['at', *pos, 0], _font(hide=True)],
                ['property', Q('Datasheet'), Q(''), ['at', *pos, 0], _font(hide=True)],
                ['property', Q('Description'), Q(''), ['at', *pos, 0], _font(hide=True)],
                ['pin', Q('1'), ['uuid', _uid(uid, 'p1')]],
                self._instances(ref)]
        return node

    def _symbol(self, pl):
        x0, y0, x1, y1 = pl.screen_bbox()
        X, Y = pl.pos
        # fields rotate with the symbol: compensate so text always reads horizontally
        ang = 90 if pl.rot in (90, 270) else 0
        pins = [p for p in pl.sym.pins if p.unit in (0, pl.unit)]
        has_top = any(pl.pin_outward(p) == 90 for p in pins)
        if x1 - x0 < 6:
            # small vertical part (R, C, LED ...): fields to the right
            ref_at = (_snap(x1 + 0.8, 0.01), _snap(Y - 1.0, 0.01), ang, 'left')
            val_at = (_snap(x1 + 0.8, 0.01), _snap(Y + 1.6, 0.01), ang, 'left')
        elif y1 - y0 < 6:
            # small horizontal part: reference above, value below
            ref_at = (X, _snap(y0 - 1.5, 0.01), ang, None)
            val_at = (X, _snap(y1 + 2.5, 0.01), ang, None)
        elif has_top:
            ref_at = (_snap(x1 + 1.0, 0.01), _snap(y0 + 1.5, 0.01), ang, 'left')
            val_at = (_snap(x1 + 1.0, 0.01), _snap(y0 + 3.8, 0.01), ang, 'left')
        else:
            # connectors, switches, transformers: stacked above the body
            ref_at = (_snap(x0, 0.01), _snap(y0 - 4.0, 0.01), ang, 'left')
            val_at = (_snap(x0, 0.01), _snap(y0 - 1.5, 0.01), ang, 'left')
        for name, (dx, dy, just) in getattr(pl, 'fields_at', {}).items():
            spot = (_snap(X + dx, 0.01), _snap(Y + dy, 0.01), ang, just)
            if name == 'Reference':
                ref_at = spot
            else:
                val_at = spot
        props = [
            ['property', Q('Reference'), Q(pl.ref), ['at', *ref_at[:3]], _font(1.27, ref_at[3])],
            ['property', Q('Value'), Q(pl.value), ['at', *val_at[:3]], _font(1.27, val_at[3])],
            ['property', Q('Footprint'), Q(pl.footprint), ['at', X, Y, 0], _font(hide=True)],
            ['property', Q('Datasheet'), Q(pl.fields.get('Datasheet', '~')), ['at', X, Y, 0], _font(hide=True)],
            ['property', Q('Description'), Q(pl.fields.get('Description', '')), ['at', X, Y, 0], _font(hide=True)],
        ]
        for k, v in pl.fields.items():
            if k in ('Datasheet', 'Description'):
                continue
            props.append(['property', Q(k), Q(str(v)), ['at', X, Y, 0], _font(hide=True)])
        node = ['symbol', ['lib_id', Q(pl.sym.lib_id)], ['at', X, Y, pl.rot]]
        if pl.mirror:
            node.append(['mirror', pl.mirror])
        node += [['unit', pl.unit], ['exclude_from_sim', 'no'],
                 ['in_bom', 'yes' if pl.in_bom and not pl.dnp else 'no'],
                 ['on_board', 'yes' if pl.on_board else 'no'], ['dnp', 'yes' if pl.dnp else 'no'],
                 ['uuid', pl.uuid], *props]
        for pin in pl.sym.pins:
            if pin.unit in (0, pl.unit):
                node.append(['pin', Q(pin.number), ['uuid', _uid(pl.uuid, 'pin', pin.number)]])
        node.append(self._instances(pl.ref, pl.unit))
        return node

    def _file(self, lib_symbols, items):
        return ['kicad_sch', ['version', 20250114], ['generator', Q('eeschema')],
                ['generator_version', Q('9.0')], ['uuid', self.uuid], ['paper', Q(self.paper)],
                self.project.title_block(self.title), lib_symbols, *items,
                ['embedded_fonts', 'no']]


class Project:
    def __init__(self, name, directory, title, rev='0.2', company='', comments=(), date=''):
        self.name, self.dir = name, directory
        self.title, self.rev, self.company, self.comments, self.date = title, rev, company, comments, date
        self.root_notes = []      # text lines under the sheet row on the root page
        self.root_arrows = None   # arrows between the first k sheets (default: all)
        self.libs = Libraries()
        self.sheets = []
        self.root_uuid = _uid(name, 'root')
        self._refs = {}

    def next_ref(self, prefix):
        self._refs[prefix] = self._refs.get(prefix, 0) + 1
        return f'{prefix}{self._refs[prefix]:03d}'

    def sheet(self, name, filename, title, paper='A3'):
        s = Sheet(self, name, filename, title, paper)
        self.sheets.append(s)
        return s

    def title_block(self, sheet_title):
        tb = ['title_block', ['title', Q(f'{self.title} - {sheet_title}' if sheet_title else self.title)]]
        if self.date:
            tb.append(['date', Q(self.date)])
        tb.append(['rev', Q(self.rev)])
        if self.company:
            tb.append(['company', Q(self.company)])
        for i, c in enumerate(self.comments, 1):
            tb.append(['comment', i, Q(c)])
        return tb

    def netlist(self):
        """{net: set((ref, pin))} of the intended connectivity."""
        nets = {}
        for s in self.sheets:
            for pl in s.symbols:
                for pin, net in pl.nets.items():
                    if net:
                        nets.setdefault(net, set()).add((pl.ref, pin))
        return nets

    def components(self):
        return [pl for s in self.sheets for pl in s.symbols]

    def write(self):
        count = {}
        for s in self.sheets:
            for n in s.nets_used():
                count[n] = count.get(n, 0) + 1
        global_nets = {n for n, c in count.items() if c > 1 and not is_power_net(n)}
        self._refs = {}
        for s in self.sheets:
            with open(os.path.join(self.dir, s.filename), 'w', encoding='utf-8') as f:
                f.write(dumps(s.render(global_nets)) + '\n')
        root = ['kicad_sch', ['version', 20250114], ['generator', Q('eeschema')],
                ['generator_version', Q('9.0')], ['uuid', self.root_uuid], ['paper', Q('A4')],
                self.title_block(''), ['lib_symbols']]
        n = len(self.sheets)
        w, gap = 55.88, 12.7
        x0 = 20.32
        for i, s in enumerate(self.sheets):
            # one row, in signal-flow order, with an arrow to the next sheet
            x, y = x0 + i * (w + gap), 45.72
            root.append(['sheet', ['at', x, y], ['size', w, 25.4], ['exclude_from_sim', 'no'],
                         ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
                         ['fields_autoplaced', 'yes'],
                         ['stroke', ['width', 0.1524], ['type', 'solid']], ['fill', ['color', 0, 0, 0, 0]],
                         ['uuid', s.uuid],
                         ['property', Q('Sheetname'), Q(s.title), ['at', x, y - 0.7, 0], _font(1.27, 'left bottom')],
                         ['property', Q('Sheetfile'), Q(s.filename), ['at', x, y + 26.0, 0], _font(1.27, 'left top')],
                         ['instances', ['project', Q(self.name), ['path', Q(f'/{self.root_uuid}'), ['page', Q(str(i + 2))]]]]])
            if i < (self.root_arrows if self.root_arrows is not None else n - 1):
                ya, xa, xb = y + 12.7, x + w + 1.27, x + w + gap - 1.27
                for pts in (((xa, ya), (xb, ya)), ((xb - 1.5, ya - 1.0), (xb, ya), (xb - 1.5, ya + 1.0))):
                    root.append(['polyline', ['pts', *[['xy', *p] for p in pts]],
                                 ['stroke', ['width', 0.254], ['type', 'default']], ['fill', ['type', 'none']],
                                 ['uuid', _uid(self.root_uuid, 'arrow', i, len(pts))]])
        for i, line in enumerate(self.root_notes):
            root.append(['text', Q(line), ['exclude_from_sim', 'no'], ['at', x0, 95.25 + i * 6.35, 0],
                         _font(1.8, 'left bottom'), ['uuid', _uid(self.root_uuid, 'note', i)]])
        root.append(['sheet_instances', ['path', Q('/'), ['page', Q('1')]]])
        root.append(['embedded_fonts', 'no'])
        with open(os.path.join(self.dir, f'{self.name}.kicad_sch'), 'w', encoding='utf-8') as f:
            f.write(dumps(root) + '\n')
