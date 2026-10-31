#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA -- thermal simulations of the outdoor unit

  1. Board level: steady-state 2-D finite-difference heat spreading on the two
     PCBs.  Copper is rasterised from the real boards (zone fills and tracks of
     PCB/<board>/<board>.kicad_pcb), heat sources sit on the real footprints,
     and each board loses heat by gap conduction/convection and radiation to
     its aluminium enclosure (plus, on the amplifier, conduction into the
     shield walls through the bolted GND strips).  Dissipations are computed
     from the design (PCB/*/design.py) and datasheet-typical supply currents.
  2. Enclosure level: a lumped transient network of the outdoor box (Fibox
     ARCA 403015, 300 x 400 x 150 mm polycarbonate) with the amplifier shield,
     the PSU box and the PE-HD mounting plate inside; clear-sky sun for east
     Slovenia (46.5 N, 16.0 E), sky and ground radiation, wind convection.
     24 h design days (summer, record summer, winter, autumn condensation) for
     light-grey, white and black box surfaces.
  3. Front end: LMP7721 input bias current against temperature, temperature
     swing rates, and the frequency response from sun / wind to the input
     stage (are clouds or gusts visible below 1 Hz?).

Writes results.json and four SVG plots next to this script.
Run: .venv/bin/python simulations/thermal/run_thermal.py   (about 30 s)

Licence: CERN-OHL-W-2.0
"""

import ast
import json
import math
import os
import re
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.integrate import solve_ivp

import os as _os  # noqa: E402
_os.environ.setdefault("SOURCE_DATE_EPOCH", "0")   # fixed SVG date: no churn on re-runs
import matplotlib  # noqa: E402
matplotlib.rc_file(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "matplotlibrc"))
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.path import Path                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "mechanical"))
import params as MP                                 # noqa: E402

# ---------------------------------------------------------------------------
# Plot style (same palette as simulations/psu and simulations/spice)
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

SIGMA = 5.670e-8
K0 = 273.15

# ===========================================================================
# 0. Assumptions (every number used below; sources in README.md)
# ===========================================================================
# --- PCB build (ASSEMBLY.md: 1.6 mm FR4, 1 oz, ENIG; JLCPCB 4-layer default stack-up)
CU_K = 390.0                    # W/m/K copper
FR4_K = 0.30                    # W/m/K in-plane (glass/epoxy, 0.3-0.8; low end)
BOARD_T = 1.6e-3
CU_T = {"F.Cu": 35e-6, "B.Cu": 35e-6, "In1.Cu": 17.5e-6, "In2.Cu": 17.5e-6}   # 1 oz outer, 0.5 oz inner
EPS_MASK = 0.90                 # IR emissivity of solder mask, any colour (green, white, black: 0.85-0.95)
EPS_ENIG = 0.05                 # unmasked gold island / strips
EPS_AL = 0.25                   # bead-blasted + chromate aluminium (raw 0.05-0.1, blasted 0.2-0.4)
EPS_PC = 0.90                   # polycarbonate / paint, IR
EPS_PE = 0.90                   # PE-HD mounting plate
K_AIR = 0.026
H_CONTACT = 300.0               # W/m2/K, Cu strip to Al bar, averaged over the strip (bolts every ~35 mm)
H_CONTACT_SWEEP = (100.0, 1000.0)
CELL = 0.5e-3                   # FD grid, m

# --- Amplifier (design.py power sheet text: ~40 mA on +5VA, ~45 mA on +3V3)
I_5VA = 40e-3
I_3V3 = 45e-3
I_GND_ADM = 5e-3                # ADM7150 ground current (as simulations/psu)
I_LMP7721 = 1.3e-3              # datasheet typ, 5 V
I_LMP7715 = 1.15e-3             # datasheet typ, 5 V
I_DIVIDER = 5.0 / 94e3          # 47k/47k bias divider
I_OSC = 4.5e-3                  # SiT2001B 24.576 MHz, 3.3 V, 15 pF (datasheet ~3.8-4.5 mA)
I_PCM_D = 15e-3                 # PCM1804 VDD at 192 kHz (datasheet typ, scaled to dual rate)
AES_R_DRV = 33.5                # CS8406 TXP/TXN driver resistance each (design.py note)
AES_R_SER = 22.0                # R412, R413
AES_R_LOAD = 110.0
VF_SS34 = 0.30                  # at ~0.1 A, 25 C (Vishay curve)
# input voltage cases at the amplifier (after D101)
VIN_CASES = {
    "PSU (6.98 V - 7.2 R CMC+cable - SS34)": 6.98 - 7.2 * 0.095 - VF_SS34,
    "fresh PP3 battery 9.6 V": 9.6 - VF_SS34,
    "15 V battery (max)": 15.0 - VF_SS34,
}

# --- PSU (PCB/acdc_converter/design.py, simulations/psu/psu_model.py NOMINAL)
V_IRM = 15.0
ETA_IRM = 0.75                  # IRM-05-15: 80 % at full load (datasheet); ~40 % load -> 75 % assumed
I_CC = 1.25 / 6.2
V_CV = 10.4
R_CHG, R_LOAD, R_ESR = 2.2, 3.3, 0.2
C_BUCKET = 2.5
T_HALF = 15.2
V_LT = 6.98
I_LT_OUT = I_5VA + I_3V3 + 2 * I_GND_ADM      # 95 mA
I_Q_LT = 2.3e-3
I_DIV_CV = V_CV / (240 + 1740)                 # R3 + R4
I_BAL = 4 * 2.55 / (4 * 5100)                  # per bucket
R_COIL, R_COIL_SER, V_COIL = 200.0, 82.0, 12.0
I_LED = (12.0 - 2.0) / 4700
I_Q_78L = 3.5e-3
I_4060 = 0.3e-3
R_CMC = 6.78                                   # SRF1260-102M, both windings
IRM_BODY = (33.7e-3, 22.2e-3, 15.0e-3)         # mm -> m, Mean Well IRM-05 case
EDLC_BODY = (10e-3, 30e-3)                     # D x L

# --- Junction-to-board (or case-to-board) resistances, K/W (datasheet-typical / package-typical)
THETA = {
    "U101": 15.0, "U102": 15.0,      # ADM7150 SOIC-8 EP (theta_JB; theta_JA 36.9 on JEDEC 4-layer)
    "U302": 45.0,                    # PCM1804 SSOP-28
    "U401": 45.0,                    # CS8406 TSSOP-28
    "U201": 60.0, "U202": 90.0, "U203": 90.0, "U301": 90.0,   # SOIC-8 / SOT-23-5
    "Y402": 100.0, "D101": 30.0,
    "U1": 6.0, "U2": 6.0,            # LM317 TO-220 theta_JC 3-5 + tab-to-copper ~1-2
    "U3": 40.0,                      # L78L12 SOT-89
    "U5": 10.0,                      # LT3045 MSOP-12 EP (theta_JC(pad) ~ 5-10)
    "D1": 30.0, "D6": 30.0, "D7": 30.0,
}

# --- Operating-temperature limits (datasheets; 'check' = verify, see README)
LIMITS = {
    "U201 LMP7721MA": (-40, 85, "ambient"),
    "U202/U203/U301 LMP7715MF": (-40, 125, "ambient"),
    "U101/U102 ADM7150": (-40, 125, "junction"),
    "U302 PCM1804DB": (-25, 85, "ambient, check"),
    "U401 CS8406-CZZ": (-10, 70, "ambient, commercial grade"),
    "Y402 SiT2001BI": (-40, 85, "ambient"),
    "U1/U2 LM317KCSE3": (0, 125, "junction (TI recommended)"),
    "U3 L78L12ACUTR": (0, 125, "junction, AC grade; check"),
    "U5 LT3045EMSE": (-40, 125, "junction"),
    "PS1 IRM-05-15": (-30, 70, "ambient, derate above +50 C; check curve"),
    "C8-C15 Eaton HV1030 EDLC": (-40, 65, "at 2.7 V"),
    "K1-K4 SIL05 reed relay": (-20, 70, "check datasheet"),
    "Panasonic FR electrolytics": (-40, 105, "105 C series"),
    "Fibox ARCA polycarbonate": (-40, 80, "continuous"),
}

# --- Front end
IB25_TYP = 3e-15
IB25_MAX = 20e-15
IB_DOUBLING_K = 10.0
TCVOS = 4e-6                    # V/K, LMP7721 bound (typ ~1.5 uV/K)
C_NODE = 240e-12                # C_ant 140 p + 100 p filter
R_J202 = 100e9
NOISE_INP_SR1 = 26.7e-9         # simulations/spice (no J202)
NOISE_ANT_100G = 74.8e-9        # simulations/system, J202 = 100 G, SR1
Z_ANT_PER_A = 1.452e-9 / 0.01e-15   # simulations/system: 0.01 fA/rtHz at IN_P -> 1.452 nV/rtHz at antenna, SR1
Q_E = 1.602e-19

# --- Outer box and site (east Slovenia: Maribor / Ptuj / Murska Sobota)
LAT, LON = 46.5, 16.0
BOX_OUT = (0.300, 0.400, 0.150)         # W x H x D (Fibox ARCA 403015 outer)
BOX_WALL = 4e-3
PC_RHO_CP = 1200.0 * 1250.0
K_PC = 0.20
ALBEDO = 0.20                            # grass
DIFFUSE_C = 0.12                         # ASHRAE clear-sky diffuse/DNI ratio, summer
COLOURS = {"light grey RAL 7035 (as supplied)": 0.55, "white paint": 0.25, "black": 0.95}
H_IN_MIN = 1.0

# ===========================================================================
# 1. KiCad board reader (minimal S-expression parser)
# ===========================================================================
_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')


def parse_sexpr(text):
    stack = [[]]
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append([])
        elif t == ")":
            node = stack.pop()
            stack[-1].append(node)
        else:
            stack[-1].append(t[1:-1] if t[0] == '"' else t)
    return stack[0][0]


def kids(node, tag):
    return [c for c in node if isinstance(c, list) and c and c[0] == tag]


def kid(node, tag):
    k = kids(node, tag)
    return k[0] if k else None


def read_board(path, cell=CELL):
    with open(path, encoding="utf-8") as fh:
        tree = parse_sexpr(fh.read())
    # board outline
    xs, ys = [], []
    for g in tree:
        if isinstance(g, list) and g and g[0] in ("gr_line", "gr_rect") and kid(g, "layer") and kid(g, "layer")[1] == "Edge.Cuts":
            for t in ("start", "end"):
                p = kid(g, t)
                xs.append(float(p[1]))
                ys.append(float(p[2]))
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    w, h = (x1 - x0) * 1e-3, (y1 - y0) * 1e-3
    nx, ny = int(round(w / cell)), int(round(h / cell))
    xc = (np.arange(nx) + 0.5) * cell * 1e3       # board mm
    yc = (np.arange(ny) + 0.5) * cell * 1e3
    XX, YY = np.meshgrid(xc, yc)
    pts = np.column_stack([XX.ravel(), YY.ravel()])
    layers = [l for l in CU_T if any(isinstance(c, list) and len(c) > 1 and c[1] == l for c in kid(tree, "layers")[1:])]
    cu = {l: np.zeros((ny, nx)) for l in layers}
    # zone fills
    for z in kids(tree, "zone"):
        for fp in kids(z, "filled_polygon"):
            lay = kid(fp, "layer")[1]
            if lay not in cu:
                continue
            poly = np.array([[float(q[1]) - x0, float(q[2]) - y0] for q in kid(fp, "pts")[1:] if q[0] == "xy"])
            bx0, by0 = poly.min(0)
            bx1, by1 = poly.max(0)
            m = (pts[:, 0] >= bx0) & (pts[:, 0] <= bx1) & (pts[:, 1] >= by0) & (pts[:, 1] <= by1)
            inside = np.zeros(len(pts), bool)
            inside[m] = Path(poly).contains_points(pts[m])
            cu[lay] = np.maximum(cu[lay], inside.reshape(ny, nx))
    # tracks
    cmm = cell * 1e3
    for s in kids(tree, "segment"):
        lay = kid(s, "layer")[1]
        if lay not in cu:
            continue
        ax, ay = float(kid(s, "start")[1]) - x0, float(kid(s, "start")[2]) - y0
        bx, by = float(kid(s, "end")[1]) - x0, float(kid(s, "end")[2]) - y0
        wd = float(kid(s, "width")[1])
        r = max(wd, cmm) / 2
        i0, i1 = int(max(0, (min(ax, bx) - r) / cmm)), int(min(nx, (max(ax, bx) + r) / cmm + 1))
        j0, j1 = int(max(0, (min(ay, by) - r) / cmm)), int(min(ny, (max(ay, by) + r) / cmm + 1))
        gx, gy = np.meshgrid(xc[i0:i1], yc[j0:j1])
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        tt = np.clip(((gx - ax) * dx + (gy - ay) * dy) / L2, 0, 1) if L2 > 0 else 0.0
        d = np.hypot(gx - (ax + tt * dx), gy - (ay + tt * dy))
        cov = np.where(d <= r, min(1.0, wd / cmm), 0.0)
        cu[lay][j0:j1, i0:i1] = np.maximum(cu[lay][j0:j1, i0:i1], cov)
    # footprints: reference, position, courtyard box (board mm)
    fps = {}
    for f in kids(tree, "footprint"):
        at = kid(f, "at")
        fx, fy = float(at[1]) - x0, float(at[2]) - y0
        rot = math.radians(float(at[3])) if len(at) > 3 else 0.0
        ref = next((p[2] for p in kids(f, "property") if p[1] == "Reference"), None)
        side = kid(f, "layer")[1]
        loc = []
        for g in f:
            if isinstance(g, list) and g and g[0] in ("fp_line", "fp_rect", "fp_poly", "fp_circle", "fp_arc"):
                ly = kid(g, "layer")
                if not ly or "CrtYd" not in ly[1]:
                    continue
                if g[0] == "fp_circle":
                    c, e = kid(g, "center"), kid(g, "end")
                    cx, cy = float(c[1]), float(c[2])
                    rr = math.hypot(float(e[1]) - cx, float(e[2]) - cy)
                    loc += [(cx - rr, cy - rr), (cx + rr, cy + rr)]
                    continue
                for t in ("start", "end", "mid"):
                    p = kid(g, t)
                    if p:
                        loc.append((float(p[1]), float(p[2])))
                pp = kid(g, "pts")
                if pp:
                    loc += [(float(q[1]), float(q[2])) for q in pp[1:] if q[0] == "xy"]
        if not loc:
            loc = [(float(kid(p, "at")[1]), float(kid(p, "at")[2])) for p in kids(f, "pad")] or [(0, 0)]
        ca, sa = math.cos(rot), math.sin(rot)
        absx = [fx + px * ca + py * sa for px, py in loc]
        absy = [fy - px * sa + py * ca for px, py in loc]
        fps[ref] = {"x": fx, "y": fy, "side": side, "box": (min(absx), min(absy), max(absx), max(absy))}
    return {"nx": nx, "ny": ny, "w": w, "h": h, "cu": cu, "fps": fps, "xc": xc, "yc": yc, "layers": layers}


def box_mask(b, box, shrink=0.25):
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = x0 + shrink, y0 + shrink, x1 - shrink, y1 - shrink
    m = (b["xc"][None, :] >= x0) & (b["xc"][None, :] <= x1) & (b["yc"][:, None] >= y0) & (b["yc"][:, None] <= y1)
    if not m.any():           # tiny part: nearest cell
        i = np.argmin(abs(b["xc"] - (x0 + x1) / 2))
        j = np.argmin(abs(b["yc"] - (y0 + y1) / 2))
        m[j, i] = True
    return m


# ===========================================================================
# 2. 2-D finite-difference board solver
# ===========================================================================
def h_gap(gap, height, dT=1.0):
    """Convective coefficient across an enclosed vertical air slot (W/m2/K):
    conduction for thin slots, Catton/MacGregor-Emery type for wide ones."""
    beta_g = 9.81 / 300.0
    nu_alpha = 1.6e-5 * 2.25e-5
    ra = beta_g * max(dT, 0.05) * gap ** 3 / nu_alpha
    nu = max(1.0, 0.22 * (0.71 / 0.91 * ra) ** 0.28 * (height / gap) ** -0.25)
    return nu * K_AIR / gap


def eps_pair(e1, e2):
    return 1.0 / (1.0 / e1 + 1.0 / e2 - 1.0)


def solve_board(b, power, t_wall, h_conv_top, h_conv_bot, eps_top, eps_bot, eps_wall,
                extra_g=None, iters=4):
    """Steady temperature (C) of the board above enclosure walls at t_wall (C).
    power: (ny, nx) W per cell; extra_g: (ny, nx) W/K per cell to t_wall."""
    ny, nx = b["ny"], b["nx"]
    a = CELL * CELL
    s = FR4_K * BOARD_T + sum(CU_K * CU_T[l] * b["cu"][l] for l in b["layers"])     # W/K per square
    # neighbour conductances (harmonic mean, square cells)
    gx = 2 * s[:, 1:] * s[:, :-1] / (s[:, 1:] + s[:, :-1])
    gy = 2 * s[1:, :] * s[:-1, :] / (s[1:, :] + s[:-1, :])
    idx = np.arange(nx * ny).reshape(ny, nx)
    rows = np.concatenate([idx[:, 1:].ravel(), idx[:, :-1].ravel(), idx[1:, :].ravel(), idx[:-1, :].ravel()])
    cols = np.concatenate([idx[:, :-1].ravel(), idx[:, 1:].ravel(), idx[:-1, :].ravel(), idx[1:, :].ravel()])
    vals = -np.concatenate([gx.ravel(), gx.ravel(), gy.ravel(), gy.ravel()])
    lap = sp.csr_matrix((vals, (rows, cols)), shape=(nx * ny, nx * ny))
    diag_lap = -np.asarray(lap.sum(axis=1)).ravel()
    tw = t_wall + K0
    et = eps_pair(eps_top, eps_wall) if np.isscalar(eps_top) else 1 / (1 / eps_top + 1 / eps_wall - 1)
    eb = eps_pair(eps_bot, eps_wall) if np.isscalar(eps_bot) else 1 / (1 / eps_bot + 1 / eps_wall - 1)
    eg = np.zeros((ny, nx)) if extra_g is None else extra_g
    T = np.full((ny, nx), tw + 1.0)
    for _ in range(iters):
        hr = SIGMA * (T ** 2 + tw ** 2) * (T + tw)
        dT = np.maximum(T.mean() - tw, 0.05)
        g = (h_conv_top(dT) + h_conv_bot(dT) + (et + eb) * hr) * a + eg
        A = lap + sp.diags(diag_lap + g.ravel())
        rise = spla.spsolve(A.tocsc(), power.ravel()).reshape(ny, nx)
        T = tw + rise
    g_tot = float(g.sum())
    return T - K0, g_tot, s


# ===========================================================================
# 3. Power budgets
# ===========================================================================
def amp_power(vin):
    """Dissipation per reference designator on the amplifier board (W)."""
    i_aes = 3.3 / (2 * AES_R_DRV + 2 * AES_R_SER + AES_R_LOAD)     # TXP/TXN complementary: |I| constant
    i_pcm_a = I_5VA - I_LMP7721 - 3 * I_LMP7715 - I_DIVIDER
    i_cs = I_3V3 - I_PCM_D - I_OSC - i_aes                    # CS8406 core (remainder of the 45 mA budget)
    i_in = I_5VA + I_3V3 + 2 * I_GND_ADM
    p = {
        "U101": (vin - 5.0) * I_5VA + vin * I_GND_ADM,
        "U102": (vin - 3.3) * I_3V3 + vin * I_GND_ADM,
        "U302": 5.0 * i_pcm_a + 3.3 * I_PCM_D,
        "U401": 3.3 * i_cs + i_aes ** 2 * 2 * AES_R_DRV,
        "R412": i_aes ** 2 * AES_R_SER, "R413": i_aes ** 2 * AES_R_SER,
        "Y402": 3.3 * I_OSC,
        "U201": 5.0 * I_LMP7721, "U202": 5.0 * I_LMP7715, "U203": 5.0 * I_LMP7715, "U301": 5.0 * I_LMP7715,
        "D101": VF_SS34 * i_in,
        "R101": 10.0 * (I_LMP7721 + 2 * I_LMP7715 + I_DIVIDER) ** 2,
        "R204": I_DIVIDER ** 2 * 47e3, "R205": I_DIVIDER ** 2 * 47e3,
    }
    off_board = i_aes ** 2 * AES_R_LOAD
    return p, {"I_in_A": i_in, "P_in_W": (vin + VF_SS34) * i_in, "AES3_line_W_off_board": off_board,
               "I_PCM1804_VCC_A": i_pcm_a, "I_CS8406_core_A": i_cs, "I_AES3_A": i_aes}


def vf(i):
    return 0.27 + 0.33 * i            # SS34 forward voltage, 0.05-0.3 A, 25 C


def psu_power():
    """Periodic bucket charge/discharge model -> average dissipation per part (W)."""
    i_dis = I_LT_OUT + I_Q_LT + I_BAL
    dt = 0.005
    n = int(T_HALF / dt)
    v = 9.4
    for _ in range(40):
        v_lo = v
        acc = {k: 0.0 for k in ("U1", "U2", "R2", "D1", "Rchg", "R4R3", "Ichg")}
        for _k in range(n):
            # CC or CV: the CV stage holds CHG at 10.4 V if the CC stage allows
            ib = 0.1
            for _j in range(4):
                ib = (V_CV - vf(ib) - v) / (R_CHG + R_ESR)
            if ib + I_DIV_CV >= I_CC:              # constant current
                itot = I_CC
                ib = itot - I_DIV_CV
                chg = v + ib * (R_CHG + R_ESR) + vf(ib)
                vdo2 = 1.55 + 0.6 * itot
                p_u2 = vdo2 * itot
                p_r2 = 1.25 * itot
                p_u1 = (V_IRM - chg - vdo2 - 1.25) * itot
            else:                                   # constant voltage, CC stage saturated
                itot = ib + I_DIV_CV
                vdo1 = 1.55 + 0.6 * itot
                p_u1 = vdo1 * itot
                p_r2 = 6.2 * itot ** 2
                p_u2 = (V_IRM - V_CV - vdo1 - 6.2 * itot) * itot
            acc["U1"] += p_u1 * dt
            acc["U2"] += p_u2 * dt
            acc["R2"] += p_r2 * dt
            acc["D1"] += vf(ib) * ib * dt
            acc["Rchg"] += R_CHG * ib ** 2 * dt
            acc["R4R3"] += I_DIV_CV * V_CV * dt
            acc["Ichg"] += itot * dt
            v += (ib - I_BAL) / C_BUCKET * dt
        v_hi = v
        v = v_hi - i_dis * T_HALF / C_BUCKET
        if abs(v - v_lo) < 1e-5:
            break
    # charger runs all the time (one bucket or the other): averages over one half period
    avg = {k: val / T_HALF for k, val in acc.items()}
    v_avg_dis = (v_hi + v) / 2
    v_loadp = v_avg_dis - vf(i_dis) - (R_LOAD + R_ESR) * i_dis
    i_coil = V_COIL / (2 * R_COIL + R_COIL_SER)
    i12 = i_coil * 2 * 0.5 + I_LED + I_4060      # both coil strings on during the same half period
    p = {
        "U1": avg["U1"], "U2": avg["U2"], "R2": avg["R2"], "D1": avg["D1"],
        "R10": avg["Rchg"] / 2, "R11": avg["Rchg"] / 2,
        "R3": (1.25 ** 2) / 240, "R4": I_DIV_CV ** 2 * 1740,
        "U3": (V_IRM - 12.0) * i12 + V_IRM * I_Q_78L,
        "R5": I_LED * (12 - 2.0), "D2": I_LED * 2.0,
        "K1": 0.5 * i_coil ** 2 * R_COIL, "K2": 0.5 * i_coil ** 2 * R_COIL,
        "K3": 0.5 * i_coil ** 2 * R_COIL, "K4": 0.5 * i_coil ** 2 * R_COIL,
        "R24": 0.5 * i_coil ** 2 * R_COIL_SER, "R25": 0.5 * i_coil ** 2 * R_COIL_SER,
        "U4": 12.0 * I_4060,
        "U5": (v_loadp - V_LT) * I_LT_OUT + v_loadp * I_Q_LT,
        "L1": R_CMC * I_LT_OUT ** 2,
        "D6": 0.5 * vf(i_dis) * i_dis, "D7": 0.5 * vf(i_dis) * i_dis,
        "R12": 0.5 * R_LOAD * i_dis ** 2, "R13": 0.5 * R_LOAD * i_dis ** 2,
    }
    for k in range(14, 22):
        p[f"R{k}"] = (2.55 ** 2) / 5100
    i15 = avg["Ichg"] + i12 + I_Q_78L
    p_out = V_IRM * i15
    p["PS1"] = p_out * (1 / ETA_IRM - 1)
    info = {"bucket_V_lo": v, "bucket_V_hi": v_hi, "LOAD_P_avg_V": v_loadp, "I_charger_avg_A": avg["Ichg"],
            "I_12V_avg_A": i12, "I_coil_string_A": i_coil, "IRM_P_out_W": p_out, "IRM_eta_assumed": ETA_IRM,
            "mains_input_W": p_out / ETA_IRM, "delivered_to_cable_W": V_LT * I_LT_OUT - p["L1"]}
    return p, info


# ===========================================================================
# 4. Board cases
# ===========================================================================
def read_island():
    with open(os.path.join(ROOT, "PCB", "antenna_amplifier", "layout.py")) as fh:
        txt = fh.read()
    m = re.search(r"^ISLAND\s*=\s*(\([^\n]*\))", txt, re.M)
    return ast.literal_eval(m.group(1))


def amp_board_model(b, pw, t_shield=25.0, h_contact=H_CONTACT, eps_mask=EPS_MASK):
    ny, nx = b["ny"], b["nx"]
    a = CELL * CELL
    power = np.zeros((ny, nx))
    masks = {}
    for ref, p in pw.items():
        m = box_mask(b, b["fps"][ref]["box"])
        masks[ref] = m
        power[m] += p / m.sum()
    # wall strips: perimeter clamped by frame (top) and tray rim (bottom), internal by the frame only
    eg = np.zeros((ny, nx))
    XX, YY = np.meshgrid(b["xc"], b["yc"])
    for name, (x0, y0, x1, y1) in MP.wall_rects().items():
        m = (XX >= x0) & (XX <= x1) & (YY >= y0) & (YY <= y1)
        eg[m] += h_contact * a * (1 if name.startswith("internal") else 2)
    for (x0, y0, x1, y1) in ((178.0, 0.0, 192.0, 7.0), (193.0, 23.0, 200.0, 43.0)):   # frame cut-outs (layout.CUTOUTS)
        m = (XX >= x0) & (XX <= x1) & (YY >= y0) & (YY <= y1)
        eg[m] = np.minimum(eg[m], h_contact * a)                                       # tray rim still clamps
    isl = read_island()
    mi = (XX >= isl[0]) & (XX <= isl[2]) & (YY >= isl[1]) & (YY <= isl[3])
    eps = np.where(mi, EPS_ENIG, eps_mask)
    gap_top = MP.FRAME_H * 1e-3
    gap_bot = MP.TRAY_DEPTH * 1e-3
    hgt = (MP.PCB_H - 2 * MP.WALL_T) * 1e-3
    T, g_tot, s = solve_board(b, power, t_shield, lambda d: h_gap(gap_top, hgt, d), lambda d: h_gap(gap_bot, hgt, d),
                              eps, eps, EPS_AL, extra_g=eg)
    return T, g_tot, masks, mi, s, eg


def psu_board_model(b, pw, t_box=25.0, eps_mask=EPS_MASK, h_scale=1.0):
    ny, nx = b["ny"], b["nx"]
    a = CELL * CELL
    power = np.zeros((ny, nx))
    masks = {}
    for ref, p in pw.items():
        m = box_mask(b, b["fps"][ref]["box"])
        masks[ref] = m
        power[m] += p / m.sum()
    eg = np.zeros((ny, nx))
    h_body = 2.5 + eps_pair(EPS_PC, EPS_AL) * 6.3       # part bodies to the box: convection + radiation
    # IRM module: its own case surface (above the footprint) also sheds heat
    l, w, hh = IRM_BODY
    m = box_mask(b, b["fps"]["PS1"]["box"])
    eg[m] += h_body * (2 * (l + w) * hh) / m.sum()
    masks.setdefault("PS1", m)
    for k in range(8, 16):                               # EDLC cans are fins
        m = box_mask(b, b["fps"][f"C{k}"]["box"])
        d, L = EDLC_BODY
        eg[m] += h_body * (math.pi * d * L) / m.sum()
        masks[f"C{k}"] = m
    # standoffs: metal M3x10 hex at H1/H3 (PE end), nylon at H2/H4 (psu_box.py)
    for ref, g in (("H1", 0.10), ("H3", 0.10), ("H2", 0.002), ("H4", 0.002)):
        m = box_mask(b, b["fps"][ref]["box"], shrink=1.0)
        eg[m] += g / m.sum()
    gap_bot = MP.PSU_STANDOFF_H * 1e-3
    gap_top = (MP.PSU_INNER_H - MP.PSU_STANDOFF_H - MP.PSU_PCB_T) * 1e-3
    hgt = MP.PSU_PCB_H * 1e-3
    T, g_tot, s = solve_board(b, power, t_box, lambda d: h_scale * h_gap(gap_top, hgt, d),
                              lambda d: h_scale * h_gap(gap_bot, hgt, d), eps_mask, eps_mask, EPS_AL, extra_g=eg)
    return T, g_tot, masks, s


def part_temps(T, masks, pw, groups=None):
    out = {}
    for ref, m in masks.items():
        tb = float(T[m].max())
        p = pw.get(ref, 0.0)
        out[ref] = {"P_W": p, "T_board_C": tb, "T_j_C": tb + p * THETA.get(ref, 0.0)}
    return out


# ===========================================================================
# 5. Enclosure network
# ===========================================================================
def sun(day, hour_utc):
    decl = math.radians(23.45 * math.sin(2 * math.pi * (284 + day) / 365))
    bb = 2 * math.pi * (day - 81) / 364
    eot = 9.87 * math.sin(2 * bb) - 7.53 * math.cos(bb) - 1.5 * math.sin(bb)
    st = hour_utc + LON / 15 + eot / 60
    hra = math.radians(15 * (st - 12))
    lat = math.radians(LAT)
    cz = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(hra)
    z = math.acos(max(-1, min(1, cz)))
    az = math.atan2(-math.sin(hra) * math.cos(decl), math.sin(decl) * math.cos(lat) - math.cos(decl) * math.sin(lat) * math.cos(hra))
    return z, az % (2 * math.pi)


def clear_sky(z):
    """Meinel/ASHRAE clear-sky beam and diffuse (W/m2)."""
    if z >= math.radians(89.5):
        return 0.0, 0.0
    zd = math.degrees(z)
    am = 1.0 / (math.cos(z) + 0.50572 * (96.07995 - zd) ** -1.6364)
    dni = 1361.0 * 0.7 ** (am ** 0.678)
    return dni, DIFFUSE_C * dni


def ambient_profile(tmax, tmin, dst=0):
    """ASHRAE design-day fraction of the daily range, hour 1..24 of local standard time
    (minimum at 05:00, maximum at 15:00 standard time; dst = 1 shifts it to CEST)."""
    frac = [0.87, 0.92, 0.96, 0.99, 1.00, 0.98, 0.93, 0.84, 0.71, 0.56, 0.39, 0.23,
            0.11, 0.03, 0.00, 0.03, 0.10, 0.21, 0.34, 0.47, 0.58, 0.68, 0.76, 0.82]
    hrs = np.arange(1, 25)
    f = np.array(frac)

    def ta(h):
        hh = (h - dst) % 24
        return tmax - np.interp(hh, np.r_[0, hrs], np.r_[f[-1], f]) * (tmax - tmin)
    return ta


def sky_temp(ta_c, td_c, cloud=0.0):
    """Berdahl & Martin clear-sky emissivity, cloud fraction raises it towards 1."""
    e = 0.711 + 0.56 * td_c / 100 + 0.73 * (td_c / 100) ** 2
    e = e + (1 - e) * 0.8 * cloud
    return (ta_c + K0) * e ** 0.25 - K0


def dew_point(t, rh):
    a, bb = 17.62, 243.12
    g = math.log(rh) + a * t / (bb + t)
    return bb * g / (a - g)


def faces(az_door):
    """(name, area, tilt from horizontal-up normal, outward azimuth, char. length)."""
    w, h, d = BOX_OUT
    return [("door", w * h, math.pi / 2, az_door, h),
            ("back", w * h, math.pi / 2, az_door + math.pi, h),
            ("left", h * d, math.pi / 2, az_door - math.pi / 2, h),
            ("right", h * d, math.pi / 2, az_door + math.pi / 2, h),
            ("top", w * d, 0.0, 0.0, d),
            ("bottom", w * d, math.pi, 0.0, d)]


def irradiance(fc, z, az, dni, dhi, shade=False):
    out = []
    ghi = dni * math.cos(z) + dhi if z < math.pi / 2 else 0.0
    for (_n, _a, tilt, gam, _L) in fc:
        ci = math.cos(z) * math.cos(tilt) + math.sin(z) * math.sin(tilt) * math.cos(az - gam)
        beam = 0.0 if shade else dni * max(ci, 0.0)
        out.append(beam + dhi * (1 + math.cos(tilt)) / 2 + ALBEDO * ghi * (1 - math.cos(tilt)) / 2)
    return out, ghi


def unit_geometry():
    """Areas and heat capacities of the units inside the box (from mechanical/params.py)."""
    ft = MP.WALL_T
    bars = (2 * MP.PCB_W * ft + 4 * (MP.PCB_H - 2 * ft) * ft) * MP.FRAME_H
    lid = (MP.PCB_W + 2 * MP.LID_EAR) * MP.PCB_H * MP.LID_T
    tray = MP.PCB_W * MP.PCB_H * MP.TRAY_T - (MP.PCB_W - 2 * ft) * (MP.PCB_H - 2 * ft) * MP.TRAY_DEPTH
    v_amp = (bars + lid + tray) * 1e-9
    hs = (MP.FRAME_H + MP.PCB_T + MP.TRAY_T) * 1e-3          # shield side height (lid on the plate)
    a_amp_out = (MP.PCB_W * MP.PCB_H) * 1e-6 + 2 * (MP.PCB_W + MP.PCB_H) * 1e-3 * hs
    a_amp_lid = (MP.PCB_W + 2 * MP.LID_EAR) * MP.PCB_H * 1e-6
    ow, od = MP.PSU_INNER_W + 2 * MP.PSU_BAR_T, MP.PSU_INNER_D + 2 * MP.PSU_BAR_T
    v_psu = (2 * ow * MP.PSU_BAR_T + 2 * MP.PSU_INNER_D * MP.PSU_BAR_T) * MP.PSU_INNER_H \
        + (ow + 2 * MP.PSU_EAR) * od * MP.PSU_BASE_T + ow * od * MP.PSU_LID_T
    v_psu *= 1e-9
    hp = (MP.PSU_INNER_H + MP.PSU_LID_T) * 1e-3
    a_psu_out = ow * od * 1e-6 + 2 * (ow + od) * 1e-3 * hp
    a_psu_base = (ow + 2 * MP.PSU_EAR) * od * 1e-6
    a_plate = MP.MOUNT_PLATE_W * MP.MOUNT_PLATE_H * 1e-6
    return {"amp_shield_kg": v_amp * 2700, "amp_shield_C": v_amp * 2700 * 900, "amp_out_m2": a_amp_out,
            "amp_lid_m2": a_amp_lid, "amp_board_C": 130.0,
            "psu_box_kg": v_psu * 2700, "psu_box_C": v_psu * 2700 * 900, "psu_out_m2": a_psu_out,
            "psu_base_m2": a_psu_base, "psu_board_C": 160.0,
            "plate_m2": a_plate, "plate_C": a_plate * MP.MOUNT_PLATE_T * 1e-3 * 950 * 1900,
            "air_C": (MP.BOX_INNER_W * MP.BOX_INNER_H * MP.BOX_INNER_D * 1e-9 - 0.004) * 1.15 * 1007}


GEO = unit_geometry()


def h_nat(dT, L):
    return 1.42 * ((dT * dT + 0.04) ** 0.5 / L) ** 0.25


class Enclosure:
    """Nodes: 0-5 box faces, 6 air, 7 plate, 8 amp shield, 9 amp board, 10 PSU box, 11 PSU board.
    Radiation inside: mean-radiant-temperature star node (Walton)."""
    N = 12

    def __init__(self, case, g_amp_board, g_psu_board, p_amp, p_psu):
        self.c = case
        self.fc = faces(math.radians(case.get("door_az", 180.0)))
        self.g_ab, self.g_pb = g_amp_board, g_psu_board
        self.p_amp, self.p_psu = p_amp, p_psu
        a = [f[1] for f in self.fc]
        self.A = np.array(a)
        self.cap = np.zeros(self.N)
        self.cap[:6] = self.A * BOX_WALL * PC_RHO_CP
        self.cap[6] = GEO["air_C"]
        self.cap[7] = GEO["plate_C"]
        self.cap[8] = GEO["amp_shield_C"]
        self.cap[9] = GEO["amp_board_C"]
        self.cap[10] = GEO["psu_box_C"]
        self.cap[11] = GEO["psu_board_C"]
        # inner areas (4 mm smaller each way), facing the interior
        self.Ain = self.A * 0.95
        self.Ain[1] = self.Ain[1] - GEO["plate_m2"]           # back wall hidden behind the plate
        self.a_amp = GEO["amp_out_m2"]
        self.a_psu = GEO["psu_out_m2"]
        self.a_plate = GEO["plate_m2"] - GEO["amp_lid_m2"] - GEO["psu_base_m2"]
        # radiating surfaces into the star node: faces (inner), plate front, amp shield, PSU box
        self.eA = np.r_[EPS_PC * self.Ain, EPS_PE * self.a_plate, EPS_AL * self.a_amp, EPS_AL * self.a_psu]
        # fixed conductances
        hr_gap = 4 * SIGMA * 300 ** 3
        self.g_plate_back = GEO["plate_m2"] * (K_AIR / (MP.BOX_BOSS_H * 1e-3) + eps_pair(EPS_PE, EPS_PC) * hr_gap)
        sp_g = 0.05                                             # 4 M4 studs + spacers into PE-HD (per unit)
        self.g_lid_plate = GEO["amp_lid_m2"] * (K_AIR / (MP.MOUNT_SPACER_H * 1e-3) + eps_pair(EPS_AL, EPS_PE) * hr_gap) + sp_g
        self.g_base_plate = GEO["psu_base_m2"] * (K_AIR / (MP.MOUNT_SPACER_H * 1e-3) + eps_pair(EPS_AL, EPS_PE) * hr_gap) + sp_g
        # wall conduction (4 mm PC) in series with nothing: faces are single nodes
        self.precompute()

    def precompute(self):
        c = self.c
        day, utc = c["day"], c["utc_offset"]
        self.tgrid = np.arange(0, 24 * 3600 + 1, 60.0)
        ta = ambient_profile(c["tmax"], c["tmin"], dst=utc - 1)
        hrs = self.tgrid / 3600
        self.ta = np.array([ta(h) for h in hrs])
        self.td = np.minimum(np.full_like(self.ta, c["td"]), self.ta)
        cloud = np.zeros_like(hrs)
        sunfac = np.ones_like(hrs)
        for (t0, t1, f) in c.get("clouds", []):
            m = (hrs >= t0) & (hrs < t1)
            sunfac[m] = f
            cloud[m] = 1.0 - f
        self.tsky = np.array([sky_temp(a, d, cl) for a, d, cl in zip(self.ta, self.td, cloud)])
        q = np.zeros((len(hrs), 6))
        ghi = np.zeros(len(hrs))
        for i, h in enumerate(hrs):
            z, az = sun(day, h - utc)
            dni, dhi = clear_sky(z)
            dni2 = dni * sunfac[i]
            dhi2 = dhi + (dni - dni2) * 0.25 * math.cos(z) if z < math.pi / 2 else 0.0   # cloud: some beam -> diffuse
            q[i], ghi[i] = irradiance(self.fc, z, az, dni2, dhi2, shade=c.get("shade", False))
        self.q = q
        self.ghi = ghi
        self.tgnd = self.ta + 0.008 * ghi                         # sunlit grass surface
        self.wind = np.full_like(hrs, c["wind"])
        for (t0, t1, v) in c.get("gusts", []):
            self.wind[(hrs >= t0) & (hrs < t1)] = v

    def inputs(self, t):
        tt = t % (24 * 3600)
        i = min(int(tt // 60), len(self.tgrid) - 2)
        f = (tt - self.tgrid[i]) / 60.0
        lerp = lambda arr: arr[i] * (1 - f) + arr[i + 1] * f
        return lerp(self.ta), lerp(self.tsky), lerp(self.tgnd), self.q[i] * (1 - f) + self.q[i + 1] * f, lerp(self.wind)

    def rhs(self, t, x, alpha=None, dq=0.0, dv=0.0):
        alpha = self.c["alpha"] if alpha is None else alpha
        ta, tsky, tgnd, q, wind = self.inputs(t)
        wind = wind + dv
        Tk = x + K0
        dx = np.zeros(self.N)
        # outer faces
        for k, (_n, A, tilt, _g, L) in enumerate(self.fc):
            fsky = (1 + math.cos(tilt)) / 2
            if self.c.get("shade"):        # roof above the box: top sees the roof (~ambient), sides half their sky
                fsky = fsky * (0.0 if k == 4 else 0.5)
            hc = (h_nat(x[k] - ta, L) ** 3 + (2.8 + 3.0 * wind) ** 3) ** (1 / 3)
            qo = A * (alpha * (q[k] * (1 + dq)) - hc * (x[k] - ta)
                      - EPS_PC * SIGMA * (fsky * (Tk[k] ** 4 - (tsky + K0) ** 4) + (1 - fsky) * (Tk[k] ** 4 - (tgnd + K0) ** 4)))
            dx[k] += qo
        # interior convection to air
        air = x[6]
        for k in range(6):
            g = self.Ain[k] * max(H_IN_MIN, h_nat(x[k] - air, 0.3))
            dx[k] -= g * (x[k] - air)
            dx[6] += g * (x[k] - air)
        for node, area in ((7, self.a_plate), (8, self.a_amp), (10, self.a_psu)):
            g = area * max(H_IN_MIN, h_nat(x[node] - air, 0.15))
            dx[node] -= g * (x[node] - air)
            dx[6] += g * (x[node] - air)
        # interior radiation via the MRT star
        trad = np.r_[Tk[:6], Tk[7], Tk[8], Tk[10]]
        tm4 = np.sum(self.eA * trad ** 4) / np.sum(self.eA)
        qr = self.eA * SIGMA * (trad ** 4 - tm4)
        dx[:6] -= qr[:6]
        dx[7] -= qr[6]
        dx[8] -= qr[7]
        dx[10] -= qr[8]
        # plate links
        for a_, b_, g in ((7, 1, self.g_plate_back), (8, 7, self.g_lid_plate), (10, 7, self.g_base_plate),
                          (9, 8, self.g_ab), (11, 10, self.g_pb)):
            f_ = g * (x[a_] - x[b_])
            dx[a_] -= f_
            dx[b_] += f_
        dx[9] += self.p_amp
        dx[11] += self.p_psu
        return dx / self.cap

    def run(self, days=3):
        x0 = np.full(self.N, float(self.c["tmin"]) + 3)
        sol = solve_ivp(self.rhs, (0, days * 86400), x0, method="LSODA", max_step=120.0, rtol=1e-6, atol=1e-4,
                        t_eval=np.arange((days - 1) * 86400, days * 86400 + 1, 60.0))
        t = sol.t - (days - 1) * 86400
        return t / 3600, sol.y


# ===========================================================================
# 6. Main
# ===========================================================================
def main():
    results = {"meta": {"method": "2-D finite differences (boards) + lumped transient network (enclosure)",
                        "sources": ["PCB/antenna_amplifier/antenna_amplifier.kicad_pcb", "PCB/acdc_converter/acdc_converter.kicad_pcb",
                                    "PCB/*/design.py", "mechanical/params.py", "simulations/psu", "simulations/system"],
                        "site": {"lat": LAT, "lon": LON, "region": "east Slovenia (Pannonian lowland)"}}}

    # ---------------- power budgets ----------------
    amp_cases = {}
    for name, vin in VIN_CASES.items():
        pw, info = amp_power(vin)
        amp_cases[name] = {"V_in_after_SS34_V": vin, "parts_W": pw, "total_W": sum(pw.values()), **info}
    pw_psu, info_psu = psu_power()
    results["power"] = {"amplifier": amp_cases,
                        "psu": {"parts_W": pw_psu, "total_W": sum(pw_psu.values()), **info_psu}}
    print("amplifier dissipation:", {k: round(v["total_W"], 3) for k, v in amp_cases.items()})
    print("PSU dissipation: %.3f W" % sum(pw_psu.values()), {k: round(v, 3) for k, v in pw_psu.items() if v > 0.02})

    # ---------------- boards ----------------
    amp = read_board(os.path.join(ROOT, "PCB", "antenna_amplifier", "antenna_amplifier.kicad_pcb"))
    psu = read_board(os.path.join(ROOT, "PCB", "acdc_converter", "acdc_converter.kicad_pcb"))
    cov = {"amplifier": {l: float(amp["cu"][l].mean()) for l in amp["layers"]},
           "psu": {l: float(psu["cu"][l].mean()) for l in psu["layers"]}}
    results["copper_coverage"] = cov
    print("copper coverage:", cov)

    board = {"amplifier": {}, "psu": {}}
    keep = {}
    for name in VIN_CASES:
        pw = amp_cases[name]["parts_W"]
        T, g, masks, mi, s, eg = amp_board_model(amp, pw)
        pt = part_temps(T, masks, pw)
        isl = T[mi]
        board["amplifier"][name] = {
            "rise_max_K": float(T.max() - 25), "rise_mean_K": float(T.mean() - 25), "G_to_shield_W_per_K": g,
            "hottest": max(pt, key=lambda r: pt[r]["T_j_C"]), "parts_rise_K": {r: {"P_W": v["P_W"], "board_rise_K": v["T_board_C"] - 25,
                                                                                  "junction_rise_K": v["T_j_C"] - 25} for r, v in pt.items()},
            "U201_rise_K": pt["U201"]["T_j_C"] - 25, "U201_board_rise_K": pt["U201"]["T_board_C"] - 25,
            "guard_island_dT_K": float(isl.max() - isl.min()), "guard_island_rise_K": float(isl.mean() - 25)}
        keep[name] = (T, masks)
    sens = {}
    nom = list(VIN_CASES)[0]
    pw0 = amp_cases[nom]["parts_W"]
    for hc in H_CONTACT_SWEEP:
        T, g, masks, mi, s, eg = amp_board_model(amp, pw0, h_contact=hc)
        sens[f"h_contact {hc:g} W/m2K"] = {"rise_max_K": float(T.max() - 25), "U201_board_rise_K": float(T[masks["U201"]].max() - 25),
                                           "G_to_shield_W_per_K": g}
    T, g, masks, mi, s, eg = amp_board_model(amp, pw0, h_contact=0.0)
    sens["no wall contact (strips insulated)"] = {"rise_max_K": float(T.max() - 25), "U201_board_rise_K": float(T[masks["U201"]].max() - 25),
                                                  "G_to_shield_W_per_K": g}
    board["amplifier_sensitivity"] = sens
    # white mask: same IR emissivity as green; 0.80 as a pessimistic white
    wm = {}
    for lab, e in (("green mask eps 0.90", 0.90), ("white mask eps 0.88", 0.88), ("pessimistic eps 0.80", 0.80)):
        T, g, masks, mi, s, eg = amp_board_model(amp, pw0, eps_mask=e)
        Tp, gp, mp_, sp_ = psu_board_model(psu, pw_psu, eps_mask=e)
        wm[lab] = {"amp_max_rise_K": float(T.max() - 25), "U201_rise_K": float(T[masks["U201"]].max() - 25),
                   "psu_max_rise_K": float(Tp.max() - 25)}
    board["mask_colour"] = wm

    Tp, gp, masks_p, s_p = psu_board_model(psu, pw_psu)
    Tp2, _, _, _ = psu_board_model(psu, pw_psu, h_scale=2.0)
    board["psu_sensitivity"] = {"convection x2 (stirred box air)": {"rise_max_K": float(Tp2.max() - 25)}}
    ptp = part_temps(Tp, masks_p, pw_psu)
    edlc = [ptp[f"C{k}"]["T_board_C"] - 25 for k in range(8, 16)]
    board["psu"] = {"rise_max_K": float(Tp.max() - 25), "rise_mean_K": float(Tp.mean() - 25), "G_to_box_W_per_K": gp,
                    "parts_rise_K": {r: {"P_W": v["P_W"], "board_rise_K": v["T_board_C"] - 25, "junction_rise_K": v["T_j_C"] - 25}
                                     for r, v in ptp.items()},
                    "EDLC_rise_K_max": max(edlc), "EDLC_rise_K_min": min(edlc)}
    results["boards_steady_25C_walls"] = board
    for name in VIN_CASES:
        bb = board["amplifier"][name]
        print(f"amp [{name}]: max rise {bb['rise_max_K']:.2f} K, hottest {bb['hottest']} "
              f"Tj rise {bb['parts_rise_K'][bb['hottest']]['junction_rise_K']:.1f} K, U201 {bb['U201_rise_K']:.3f} K, "
              f"island dT {bb['guard_island_dT_K']*1e3:.1f} mK")
    print(f"psu: max rise {board['psu']['rise_max_K']:.1f} K, G {gp:.3f} W/K")

    # ---------------- enclosure, 24 h ----------------
    g_ab = board["amplifier"][nom]["G_to_shield_W_per_K"]
    p_amp = amp_cases[nom]["total_W"]
    p_psu = sum(pw_psu.values())
    rise_amp = board["amplifier"][nom]
    rise_psu = board["psu"]
    kappa_u201 = rise_amp["U201_board_rise_K"] / rise_amp["rise_mean_K"]
    summer = dict(day=196, utc_offset=2, tmax=37.0, tmin=21.0, td=18.0, wind=1.0, door_az=180.0)
    cases = {}
    for cname, alpha in COLOURS.items():
        for door, az in (("S", 180.0), ("W", 270.0)):
            cases[f"summer, {cname}, door {door}"] = dict(summer, alpha=alpha, door_az=az)
    cases["summer, light grey + sun shade (beam blocked), door S"] = dict(summer, alpha=0.55, shade=True)
    cases["record summer 40 C, light grey, door W"] = dict(summer, alpha=0.55, door_az=270.0, tmax=40.0, tmin=24.0, td=20.0)
    cases["summer, light grey, door S, wind 3 m/s"] = dict(summer, alpha=0.55, wind=3.0)
    cases["summer, light grey, door S, clouds + gust"] = dict(summer, alpha=0.55, clouds=[(13.0, 13.25, 0.15), (14.0, 14.1, 0.15)],
                                                              gusts=[(15.0, 15.05, 25.0)])
    winter = dict(day=15, utc_offset=1, tmax=-6.0, tmin=-18.0, td=-21.0, wind=1.0, door_az=180.0, alpha=0.55)
    cases["winter cold spell -18 C, light grey, PSU"] = dict(winter)
    cases["winter cold spell -18 C, light grey, battery (no PSU)"] = dict(winter, battery=True)
    autumn = dict(day=305, utc_offset=1, tmax=11.0, tmin=2.0, td=2.0, wind=0.5, door_az=180.0, alpha=0.55)
    cases["autumn clear night, fog at dawn, light grey"] = dict(autumn)
    cases["autumn clear night, fog at dawn, light grey, battery"] = dict(autumn, battery=True)
    cases["autumn clear night, fog at dawn, light grey + shade roof"] = dict(autumn, shade=True)

    enc = {}
    traces = {}
    for cname, c in cases.items():
        batt = c.get("battery", False)
        if batt:
            pw_b, _ = amp_power(VIN_CASES["fresh PP3 battery 9.6 V"])
            pa, pp = sum(pw_b.values()), 0.0
        else:
            pa, pp = p_amp, p_psu
        e = Enclosure(c, g_ab, gp, pa, pp)
        hrs, y = e.run()
        ta = np.interp(hrs, e.tgrid / 3600, e.ta)
        td = np.interp(hrs, e.tgrid / 3600, e.td)
        t_shield, t_board, t_psu, t_air = y[8], y[9], y[11], y[6]
        scale_a = pa / p_amp if p_amp else 0
        u201 = t_shield + kappa_u201 * (t_board - t_shield)
        amp_hot = t_shield + (t_board - t_shield) * (rise_amp["rise_max_K"] / rise_amp["rise_mean_K"])
        psu_hot = (y[10] + (t_psu - y[10]) * (rise_psu["rise_max_K"] / rise_psu["rise_mean_K"])) if pp else y[10]
        edlc_t = (y[10] + (t_psu - y[10]) * (rise_psu["EDLC_rise_K_max"] / rise_psu["rise_mean_K"])) if pp else y[10]
        psu_air = y[10] + 0.5 * (t_psu - y[10])          # PSU box air: between its walls and the board (estimate)
        dudt = np.gradient(u201, hrs)                      # K/h
        inner_min = y[:6].min(axis=0)
        r = {"T_ambient_C": [float(ta.min()), float(ta.max())],
             "T_box_air_C": [float(t_air.min()), float(t_air.max())],
             "T_box_face_max_C": float(y[:6].max()),
             "T_amp_shield_C": [float(t_shield.min()), float(t_shield.max())],
             "T_U201_C": [float(u201.min()), float(u201.max())],
             "T_amp_board_hottest_C": [float(amp_hot.min()), float(amp_hot.max())],
             "T_psu_box_C": [float(y[10].min()), float(y[10].max())],
             "T_psu_board_hottest_C": [float(psu_hot.min()), float(psu_hot.max())],
             "T_EDLC_max_C": float(edlc_t.max()), "T_EDLC_mean_C": float(edlc_t.mean()),
             "T_EDLC_life_equivalent_C": float(IB_DOUBLING_K * np.log2(np.mean(2 ** (edlc_t / IB_DOUBLING_K)))),
             "T_psu_box_air_est_C": [float(psu_air.min()), float(psu_air.max())],
             "U201_rate_max_K_per_h": float(np.abs(dudt).max()),
             "U201_rate_max_heating_K_per_h": float(dudt.max()), "U201_rate_max_cooling_K_per_h": float(-dudt.min()),
             "air_minus_ambient_max_K": float((t_air - ta).max()), "air_minus_ambient_min_K": float((t_air - ta).min()),
             "inner_face_min_minus_dewpoint_vented_K": float((inner_min - td).min()),
             "board_minus_dewpoint_vented_K": float((u201 - td).min()),
             "P_amp_W": pa, "P_psu_W": pp, "alpha": c["alpha"]}
        # internal dew point of a sealed box with silica gel: assumed -10 C
        r["inner_face_min_minus_dewpoint_sealed_desiccant_K"] = float((inner_min - (-10.0)).min())
        # part junction maxima (board-model rises scaled onto the transient)
        if not batt:
            jt = {}
            for ref in ("U101", "U102", "U302", "U401", "U201"):
                jt[ref] = float(t_shield.max() + rise_amp["parts_rise_K"][ref]["junction_rise_K"] / rise_amp["rise_mean_K"]
                                * (t_board - t_shield)[np.argmax(t_shield)])
            for ref in ("U1", "U2", "U3", "U5", "PS1"):
                k = rise_psu["parts_rise_K"][ref]["junction_rise_K"] / rise_psu["rise_mean_K"]
                jt[ref] = float((y[10] + k * (t_psu - y[10])).max())
            r["T_max_C"] = jt
            jmin = {}
            for ref in ("U201", "U302", "U401", "Y402"):
                k = rise_amp["parts_rise_K"][ref]["board_rise_K"] / rise_amp["rise_mean_K"]
                jmin[ref] = float((t_shield + k * (t_board - t_shield)).min())
            for ref in ("U1", "U2", "U3", "PS1", "K1"):
                k = rise_psu["parts_rise_K"][ref]["board_rise_K"] / rise_psu["rise_mean_K"]
                jmin[ref] = float((y[10] + k * (t_psu - y[10])).min())
            r["T_min_C"] = jmin
        else:
            r["T_min_C"] = {"U201..U401 (board)": float(t_shield.min())}
        enc[cname] = r
        traces[cname] = {"h": hrs, "ta": ta, "air": t_air, "u201": u201, "psu": psu_hot, "edlc": edlc_t,
                         "faces": y[:6], "td": td, "ghi": np.interp(hrs, e.tgrid / 3600, e.ghi), "dudt": dudt,
                         "shield": t_shield}
        print(f"{cname:58s} air {r['T_box_air_C'][0]:6.1f}..{r['T_box_air_C'][1]:5.1f}  U201 {r['T_U201_C'][0]:6.1f}..{r['T_U201_C'][1]:5.1f}"
              f"  PSU hot {r['T_psu_board_hottest_C'][1]:5.1f}  rate {r['U201_rate_max_K_per_h']:.2f} K/h")
    results["enclosure_24h"] = enc

    # ---------------- frequency response: sun / wind -> U201 ----------------
    c0 = cases["summer, light grey, door S, wind 3 m/s"]
    e = Enclosure(dict(c0), g_ab, gp, p_amp, p_psu)
    hrs, y = e.run()
    t_noon = 13.0 * 3600
    x0 = y[:, np.argmin(abs(hrs - 13.0))]
    f0 = e.rhs(t_noon, x0)
    Jm = np.zeros((e.N, e.N))
    for k in range(e.N):
        dx = np.zeros(e.N)
        dx[k] = 1e-3
        Jm[:, k] = (e.rhs(t_noon, x0 + dx) - f0) / 1e-3
    ghi_noon = float(np.interp(13.0, e.tgrid / 3600, e.ghi))
    Bq = (e.rhs(t_noon, x0, dq=1e-3) - f0) / 1e-3 / ghi_noon       # per W/m2 of GHI (all components scaled)
    Bv = (e.rhs(t_noon, x0, dv=1e-2) - f0) / 1e-2                  # per m/s
    cvec = np.zeros(e.N)
    cvec[8] = 1 - kappa_u201
    cvec[9] = kappa_u201
    freqs = np.logspace(-5, 0.5, 300)
    Hq = np.array([abs(cvec @ np.linalg.solve(2j * np.pi * f * np.eye(e.N) - Jm, Bq)) for f in freqs])
    Hv = np.array([abs(cvec @ np.linalg.solve(2j * np.pi * f * np.eye(e.N) - Jm, Bv)) for f in freqs])
    taus = sorted(-1 / np.linalg.eigvals(Jm).real)
    t_u = max(enc["summer, light grey RAL 7035 (as supplied), door W"]["T_U201_C"][1], 25.0)
    ib_typ = IB25_TYP * 2 ** ((t_u - 25) / IB_DOUBLING_K)
    dib_dt = ib_typ * math.log(2) / IB_DOUBLING_K
    dib_dt_max = IB25_MAX * 2 ** ((t_u - 25) / IB_DOUBLING_K) * math.log(2) / IB_DOUBLING_K

    def v_inp(f, dI):
        w = 2 * np.pi * f
        return dI * R_J202 / np.abs(1 + 1j * w * R_J202 * C_NODE)

    fr = {}
    for f in (1e-3, 1e-2, 0.1, 1.0):
        hq = float(np.interp(np.log(f), np.log(freqs), Hq))
        hv = float(np.interp(np.log(f), np.log(freqs), Hv))
        dT_cloud = hq * 800.0           # 800 W/m2 of sun modulated (cloud train), peak
        dT_gust = hv * 10.0             # 10 m/s wind modulation, peak
        fr[f"{f:g} Hz"] = {"K_per_Wm2": hq, "K_per_m_s": hv, "dT_U201_cloud_800Wm2_K": dT_cloud,
                           "dT_U201_gust_10ms_K": dT_gust,
                           "V_INP_from_Ib_typ_cloud_V": float(v_inp(f, dib_dt * dT_cloud)),
                           "V_INP_from_Ib_max_cloud_V": float(v_inp(f, dib_dt_max * dT_cloud)),
                           "V_INP_from_TCVos_cloud_V": TCVOS * dT_cloud,
                           "V_INP_from_TCVos_gust_V": TCVOS * dT_gust}
    results["frequency_response_U201"] = {"operating_point": "summer clear day 13:00, light grey, door S, 3 m/s",
                                          "time_constants_s": [float(x) for x in taus],
                                          "points": fr, "noise_IN_P_SR1_V_per_rtHz": NOISE_INP_SR1,
                                          "note": "amplitudes (V peak at IN_P) for a sinusoidal modulation of the given size; "
                                                  "compare with the receiver noise in a 1 Hz bin (26.7 nV rms at IN_P)."}

    # ---------------- LMP7721 bias current vs temperature ----------------
    ts = np.arange(-20, 71, 1.0)
    ib_t = IB25_TYP * 2 ** ((ts - 25) / IB_DOUBLING_K)
    ib_m = IB25_MAX * 2 ** ((ts - 25) / IB_DOUBLING_K)
    shot_t = np.sqrt(2 * Q_E * ib_t)
    shot_m = np.sqrt(2 * Q_E * ib_m)
    v_t = shot_t * Z_ANT_PER_A
    v_m = shot_m * Z_ANT_PER_A
    tot_t = np.sqrt(NOISE_ANT_100G ** 2 + v_t ** 2)
    tot_m = np.sqrt(NOISE_ANT_100G ** 2 + v_m ** 2)
    ib_tab = {}
    for tt in (-15.0, 25.0, 40.0, 50.0, 60.0):
        i = int(np.argmin(abs(ts - tt)))
        ib_tab[f"{tt:g} C"] = {"Ib_typ_fA": float(ib_t[i] * 1e15), "Ib_max_fA": float(ib_m[i] * 1e15),
                               "shot_typ_aA_rtHz": float(shot_t[i] * 1e18), "shot_max_aA_rtHz": float(shot_m[i] * 1e18),
                               "at_antenna_typ_nV": float(v_t[i] * 1e9), "at_antenna_max_nV": float(v_m[i] * 1e9),
                               "total_SR1_100G_typ_nV": float(tot_t[i] * 1e9), "total_SR1_100G_max_nV": float(tot_m[i] * 1e9),
                               "DC_shift_100G_typ_mV": float(ib_t[i] * R_J202 * 1e3), "DC_shift_100G_max_mV": float(ib_m[i] * R_J202 * 1e3)}
    results["lmp7721_bias_vs_T"] = {"doubling_K": IB_DOUBLING_K, "Ib25_typ_fA": IB25_TYP * 1e15, "Ib25_max_fA": IB25_MAX * 1e15,
                                    "transimpedance_to_antenna_SR1_ohm": Z_ANT_PER_A, "table": ib_tab,
                                    "note": "shot noise sqrt(2 q Ib) at IN_P referred to the antenna with the simulations/system "
                                            "transfer (J202 = 100 G, SR1); total = 74.8 nV/rtHz budget + this term in quadrature "
                                            "(the budget already holds 0.01 fA/rtHz, i.e. this slightly double counts)."}

    # ---------------- verdicts ----------------
    worst_sum = max((k for k in enc if k.startswith("summer") or k.startswith("record")), key=lambda k: enc[k]["T_psu_board_hottest_C"][1])
    tj_all = {}
    for k, v in enc.items():
        for ref, t in v.get("T_max_C", {}).items():
            tj_all[ref] = max(tj_all.get(ref, -99), t)
    tmin_all = {}
    for k, v in enc.items():
        for ref, t in v.get("T_min_C", {}).items():
            tmin_all[ref] = min(tmin_all.get(ref, 99), t)
    results["extremes"] = {"T_max_C_all_cases": tj_all, "T_min_C_all_cases": tmin_all, "hottest_case": worst_sum}
    edlc_max = enc["record summer 40 C, light grey, door W"]["T_EDLC_max_C"]
    irm_amb = max(v["T_psu_box_air_est_C"][1] for k, v in enc.items() if "black" not in k)
    autumn_v = enc["autumn clear night, fog at dawn, light grey"]
    grey = enc["summer, light grey RAL 7035 (as supplied), door W"]
    white = enc["summer, white paint, door W"]
    verdict = {
        "all junctions <= 125 C (record summer)": all(t < 125 for t in tj_all.values()),
        "LMP7721 <= 85 C (record summer)": tj_all["U201"] < 85,
        "CS8406 <= 70 C (commercial grade, record summer)": tj_all["U401"] < 70,
        "PCM1804 <= 85 C": tj_all["U302"] < 85,
        "EDLC <= 65 C (light grey, record summer)": edlc_max < 65,
        "IRM-05 ambient (PSU box air) <= 70 C (41 % load; grey/white cases)": irm_amb < 70,
        "CS8406-CZZ >= -10 C in a -18 C cold spell": tmin_all["U401"] >= -10,
        "LM317 >= 0 C junction in a -18 C cold spell (TI recommended range)": tmin_all["U1"] >= 0,
        "sun/wind artefact at >= 1 Hz below 1/1000 of the 1 Hz-bin noise (max-Ib part)":
            max(fr["1 Hz"]["V_INP_from_Ib_max_cloud_V"], fr["1 Hz"]["V_INP_from_TCVos_cloud_V"],
                fr["1 Hz"]["V_INP_from_TCVos_gust_V"]) < NOISE_INP_SR1 * 1e-3,
        "sun/wind artefact at 0.1 Hz below the noise in a 0.01 Hz bin (max-Ib part)":
            max(fr["0.1 Hz"]["V_INP_from_Ib_max_cloud_V"], fr["0.1 Hz"]["V_INP_from_TCVos_cloud_V"],
                fr["0.1 Hz"]["V_INP_from_TCVos_gust_V"]) < NOISE_INP_SR1 * 0.1,
        "no condensation on the boards, vented box, autumn clear night": autumn_v["board_minus_dewpoint_vented_K"] > 0,
        "no condensation on the inner walls, vented box, autumn clear night": autumn_v["inner_face_min_minus_dewpoint_vented_K"] > 0,
        "no condensation anywhere, sealed box + silica gel (dew point -10 C)":
            all(v["inner_face_min_minus_dewpoint_sealed_desiccant_K"] > 0 for k, v in enc.items() if not k.startswith("winter")),
    }
    results["verdict"] = verdict
    results["white_box_vs_grey_door_W"] = {"air_max_C": [grey["T_box_air_C"][1], white["T_box_air_C"][1]],
                                           "U201_max_C": [grey["T_U201_C"][1], white["T_U201_C"][1]],
                                           "EDLC_max_C": [grey["T_EDLC_max_C"], white["T_EDLC_max_C"]]}
    results["geometry"] = GEO

    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=float)
    print("results.json written")

    plot_boards(amp, psu, keep[nom][0], Tp, amp_cases[nom]["parts_W"], pw_psu)
    plot_24h(traces)
    plot_frontend(freqs, Hq, Hv, ts, ib_t, ib_m, tot_t, tot_m, traces, dib_dt, dib_dt_max, v_inp)
    plot_cold_wet(traces, enc)
    print("\n==== thermal summary ====")
    for k, v in verdict.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")


