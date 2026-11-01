#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA -- mechanical / vibration checks of the outdoor unit

1. Modal analysis of the amplifier PCB (frame-clamped and screws-only) and
   of the PSU PCB (4 corner standoffs), component masses from the KiCad boards.
2. Air-gap plate capacitor: plate modes, sag, gap change under acceleration
   (bending mismatch of the two plates + washer compliance), microphonic
   sensitivity referred to the antenna EMF, thermal gap drift, clamp preload.
3. Mounting plate (PE-HD) carrying the three units: modes, transmissibility
   from the box to the plate capacitor; box on a wall or a pole: buffeting,
   vortex shedding, lock-in; wind loads (EN 1991-1-4, Slovenian NA, east
   Slovenia) on the box, pole and fixings; shield frame / lid / tray panels.
4. Transport shock (5 g and 15 g, 11 ms half-sine): heavy THT parts and solder
   joints on both boards, SMD board-deflection check (Steinberg).

Everything is a Kirchhoff-plate FE model (plate_fem.py, BFS elements) or a
closed-form / SDOF estimate; every assumption is in the dicts below.

Outputs: results.json and SVG plots next to this script.
"""

import json
import os
import re
import sys

import numpy as np
import scipy.signal as sig
import scipy.sparse as sp
import scipy.sparse.linalg as sla

import os as _os  # noqa: E402
_os.environ.setdefault("SOURCE_DATE_EPOCH", "0")   # fixed SVG date: no churn on re-runs
import matplotlib  # noqa: E402
matplotlib.rc_file(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "matplotlibrc"))
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "mechanical"))

import params as P                      # noqa: E402  mechanical single source of truth
from plate_fem import Plate, axis, flex_rigidity, _selftest   # noqa: E402

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

G = 9.80665
EPS0 = 8.8541878128e-12
RHO_AIR = 1.25                      # EN 1991-1-4 recommended value
NU_AIR = 1.5e-5
SCHUMANN = [7.83, 14.3, 20.8, 27.3, 33.8, 39.0, 45.0]
SR_LABELS = ["SR1", "SR2", "SR3", "SR4", "SR5", "SR6", "SR7"]
MM = 1e-3

# ---------------------------------------------------------------------------
# Materials (datasheet-typical; ranges in the README)
# ---------------------------------------------------------------------------
MAT = {
    "FR4_4L": dict(E=22e9, nu=0.14, rho=1850.0),   # 4-layer, copper planes stiffen (laminate 18-24 GPa)
    "FR4_2L": dict(E=20e9, nu=0.14, rho=1850.0),
    "PEHD": dict(E=0.9e9, nu=0.42, rho=950.0, E_m20=1.6e9, E_p60=0.45e9, zeta=0.03),
    "Al": dict(E=70e9, nu=0.33, rho=2700.0, zeta=0.02),
    "POM": dict(E=2.8e9, nu=0.35, rho=1410.0),
    "PTFE": dict(E=0.5e9, nu=0.46, rho=2170.0),
    "PA66": dict(E=1.8e9, rho=1140.0, alpha=85e-6),   # conditioned (50 % RH); dry 3 GPa
    "PEEK": dict(E=3.6e9, rho=1300.0, alpha=47e-6),   # plate-cap clamp screws (2026-10-31)
    "Al2O3": dict(E=300e9, rho=3900.0, alpha=7e-6),   # 96 % alumina spacer washers
    "PC": dict(E=2.3e9, rho=1200.0),
    "steel": dict(E=210e9, rho=7850.0, fy=235e6),
    "Cu": dict(E=117e9, rho=8960.0),
}
CU_AREAL_4L = (2 * 35e-6 + 2 * 17.5e-6) * 8960 * 0.6     # 1 oz outer + 0.5 oz inner, 60 % fill
CU_AREAL_2L = (2 * 35e-6) * 8960 * 0.6

# ---------------------------------------------------------------------------
# Electrical context (PLAN.md, simulations/system)
# ---------------------------------------------------------------------------
ELEC = dict(
    C_ant=140e-12,
    C_plate=P.plate_capacitance_pf()[0] * 1e-12,     # 48.9 pF per air-gap capacitor
    V_dc_nom=0.03,           # lower plates on PLATE_RET (2.5 V like the node): only the air-earth current
                             # x J202 10 G is left, 3 pA -> 30 mV (was 2.5 V with the plates on GND)
    V_lead=2.5,              # the node2 lead and Cg still have the 2.5 V bias to the GND metal around them
    V_dc_worst=1.0,          # air-earth current at the DC-point limit: 100 pA x J202 10 G (was 4 V on GND)
    floor=45.8e-9,           # V/rtHz at the antenna (EMF-referred), SPICE SR1, no J202 resistor
    floor_100G=74.8e-9,      # with J202 = 100 G (simulations/system)
    sr1_quiet=0.3e-6 * 6.5,  # quiet SR1 peak, EMF-referred (0.3 uV/m/rtHz x h_eff 6.5 m)
    E_fair=130.0,            # fair-weather field, V/m (typical 100-150)
    h_eff=6.5,
)
ELEC["divider"] = ELEC["C_ant"] / (ELEC["C_ant"] + 2 * ELEC["C_plate"])

# Site: east Slovenia (Pannonian lowland, ~46.5 N 16 E), user input 2026-10-31
SITE = dict(
    v_b0=20.0,               # SIST EN 1991-1-4 NA: wind zone 1 (most of Slovenia < 800 m, incl. NE) -- verify
    v_b0_alt=25.0,           # sensitivity case
    terrain="II", z0=0.05, z_min=2.0,
    z_box=2.0,               # box centre above ground (wall or pole)
    v_storm_gust=30.0,       # summer thunderstorm peak gust (downburst), applied as a peak velocity
    T_min=-20.0, T_max=60.0, T_assy=23.0,
    ice_t=0.010,             # 10 mm glaze on exposed faces (minor case)
    snow_sk=1.5e3,           # N/m^2, lowland NE Slovenia order of magnitude (EN 1991-1-3 NA) -- minor
)


# ===========================================================================
# helpers
# ===========================================================================
def style(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=SUBTLE, labelsize=9)
    ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
    for s in ax.spines.values():
        s.set_color(BORDER)


def labels(ax, title, xl, yl, fs=11):
    ax.set_title(title, fontsize=fs, fontweight="bold", color=TEXT, fontfamily="monospace", pad=8)
    ax.set_xlabel(xl, fontsize=9, color=TEXT, fontfamily="monospace")
    ax.set_ylabel(yl, fontsize=9, color=TEXT, fontfamily="monospace")


def legend(ax, loc="best", **kw):
    lg = ax.legend(loc=loc, fontsize=7.5, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT, **kw)
    lg.get_frame().set_alpha(0.9)


def sr_band(ax):
    ax.axvspan(1, 50, color=GREEN, alpha=0.05)
    for fx in SCHUMANN:
        ax.axvline(fx, color=SUBTLE, alpha=0.25, linestyle="--", linewidth=0.7)


def save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("Plot saved:", path)


def r3(x, n=3):
    """Round for JSON (significant digits)."""
    if isinstance(x, dict):
        return {k: r3(v, n) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [r3(v, n) for v in x]
    if isinstance(x, (float, np.floating)):
        if x == 0 or not np.isfinite(x):
            return float(x)
        return float(f"{x:.{n}g}")
    if isinstance(x, np.integer):
        return int(x)
    return x


def half_sine(a_pk, T, t):
    return np.where((t >= 0) & (t <= T), a_pk * np.sin(np.pi * t / T), 0.0)


def srs_factor(fn, T, zeta=0.05):
    """Max |absolute acceleration| / pulse peak of an SDOF on a half-sine of duration T."""
    wn = 2 * np.pi * fn
    dt = min(T / 400, 1 / fn / 60)
    t = np.arange(0, T + 6 / fn + 0.02, dt)
    a = half_sine(1.0, T, t)
    sys_ = sig.lti([2 * zeta * wn, wn**2], [1, 2 * zeta * wn, wn**2])
    _, y, _ = sig.lsim(sys_, a, t)
    return float(np.max(np.abs(y)))


# ===========================================================================
# 1. PCB footprints and masses
# ===========================================================================
def parse_board(path, origin=(50.0, 50.0)):
    s = open(path).read()
    starts = [m.start() for m in re.finditer(r'\n\t\(footprint "', s)]
    out = []
    for k, i in enumerate(starts):
        blk = s[i:starts[k + 1] if k + 1 < len(starts) else len(s)]
        name = re.search(r'\(footprint "([^"]+)"', blk).group(1).split(":")[-1]
        at = re.search(r'\n\t\t\(at ([\d\.\-]+) ([\d\.\-]+)(?: ([\d\.\-]+))?\)', blk)
        X, Y = float(at.group(1)), float(at.group(2))
        rot = np.radians(float(at.group(3) or 0.0))
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        dnp = "(dnp" in blk or "exclude_from_bom" in blk
        pads = []
        for m in re.finditer(r'\(pad "[^"]*" (thru_hole|smd|np_thru_hole) \w+\s*\n?\s*\(at ([\d\.\-]+) ([\d\.\-]+)', blk):
            px, py = float(m.group(2)), float(m.group(3))
            x = X + px * np.cos(rot) + py * np.sin(rot)
            y = Y - px * np.sin(rot) + py * np.cos(rot)
            pads.append((m.group(1), x - origin[0], y - origin[1]))
        out.append(dict(ref=ref, fp=name, x=X - origin[0], y=Y - origin[1], pads=pads, dnp=dnp))
    return out


# masses in grams, (pattern on footprint or ref) -> mass; first match wins.
# Sources: datasheet dimensions x typical density (film caps ~1.3 g/cm^3, Al electrolytics
# ~1.5 g/cm^3, potted modules ~1.6-1.8 g/cm^3); flagged values in the README.
MASS_RULES = [
    ("C_Rect_L41.5mm", 43.0),      # WIMA MKS4 100 uF 63 V, 41.5 x 20 x 39.5 mm
    ("C_Rect_L26.5mm", 5.5),       # WIMA MKS4 10 uF 63 V, 26.5 x 8.5 x ~18.5 mm
    ("IRM-05", 40.0),              # Mean Well IRM-05, 45.7 x 25.4 x 21.5 mm potted (verify datasheet weight)
    ("CP_Radial_D16.0", 7.6),      # Panasonic FR 16 x 25
    ("PS1", 40.0),
    ("CP_Radial_D6.3", 0.45),
    ("Relay_SPDT_StandexMeder_SIL", 1.8),
    ("TerminalBlock", 4.0),
    ("Fuseholder", 3.0),
    ("RV_Disc", 1.5),
    ("CommonModeChoke", 3.0),
    ("RJ45", 6.0),
    ("TO-220", 2.0),
    ("Transformer", 1.5),
    ("SW_DIP", 1.5),
    ("SW_SPST", 0.5),
    ("Micro-Fit", 1.2),
    ("Turret", 0.4),
    ("PinHeader", 0.3),
    ("TestPoint", 0.15),
    ("SSOP-28", 0.25), ("TSSOP-28", 0.12), ("SOIC-16", 0.15), ("SOIC-8", 0.08), ("MSOP", 0.03),
    ("SOT-89", 0.05), ("SOT-23", 0.01), ("D_SMA", 0.07), ("SOD-123", 0.01), ("PQFN", 0.02),
    ("2512", 0.045), ("1206", 0.02), ("0805", 0.008), ("0603", 0.004), ("0402", 0.001),
    ("MountingHole", 0.0), ("Hole", 0.0), ("LED", 0.005),
]


def part_mass(p):
    if p["fp"].startswith("CP_Radial_D12.5"):
        return 3.6 if p["ref"] != "C16" else 4.2     # Eaton HV1030 EDLC / Panasonic FR 12.5 x 20
    for pat, m in MASS_RULES:
        if pat in p["fp"] or pat == p["ref"]:
            return m
    return 0.05


# ===========================================================================
# 2. PCB modal analysis
# ===========================================================================
def amp_pcb_model(parts, support, h=2.5 * MM):
    W, H = P.PCB_W * MM, P.PCB_H * MM
    req_x = sorted({v * MM for r in P.wall_rects().values() for v in (r[0], r[2])} | {x * MM for x, _ in P.AMP_HOLES})
    req_y = sorted({v * MM for r in P.wall_rects().values() for v in (r[1], r[3])} | {y * MM for _, y in P.AMP_HOLES})
    xs, ys = axis(W, h, req_x), axis(H, h, req_y)
    m = MAT["FR4_4L"]
    D = flex_rigidity(m["E"], P.PCB_T * MM, m["nu"])
    rho_h = m["rho"] * P.PCB_T * MM + CU_AREAL_4L
    pl = Plate(xs, ys, D, rho_h, m["nu"])
    for p in parts:
        mp = part_mass(p) * 1e-3
        pads = p["pads"] or [("smd", p["x"], p["y"])]
        for _, x, y in pads:
            pl.add_mass(x * MM, y * MM, mp / len(pads))
    if support == "frame":
        # PCB clamped between the 7 mm wall bars and the tray rim (same footprint)
        notch = []
        for c in P.CUTOUTS:
            e, lo, hi, _, _ = P.cutout_rect(c)
            notch.append((e, lo, hi))
        for (x0, y0, x1, y1) in P.wall_rects().values():
            nodes = pl.nodes_in(lambda X, Y: (X >= x0 * MM - 1e-9) & (X <= x1 * MM + 1e-9)
                                & (Y >= y0 * MM - 1e-9) & (Y <= y1 * MM + 1e-9))
            Xn, Yn = pl.node_xy()
            for n in nodes:
                xm, ym = Xn[n] / MM, Yn[n] / MM
                in_notch = any((e == "top" and ym < P.WALL_T + 1e-6 and lo <= xm <= hi)
                               or (e == "right" and xm > P.PCB_W - P.WALL_T - 1e-6 and lo <= ym <= hi)
                               for e, lo, hi in notch)
                if in_notch:
                    pl.pin([n])          # tray rim only: pinned, no clamp
                else:
                    pl.clamp([n])
    else:
        for x, y in P.AMP_HOLES:
            pl.clamp([pl.nearest(x * MM, y * MM)])
    return pl


def psu_pcb_model(parts, support, h=2.5 * MM):
    W, H = P.PSU_PCB_W * MM, P.PSU_PCB_H * MM
    i = P.PSU_PCB_HOLE_INSET * MM
    xs, ys = axis(W, h, [i, W - i]), axis(H, h, [i, H - i])
    m = MAT["FR4_2L"]
    D = flex_rigidity(m["E"], P.PSU_PCB_T * MM, m["nu"])
    pl = Plate(xs, ys, D, m["rho"] * P.PSU_PCB_T * MM + CU_AREAL_2L, m["nu"])
    for p in parts:
        mp = part_mass(p) * 1e-3
        pads = [q for q in p["pads"] if q[0] != "np_thru_hole"] or [("smd", p["x"], p["y"])]
        for _, x, y in pads:
            pl.add_mass(x * MM, y * MM, mp / len(pads))
    holes = [(i, i), (W - i, i), (i, H - i), (W - i, H - i)]
    for x, y in holes:
        n = pl.nearest(x, y)
        if support == "pinned":
            pl.pin([n])
        else:
            # standoff face (5.5 mm AF hex) and screw head clamp the board
            pl.clamp(pl.nodes_in(lambda X, Y: np.hypot(X - x, Y - y) <= 2.8 * MM))
    return pl


def modal_shock(pl, phi, freq, a_pk, T, zeta=0.03, nodes_sets=None):
    """Base half-sine normal to the board: max absolute acceleration (per node set)
    and max relative deflection, by modal superposition."""
    r = pl.rigid_vector()
    gam = phi.T @ (pl.M @ r)
    tmax = T + 0.05
    dt = min(T / 400, 1 / freq.max() / 40)
    t = np.arange(0, tmax, dt)
    a = half_sine(a_pk, T, t)
    qdd = np.zeros((len(freq), len(t)))
    q = np.zeros((len(freq), len(t)))
    for k, f in enumerate(freq):
        w = 2 * np.pi * f
        _, y, x = sig.lsim(sig.lti([-gam[k]], [1, 2 * zeta * w, w**2]), a, t)
        q[k] = y
        qdd[k] = -gam[k] * a - 2 * zeta * w * np.gradient(y, dt) - w**2 * y
    out = {}
    wdofs = np.arange(0, pl.ndof, 4)
    defl = phi[wdofs].T                          # (nmodes, nn)
    rel = defl.T @ q                             # (nn, nt)
    out["max_rel_defl_m"] = float(np.max(np.abs(rel)))
    for name, nodes in (nodes_sets or {}).items():
        acc = a[None, :] + defl[:, nodes].T @ qdd
        out[name] = float(np.max(np.abs(acc.mean(axis=0))) / G)
    return out


def plot_modes(pl, freq, phi, title, fname, n=4, outline=None, supports=None, masses=None):
    fig, axs = plt.subplots(1, n, figsize=(4.2 * n, 3.0 * pl.ys[-1] / pl.xs[-1] + 1.4))
    fig.patch.set_facecolor(BG)
    X, Y = np.meshgrid(pl.xs / MM, pl.ys / MM)
    for k, ax in enumerate(np.atleast_1d(axs)):
        w = pl.w_grid(phi[:, k])
        w = w / np.max(np.abs(w))
        w = np.where(np.abs(w) < 0.02, 0.0, w)          # drop numerical noise in the clamped strips
        ax.contourf(X, Y, w, levels=np.linspace(-1, 1, 21), cmap="RdBu_r")
        ax.contour(X, Y, w, levels=[0], colors=[TEXT], linewidths=0.6)
        if supports is not None:
            step = max(1, len(supports[0]) // 500)          # keep the SVG small
            ax.plot(supports[0][::step], supports[1][::step], "s", ms=1.2 * np.sqrt(step), color=YELLOW, alpha=0.6)
        if masses is not None:
            ax.scatter(masses[0], masses[1], s=masses[2], facecolors="none", edgecolors=GREEN, linewidths=0.8)
        ax.set_aspect("equal")
        ax.invert_yaxis()
        style(ax)
        ax.set_title(f"mode {k + 1}: {freq[k]:.0f} Hz", fontsize=10, color=TEXT, fontfamily="monospace")
        ax.set_xlabel("x (mm)", fontsize=8, color=TEXT, fontfamily="monospace")
    fig.suptitle(title, fontsize=12, fontweight="bold", color=TEXT, fontfamily="monospace")
    fig.tight_layout()
    save(fig, fname)


def run_pcbs():
    amp_parts = parse_board(os.path.join(ROOT, "PCB/antenna_amplifier/antenna_amplifier.kicad_pcb"))
    psu_parts = parse_board(os.path.join(ROOT, "PCB/acdc_converter/acdc_converter.kicad_pcb"))
    res = {}
    for nm, parts in (("amp", amp_parts), ("psu", psu_parts)):
        ms = sorted(((part_mass(p), p["ref"]) for p in parts), reverse=True)
        res[nm + "_parts_mass_g"] = sum(m for m, _ in ms)
        res[nm + "_heavy_parts_g"] = {r: m for m, r in ms[:8]}
    out_models = {}
    # amplifier
    for sup in ("frame", "screws"):
        pl = amp_pcb_model(amp_parts, sup)
        f, phi = pl.modes(8)
        res[f"amp_pcb_{sup}_modes_Hz"] = list(f[:6])
        out_models[("amp", sup)] = (pl, f, phi)
        pm_board = (MAT["FR4_4L"]["rho"] * P.PCB_T * MM + CU_AREAL_4L) * P.PCB_W * P.PCB_H * MM * MM
        res["amp_pcb_bare_mass_g"] = pm_board * 1e3
    for sup in ("pinned", "clamped"):
        pl = psu_pcb_model(psu_parts, sup)
        f, phi = pl.modes(8)
        res[f"psu_pcb_{sup}_modes_Hz"] = list(f[:6])
        out_models[("psu", sup)] = (pl, f, phi)
    res["psu_pcb_bare_mass_g"] = (MAT["FR4_2L"]["rho"] * P.PSU_PCB_T * MM + CU_AREAL_2L) * P.PSU_PCB_W * P.PSU_PCB_H * 1e-3

    # plots
    for (nm, sup), (pl, f, phi) in out_models.items():
        parts = amp_parts if nm == "amp" else psu_parts
        Xn, Yn = pl.node_xy()
        fixed_w = sorted(d // 4 for d in pl.fixed if d % 4 == 0)
        heavy = [p for p in parts if part_mass(p) >= 1.0]
        mx = [np.mean([q[1] for q in p["pads"]]) if p["pads"] else p["x"] for p in heavy]
        my = [np.mean([q[2] for q in p["pads"]]) if p["pads"] else p["y"] for p in heavy]
        msz = [6 * part_mass(p) for p in heavy]
        title = {("amp", "frame"): "Amplifier PCB, clamped by the shield walls and tray rim",
                 ("amp", "screws"): "Amplifier PCB, clamped at the 24 screws only (bound)",
                 ("psu", "pinned"): "PSU PCB on 4 corner standoffs, pinned (bound)",
                 ("psu", "clamped"): "PSU PCB on 4 corner standoffs, clamped"}[(nm, sup)]
        plot_modes(pl, f, phi, title + "  (green: parts >= 1 g)", f"modes_{nm}_pcb_{sup}.svg", n=4,
                   supports=(Xn[fixed_w] / MM, Yn[fixed_w] / MM), masses=(mx, my, msz))
    return res, out_models, amp_parts, psu_parts


# ===========================================================================
# 3. Air-gap plate capacitor
# ===========================================================================
PCAP = dict(
    t=P.PLATE_T * MM, S=P.PLATE_SIZE * MM, gap=P.PLATE_GAP * MM, hole=P.PLATE_HOLE_INSET * MM,
    cu=P.PLATE_CU * MM, relief=P.PLATE_CU_KEEPOUT_R * MM,
    washer=P.PTFE_WASHER, clamp_r=3.0 * MM,
    m_tongue_node=0.35e-3, m_tongue_gnd=0.15e-3,      # resistor half + lead + solder per tongue
    mismatch=(0.05, 0.10),                            # plate thickness mismatch (IPC-4101 1.6 mm +-10 %)
    k_disc=MAT["PTFE"]["E"] * np.pi / 4 * (6e-3) ** 2 / (P.PLATE_GAP * MM),
    standoff=P.PLATE_STANDOFF, screw_L=20.0 * MM, screw_As=5.03e-6,
    preload_turn=1 / 8, pitch=0.5 * MM,
    # clamp as designed since 2026-10-31: PEEK M3 screws, 0.5 mm alumina spacers (they set
    # the gap), a stainless M3 wave spring under each head preloaded to F_spring
    screw_mat="PEEK", washer_mat="Al2O3", k_spring=20e3, F_spring=30.0,
)


def ptfe_strain(T, Tref=23.0):
    """Linear thermal strain of PTFE relative to Tref.  Baseline 100 ppm/K below the
    19 C transition and 120 ppm/K above 30 C, plus 0.15 % across the 19/30 C phase
    transitions (smoothed); mean 23..60 C ~ 125 ppm/K (DuPont/Chemours handbook order)."""
    def raw(t):
        base = 100e-6 * t + 20e-6 * np.logaddexp(0, (t - 30.0) / 3.0) * 3.0
        step = 0.0012 / (1 + np.exp(-(t - 19.0) / 1.5)) + 0.0003 / (1 + np.exp(-(t - 30.0) / 2.0))
        return base + step
    return raw(np.asarray(T, float)) - raw(Tref)


def plate_cap_mesh(h=1.0 * MM):
    S, i = PCAP["S"], PCAP["hole"]
    c0 = (S - PCAP["cu"]) / 2
    req = [i, S - i, S / 2, c0, S - c0, i - PCAP["clamp_r"], i + PCAP["clamp_r"],
           S - i - PCAP["clamp_r"], S - i + PCAP["clamp_r"]]
    return axis(S, h, req), axis(S, h, req)


def plate_cap_plate(xs, ys, t, node_plate, support="clamped", E=None):
    m = MAT["FR4_2L"]
    E = E or m["E"]
    D = flex_rigidity(E, t, m["nu"])
    # FR4 plus the copper square smeared over the plate
    rho_h = m["rho"] * t + (P.PLATE_CU * MM) ** 2 * P.PLATE_CU_T * MM * 8960 / (P.PLATE_SIZE * MM) ** 2
    pl = Plate(xs, ys, D, rho_h, m["nu"])
    S, i = PCAP["S"], PCAP["hole"]
    for (x, y) in ((i, i), (S - i, i), (i, S - i), (S - i, S - i)):
        if support == "clamped":
            pl.clamp(pl.nodes_in(lambda X, Y: np.hypot(X - x, Y - y) <= PCAP["clamp_r"] + 1e-9))
        else:
            pl.pin([pl.nearest(x, y)])
    tg = P.PLATE_TONGUE
    if node_plate:     # turned over left-right: tongues at left y=44, right y=20 (KiCad y from top)
        pl.add_mass(0.0, tg["y_right"] * MM, PCAP["m_tongue_node"])
        pl.add_mass(S, tg["y_left"] * MM, PCAP["m_tongue_node"])
    else:
        pl.add_mass(S, tg["y_right"] * MM, PCAP["m_tongue_gnd"])
    return pl


def copper_weights(pl):
    S, i = PCAP["S"], PCAP["hole"]
    c0 = (S - PCAP["cu"]) / 2
    X, Y = pl.node_xy()
    inside = (X >= c0 - 1e-9) & (X <= S - c0 + 1e-9) & (Y >= c0 - 1e-9) & (Y <= S - c0 + 1e-9)
    for (x, y) in ((i, i), (S - i, i), (i, S - i), (S - i, S - i)):
        inside &= np.hypot(X - x, Y - y) > PCAP["relief"]
    w = pl.area_weights() * inside
    return w / w.sum()


def two_plate(xs, ys, eps, support="clamped", disc=False, n_modes=4):
    """GND plate (lower, nominal t) + node plate (upper, t (1 - eps)) on common corner
    clamps, optionally tied at the centre by the PTFE disc.  Returns the mean copper-gap
    change per 1 m/s^2 normal acceleration and the coupled modes."""
    p1 = plate_cap_plate(xs, ys, PCAP["t"], False, support)
    p2 = plate_cap_plate(xs, ys, PCAP["t"] * (1 - eps), True, support)
    K1, M1 = p1.assemble()
    K2, M2 = p2.assemble()
    n = p1.ndof
    K = sp.block_diag([K1, K2]).tolil()
    M = sp.block_diag([M1, M2]).tocsr()
    if disc:
        c = p1.nearest(PCAP["S"] / 2, PCAP["S"] / 2)
        a, b = 4 * c, n + 4 * c
        k = PCAP["k_disc"]
        K[a, a] += k
        K[b, b] += k
        K[a, b] -= k
        K[b, a] -= k
    K = K.tocsr()
    fixed = set(p1.fixed) | {n + d for d in p2.fixed}
    free = np.array(sorted(set(range(2 * n)) - fixed))
    r = np.zeros(2 * n)
    r[0:n:4] = 1
    r[n::4] = 1
    F = -(M @ r)
    u = np.zeros(2 * n)
    Kf = K[free][:, free].tocsc()
    u[free] = sla.spsolve(Kf, F[free])
    wc = copper_weights(p1)
    w1, w2 = u[0:n:4], u[n::4]
    dg = float(np.sum(wc * (w2 - w1)))
    lam, vec = sla.eigsh(Kf, k=n_modes, M=M[free][:, free], sigma=0, which="LM", v0=np.ones(len(free)))
    f = np.sqrt(np.sort(lam)) / (2 * np.pi)
    return dict(dgap_per_ms2=dg, w_lower_mean=float(np.sum(wc * w1)), w_upper_mean=float(np.sum(wc * w2)),
                w_lower_max=float(np.max(np.abs(w1))), modes=list(f)), (p1, u[:n], u[n:])


def washer_gap_per_ms2():
    """Rigid stack: base -- standoffs -- lower plate -- washers -- upper plate, and the
    nylon screws from the base to the upper plate (head).  Gap change per m/s^2."""
    so = PCAP["standoff"]
    A_so = np.pi / 4 * ((so["d"] * MM) ** 2 - (so["bore"] * MM) ** 2)
    k_so = 4 * MAT["PTFE"]["E"] * A_so / (so["h"] * MM)
    A_w = np.pi / 4 * ((PCAP["washer"]["od"] * MM) ** 2 - (PCAP["washer"]["id"] * MM) ** 2)
    k_w = 4 * MAT["PTFE"]["E"] * A_w / (PCAP["washer"]["t"] * MM)
    k_s = 4 * MAT["PA66"]["E"] * PCAP["screw_As"] / PCAP["screw_L"]
    m = MAT["FR4_2L"]["rho"] * PCAP["t"] * PCAP["S"] ** 2 + 0.6e-3        # plate + screws heads share
    K = np.array([[k_so + k_w, -k_w], [-k_w, k_w + k_s]])
    x = np.linalg.solve(K, -np.array([m, m]))
    Mm = np.diag([m, m])
    lam = np.linalg.eigvals(np.linalg.solve(Mm, K))
    return dict(dgap_per_ms2=float(abs(x[1] - x[0])), k_standoffs=k_so, k_washers=k_w, k_screws=k_s,
                f_stack_Hz=sorted(float(np.sqrt(l) / 2 / np.pi) for l in lam))


def preload_vs_T(T):
    """Clamp force per corner screw vs temperature (assembly at 23 C, finger tight + 1/8 turn)."""
    so = PCAP["standoff"]
    A_so = np.pi / 4 * ((so["d"] * MM) ** 2 - (so["bore"] * MM) ** 2)
    k_so = MAT["PTFE"]["E"] * A_so / (so["h"] * MM)
    A_w = np.pi / 4 * ((PCAP["washer"]["od"] * MM) ** 2 - (PCAP["washer"]["id"] * MM) ** 2)
    wm, sm = MAT[PCAP["washer_mat"]], MAT[PCAP["screw_mat"]]
    k_w = wm["E"] * A_w / (PCAP["washer"]["t"] * MM)
    k_fr4 = 10e9 * np.pi / 4 * ((5.5 * MM) ** 2 - (3.2 * MM) ** 2) / (2 * PCAP["t"])
    k_c = 1 / (1 / k_so + 1 / k_w + 1 / k_fr4)
    k_s = sm["E"] * PCAP["screw_As"] / PCAP["screw_L"]
    k_s = 1 / (1 / k_s + 1 / PCAP["k_spring"])          # wave spring in series with the screw
    k_eff = 1 / (1 / k_s + 1 / k_c)
    F0 = PCAP["F_spring"]
    dT = np.asarray(T) - SITE["T_assy"]
    d_parts = so["h"] * MM * ptfe_strain(T) + PCAP["washer"]["t"] * MM * wm["alpha"] * dT \
        + 2 * PCAP["t"] * 60e-6 * dT
    d_screw = PCAP["screw_L"] * sm["alpha"] * dT
    F = F0 + k_eff * (d_parts - d_screw)
    return F, F0, k_eff


def gap_vs_T(T):
    """Copper gap (set by the alumina spacer thickness) and C relative to 23 C."""
    g = PCAP["gap"] * (1 + MAT[PCAP["washer_mat"]]["alpha"] * (np.asarray(T) - SITE["T_assy"]))
    area = (1 + 15e-6 * (np.asarray(T) - SITE["T_assy"])) ** 2       # FR4 in-plane 15 ppm/K
    C = ELEC["C_plate"] * area * PCAP["gap"] / g
    return g, C


def run_platecap(res):
    xs, ys = plate_cap_mesh()
    out = {}
    # single plate modes and sag
    for sup in ("clamped", "pinned"):
        pl = plate_cap_plate(xs, ys, PCAP["t"], True, sup)
        f, phi = pl.modes(6)
        u = pl.static_accel(G)
        wc = copper_weights(pl)
        out[f"plate_{sup}"] = dict(modes_Hz=list(f[:4]), sag_1g_max_um=float(np.max(np.abs(u[0::4]))) / 1e-6,
                                   sag_1g_mean_copper_um=float(abs(np.sum(wc * u[0::4]))) / 1e-6)
        if sup == "clamped":
            plot_data = (pl, f, phi, u)
    # two-plate differential response
    cases = {}
    for eps in (0.0,) + PCAP["mismatch"]:
        for disc in (False, True):
            r, _ = two_plate(xs, ys, eps, "clamped", disc)
            cases[f"eps{eps:.2f}_{'disc' if disc else 'nodisc'}"] = r
    r_pin, _ = two_plate(xs, ys, PCAP["mismatch"][0], "pinned", False)
    cases["eps0.05_nodisc_pinned"] = r_pin
    out["two_plate"] = cases
    wsh = washer_gap_per_ms2()
    out["washer_stack"] = wsh

    # microphonic sensitivity: per cap, EMF-referred: e = V_dc C_plate (dg/g) / C_ant
    nominal = cases[f"eps{PCAP['mismatch'][0]:.2f}_nodisc"]
    dg_nom = abs(nominal["dgap_per_ms2"]) + wsh["dgap_per_ms2"]
    worst = cases[f"eps{PCAP['mismatch'][1]:.2f}_nodisc"]
    dg_worst = abs(worst["dgap_per_ms2"]) + wsh["dgap_per_ms2"]
    f1 = nominal["modes"][0]

    def sens(dg, V, n_caps_coh):
        return V * ELEC["C_plate"] * dg / PCAP["gap"] / ELEC["C_ant"] * n_caps_coh
    S_nom = sens(dg_nom, ELEC["V_dc_nom"], np.sqrt(2))       # two caps, independent mismatch
    S_worst = sens(dg_worst, ELEC["V_dc_worst"], 2.0)        # coherent, 10 % mismatch, V_dc_worst
    out["microphonic"] = dict(
        dgap_nominal_m_per_ms2=dg_nom, dgap_worst_m_per_ms2=dg_worst,
        S_nominal_V_per_ms2=S_nom, S_worst_V_per_ms2=S_worst,
        threshold_nominal_ms2_rtHz=ELEC["floor"] / S_nom, threshold_worst_ms2_rtHz=ELEC["floor"] / S_worst,
        f1_plate_Hz=f1,
        dC_over_C_per_ms2=dg_nom / PCAP["gap"],
        gap_for_floor_pm=ELEC["floor"] * ELEC["C_ant"] / (ELEC["V_dc_nom"] * ELEC["C_plate"] * np.sqrt(2)) * PCAP["gap"] / 1e-12,
        S_if_gnd_plates_at_bias_V_per_ms2=sens(dg_nom, 2e-3, np.sqrt(2)),
    )
    # lateral (in-plane) shift: overlap change per um
    out["lateral_dC_over_C_per_um"] = 1e-6 / PCAP["cu"]
    # in-plane slip under gravity (vertical plates): friction capacity vs weight
    F0 = preload_vs_T(SITE["T_assy"])[1]
    m_plate = MAT["FR4_2L"]["rho"] * PCAP["t"] * PCAP["S"] ** 2
    out["slip_g_level_at_nominal_preload"] = (0.3 + 0.05) * 4 * F0 / (m_plate * G)

    # thermal
    T = np.linspace(SITE["T_min"], SITE["T_max"], 161)
    g, C = gap_vs_T(T)
    F, F0, keff = preload_vs_T(T)
    H = ELEC["C_ant"] / (ELEC["C_ant"] + 2 * C)
    fc = 1 / (2 * np.pi * 33e3 * C)
    dCdT = np.gradient(C, T)
    i0 = np.argmin(np.abs(T - 23))
    out["thermal"] = dict(
        C_pF={"-20C": C[0] / 1e-12, "23C": C[i0] / 1e-12, "60C": C[-1] / 1e-12},
        C_change_pct_m20_to_p60=(C[-1] - C[0]) / C[i0] * 100,
        dCdT_ppm_per_K={"0C": dCdT[np.argmin(np.abs(T))] / C[i0] * 1e6, "40C": dCdT[np.argmin(np.abs(T - 40))] / C[i0] * 1e6},
        gap_um={"-20C": g[0] / 1e-6, "60C": g[-1] / 1e-6},
        divider_change_dB=20 * np.log10(H[-1] / H[0]),
        fc_change_pct=(fc[-1] - fc[0]) / fc[i0] * 100,
        preload_N={"assembly_23C": F0, "-20C": F[0], "60C": F[-1]},
        preload_k_eff_N_per_m=keff,
        EMF_per_K_V=ELEC["V_dc_nom"] * 2 * abs(dCdT[i0]) / ELEC["C_ant"],
        dT_for_floor_mK_rtHz=ELEC["floor"] / (ELEC["V_dc_nom"] * 2 * abs(dCdT[i0]) / ELEC["C_ant"]) * 1e3,
        alumina_washers_dCdT_ppm_per_K=(2 * 15e-6 - 7e-6) * 1e6,
        pom_washers_dCdT_ppm_per_K=(2 * 15e-6 - 110e-6) * 1e6,
    )
    res["plate_capacitor"] = out
    plot_platecap(plot_data, cases, T, C, F, g)
    return out


def plot_platecap(plot_data, cases, T, C, F, g):
    pl, f, phi, u = plot_data
    fig = plt.figure(figsize=(15, 8.2))
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(2, 3)
    X, Y = np.meshgrid(pl.xs / MM, pl.ys / MM)
    for k in range(2):
        ax = fig.add_subplot(gs[0, k])
        w = pl.w_grid(phi[:, k])
        w /= np.max(np.abs(w))
        ax.contourf(X, Y, w, levels=np.linspace(-1, 1, 21), cmap="RdBu_r")
        ax.contour(X, Y, w, levels=[0], colors=[TEXT], linewidths=0.6)
        c0 = (P.PLATE_SIZE - P.PLATE_CU) / 2
        ax.add_patch(plt.Rectangle((c0, c0), P.PLATE_CU, P.PLATE_CU, fill=False, ec=ORANGE, lw=0.8, ls="--"))
        for (x, y) in ((5, 5), (59, 5), (5, 59), (59, 59)):
            ax.add_patch(plt.Circle((x, y), 3.0, fc=YELLOW, ec="none", alpha=0.8))
        ax.set_aspect("equal")
        style(ax)
        labels(ax, f"plate mode {k + 1}: {f[k]:.0f} Hz (corners clamped)", "x (mm)", "y (mm)", fs=10)
    ax = fig.add_subplot(gs[0, 2])
    w = pl.w_grid(u) / 1e-6
    cs = ax.contourf(X, Y, w, levels=20, cmap="viridis")
    cb = fig.colorbar(cs, ax=ax)
    cb.ax.tick_params(colors=SUBTLE, labelsize=8)
    cb.set_label("um", color=TEXT, fontsize=8)
    ax.set_aspect("equal")
    style(ax)
    labels(ax, f"sag under 1 g normal (plate horizontal): max {np.max(np.abs(w)):.2f} um", "x (mm)", "y (mm)", fs=10)

    ax = fig.add_subplot(gs[1, 0])
    names, vals, cols = [], [], []
    for key, r in cases.items():
        names.append(key.replace("_nodisc", "").replace("_disc", " +disc").replace("eps", "dt="))
        vals.append(abs(r["dgap_per_ms2"]) / 1e-12)
        cols.append(BLUE if "disc" not in key or "nodisc" in key else PURPLE)
    ax.barh(range(len(vals)), vals, color=cols)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(names, fontsize=7.5, color=TEXT, fontfamily="monospace")
    ax.set_xscale("log")
    style(ax)
    labels(ax, "mean copper-gap change per 1 m/s^2", "pm per (m/s^2)", "", fs=10)

    ax = fig.add_subplot(gs[1, 1])
    ax.plot(T, (C / C[np.argmin(np.abs(T - 23))] - 1) * 100, color=BLUE, lw=1.6, label="C (alumina spacers, as designed)")
    gpt = (1 + 15e-6 * (T - 23)) ** 2 / (1 + ptfe_strain(T)) - 1
    ax.plot(T, gpt * 100, color=RED, lw=1.2, ls="--", label="C with PTFE washers (before)")
    ax.axvspan(SITE["T_min"], SITE["T_max"], color=GREY, alpha=0.05)
    style(ax)
    legend(ax, loc="lower left")
    labels(ax, "capacitance drift vs temperature", "temperature (C)", "dC/C (%)", fs=10)

    ax = fig.add_subplot(gs[1, 2])
    ax.plot(T, F, color=ORANGE, lw=1.6, label=f"wave spring preload {PCAP['F_spring']:.0f} N at 23 C")
    ax.plot(T, F - PCAP["k_spring"] * 0.01 * PCAP["standoff"]["h"] * MM, color=RED, lw=1.2, ls="--",
            label="after 1 % creep of the PTFE standoffs (spring takes it up)")
    ax.axhline(0, color=SUBTLE, lw=0.8)
    style(ax)
    legend(ax, loc="upper left")
    labels(ax, "clamp force per corner screw", "temperature (C)", "N", fs=10)
    fig.suptitle("Air-gap plate capacitor (64 x 64 x 1.6 FR4, 0.5 mm alumina spacers, PEEK + wave springs)", fontsize=13,
                 fontweight="bold", color=TEXT, fontfamily="monospace")
    fig.tight_layout()
    save(fig, "platecap_mechanics.svg")


# ===========================================================================
# 4. Mounting plate with the units
# ===========================================================================
def unit_masses(res):
    """kg; aluminium masses from mechanical/README, boards from section 1."""
    pc_base = P.PLATECAP_BASE_W * P.PLATECAP_BASE_D * P.PLATECAP_BASE_T * 1e-9 * MAT["POM"]["rho"]
    plates = 4 * (MAT["FR4_2L"]["rho"] * PCAP["t"] * PCAP["S"] ** 2)
    so = P.PLATE_STANDOFF
    ptfe = (8 * np.pi / 4 * (so["d"] ** 2 - so["bore"] ** 2) * so["h"]
            + 2 * np.pi / 4 * P.TERMINAL_POST["d"] ** 2 * P.TERMINAL_POST["h"]) * 1e-9 * MAT["PTFE"]["rho"]
    m = dict(
        amp=1.10 + res["amp_pcb_bare_mass_g"] / 1e3 + res["amp_parts_mass_g"] / 1e3 + 0.08,   # + 40 screws
        psu=0.70 + res["psu_pcb_bare_mass_g"] / 1e3 + res["psu_parts_mass_g"] / 1e3 + 0.06,
        platecap=pc_base + plates + ptfe + 0.02,
    )
    m["mount_plate"] = P.MOUNT_PLATE_W * P.MOUNT_PLATE_H * P.MOUNT_PLATE_T * 1e-9 * MAT["PEHD"]["rho"]
    m["box_empty"] = 2.3                 # Fibox ARCA 403015 PC (catalogue order, verify)
    m["glands_cables_studs"] = 0.45
    m["total"] = sum(m.values())
    return m


def mounting_plate(units, mat="PEHD", t=None, rigid=True, h=5 * MM, E_scale=1.0, extra_supports=()):
    W, H = P.MOUNT_PLATE_W * MM, P.MOUNT_PLATE_H * MM
    t = t or P.MOUNT_PLATE_T * MM
    import outer_box as OB
    studs = OB.stud_points()
    fix = OB.plate_fixing_points()
    cx, cy = W / 2, H / 2
    req_x = [cx + x * MM for pts in studs.values() for x, _ in pts] + [cx + x * MM for x, _ in fix]
    req_y = [cy + y * MM for pts in studs.values() for _, y in pts] + [cy + y * MM for _, y in fix]
    xs, ys = axis(W, h, req_x), axis(H, h, req_y)
    m = MAT[mat]
    pl = Plate(xs, ys, flex_rigidity(m["E"] * E_scale, t, m["nu"]), m["rho"] * t, m["nu"])
    for (x, y) in list(fix) + list(extra_supports):
        X0, Y0 = cx + x * MM, cy + y * MM
        pl.clamp(pl.nodes_in(lambda X, Y: np.hypot(X - X0, Y - Y0) <= P.BOX_BOSS_D / 2 * MM + 1e-9))
    nodes = {}
    for unit, pts in studs.items():
        ns = [pl.nearest(cx + x * MM, cy + y * MM) for x, y in pts]
        nodes[unit] = ns
        for n in ns:
            pl.point_mass[n] += units[unit] / len(ns)
        if rigid:
            pl.rigid_link(ns)
    pl.studs = nodes
    return pl


def transmissibility(pl, freq, phi, f, zeta, nodes):
    """|a_abs / a_base| averaged over nodes (base = box fixings), modal superposition."""
    gam = phi.T @ (pl.M @ pl.rigid_vector())
    w = 2 * np.pi * f
    T = np.ones_like(f, dtype=complex)
    wd = np.array([4 * n for n in nodes])
    for k, fk in enumerate(freq):
        wk = 2 * np.pi * fk
        Hk = w**2 / (wk**2 - w**2 + 2j * zeta * wk * w)
        T += np.mean(phi[wd, k]) * gam[k] * Hk
    return T


def run_mounting_plate(res):
    units = unit_masses(res["pcb"])
    out = dict(masses_kg=units)
    variants = {
        "PE-HD 8 mm, units flexible (bound)": dict(mat="PEHD", t=8 * MM, rigid=False, extra=[(-110, 50), (110, 50)]),
        # as designed since 2026-10-31: 4 corner bosses + 2 mid supports (params.MOUNT_PLATE_SUPPORTS)
        "PE-HD 8 mm (as designed)": dict(mat="PEHD", t=8 * MM, rigid=True, extra=[(-110, 50), (110, 50)]),
        "PE-HD 8 mm at -20 C": dict(mat="PEHD", t=8 * MM, rigid=True, E_scale=MAT["PEHD"]["E_m20"] / MAT["PEHD"]["E"], extra=[(-110, 50), (110, 50)]),
        "PE-HD 8 mm at +60 C": dict(mat="PEHD", t=8 * MM, rigid=True, E_scale=MAT["PEHD"]["E_p60"] / MAT["PEHD"]["E"], extra=[(-110, 50), (110, 50)]),
        "PE-HD 8 mm, corners only (before)": dict(mat="PEHD", t=8 * MM, rigid=True),
        "PE-HD 15 mm": dict(mat="PEHD", t=15 * MM, rigid=True),
        "Al 3 mm": dict(mat="Al", t=3 * MM, rigid=True),
        "Al 6 mm": dict(mat="Al", t=6 * MM, rigid=True),
    }
    fgrid = np.logspace(0, np.log10(300), 600)
    modal = {}
    for name, v in variants.items():
        u = dict(units)
        if v["mat"] == "Al":
            u["mount_plate"] = 0.0
        pl = mounting_plate(u, v["mat"], v["t"], v["rigid"], E_scale=v.get("E_scale", 1.0),
                            extra_supports=v.get("extra", ()))
        f, phi = pl.modes(10)
        zeta = MAT[v["mat"]]["zeta"]
        Tpc = transmissibility(pl, f, phi, fgrid, zeta, pl.studs["platecap"])
        Tamp = transmissibility(pl, f, phi, fgrid, zeta, pl.studs["amp"])
        # relative normal motion platecap vs amplifier (for the node2 lead), per 1 m/s^2 at the box
        rel = np.abs(Tpc - Tamp) / (2 * np.pi * fgrid) ** 2
        modal[name] = dict(pl=pl, f=f, phi=phi, Tpc=Tpc, Tamp=Tamp, rel=rel, zeta=zeta)
        inband = (fgrid >= 1) & (fgrid <= 50)
        out[name] = dict(modes_Hz=list(f[:5]), max_T_platecap_1_50Hz=float(np.max(np.abs(Tpc[inband]))),
                         max_T_amp_1_50Hz=float(np.max(np.abs(Tamp[inband]))))
    # static 5 g (transport, box lying on its back) stresses, design variant
    base = modal["PE-HD 8 mm (as designed)"]
    pl = base["pl"]
    f1 = base["f"][0]
    daf = srs_factor(f1, 0.011, MAT["PEHD"]["zeta"])
    u = pl.static_accel(5 * G * daf)
    svm = pl.stress_vm(u, MAT["PEHD"]["E"], 8 * MM)
    ug = pl.static_accel(G)
    out["static"] = dict(
        defl_1g_mm=float(np.max(np.abs(ug[0::4]))) / MM,
        shock_5g_daf=daf, shock_5g_defl_mm=float(np.max(np.abs(u[0::4]))) / MM,
        shock_5g_stress_vm_MPa=float(np.max(svm)) / 1e6,
        pehd_yield_MPa=22.0, pehd_longterm_MPa=4.0,
        boss_screw_force_5g_N=(units["amp"] + units["psu"] + units["platecap"] + units["mount_plate"]) * 5 * G * daf / 4,
    )
    flex = modal["PE-HD 8 mm, units flexible (bound)"]
    u2 = flex["pl"].static_accel(5 * G * srs_factor(flex["f"][0], 0.011, 0.03))
    out["static"]["shock_5g_stress_vm_flexible_MPa"] = float(np.max(flex["pl"].stress_vm(u2, MAT["PEHD"]["E"], 8 * MM))) / 1e6
    res["mounting_plate"] = out
    plot_mounting_plate(modal, fgrid)
    return modal, fgrid, units


def plot_mounting_plate(modal, fgrid):
    import outer_box as OB
    base = modal["PE-HD 8 mm (as designed)"]
    pl, f, phi = base["pl"], base["f"], base["phi"]
    fig = plt.figure(figsize=(15, 9))
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(2, 4, height_ratios=[1.25, 1])
    X, Y = np.meshgrid(pl.xs / MM - P.MOUNT_PLATE_W / 2, pl.ys / MM - P.MOUNT_PLATE_H / 2)
    cols = {"platecap": ORANGE, "amp": BLUE, "psu": PURPLE}
    for k in range(4):
        ax = fig.add_subplot(gs[0, k])
        w = pl.w_grid(phi[:, k])
        w /= np.max(np.abs(w))
        ax.contourf(X, Y, w, levels=np.linspace(-1, 1, 21), cmap="RdBu_r")
        ax.contour(X, Y, w, levels=[0], colors=[TEXT], linewidths=0.6)
        for unit, pts in OB.stud_points().items():
            xs_, ys_ = zip(*pts)
            ax.plot(xs_, ys_, "o", ms=4, color=cols[unit])
            ax.add_patch(plt.Rectangle((min(xs_), min(ys_)), max(xs_) - min(xs_), max(ys_) - min(ys_),
                                       fill=False, ec=cols[unit], lw=0.8))
        for x, y in OB.plate_fixing_points():
            ax.plot(x, y, "s", ms=6, color=YELLOW)
        ax.set_aspect("equal")
        style(ax)
        labels(ax, f"mode {k + 1}: {f[k]:.1f} Hz", "X (mm)", "Y (mm)" if k == 0 else "", fs=10)
    ax = fig.add_subplot(gs[1, :2])
    pal = [GREY, BLUE, BLUE, BLUE, GREEN, ORANGE, YELLOW, PURPLE]
    lss = ["--", "-", ":", "-.", "-", "-", "-", "-"]
    for (name, d), c, ls in zip(modal.items(), pal, lss):
        ax.loglog(fgrid, np.abs(d["Tpc"]), color=c, ls=ls, lw=1.3, label=f"{name}: f1 {d['f'][0]:.0f} Hz")
    sr_band(ax)
    ax.set_xlim(1, 300)
    style(ax)
    legend(ax, loc="lower left", ncol=1)
    labels(ax, "transmissibility box -> plate-capacitor studs (normal)", "frequency (Hz)", "|a_platecap / a_box|", fs=10)
    ax = fig.add_subplot(gs[1, 2:])
    for (name, d), c, ls in zip(modal.items(), pal, lss):
        if name in ("PE-HD 8 mm (as designed)", "Al 6 mm", "PE-HD 8 mm, corners only (before)", "PE-HD 8 mm, units flexible (bound)"):
            ax.loglog(fgrid, d["rel"] / 1e-6, color=c, ls=ls, lw=1.3, label=name)
    sr_band(ax)
    ax.set_xlim(1, 300)
    style(ax)
    legend(ax, loc="lower left")
    labels(ax, "relative motion plate cap vs amplifier (node2 lead)", "frequency (Hz)", "um per (m/s^2) at the box", fs=10)
    fig.suptitle("Mounting plate 240 x 350 (box fixings yellow; studs: plate cap orange, amplifier blue, PSU purple)",
                 fontsize=12, fontweight="bold", color=TEXT, fontfamily="monospace")
    fig.tight_layout()
    save(fig, "mounting_plate_modes.svg")


# ===========================================================================
# 5. Wind: loads, pole dynamics, buffeting and vortex shedding
# ===========================================================================
BOX_OUT = dict(W=0.300, H=0.400, D=0.150)          # Fibox ARCA 403015 outer
# shade roof (mechanical/params.SHADE_ROOF) on two shelf brackets on the same post: adds
# mass at the post top, a drip-edge strip to the frontal area, and uplift on the brackets
_R = P.SHADE_ROOF
ROOF = dict(m=2700 * (_R["w"] + 2 * _R["drip"]) * (_R["d"] + 2 * _R["drip"]) * _R["t"] * 1e-9 + 2 * 0.8,   # + 2 brackets
            A_front=_R["w"] * 1e-3 * (_R["drip"] + _R["t"]) * 1e-3, A_plan=_R["w"] * _R["d"] * 1e-6,
            cp_uplift=1.5)          # free-standing canopy, EN 1991-1-4 Table 7.6 order of magnitude
POLES = {
    "48.3x3.2, 2.0 m": dict(D=48.3e-3, t=3.2e-3, L=2.0),
    "60.3x4.0, 2.0 m": dict(D=60.3e-3, t=4.0e-3, L=2.0),
    "76.1x5.0, 1.5 m": dict(D=76.1e-3, t=5.0e-3, L=1.5),
    "114.3x6.3, 1.0 m": dict(D=114.3e-3, t=6.3e-3, L=1.0),
}
WIND = dict(
    St_box=0.12,       # EN 1991-1-4 Fig. E.1, rectangle d/b = 0.5 (wind on the door); edge-on d/b = 2 -> 0.06 on b = 0.15 m: same f
    St_pole=0.18,      # circular cylinder, subcritical Re (EN E.1.3.2: 0.18)
    cL_box=0.30,       # rms lateral coefficient of the short 3D box (free ends) -- assumption
    cL_pole=0.25,      # rms, reduced for spanwise correlation over 2 m (~5 d correlation length) -- assumption
    B_vs=0.20,         # relative bandwidth of the shedding spectrum in turbulent flow (Vickery & Clark: 0.1-0.3)
    delta_s=0.05,      # log decrement steel pole + bolted plastic box (EN F.2: welded steel 0.02, bolted 0.03)
    cf_pole=1.2,
    U_ops=(3.0, 6.0, 10.0),
)


def cf_rect(d_over_b, slender_l, b):
    """EN 1991-1-4 7.6: c_f = c_f0(d/b) psi_lambda (sharp corners, psi_r = 1).
    Fig 7.23 read approximately; psi_lambda from Fig 7.36 (solidity 1), lambda = 2 l/b (l < 15 m)."""
    db = [0.1, 0.2, 0.5, 0.7, 1.0, 2.0, 5.0, 10.0]
    c0 = [2.0, 2.1, 2.35, 2.4, 2.1, 1.65, 1.0, 0.9]
    cf0 = float(np.interp(np.log10(d_over_b), np.log10(db), c0))
    lam = min(2 * slender_l / b, 70)
    psi = float(np.interp(np.log10(lam), np.log10([1, 10, 70]), [0.6, 0.7, 0.92]))
    return cf0 * psi, cf0, psi


def en_qp(vb0, z):
    z0 = SITE["z0"]
    ze = max(z, SITE["z_min"])
    kr = 0.19 * (z0 / 0.05) ** 0.07
    vm = kr * np.log(ze / z0) * vb0
    Iv = 1 / np.log(ze / z0)
    qp = (1 + 7 * Iv) * 0.5 * RHO_AIR * vm**2
    return dict(vm=vm, Iv=Iv, qp=qp, v_peak=np.sqrt(2 * qp / RHO_AIR))


def pole_sdof(pole, m_box):
    I = np.pi / 64 * (pole["D"] ** 4 - (pole["D"] - 2 * pole["t"]) ** 4)
    EI = MAT["steel"]["E"] * I
    k = 3 * EI / pole["L"] ** 3
    mpole = MAT["steel"]["rho"] * np.pi / 4 * (pole["D"] ** 2 - (pole["D"] - 2 * pole["t"]) ** 2) * pole["L"]
    m = m_box + 0.236 * mpole
    W = I / (pole["D"] / 2)
    return dict(k=k, m=m, f=np.sqrt(k / m) / 2 / np.pi, EI=EI, W=W, mpole=mpole)


def wind_spectra(U, sd, f, Iv, Lz):
    """Box acceleration ASD (m/s^2/rtHz) normal to the door for a pole-mounted box:
    along-wind buffeting (wind on the door) and across-wind vortex shedding (wind
    along the door) from the box and from the pole."""
    A = BOX_OUT["W"] * BOX_OUT["H"] + ROOF["A_front"]
    cf, _, _ = cf_rect(BOX_OUT["D"] / BOX_OUT["W"], BOX_OUT["H"], BOX_OUT["W"])
    sigma_u = Iv * U
    fL = f * Lz / U
    SL = 6.8 * fL / (1 + 10.2 * fL) ** (5 / 3)
    Su = sigma_u**2 * SL / f
    chi2 = 1 / (1 + (2 * f * np.sqrt(A) / U) ** (4 / 3)) ** 2
    pole_area = sd["pole"]["D"] * sd["pole"]["L"]
    Fd = RHO_AIR * U * (cf * A + 0.375 * WIND["cf_pole"] * pole_area)
    S_buf = Fd**2 * Su * chi2
    q = 0.5 * RHO_AIR * U**2

    def vs(St, b, area, cl):
        fs = St * U / b
        Bf = WIND["B_vs"] * fs
        return (q * cl * area) ** 2 / (np.sqrt(np.pi) * Bf) * np.exp(-((f - fs) / Bf) ** 2), fs
    S_vb, fs_box = vs(WIND["St_box"], BOX_OUT["W"], BOX_OUT["D"] * BOX_OUT["H"] * 2, WIND["cL_box"])   # b=0.15, St .06 == .12 on 0.30
    S_vp, fs_pole = vs(WIND["St_pole"], sd["pole"]["D"], 0.375 * pole_area, WIND["cL_pole"])
    zeta_a = RHO_AIR * cf * A * U / (4 * np.pi * sd["f"] * sd["m"])
    zeta = WIND["delta_s"] / (2 * np.pi) + zeta_a
    r = f / sd["f"]
    Ha = (2 * np.pi * f) ** 2 / (sd["k"] * (1 - r**2 + 2j * zeta * r))
    return dict(buffet=np.sqrt(S_buf) * np.abs(Ha), vortex=np.sqrt(S_vb + S_vp) * np.abs(Ha),
                fs_box=fs_box, fs_pole=fs_pole, zeta=zeta)


def run_wind(res, units, modal):
    out = {}
    m_box = units["total"] + ROOF["m"]
    # --- design wind pressure
    q20 = en_qp(SITE["v_b0"], SITE["z_box"])
    q25 = en_qp(SITE["v_b0_alt"], SITE["z_box"])
    q_storm = 0.5 * RHO_AIR * SITE["v_storm_gust"] ** 2
    q_des = max(q20["qp"], q25["qp"], q_storm)
    cf_door, cf0_d, psi_d = cf_rect(BOX_OUT["D"] / BOX_OUT["W"], BOX_OUT["H"], BOX_OUT["W"])
    cf_side, cf0_s, psi_s = cf_rect(BOX_OUT["W"] / BOX_OUT["D"], BOX_OUT["H"], BOX_OUT["D"])
    F_door = cf_door * q_des * BOX_OUT["W"] * BOX_OUT["H"]
    F_side = cf_side * q_des * BOX_OUT["D"] * BOX_OUT["H"]
    out["pressure"] = dict(EN_vb20=q20, EN_vb25=q25, storm_gust_q_Pa=q_storm, q_design_Pa=q_des,
                           cf_door=cf_door, cf0_door=cf0_d, psi_lambda_door=psi_d, cf_side=cf_side,
                           F_door_N=F_door, F_side_N=F_side)
    # --- box fixings (4 x M6 through the box's corner lugs / wall brackets, assumed pattern)
    lug_dx, lug_dy = 0.26, 0.43
    arm = BOX_OUT["D"] / 2 + 0.02
    W_box = m_box * G
    T_suction = F_door / 4                              # door-face suction case, all four in tension
    T_side = F_side * arm / lug_dx / 2                  # side wind overturning, two lugs
    V_per = np.hypot(W_box, F_side) / 4
    T_weight = W_box * arm / lug_dy / 2                 # weight acting at the CG arm (vertical box)
    out["box_fixings"] = dict(assumed="4 x M6 A2-70 through the box lugs, pattern 260 x 430 mm, CG 95 mm off the wall",
                              tension_per_screw_N=T_suction + T_side + T_weight, shear_per_screw_N=V_per,
                              M6_A2_70_proof_N=0.75 * 450e6 * 20.1e-6,
                              SF_screw=0.75 * 450e6 * 20.1e-6 / (T_suction + T_side + T_weight),
                              PC_lug_pullthrough_N=np.pi * 12e-3 * 4e-3 * 0.6 * 60e6)
    out["box_fixings"]["SF_lug"] = out["box_fixings"]["PC_lug_pullthrough_N"] / out["box_fixings"]["tension_per_screw_N"]
    # --- ice / snow (minor)
    area_exp = BOX_OUT["W"] * BOX_OUT["H"] + 2 * BOX_OUT["D"] * BOX_OUT["H"] + BOX_OUT["W"] * BOX_OUT["D"]
    m_ice = area_exp * SITE["ice_t"] * 900
    F_snow = SITE["snow_sk"] * 0.8 * BOX_OUT["W"] * BOX_OUT["D"]
    out["ice_snow"] = dict(ice_mass_kg=m_ice, snow_on_top_N=F_snow)
    out["shade_roof"] = dict(mass_incl_brackets_kg=ROOF["m"], uplift_storm_N=ROOF["cp_uplift"] * q_des * ROOF["A_plan"],
                             uplift_per_bracket_N=ROOF["cp_uplift"] * q_des * ROOF["A_plan"] / 2,
                             snow_N=SITE["snow_sk"] * 0.8 * ROOF["A_plan"])
    # --- poles
    poles = {}
    for name, pole in POLES.items():
        sd = pole_sdof(pole, m_box)
        sd["pole"] = pole
        sd_ice = pole_sdof(pole, m_box + m_ice)
        F_pole = WIND["cf_pole"] * q_des * pole["D"] * pole["L"]
        M_base = max(F_door, F_side) * pole["L"] + F_pole * pole["L"] / 2 + W_box * arm
        sigma = M_base / sd["W"]
        defl = max(F_door, F_side) * pole["L"] ** 3 / (3 * sd["EI"])
        vcrit_box = sd["f"] * BOX_OUT["W"] / WIND["St_box"]
        vcrit_pole = sd["f"] * pole["D"] / WIND["St_pole"]
        m_e = sd["m"] / BOX_OUT["H"]
        Sc = 2 * WIND["delta_s"] * m_e / (RHO_AIR * BOX_OUT["W"] ** 2)
        poles[name] = dict(f_Hz=sd["f"], f_with_ice_Hz=sd_ice["f"], k_N_per_m=sd["k"], m_eff_kg=sd["m"],
                           M_base_Nm=M_base, sigma_base_MPa=sigma / 1e6,
                           SF_yield=MAT["steel"]["fy"] / sigma, utilisation_EN=1.5 * sigma / MAT["steel"]["fy"],
                           static_defl_mm=defl / MM,
                           vcrit_box_ms=vcrit_box, vcrit_pole_ms=vcrit_pole, Scruton_box=Sc,
                           EN_E131_needs_check=bool(vcrit_box < 1.25 * q20["vm"]),
                           lockin_in_storm=bool(vcrit_box < SITE["v_storm_gust"]))
        sd_all = sd
        poles[name]["_sd"] = sd_all
    out["poles"] = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in poles.items()}
    out["wall"] = dict(note="Box on a building wall with 4 lugs: rigid-body mode set by the PC lugs, "
                            "estimated k ~ 1e6 N/m per lug",
                       f_Hz=np.sqrt(4e6 / m_box) / (2 * np.pi))
    out["shedding_freq_per_ms"] = dict(box=WIND["St_box"] / BOX_OUT["W"], pole_48=WIND["St_pole"] / 0.0483,
                                       antenna_wire_2mm=0.2 / 0.002)
    res["wind"] = out
    return poles


# ===========================================================================
# 6. Microphonics: sensitivities and spectra
# ===========================================================================
LEADS = {
    "node2 lead (IN+ post -> PTFE bush), stranded 0.5 mm2": dict(L=0.100, L_near=0.050, h=12e-3, r=0.4e-3, stranded=True),
    "node2 lead, solid 0.8 mm": dict(L=0.100, L_near=0.050, h=12e-3, r=0.4e-3, stranded=False),
    "antenna lead (gland -> ANT post), stranded": dict(L=0.080, L_near=0.040, h=20e-3, r=0.4e-3, stranded=True),
    # as designed since 2026-10-31: solid 0.8 mm, held on a PTFE post halfway (span halved);
    # antenna lead tied to a PTFE post right after the gland
    "node2 lead, solid 0.8 mm, PTFE post midway (as designed)": dict(L=0.050, L_near=0.025, h=12e-3, r=0.4e-3, stranded=False),
    "antenna lead, tied after the gland (as designed)": dict(L=0.040, L_near=0.020, h=20e-3, r=0.4e-3, stranded=True),
}
CG = dict(rho=1400.0, H=0.0395, E_eff=(0.5e9, 1e9, 5e9), avg=0.5)


def lead_props(ld):
    d_c = 2 * ld["r"]
    if ld["stranded"]:
        EI_c = 19 * MAT["Cu"]["E"] * np.pi * (0.18e-3) ** 4 / 64       # 19 x 0.18 mm, strands slip
    else:
        EI_c = MAT["Cu"]["E"] * np.pi * d_c**4 / 64
    EI_j = MAT["PTFE"]["E"] * np.pi * ((1.4e-3) ** 4 - d_c**4) / 64
    mu = MAT["Cu"]["rho"] * np.pi / 4 * d_c**2 * (0.9 if ld["stranded"] else 1.0) \
        + MAT["PTFE"]["rho"] * np.pi / 4 * ((1.4e-3) ** 2 - d_c**2)
    f1 = np.pi / (2 * ld["L"] ** 2) * np.sqrt((EI_c + EI_j) / mu)
    Cp = 2 * np.pi * EPS0 / np.arccosh(ld["h"] / ld["r"])
    dCp = 2 * np.pi * EPS0 / np.arccosh(ld["h"] / ld["r"]) ** 2 / np.sqrt(ld["h"] ** 2 - ld["r"] ** 2)
    return f1, Cp, dCp


def lead_sens(ld, f, zeta=0.03, V=ELEC["V_lead"]):
    """EMF-referred V per (m/s^2) of base acceleration, vs frequency."""
    f1, Cp, dCp = lead_props(ld)
    w1 = 2 * np.pi * f1
    r = f / f1
    disp = 1.15 / w1**2 / np.abs(1 - r**2 + 2j * zeta * r)
    dC = dCp * ld["L_near"] * disp
    return V * dC / ELEC["C_ant"], f1, Cp * ld["L"]


def cg_sens(E_eff):
    p = CG["rho"] * CG["H"] / 2
    dCC = CG["avg"] * p / E_eff
    return ELEC["V_lead"] * dCC / ELEC["divider"]


VC = {"VC-A (50 um/s)": 50e-6, "ISO residential day (200 um/s)": 200e-6, "VC-C (12.5 um/s)": 12.5e-6}


def vc_asd(v13, f):
    """Acceleration ASD for a constant 1/3-octave rms velocity criterion."""
    return 2 * np.pi * f * v13 / np.sqrt(0.2316 * f)


def run_microphonics(res, modal, fgrid, poles):
    pc = res["plate_capacitor"]["microphonic"]
    f = fgrid
    out = {}
    f1p = pc["f1_plate_Hz"]
    S_pc = pc["S_nominal_V_per_ms2"] / np.abs(1 - (f / f1p) ** 2)
    out["sensitivity_V_per_ms2_at_8Hz"] = {}
    out["threshold_ms2_rtHz_at_8Hz"] = {}
    i8 = np.argmin(np.abs(f - 7.83))
    out["sensitivity_V_per_ms2_at_8Hz"][f"plate capacitors (5 % mismatch, {ELEC['V_dc_nom']} V)"] = S_pc[i8]
    out["sensitivity_V_per_ms2_at_8Hz"][f"plate capacitors worst (10 %, {ELEC['V_dc_worst']} V, coherent)"] = pc["S_worst_V_per_ms2"]
    leads = {}
    for name, ld in LEADS.items():
        s, f1, C = lead_sens(ld, f)
        leads[name] = s
        out["sensitivity_V_per_ms2_at_8Hz"][name] = s[i8]
        out.setdefault("lead_f1_Hz", {})[name] = f1
        out.setdefault("lead_C_pF", {})[name] = C / 1e-12
    for E in CG["E_eff"]:
        out["sensitivity_V_per_ms2_at_8Hz"][f"C202 Cg film, E_eff {E / 1e9:.1f} GPa"] = cg_sens(E)
    for k, v in out["sensitivity_V_per_ms2_at_8Hz"].items():
        out["threshold_ms2_rtHz_at_8Hz"][k] = ELEC["floor"] / v
    out["guarded_input_node"] = "IN+ to guard: guard follows IN- (offset < 0.2 mV), so V_dc across it is ~1e-4 of 2.5 V: negligible"
    out["fair_weather_antenna"] = dict(
        EMF_dc_V=ELEC["E_fair"] * ELEC["h_eff"],
        dh_eff_for_floor_nm_rtHz=ELEC["floor"] / ELEC["E_fair"] / 1e-9,
        EMF_per_mm_vertical_mV=ELEC["E_fair"] * 1e-3 * 1e3,
    )

    # spectra: total microphonic EMF ASD
    base = modal["PE-HD 8 mm (as designed)"]
    alt = modal["Al 6 mm"]
    lead_main = leads["node2 lead, solid 0.8 mm, PTFE post midway (as designed)"]
    lead_ant = leads["antenna lead, tied after the gland (as designed)"]
    lead_solid = leads["node2 lead, solid 0.8 mm"]
    S_cg = cg_sens(1e9)

    def emf(a_box, md, lead=lead_main):
        a_pc = a_box * np.abs(md["Tpc"])
        a_amp = a_box * np.abs(md["Tamp"])
        e_pc = S_pc * a_pc
        e_lead = lead * a_amp + ELEC["V_lead"] * lead_props(LEADS["node2 lead, solid 0.8 mm, PTFE post midway (as designed)"])[2] \
            * 0.040 * 0.5 * md["rel"] * a_box / ELEC["C_ant"]
        e_ant = lead_ant * a_pc
        e_cg = S_cg * a_amp
        return np.sqrt(e_pc**2 + e_lead**2 + e_ant**2 + e_cg**2), dict(pc=e_pc, lead=e_lead, ant=e_ant, cg=e_cg)

    spectra = {}
    q = en_qp(SITE["v_b0"], SITE["z_box"])
    Lz = 300 * (max(SITE["z_box"], SITE["z_min"]) / 200) ** (0.67 + 0.05 * np.log(SITE["z0"]))
    pole_name = "60.3x4.0, 2.0 m"
    sd = poles[pole_name]["_sd"]
    for U in WIND["U_ops"]:
        ws = wind_spectra(U, sd, f, q["Iv"], Lz)
        a_box = np.sqrt(ws["buffet"] ** 2 + ws["vortex"] ** 2)
        e, parts = emf(a_box, base)
        e_al, _ = emf(a_box, alt, lead_solid)
        spectra[f"pole {U:.0f} m/s"] = dict(a_box=a_box, e=e, e_al6=e_al, parts=parts, ws=ws)
    for name, v in VC.items():
        a_box = vc_asd(v, f)
        e, parts = emf(a_box, base)
        e_al, _ = emf(a_box, alt, lead_solid)
        spectra[f"wall, {name}"] = dict(a_box=a_box, e=e, e_al6=e_al, parts=parts)
    inband = (f >= 3) & (f <= 50)
    out["spectra_summary"] = {}
    for k, s in spectra.items():
        out["spectra_summary"][k] = dict(
            a_box_max_1_50Hz=float(np.max(s["a_box"][inband])),
            emf_max_nV=float(np.max(s["e"][inband])) / 1e-9,
            emf_at_SR1_nV=float(s["e"][i8]) / 1e-9,
            f_of_max_Hz=float(f[inband][np.argmax(s["e"][inband])]),
            emf_max_Al6_solidlead_nV=float(np.max(s["e_al6"][inband])) / 1e-9,
            fraction_band_above_floor=float(np.mean(s["e"][inband] > ELEC["floor"])),
            dominant=max(s["parts"], key=lambda kk: np.max(s["parts"][kk][inband])),
        )
    out["pole_for_spectra"] = pole_name
    out["turbulence"] = dict(Iv=q["Iv"], L_m=Lz)
    res["microphonics"] = out
    plot_microphonics(f, spectra, out, poles)
    return out


def plot_microphonics(f, spectra, out, poles):
    fig = plt.figure(figsize=(15, 9.5))
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(2, 2)
    ax = fig.add_subplot(gs[0, 0])
    sens = out["threshold_ms2_rtHz_at_8Hz"]
    names = list(sens.keys())
    vals = [sens[k] for k in names]
    colors = [ORANGE if "plate" in k else BLUE if "lead" in k else PURPLE for k in names]
    ax.barh(range(len(vals)), vals, color=colors)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels([k[:52] for k in names], fontsize=7, color=TEXT, fontfamily="monospace")
    ax.set_xscale("log")
    ax.set_ylim(-1.2, len(vals) - 0.5)
    for xv, lab in ((vc_asd(50e-6, 7.83), "VC-A"), (vc_asd(200e-6, 7.83), "ISO res. day")):
        ax.axvline(xv, color=GREY, ls="--", lw=0.8)
        ax.text(xv, -0.85, " " + lab + " at 7.8 Hz", color=GREY, fontsize=7, va="center", ha="left")
    style(ax)
    labels(ax, "acceleration for microphonics = 45.8 nV/rtHz (at SR1)", "m/s^2/rtHz (at the part)", "", fs=10)

    ax = fig.add_subplot(gs[0, 1])
    cols = {"pole 3 m/s": GREEN, "pole 6 m/s": YELLOW, "pole 10 m/s": RED,
            "wall, VC-A (50 um/s)": BLUE, "wall, ISO residential day (200 um/s)": PURPLE, "wall, VC-C (12.5 um/s)": GREY}
    for k, s in spectra.items():
        ax.loglog(f, s["a_box"], color=cols[k], lw=1.2, label=k)
    sr_band(ax)
    ax.set_xlim(1, 100)
    ax.set_ylim(1e-6, 10)
    style(ax)
    legend(ax, loc="upper right")
    labels(ax, f"box acceleration normal to the door (pole {out['pole_for_spectra']})", "frequency (Hz)",
           "m/s^2/rtHz", fs=10)

    ax = fig.add_subplot(gs[1, 0])
    for k, s in spectra.items():
        ax.loglog(f, s["e"] / 1e-9, color=cols[k], lw=1.3, label=k)
    ax.axhline(ELEC["floor"] / 1e-9, color=TEXT, lw=1.2, ls="--", label="receiver floor 45.8 nV/rtHz")
    ax.axhline(ELEC["sr1_quiet"] / 1e-9, color=GREEN, lw=0.9, ls=":", label="quiet SR1 peak (EMF)")
    sr_band(ax)
    ax.set_xlim(1, 100)
    ax.set_ylim(1e-2, 1e6)
    style(ax)
    legend(ax, loc="upper right")
    labels(ax, "microphonic EMF, design as built (PE-HD 8 mm, stranded lead)", "frequency (Hz)", "nV/rtHz at the antenna", fs=10)

    ax = fig.add_subplot(gs[1, 1])
    s = spectra["pole 6 m/s"]
    pc = {"pc": ("plate capacitors", ORANGE), "lead": ("node2 lead", BLUE), "ant": ("antenna lead", GREEN),
          "cg": ("C202 Cg film", PURPLE)}
    for kk, (lab, c) in pc.items():
        ax.loglog(f, s["parts"][kk] / 1e-9, color=c, lw=1.2, label=lab)
    ax.loglog(f, s["e_al6"] / 1e-9, color=TEXT, lw=1.0, ls="-.", label="total: 6 mm Al plate + solid lead")
    ax.axhline(ELEC["floor"] / 1e-9, color=TEXT, lw=1.2, ls="--", label="floor 45.8 nV/rtHz")
    sr_band(ax)
    ax.set_xlim(1, 100)
    ax.set_ylim(1e-2, 1e6)
    style(ax)
    legend(ax, loc="upper right")
    labels(ax, "breakdown, pole-mounted box at 6 m/s", "frequency (Hz)", "nV/rtHz at the antenna", fs=10)
    fig.suptitle(f"Microphonics referred to the antenna EMF (V_dc {ELEC['V_dc_nom']} V across the plate caps)", fontsize=13,
                 fontweight="bold", color=TEXT, fontfamily="monospace")
    fig.tight_layout()
    save(fig, "microphonics.svg")


def plot_wind(res, poles):
    fig = plt.figure(figsize=(15, 6))
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.3, 1])
    ax = fig.add_subplot(gs[0, 0])
    U = np.linspace(0.5, 32, 300)
    ax.plot(U, WIND["St_box"] * U / BOX_OUT["W"], color=ORANGE, lw=1.6, label="box shedding (St 0.12 on 0.30 m)")
    ax.plot(U, WIND["St_pole"] * U / 0.0483, color=BLUE, lw=1.2, label="pole 48.3 mm shedding")
    ax.plot(U, WIND["St_pole"] * U / 0.0603, color=BLUE, lw=1.2, ls="--", label="pole 60.3 mm shedding")
    pal = [RED, YELLOW, GREEN, PURPLE]
    for (name, p), c in zip(poles.items(), pal):
        ax.axhline(p["f_Hz"], color=c, lw=1.0, ls=":", label=f"box on pole {name}: {p['f_Hz']:.1f} Hz")
    mp = res["mounting_plate"]["PE-HD 8 mm (as designed)"]["modes_Hz"][0]
    ax.axhline(mp, color=TEXT, lw=1.0, ls="-.", label=f"mounting plate mode 1: {mp:.0f} Hz")
    ax.axhspan(1, 50, color=GREEN, alpha=0.05)
    ax.axvline(res["wind"]["pressure"]["EN_vb20"]["vm"], color=GREY, lw=0.8)
    ax.text(res["wind"]["pressure"]["EN_vb20"]["vm"], 92, " v_m 50-yr\n (2 m)", color=GREY, fontsize=7, va="top")
    ax.axvline(SITE["v_storm_gust"], color=GREY, lw=0.8)
    ax.text(SITE["v_storm_gust"], 92, "storm gust ", color=GREY, fontsize=7, va="top", ha="right")
    ax.set_ylim(0, 100)
    ax.set_xlim(0, 32)
    style(ax)
    legend(ax, loc="upper left")
    labels(ax, "vortex shedding frequency vs structural modes (ELF band shaded)", "wind speed (m/s)", "Hz", fs=10)
    ax = fig.add_subplot(gs[0, 1])
    names = list(poles.keys())
    sf = [poles[n]["SF_yield"] for n in names]
    vc = [poles[n]["vcrit_box_ms"] for n in names]
    x = np.arange(len(names))
    ax.bar(x - 0.2, sf, 0.4, color=GREEN, label="SF on yield at design gust")
    ax.bar(x + 0.2, vc, 0.4, color=ORANGE, label="v_crit box lock-in (m/s)")
    ax.axhline(SITE["v_storm_gust"], color=RED, lw=0.8, ls="--", label="30 m/s storm gust")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=7.5, color=TEXT, fontfamily="monospace", rotation=12)
    ax.set_yscale("log")
    style(ax)
    legend(ax, loc="upper left")
    labels(ax, "pole options: strength and lock-in speed", "", "", fs=10)
    fig.suptitle(f"Wind on the outdoor box (east Slovenia, q_design {res['wind']['pressure']['q_design_Pa']:.0f} Pa)",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    fig.tight_layout()
    save(fig, "wind_vortex.svg")


# ===========================================================================
# 7. Shield frame, lid and tray panels
# ===========================================================================
def clamped_rect_f1(a, b, E, t, rho, nu, h=1.5 * MM):
    pl = Plate(axis(a, h), axis(b, h), flex_rigidity(E, t, nu), rho * t, nu)
    pl.clamp(pl.nodes_in(lambda X, Y: (X < 1e-9) | (X > a - 1e-9) | (Y < 1e-9) | (Y > b - 1e-9)))
    f, _ = pl.modes(2)
    return float(f[0])


def run_shield(res, units):
    al = MAT["Al"]
    out = {}
    for name, c in P.COMPARTMENTS.items():
        a, b = (c["x1"] - c["x0"]) * MM, (c["y1"] - c["y0"]) * MM
        out[f"lid panel {name}"] = clamped_rect_f1(a, b, al["E"], P.LID_T * MM, al["rho"], al["nu"])
        out[f"tray floor {name}"] = clamped_rect_f1(a, b, al["E"], P.TRAY_FLOOR_T * MM, al["rho"], al["nu"])
    # frame + tray as a free-free beam (two long bars + tray rim), bending normal to the PCB
    I = 2 * P.WALL_T * P.FRAME_H**3 / 12 * MM**4
    L = (P.PCB_W + 2 * P.LID_EAR) * MM
    mu = units["amp"] / L
    out["shield beam free-free"] = 22.37 / (2 * np.pi * L**2) * np.sqrt(al["E"] * I / mu)
    # shield on its 4 ear studs: ear bending (2 mm Al, 7 mm to the frame) + stud in PE-HD
    I_ear = 100 * MM * (P.LID_T * MM) ** 3 / 12
    k_ear = 3 * al["E"] * I_ear / (P.LID_EAR_HOLE_X_OFF * MM) ** 3
    k_stud = MAT["PEHD"]["E"] * np.pi / 4 * ((12 * MM) ** 2 - (4.5 * MM) ** 2) / (8 * MM)
    k_tot = 4 / (1 / (k_ear / 2) + 1 / k_stud)
    out["shield on studs (local)"] = np.sqrt(k_tot / units["amp"]) / (2 * np.pi)
    # PSU base 3 mm Al between the bars
    out["PSU base panel"] = clamped_rect_f1(P.PSU_INNER_W * MM, P.PSU_INNER_D * MM, al["E"], P.PSU_BASE_T * MM, al["rho"], al["nu"])
    # sun/rain shade roof (bom B11: 1 mm Al 500 x 400, 30 mm stand-off), on 4 or 6 fixings 20 mm in
    for n_fix, pts in ((4, [(0.02, 0.02), (0.48, 0.02), (0.02, 0.38), (0.48, 0.38)]),
                       (6, [(0.02, 0.02), (0.25, 0.02), (0.48, 0.02), (0.02, 0.38), (0.25, 0.38), (0.48, 0.38)])):
        roof = Plate(axis(0.5, 10 * MM, [0.02, 0.25, 0.48]), axis(0.4, 10 * MM, [0.02, 0.38]),
                     flex_rigidity(al["E"], 1 * MM, al["nu"]), al["rho"] * 1 * MM, al["nu"])
        for x, y in pts:
            roof.clamp([roof.nearest(x, y)])
        out[f"shade roof 1 mm Al, {n_fix} fixings"] = float(roof.modes(2)[0][0])
    # stud loads: unit weight with CG offset (box vertical) and 5 g normal
    loads = {}
    for unit, (span, cg) in {"amp": (60e-3, 0.040), "psu": (60e-3, 0.030)}.items():
        m = units[unit]
        loads[unit] = dict(weight_moment_tension_N=m * G * cg / span / 2,
                           shock_5g_per_stud_N=m * 5 * G * 1.7 / 4,
                           pehd_bearing_MPa=m * 5 * G * 1.7 / 4 / (np.pi / 4 * ((8 * MM) ** 2 - (4.5 * MM) ** 2)) / 1e6)
    res["shield_and_units"] = dict(f1_Hz=out, stud_loads=loads,
                                   shade_roof_wind_N=1.3 * 562.5 * 0.5 * 0.4,
                                   shade_roof_note="force coefficient 1.3 (canopy, EN 7.3, net, either sign) on 0.2 m^2")
    return out


# ===========================================================================
# 8. Transport shock on the heavy parts
# ===========================================================================
HEAVY = {
    # ref: (mass g, height of CG above board mm, lead dia mm, n leads, lever for overturning mm, seated)
    "C202": dict(board="amp", m=43.0, hcg=19.75, d=1.0, n=2, lever=10.0, desc="WIMA MKS4 100 uF film (Cg)"),
    "C301": dict(board="amp", m=5.5, hcg=9.0, d=0.8, n=2, lever=4.25, desc="WIMA MKS4 10 uF film"),
    "C207": dict(board="amp", m=7.6, hcg=12.5, d=0.8, n=2, lever=8.0, desc="4700 uF 16 x 25 electrolytic"),
    "PS1": dict(board="psu", m=40.0, hcg=10.75, d=1.0, n=4, lever=12.7, desc="IRM-05-15 module"),
    "C8": dict(board="psu", m=3.6, hcg=15.75, d=0.6, n=2, lever=5.0, desc="EDLC 10 F, 10 x 31.5"),
    "C16": dict(board="psu", m=4.2, hcg=10.0, d=0.6, n=2, lever=6.25, desc="2200 uF 12.5 x 20 electrolytic"),
    "K1": dict(board="psu", m=1.8, hcg=3.8, d=0.45, n=4, lever=2.5, desc="SIL05 reed relay"),
    "L1": dict(board="psu", m=3.0, hcg=3.0, d=None, n=4, lever=6.0, pad_area=6e-6, desc="SRF1260 SMD choke"),
}
SOLDER = dict(tau_static=20e6, tau_fatigue=3e6)     # SAC305: ~35-40 MPa ultimate shear; 3 MPa for >1e6 cycles
LEAD_YIELD = 150e6


def run_shock(res, models, amp_parts, psu_parts):
    out = {}
    for a_g in (5.0, 15.0):
        T = 0.011
        board_acc = {}
        for nm, sup, parts in (("amp", "frame", amp_parts), ("amp", "screws", amp_parts),
                               ("psu", "clamped", psu_parts), ("psu", "pinned", psu_parts)):
            pl, f, phi = models[(nm, sup)]
            sets = {}
            for ref, h in HEAVY.items():
                if h["board"] != nm:
                    continue
                p = next(p for p in parts if p["ref"] == ref)
                sets[ref] = [pl.nearest(x * MM, y * MM) for _, x, y in p["pads"] if _ != "np_thru_hole"]
            r = modal_shock(pl, phi, f, a_g * G, T, 0.03, sets)
            board_acc[(nm, sup)] = r
            out[f"{a_g:.0f}g_{nm}_{sup}_board"] = dict(max_rel_defl_mm=r["max_rel_defl_m"] / MM,
                                                       part_acc_g={k: v for k, v in r.items() if k != "max_rel_defl_m"})
        parts_out = {}
        for ref, h in HEAVY.items():
            sup = "screws" if h["board"] == "amp" else "pinned"
            a_n = board_acc[(h["board"], sup)][ref] * G          # normal to the board (worst support case)
            a_l = a_g * G * 1.7                                  # in-plane, SRS peak of a half-sine (rocking mode)
            m = h["m"] * 1e-3
            if h["d"]:
                A_j = np.pi * h["d"] * MM * P.PCB_T * MM         # PTH barrel shear area per lead
            else:
                A_j = h["pad_area"]
            tau_n = m * a_n / h["n"] / A_j
            M = m * a_l * h["hcg"] * MM
            # seated: overturning taken by the leads on the far side, fulcrum at the body edge
            F_lead = M / (h["lever"] * MM) / max(1, h["n"] // 2)
            tau_l = F_lead / A_j
            if h["d"]:
                sig_b = (M / h["n"]) / (np.pi * (h["d"] * MM) ** 3 / 32)     # not seated: leads bend
            else:
                sig_b = 0.0
            parts_out[ref] = dict(desc=h["desc"], a_normal_g=a_n / G, tau_normal_MPa=tau_n / 1e6,
                                  tau_overturn_seated_MPa=tau_l / 1e6,
                                  SF_solder_static=SOLDER["tau_static"] / max(tau_n, tau_l),
                                  SF_solder_fatigue=SOLDER["tau_fatigue"] / max(tau_n, tau_l),
                                  lead_bending_if_not_seated_MPa=sig_b / 1e6,
                                  SF_lead_if_not_seated=(LEAD_YIELD / sig_b) if sig_b else None)
        out[f"{a_g:.0f}g_parts"] = parts_out
    # Steinberg allowable board deflection for the largest SMD packages (fatigue-based, 2e7 cycles)
    def steinberg(B_mm, L_mm, c=1.0, r=1.0):
        B, L, h = B_mm / 25.4, L_mm / 25.4, P.PCB_T / 25.4
        return 0.00022 * B / (c * h * r * np.sqrt(L)) * 25.4
    out["steinberg_allow_mm"] = dict(amp_SSOP28_in_86mm_bay=steinberg(86, 10.2),
                                     psu_SOIC16_150mm_span=steinberg(150, 9.9))
    res["shock"] = out
    return out


# ===========================================================================
def main():
    res = {}
    st = _selftest()
    res["fem_selftest_lambda"] = {k: dict(fem=v[0], leissa=v[1]) for k, v in st.items()}
    print("FEM self-test:", {k: round(v[0], 3) for k, v in st.items()})
    pcb, models, amp_parts, psu_parts = run_pcbs()
    res["pcb"] = pcb
    print("PCB modes:", {k: [round(x) for x in v] for k, v in pcb.items() if k.endswith("Hz")})
    run_platecap(res)
    pcm = res["plate_capacitor"]["microphonic"]
    print("Plate cap: f1 %.0f Hz, S %.3g V/(m/s2), threshold %.3g m/s2/rtHz" % (
        pcm["f1_plate_Hz"], pcm["S_nominal_V_per_ms2"], pcm["threshold_nominal_ms2_rtHz"]))
    modal, fgrid, units = run_mounting_plate(res)
    print("Mounting plate:", {k: round(v["modes_Hz"][0], 1) for k, v in res["mounting_plate"].items()
                              if isinstance(v, dict) and "modes_Hz" in v})
    poles = run_wind(res, units, modal)
    print("Poles:", {k: round(v["f_Hz"], 1) for k, v in res["wind"]["poles"].items()})
    run_microphonics(res, modal, fgrid, poles)
    plot_wind(res, res["wind"]["poles"])
    run_shield(res, units)
    run_shock(res, models, amp_parts, psu_parts)
    res["assumptions"] = dict(materials=MAT, electrical=ELEC, site=SITE, wind=WIND, platecap=PCAP,
                              leads=LEADS, cg=CG, heavy_parts=HEAVY, solder=SOLDER, box_outer=BOX_OUT)
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(r3(res, 4), fh, indent=1, default=lambda o: r3(float(o)) if np.isscalar(o) else str(o))
    print("results.json written")
    return res


if __name__ == "__main__":
    main()
