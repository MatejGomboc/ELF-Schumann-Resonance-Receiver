#!/usr/bin/env python3
"""ELARA "two-bucket" PSU -- single source of truth for the schematic.

Goal: a mains supply as quiet as a battery.

  230 V AC -> Mean Well IRM-05-15 (charger side, GND_C, bonded to PE/enclosure)
           -> constant-current 0.2 A / constant-voltage 10.4 V supercap charger
           -> two supercapacitor "buckets" (4 x 10 F each)
           -> four SPDT reed relays (form C) swap the buckets every ~15 s
           -> receiver side: reservoir -> LT3045 (0.8 uV rms) -> common-mode
              choke -> 6.98 V out

A form-C relay breaks before it makes, so a bucket is never connected to the
charger and the receiver at the same time: the receiver ground is
galvanically isolated from mains at every instant, and the only coupling left
is the open reed contacts and coil-to-contact capacitance, ~1.5 pF each, under
10 pF in total (vs 20-100 pF across an AC-DC module's barrier).

Each bucket has its own pair of relays (coils in series) and its own driver.
At a swap the arriving bucket switches at once and the leaving one some 10-50 ms
later (an RC on its driver gate), so both buckets are briefly on the load,
diode-ORed by SS34s: the leaving bucket's load contacts then open dry, with its
diode reverse biased, and the two buckets are never on the charger together.
Bucket B is wired the opposite way round, so with the coils off (mains failed)
it stays on the receiver and carries it through the hold-up. The swap rate (33 mHz) is below the ELF band, and the
bucket droop / swap step is removed by the LT3045 and again by the ADM7150s
on the amplifier board. The charger side, its timer and relay coils live in
the grounded ALU PSU enclosure; there is no LED on the receiver side.

A 9-13 V battery on the amplifier's input connector replaces this whole unit.

Usage:  .venv/bin/python PCB/acdc_converter/design.py [--no-check]
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))

from kicadgen import schematic, symbols  # noqa: E402
from kicadgen.schematic import Project  # noqa: E402
from kicadgen.sexpr import dumps  # noqa: E402
from kicadgen.symlib import derived  # noqa: E402

NAME = 'acdc_converter'
schematic.POWER_SYMBOLS['GND_C'] = 'power:GNDD'   # charger-side ground (PE bonded)

R0805 = 'Resistor_SMD:R_0805_2012Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
R2512 = 'Resistor_SMD:R_2512_6332Metric'
R1206 = 'Resistor_SMD:R_1206_3216Metric'
C1210 = 'Capacitor_SMD:C_1210_3225Metric'
LIB = NAME


def project_symbols():
    # Bourns SRF1260 numbers its windings 1-3 and 2-4 (dots on 1 and 2; datasheet p.1);
    # KiCad's common-mode choke symbol has them on 1-2 and 3-4: same drawing, pins 2/3
    # renumbered so the footprint pads land on the right windings
    return [derived('Device:Filter_EMI_CommonMode', 'CMC_SRF1260', {},
                    'Common-mode choke, Bourns SRF1260 winding numbering (N1 = 1-3, N2 = 2-4)',
                    pin_numbers={'2': '3', '3': '2'}),
            # UTC/onsemi MCR100 in TO-92: 1 K, 2 G, 3 A (BT169's drawing numbers A 1, K 3)
            derived('Triac_Thyristor:BT169B', 'SCR_MCR100', {},
                    'SCR 0.8 A, MCR100 pinout (TO-92: 1 K, 2 G, 3 A)', pin_numbers={'1': '3', '3': '1'})]

ERA = {'120': '121V', '499': '4990V', '100': '101V', '240': '241V', '1.74k': '1741V', '4.7k': '472V', '100k': '104V', '80.6k': '8062V',
       '1M': '105V', '69.8k': '6982V', '36.5k': '3652V', '10k': '103V'}


def pana(mpn, desc):
    return {'Manufacturer': 'Panasonic', 'MPN': mpn, 'Description': desc}


def mur(mpn, desc):
    return {'Manufacturer': 'Murata', 'MPN': mpn, 'Description': desc}


CAP_100N = mur('GRM21BR71H104KA01L', 'MLCC 100n 50V X7R 0805')
CAP_10U = mur('GRM31CR71E106KA12L', 'MLCC 10u 25V X7R 1206')


class Refs:
    def __init__(self):
        self.n = {}

    def __call__(self, prefix):
        self.n[prefix] = self.n.get(prefix, 0) + 1
        return f'{prefix}{self.n[prefix]}'


ref = Refs()


def R(sh, value, pos, a, b, rot=0, fp=R0805, fields=None, **kw):
    return sh.add(ref('R'), 'Device:R', value, pos, {1: a, 2: b}, rot=rot, footprint=fp, **kw,
                  fields=fields or pana(f'ERA-6AEB{ERA[value]}', f'Thin film {value} 0.1% 0805'))


def C(sh, value, pos, a, b, rot=0, fp=C0805, fields=CAP_100N, polar=False, **kw):
    return sh.add(ref('C'), 'Device:C_Polarized' if polar else 'Device:C', value, pos, {1: a, 2: b}, rot=rot,
                  footprint=fp, fields=fields, **kw)


def bucket(sh, name, x, y):
    """Four 10 F / 2.7 V EDLC cells in series, each with a passive balancing resistor.

    Cells (and resistors) are stacked so adjacent pins touch; each node is
    wired across to its balancing resistor.
    """
    nodes = [f'{name}_P', f'{name}_1', f'{name}_2', f'{name}_3', f'{name}_N']
    for i in range(4):
        C(sh, '10F', (x, y + i * 7.62), nodes[i], nodes[i + 1], polar=True,
          fields_at={'Reference': (-3.2, -0.6, 'right'), 'Value': (-3.2, 1.9, 'right')},
          fp='Capacitor_THT:CP_Radial_D12.5mm_P5.00mm',
          fields={'Manufacturer': 'Eaton', 'MPN': 'HV1030-2R7106-R',
                  'Description': 'EDLC 10 F 2.7 V, D10 x 30 mm, P5.0 (any 10 F 2.7 V radial cell; match within 5%)'})
        R(sh, '5.1k', (x + 12.7, y + i * 7.62), nodes[i], nodes[i + 1], fp='Resistor_SMD:R_1206_3216Metric',
          fields=pana('ERJ-8ENF5101V', 'Balancing 5k1 1% 1206 (~0.5 mA, >10x cell leakage)'))
    for i in range(5):
        yy = y - 3.81 + i * 7.62
        if 0 < i < 4:
            sh.wire((x, yy), (x + 12.7, yy))
            sh.label(nodes[i], (x + 6.35, yy))


def build():
    p = Project(NAME, HERE, 'ELARA PSU', rev='0.2', company='ELARA -- ELF Atmospheric Radio Analyser',
                comments=('CERN-OHL-W-2.0',
                          'Generated by PCB/acdc_converter/design.py -- edit the script, not the sheet',
                          'MAINS VOLTAGE on the primary side -- 6.4 mm creepage to everything else'),
                date='2026-09-30')
    p.root_notes = [
        'Power: 230 V AC -> IRM-05-15 (15 V; GND_C bonded to PE) -> LM317 CC 0.2 A -> LM317 CV 10.76 V -> SS34',
        '       -> two 2.5 F supercap buckets, swapped every ~15 s by four SIL05-1C90-51D reed relays (staggered, dry load break)',
        '       -> receiver side: 2200 uF -> LT3045 6.98 V -> common-mode choke -> J2 to the amplifier.',
        'Board: 150 x 90 mm, 2 layers; mains >= 2.5 mm L-N and to PE, >= 6.4 mm to everything else (layout.py).',
        'The only LED (D2, mains present) is on the charger side; the receiver side has none.',
        'Buckets swing 9.4-10.0 V (CV 10.76 V, two SS34s: 2.6 V per cell); 15 s at ~0.1 A droops ~0.6 V; the LT3045 keeps',
        'its headroom in the worst corner (simulations/psu). Swap rate 33 mHz, far below the ELF band.',
        '+9V_OUT carries the 6.98 V output (net name kept from rev 0.1).',
    ]
    lib_path = os.path.join(HERE, f'{NAME}.kicad_sym')
    with open(lib_path, 'w', encoding='utf-8') as f:
        f.write(dumps(symbols.library(project_symbols())) + '\n')
    p.libs.add(LIB, lib_path)
    sh = p.sheet('psu', 'psu.kicad_sch', 'Two-bucket isolated supply')

    # ---- primary ---------------------------------------------------------
    sh.box(15, 20, 105, 100, 'MAINS  (primary)')
    j1 = sh.add('J1', 'Connector:Screw_Terminal_01x03', 'MAINS L N PE', (33.02, 45.72),
           {1: 'L_IN', 2: 'AC_N', 3: 'PE'}, mirror='y',
           footprint='elara:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal_Mains',
           fields={'Manufacturer': 'Phoenix Contact', 'MPN': '1715734',
                   'Description': 'Mains input: 1 L, 2 N, 3 PE (2.3 mm pads: 2.78 mm creepage pin to pin)'})
    f1 = sh.add('F1', 'Device:Fuse', 'T500mA', (55.88, 35.56), {1: 'L_IN', 2: 'AC_L'}, rot=90,
           footprint='Fuse:Fuseholder_Clip-5x20mm_Bel_FC-203-22_Lateral_P17.80x5.00mm_D1.17mm_Horizontal',
           fields={'Manufacturer': 'Littelfuse / Bel Fuse', 'MPN': '0215.500MXP + 2x FC-203-22 clips',
                   'Description': 'Fuse 5x20 mm T500 mA 250 V slow-blow, CERAMIC, 1500 A breaking '
                                  '(a glass 5x20 breaks only ~35 A), in PCB clips'})
    sh.join(j1, 1, f1, 1)
    sh.add('RV1', 'Device:Varistor', '275VAC', (86.36, 58.42), {1: 'AC_L', 2: 'AC_N'},
           footprint='Varistor:RV_Disc_D12mm_W4.7mm_P7.5mm',
           fields={'Manufacturer': 'TDK', 'MPN': 'B72210S0271K101',
                   'Description': 'MOV 275 VAC, mains surge clamp after the fuse'})
    for i in range(2):
        sh.add(f'H{2 * i + 1}', 'Mechanical:MountingHole_Pad', 'M3 PE', (25.4 + i * 12.7, 86.36), {1: 'PE'},
               footprint='MountingHole:MountingHole_3.2mm_M3_Pad_Via',
               fields={'Manufacturer': '-', 'MPN': '-', 'Description': 'M3 hole bonded to PE (ALU enclosure), mains side'},
               in_bom=False)
        sh.add(f'H{2 * i + 2}', 'Mechanical:MountingHole', 'M3', (50.8 + i * 12.7, 86.36), {},
               footprint='MountingHole:MountingHole_3.2mm_M3',
               fields={'Manufacturer': '-', 'MPN': '-',
                       'Description': 'M3 hole, unplated: no PE copper next to the receiver side'},
               in_bom=False)
    sh.flag('AC_L', (99.06, 38.1))
    sh.flag('AC_N', (99.06, 76.2))
    sh.flag('PE', (78.74, 86.36))

    sh.box(110, 20, 165, 100, 'AC-DC  15 V')
    sh.add('PS1', 'Converter_ACDC:IRM-05-15', 'IRM-05-15', (137.16, 55.88),
           {2: 'AC_L', 1: 'AC_N', 4: '+15V_C', 3: 'GND_C'},
           footprint='Converter_ACDC:Converter_ACDC_MeanWell_IRM-05-xx_THT',
           fields={'Manufacturer': 'Mean Well', 'MPN': 'IRM-05-15',
                   'Description': '5 W 15 V encapsulated AC-DC module, 3 kVAC, EN55032 class B'})
    R(sh, '0', (152.4, 81.28), 'GND_C', 'PE', fp='Resistor_SMD:R_1206_3216Metric',
      fields={'Manufacturer': 'Panasonic', 'MPN': 'ERJ-8GEY0R00V',
              'Description': 'Bonds charger ground to PE/enclosure: all switching noise stays in the grounded box'})

    # ---- charger side (GND_C) -------------------------------------------
    sh.box(170, 20, 405, 100, 'CHARGER  (GND_C)  CC 0.2 A -> CV 10.76 V')
    C(sh, '47u', (177.8, 58.42), '+15V_C', 'GND_C', polar=True, fp='Capacitor_THT:CP_Radial_D6.3mm_P2.50mm',
      fields=pana('EEU-FR1E470', 'Electrolytic 47u 25V low-ESR'))
    C(sh, '100n', (187.96, 58.42), '+15V_C', 'GND_C')
    sh.add('U1', 'Regulator_Linear:LM317_TO-220', 'LM317', (210.82, 38.1),
           {3: '+15V_C', 2: 'CC_SET', 1: 'CC_OUT'}, footprint='Package_TO_SOT_THT:TO-220-3_Horizontal_TabDown',
           fields={'Manufacturer': 'onsemi', 'MPN': 'LM317BTG',
                   'Description': 'Constant current, 1.25 V / 6.2 R = 0.2 A (tab = OUT = CC_SET, on a copper area); B grade, -40 C'})
    R(sh, '6.2', (210.82, 60.96), 'CC_SET', 'CC_OUT', rot=90, fp=R2512,
      fields={'Manufacturer': 'Vishay', 'MPN': 'CRCW25126R20FKEG', 'Description': 'Current set 6R2 1% 1 W 2512'})
    sh.add('U2', 'Regulator_Linear:LM317_TO-220', 'LM317', (251.46, 38.1),
           {3: 'CC_OUT', 2: 'CHG', 1: 'CV_ADJ'}, footprint='Package_TO_SOT_THT:TO-220-3_Horizontal_TabDown',
           fields={'Manufacturer': 'onsemi', 'MPN': 'LM317BTG',
                   'Description': 'Constant voltage 1.25 V x (1 + 909/120) + 50 uA x 909 = 10.76 V (two SS34s to the '
                                  'cells); the 10.5 mA divider keeps the LM317 above its 10 mA minimum load '
                                  '(tab bolted to the base)'})
    r3 = R(sh, '120', (271.78, 58.42), 'CHG', 'CV_ADJ')
    r4 = R(sh, '909', (271.78, 83.82), 'CV_ADJ', 'GND_C', fp=R1206,
           fields=pana('ERA-8AEB9090V', 'Thin film 909R 0.1% 1206 (100 mW)'))
    sh.join(r3, 2, r4, 1)
    C(sh, '100n', (284.48, 71.12), 'CHG', 'GND_C')
    sh.add('D1', 'Diode:SS34', 'SS34', (302.26, 38.1), {1: 'CHG_D', 2: 'CHG'}, rot=180,
           footprint='Diode_SMD:D_SMA',
           fields={'Manufacturer': 'Vishay', 'MPN': 'SS34-E3/57T',
                   'Description': 'Stops the buckets discharging into the charger when mains is off'})
    sh.add('U3', 'Regulator_Linear:L78L12_SOT89', 'L78L12', (335.28, 38.1),
           {3: '+15V_C', 1: '+12V_C', 2: 'GND_C'}, footprint='Package_TO_SOT_SMD:SOT-89-3',
           fields={'Manufacturer': 'STMicroelectronics', 'MPN': 'L78L12ABUTR',
                   'Description': '12 V for the relay coils and timer; B grade, -40 C'})
    C(sh, '330n', (322.58, 60.96), '+15V_C', 'GND_C', fields=mur('GRM21BR71H334KA88L', 'MLCC 330n 50V X7R 0805'))
    C(sh, '100n', (347.98, 60.96), '+12V_C', 'GND_C')
    r5 = R(sh, '4.7k', (368.3, 45.72), '+12V_C', 'LED_C')
    d2 = sh.add('D2', 'Device:LED', 'GREEN', (368.3, 68.58), {2: 'LED_C', 1: 'GND_C'}, rot=90,
                fields_at={'Reference': (-3.3, -0.5, 'left'), 'Value': (-3.3, 2.0, 'left')},
           footprint='LED_SMD:LED_0805_2012Metric',
           fields={'Manufacturer': 'Wurth', 'MPN': '150080VS75000',
                   'Description': 'LED green, mains present (charger side only)'})
    sh.join(r5, 2, d2, 2)
    sh.flag('CC_OUT', (231.14, 53.34))

    # ---- swap timer -----------------------------------------------------
    sh.box(15, 105, 108, 195, 'SWAP TIMER  Q14 toggles every ~15 s')
    sh.add('U4', '4xxx:4060', 'CD4060B', (55.88, 147.32),
           {9: 'OSC_C', 10: 'OSC_R', 11: 'OSC_I', 12: 'GND_C', 16: '+12V_C', 8: 'GND_C',
            7: None, 5: None, 4: None, 6: None, 14: None, 13: None, 15: None, 1: None, 2: None, 3: 'SWAP'},
           footprint='Package_SO:SOIC-16_3.9x9.9mm_P1.27mm',
           fields={'Manufacturer': 'Texas Instruments', 'MPN': 'CD4060BM96',
                   'Description': '14-stage counter + RC oscillator, f = 1/(2.3 Rt Ct) = 540 Hz, Q14 toggles every ~15 s'})
    C(sh, '10n', (91.44, 124.46), 'OSC_C', 'OSC_X', rot=90,
      fields=mur('GRM2195C1H103JA01D', 'MLCC 10n 50V C0G 0805 (Ct)'))
    R(sh, '80.6k', (91.44, 139.7), 'OSC_R', 'OSC_X', rot=90)
    R(sh, '1M', (91.44, 154.94), 'OSC_I', 'OSC_X', rot=90)
    C(sh, '100n', (91.44, 177.8), '+12V_C', 'GND_C')

    sh.box(170, 105, 405, 195, 'BUCKET SWAP  (reed, form C; the arriving bucket switches first)')
    R(sh, '100', (185.42, 129.54), 'SWAP', 'SW_R', rot=90)
    R(sh, '100k', (198.12, 160.02), 'GATE_A', 'GND_C',
      fields=pana('ERA-6AEB104V', 'Thin film 100k 0.1% 0805: bucket A release delay with C20 (30-50 ms)'))
    # bucket A: gate charged at once through D3, held on by C20 / R9 when SWAP falls;
    # bucket B: gate charged slowly through R23 into C21, discharged at once through D4
    for i, (bk, q, gate, coil, d, anode, cathode) in enumerate((
            ('A', 'Q1', 'GATE_A', 'COIL_A', 'D3', 'SW_R', 'GATE_A'),
            ('B', 'Q2', 'GATE_B', 'COIL_B', 'D4', 'GATE_B', 'SW_R'))):
        x = (223.52, 259.08)[i]
        sh.add(q, 'Transistor_FET:2N7002', '2N7002', (x, 147.32), {1: gate, 3: coil, 2: 'GND_C'},
               footprint='Package_TO_SOT_SMD:SOT-23',
               fields={'Manufacturer': 'onsemi', 'MPN': '2N7002LT1G', 'Description': f'Bucket {bk} relay coil driver'})
        sh.add(d, 'Diode:1N4148W', '1N4148W', ((203.2, 251.46)[i], 129.54), {1: cathode, 2: anode},
               rot=270,
               fields_at={'Reference': (2.6, -0.6, 'left'), 'Value': (2.6, 1.9, 'left')},
               footprint='Diode_SMD:D_SOD-123',
               fields={'Manufacturer': 'Diodes Inc.', 'MPN': '1N4148W-7-F',
                       'Description': f'Bucket {bk} gate: fast {"on" if bk == "A" else "off"} edge'})
    # four reeds: pin 7 common, 2 NC, 1 NO, coil 3 (+) -> 5 with a built-in diode.
    # A: NC = charger, NO = load.  B the other way round (coil off = B on the receiver).
    relays = (('K1', 'A_P', 'CHG_A', 'LOAD_A', '+12V_C', 'COIL_A1'),
              ('K2', 'A_N', 'A_NC', 'A_NL', 'COIL_A1', 'COIL_A2'),
              ('K3', 'B_P', 'LOAD_B', 'CHG_B', '+12V_C', 'COIL_B1'),
              ('K4', 'B_N', 'B_NL', 'B_NC', 'COIL_B1', 'COIL_B2'))
    for i, (k, com, nc, no, cp, cn) in enumerate(relays):
        x = 281.94 + i * 31.75
        sh.add(k, 'Relay:SILxx-1Cxx-51x', 'SIL05-1C90-51D', (x, 144.78), labels_only=True,
               fields_at={'Reference': (11.4, -1.3, 'left'), 'Value': (7.0, 13.3, 'left')},
               nets={7: com, 2: nc, 1: no, 3: cp, 5: cn},
               footprint='Relay_THT:Relay_SPDT_StandexMeder_SIL_Form1C',
               fields={'Manufacturer': 'Standex', 'MPN': 'SIL05-1C90-51D',
                       'Description': f'Bucket {k in ("K1", "K2") and "A" or "B"} reed relay, SPDT 10 W 0.5 A, '
                                      '1.5 pF open, 5 V 200 R coil with diode; two coils in series per bucket'})
    for i, (net, dst) in enumerate((('CHG_A', 'CHG_D'), ('CHG_B', 'CHG_D'), ('LA_D', 'OR_P'), ('LB_D', 'OR_P'))):
        val, mpn = ('2.2', 'CRCW25122R20FKEG') if i < 2 else ('1', 'CRCW25121R00FKEG')
        R(sh, val, ((184.15, 210.82, 264.16, 314.96)[i], 182.88), net, dst, rot=90, fp=R2512,
          fields={'Manufacturer': 'Vishay', 'MPN': mpn,
                  'Description': 'Charger path, limits the make current' if i < 2 else
                  'Load path, damps the make current (the 0.4 A limiter Q3/Q4 caps it)'})

    # ---- buckets ----------------------------------------------------------
    sh.box(15, 200, 67, 280, 'BUCKET A  2.5 F')
    bucket(sh, 'A', 30.48, 226.06)
    sh.box(72, 200, 124, 280, 'BUCKET B  2.5 F')
    bucket(sh, 'B', 87.63, 226.06)

    # ---- receiver side (GND) ------------------------------------------------
    sh.box(129, 200, 282, 280, 'RECEIVER SIDE  LT3045 6.98 V')
    C(sh, '2200u', (139.7, 243.84), 'LOAD_P', 'GND', polar=True, fp='Capacitor_THT:CP_Radial_D12.5mm_P5.00mm',
      fields=pana('EEU-FR1C222', 'Electrolytic 2200u 16V low-ESR, 12.5 x 20 mm, rides through the relay transit'))
    C(sh, '10u', (152.4, 243.84), 'LOAD_P', 'GND', fp=C1206, fields=CAP_10U)
    sh.add('U5', 'Regulator_Linear:LT3045xMSE', 'LT3045', (182.88, 233.68),
           {1: 'LOAD_P', 2: 'LOAD_P', 3: 'LOAD_P', 4: 'LOAD_P', 7: 'LOAD_P', 6: 'ILIM', 8: 'SET',
            9: 'GND', 13: 'GND', 11: 'VREG', 12: 'VREG', 10: 'VREG', 5: None},
           stubs={6: 5 * 2.54},
           footprint='Package_SO:MSOP-12-1EP_3x4.039mm_P0.65mm_EP1.651x2.845mm',
           fields={'Manufacturer': 'Analog Devices', 'MPN': 'LT3045EMSE#PBF',
                   'Description': 'Ultralow-noise LDO: EN and PGFB tied to IN (no fast start-up), ILIM 499 R (~0.3 A)'})
    R(sh, '69.8k', (182.88, 264.16), 'SET', 'GND')
    C(sh, '22u', (195.58, 264.16), 'SET', 'GND', fp=C1206,
      fields=mur('GRM31CR71C226ME15L', 'MLCC 22u 16V X7R 1206 (C_SET: lowest 1/f noise, ~4 s soft start)'))
    C(sh, '22u', (215.9, 243.84), 'VREG', 'GND', fp=C1210,
      fields=mur('GRM32ER71E226KE15L', 'MLCC 22u 25V X7R 1210 (LT3045 COUT >= 10 uF effective)'))
    sh.add('L1', f'{LIB}:CMC_SRF1260', 'CMC', (241.3, 223.52),
           {1: 'VREG', 3: '+9V_OUT', 2: 'GND', 4: 'OUT_N'},
           footprint='Inductor_SMD:L_CommonModeChoke_Bourns_SRF1260',
           fields={'Manufacturer': 'Bourns', 'MPN': 'SRF1260-102M',
                   'Description': 'Common-mode choke 1 mH, keeps RF off the output cable'})
    sh.add('D5', 'Diode:SMAJ12A', 'SMAJ12A', (256.54, 262.89), {1: '+9V_OUT', 2: 'OUT_N'}, rot=270,
           footprint='Diode_SMD:D_SMA',
           fields={'Manufacturer': 'Littelfuse', 'MPN': 'SMAJ12A', 'Description': 'TVS 12 V, output clamp'})
    sh.add('J2', 'Connector_Generic:Conn_01x02', 'DC OUT', (274.32, 241.3), {1: '+9V_OUT', 2: 'OUT_N'},
           stubs={1: 5 * 2.54},
           footprint='Connector_Molex:Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal',
           fields={'Manufacturer': 'Molex', 'MPN': '43650-0200',
                   'Description': 'Micro-Fit 3.0 2-pin, 6.98 V to the antenna amplifier (shielded pair)'})
    sh.flag('LOAD_P', (160.02, 259.08))
    sh.flag('GND', (231.14, 271.78))
    sh.flag('+9V_OUT', (243.84, 271.78))

    # ---- added in the reed-relay revision (numbered last: existing refs unchanged) ----
    C(sh, '220n', (208.28, 160.02), 'GATE_A', 'GND_C', fields=mur('GRM21BR71H224KA01L', 'MLCC 220n 50V X7R 0805 (gate A hold)'))
    C(sh, '220n', (243.84, 160.02), 'GATE_B', 'GND_C', fields=mur('GRM21BR71H224KA01L', 'MLCC 220n 50V X7R 0805 (gate B delay)'))
    R(sh, '470k', (236.22, 129.54), 'SW_R', 'GATE_B',
      fields=pana('ERJ-6ENF4703V', 'Thick film 470k 1% 0805: bucket B arrival delay with C21'))
    for i, (cn, coil) in enumerate((('COIL_A2', 'COIL_A'), ('COIL_B2', 'COIL_B'))):
        R(sh, '47', (345.44 + i * 30.48, 182.88), cn, coil, rot=90,
          fields=pana('ERJ-6ENF47R0V', 'Thick film 47R 1% 0805: two 5 V coils in series from 12 V (27 mA, '
                      'pull-in margin kept at 85 C)'))
    for i, (src, dst) in enumerate((('LOAD_A', 'LA_D'), ('LOAD_B', 'LB_D'))):
        sh.add(f'D{6 + i}', 'Diode:SS34', 'SS34', (238.76 + i * 50.8, 182.88), {1: dst, 2: src},
               footprint='Diode_SMD:D_SMA',
               fields={'Manufacturer': 'Vishay', 'MPN': 'SS34-E3/57T',
                       'Description': 'Buckets diode-OR onto LOAD_P: the leaving bucket breaks with no current'})

    # ---- added in the review revision (numbered last: existing refs unchanged) ----
    # bucket negative legs through Schottkys: a pair's two reeds are separate switches,
    # and during their skew (or with one welded) a bucket would bridge charger and
    # receiver through the earth loop; each leg now conducts one way only
    for i, (net, a, k) in enumerate((('A_NC', 'A_NC', 'GND_C'), ('A_NL', 'GND', 'A_NL'),
                                     ('B_NC', 'B_NC', 'GND_C'), ('B_NL', 'GND', 'B_NL'))):
        sh.add(f'D{8 + i}', 'Diode:SS34', 'SS34', (297.18 + i * 27.94, 208.28), {1: k, 2: a},
               footprint='Diode_SMD:D_SMA',
               fields={'Manufacturer': 'Vishay', 'MPN': 'SS34-E3/57T',
                       'Description': 'Bucket negative leg, one way only: no charger-receiver loop '
                                      'through earth during reed skew or with a welded reed'})
    # 0.4 A limit between the diode-OR and the reservoir: a bucket arriving charged on a
    # drained reservoir after a mains outage would otherwise make at ~2 A (reed 0.5 A)
    sh.box(285, 216, 348, 252, 'LOAD-PATH LIMITER  0.4 A')
    r_s = R(sh, '1.5', (297.18, 223.52), 'OR_P', 'LIM_S', rot=90, fp=R2512,
      fields={'Manufacturer': 'Vishay', 'MPN': 'CRCW25121R50FKEG', 'Description': 'Limiter sense 1R5 1% 1 W 2512 (0.4 A)'})
    q3 = sh.add('Q3', 'Transistor_FET:Si2319CDS', 'Si2319CDS', (320.04, 233.68), {1: 'LIM_G', 2: 'LIM_S', 3: 'LOAD_P'},
           footprint='Package_TO_SOT_SMD:SOT-23',
           fields={'Manufacturer': 'Vishay', 'MPN': 'Si2319CDS-T1-GE3',
                   'Description': 'Load-path limiter pass FET, P-ch 40 V 4.4 A, VGS +-20 V'})
    q4 = sh.add('Q4', 'Transistor_BJT:MMBT3906', 'MMBT3906', (307.34, 237.49), {1: 'LIM_S', 2: 'OR_P', 3: 'LIM_G'},
           fields_at={'Reference': (-11.43, 5.08, 'left'), 'Value': (-11.43, 7.62, 'left')},
           footprint='Package_TO_SOT_SMD:SOT-23',
           fields={'Manufacturer': 'onsemi', 'MPN': 'MMBT3906LT1G',
                   'Description': 'Limiter sense: turns Q3 down above 0.6 V / 1.5 R = 0.4 A'})
    r_g = R(sh, '100k', (340.36, 238.76), 'LIM_G', 'GND',
      fields_at={'Reference': (-2.54, -1.27, 'right'), 'Value': (-2.54, 1.27, 'right')},
      fields=pana('ERA-6AEB104V', 'Thin film 100k 0.1% 0805: Q3 gate pull-down (Q3 fully on below the limit)'))
    sh.join(q4, 3, q3, 1)
    sh.join(r_g, 1, q3, 1)
    sh.join(q4, 1, r_s, 2)
    R(sh, '499', (172.72, 264.16), 'ILIM', 'GND')
    C(sh, '100n', (238.76, 76.2), 'CC_OUT', 'GND_C')
    for i, net in enumerate(('CHG_D', '+12V_C', 'SWAP', 'GND_C', 'LOAD_P', 'VREG', 'GND')):
        sh.add(f'TP{i + 1}', 'Connector:TestPoint', net, ((294.64 + i * 15.24, 86.36) if i < 4 else (360.68 + (i - 4) * 15.24, 236.22)),
               {1: net}, footprint='TestPoint:TestPoint_Keystone_5000-5004_Miniature',
               fields={'Manufacturer': 'Keystone', 'MPN': '5001' if 'GND' in net else '5000',
                       'Description': f'Test point {net}'})

    sh.box(351, 216, 405, 252, 'RECEIVER TEST POINTS')

    # ---- added in the protection revision (numbered last: existing refs unchanged) ----
    # EDLC overvoltage crowbar: a failed (shorted) LM317 would put 15 V on the buckets
    # (3.75 V per 2.7 V cell). Above CHG = 11.7 V (11.5-11.9 V over tolerance and temperature;
    # bucket ~0.4 V lower, 2.8-2.9 V per cell; normal CV
    # is at most 11.24 V) the TL431 pulls Q5 on, Q5 fires the SCR, and the SCR holds CHG
    # down on the CC stage's 0.2 A (or the IRM's own limit) until mains is removed. D1
    # keeps the buckets from discharging into it.
    sh.box(112, 105, 168, 195, 'CROWBAR  CHG > 11.7 V')
    r29 = R(sh, '36.5k', (119.38, 124.46), 'CHG', 'CB_REF',
            fields=pana('ERA-6AEB3652V', 'Thin film 36k5 0.1% 0805: crowbar divider top (trip 11.7 V)'))
    r30 = R(sh, '10k', (119.38, 149.86), 'CB_REF', 'GND_C',
            fields=pana('ERA-6AEB103V', 'Thin film 10k 0.1% 0805: crowbar divider bottom'))
    c23 = C(sh, '100n', (129.54, 149.86), 'CB_REF', 'GND_C', fields_at={'Reference': (1.905, -1.27, 'left'), 'Value': (1.905, 1.27, 'left')})
    u6 = sh.add('U6', 'Reference_Voltage:TL431DBZ', 'TL431B', (144.78, 160.02), {1: 'CB_K', 2: 'CB_REF', 3: 'GND_C'}, rot=90,
                fields_at={'Reference': (-1.27, -10.16, 'left'), 'Value': (-1.27, -7.62, 'left')},
                footprint='Package_TO_SOT_SMD:SOT-23',
                fields={'Manufacturer': 'Texas Instruments', 'MPN': 'TL431BIDBZR',
                        'Description': 'Shunt reference 0.5 %, crowbar threshold (DBZ: 1 K, 2 REF, 3 A)'})
    r31 = R(sh, '680', (144.78, 119.38), 'CHG', 'CB_B',
            fields=pana('ERJ-6ENF6800V', 'Thick film 680R 1% 0805: Q5 base-emitter (TL431 >= 1 mA before Q5 turns on)'))
    r32 = R(sh, '1k', (144.78, 142.24), 'CB_B', 'CB_K',
            fields=pana('ERJ-6ENF1001V', 'Thick film 1k 1% 0805: Q5 base current limit'))
    q5 = sh.add('Q5', 'Transistor_BJT:MMBT3906', 'MMBT3906', (152.4, 129.54), {1: 'CB_B', 2: 'CHG', 3: 'CB_C'},
                mirror='x', footprint='Package_TO_SOT_SMD:SOT-23',
                fields={'Manufacturer': 'onsemi', 'MPN': 'MMBT3906LT1G', 'Description': 'Crowbar gate driver (PNP)'})
    r33 = R(sh, '470', (154.94, 149.86), 'CB_C', 'CB_G',
            fields=pana('ERJ-6ENF4700V', 'Thick film 470R 1% 0805: SCR gate current ~20 mA'))
    c24 = C(sh, '100n', (144.78, 182.88), 'CB_G', 'GND_C', fields_at={'Reference': (1.905, -1.27, 'left'), 'Value': (1.905, 1.27, 'left')})
    r34 = R(sh, '1k', (154.94, 182.88), 'CB_G', 'GND_C',
            fields=pana('ERJ-6ENF1001V', 'Thick film 1k 1% 0805: SCR gate-cathode (dv/dt, leakage)'))
    q6 = sh.add('Q6', f'{LIB}:SCR_MCR100', 'MCR100-6', (129.54, 182.88), {3: 'CHG', 1: 'GND_C', 2: 'CB_G'},
                mirror='y', fields_at={'Reference': (-5.08, -3.81, 'left'), 'Value': (-5.08, -1.27, 'left')}, footprint='Package_TO_SOT_THT:TO-92',
                fields={'Manufacturer': 'onsemi / UTC', 'MPN': 'MCR100-6G',
                        'Description': 'SCR 400 V 0.8 A TO-92 (1 K, 2 G, 3 A): EDLC overvoltage crowbar on CHG'})
    sh.join(r29, 2, r30, 1)
    sh.join(r30, 1, c23, 1)
    sh.join(r32, 2, u6, 1)
    sh.join(r32, 1, q5, 1)
    sh.join(r31, 2, q5, 1)
    sh.join(q5, 3, r33, 1)
    sh.join(r33, 2, r34, 1)
    sh.join(c24, 1, r34, 1)
    sh.join(q6, 2, c24, 1)
    # surge path between the PE-bonded charger ground and the receiver ground: the two
    # earths (mains PE and the receiver's own earth rod) can differ by kV in a nearby
    # strike; the GDT sparks over instead of the 1 mm charger/receiver barrier or a reed
    sh.add('GDT1', 'Device:GDT_2Pin', '150V', (127.0, 81.28), {1: 'GND_C', 3: 'GND'},
           footprint='elara:GDT_Bourns_2051',
           fields={'Manufacturer': 'Bourns', 'MPN': '2051-15-SM-RPLF',
                   'Description': 'GDT 150 V +-30 % DC sparkover, < 0.5 pF, 2 kA 8/20: GND_C/PE to receiver GND'})
    return p


def main():
    p = build()
    p.write()
    comps = [{'ref': pl.ref, 'value': pl.value, 'footprint': pl.footprint, 'lib_id': pl.sym.lib_id,
              'sheet': s.name, 'sheet_uuid': s.uuid, 'uuid': pl.uuid, 'dnp': pl.dnp, 'fields': pl.fields,
              'pins': dict(pl.nets)} for s in p.sheets for pl in s.symbols]
    with open(os.path.join(HERE, 'design_netlist.json'), 'w', encoding='utf-8') as f:
        json.dump({'project': p.name, 'root_uuid': p.root_uuid, 'components': comps}, f, indent=1)
    print(f'{len(comps)} components, {len(p.netlist())} nets written')
    if '--no-check' not in sys.argv:
        from kicadgen.netcheck import compare, export_netlist, exported_nets, record_kicad_names
        exported = exported_nets(export_netlist(os.path.join(HERE, f'{NAME}.kicad_sch')))
        problems = compare(p.netlist(), exported)
        record_kicad_names(os.path.join(HERE, 'design_netlist.json'), p.netlist(), exported)
        print('\n'.join(problems) if problems else 'net list check: KiCad connectivity matches design')
        sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
