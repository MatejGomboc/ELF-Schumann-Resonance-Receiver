#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA -- two-bucket PSU: ngspice netlist generator and runner.

The netlist follows PCB/acdc_converter/design.py (charger, buckets, relays,
LT3045 receiver side) and PCB/antenna_amplifier/design.py (SS34, bulk caps,
two ADM7150 regulators).  All vendor parts are behavioural; every assumed
number is a parameter below and is listed in README.md.

run_psu.py imports this module; `python psu_model.py` just writes the
nominal steady-state netlist psu_two_bucket.cir (runs standalone with
`ngspice -b psu_two_bucket.cir`).

Licence: CERN-OHL-W-2.0
"""

import os
import subprocess
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Nominal parameters (value, meaning).  Units SI.
# ---------------------------------------------------------------------------
NOMINAL = {
    # charger (GND_C side)
    "VIRM": 15.0,        # IRM-05-15 output
    "VCV": 10.40,        # LM317 CV set point 1.25*(1+1.74k/240) + 50 uA*1.74k (2.6 V per cell)
    "ICC": 1.25 / 6.2,   # LM317 CC set, 0.2016 A (total, incl. CV divider current)
    "RCV": 0.02,         # CV output resistance (LM317 typ ~ 10 mOhm + wiring)
    "RCS": 6.2,          # CC sense resistor (1.25 V at ICC; below ICC U1 is in dropout and drops RCS*I)
    "VDO0": 1.55,        # LM317 dropout at zero current (each of U1, U2), 25 degC
    "RDO": 0.6,          # LM317 dropout slope (V/A), i.e. 1.67 V at 0.2 A
    "RDIV": 1980.0,      # 240 R + 1.74 k divider on CHG
    "CCHG": 100e-9,      # C3 on CHG (rev 0.1 had 10 uF: the cold-start contact spike)
    "RSER": 2.2,         # 2.2 R in every bucket path (charger and load)
    "RCON": 0.05,        # relay contact resistance (G6K max 100 mOhm)
    # buckets: 4 x 10 F in series
    "CB": 2.5,
    "RESRB": 4 * 0.05,   # bucket ESR (4 cells x 50 mOhm nominal)
    "RBAL": 4 * 5.1e3,   # passive balancing chain
    # receiver side
    "CRES": 2200e-6, "ESRRES": 0.025,
    "CIN10": 10e-6,
    "VSETLT": 6.98, "RSET": 69.8e3, "CSET": 22e-6, "ISET": 100e-6,   # as built (rev 0.2)
    "VDOLT": 0.30, "IDOLT": 0.10,   # LT3045 dropout 0.3 V at 0.1 A (resistive, 3 Ohm)
    "IQLT": 2.3e-3,
    "CVREG": 10e-6,
    "RPATH": 7.2,        # CMC loop: SRF1260-102M both windings 6.78 R (datasheet, series) + 0.4 R cable
    # amplifier board
    "CBULK": 100e-6, "ESRBULK": 0.3, "CIN_AMP": 30e-6,
    "V5": 5.0, "V33": 3.3,
    "VDOADM": 0.15,      # ADM7150 dropout at 40-45 mA (behavioural)
    "IQADM": 5e-3,       # ADM7150 ground current each (assumed, pessimistic)
    "ILOAD5": 40e-3, "ILOAD33": 45e-3,
    # timing
    "THALF": 15.19,      # CD4060: 1/(2.3*80.6k*10n) = 539 Hz, Q14 toggles every 8192 clocks
}

# rev 0.1, which these simulations started from: LT3045 at 8.45 V (R_SET 84.5k), a
# 30 s swap (CD4060 Rt 160k), 10 uF on CHG and the charger set to 11.08 V (240 R / 1.87 k,
# which floats the 2.7 V cells at 2.72 V with no load). Kept as a history case in run_psu.py.
REV01 = {"VSETLT": 8.45, "RSET": 84.5e3, "THALF": 30.1, "CCHG": 10e-6, "VCV": 11.08, "RDIV": 2110.0}

# Relay timing (seconds): break delay after coil edge, transit (break -> make)
RELAY_NOMINAL = {
    "K1": {"op_break": 2.0e-3, "rel_break": 1.5e-3, "transit": 3.0e-3},
    "K2": {"op_break": 2.0e-3, "rel_break": 1.5e-3, "transit": 3.0e-3},
}

SAVE_VECS = ["v(a_p)", "v(a_n)", "v(b_p)", "v(b_n)", "v(load_p)", "v(rgnd)", "v(vreg)",
             "v(set)", "v(p9)", "v(p5)", "v(p33)", "v(chg)", "v(v15)",
             "i(vk1nc)", "i(vk1no)", "i(vk2nc)", "i(vk2no)", "i(vlt)", "i(vchg)"]


def coil_edges(t_end, thalf, t_fail=None, first_on=None):
    """Coil on/off intervals.  Coil is OFF at t=0 and toggles every thalf.
    After t_fail the coil is off for good (no +12 V_C)."""
    t0 = thalf if first_on is None else first_on
    ons = []
    t = t0
    while t < t_end:
        ons.append((t, t + thalf))
        t += 2 * thalf
    if t_fail is not None:
        cut = []
        for a, b in ons:
            if a >= t_fail:
                break
            cut.append((a, min(b, t_fail)))
        ons = cut
    return ons


def pwl_contact(ons, t_end, relay, closed_when_on, ramp=20e-6):
    """PWL control (1 = contact closed) for one contact of a form-C relay.

    NO contact: closes op_break+transit after coil on, opens rel_break after off.
    NC contact: opens op_break after coil on, closes rel_break+transit after off.
    """
    ob, rb, tr = relay["op_break"], relay["rel_break"], relay["transit"]
    pts = []
    if closed_when_on:            # NO
        state0 = 0.0
        events = []
        for a, b in ons:
            events.append((a + ob + tr, 1.0))
            events.append((b + rb, 0.0))
    else:                         # NC
        state0 = 1.0
        events = []
        for a, b in ons:
            events.append((a + ob, 0.0))
            events.append((b + rb + tr, 1.0))
    pts.append((0.0, state0))
    cur = state0
    for t, s in events:
        if t >= t_end:
            break
        pts.append((t, cur))
        pts.append((t + ramp, s))
        cur = s
    pts.append((t_end + 1.0, cur))
    return " ".join(f"{t:.10g} {v:g}" for t, v in pts)


def netlist(p=None, relays=None, t_end=180.0, tmax=20e-3, ic=None, t_fail=None,
            first_on=None, control=None, title="ELARA two-bucket PSU"):
    q = dict(NOMINAL)
    if p:
        q.update(p)
    rl = {k: dict(v) for k, v in RELAY_NOMINAL.items()}
    if relays:
        for k, v in relays.items():
            rl[k].update(v)
    ic = ic or {}
    ons = coil_edges(t_end, q["THALF"], t_fail, first_on)
    k1no = pwl_contact(ons, t_end, rl["K1"], True)
    k1nc = pwl_contact(ons, t_end, rl["K1"], False)
    k2no = pwl_contact(ons, t_end, rl["K2"], True)
    k2nc = pwl_contact(ons, t_end, rl["K2"], False)
    if t_fail is None:
        v15 = f"dc {q['VIRM']}"
    else:
        v15 = f"pwl(0 {q['VIRM']} {t_fail} {q['VIRM']} {t_fail + 5e-3} 0)"
    ica = ic.get("va", 0.0)
    icb = ic.get("vb", 0.0)
    icres = ic.get("vres", 0.0)
    icset = ic.get("vset", 0.0)
    icreg = ic.get("vreg", 0.0)
    icp9 = ic.get("vp9", 0.0)
    icchg = ic.get("vchg", 0.0)
    r = 5.0 / q["ILOAD5"] * q["V5"] / 5.0
    r33 = q["V33"] / q["ILOAD33"]
    txt = f"""* {title}
