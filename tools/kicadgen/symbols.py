"""Builders for simple, clean custom symbols (boxes, op-amps, transformers)."""

from .sexpr import Q

G = 2.54


def _font(hide=False, justify=None):
    eff = ['effects', ['font', ['size', 1.27, 1.27]]]
    if justify:
        eff.append(['justify', *justify.split()])
    if hide:
        eff.append(['hide', 'yes'])
    return eff


def _prop(key, val, x=0, y=0, rot=0, hide=False, justify=None):
    return ['property', Q(key), Q(val), ['at', x, y, rot], _font(hide, justify)]


def _pin(etype, x, y, angle, number, name, length=G, hidden_name=False):
    shape = 'line'
    pin = ['pin', etype, shape, ['at', x, y, angle], ['length', length],
           ['name', Q(name), _font()], ['number', Q(str(number)), _font()]]
    if hidden_name:
        pin.insert(3, ['hide', 'yes'])
    return pin


def _stroke(w=0.254):
    return ['stroke', ['width', w], ['type', 'default']]


def _header(name, ref, value, footprint, datasheet, description, keywords='',
            pin_names_offset=1.016, hide_pin_names=False, ref_at=(0, 0), val_at=(0, 0)):
    pn = ['pin_names', ['offset', pin_names_offset]]
    if hide_pin_names:
        pn.append(['hide', 'yes'])
    node = ['symbol', Q(name), pn,
            ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'],
            _prop('Reference', ref, *ref_at, justify='left'),
            _prop('Value', value, *val_at, justify='left'),
            _prop('Footprint', footprint, hide=True),
            _prop('Datasheet', datasheet, hide=True),
            _prop('Description', description, hide=True)]
    if keywords:
        node.append(_prop('ki_keywords', keywords, hide=True))
    return node