# ===========================================================================
# 7. Plots
# ===========================================================================
def style(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=SUBTLE, labelsize=9)
    ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
    for s in ax.spines.values():
        s.set_color(BORDER)


def labels(ax, title, xl, yl):
    ax.set_title(title, fontsize=12, fontweight="bold", color=TEXT, fontfamily="monospace", pad=8)
    ax.set_xlabel(xl, fontsize=10, color=TEXT, fontfamily="monospace")
    ax.set_ylabel(yl, fontsize=10, color=TEXT, fontfamily="monospace")


def legend(ax, loc="best", **kw):
    lg = ax.legend(loc=loc, fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT, **kw)
    lg.get_frame().set_alpha(0.9)


def save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("Plot saved:", path)


def _board_panel(fig, ax, b, T, pw, title, top_n, outline=None):
    ext = (0, b["w"] * 1e3, b["h"] * 1e3, 0)
    im = ax.imshow(T - 25, extent=ext, cmap="inferno", origin="upper", interpolation="bilinear")
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    cb.ax.tick_params(colors=SUBTLE, labelsize=8)
    cb.set_label("rise above enclosure wall (K)", color=TEXT, fontsize=9, fontfamily="monospace")
    for r in sorted(pw, key=pw.get, reverse=True)[:top_n]:
        x0, y0, x1, y1 = b["fps"][r]["box"]
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=BLUE, lw=0.8))
        ax.text((x0 + x1) / 2, y0 - 0.8, f"{r} {pw[r]*1e3:.0f} mW", color=TEXT, fontsize=7, ha="center", va="bottom",
                fontfamily="monospace", bbox=dict(fc=PANEL, ec="none", alpha=0.7, pad=0.6))
    if outline:
        for (x0, y0, x1, y1), col in outline:
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=col, lw=1.0, ls="--"))
    style(ax)
    ax.grid(False)
    labels(ax, title, "x (mm)", "y (mm)")