* generated by simulations/psu/psu_model.py -- behavioural model, see README.md
* GND_C (charger side, PE bonded) = node 0 ; receiver GND = node rgnd
{OPT_TIGHT}
.param VIRM={q['VIRM']} VCV={q['VCV']} ICC={q['ICC']} RCV={q['RCV']} RCS={q['RCS']}
.param VDO0={q['VDO0']} RDO={q['RDO']}
.func sminv(a,b) {{0.5*(a+b-sqrt((a-b)*(a-b)+1e-6))}}
.func smaxv(a,b) {{0.5*(a+b+sqrt((a-b)*(a-b)+1e-6))}}
.func smini(a,b) {{0.5*(a+b-sqrt((a-b)*(a-b)+1e-8))}}
.func smaxi(a,b) {{0.5*(a+b+sqrt((a-b)*(a-b)+1e-8))}}
* (smooth min/max, 1 mV / 0.1 mA knee, keep the Newton iteration happy)
.model SS34 D(IS=2.6u N=1.1 RS=0.05 BV=40)
* relay contact resistance {q['RCON']} Ohm
* relay contact = conductance ramped by its control voltage (0 open, 1 closed, 20 us ramp)

* ---- IRM-05-15 and LM317 CC (0.2 A) -> LM317 CV ({q['VCV']} V) charger ----------
V15 v15 0 {v15}
* charger current = min(CC, CV, dropout-limited): both LM317s need VDO0+RDO*I, and
* the CC stage also drops RCS*I across its sense resistor (1.25 V at ICC)
Bchg 0 chg_i I = smaxi(0, smini(ICC, smini((VCV - v(chg))/RCV, (v(v15) - 2*VDO0 - v(chg))/(2*RDO + RCS))))
Vchg chg_i chg 0
Rdiv chg 0 {q['RDIV']}
Cchg chg 0 {q['CCHG']}
D1 chg chg_d SS34
Rca chg_d chg_a {q['RSER']}
Rcb chg_d chg_b {q['RSER']}
* strays on nodes that float while a relay is in transit (numerical only)
Cs1 chg_d 0 1n
Cs2 chg_a 0 1n
Cs3 chg_b 0 1n

