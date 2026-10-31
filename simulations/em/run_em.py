#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA -- electromagnetic studies of the outdoor unit

  1. Electrostatic 3-D field solve of the guarded input (real copper from
     PCB/antenna_amplifier/antenna_amplifier.kicad_pcb, JLCPCB 4-layer stack-up,
     compartment-1 walls, lid and tray as the boundary): capacitance from IN_P
     to every nearby net with the driven guard, without it (GND planes under the
     island) and with bare inner layers.  Injected signal for each aggressor,
     referred to the antenna and compared with the receiver noise floor.
  2. Shielding effectiveness of the aluminium shield, 1 Hz - 100 MHz:
     Schelkunoff (exact transmission-line form) for near-field E and H sources,
     the closed-box low-frequency magnetic limit, and aperture leakage (RJ45
     cut-out, lid seams, PTFE feed-through).  50 Hz E-field pickup on IN_P through
     the shield compared with the 29.5 mV rms clip level (simulations/system).
  3. 50 Hz magnetic induction into the front-end loops (board loop from the
     layout, the node-2 flying lead and GND wire from the mechanical layout) and
     into the AES3 cable.
  4. Clock and digital emissions: synchronous-alias argument, RF rectification
     (EMIRR) of the 24.576 MHz clock and the AES3 stream, PSU relay coils and
     charger loops as magnetic sources at their real distance.
  5. The air-gap plate capacitor: 3-D solve of the square plates (params.PLATE_CU)
     (corner reliefs, solder mask, FR4 backing), fringing against the
     parallel-plate formula, and dC/dgap.

Writes results.json and five SVG plots next to this script.  Runs in about
2-3 minutes with pyamg installed (scipy-only fallback is slower).