def plot_boards(amp, psu, Ta, Tp, pwa, pwp):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 13), gridspec_kw={"height_ratios": [1, 0.95]})
    fig.patch.set_facecolor(BG)
    walls = [((x0, y0, x1, y1), GREEN) for (x0, y0, x1, y1) in MP.wall_rects().values()]
    isl = read_island()
    _board_panel(fig, ax1, amp, Ta, pwa, f"Amplifier (PSU-fed, {sum(pwa.values())*1e3:.0f} mW): max rise "
                 f"{Ta.max()-25:.2f} K above the shield", 9, walls + [((isl[0], isl[1], isl[2], isl[3]), PURPLE)])
    ax1.text(isl[0], isl[3] + 3.5, "guard island", color=PURPLE, fontsize=8, fontfamily="monospace")
    ax1.text(2, 98.5, "green dashed: GND strips bolted to the shield walls", color=GREEN, fontsize=8, fontfamily="monospace")
    edlc = [(psu["fps"][f"C{k}"]["box"], GREEN) for k in range(8, 16)]
    _board_panel(fig, ax2, psu, Tp, pwp, f"PSU ({sum(pwp.values()):.2f} W): max rise {Tp.max()-25:.1f} K above the PSU box",
                 9, edlc)
    x0, y0 = psu["fps"]["C12"]["box"][:2]
    ax2.text(x0, 89.3, "green dashed: EDLC cells C8-C15", color=GREEN, fontsize=8, fontfamily="monospace")
    fig.suptitle("ELARA -- steady-state board temperature rise (2-D FD, copper from the KiCad boards)",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "thermal_boards.svg")