* ---- buckets: 2.5 F (4 x 10 F), ESR, 4 x 5.1k balancing -------------------
CA a_c a_n {q['CB']} ic={ica}
RA a_p a_c {q['RESRB']}
RBA a_p a_n {q['RBAL']}
CB b_c b_n {q['CB']} ic={icb}
RB b_p b_c {q['RESRB']}
RBB b_p b_n {q['RBAL']}
* strays that keep a bucket's potential defined while both its relays are open
* (10 nF / 100 MOhm to each ground: ~0.1 uA, numerically only)
CsA1 a_n 0 10n
CsA2 a_n rgnd 10n
RsA1 a_n 0 1e8
RsA2 a_n rgnd 1e8
CsB1 b_n 0 10n
CsB2 b_n rgnd 10n
RsB1 b_n 0 1e8
RsB2 b_n rgnd 1e8

* ---- relays (form C, break before make); K2 wired opposite to K1 ----------
* K1: A_P NC->CHG_A NO->LOAD_A ; A_N NC->GND_C NO->GND
Vk1nc a_p k1nc 0
B1a k1nc chg_a I = v(k1nc,chg_a)*(v(c_k1nc)*{1/q['RCON']} + 1e-9)
Vk1no a_p k1no 0
B1b k1no load_a I = v(k1no,load_a)*(v(c_k1no)*{1/q['RCON']} + 1e-9)
B1c a_n 0 I = v(a_n,0)*(v(c_k1nc)*{1/q['RCON']} + 1e-9)
B1d a_n rgnd I = v(a_n,rgnd)*(v(c_k1no)*{1/q['RCON']} + 1e-9)
* K2: B_P NC->LOAD_B NO->CHG_B ; B_N NC->GND NO->GND_C
Vk2nc b_p k2nc 0
B2a k2nc load_b I = v(k2nc,load_b)*(v(c_k2nc)*{1/q['RCON']} + 1e-9)
Vk2no b_p k2no 0
B2b k2no chg_b I = v(k2no,chg_b)*(v(c_k2no)*{1/q['RCON']} + 1e-9)
B2c b_n rgnd I = v(b_n,rgnd)*(v(c_k2nc)*{1/q['RCON']} + 1e-9)
B2d b_n 0 I = v(b_n,0)*(v(c_k2no)*{1/q['RCON']} + 1e-9)
Vc1 c_k1no 0 pwl({k1no})
Vc2 c_k1nc 0 pwl({k1nc})
Vc3 c_k2no 0 pwl({k2no})
Vc4 c_k2nc 0 pwl({k2nc})
* galvanic isolation between GND_C and receiver GND (DC reference only)
Riso rgnd 0 1e9

* ---- receiver side: 2.2 R per bucket -> reservoir -> LT3045 ---------------
Rla load_a load_p {q['RSER']}
Rlb load_b load_p {q['RSER']}
Cs4 load_a rgnd 1n
Cs5 load_b rgnd 1n
Cres load_p cres_e {q['CRES']} ic={icres}
Rres cres_e rgnd {q['ESRRES']}
C10 load_p rgnd {q['CIN10']} ic={icres}
* LT3045: SET = 100 uA into RSET||CSET (soft start); VOUT = min(VSET, VIN - Rdo*I)
Bset rgnd set I = {q['ISET']}/(1+exp(-(v(load_p,rgnd)-2.0)/0.05))
Rset set rgnd {q['RSET']}
Cset set rgnd {q['CSET']} ic={icset}
Blt lt_i rgnd V = smaxv(0, sminv(v(set,rgnd), v(load_p,rgnd) - {q['VDOLT']/q['IDOLT']}*i(Vlt)))
Vlt lt_i vreg 0
Bltin load_p rgnd I = smaxi(i(Vlt),0) + {q['IQLT']}/(1+exp(-(v(load_p,rgnd)-2.0)/0.05))
Cvreg vreg rgnd {q['CVREG']} ic={icreg}
* common-mode choke DCR + cable
Rpath vreg vc {q['RPATH']}