def box(name, pins, ref='U', footprint='', datasheet='', description='',
        keywords='', min_width=10.16, pin_len=G):
    """Rectangular IC symbol.

    pins: dict side -> list of (number, name, etype) or None (gap),
          side in {'L', 'R', 'T', 'B'}; lists run top->bottom / left->right.
    """
    sides = {k: pins.get(k, []) for k in 'LRTB'}
    TB = 2 * G   # wider pitch on top/bottom so power symbols do not collide
    longest = max([len(p[1]) for s in 'LR' for p in sides[s] if p] + [1])
    tb_names = max([len(p[1]) for s in 'TB' for p in sides[s] if p] + [0])
    w = max(min_width, 2 * (longest * 1.05 + 2.0), (max(len(sides['T']), len(sides['B'])) + 1) * TB)
    w = G * 2 * int(-(-w // (2 * G)))
    h = (max(len(sides['L']), len(sides['R'])) + 1) * G
    if tb_names:
        h += 2 * (tb_names * 1.05 + 1.5) * (1 if sides['T'] and sides['B'] else 0.5)
    h = G * 2 * int(-(-h // (2 * G)))
    x0, y0 = w / 2, h / 2
    node = _header(name, ref, name, footprint, datasheet, description, keywords,
                   ref_at=(-x0, y0 + 1.27), val_at=(-x0, -y0 - 1.27))
    body = ['symbol', Q(f'{name}_0_1'),
            ['rectangle', ['start', -x0, y0], ['end', x0, -y0], _stroke(), ['fill', ['type', 'background']]]]
    pinsub = ['symbol', Q(f'{name}_1_1')]

    def run(lst, start, step):
        return [(start + i * step, p) for i, p in enumerate(lst)]

    top_y = (len(sides['L']) - 1) * G / 2
    top_y = G * round(top_y / G)
    for y, p in run(sides['L'], top_y, -G):
        if p:
            pinsub.append(_pin(p[2], -x0 - pin_len, y, 0, p[0], p[1], pin_len))
    top_y = G * round((len(sides['R']) - 1) * G / 2 / G)
    for y, p in run(sides['R'], top_y, -G):
        if p:
            pinsub.append(_pin(p[2], x0 + pin_len, y, 180, p[0], p[1], pin_len))
    left_x = -G * round((len(sides['T']) - 1) * TB / 2 / G)
    for x, p in run(sides['T'], left_x, TB):
        if p:
            pinsub.append(_pin(p[2], x, y0 + pin_len, 270, p[0], p[1], pin_len))
    left_x = -G * round((len(sides['B']) - 1) * TB / 2 / G)
    for x, p in run(sides['B'], left_x, TB):
        if p:
            pinsub.append(_pin(p[2], x, -y0 - pin_len, 90, p[0], p[1], pin_len))
    node += [body, pinsub, ['embedded_fonts', 'no']]
    return node


def opamp(name, inp, inn, out, vp, vn, extra_bottom=(), extra_top=(), footprint='',
          datasheet='', description='', keywords=''):
    """Triangle op-amp: +IN top-left, -IN bottom-left, OUT right, V+ top, V- bottom.

    Each pin argument is (number, name); extra_* are (number, name, etype).
    """
    node = _header(name, 'U', name, footprint, datasheet, description, keywords,
                   hide_pin_names=False, pin_names_offset=0.254,
                   ref_at=(2.54, 7.62), val_at=(2.54, -7.62))
    body = ['symbol', Q(f'{name}_0_1'),
            ['polyline', ['pts', ['xy', -5.08, 5.08], ['xy', 5.08, 0], ['xy', -5.08, -5.08], ['xy', -5.08, 5.08]],
             _stroke(), ['fill', ['type', 'background']]]]
    pins = ['symbol', Q(f'{name}_1_1'),
            _pin('input', -7.62, 2.54, 0, inp[0], '+'),
            _pin('input', -7.62, -2.54, 0, inn[0], '-'),
            _pin('output', 7.62, 0, 180, out[0], '~'),
            _pin('power_in', -2.54, 7.62, 270, vp[0], '~', length=3.81),
            _pin('power_in', -2.54, -7.62, 90, vn[0], '~', length=3.81)]
    # extra pins start right of the supply pin and end on the sloping edge
    for i, (num, nm, et) in enumerate(extra_bottom):
        x = 2.54 * (i + 1)
        pins.append(_pin(et, x, -7.62, 90, num, '~', length=5.08 + x / 2))
    for i, (num, nm, et) in enumerate(extra_top):
        x = 2.54 * (i + 1)
        pins.append(_pin(et, x, 7.62, 270, num, '~', length=5.08 + x / 2))
    node += [body, pins, ['embedded_fonts', 'no']]
    return node


def transformer(name, footprint='', datasheet='', description=''):
    """1:1 pulse transformer: P1/P2 left, S1/S2 right (dots on pin 1 sides)."""
    node = _header(name, 'TR', name, footprint, datasheet, description,
                   'transformer pulse spdif aes', hide_pin_names=False,
                   ref_at=(-2.54, 6.35), val_at=(-2.54, -6.35))
    g = ['symbol', Q(f'{name}_0_1')]
    for cx in (-1.27, 1.27):
        for k in range(4):
            yc = 3.0 - 2.0 * k - 1.0
            # coil bump as an arc
            sgn = -1 if cx < 0 else 1
            g.append(['arc', ['start', cx, yc + 1.0], ['mid', cx + sgn * 1.0, yc], ['end', cx, yc - 1.0],
                      _stroke(), ['fill', ['type', 'none']]])
    g.append(['polyline', ['pts', ['xy', -0.254, 3.3], ['xy', -0.254, -3.3]], _stroke(), ['fill', ['type', 'none']]])
    g.append(['polyline', ['pts', ['xy', 0.254, 3.3], ['xy', 0.254, -3.3]], _stroke(), ['fill', ['type', 'none']]])
    g.append(['circle', ['center', -2.8, 3.6], ['radius', 0.3], _stroke(), ['fill', ['type', 'outline']]])
    g.append(['circle', ['center', 2.8, 3.6], ['radius', 0.3], _stroke(), ['fill', ['type', 'outline']]])
    g.append(['polyline', ['pts', ['xy', -5.08, 2.54], ['xy', -1.27, 2.54], ['xy', -1.27, 2.0]], _stroke(0), ['fill', ['type', 'none']]])
    g.append(['polyline', ['pts', ['xy', -5.08, -2.54], ['xy', -1.27, -2.54], ['xy', -1.27, -2.0]], _stroke(0), ['fill', ['type', 'none']]])
    g.append(['polyline', ['pts', ['xy', 5.08, 2.54], ['xy', 1.27, 2.54], ['xy', 1.27, 2.0]], _stroke(0), ['fill', ['type', 'none']]])
    g.append(['polyline', ['pts', ['xy', 5.08, -2.54], ['xy', 1.27, -2.54], ['xy', 1.27, -2.0]], _stroke(0), ['fill', ['type', 'none']]])
    pins = ['symbol', Q(f'{name}_1_1'),
            _pin('passive', -7.62, 2.54, 0, 1, 'P1'),
            _pin('passive', -7.62, -2.54, 0, 2, 'P2'),
            _pin('passive', 7.62, 2.54, 180, 3, 'S1'),
            _pin('passive', 7.62, -2.54, 180, 4, 'S2')]
    node[2] = ['pin_names', ['offset', 0.254], ['hide', 'yes']]
    node += [g, pins, ['embedded_fonts', 'no']]
    return node


def library(symbols):
    return ['kicad_symbol_lib', ['version', 20241209], ['generator', Q('kicadgen')],
            ['generator_version', Q('9.0')], *symbols]