COLMAP = {"light grey": GREY, "white": TEXT, "black": ORANGE}


def plot_24h(tr):
    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor(BG)
    for ax in axs.flat:
        style(ax)
    ax1, ax2, ax3, ax4 = axs.flat
    base = tr["summer, light grey RAL 7035 (as supplied), door W"]
    ax1.plot(base["h"], base["ta"], color=BLUE, lw=1.6, label="ambient (37 C design day)")
    for k, col in (("light grey RAL 7035 (as supplied)", GREY), ("white paint", TEXT), ("black", ORANGE)):
        d = tr[f"summer, {k}, door W"]
        ax1.plot(d["h"], d["u201"], color=col, lw=1.8, label=f"LMP7721 board, {k}")
        ax1.plot(d["h"], d["air"], color=col, lw=1.0, ls=":", label=f"box air, {k}")
    d = tr["summer, light grey + sun shade (beam blocked), door S"]
    ax1.plot(d["h"], d["u201"], color=GREEN, lw=1.5, ls="--", label="LMP7721 board, grey + sun shade")
    axg = ax1.twinx()
    axg.fill_between(base["h"], base["ghi"], color=YELLOW, alpha=0.08)
    axg.set_ylim(0, 3000)
    axg.set_yticks([0, 500, 1000])
    axg.tick_params(colors=YELLOW, labelsize=8)
    axg.set_ylabel("GHI (W/m2)", color=YELLOW, fontsize=9, fontfamily="monospace")
    ax1.set_xlim(0, 24)
    ax1.set_xticks(range(0, 25, 3))
    labels(ax1, "Summer clear day, door facing west (worst)", "local time CEST (h)", "temperature (C)")
    legend(ax1, loc="upper left", ncol=2)
    ax1.set_ylim(15, 75)

    for k, col in (("light grey RAL 7035 (as supplied)", GREY), ("white paint", TEXT), ("black", ORANGE)):
        d = tr[f"summer, {k}, door W"]
        ax2.plot(d["h"], d["psu"], color=col, lw=1.8, label=f"PSU hottest part (board), {k}")
        ax2.plot(d["h"], d["edlc"], color=col, lw=1.0, ls="--", label=f"EDLC cells, {k}")
    d = tr["record summer 40 C, light grey, door W"]
    ax2.plot(d["h"], d["edlc"], color=RED, lw=1.2, ls="-.", label="EDLC cells, record 40 C, light grey")
    ax2.axhline(65, color=RED, lw=1, ls=":", label="EDLC rating 65 C (2.7 V)")
    ax2.set_xlim(0, 24)
    ax2.set_xticks(range(0, 25, 3))
    labels(ax2, "PSU box contents, same day", "local time CEST (h)", "temperature (C)")
    legend(ax2, loc="upper left")
    ax2.set_ylim(15, 95)

    for k, col in (("light grey RAL 7035 (as supplied)", GREY), ("white paint", TEXT), ("black", ORANGE)):
        d = tr[f"summer, {k}, door W"]
        ax3.plot(d["h"], d["dudt"], color=col, lw=1.5, label=k)
    d = tr["summer, light grey, door S, clouds + gust"]
    ax3.plot(d["h"], d["dudt"], color=PURPLE, lw=1.2, label="grey, door S, clouds 13:00/14:00 + 25 m/s gust 15:00")
    ax3.set_xlim(0, 24)
    ax3.set_xticks(range(0, 25, 3))
    labels(ax3, "Front-end (LMP7721) temperature rate", "local time (h)", "dT/dt (K/h)")
    legend(ax3, loc="lower left")

    names = [("summer, light grey RAL 7035 (as supplied), door W", "summer grey W"), ("summer, white paint, door W", "summer white W"),
             ("summer, black, door W", "summer black W"), ("summer, light grey + sun shade (beam blocked), door S", "summer grey+shade"),
             ("record summer 40 C, light grey, door W", "record 40 C grey"),
             ("winter cold spell -18 C, light grey, PSU", "winter -18 C, PSU"),
             ("winter cold spell -18 C, light grey, battery (no PSU)", "winter -18 C, battery")]
    y = np.arange(len(names))
    for i, (k, lab) in enumerate(names):
        d = tr[k]
        ax4.plot([d["u201"].min(), d["u201"].max()], [i, i], color=BLUE, lw=6, alpha=0.8, solid_capstyle="butt")
        ax4.plot([d["ta"].min(), d["ta"].max()], [i + 0.25, i + 0.25], color=GREY, lw=2)
        ax4.text(d["u201"].max() + 1, i, f"{d['u201'].min():.0f}..{d['u201'].max():.0f} C", va="center", color=TEXT,
                 fontsize=8, fontfamily="monospace")
    ax4.set_yticks(y)
    ax4.set_yticklabels([n[1] for n in names], fontsize=8, color=TEXT, fontfamily="monospace")
    ax4.invert_yaxis()
    ax4.plot([], [], color=BLUE, lw=6, label="LMP7721 board, daily range")
    ax4.plot([], [], color=GREY, lw=2, label="ambient, daily range")
    ax4.axvline(-10, color=RED, lw=1, ls=":", label="CS8406-CZZ min -10 C")
    ax4.axvline(70, color=RED, lw=1, ls="--", label="CS8406-CZZ max 70 C")
    ax4.set_xlim(-30, 95)
    labels(ax4, "Daily range of the front end, all design days", "temperature (C)", "")
    legend(ax4, loc="lower right")
    fig.suptitle("ELARA outdoor box (Fibox ARCA 403015) -- 24 h transient, east Slovenia 46.5 N 16.0 E",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "thermal_enclosure_24h.svg")