* ---- amplifier board: SS34, bulk caps, 2 x ADM7150 --------------------------
D101 vc p9 SS34
Cbulk p9 cb_e {q['CBULK']} ic={icp9}
Rbulk cb_e rgnd {q['ESRBULK']}
Cinamp p9 rgnd {q['CIN_AMP']} ic={icp9}
B5 a5_i rgnd V = smaxv(0, sminv({q['V5']}, v(p9,rgnd) - {q['VDOADM']}))
V5s a5_i p5 0
R5 p5 rgnd {r}
C5 p5 rgnd 10u
B33 a33_i rgnd V = smaxv(0, sminv({q['V33']}, v(p9,rgnd) - {q['VDOADM']}))
V33s a33_i p33 0
R33 p33 rgnd {r33}
C33 p33 rgnd 10u
Badm p9 rgnd I = smaxi(i(V5s),0) + smaxi(i(V33s),0) + {2*q['IQADM']}/(1+exp(-(v(p9,rgnd)-2.0)/0.05))

.ic v(chg)={icchg}
"""
    if control is None:
        control = (f".control\nset filetype=ascii\ntran 1m {t_end} 0 {tmax} uic\n"
                   f"write psu_two_bucket.raw {' '.join(SAVE_VECS)}\n.endc\n")
    return txt + control + ".end\n"


def parse_raw(path):
    with open(path) as fh:
        lines = fh.read().splitlines()
    i = 0
    nv = npts = 0
    names = []
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("No. Variables:"):
            nv = int(ln.split(":")[1])
        elif ln.startswith("No. Points:"):
            npts = int(ln.split(":")[1])
        elif ln.startswith("Variables:"):
            for k in range(nv):
                names.append(lines[i + 1 + k].split()[1].lower())
            i += nv
        elif ln.startswith("Values:"):
            i += 1
            break
        i += 1
    tok = " ".join(lines[i:]).split()
    arr = np.array(tok, dtype=float).reshape(npts, nv + 1)[:, 1:]
    return {n: arr[:, k] for k, n in enumerate(names)}


OPT_TIGHT = ".options reltol=1e-4 abstol=1e-9 vntol=1e-7 method=gear maxord=2 itl4=200 gmin=1e-12"
OPT_RELAXED = ".options reltol=1e-3 abstol=1e-8 vntol=1e-6 method=gear itl4=500"


def run(t_end, tmax=20e-3, **kw):
    """Run a transient case, return dict of vectors (time + SAVE_VECS).
    Tries tight tolerances first and falls back to relaxed ones (reltol 1e-3)
    if the Newton iteration fails at a relay edge."""
    last = ""
    for opt in (OPT_TIGHT, OPT_RELAXED):
        with tempfile.TemporaryDirectory(prefix="elara_psu_") as wd:
            raw = os.path.join(wd, "out.raw")
            ctl = (f".control\nset filetype=ascii\ntran 1m {t_end} 0 {tmax} uic\n"
                   f"write {raw} {' '.join(SAVE_VECS)}\nquit\n.endc\n")
            net = netlist(t_end=t_end, tmax=tmax, control=ctl, **kw).replace(OPT_TIGHT, opt)
            cir = os.path.join(wd, "psu.cir")
            with open(cir, "w") as fh:
                fh.write(net)
            res = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True, cwd=wd)
            out = res.stdout + res.stderr
            if res.returncode == 0 and os.path.exists(raw) and "aborted" not in out:
                d = parse_raw(raw)
                d["_options"] = opt
                return d
            last = out
    raise RuntimeError("ngspice failed:\n" + last[-3000:])


if __name__ == "__main__":
    path = os.path.join(HERE, "psu_two_bucket.cir")
    with open(path, "w") as fh:
        v = NOMINAL["VSETLT"]
        fh.write(netlist(t_end=180.0, ic={"va": 9.44, "vb": 10.06, "vres": 9.21, "vset": v,
                                          "vreg": v, "vp9": v - 0.35, "vchg": NOMINAL["VCV"]}))
    print("written", path)