Licence: CERN-OHL-W-2.0
"""

import json
import math
import os
import sys
import time

import numpy as np

import os as _os  # noqa: E402
_os.environ.setdefault("SOURCE_DATE_EPOCH", "0")   # fixed SVG date: no churn on re-runs
import matplotlib  # noqa: E402
matplotlib.rc_file(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "matplotlibrc"))
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
import em_lib as L  # noqa: E402
import params as MP  # noqa: E402

PCB_AMP = os.path.join(ROOT, "PCB", "antenna_amplifier", "antenna_amplifier.kicad_pcb")
PCB_PSU = os.path.join(ROOT, "PCB", "acdc_converter", "acdc_converter.kicad_pcb")

# ---------------------------------------------------------------------------
# Plot style (same palette as simulations/system and simulations/psu)
# ---------------------------------------------------------------------------
BG = "#0d1117"
TEXT = "#e6edf3"
SUBTLE = "#7d8590"
PANEL = "#161b22"
BORDER = "#30363d"
GREEN = "#7ee787"
BLUE = "#79c0ff"
PURPLE = "#d2a8ff"
RED = "#ff7b72"
YELLOW = "#f2cc60"
ORANGE = "#ffa657"
GREY = "#8b949e"

MU0 = 4e-7 * math.pi
EPS0 = L.EPS0
ETA0 = 376.73
C0 = 299792458.0
SCHUMANN = [7.83, 14.3, 20.8, 27.3, 33.8, 39.0, 45.0]

# ---------------------------------------------------------------------------
# Assumptions (sources in README.md section 1)
# ---------------------------------------------------------------------------
# JLCPCB JLC04161H-7628 4-layer 1.6 mm stack-up: 7628 prepreg 0.2104 mm, core 1.065 mm,
# inner copper 0.0152 mm; Dk 4.4 (prepreg) / 4.6 (core) from JLCPCB's impedance tool
STACK = dict(pp=0.2104, core=1.065, cu_in=0.0152, er_pp=4.4, er_core=4.6)
Z_F = 0.0
Z_IN1 = -STACK["pp"]
Z_IN2 = Z_IN1 - STACK["cu_in"] - STACK["core"]
Z_B = Z_IN2 - STACK["cu_in"] - STACK["pp"]
LAYER_Z = {"F.Cu": Z_F, "In1.Cu": Z_IN1, "In2.Cu": Z_IN2, "B.Cu": Z_B}

# compartment 1 (mechanical/params.py): inner wall faces, lid and tray floor
C1 = MP.COMPARTMENTS["C1 INPUT"]
Z_LID = MP.FRAME_H                     # lid underside, 52 mm above the board top
Z_TRAY = Z_B - MP.TRAY_DEPTH           # tray floor, 12 mm under the board
WINDOW_Y = (27.0, 64.0)                # solve window in y (Neumann ends), island 36.4-54.6
FINE = dict(x=(13.5, 39.5), y=(32.5, 58.5))
H_FINE = 0.125                         # mm, main grid
H_CHECK = 0.1875                       # mm, grid-convergence check
J202_PIN_TOP = 8.5                     # 2.54 mm header: 2.5 mm body + 6 mm pin above the board
TURRET_LEAD_D = 1.0                    # node-2 lead through the Ø1.2 mm PTFE bore
BUSH_HOLE_D = MP.FEEDTHROUGH_HOLE_D

# front end (PCB/antenna_amplifier/design.py, simulations/system)
FE = dict(C_ANT=140e-12, R1=33e3, R3=33e3, CF1=50e-12, CF2=50e-12, R_HB=100e9, R_LEAK=1e12)
G_IN_BAND = 101.0
C_IN_OPAMP = 10e-12                    # LMP7721 input C, assumed (as simulations/spice 4.3)
NOISE_ANT = dict(zip(SCHUMANN, [45.8e-9, 43.3e-9, 42.6e-9, 42.3e-9, 42.1e-9, 42.0e-9, 42.0e-9]))
BIN = 0.1                              # Hz, line-detection bin used for comparisons

# aluminium EN AW-6082 T6: 24-26 MS/m (about 42-45 % IACS)
SIGMA_AL = 2.5e7
T_LID = MP.LID_T
T_WALL = MP.WALL_T
T_TRAY = MP.TRAY_FLOOR_T

# 50 Hz environment
B50 = (0.1e-6, 1e-6)                   # T rms near a house
E50_LOCAL = (1.0, 10.0, 100.0)         # V/m rms at the shield surface (rural / domestic / unscreened cable)
MAINS_PICKUP = (1e-3, 5e-3)            # V rms at the antenna (PLAN 3.1)

# digital (PLAN 3.5/3.6, design.py)
F_MCLK = 24.576e6
FS = 192e3
F_MOD = 32 * FS                        # PCM1804 quad-rate modulator, 32x oversampling
AES3_BIT = 64 * FS                     # 12.288 Mbit/s, biphase-mark -> 24.576 MHz cell edges
# DC across each plate capacitor (microphonics scale with it): lower plates on PLATE_RET
# (BIAS_BUF via 100 k) leave only the air-earth current x J202 (10 G)
V_GAP_DC = 0.03          # V, 3 pA typical
V_GAP_DC_WORST = 1.0     # V, 100 pA (the DC-point limit of a 10 G J202)
V_GAP_DC_GND = 2.27      # V, lower plates on GND (before the change)
EMIRR_DB = 30.0                        # LMP7721 EMIRR IN+ at 6-100 MHz: not specified, assumed low


def p(*a):
    print(*a, flush=True)


# ===========================================================================
# Front-end network
# ===========================================================================
def frontend(f, c_extra=0.0, fe=FE):
    """EMF -> IN_P transfer and IN_P node impedance (3-node network of simulations/system)."""
    f = np.atleast_1d(np.asarray(f, float))
    s = 2j * np.pi * f
    g1, g3 = 1 / fe["R1"], 1 / fe["R3"]
    Y = np.zeros((len(f), 3, 3), complex)
    Y[:, 0, 0] = s * fe["C_ANT"] + g1
    Y[:, 0, 1] = Y[:, 1, 0] = -g1
    Y[:, 1, 1] = g1 + g3 + s * fe["CF1"]
    Y[:, 1, 2] = Y[:, 2, 1] = -g3
    Y[:, 2, 2] = g3 + s * (fe["CF2"] + c_extra) + 1 / fe["R_HB"] + 1 / fe["R_LEAK"]
    Z = np.linalg.inv(Y)
    return Z[:, 2, 0] * s * fe["C_ANT"], Z[:, 2, 2]


def inject_to_antenna(f, c_c, v_agg, c_extra=0.0):
    """Aggressor voltage v_agg coupled by c_c into IN_P, referred to the antenna EMF."""
    h, z = frontend(f, c_extra)
    return np.abs(2j * np.pi * np.atleast_1d(f) * c_c * z / h) * v_agg


def floor_ant(f):
    """Receiver noise at the antenna (V/rtHz), nominal build (simulations/spice)."""
    return np.interp(f, SCHUMANN, list(NOISE_ANT.values()))


# ===========================================================================
# 1. Guarded input -- 3-D electrostatic solve
# ===========================================================================
def island_grid(h):
    xs = L.graded_axis(C1["x0"], C1["x1"], *FINE["x"], h, 0.8, 1.3)
    ys = L.graded_axis(*WINDOW_Y, *FINE["y"], h, 0.8, 1.3)
    zb = [Z_F, Z_F - STACK["pp"] / 2, Z_IN1] + list(np.linspace(Z_IN1, Z_IN2, 7)[1:-1]) + \
         [Z_IN2, (Z_IN2 + Z_B) / 2, Z_B]
    up, z, dz = [], Z_F, 0.0625
    while z + dz < Z_LID - 0.3 * dz:
        z += dz
        up.append(z)
        dz = min(dz * 1.35, 6.0)
    dn, z, dz = [], Z_B, 0.0625
    while z - dz > Z_TRAY + 0.3 * dz:
        z -= dz
        dn.append(z)
        dz = min(dz * 1.35, 3.0)
    zs = np.unique(np.round(np.concatenate([[Z_TRAY], dn, zb, up, [J202_PIN_TOP, Z_LID]]), 6))
    zc = 0.5 * (zs[:-1] + zs[1:])
    eps = np.where((zc < Z_F) & (zc > Z_IN1), STACK["er_pp"],
                   np.where((zc < Z_IN1) & (zc > Z_IN2), STACK["er_core"],
                            np.where((zc < Z_IN2) & (zc > Z_B), STACK["er_pp"], 1.0)))
    return xs, ys, zs, eps


def build_island(board, h, variant):
    """variant: 'guard' (as built), 'gnd' (guard copper removed, GND planes fill the
    island on In1/In2), 'bare' (guard copper removed, nothing under the island)."""
    xs, ys, zs, eps = island_grid(h)
    S = L.Laplace3D(xs, ys, zs, eps)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    kz = {lay: int(np.argmin(np.abs(zs - z))) for lay, z in LAYER_Z.items()}
    kF, kB = kz["F.Cu"], kz["B.Cu"]
    names = ["LID", "TRAY", "WALL"]
    ids = {}

    def cid(net):
        if net not in ids:
            ids[net] = len(names)
            names.append(net)
        return ids[net]

    S.cond[0, :, :] = 2
    S.cond[-1, :, :] = 2
    S.cond[:, :, -1] = 0
    hole = (X - 20.0) ** 2 + (Y - 50.1) ** 2 <= (BUSH_HOLE_D / 2) ** 2
    bot = S.cond[:, :, 0]
    bot[~hole] = 1
    bot[hole] = -1
    xr = (xs[0] - 1, xs[-1] + 1)
    yr = (ys[0] - 1, ys[-1] + 1)
    is_guard = lambda net: net.endswith("/GUARD")              # noqa: E731
    skip = (lambda net: is_guard(net)) if variant != "guard" else (lambda net: False)
    # GND / guard fills first, signal copper on top (pours already clear signals by 0.3 mm)
    for z in board["zones"]:
        if z["layer"] not in kz:
            continue
        pts = z["pts"]
        if pts[:, 0].max() < xr[0] or pts[:, 0].min() > xr[1] or pts[:, 1].max() < yr[0] or pts[:, 1].min() > yr[1]:
            continue
        net = z["net"]
        if is_guard(net):
            if variant == "bare":
                continue
            if variant == "gnd":
                net = "GND"
        m = L.poly_mask(X, Y, pts)
        S.cond[:, :, kz[z["layer"]]][m] = cid(net)
    rmin = 0.55 * h
    for s in board["segments"]:
        if skip(s["net"]) or s["layer"] not in kz:
            continue
        if max(s["x1"], s["x2"]) < xr[0] or min(s["x1"], s["x2"]) > xr[1] or \
           max(s["y1"], s["y2"]) < yr[0] or min(s["y1"], s["y2"]) > yr[1]:
            continue
        m = L.seg_mask(X, Y, s["x1"], s["y1"], s["x2"], s["y2"], max(s["w"] / 2, rmin))
        S.cond[:, :, kz[s["layer"]]][m] = cid(s["net"])
    for v in board["vias"]:
        if skip(v["net"]) or not (xr[0] < v["x"] < xr[1] and yr[0] < v["y"] < yr[1]):
            continue
        m = (X - v["x"]) ** 2 + (Y - v["y"]) ** 2 <= max(v["d"] / 2, rmin) ** 2
        for k in range(kB, kF + 1):
            S.cond[:, :, k][m] = cid(v["net"])
    for pd in board["pads"]:
        if not pd["net"] or pd["net"].startswith("unconnected") or skip(pd["net"]):
            continue
        if not (xr[0] < pd["x"] < xr[1] and yr[0] < pd["y"] < yr[1]):
            continue
        c = cid(pd["net"])
        m = L.pad_mask(X, Y, pd)
        if "*.Cu" in pd["layers"]:
            for k in kz.values():
                S.cond[:, :, k][m] = c
            r = max(pd["drill"] / 2, rmin)
            mb = (X - pd["x"]) ** 2 + (Y - pd["y"]) ** 2 <= r * r
            for k in range(kB, kF + 1):
                S.cond[:, :, k][mb] = c
            if pd["ref"] == "J202":                                # header pins above the board
                mp_ = (np.abs(X - pd["x"]) <= max(0.32, rmin)) & (np.abs(Y - pd["y"]) <= max(0.32, rmin))
                for k in np.flatnonzero((zs > Z_F) & (zs <= J202_PIN_TOP)):
                    S.cond[:, :, k][mp_] = c
            if pd["ref"] == "J201":                                # node-2 lead down to the tray floor
                ml = (X - pd["x"]) ** 2 + (Y - pd["y"]) ** 2 <= max(TURRET_LEAD_D / 2, rmin) ** 2
                for k in np.flatnonzero(zs < Z_B):
                    S.cond[:, :, k][ml] = c
        else:
            for lay in ("F.Cu", "B.Cu"):
                if lay in pd["layers"]:
                    S.cond[:, :, kz[lay]][m] = c
    # 'gnd' variant: keep the GND fill 0.3 mm clear of the IN_P / ANT_BIAS barrels on the inner layers
    if variant == "gnd":
        g = ids["GND"]
        for pd in board["pads"]:
            if "*.Cu" in pd["layers"] and pd["ref"] in ("J201", "J202"):
                m = L.pad_mask(X, Y, pd, grow=0.3)
                for lay in ("In1.Cu", "In2.Cu"):
                    plane = S.cond[:, :, kz[lay]]
                    plane[m & (plane == g)] = -1
                m = L.pad_mask(X, Y, pd)
                for lay in ("In1.Cu", "In2.Cu"):
                    S.cond[:, :, kz[lay]][m] = ids[pd["net"]]
        for v in board["vias"]:
            if v["net"] != "GND" and v["net"] in ids and xr[0] < v["x"] < xr[1] and yr[0] < v["y"] < yr[1]:
                m = (X - v["x"]) ** 2 + (Y - v["y"]) ** 2 <= (v["d"] / 2 + 0.3) ** 2
                for lay in ("In1.Cu", "In2.Cu"):
                    plane = S.cond[:, :, kz[lay]]
                    mm = m & (plane == g)
                    plane[mm] = -1
                    S.cond[:, :, kz[lay]][(X - v["x"]) ** 2 + (Y - v["y"]) ** 2 <= max(v["d"] / 2, rmin) ** 2] = ids[v["net"]]
    return S, names, kz


def short(net):
    return net.split("/")[-1]


def island_study(board):
    out = {}
    fields = {}
    for variant, h in (("guard", H_FINE), ("gnd", H_FINE), ("bare", H_FINE), ("guard", H_CHECK)):
        t0 = time.time()
        S, names, kz = build_island(board, h, variant)
        inp = names.index("/Electrometer front end/IN_P")
        V, Q = S.solve([{inp: 1.0}], verbose=True)
        q = Q[0]
        caps = {short(names[i]): (-q[i] if i != inp else q[i]) for i in q}
        key = variant if h == H_FINE else f"{variant}_h{h}"
        out[key] = dict(grid_mm=h, nodes=int(S.nx * S.ny * S.nz),
                        C_self_IN_P_pF=caps.pop("IN_P") * 1e12,
                        C_to_pF={k: v * 1e12 for k, v in sorted(caps.items(), key=lambda kv: -kv[1])})
        p(f"    {key:10s} h={h} mm  {S.nx}x{S.ny}x{S.nz}  C_self={out[key]['C_self_IN_P_pF']:.3f} pF "
          f" ({time.time() - t0:.0f} s)")
        if key == "guard":
            fields = dict(V=V[0], xs=S.xs, ys=S.ys, zs=S.zs, cond=S.cond.copy(), names=names, kz=kz)
    return out, fields


def nearest_approach(board, target="IN_P"):
    """Edge-to-edge 2-D distance from any IN_P copper to every other net on the board (mm)."""
    def cloud(net_pred):
        pts, rad = [], []
        for s in board["segments"]:
            if net_pred(s["net"]):
                n = max(2, int(math.hypot(s["x2"] - s["x1"], s["y2"] - s["y1"]) / 0.25) + 1)
                for t in np.linspace(0, 1, n):
                    pts.append((s["x1"] + t * (s["x2"] - s["x1"]), s["y1"] + t * (s["y2"] - s["y1"])))
                    rad.append(s["w"] / 2)
        for v in board["vias"]:
            if net_pred(v["net"]):
                pts.append((v["x"], v["y"]))
                rad.append(v["d"] / 2)
        for pd in board["pads"]:
            if net_pred(pd["net"]):
                pts.append((pd["x"], pd["y"]))
                rad.append(min(pd["w"], pd["h"]) / 2)
        return np.array(pts), np.array(rad)

    tp, tr = cloud(lambda n: short(n) == target)
    nets = sorted({s["net"] for s in board["segments"]} | {pd["net"] for pd in board["pads"]})
    res = {}
    for n in nets:
        if not n or short(n) == target or n.startswith("unconnected"):
            continue
        cp, cr = cloud(lambda m, n=n: m == n)
        if len(cp) == 0:
            continue
        d = np.sqrt(((tp[:, None, :] - cp[None, :, :]) ** 2).sum(-1)) - tr[:, None] - cr[None, :]
        res[short(n)] = float(max(d.min(), 0.0))
    return dict(sorted(res.items(), key=lambda kv: kv[1]))


def aggressor_table(caps, c_extra):
    """Injected level at the antenna for each aggressor (V rms in a 0.1 Hz bin or V/rtHz)."""
    c = caps["C_to_pF"]
    get = lambda k: c.get(k, 0.0) * 1e-12                     # noqa: E731
    f1 = SCHUMANN[0]
    rows = []
    h1, z1 = frontend(f1, c_extra)
    c_node = 1 / abs(2 * np.pi * f1 * z1[0])                   # effective node capacitance at SR1
    # +5V_PRE: ADM7150 noise 100 nV/rtHz at 10 Hz (1/f, simulations/psu) and 1 uV rms 50 Hz (assumed)
    e_rail = 100e-9 * math.sqrt(10 / f1)
    rows.append(dict(aggressor="+5V_PRE", what="ADM7150 noise at SR1 (100 nV/rtHz @10 Hz, 1/f)",
                     C_pF=get("+5V_PRE") * 1e12, v_agg=e_rail, unit="V/rtHz",
                     at_antenna=float(inject_to_antenna(f1, get("+5V_PRE"), e_rail, c_extra)[0])))
    rows.append(dict(aggressor="+5V_PRE", what="50 Hz ripple, 1 uV rms (assumed bound)",
                     C_pF=get("+5V_PRE") * 1e12, v_agg=1e-6, unit="V rms",
                     at_antenna=float(inject_to_antenna(50.0, get("+5V_PRE"), 1e-6, c_extra)[0])))
    # guard: carries the LMP7721 e_n (via IN_N) plus U202's own e_n; the signal itself is bootstrapped
    e_guard = math.hypot(6.5e-9 * math.sqrt(1 + 10 / f1), 5.8e-9 * math.sqrt(1 + 30 / f1))
    rows.append(dict(aggressor="GUARD", what="U202 + LMP7721 e_n on the guard at SR1",
                     C_pF=get("GUARD") * 1e12, v_agg=e_guard, unit="V/rtHz",
                     at_antenna=float(inject_to_antenna(f1, get("GUARD") + get("GUARD_DRV"), e_guard, c_extra)[0])))
    # ANT_BIAS: U203 buffer e_n through 1 k plus divider (5.8 nV/rtHz, 30 Hz corner)
    e_bias = 5.8e-9 * math.sqrt(1 + 30 / f1)
    rows.append(dict(aggressor="ANT_BIAS", what="bias buffer U203 e_n at SR1 (bypasses J202 capacitively)",
                     C_pF=get("ANT_BIAS") * 1e12, v_agg=e_bias, unit="V/rtHz",
                     at_antenna=float(inject_to_antenna(f1, get("ANT_BIAS"), e_bias, c_extra)[0])))
    # PREAMP_OUT: in-band positive feedback -> gain error G*C_c/C_node
    t_fb = G_IN_BAND * get("PREAMP_OUT") / c_node
    rows.append(dict(aggressor="PREAMP_OUT", what="in-band feedback (gain error = G C_c / C_node)",
                     C_pF=get("PREAMP_OUT") * 1e12, v_agg=None, unit="fraction", at_antenna=t_fb))
    # CG node sits at ~Z_cg/(Rg+Z_cg) of the signal -> another gain error
    zcg = 1 / (2 * np.pi * f1 * 100e-6)
    frac_cg = zcg / math.hypot(1e3, zcg)
    rows.append(dict(aggressor="CG", what="Rg/Cg node (~20 % of signal) -> gain error",
                     C_pF=get("CG") * 1e12, v_agg=None, unit="fraction",
                     at_antenna=frac_cg * get("CG") / c_node))
    rows.append(dict(aggressor="IN_N", what="follows IN_P (virtual short): bootstrapped, no injection",
                     C_pF=get("IN_N") * 1e12, v_agg=None, unit="fraction", at_antenna=0.0))
    for r in rows:
        if r["unit"] == "V/rtHz":
            r["floor_at_antenna"] = float(floor_ant(f1))
            r["margin_dB"] = 20 * math.log10(r["floor_at_antenna"] / max(r["at_antenna"], 1e-30))
        elif r["unit"] == "V rms":
            r["floor_at_antenna"] = float(floor_ant(50.0) * math.sqrt(BIN))
            r["margin_dB"] = 20 * math.log10(r["floor_at_antenna"] / max(r["at_antenna"], 1e-30))
    return rows, c_node


def hf_coupling(caps_by_variant):
    """IN_P node at RF: R3 isolates, so the node is Cf2 + op-amp input C + board strays."""
    res = {}
    for var, caps in caps_by_variant.items():
        c = caps["C_to_pF"]
        c_node_hf = FE["CF2"] + C_IN_OPAMP + sum(c.values()) * 1e-12
        res[var] = dict(C_node_HF_pF=c_node_hf * 1e12,
                        out_to_in_fraction=c.get("PREAMP_OUT", 0) * 1e-12 / c_node_hf,
                        supply_to_in_fraction=c.get("+5V_PRE", 0) * 1e-12 / c_node_hf)
    return res


# ===========================================================================
# 2. Shielding effectiveness
# ===========================================================================
def wave_impedance(f, r, kind):
    """|Z_w| of an electric ('E') or magnetic ('H') dipole at distance r, or plane wave."""
    k = 2 * np.pi * f / C0
    kr = k * r
    a = 1 + 1 / (1j * kr)
    b = 1 + 1 / (1j * kr) - 1 / kr ** 2
    if kind == "E":
        return ETA0 * b / a
    if kind == "H":
        return ETA0 * a / b
    return ETA0 * np.ones_like(f, dtype=complex)


def se_schelkunoff(f, t_mm, zw, sigma=SIGMA_AL):
    """Exact transmission-line SE of an infinite sheet (absorption, reflection and
    multiple reflections), dB."""
    w = 2 * np.pi * f
    t = t_mm * 1e-3
    zs = np.sqrt(1j * w * MU0 / sigma)
    gamma = np.sqrt(1j * w * MU0 * sigma)
    rho = (zw - zs) / (zw + zs)
    T = 4 * zw * zs / (zw + zs) ** 2 * np.exp(-gamma * t) / (1 - rho ** 2 * np.exp(-2 * gamma * t))
    return -20 * np.log10(np.abs(T))


def se_terms(f, t_mm, zw, sigma=SIGMA_AL):
    w = 2 * np.pi * f
    delta = np.sqrt(2 / (w * MU0 * sigma)) * 1e3
    A = 8.686 * t_mm / delta
    zs = np.sqrt(1j * w * MU0 / sigma)
    R = 20 * np.log10(np.abs(zw) / (4 * np.abs(zs)))
    return A, R, delta


def se_closed_box_h(f, t_mm, a_eq_mm, sigma=SIGMA_AL):
    """Low-frequency magnetic SE of a closed non-magnetic shell (sphere of radius a):
    |cosh(kt) + (k a / 3) sinh(kt)|, k = (1+j)/delta (Kaden; -> |1 + j w mu0 sigma t a / 3| for t << delta)."""
    w = 2 * np.pi * f
    k = np.sqrt(1j * w * MU0 * sigma)
    t, a = t_mm * 1e-3, a_eq_mm * 1e-3
    return 20 * np.log10(np.abs(np.cosh(k * t) + k * a / 3 * np.sinh(k * t)))


def aperture_se(f, length_mm, depth_mm=0.0, n=1):
    """Far-field aperture SE (Ott): 20 log(lambda / 2L) + 27.3 d/L (waveguide below cut-off), -10 log n."""
    lam = C0 / f
    se = 20 * np.log10(lam / (2 * length_mm * 1e-3)) + 27.3 * depth_mm / length_mm - 10 * np.log10(n)
    return np.maximum(se, 0.0)


def static_aperture_field(e0, a_mm, b_mm, depth_mm, r_mm):
    """Quasi-static E-field leaking through an a x b aperture (E normal to the wall),
    at distance r inside: Bethe dipole p = eps0 alpha_e E0, alpha_e ~ (pi/16) a b^2 for a
    slot (b <= a; a circular hole of radius c has 2c^3/3), image doubling, decay
    exp(-pi d / b) along a depth d (lowest Laplace mode of the channel)."""
    a, b = max(a_mm, b_mm) * 1e-3, min(a_mm, b_mm) * 1e-3
    alpha = math.pi / 16 * a * b * b
    r = r_mm * 1e-3
    return e0 * alpha / (2 * math.pi * r ** 3) * 2 * math.exp(-math.pi * depth_mm / min(a_mm, b_mm))


def shield_study(c_inp_lid, c_inp_tray, c_node_elf):
    f = np.logspace(0, 8, 400)
    cases = {}
    for name, t in (("lid/tray 2 mm", T_LID), ("wall 7 mm", T_WALL)):
        cases[name] = dict(
            E_0p1m=se_schelkunoff(f, t, wave_impedance(f, 0.1, "E")),
            H_0p1m=se_schelkunoff(f, t, wave_impedance(f, 0.1, "H")),
            H_1m=se_schelkunoff(f, t, wave_impedance(f, 1.0, "H")),
            plane=se_schelkunoff(f, t, wave_impedance(f, 1.0, "P")))
    # closed box, equivalent-volume sphere of the whole shield and of compartment 1
    vol_box = MP.PCB_W * MP.PCB_H * (MP.FRAME_H + MP.PCB_T + MP.TRAY_DEPTH)
    a_box = (3 * vol_box / (4 * math.pi)) ** (1 / 3)
    c1 = MP.COMPARTMENTS["C1 INPUT"]
    vol_c1 = (c1["x1"] - c1["x0"]) * (c1["y1"] - c1["y0"]) * (MP.FRAME_H + MP.PCB_T + MP.TRAY_DEPTH)
    a_c1 = (3 * vol_c1 / (4 * math.pi)) ** (1 / 3)
    box_h = se_closed_box_h(f, T_LID, a_box)
    c1_h = se_closed_box_h(f, T_LID, a_c1)
    # apertures: RJ45 notch 20 x 16 mm through the 7 mm wall, lid seams between screws
    rj = next(c for c in MP.CUTOUTS if c["name"].startswith("J_AES3"))
    pw = next(c for c in MP.CUTOUTS if c["name"].startswith("J_PWR"))
    xs_row = sorted({x for x, y in MP.AMP_HOLES if y == 3.5})
    seam_len = max(np.diff(xs_row))
    ap = dict(rj45=aperture_se(f, rj["w"], MP.WALL_T),
              pwr=aperture_se(f, pw["w"], MP.WALL_T),
              seam=aperture_se(f, seam_len, 0.0, n=1))
    # 50 Hz E-field to IN_P through the leakiest path into compartment 1
    h_comp = MP.FRAME_H
    leak = {}
    # (a) RJ45 notch: distance from the notch (x 200, y 33) to the island centre (24, 45), no credit for
    #     the two internal walls (bound)
    r_rj = math.hypot(200 - 24, 33 - 45.5)
    # (b) lid seam over compartment 1: gap 0.05 mm (machined faces, no gasket), length = screw pitch,
    #     depth = 7 mm wall face; nearest point above the island ~ the lid edge over x=0 at 52 mm height
    r_seam = math.hypot(24 - 0.0, MP.FRAME_H)
    # (c) feed-through bush: Ø10 hole in the 2 mm floor, PTFE filled, 12 mm below the island
    r_bush = MP.TRAY_DEPTH
    for e0 in E50_LOCAL:
        e_rj = static_aperture_field(e0, rj["w"], rj["h"], MP.WALL_T, r_rj)
        e_seam = static_aperture_field(e0, seam_len, 0.05, MP.WALL_T, r_seam)
        # bush: circular hole radius 5 mm, alpha_e = 2c^3/3, decay through the 2 mm floor exp(-2.405 d / c)
        cc = BUSH_HOLE_D / 2e3
        e_bush = e0 * (2 * cc ** 3 / 3) / (2 * math.pi * (r_bush * 1e-3) ** 3) * 2 * \
            math.exp(-2.405 * T_TRAY / (BUSH_HOLE_D / 2))
        # a uniform field E_in over the compartment height acts like the lid (or tray) at
        # E_in * height; IN_P takes C(IN_P, lid or tray) / C_node of it
        v = dict(rj45_notch=e_rj * h_comp * 1e-3 * c_inp_lid / c_node_elf,
                 lid_seam=e_seam * h_comp * 1e-3 * c_inp_lid / c_node_elf,
                 feedthrough_bush=e_bush * MP.TRAY_DEPTH * 1e-3 * c_inp_tray / c_node_elf)
        leak[f"E_ext {e0:g} V/m"] = dict(E_inside_V_per_m=dict(rj45_notch=e_rj, lid_seam=e_seam, feedthrough_bush=e_bush),
                                         V_IN_P_rms=v)
    return dict(f=f, cases=cases, box_h=box_h, c1_h=c1_h, a_box_mm=a_box, a_c1_mm=a_c1, ap=ap,
                seam_len_mm=float(seam_len), leak=leak, rj=rj, pw=pw)


# ===========================================================================
# 3. Magnetic loops
# ===========================================================================
def board_loop(board):
    """Projected area (xy) of the input loop on the board: J201 -> IN_P -> U201 pin 1,
    pin 8 -> IN_N spine -> R202 (Rg) -> CG track -> C202 (Cg) -> GND, closed by a
    straight return in the GND plane back to J201."""
    pads = {(pd["ref"], pd["num"]): (pd["x"], pd["y"]) for pd in board["pads"]}
    # follow the CG track from R202 to C202 through the segment graph
    segs = [s for s in board["segments"] if short(s["net"]) == "CG"]
    start = next(pads[k] for k in pads if k[0] == "R202" and k[1] == "2")
    cg_pads = [v for k, v in pads.items() if k[0] == "C202"]
    path = [start]
    used = set()
    cur = start
    for _ in range(len(segs)):
        nxt = None
        for i, s in enumerate(segs):
            if i in used:
                continue
            a, b = (s["x1"], s["y1"]), (s["x2"], s["y2"])
            if math.dist(a, cur) < 0.05:
                nxt = b
            elif math.dist(b, cur) < 0.05:
                nxt = a
            if nxt:
                used.add(i)
                break
        if not nxt:
            break
        path.append(nxt)
        cur = nxt
    c202 = min(cg_pads, key=lambda q: math.dist(q, cur))
    c202_gnd = max(cg_pads, key=lambda q: math.dist(q, cur))
    poly = [pads[("J201", "1")], pads[("U201", "1")], pads[("U201", "8")],
            next(pads[k] for k in pads if k[0] == "R202" and k[1] == "1")] + path + [c202, c202_gnd]
    poly = np.array(poly)
    x, y = poly[:, 0], poly[:, 1]
    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    cg_len = sum(math.dist(a, b) for a, b in zip(path[:-1], path[1:]))
    return dict(poly=poly.tolist(), area_mm2=float(area), cg_track_mm=float(cg_len))


def plate_coords_amp(xk, yk, z_above_board=0.0):
    """Amplifier KiCad (x, y) -> mounting-plate coordinates (mm): the shield is mounted lid
    down on 5 mm spacers, KiCad y = 0 pointing down (mechanical/params.py LAYOUT)."""
    cx, cy = MP.LAYOUT["amp"]
    z_board_top = MP.MOUNT_SPACER_H + MP.LID_T + MP.FRAME_H
    return np.array([cx + xk - MP.PCB_W / 2, cy + yk - MP.PCB_H / 2, z_board_top + z_above_board])


def plate_coords_psu(xk, yk, z=0.0):
    cx, cy = MP.LAYOUT["psu"]
    bx = MP.PSU_CLEAR + xk
    by = MP.PSU_CLEAR + MP.PSU_PCB_H - yk
    z_pcb = MP.MOUNT_SPACER_H + MP.PSU_BASE_T + MP.PSU_STANDOFF_H + MP.PSU_PCB_T
    return np.array([cx + bx - MP.PSU_INNER_W / 2, cy + by - MP.PSU_INNER_D / 2, z_pcb + z])


def lead_loop():
    """Vector area of the off-board input loop: node-2 post -> flying lead -> PTFE bush
    -> tray -> GND wire -> GND post -> base wiring -> C_B GND plate -> node-2 plate."""
    pc = np.array(MP.LAYOUT["platecap"])
    base_top = MP.PLATECAP_BASE_T
    post_x = MP.PLATE_SIZE + MP.PLATECAP_SPACING / 2 + MP.PLATECAP_POST_MARGIN
    out_post = np.array([pc[0] - post_x, pc[1], base_top + MP.TERMINAL_POST["h"] + MP.TERMINAL_POST["pin_h"] / 2])
    bush = plate_coords_amp(*MP.FEEDTHROUGH_XY, z_above_board=MP.PCB_T + MP.TRAY_T)
    tray_tap = plate_coords_amp(MP.PCB_W / 2, MP.PCB_H, z_above_board=MP.PCB_T + MP.TRAY_T / 2)  # nearest tray edge
    gnd_post = np.array([pc[0] + MP.GND_POST["x"], pc[1] + MP.GND_POST["y"], base_top + MP.GND_POST["h"]])
    cap_b = np.array([pc[0] - (MP.PLATECAP_SPACING / 2 + MP.PLATE_SIZE / 2), pc[1],
                      base_top + MP.PLATE_STANDOFF["h"] + MP.PLATE_T])
    pts = np.array([out_post, bush, tray_tap, gnd_post, cap_b, out_post])
    a = 0.5 * sum(np.cross(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    lead_len = float(np.linalg.norm(bush - out_post))
    return dict(points_mm=pts.tolist(), vector_area_mm2=a.tolist(), area_mm2=float(np.linalg.norm(a)),
                lead_mm=lead_len, gnd_wire_mm=float(np.linalg.norm(gnd_post - tray_tap)))


def magnetic_study(board, psu_board):
    bl = board_loop(board)
    ll = lead_loop()
    w = 2 * np.pi * 50.0
    loops = {"board input loop (layout)": bl["area_mm2"] * 1e-6,
             "node-2 lead + GND wire (mechanics)": ll["area_mm2"] * 1e-6,
             "lead loop, pessimistic x3 (untidy wiring)": 3 * ll["area_mm2"] * 1e-6}
    emf = {k: {f"{b * 1e6:g} uT": w * b * a for b in B50} for k, a in loops.items()}
    # AES3 cable: differential (twisted pair) and common mode (cable vs earth)
    L_cab = 100.0
    pitch, sep = 15e-3, 1e-3
    a_dm = 0.5 * pitch * sep * 1.0           # one non-cancelled half twist (worst case, any length)
    a_cm = L_cab * 1.0                       # cable on the ground, earth path ~1 m deep (rod)
    aes = {f"{b * 1e6:g} uT": dict(differential_V=w * b * a_dm, common_mode_V=w * b * a_cm) for b in B50}
    # common mode reaching the receiver GND through the transformer (C_iw) or the optional 10 nF shell bond
    c_floating = 300e-12 + 58e-12            # simulations/psu: enclosure/cable stray + C_ant series C_filt
    cm_paths = {}
    for name, c in (("S22083 interwinding, 20 pF (assumed)", 20e-12), ("optional 10 nF shell bond (C406, DNP)", 10e-9)):
        for src, v in (("induced CM, 1 uT", aes["1 uT"]["common_mode_V"]), ("PE-to-earth 3 V", 3.0)):
            i = w * c * v
            cm_paths[f"{name} | {src}"] = dict(I_A=i, Vg_earthed_100R=i * 100, Vg_floating=v * c / (c + c_floating))
    # PSU sources at their real position (relays K1-K4, IRM-05 PS1) -> input loop
    pads = {}
    for pd in psu_board["pads"]:
        pads.setdefault(pd["ref"], []).append((pd["x"], pd["y"]))
    centre = {r: np.mean(v, axis=0) for r, v in pads.items()}
    island = plate_coords_amp(24.0, 45.5, MP.PCB_T + 6.0)      # middle of the board loop / tray space
    srcs = {}
    for r in ("K1", "K2", "K3", "K4", "PS1"):
        pos = plate_coords_psu(*centre[r], z=5.0)
        srcs[r] = dict(pos_mm=pos.tolist(), r_to_input_mm=float(np.linalg.norm(pos - island)))
    # relay coil: 5 V reed coil, ~10 mA, 40 AT (2 x 20 AT pull-in, assumed), Ø5 mm bobbin, x2 for the reeds
    m_relay = 40 * math.pi * (2.5e-3) ** 2 * 2
    relay = {}
    for r in ("K1", "K2", "K3", "K4"):
        d = srcs[r]["r_to_input_mm"] * 1e-3
        relay[r] = dict(m_Am2=m_relay, dB_T=MU0 * m_relay / (2 * math.pi * d ** 3))   # on-axis (worst)
    dB_sum = sum(v["dB_T"] for v in relay.values()) / 2       # two relays switch at each swap edge
    a_lead = ll["area_mm2"] * 1e-6
    phi = dB_sum * a_lead                                      # V s per switching edge
    T_swap = 2 * 15.19
    line_amp = 2 * phi / T_swap * math.sqrt(2) / math.sqrt(2)  # rms of each Fourier line (2 edges / period)
    tau = 1e-3                                                 # coil L/R ~ 1 ms -> spike height
    # IRM-05-15: 50 Hz input current pulses ~0.2 A peak in ~5 cm^2 of wiring (assumed)
    m_irm = 0.2 / math.sqrt(2) * 5e-4
    d_irm = srcs["PS1"]["r_to_input_mm"] * 1e-3
    b_irm = MU0 * m_irm / (2 * math.pi * d_irm ** 3)
    # charger / load current loops switching at each swap: 0.25 A in ~3 cm^2
    m_chg = 0.25 * 3e-4
    d_chg = np.mean([srcs[r]["r_to_input_mm"] for r in ("K1", "K2", "K3", "K4")]) * 1e-3
    b_chg = MU0 * m_chg / (2 * math.pi * d_chg ** 3)
    psu = dict(sources=srcs, relay=relay, relay_dB_per_edge_T=dB_sum, flux_per_edge_Vs=phi,
               spike_peak_V=phi / tau, line_rms_V=line_amp, line_spacing_Hz=1 / T_swap,
               floor_0p1Hz_bin_V=float(floor_ant(SCHUMANN[0]) * math.sqrt(BIN)),
               irm_50Hz_B_T=b_irm, irm_50Hz_emf_V=w * b_irm * a_lead,
               charger_step_B_T=b_chg, charger_flux_Vs=b_chg * a_lead)
    return dict(board_loop=bl, lead_loop=ll, loops_m2=loops, emf_50Hz_V=emf, aes3=aes, aes3_cm_to_gnd=cm_paths, psu=psu,
                cable=dict(length_m=L_cab, twist_pitch_mm=pitch * 1e3, pair_sep_mm=sep * 1e3,
                           dm_area_m2=a_dm, cm_area_m2=a_cm))


# ===========================================================================
# 4. Clock / digital
# ===========================================================================
def alias(f, fs=FS):
    return np.abs(f - np.round(f / fs) * fs)


def digital_study(board, fe_node_hf_pf):
    # synchronous tones: every clock is an integer multiple of the 1 kHz AES3 block rate,
    # derived from the one 24.576 MHz oscillator
    tones = {"MCLK 24.576 MHz": F_MCLK, "BCK 12.288 MHz": 64 * FS, "LRCK 192 kHz": FS,
             "modulator 6.144 MHz": F_MOD, "AES3 cell rate 24.576 MBd": 2 * AES3_BIT,
             "AES3 subframe 384 kHz": 2 * FS, "AES3 block 1 kHz": FS / 192}
    worst = {}
    for name, f0 in tones.items():
        n = np.arange(1, int(1e9 / f0) + 1, dtype=float)
        a = alias(n * f0)
        inband = a[(a >= 1.0) & (a <= 50.0)]
        worst[name] = dict(f0_Hz=f0, harmonics_checked=int(len(n)), min_nonzero_alias_Hz=float(a[a > 0].min()) if (a > 0).any() else 0.0,
                           harmonics_aliasing_into_1_50Hz=int(len(inband)))
    # analog attenuation before the ADC for an asynchronous tone at k*fs +- 50 Hz
    f = np.array([FS, 2 * FS, F_MOD])
    h_aa = 1 / np.abs(1 + 2j * np.pi * f * 10e3 * 100e-9)
    h_rc = 1 / np.abs(1 + 2j * np.pi * f * 100 * 2.7e-9)
    pre = np.abs(1 + 100e3 / (1e3 * (1 + 2j * np.pi * f * 100e3 * 15e-9)))   # preamp (Cg short)
    analog_db = 20 * np.log10(h_aa * h_rc * pre / G_IN_BAND)
    # RF at IN_P from the clock: MCLK loop magnetic moment from the layout -> lead loop, via shield SE
    segs = [s for s in board["segments"] if short(s["net"]) in ("MCLK_ADC", "MCLK_TX", "OSC_OUT")]
    clk_len = sum(math.hypot(s["x2"] - s["x1"], s["y2"] - s["y1"]) for s in segs)
    h_ret = 0.2104e-3 if all(s["layer"] == "F.Cu" for s in segs) else 0.5e-3
    a_clk = clk_len * 1e-3 * h_ret
    i_clk = 2 * np.pi * F_MCLK * 10e-12 * 3.3 * 2 / math.pi    # fundamental of a 3.3 V square into 2 x 5 pF
    m_clk = i_clk * a_clk
    r = 0.15                                                    # clock to the node-2 lead / plate caps
    b_clk = MU0 * m_clk / (2 * math.pi * r ** 3)
    return dict(tones=worst, async_alias_analog_attenuation_dB=dict(zip(["192 kHz", "384 kHz", "6.144 MHz"], analog_db.tolist())),
                mclk=dict(track_mm=clk_len, loop_mm2=a_clk * 1e6, i_fund_A=i_clk, m_Am2=m_clk, B_at_0p15m_unshielded_T=b_clk))


def rectified_offset(v_rf_peak, emirr_db=EMIRR_DB):
    """TI SBOA128: EMIRR = 20 log(V_RF,pk / dV_os) at V_RF = 100 mVpk; dV_os scales with V_RF^2."""
    return (v_rf_peak / 0.1) ** 2 * 0.1 * 10 ** (-emirr_db / 20)


# ===========================================================================
# 5. Air-gap plate capacitor
# ===========================================================================
def relief_area():
    return MP.plate_capacitance_pf()[1] / 4


def plate_cap(gap, h=0.125, mask=True, fr4=True, relief=True, mask_um=20.0, mask_er=3.5, er_fr4=4.4):
    """Quarter model (symmetry planes x = 0, y = 0) of one capacitor: lower (GND) copper at
    z = 0, upper (node) copper at z = gap, FR4 plates behind each, solder mask on both copper
    faces, environment box at +-60 mm / +-40 mm.  Returns (C_mutual, C_upper_total) in F."""
    half_cu = MP.PLATE_CU / 2
    half_pl = MP.PLATE_SIZE / 2
    hc = (half_pl - MP.PLATE_HOLE_INSET, half_pl - MP.PLATE_HOLE_INSET)
    keep = [half_cu, half_pl]
    xs = L.graded_axis(0.0, 60.0, 21.6, 27.6, h, 2.0, 1.3, keep=keep)
    t = mask_um / 1000 if mask else 0.0
    zg = list(np.linspace(t, gap - t, max(5, int(round((gap - 2 * t) / 0.06))) + 1))
    zin = [0.0, gap] + zg + ([t, gap - t] if mask else [])
    fr = [-1.6, -1.2, -0.8, -0.45, -0.2, -0.08]
    zin += fr + [gap - z for z in fr]
    dn, z, dz = [], -1.6, 0.25
    while z - dz > -40:
        z -= dz
        dn.append(z)
        dz = min(dz * 1.35, 6.0)
    zs = np.unique(np.round(np.concatenate([[-40.0, 40.0 + gap], dn, zin, [gap - z for z in dn]]), 6))
    ys = xs
    xc = 0.5 * (xs[:-1] + xs[1:])
    zc = 0.5 * (zs[:-1] + zs[1:])
    on_plate = (xc[:, None] <= half_pl) & (xc[None, :] <= half_pl)
    eps = np.ones((len(xc), len(xc), len(zc)))
    for k, z in enumerate(zc):
        if fr4 and ((-1.6 < z < 0) or (gap < z < gap + 1.6)):
            eps[:, :, k][on_plate] = er_fr4
        if mask and ((0 < z < t) or (gap - t < z < gap)):
            eps[:, :, k][on_plate] = mask_er
    S = L.Laplace3D(xs, ys, zs, eps)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    cu = (X <= half_cu + 1e-9) & (Y <= half_cu + 1e-9)
    if relief:
        cu &= (X - hc[0]) ** 2 + (Y - hc[1]) ** 2 > MP.PLATE_CU_KEEPOUT_R ** 2
    S.cond[-1, :, :] = 2
    S.cond[:, -1, :] = 2
    S.cond[:, :, 0] = 2
    S.cond[:, :, -1] = 2
    k0 = int(np.argmin(np.abs(zs - 0.0)))
    kg = int(np.argmin(np.abs(zs - gap)))
    S.cond[:, :, k0][cu] = 0      # lower plate, GND
    S.cond[:, :, kg][cu] = 1      # upper plate, node
    _, Q = S.solve([{1: 1.0}])
    q = Q[0]
    c_area = 4 * (cu.sum())        # unused, grid sanity
    return 4 * (-q[0]), 4 * q[1], int(S.nx * S.ny * S.nz), c_area


def palmer(a, b, d):
    """Palmer (1937) rectangular parallel plates in free space."""
    fa = 1 + d / (math.pi * a) * (1 + math.log(2 * math.pi * a / d))
    fb = 1 + d / (math.pi * b) * (1 + math.log(2 * math.pi * b / d))
    return EPS0 * a * fa * b * fb / d * 1e-3


def plate_study():
    a_eff = MP.PLATE_CU ** 2 - 4 * relief_area()
    a_sp = math.pi * (MP.PTFE_CENTRE_SPACER_D / 2) ** 2 * 1e-6           # m^2, PTFE disc eps_r 2.1
    spacer = lambda g: EPS0 * (2.1 - 1) * a_sp / (g * 1e-3)             # noqa: E731
    res = {"copper_side_mm": MP.PLATE_CU, "relief_area_each_mm2": relief_area(), "area_eff_mm2": a_eff}
    # validation: bare square plates, no FR4/mask/relief, against Palmer
    t0 = time.time()
    cm, cu_tot, n, _ = plate_cap(0.5, mask=False, fr4=False, relief=False)
    res["validation_bare_square"] = dict(C_fd_pF=cm * 1e12, C_palmer_pF=palmer(MP.PLATE_CU, MP.PLATE_CU, 0.5) * 1e12,
                                         C_parallel_pF=EPS0 * MP.PLATE_CU ** 2 * 1e-3 / 0.5 * 1e12, nodes=n)
    p(f"    plate validation: FD {cm * 1e12:.3f} pF, Palmer {res['validation_bare_square']['C_palmer_pF']:.3f} pF "
      f"({time.time() - t0:.0f} s)")
    gaps = [0.40, 0.45, 0.50, 0.55, 0.60]
    sweep = []
    for g in gaps:
        cm, cu_tot, n, _ = plate_cap(g)
        tm = 0.02
        c_pp = EPS0 * a_eff * 1e-3 / g
        c_pp_mask = EPS0 * a_eff * 1e-3 / ((g - 2 * tm) + 2 * tm / 3.5)
        sweep.append(dict(gap_mm=g, C_fd_pF=cm * 1e12, C_fd_plus_spacer_pF=(cm + spacer(g)) * 1e12,
                          C_upper_total_pF=cu_tot * 1e12, C_parallel_pF=c_pp * 1e12, C_parallel_mask_pF=c_pp_mask * 1e12))
        p(f"    gap {g:.2f} mm: FD {cm * 1e12:.3f} pF  parallel {c_pp * 1e12:.3f}  with mask {c_pp_mask * 1e12:.3f}")
    res["sweep"] = sweep
    # grid check at the nominal gap
    cm_f, _, n_f, _ = plate_cap(0.5, h=0.0625)
    res["grid_check"] = dict(h_mm=[0.125, 0.0625], C_pF=[sweep[2]["C_fd_pF"], cm_f * 1e12], nodes_fine=n_f)
    # variants at 0.5 mm: no mask, no FR4
    cm_nm, *_ = plate_cap(0.5, mask=False)
    cm_nf, *_ = plate_cap(0.5, fr4=False)
    res["variants_0p5"] = dict(no_mask_pF=cm_nm * 1e12, no_fr4_pF=cm_nf * 1e12)
    g = np.array(gaps)
    c = np.array([s["C_fd_plus_spacer_pF"] for s in sweep])
    dcdg = np.gradient(c, g)                                   # pF / mm
    i0 = 2
    res["dC_dgap_pF_per_um"] = float(dcdg[i0] / 1000)
    res["dC_dgap_parallel_pF_per_um"] = float(-sweep[i0]["C_parallel_mask_pF"] / (0.5 - 0.04 + 0.04 / 3.5) / 1000)
    res["C_nominal_pF"] = float(c[i0])
    res["spacer_pF"] = spacer(0.5) * 1e12
    cn = float(c[i0]) * 1e-12
    res["consequences"] = dict(divider_loss_dB=20 * math.log10(140e-12 / (140e-12 + 2 * cn)),
                               divider_loss_design_dB=20 * math.log10(140 / 240), rc_fc_kHz=1 / (2 * math.pi * 33e3 * cn) / 1e3)
    res["C_upper_to_environment_pF"] = sweep[i0]["C_upper_total_pF"] - sweep[i0]["C_fd_pF"]
    res["fringe_fraction"] = float(sweep[i0]["C_fd_pF"] / sweep[i0]["C_parallel_mask_pF"] - 1)
    # microphonic sensitivity: DC across each cap. Since the PLATE_RET change the lower
    # plates sit at BIAS_BUF like the node, so only the air-earth current's drop across
    # J202 (10 G) is left: 3 pA typical -> 30 mV (100 pA, the DC-point limit -> 1 V).
    # Before the change: the full IN_P bias, 2.27 V.
    v_dc = V_GAP_DC
    _, z1 = frontend(SCHUMANN[0])
    c_node = 1 / abs(2 * np.pi * SCHUMANN[0] * z1[0])
    h1, _ = frontend(SCHUMANN[0])
    dv = v_dc * abs(dcdg[i0]) * 1e-12 / 1e6 / c_node          # V per nm at IN_P
    res["microphonics_before_plate_ret"] = dict(V_dc=V_GAP_DC_GND, dV_inp_per_nm_V=V_GAP_DC_GND * abs(dcdg[i0]) * 1e-12 / 1e6 / c_node)
    res["microphonics"] = dict(V_dc=v_dc, V_dc_worst=V_GAP_DC_WORST, C_node_pF=c_node * 1e12, dV_inp_per_nm_V=dv,
                               dV_ant_per_nm_V=dv / abs(h1[0]),
                               gap_motion_for_floor_at_SR1_pm_per_rtHz=float(floor_ant(SCHUMANN[0]) / (dv / abs(h1[0])) * 1e3))
    return res


# ===========================================================================
# Plots
# ===========================================================================
def style(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=SUBTLE, labelsize=9)
    ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
    for s in ax.spines.values():
        s.set_color(BORDER)


def labels(ax, title, xl, yl):
    ax.set_title(title, color=TEXT, fontsize=11, loc="left", pad=8)
    ax.set_xlabel(xl, color=SUBTLE, fontsize=9)
    ax.set_ylabel(yl, color=SUBTLE, fontsize=9)


def legend(ax, loc="best", **kw):
    lg = ax.legend(loc=loc, fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT, **kw)
    return lg


def save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    p("  wrote", name)


def plot_guard(isl, fields, rows, near):
    fig = plt.figure(figsize=(15, 10.5), facecolor=BG)
    gs = fig.add_gridspec(2, 3, width_ratios=[1.15, 1, 1], hspace=0.32, wspace=0.42)
    # (a) copper map of compartment 1 around the island with the potential on F.Cu
    ax = fig.add_subplot(gs[0, 0])
    style(ax)
    xs, ys, zs, V, cond, names, kz = (fields[k] for k in ("xs", "ys", "zs", "V", "cond", "names", "kz"))
    k = kz["F.Cu"]
    k_air = int(np.argmin(np.abs(zs - 0.25)))
    vv = np.clip(V[:, :, k_air], 1e-5, 1)
    im = ax.pcolormesh(xs, ys, vv.T, norm=LogNorm(1e-4, 1), cmap="magma", shading="gouraud", rasterized=True)
    colours = {"/Electrometer front end/IN_P": GREEN, "/Electrometer front end/GUARD": BLUE, "GND": GREY,
               "PREAMP_OUT": RED, "+5V_PRE": ORANGE, "/Electrometer front end/IN_N": PURPLE,
               "/Electrometer front end/ANT_BIAS": YELLOW}
    for net, col in colours.items():
        if net in names:
            m = cond[:, :, k] == names.index(net)
            ax.contour(xs, ys, m.T.astype(float), levels=[0.5], colors=[col], linewidths=0.8)
    ax.set_xlim(13, 40)
    ax.set_ylim(58, 33)
    ax.set_aspect("equal")
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.ax.tick_params(colors=SUBTLE, labelsize=8)
    cb.set_label("V, 0.25 mm above F.Cu (IN_P = 1 V)", color=SUBTLE, fontsize=8)
    for net, col in colours.items():
        ax.plot([], [], color=col, label=short(net))
    legend(ax, loc="lower left", ncol=2)
    labels(ax, "Guarded input: copper outlines (F.Cu) and field", "x (mm, board)", "y (mm, board)")
    # (b) cross-section through IN_P track y = 50.1
    ax = fig.add_subplot(gs[0, 1:])
    style(ax)
    j = int(np.argmin(np.abs(ys - 50.1)))
    sel = (zs > -4) & (zs < 4)
    im = ax.pcolormesh(xs, zs[sel], np.clip(V[:, j, sel], 1e-5, 1).T, norm=LogNorm(1e-4, 1), cmap="magma",
                       shading="gouraud", rasterized=True)
    for net, col in colours.items():
        if net in names:
            m = (cond[:, j, :] == names.index(net))[:, sel]
            ax.contour(xs, zs[sel], m.T.astype(float), levels=[0.5], colors=[col], linewidths=1.0)
    for z in LAYER_Z.values():
        ax.axhline(z, color=BORDER, lw=0.4)
    ax.axhspan(Z_B, Z_F, color="#ffffff", alpha=0.04)
    ax.set_xlim(13, 40)
    labels(ax, "Cross-section at y = 50.1 mm (J201 -> U201 pin 1), z exaggerated", "x (mm, board)", "z (mm)")
    # (c) capacitance bars per variant
    ax = fig.add_subplot(gs[1, 0])
    style(ax)
    nets = ["GUARD", "GND", "TRAY", "LID", "WALL", "IN_N", "ANT_BIAS", "PREAMP_OUT", "+5V_PRE", "GUARD_DRV", "CG"]
    var = [("guard", "driven guard (as built)", GREEN), ("gnd", "no guard, GND planes", ORANGE), ("bare", "no guard, bare inner layers", RED)]
    yy = np.arange(len(nets))
    for i, (v, lab, col) in enumerate(var):
        vals = [max(isl[v]["C_to_pF"].get(n, 0.0) * 1e3, 1e-3) for n in nets]
        ax.barh(yy + (i - 1) * 0.27, vals, height=0.26, color=col, label=lab)
    ax.set_xscale("log")
    ax.set_yticks(yy)
    ax.set_yticklabels(nets, color=TEXT, fontsize=8)
    ax.invert_yaxis()
    labels(ax, "Capacitance from IN_P (3-D solve)", "C (fF)", "")
    legend(ax, loc="lower right")
    # (d) injected level vs floor, as built
    ax = fig.add_subplot(gs[1, 1])
    style(ax)
    dens = [r for r in rows["guard"] if r["unit"] in ("V/rtHz", "V rms")]
    short_lab = {"ADM7150": "+5V_PRE noise, SR1", "50 Hz r": "+5V_PRE 1 µV 50 Hz", "U202 + ": "guard e_n, SR1",
                 "bias bu": "ANT_BIAS e_n, SR1"}
    lab = [next(v for k, v in short_lab.items() if r["what"].startswith(k)) for r in dens]
    yy = np.arange(len(dens))
    ax.barh(yy, [r["at_antenna"] for r in dens], height=0.5, color=GREEN, label="injected (as built)")
    ax.scatter([r["floor_at_antenna"] for r in dens], yy, marker="D", s=40, color=TEXT, zorder=5,
               label="receiver floor (V/rtHz; 0.1 Hz bin for the line)")
    for y_, r in zip(yy, dens):
        ax.text(r["at_antenna"] * 1.5, y_, f"{r['margin_dB']:.0f} dB below", va="center", color=TEXT, fontsize=8)
    ax.set_xscale("log")
    ax.set_xlim(1e-14, 1e-6)
    ax.set_yticks(yy)
    ax.set_yticklabels(lab, color=TEXT, fontsize=8)
    ax.set_ylim(len(dens) + 0.4, -0.6)
    labels(ax, "Injected at the antenna (as built)", "V/rtHz  or  V rms", "")
    legend(ax, loc="lower right")
    # (e) nearest approach of other nets
    ax = fig.add_subplot(gs[1, 2])
    style(ax)
    items = [(n, d) for n, d in near.items() if n != "GUARD"][:13]
    dig = {"MCLK_ADC", "MCLK_TX", "OSC_OUT", "BCK", "LRCK", "SDATA", "TXP", "TXN", "RESET_N"}
    cols = [RED if n in dig else (ORANGE if n in ("+5V_PRE", "PREAMP_OUT", "+5VA", "+3V3", "+9V") else BLUE) for n, _ in items]
    ax.barh(np.arange(len(items)), [d for _, d in items], color=cols)
    for n in ("MCLK_ADC", "BCK", "TXP"):
        if n in near:
            ax.barh(len(items), near[n], color=RED)
            items.append((n + " (digital)", near[n]))
    ax.set_yticks(np.arange(len(items)))
    ax.set_yticklabels([n for n, _ in items], color=TEXT, fontsize=8)
    ax.invert_yaxis()
    ax.set_xscale("log")
    labels(ax, "Nearest approach to IN_P copper (edge to edge, GUARD touches)", "distance (mm)", "")
    fig.suptitle("ELARA -- electrostatic coupling into the guarded input (PCB as built)", color=TEXT, fontsize=13, x=0.01, ha="left")
    save(fig, "em_guard_coupling.svg")


def plot_shield(sh, clip):
    f = sh["f"]
    fig, axs = plt.subplots(1, 2, figsize=(15, 6), facecolor=BG)
    ax = axs[0]
    style(ax)
    c = sh["cases"]
    ax.semilogx(f, c["lid/tray 2 mm"]["E_0p1m"], color=BLUE, label="E-source 0.1 m, 2 mm sheet (Schelkunoff)")
    ax.semilogx(f, c["lid/tray 2 mm"]["plane"], color=PURPLE, label="plane wave, 2 mm sheet")
    ax.semilogx(f, c["lid/tray 2 mm"]["H_0p1m"], color=ORANGE, label="H-source 0.1 m, 2 mm sheet")
    ax.semilogx(f, c["wall 7 mm"]["H_0p1m"], color=YELLOW, ls="--", label="H-source 0.1 m, 7 mm wall")
    ax.semilogx(f, sh["box_h"], color=RED, lw=2, label=f"H, closed box (sphere a = {sh['a_box_mm']:.0f} mm, 2 mm)")
    ax.semilogx(f, sh["ap"]["rj45"], color=GREEN, lw=2, label="aperture: RJ45 notch 20 mm, 7 mm deep")
    ax.semilogx(f, sh["ap"]["seam"], color=GREEN, ls=":", label=f"aperture: lid seam {sh['seam_len_mm']:.1f} mm (screw pitch)")
    ax.axvline(50, color=SUBTLE, lw=0.6)
    ax.text(55, 285, "50 Hz", color=SUBTLE, fontsize=8)
    ax.set_ylim(0, 300)
    labels(ax, "Shielding effectiveness, aluminium 6082 (25 MS/m)", "frequency (Hz)", "SE (dB)")
    legend(ax, loc="upper right")
    ax = axs[1]
    style(ax)
    e = np.array(E50_LOCAL)
    for key, col, lab in (("rj45_notch", GREEN, "RJ45 notch (C3), no credit for internal walls"),
                          ("lid_seam", BLUE, "lid seam over C1 (0.05 mm gap)"),
                          ("feedthrough_bush", ORANGE, "PTFE feed-through, Ø10 hole"),
                          ("outside_shield_lead_and_plates", PURPLE, "lead + node plates outside the shield (estimate)")):
        v = [sh["leak"][f"E_ext {x:g} V/m"]["V_IN_P_rms"][key] for x in e]
        if max(v) < 1e-30:
            lab += f" ({max(v):.0e} V, off scale)"
        ax.loglog(e, np.maximum(v, 1e-300), "o-", color=col, label=lab)
    ax.axhline(clip, color=RED, ls="--", label=f"50 Hz clip level {clip * 1e3:.1f} mV rms (antenna)")
    ax.axhline(MAINS_PICKUP[0], color=YELLOW, ls=":", label="antenna mains pickup 1-5 mV (by design)")
    ax.axhline(MAINS_PICKUP[1], color=YELLOW, ls=":")
    ax.axhline(floor_ant(50.0) * math.sqrt(BIN), color=GREY, ls="-.", label="noise in a 0.1 Hz bin at 50 Hz")
    ax.set_ylim(1e-13, 1e-1)
    labels(ax, "50 Hz E-field reaching IN_P through the shield", "E-field at the shield (V/m rms)", "V at IN_P (V rms)")
    legend(ax, loc="lower right")
    fig.suptitle("ELARA -- aluminium shield: transparent to ELF H, opaque to E", color=TEXT, fontsize=13, x=0.01, ha="left")
    save(fig, "em_shielding.svg")


def plot_magnetic(mag, clip):
    fig, axs = plt.subplots(1, 2, figsize=(15, 6), facecolor=BG)
    ax = axs[0]
    style(ax)
    b = np.logspace(-8, -5, 50)
    w = 2 * np.pi * 50
    cols = [GREEN, BLUE, PURPLE]
    for (k, a), col in zip(mag["loops_m2"].items(), cols):
        ax.loglog(b * 1e6, w * b * a, color=col, label=f"{k}: {a * 1e6:.0f} mm²")
    ax.loglog(b * 1e6, w * b * mag["cable"]["dm_area_m2"], color=ORANGE, ls="--", label="AES3 pair, differential")
    ax.loglog(b * 1e6, w * b * mag["cable"]["cm_area_m2"], color=RED, ls="--", label="AES3 cable vs earth, common mode (100 m; at the transformer, not at IN_P)")
    ax.axhline(clip, color=RED, lw=0.8, label=f"clip level {clip * 1e3:.0f} mV")
    ax.axhline(MAINS_PICKUP[0], color=YELLOW, ls=":", label="antenna mains E pickup 1-5 mV")
    ax.axhline(floor_ant(50) * math.sqrt(BIN), color=GREY, ls="-.", label="noise, 0.1 Hz bin")
    ax.axvspan(0.1, 1.0, color=YELLOW, alpha=0.06)
    labels(ax, "50 Hz magnetic induction (shield gives ~0 dB at 50 Hz)", "B (µT rms)", "EMF (V rms)")
    legend(ax, loc="upper left")
    ax = axs[1]
    style(ax)
    ps = mag["psu"]
    f = np.logspace(-2, 2, 400)
    # relay switching: two impulses of flux phi per 30.4 s period -> lines every 1/30.4 Hz
    ax.loglog(f, np.full_like(f, ps["line_rms_V"]), color=ORANGE, label="relay coil edges: each swap line (rms)")
    ax.loglog(f, np.full_like(f, ps["charger_flux_Vs"] * 2 / 30.38), color=PURPLE, label="charger/load loop step: each line")
    ax.loglog(f, floor_ant(np.clip(f, 7.83, 45)) * math.sqrt(BIN), color=GREY, ls="-.", label="receiver noise, 0.1 Hz bin")
    ax.scatter([50], [ps["irm_50Hz_emf_V"]], color=RED, zorder=5, label="IRM-05 50 Hz input-current field")
    ax.axvspan(1, 50, color=GREEN, alpha=0.05)
    labels(ax, "PSU box as a magnetic source (into the input lead loop)", "frequency (Hz)", "V at the input (rms)")
    legend(ax, loc="center right")
    fig.suptitle("ELARA -- magnetic coupling at ELF", color=TEXT, fontsize=13, x=0.01, ha="left")
    save(fig, "em_magnetic.svg")


def plot_plate(pl):
    fig, axs = plt.subplots(1, 2, figsize=(14, 5.5), facecolor=BG)
    ax = axs[0]
    style(ax)
    g = [s["gap_mm"] for s in pl["sweep"]]
    gg = np.linspace(0.38, 0.62, 50)
    a = pl["area_eff_mm2"]
    ax.plot(gg, EPS0 * a * 1e-3 / gg * 1e12, color=GREY, ls="--", label="parallel plate ε0A/d (air)")
    ax.plot(gg, EPS0 * a * 1e-3 / ((gg - 0.04) + 0.04 / 3.5) * 1e12, color=BLUE, ls=":", label="parallel plate + 2 x 20 µm mask")
    ax.plot(g, [s["C_fd_pF"] for s in pl["sweep"]], "o-", color=GREEN, label="3-D solve (fringing, FR4, mask)")
    ax.plot(g, [s["C_fd_plus_spacer_pF"] for s in pl["sweep"]], "s-", color=ORANGE, label="3-D + PTFE centre disc")
    ax.axvline(0.5, color=SUBTLE, lw=0.6)
    labels(ax, "Air-gap plate capacitor: C against gap", "gap (mm)", "C (pF)")
    legend(ax)
    ax = axs[1]
    style(ax)
    names = ["parallel\n(air)", "parallel\n+mask", "3-D\nbare", "3-D no\nmask", "3-D no\nFR4", "3-D\nall", "3-D all\n+disc"]
    s0 = pl["sweep"][2]
    vals = [s0["C_parallel_pF"], s0["C_parallel_mask_pF"], pl["validation_bare_square"]["C_fd_pF"],
            pl["variants_0p5"]["no_mask_pF"], pl["variants_0p5"]["no_fr4_pF"], s0["C_fd_pF"], s0["C_fd_plus_spacer_pF"]]
    ax.bar(range(len(vals)), vals, color=[GREY, BLUE, PURPLE, YELLOW, ORANGE, GREEN, GREEN])
    for i, v in enumerate(vals):
        ax.text(i, v + 0.2, f"{v:.2f}", color=TEXT, ha="center", fontsize=8)
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(names, color=TEXT, fontsize=8)
    ax.set_ylim(min(vals) - 3, max(vals) + 2)
    labels(ax, f"At 0.5 mm: dC/dgap = {pl['dC_dgap_pF_per_um'] * 1e3:.1f} fF/µm", "", "C (pF)")
    fig.suptitle(f"ELARA -- air-gap plate capacitor ({MP.PLATE_CU:.1f} mm copper, R4.8 corner reliefs)", color=TEXT, fontsize=13, x=0.01, ha="left")
    save(fig, "em_plate_capacitor.svg")


def plot_digital(dg, hf, rf_levels):
    fig, axs = plt.subplots(1, 2, figsize=(15, 5.5), facecolor=BG)
    ax = axs[0]
    style(ax)
    names = list(dg["tones"].keys())
    vals = [max(dg["tones"][n]["min_nonzero_alias_Hz"], 0.1) for n in names]
    ax.barh(range(len(names)), vals, color=[BLUE] * len(names))
    for i, n in enumerate(names):
        t = dg["tones"][n]
        txt = "all harmonics alias to DC" if t["min_nonzero_alias_Hz"] == 0 else f"nearest alias {t['min_nonzero_alias_Hz']:.0f} Hz"
        ax.text(0.15, i, f"  {txt}, {t['harmonics_checked']} harmonics to 1 GHz", va="center", color=TEXT, fontsize=8)
    ax.axvspan(1, 50, color=RED, alpha=0.15, label="1-50 Hz band")
    ax.set_xscale("log")
    ax.set_xlim(0.1, 3e5)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, color=TEXT, fontsize=8)
    labels(ax, "Synchronous clocks after sampling at 192 kHz", "lowest non-zero alias (Hz)", "")
    legend(ax, loc="lower right")
    ax = axs[1]
    style(ax)
    keys = list(rf_levels.keys())
    v_rf = [rf_levels[k]["V_rf_peak"] for k in keys]
    v_dc = [rf_levels[k]["dV_os"] for k in keys]
    y = np.arange(len(keys))
    ax.barh(y - 0.2, v_rf, height=0.38, color=ORANGE, label="RF amplitude at IN+ (V peak)")
    ax.barh(y + 0.2, np.maximum(v_dc, 1e-30), height=0.38, color=PURPLE, label=f"rectified shift (EMIRR {EMIRR_DB:.0f} dB; DC for a steady clock)")
    ax.axvline(floor_ant(7.83) * math.sqrt(BIN) * 0.583, color=GREY, ls="-.", label="IN_P noise in a 0.1 Hz bin")
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(keys, color=TEXT, fontsize=8)
    labels(ax, "RF at the LMP7721 input and its demodulated part", "V", "")
    ax.set_xlim(1e-19, 1e-1)
    legend(ax, loc="lower right")
    fig.suptitle("ELARA -- clock and AES3 emissions", color=TEXT, fontsize=13, x=0.01, ha="left")
    save(fig, "em_digital.svg")


# ===========================================================================
# main
# ===========================================================================
def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def main():
    t_start = time.time()
    if L.pyamg is None:
        p("pyamg not installed: falling back to Jacobi-CG (slower). pip install pyamg")
    try:
        with open(os.path.join(HERE, "..", "system", "results.json")) as fh:
            clip = json.load(fh)["headroom_50Hz"]["max_input_50Hz_V_rms"]
    except (OSError, KeyError):
        clip = 21.06e-3
    p("1. guarded input: parsing", os.path.relpath(PCB_AMP, ROOT))
    board = L.load_board(PCB_AMP)
    isl, fields = island_study(board)
    near = nearest_approach(board)
    rows, cnode = {}, {}
    for v in ("guard", "gnd", "bare"):
        caps = isl[v]["C_to_pF"]
        # strays that load the node: everything except the bootstrapped guard / IN_N / GUARD_DRV
        boot = {"GUARD", "IN_N", "GUARD_DRV"}
        c_load = sum(c for n, c in caps.items() if n not in boot) * 1e-12
        isl[v]["C_load_unbootstrapped_pF"] = c_load * 1e12
        h0, _ = frontend(SCHUMANN[0])
        h1, _ = frontend(SCHUMANN[0], c_load)
        isl[v]["extra_divider_loss_dB"] = float(20 * np.log10(abs(h0[0]) / abs(h1[0])))
        rows[v], cnode[v] = aggressor_table(isl[v], c_load)
    hf = hf_coupling({v: isl[v] for v in ("guard", "gnd", "bare")})

    p("2. shielding")
    sh = shield_study(isl["guard"]["C_to_pF"].get("LID", 0.0) * 1e-12, isl["guard"]["C_to_pF"].get("TRAY", 0.0) * 1e-12,
                      cnode["guard"])

    p("3. magnetic")
    psu_board = L.load_board(PCB_PSU)
    mag = magnetic_study(board, psu_board)

    p("4. clock / digital")
    dg = digital_study(board, hf["guard"]["C_node_HF_pF"])
    # RF levels at IN+:
    #  (a) MCLK field into the node-2 lead loop, reduced by the shield's aperture SE at 24.576 MHz
    se_ap = float(np.interp(F_MCLK, sh["f"], sh["ap"]["rj45"]))
    v_mclk = 2 * np.pi * F_MCLK * dg["mclk"]["B_at_0p15m_unshielded_T"] * 10 ** (-se_ap / 20) * mag["lead_loop"]["area_mm2"] * 1e-6
    #  (b) AES3 radiated by the cable near the antenna: 40 dBuV/m at 6-25 MHz (assumed), h_eff 6.5 m, RF filter
    e_aes = 100e-6
    h_rf, _ = frontend(np.array([AES3_BIT / 2, 2 * AES3_BIT]))
    v_aes = e_aes * 6.5 * np.abs(h_rf) * math.sqrt(2)
    #  (c) 1 mV of MCLK on the C1 ground relative to the shield (pessimistic bound)
    rf_levels = {"MCLK -> lead loop (shielded)": dict(V_rf_peak=v_mclk * math.sqrt(2)),
                 "AES3 cable field, 6.1 MHz": dict(V_rf_peak=float(v_aes[0])),
                 "AES3 cable field, 24.6 MHz": dict(V_rf_peak=float(v_aes[1])),
                 "1 mV MCLK on C1 GND (bound)": dict(V_rf_peak=1e-3 * math.sqrt(2)),
                 "FM 1 V/m at antenna (PLAN 3.0)": dict(V_rf_peak=float(1.0 * 6.5 * np.abs(frontend(100e6)[0][0]) * math.sqrt(2)))}
    for k in rf_levels:
        rf_levels[k]["dV_os"] = rectified_offset(rf_levels[k]["V_rf_peak"])
    dg["rf_levels"] = rf_levels
    dg["shield_SE_rj45_at_MCLK_dB"] = se_ap
    # two-tone beat: the two strongest realistic RF lines at IN+ (FM carrier, AES3 6.1 MHz) would have
    # to sit within 50 Hz of each other; their product term V1 V2 / 100 mV x 10^(-EMIRR/20)
    v1, v2 = rf_levels["FM 1 V/m at antenna (PLAN 3.0)"]["V_rf_peak"], rf_levels["AES3 cable field, 6.1 MHz"]["V_rf_peak"]
    dg["two_tone_beat_V"] = v1 * v2 / 0.1 * 10 ** (-EMIRR_DB / 20)
    dg["two_tone_beat_1mV_each_bound_V"] = 1e-3 * 1e-3 / 0.1 * 10 ** (-EMIRR_DB / 20)

    p("5. air-gap plate capacitor")
    pl = plate_study()

    # IN_P / node-1 metal outside the shield (by design part of the antenna): the 109 mm flying lead
    # (~10 pF/m) and the two node plates (C to the surroundings from the plate solve), at a mean
    # 30 mm from grounded metal (estimate)
    c_exp = 10e-12 * mag["lead_loop"]["lead_mm"] * 1e-3 + 2 * pl["C_upper_to_environment_pF"] * 1e-12
    for e0 in E50_LOCAL:
        sh["leak"][f"E_ext {e0:g} V/m"]["V_IN_P_rms"]["outside_shield_lead_and_plates"] = e0 * 0.03 * c_exp / cnode["guard"]
    sh["exposed_C_pF"] = c_exp * 1e12

    results = dict(
        meta=dict(tool="finite-difference Laplace (em_lib.py), pyamg " + ("yes" if L.pyamg else "no"),
                  board=os.path.relpath(PCB_AMP, ROOT), stack=STACK, sigma_Al_S_per_m=SIGMA_AL,
                  clip_level_50Hz_V_rms=clip, noise_floor_antenna_V_per_rtHz=NOISE_ANT,
                  runtime_s=None),
        guarded_input=dict(capacitance=isl, nearest_approach_mm=near, aggressors=rows,
                           C_node_ELF_pF={k: v * 1e12 for k, v in cnode.items()}, rf_node=hf),
        shielding=dict(at_freqs={f"{fq:g} Hz": {name: {k: float(np.interp(fq, sh["f"], v)) for k, v in c.items()}
                                                for name, c in sh["cases"].items()} | {
                                                    "closed box H (2 mm)": float(np.interp(fq, sh["f"], sh["box_h"])),
                                                    "closed C1 H (2 mm)": float(np.interp(fq, sh["f"], sh["c1_h"])),
                                                    "aperture RJ45": float(np.interp(fq, sh["f"], sh["ap"]["rj45"])),
                                                    "aperture lid seam": float(np.interp(fq, sh["f"], sh["ap"]["seam"]))}
                                         for fq in (1, 8, 50, 1e3, 1e5, 6.144e6, 24.576e6, 1e8)},
                       terms_50Hz_2mm=dict(zip(("absorption_dB", "reflection_H_0p1m_dB", "skin_depth_mm"),
                                               [float(np.asarray(x).ravel()[0]) for x in
                                                se_terms(np.array([50.0]), T_LID, wave_impedance(np.array([50.0]), 0.1, "H"))])),
                       a_eq_box_mm=sh["a_box_mm"], a_eq_c1_mm=sh["a_c1_mm"], seam_length_mm=sh["seam_len_mm"],
                       e50_leak=sh["leak"], exposed_outside_shield_C_pF=sh["exposed_C_pF"]),
        magnetic=mag,
        digital=dg,
        plate_capacitor=pl)
    results["meta"]["runtime_s"] = time.time() - t_start
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(jsonable(results), fh, indent=2)
    p("results.json written")

    plot_guard(isl, fields, rows, near)
    plot_shield(sh, clip)
    plot_magnetic(mag, clip)
    plot_plate(pl)
    plot_digital(dg, hf, rf_levels)
    p(f"done in {time.time() - t_start:.0f} s")


if __name__ == "__main__":
    main()