def plot_frontend(freqs, Hq, Hv, ts, ib_t, ib_m, tot_t, tot_m, tr, dib, dibm, v_inp):
    fig, axs = plt.subplots(1, 3, figsize=(18, 6.5))
    fig.patch.set_facecolor(BG)
    for ax in axs:
        style(ax)
    ax1, ax2, ax3 = axs
    ax1.semilogy(ts, ib_t * 1e15, color=GREEN, lw=1.8, label="Ib typ (3 fA at 25 C, x2 / 10 K)")
    ax1.semilogy(ts, ib_m * 1e15, color=RED, lw=1.8, label="Ib max (20 fA at 25 C, x2 / 10 K)")
    ax1b = ax1.twinx()
    ax1b.plot(ts, tot_t * 1e9, color=GREEN, lw=1.2, ls="--", label="SR1 noise at antenna, typ Ib")
    ax1b.plot(ts, tot_m * 1e9, color=RED, lw=1.2, ls="--", label="SR1 noise at antenna, max Ib")
    ax1b.set_ylim(70, 110)
    ax1b.tick_params(colors=SUBTLE, labelsize=9)
    ax1b.set_ylabel("total noise at antenna, SR1, J202 100 G (nV/rtHz)", color=TEXT, fontsize=9, fontfamily="monospace")
    hot = tr["summer, light grey RAL 7035 (as supplied), door W"]["u201"].max()
    ax1.axvspan(hot - 0.5, hot + 0.5, color=YELLOW, alpha=0.3)
    ax1.text(hot - 1, 0.5, f"summer max {hot:.0f} C", color=YELLOW, fontsize=8, rotation=90, ha="right", va="bottom",
             fontfamily="monospace")
    labels(ax1, "LMP7721 input bias vs temperature", "front-end temperature (C)", "Ib (fA)")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax1b.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT)

    ax2.loglog(freqs, Hq * 1e3, color=YELLOW, lw=1.8, label="sun: K per W/m2 (x 1000)")
    ax2.loglog(freqs, Hv, color=BLUE, lw=1.8, label="wind: K per m/s")
    ax2.axvspan(0.1, 3, color=PURPLE, alpha=0.06)
    labels(ax2, "Transfer to the LMP7721 temperature", "modulation frequency (Hz)", "|dT_U201| per unit input")
    legend(ax2, loc="lower left")
    ax2.set_xlim(1e-5, 3)

    vq = v_inp(freqs, dibm * Hq * 800.0)
    vq_t = v_inp(freqs, dib * Hq * 800.0)
    vos = TCVOS * Hq * 800.0
    vg = TCVOS * Hv * 10.0
    ax3.loglog(freqs, vq, color=RED, lw=1.8, label="Ib(T), max part: 800 W/m2 cloud modulation")
    ax3.loglog(freqs, vq_t, color=GREEN, lw=1.5, label="Ib(T), typ part")
    ax3.loglog(freqs, vos, color=YELLOW, lw=1.5, label="TCVos 4 uV/K: cloud")
    ax3.loglog(freqs, vg, color=BLUE, lw=1.5, label="TCVos 4 uV/K: 10 m/s gusts")
    ax3.axhline(NOISE_INP_SR1, color=PURPLE, lw=1.5, ls=":", label="receiver noise at IN_P, 1 Hz bin (26.7 nV)")
    ax3.axhline(NOISE_INP_SR1 * np.sqrt(0.01), color=PURPLE, lw=1.0, ls="--", label="same, 0.01 Hz bin")
    ax3.axvspan(0.1, 3, color=PURPLE, alpha=0.06)
    ax3.set_xlim(1e-5, 3)
    ax3.set_ylim(1e-22, 1e-1)
    labels(ax3, "Equivalent voltage at IN_P", "modulation frequency (Hz)", "V peak at IN_P")
    legend(ax3, loc="lower left")
    fig.suptitle("ELARA front end -- bias current, and can sun or wind reach the input below 1 Hz?",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "thermal_frontend.svg")


