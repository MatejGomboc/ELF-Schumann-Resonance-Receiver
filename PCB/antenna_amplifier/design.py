#!/usr/bin/env python3
"""ELARA antenna amplifier -- single source of truth for the schematic.

Running this script regenerates:
  antenna_amplifier.kicad_sch + power/frontend/adc/digital sub-sheets
  antenna_amplifier.kicad_sym  (project symbols)
  sym-lib-table
  design_netlist.json          (consumed by the PCB generator)
and then checks KiCad's own net-list export against the intended nets.

Usage:  .venv/bin/python PCB/antenna_amplifier/design.py [--no-check]
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))

from kicadgen import symbols  # noqa: E402
from kicadgen.schematic import Project  # noqa: E402
from kicadgen.sexpr import dumps  # noqa: E402

NAME = 'antenna_amplifier'
LIB = NAME

# ---------------------------------------------------------------------------
# Project symbols
# ---------------------------------------------------------------------------
TI = 'https://www.ti.com/lit/ds/symlink/'
ADI = 'https://www.analog.com/media/en/technical-documentation/data-sheets/'


def project_symbols():
    return [
        symbols.opamp('LMP7721', ('1', '+'), ('3', '-'), ('6', 'OUT'), ('8', 'V+'), ('4', 'V-'),
                      extra_bottom=[('2', 'GRD', 'passive'), ('7', 'GRD', 'passive')], extra_top=[('5', 'NC', 'no_connect')],
                      footprint='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', datasheet=TI + 'lmp7721.pdf',
                      description='3 fA input bias current electrometer op-amp, guard pins 2 and 7',
                      keywords='electrometer opamp femtoampere'),
        symbols.opamp('LMP7715', ('3', '+'), ('4', '-'), ('1', 'OUT'), ('5', 'V+'), ('2', 'V-'),
                      footprint='Package_TO_SOT_SMD:SOT-23-5', datasheet=TI + 'lmp7715.pdf',
                      description='Precision CMOS op-amp, 17 MHz, SOT-23-5', keywords='opamp'),
        symbols.box('PCM1804', {
            'L': [('4', 'VINL+', 'input'), ('5', 'VINL-', 'input'), ('3', 'VCOML', 'passive'),
                  ('1', 'VREFL', 'passive'), None,
                  ('25', 'VINR+', 'input'), ('24', 'VINR-', 'input'), ('26', 'VCOMR', 'passive'),
                  ('28', 'VREFR', 'passive'), None,
                  ('6', 'FMT0', 'input'), ('7', 'FMT1', 'input'), ('8', 'S/M', 'input'),
                  ('9', 'OSR0', 'input'), ('10', 'OSR1', 'input'), ('11', 'OSR2', 'input'),
                  ('12', 'BYPAS', 'input'), ('19', '~{RST}', 'input')],
            'R': [('18', 'SCKI', 'input'), None, ('16', 'BCK', 'bidirectional'),
                  ('17', 'LRCK', 'bidirectional'), ('15', 'DATA', 'output'), None,
                  ('21', 'OVFL', 'output'), ('20', 'OVFR', 'output')],
            'T': [('22', 'VCC', 'power_in'), None, None, ('14', 'VDD', 'power_in')],
            'B': [('2', 'AGNDL', 'power_in'), ('23', 'AGND', 'power_in'), ('27', 'AGNDR', 'power_in'),
                  ('13', 'DGND', 'power_in')]},
            footprint='Package_SO:SSOP-28_5.3x10.2mm_P0.65mm', datasheet=TI + 'pcm1804.pdf',
            description='24-bit 192 kHz stereo delta-sigma ADC, differential inputs', keywords='adc audio'),
        symbols.box('ADM7150', {
            'L': [('8', 'VIN', 'power_in'), ('7', 'EN', 'input')],
            'R': [('2', 'VOUT', 'power_out'), ('1', 'VREG', 'passive'), ('3', 'BYP', 'passive'),
                  ('6', 'REF', 'passive'), ('5', 'REF_SENSE', 'input')],
            'B': [('4', 'GND', 'power_in'), ('9', 'EP', 'power_in')]},
            footprint='Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm',
            datasheet=ADI + 'adm7150.pdf', description='800 mA ultralow-noise LDO, fixed output',
            keywords='ldo regulator low noise'),
        symbols.box('MEMS_OSC', {
            'L': [('1', 'OE', 'input')], 'R': [('3', 'OUT', 'output')],
            'T': [('4', 'VDD', 'power_in')], 'B': [('2', 'GND', 'power_in')]},
            ref='Y', footprint='Oscillator:Oscillator_SMD_SiT_PQFN-4Pin_3.2x2.5mm',
            description='MEMS oscillator, 4-pin 3.2x2.5 mm', keywords='oscillator mems clock'),
        symbols.transformer('XFMR_1to1', footprint='elara:Transformer_Pulse_4Pin_W7.62mm',
                            description='1:1 digital-audio pulse transformer (S/PDIF, AES3)'),
    ]


# ---------------------------------------------------------------------------
# Parts catalogue: key -> (lib_id, footprint, fields)
# ---------------------------------------------------------------------------
def tf(mpn, desc):
    return {'Manufacturer': 'Panasonic', 'MPN': mpn, 'Description': desc}


def mur(mpn, desc):
    return {'Manufacturer': 'Murata', 'MPN': mpn, 'Description': desc}


R0603 = 'Resistor_SMD:R_0603_1608Metric'
R0805 = 'Resistor_SMD:R_0805_2012Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'

# thin-film resistors, Panasonic ERA series (0.1 %, 25 ppm/K) unless noted
RES = {
    '10': (R0805, tf('ERA-6AEB100V', 'Thin film 10R 0.1% 0805')),
    '33': (R0603, tf('ERA-3AEB330V', 'Thin film 33R 0.1% 0603')),
    '39': (R0603, tf('ERA-3AEB390V', 'Thin film 39R 0.1% 0603')),
    '90.9': (R0603, tf('ERA-3AEB90R9V', 'Thin film 90R9 0.1% 0603')),
    '249': (R0603, tf('ERA-3AEB2490V', 'Thin film 249R 0.1% 0603')),
    '470': (R0603, tf('ERA-3AEB471V', 'Thin film 470R 0.1% 0603')),
    '1k': (R0603, tf('ERA-3AEB102V', 'Thin film 1k 0.1% 0603')),
    '1k_prec': (R0805, tf('ERA-6AEB102V', 'Thin film 1k 0.1% 25ppm 0805 (Rg)')),
    '2.2k': (R0603, tf('ERA-3AEB222V', 'Thin film 2k2 0.1% 0603')),
    '10k': (R0603, tf('ERA-3AEB103V', 'Thin film 10k 0.1% 0603')),
    '10k_prec': (R0805, tf('ERA-6AEB103V', 'Thin film 10k 0.1% 25ppm 0805 (R_AA)')),
    '47k_prec': (R0805, tf('ERA-6AEB473V', 'Thin film 47k 0.1% 25ppm 0805')),
    '47k_div': (R0603, tf('ERA-3VRW4702V', 'Thin film 47k 0.05% 10ppm 0603 (bias divider)')),
    '100k_prec': (R0805, tf('ERA-6AEB104V', 'Thin film 100k 0.1% 25ppm 0805 (Rf)')),
    '100': (R0603, tf('ERA-3AEB101V', 'Thin film 100R 0.1% 0603')),
    '0': (R0603, {'Manufacturer': 'Panasonic', 'MPN': 'ERJ-3GEY0R00V', 'Description': 'Jumper 0R 0603'}),
}

CAP = {
    '100n': (C0603, mur('GRM188R71H104KA93D', 'MLCC 100n 50V X7R 0603 (decoupling)')),
    '1u': (C0603, mur('GRM188R71E105KA12D', 'MLCC 1u 25V X7R 0603 (decoupling)')),
    '10u': (C1206, mur('GRM31CR71E106KA12L', 'MLCC 10u 25V X7R 1206 (decoupling)')),
    '22u': (C1206, mur('GRM31CR61C226ME15L', 'MLCC 22u 16V X5R 1206 (decoupling)')),
    '10n_dnp': (C0603, mur('GRM188R72A103KA01D', 'MLCC 10n 100V X7R 0603 (shield RF bond, DNP)')),
    '100n_c0g': (C1206, mur('GRM31C5C1H104JA01L', 'MLCC 100n 50V C0G 1206 (signal path)')),
    '220p_c0g': (C0603, mur('GRM1885C1H221JA01D', 'MLCC 220p 50V C0G 0603 (guard stability)')),
    '2.7n_c0g': (C0603, mur('GRM1885C1H272JA01D', 'MLCC 2n7 50V C0G 0603 (ADC charge reservoir)')),
    '15n_c0g': (C0805, mur('GRM2195C1H153JA01D', 'MLCC 15n 50V C0G 0805 (Cf, signal path)')),
    '100u_film': ('Capacitor_THT:C_Rect_L41.5mm_W35.0mm_P37.50mm_MKS4',
                  {'Manufacturer': 'WIMA', 'MPN': 'MKS4 100uF 63V PCM37.5',
                   'Description': 'Film 100u 63V PET, PCM 37.5 mm (Cg)'}),
    '10u_film': ('Capacitor_THT:C_Rect_L26.5mm_W11.5mm_P22.50mm_MKS4',
                 {'Manufacturer': 'WIMA', 'MPN': 'MKS4 10uF 63V PCM22.5',
                  'Description': 'Film 10u 63V PET, PCM 22.5 mm (C_out)'}),
    '100u_el': ('Capacitor_THT:CP_Radial_D6.3mm_P2.50mm',
                {'Manufacturer': 'Panasonic', 'MPN': 'EEU-FR1E101',
                 'Description': 'Electrolytic 100u 25V low-ESR, D6.3 P2.5'}),
    '4700u_el': ('Capacitor_THT:CP_Radial_D16.0mm_P7.50mm',
                 {'Manufacturer': 'Panasonic', 'MPN': 'EEU-FR1C472',
                  'Description': 'Electrolytic 4700u 16V, D16 P7.5 (bias divider filter)'}),
}


class Refs:
    """Per-sheet annotation: power 1xx, front end 2xx, ADC 3xx, digital 4xx."""

    def __init__(self):
        self.n, self.base = {}, 100

    def sheet(self, base):
        self.n, self.base = {}, base

    def __call__(self, prefix):
        self.n[prefix] = self.n.get(prefix, 0) + 1
        return f'{prefix}{self.base + self.n[prefix]}'


ref = Refs()


def R(sh, value, pos, a, b, rot=0, role='', key=None, dnp=False):
    fp, f = RES[key or value]
    fields = dict(f)
    if role:
        fields['Role'] = role
    shown = value.replace('_prec', '').replace('_div', '')
    return sh.add(ref('R'), 'Device:R', shown, pos, {1: a, 2: b}, rot=rot, footprint=fp,
                  fields=fields, dnp=dnp)


def C(sh, key, pos, a, b, rot=0, role='', dnp=False):
    fp, f = CAP[key]
    fields = dict(f)
    if role:
        fields['Role'] = role
    value = key.split('_')[0]
    lib = 'Device:C_Polarized' if key.endswith('_el') else 'Device:C'
    return sh.add(ref('C'), lib, value, pos, {1: a, 2: b}, rot=rot, footprint=fp, fields=fields, dnp=dnp)


def decap(sh, x, y, rail, keys=('100n',), dx=12.7):
    """Row of vertical decoupling caps from rail (top) to GND (bottom)."""
    for i, k in enumerate(keys):
        C(sh, k, (x + i * dx, y), rail, 'GND')


# ---------------------------------------------------------------------------
# Sheets  (all coordinates in mm on the 1.27 mm grid; blocks are dashed boxes)
# ---------------------------------------------------------------------------
def sheet_power(p):
    ref.sheet(100)
    sh = p.sheet('power', 'power.kicad_sch', 'Power input and regulators', paper='A4')
    sh.box(15, 20, 95, 80, '9 V INPUT')
    sh.add(ref('J'), 'Connector_Generic:Conn_01x02', 'PWR_IN 9V', (25.4, 38.1),
           {1: 'VIN_RAW', 2: 'GND'}, mirror='y',
           footprint='Connector_Molex:Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal',
           fields={'Manufacturer': 'Molex', 'MPN': '43650-0200',
                   'Description': 'Micro-Fit 3.0 2-pin right-angle header, 9 V DC in (from PSU or battery)'})
    sh.add(ref('D'), 'Diode:SS34', 'SS34', (48.26, 38.1), {1: '+9V', 2: 'VIN_RAW'}, rot=180,
           footprint='Diode_SMD:D_SMA',
           fields={'Manufacturer': 'Vishay', 'MPN': 'SS34-E3/57T', 'Description': 'Schottky 3 A 40 V, reverse-polarity protection'})
    sh.add(ref('D'), 'Diode:SMAJ15A', 'SMAJ15A', (55.88, 62.23), {1: '+9V', 2: 'GND'}, rot=270,
           footprint='Diode_SMD:D_SMA',
           fields={'Manufacturer': 'Littelfuse', 'MPN': 'SMAJ15A', 'Description': 'TVS 15 V unidirectional, input surge clamp'})
    C(sh, '100u_el', (68.58, 62.23), '+9V', 'GND', role='input bulk')
    C(sh, '10u', (78.74, 62.23), '+9V', 'GND')
    sh.flag('+9V', (86.36, 36.83))
    sh.flag('GND', (86.36, 69.85))

    for (x0, rail, sfx, part, label) in ((100, '+5VA', 'A', 'ADM7150ARDZ-5.0-R7', '+5 V ANALOG'),
                                          (190, '+3V3', 'D', 'ADM7150ARDZ-3.3-R7', '+3.3 V DIGITAL')):
        sh.box(x0, 20, x0 + 87, 80, f'{label}  ADM7150')
        sh.add(ref('U'), f'{LIB}:ADM7150', part.replace('-R7', ''), (x0 + 22.86, 45.72),
               {8: '+9V', 7: '+9V', 2: rail, 1: f'VREG_{sfx}', 3: f'BYP_{sfx}', 6: f'REF_{sfx}',
                5: f'REF_{sfx}', 4: 'GND', 9: 'GND'},
               footprint='Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm',
               fields={'Manufacturer': 'Analog Devices', 'MPN': part,
                       'Description': f'Ultralow-noise LDO (1.6 uV rms), {rail} rail'})
        for i, (net, key, role) in enumerate(((('+9V', '10u', 'LDO input')), (f'VREG_{sfx}', '10u', 'VREG'),
                                              (rail, '10u', 'LDO output'), (f'BYP_{sfx}', '1u', 'BYP'),
                                              (f'REF_{sfx}', '1u', 'REF'))):
            C(sh, key, (x0 + 43.18 + i * 10.16, 64.77), net, 'GND', role=role)

    sh.box(100, 85, 187, 125, 'PREAMP RAIL FILTER')
    R(sh, '10', (116.84, 100.33), '+5VA', '+5V_PRE', rot=90, role='isolates preamp from ADC supply current')
    C(sh, '22u', (144.78, 107.95), '+5V_PRE', 'GND')
    C(sh, '100n', (152.4, 107.95), '+5V_PRE', 'GND')
    sh.flag('+5V_PRE', (166.37, 105.41))

    sh.text('No power LED: this board may run from a battery (overload LED D301 only lights on clipping).',
            (190, 90), size=1.5)

    sh.text('Budget: ~40 mA on +5VA (PCM1804 VCC, preamp, ADC driver), ~45 mA on +3V3.', (15, 135))
    sh.text('ADM7150: REF_SENSE tied to REF (fixed output), EN tied to VIN.', (15, 140))
    sh.text('No switching regulators on this board.', (15, 145))
    return sh


def sheet_frontend(p):
    ref.sheet(200)
    sh = p.sheet('frontend', 'frontend.kicad_sch', 'Electrometer front end', paper='A4')
    sh.box(15, 20, 70, 85, 'INPUT  (comp. 1)')
    sh.add(ref('J'), 'Connector_Generic:Conn_01x01', 'FILT_IN', (27.94, 38.1), {1: 'IN_P'}, mirror='y',
           footprint='elara:Turret_PTFE_D3.0mm_Drill1.6mm',
           fields={'Manufacturer': '-', 'MPN': 'PTFE press-fit turret or direct wire',
                   'Description': 'Input from air-mounted RC filter (node 2), enters from the PCB bottom'})
    sh.add(ref('J'), 'Connector_Generic:Conn_01x02', 'BIAS', (27.94, 55.88),
           {1: 'ANT_BIAS', 2: 'IN_P'}, mirror='y',
           footprint='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
           fields={'Manufacturer': 'Sullins', 'MPN': 'PRPC002SAAN-RC + SPC02SYAN shunt',
                   'Description': 'Bias link: shunt = reset only; for operation fit a 1-100 G glass '
                                  'resistor (see docs, ion current)'})
    sh.text('IN_P: guard on all layers,', (17, 72), size=1.5)
    sh.text('no mask, PTFE turret.', (17, 76), size=1.5)
    sh.text('J2: fit G-ohm bias R', (17, 80), size=1.5)

    sh.box(75, 20, 185, 95, 'ELECTROMETER  G = 101')
    sh.add(ref('U'), f'{LIB}:LMP7721', 'LMP7721', (104.14, 45.72),
           {1: 'IN_P', 3: 'IN_N', 6: 'PREAMP_OUT', 8: '+5V_PRE', 4: 'GND', 2: 'GUARD', 7: 'GUARD'},
           footprint='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
           fields={'Manufacturer': 'Texas Instruments', 'MPN': 'LMP7721MA/NOPB',
                   'Description': 'Electrometer op-amp, 3 fA bias, guard pins 2/7'})
    R(sh, '100k_prec', (147.32, 30.48), 'IN_N', 'PREAMP_OUT', rot=90, role='Rf', key='100k_prec')
    C(sh, '15n_c0g', (147.32, 43.18), 'IN_N', 'PREAMP_OUT', rot=90, role='Cf')
    R(sh, '1k_prec', (85.09, 78.74), 'IN_N', 'CG', role='Rg', key='1k_prec')
    C(sh, '100u_film', (97.79, 78.74), 'CG', 'GND', role='Cg (DC block to GND)')
    decap(sh, 158.75, 78.74, '+5V_PRE', ('100n', '10u'))

    sh.box(190, 20, 282, 70, 'GUARD DRIVER')
    sh.add(ref('U'), f'{LIB}:LMP7715', 'LMP7715', (208.28, 43.18),
           {3: 'IN_N', 4: 'GUARD_DRV', 1: 'GUARD_DRV', 5: '+5V_PRE', 2: 'GND'},
           footprint='Package_TO_SOT_SMD:SOT-23-5',
           fields={'Manufacturer': 'Texas Instruments', 'MPN': 'LMP7715MF/NOPB',
                   'Description': 'Guard ring buffer (senses IN-, tracks IN+)'})
    R(sh, '470', (251.46, 43.18), 'GUARD_DRV', 'GUARD', rot=90, role='guard isolation')
    C(sh, '220p_c0g', (262.89, 55.88), 'GUARD', 'GND', role='guard buffer stability (PM 43 -> 56 deg)')
    decap(sh, 271.78, 50.8, '+5V_PRE')

    sh.box(15, 100, 185, 160, 'ANTENNA BIAS  2.5 V')
    R(sh, '47k_div', (27.94, 118.11), '+5V_PRE', 'BIAS_DIV', key='47k_div')
    R(sh, '47k_div', (27.94, 147.32), 'BIAS_DIV', 'GND', key='47k_div')
    C(sh, '4700u_el', (40.64, 144.78), 'BIAS_DIV', 'GND', role='divider noise filter, 1.4 mHz')
    sh.add(ref('U'), f'{LIB}:LMP7715', 'LMP7715', (82.55, 127),
           {3: 'BIAS_DIV', 4: 'BIAS_BUF', 1: 'BIAS_BUF', 5: '+5V_PRE', 2: 'GND'},
           footprint='Package_TO_SOT_SMD:SOT-23-5',
           fields={'Manufacturer': 'Texas Instruments', 'MPN': 'LMP7715MF/NOPB',
                   'Description': 'Antenna bias buffer'})
    R(sh, '1k', (120.65, 127), 'BIAS_BUF', 'ANT_BIAS', rot=90, role='isolates buffer from input capacitance')
    decap(sh, 166.37, 144.78, '+5V_PRE')

    sh.box(190, 75, 282, 110, 'TEST POINTS')
    for i, net in enumerate(('PREAMP_OUT', 'BIAS_BUF', 'GUARD_DRV', 'GND')):
        sh.add(ref('TP'), 'Connector:TestPoint', net, (200.66 + i * 20.32, 91.44), {1: net},
               footprint='TestPoint:TestPoint_Keystone_5000-5004_Miniature',
               fields={'Manufacturer': 'Keystone', 'MPN': '5001' if net == 'GND' else '5000',
                       'Description': f'Test point {net}'})
    sh.text('Cg returns to GND: the 2.5 V buffer noise stays out of the gain path.', (15, 168), size=1.5)
    sh.text('Guard buffer senses IN- (virtual short to IN+): no bias current on IN_P.', (15, 172), size=1.5)
    return sh


def sheet_adc(p):
    ref.sheet(300)
    sh = p.sheet('adc', 'adc.kicad_sch', 'ADC (PCM1804)')
    sh.box(15, 20, 165, 95, 'COUPLING, ANTI-ALIAS, ADC DRIVER')
    C(sh, '10u_film', (30.48, 33.02), 'PREAMP_OUT', 'ADC_A', rot=90, role='C_out, HPF 0.34 Hz')
    R(sh, '47k_prec', (45.72, 50.8), 'ADC_A', 'VCOML', role='R_bias', key='47k_prec')
    R(sh, '10k_prec', (60.96, 33.02), 'ADC_A', 'VINL_F', rot=90, role='R_AA, LPF 159 Hz', key='10k_prec')
    C(sh, '100n_c0g', (76.2, 50.8), 'VINL_F', 'VCOML', role='C_AA')
    sh.add(ref('U'), f'{LIB}:LMP7715', 'LMP7715', (104.14, 35.56),
           {3: 'VINL_F', 4: 'DRV_OUT', 1: 'DRV_OUT', 5: '+5VA', 2: 'GND'},
           footprint='Package_TO_SOT_SMD:SOT-23-5',
           fields={'Manufacturer': 'Texas Instruments', 'MPN': 'LMP7715MF/NOPB',
                   'Description': 'ADC driver, unity gain (isolates the AA filter from ADC kick-back)'})
    R(sh, '100', (139.7, 35.56), 'DRV_OUT', 'VINL', rot=90, role='driver isolation')
    C(sh, '2.7n_c0g', (157.48, 50.8), 'VINL', 'VCOML', role='ADC charge reservoir')
    decap(sh, 104.14, 78.74, '+5VA')

    sh.box(170, 20, 290, 160, 'PCM1804  master, 192 kHz')
    sh.add(ref('U'), f'{LIB}:PCM1804', 'PCM1804', (229.87, 71.12),
           {4: 'VINL', 5: 'VCOML', 3: 'VCOML', 1: 'VREFL', 25: 'VCOMR', 24: 'VCOMR', 26: 'VCOMR',
            28: 'VREFR', 6: 'FMT0', 7: 'FMT1', 8: 'SM', 9: 'OSR0', 10: 'OSR1', 11: 'OSR2',
            12: 'BYPAS', 19: 'RESET_N', 18: 'MCLK_ADC', 16: 'BCK', 17: 'LRCK', 15: 'SDATA',
            21: 'OVFL', 20: None, 22: '+5VA', 14: '+3V3', 2: 'GND', 23: 'GND', 27: 'GND', 13: 'GND'},
           footprint='Package_SO:SSOP-28_5.3x10.2mm_P0.65mm',
           fields={'Manufacturer': 'Texas Instruments', 'MPN': 'PCM1804DB',
                   'Description': '24-bit 192 kHz stereo ADC; right channel = shorted noise reference'})
    for i, net in enumerate(('VREFL', 'VCOML', 'VREFR', 'VCOMR')):
        decap(sh, 180.34 + i * 27.94, 142.24, net, ('10u', '100n'))

    sh.box(295, 20, 405, 60, 'SUPPLY DECOUPLING')
    decap(sh, 307.34, 43.18, '+5VA', ('10u', '100n'))
    decap(sh, 345.44, 43.18, '+3V3', ('10u', '100n'))

    sh.box(295, 65, 345, 120, 'OVERLOAD')
    R(sh, '1k', (313.69, 83.82), 'OVFL', 'LED_OVF')
    sh.add(ref('D'), 'Device:LED', 'RED', (313.69, 101.6), {2: 'LED_OVF', 1: 'GND'}, rot=90,
           footprint='LED_SMD:LED_0805_2012Metric',
           fields={'Manufacturer': 'Wurth', 'MPN': '150080RS75000', 'Description': 'LED red 0805, left-channel overflow'})

    sh.box(350, 65, 405, 120, 'RESET')
    R(sh, '10k', (360.68, 83.82), '+3V3', 'RESET_N')
    C(sh, '1u', (375.92, 101.6), 'RESET_N', 'GND')
    sh.add(ref('SW'), 'Switch:SW_Push', 'RESET', (391.16, 101.6), {1: 'RESET_N', 2: 'GND'}, rot=270,
           footprint='Button_Switch_SMD:SW_SPST_TL3342',
           fields={'Manufacturer': 'E-Switch', 'MPN': 'TL3342F160QG', 'Description': 'Reset push button (ADC + S/PDIF TX)'})

    sh.box(15, 100, 165, 160, 'PCM1804 MODE  (ON = 1)')
    sw_nets = ['FMT0', 'FMT1', 'SM', 'OSR0', 'OSR1', 'OSR2', 'BYPAS']
    nets = {i + 1: '+3V3' for i in range(7)}
    for i, n in enumerate(sw_nets):
        nets[16 - i] = n
    nets[8] = None
    nets[9] = None
    sh.add(ref('SW'), 'Switch:SW_DIP_x08', 'PCM1804 MODE', (38.1, 129.54), nets,
           footprint='Button_Switch_THT:SW_DIP_SPSTx08_Slide_9.78x22.5mm_W7.62mm_P2.54mm',
           fields={'Manufacturer': 'CTS', 'MPN': '206-8ST', 'Description': '8-way DIP switch, PCM1804 mode pins'})
    for i, n in enumerate(sw_nets):
        R(sh, '10k', (78.74 + i * 11.43, 132.08), n, 'GND', role='pull-down')

    sh.text('Default (192 kHz): S/M=1 master, OSR2..0=111 (SCKI=128 fs), FMT1..0=01 I2S, BYPAS=1 (HPF off).',
            (170, 166), size=1.5)
    sh.text('Change switches with power off, or press RESET afterwards.', (170, 170), size=1.5)
    return sh


def sheet_digital(p):
    ref.sheet(400)
    sh = p.sheet('digital', 'digital.kicad_sch', 'Clock and S/PDIF + AES3 output')
    sh.box(15, 20, 110, 75, 'MASTER CLOCK 24.576 MHz')
    sh.add(ref('Y'), f'{LIB}:MEMS_OSC', '24.576MHz', (38.1, 45.72),
           {1: '+3V3', 4: '+3V3', 2: 'GND', 3: 'OSC_OUT'},
           footprint='Oscillator:Oscillator_SMD_SiT_PQFN-4Pin_3.2x2.5mm',
           fields={'Manufacturer': 'SiTime', 'MPN': 'SiT1602BI-33-33E-24.576000',
                   'Description': 'MEMS oscillator 24.576 MHz 3.3 V 3.2x2.5 mm'})
    R(sh, '33', (80.01, 38.1), 'OSC_OUT', 'MCLK_ADC', rot=90, role='series termination, ADC branch')
    R(sh, '33', (80.01, 50.8), 'OSC_OUT', 'MCLK_TX', rot=90, role='series termination, S/PDIF branch')
    decap(sh, 100.33, 62.23, '+3V3')

    sh.box(115, 20, 250, 125, 'CS8406  hardware mode')
    sh.add(ref('U'), 'Audio:CS8406', 'CS8406', (182.88, 68.58),
           {1: 'GND', 2: 'GND', 3: 'EMPH_N', 4: 'SFMT0', 5: 'SFMT1', 6: '+3V3', 7: 'GND', 8: 'GND',
            9: 'RESET_N', 10: 'APMS', 11: 'GND', 12: 'LRCK', 13: 'BCK', 14: 'SDATA', 15: 'TCBL',
            16: 'CEN', 17: 'GND', 18: 'GND', 19: 'AUDIO_N', 20: 'HWCK0', 21: 'MCLK_TX', 22: 'GND',
            23: '+3V3', 24: '+3V3', 25: 'TXN', 26: 'TXP', 27: 'HWCK1', 28: 'GND'},
           footprint='Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm',
           fields={'Manufacturer': 'Cirrus Logic', 'MPN': 'CS8406-CZZ',
                   'Description': '192 kHz digital audio interface transmitter (hardware mode: H/S high)'})
    R(sh, '10k', (124.46, 111.76), 'TCBL', 'GND', role='TCBL defined whichever direction TCBLD selects')
    decap(sh, 207.01, 111.76, '+3V3', ('10u', '100n', '100n'))

    sh.box(255, 20, 405, 75, 'CS8406 MODE  (ON = 1)')
    sw2 = ['HWCK0', 'HWCK1', 'SFMT0', 'SFMT1', 'APMS', 'CEN', 'EMPH_N', 'AUDIO_N']
    nets = {i + 1: '+3V3' for i in range(8)}
    for i, n in enumerate(sw2):
        nets[16 - i] = n
    sh.add(ref('SW'), 'Switch:SW_DIP_x08', 'CS8406 MODE', (275.59, 48.26), nets,
           footprint='Button_Switch_THT:SW_DIP_SPSTx08_Slide_9.78x22.5mm_W7.62mm_P2.54mm',
           fields={'Manufacturer': 'CTS', 'MPN': '206-8ST', 'Description': '8-way DIP switch, CS8406 hardware-mode pins'})
    for i, n in enumerate(sw2):
        R(sh, '10k', (308.61 + i * 11.43, 50.8), n, 'GND', role='pull-down')

    sh.box(15, 130, 405, 190, 'OUTPUTS  transformer isolated')
    sh.text('AES3  110 R balanced', (20, 140), size=1.5, bold=True)
    R(sh, '39', (30.48, 152.4), 'TXP', 'AES_A', rot=90)
    C(sh, '100n', (63.5, 152.4), 'AES_A', 'AES_P1', rot=90, role='DC block')
    R(sh, '39', (30.48, 167.64), 'AES_P2', 'TXN', rot=90)
    sh.add(ref('TR'), f'{LIB}:XFMR_1to1', 'S22083', (99.06, 160.02),
           {1: 'AES_P1', 2: 'AES_P2', 3: 'AES_HOT', 4: 'AES_COLD'},
           footprint='elara:Transformer_Pulse_4Pin_W7.62mm',
           fields={'Manufacturer': 'Newava', 'MPN': 'S22083',
                   'Description': 'AES3 110 R pulse transformer 1:1 (4-pin, windings 1-2 / 3-4; slots fit 5.08 or 10.16 mm pitch)'})
    sh.add(ref('J'), 'Connector:Screw_Terminal_01x03', 'AES3 OUT', (129.54, 160.02),
           {1: 'AES_SHIELD', 2: 'AES_HOT', 3: 'AES_COLD'}, mirror='y',
           footprint='TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal',
           fields={'Manufacturer': 'Phoenix Contact', 'MPN': '1715734',
                   'Description': 'AES3 cable: 1 shield (open by default), 2 hot, 3 cold'})
    C(sh, '10n_dnp', (152.4, 172.72), 'AES_SHIELD', 'GND', dnp=True, role='optional RF bond')
    R(sh, '0', (165.1, 172.72), 'AES_SHIELD', 'GND', dnp=True, role='optional DC bond (shield is grounded indoors)')

    sh.text('S/PDIF  75 R coax, 0.5 Vpp', (200, 140), size=1.5, bold=True)
    R(sh, '249', (210.82, 152.4), 'TXP', 'COAX_A', rot=90)
    C(sh, '100n', (243.84, 152.4), 'COAX_A', 'COAX_P1', rot=90, role='DC block')
    R(sh, '249', (210.82, 170.18), 'COAX_P2', 'TXN', rot=90)
    R(sh, '90.9', (266.7, 161.29), 'COAX_P1', 'COAX_P2', role='75 R source, 0.5 Vpp')
    sh.add(ref('TR'), f'{LIB}:XFMR_1to1', 'S22083', (302.26, 160.02),
           {1: 'COAX_P1', 2: 'COAX_P2', 3: 'SPDIF_OUT', 4: 'SPDIF_RET'},
           footprint='elara:Transformer_Pulse_4Pin_W7.62mm',
           fields={'Manufacturer': 'Newava', 'MPN': 'S22083',
                   'Description': 'S/PDIF 75 R pulse transformer 1:1 (4-pin, windings 1-2 / 3-4; slots fit 5.08 or 10.16 mm pitch)'})
    sh.add(ref('J'), 'Connector:Conn_Coaxial', 'S/PDIF OUT', (335.28, 160.02),
           {1: 'SPDIF_OUT', 2: 'SPDIF_RET'}, mirror='y',
           footprint='Connector_Coaxial:BNC_Amphenol_031-6575_Horizontal',
           fields={'Manufacturer': 'Amphenol RF', 'MPN': '031-6575',
                   'Description': 'BNC right-angle PCB jack, S/PDIF coax (BNC-RCA adapter)'})
    sh.text('AES3: 2 x 39 R + ~2 x 26 R driver ~ 110 R source, ~3 Vpp into 110 R.', (15, 197), size=1.5)
    sh.text('S/PDIF: 2 x 249 R + 90.9 R shunt: 75 R source, 0.5 Vpp into 75 R.', (15, 201), size=1.5)
    sh.text('Default (192 kHz): HWCK -> OMCK = 128 fs, SFMT = I2S, APMS=0 (slave), CEN=0, EMPH_N=1, AUDIO_N=0.',
            (255, 82), size=1.5)
    return sh


def build():
    p = Project(NAME, HERE, 'ELARA antenna amplifier', rev='0.2',
                company='ELARA -- ELF Atmospheric Radio Analyser',
                comments=('CERN-OHL-W-2.0', 'Generated by PCB/antenna_amplifier/design.py -- edit the script, not the sheets'))
    lib_path = os.path.join(HERE, f'{NAME}.kicad_sym')
    with open(lib_path, 'w', encoding='utf-8') as f:
        f.write(dumps(symbols.library(project_symbols())) + '\n')
    p.libs.add(LIB, lib_path)
    sheet_power(p)
    sheet_frontend(p)
    sheet_adc(p)
    sheet_digital(p)
    return p


def write_tables():
    with open(os.path.join(HERE, 'sym-lib-table'), 'w', encoding='utf-8') as f:
        f.write('(sym_lib_table\n\t(version 7)\n'
                f'\t(lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{NAME}.kicad_sym")(options "")(descr "ELARA project symbols"))\n)\n')
    with open(os.path.join(HERE, 'fp-lib-table'), 'w', encoding='utf-8') as f:
        f.write('(fp_lib_table\n\t(version 7)\n'
                '\t(lib (name "elara")(type "KiCad")(uri "${KIPRJMOD}/../elara.pretty")(options "")(descr "ELARA project footprints"))\n)\n')


def write_netlist_json(p):
    comps = []
    for s in p.sheets:
        for pl in s.symbols:
            comps.append({'ref': pl.ref, 'value': pl.value, 'footprint': pl.footprint,
                          'lib_id': pl.sym.lib_id, 'sheet': s.name, 'sheet_uuid': s.uuid,
                          'uuid': pl.uuid, 'dnp': pl.dnp, 'fields': pl.fields,
                          'pins': {k: v for k, v in pl.nets.items()}})
    with open(os.path.join(HERE, 'design_netlist.json'), 'w', encoding='utf-8') as f:
        json.dump({'project': p.name, 'root_uuid': p.root_uuid, 'components': comps}, f, indent=1)


def main():
    p = build()
    p.write()
    write_tables()
    write_netlist_json(p)
    print(f'{len(p.components())} components, {len(p.netlist())} nets written')
    if '--no-check' not in sys.argv:
        from kicadgen.netcheck import compare, export_netlist, exported_nets
        problems = compare(p.netlist(), exported_nets(export_netlist(os.path.join(HERE, f'{NAME}.kicad_sch'))))
        print('\n'.join(problems) if problems else 'net list check: KiCad connectivity matches design')
        sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