def plot_cold_wet(tr, enc):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.5))
    fig.patch.set_facecolor(BG)
    for ax in (ax1, ax2):
        style(ax)
    d = tr["autumn clear night, fog at dawn, light grey"]
    db = tr["autumn clear night, fog at dawn, light grey, battery"]
    ax1.plot(d["h"], d["ta"], color=BLUE, lw=1.5, label="ambient")
    ax1.plot(d["h"], d["td"], color=PURPLE, lw=1.5, ls="--", label="outdoor dew point (= inside, vented box)")
    ax1.axhline(-10, color=GREEN, lw=1.2, ls="--", label="inside dew point, sealed box + silica gel (assumed)")
    names = ["door", "back", "left", "right", "top", "bottom"]
    for k in (0, 4):
        ax1.plot(d["h"], d["faces"][k], color=(GREY if k == 0 else ORANGE), lw=1.2, label=f"box {names[k]} wall")
    ax1.plot(d["h"], d["air"], color=YELLOW, lw=1.2, ls=":", label="box air")
    ax1.plot(d["h"], d["u201"], color=GREEN, lw=1.8, label="amplifier board (PSU running)")
    ax1.plot(db["h"], db["u201"], color=RED, lw=1.5, label="amplifier board (battery, no PSU)")
    ax1.set_xlim(0, 24)
    ax1.set_xticks(range(0, 25, 3))
    labels(ax1, "Autumn clear night, saturated at dawn (condensation case)", "local time CET (h)", "temperature (C)")
    legend(ax1, loc="upper left")
    ax1.set_ylim(-12, 45)

    for k, col in (("winter cold spell -18 C, light grey, PSU", BLUE), ("winter cold spell -18 C, light grey, battery (no PSU)", RED)):
        dd = tr[k]
        lab = "battery" if "battery" in k else "PSU"
        ax2.plot(dd["h"], dd["u201"], color=col, lw=1.8, label=f"amplifier board, {lab}")
        ax2.plot(dd["h"], dd["air"], color=col, lw=1.0, ls=":", label=f"box air, {lab}")
    dd = tr["winter cold spell -18 C, light grey, PSU"]
    ax2.plot(dd["h"], dd["psu"], color=ORANGE, lw=1.4, label="PSU hottest part")
    ax2.plot(dd["h"], dd["ta"], color=GREY, lw=1.5, label="ambient")
    ax2.axhline(-10, color=RED, lw=1, ls="--", label="CS8406-CZZ min -10 C")
    ax2.axhline(0, color=YELLOW, lw=1, ls="--", label="LM317 / L78L12-AC min 0 C (Tj)")
    ax2.axhline(-25, color=PURPLE, lw=1, ls="--", label="PCM1804 min -25 C (check)")
    ax2.set_xlim(0, 24)
    ax2.set_xticks(range(0, 25, 3))
    ax2.set_ylim(-30, 25)
    labels(ax2, "Winter cold spell (clear, -18 C at dawn)", "local time CET (h)", "temperature (C)")
    legend(ax2, loc="upper left", ncol=2)
    fig.suptitle("ELARA outdoor box -- condensation and cold extremes",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "thermal_cold_condensation.svg")


if __name__ == "__main__":
    main()
