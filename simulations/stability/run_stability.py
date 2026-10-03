#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA -- op-amp stability of the four amplifier stages (ngspice-42)

Circuits (PCB/antenna_amplifier/design.py):

  U301  LMP7715 unity-gain ADC driver -> 100 R -> VINL, 2.7 nF C0G to VCOM
  U202  LMP7715 guard buffer (senses IN-) -> 470 R -> guard, 20-200 pF
  U203  LMP7715 bias buffer -> 1 k -> ANT_BIAS -> (J202 shunt) -> IN_P, ~240 pF
  U201  LMP7721, G = 101: Rf 100k || Cf 15 nF, Rg 1k + Cg 100 uF to GND,
        input RC filter + 140 pF antenna on IN+, output C_out 10 uF film ->
        47k || (10k + 100 nF) (~8.5 k at HF)

Op-amp model (vendor models not available): two-pole behavioural
  A0 = 120 dB, GBW = 17 MHz, second pole FP2 = 40 / 60 / 80 MHz,
  open-loop output resistance RO = 50 / 100 / 200 Ohm,
  common-mode input capacitance CIN = 10 / 20 pF on each input,
  10 pF stray on every output pin.

For each case one ngspice run contains three copies of the stage:
  L_  loop broken inside the op-amp: the gm stage senses a 1 V AC test
      source instead of (IN+ - IN-); the return ratio is
      T = -(v(IN+) - v(IN-)) / v_test.  Exact for this model, because the
      model inputs draw no current other than through the explicit input
      capacitances, which stay in the circuit.
  S_  closed loop, 10 mV / 1 ns input step, real op-amp
  I_  closed loop, same step, ideal op-amp (GBW 10 GHz, RO 1 mOhm)
Overshoot = max(v_S - v_I) / step (so the slow Rg-Cf ramp of U201 and the
RC low-pass of the isolation resistors are not counted as overshoot).

Requirement: phase margin >= 45 deg in every corner.

Writes results.json, stability_bode.svg and stability_margins.svg.
"""

import itertools
import json
import os
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))

# Plot style (same palette as simulations/spice/run_spice.py)
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

# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------
A0 = 1e6
GBW = 17e6
FP2 = (40e6, 60e6, 80e6)
RO = (50.0, 100.0, 200.0)
CIN = (10e-12, 20e-12)
C_PIN = 10e-12           # stray on each op-amp output pin (trace + test point)
REQ_PM = 45.0
STEP = 10e-3
NOM = {"fp2": 60e6, "ro": 100.0, "cin": 10e-12}

STAGES = {
    "U301": {"title": "U301 ADC driver (100 R + 2.7 nF)", "loads": {"2.7 nF": 2.7e-9}, "riso": 100.0,
             "color": BLUE},
    "U202": {"title": "U202 guard buffer (470 R + C_guard)",
             "loads": {"20 pF": 20e-12, "50 pF": 50e-12, "100 pF": 100e-12, "200 pF": 200e-12,
                       # proposed fix: 220 pF C0G from GUARD to GND on top of the smallest guard C
                       "FIX (C205, as built): 20 pF + 220 pF C0G": 240e-12},
             "riso": 470.0, "color": PURPLE},
    "U203": {"title": "U203 bias buffer (1 k + input node)", "loads": {"240 pF": 240e-12, "500 pF": 500e-12},
             "riso": 1e3, "color": ORANGE},
    "U201": {"title": "U201 LMP7721 G = 101", "loads": {"C_out 10 uF + 8.5 k": None}, "riso": None,
             "color": GREEN},
}


# ---------------------------------------------------------------------------
# netlist
# ---------------------------------------------------------------------------
def opamp(tag, inp, inn, out, fp2, ro, cin, ctl=None, ideal=False):
    """Two-pole behavioural op-amp.  ctl = (p, n) nodes the gm stage senses."""
    gbw, f2, r_o = (10e9, 1e13, 1e-3) if ideal else (GBW, fp2, ro)
    cp, cn = ctl if ctl else (inp, inn)
    return f"""G{tag} 0 {tag}_x {cp} {cn} 1
R{tag}x {tag}_x 0 {A0:g}
C{tag}x {tag}_x 0 {1 / (2 * np.pi * gbw):.6g}
E{tag}2 {tag}_y 0 {tag}_x 0 1
R{tag}2 {tag}_y {tag}_z 1k
C{tag}2 {tag}_z 0 {1 / (2 * np.pi * 1e3 * f2):.6g}
E{tag}o {tag}_o 0 {tag}_z 0 1
R{tag}o {tag}_o {out} {r_o:g}
C{tag}p {inp} 0 {cin:g}
C{tag}n {inn} 0 {cin:g}
C{tag}s {out} 0 {C_PIN:g}
"""


def stage(stg, p, mode, load_c, riso):
    """Return netlist text for one copy.  mode: 'L' loop, 'S' step real, 'I' step ideal."""
    x = mode + "_"
    ctl = ("tst", "0") if mode == "L" else None
    ideal = mode == "I"
    drive = mode in ("S", "I")
    src = f"V{x}s {x}inp 0 dc 0 pwl(0 0 10n 0 11n {STEP})\n"
    if stg in ("U301", "U202", "U203"):
        # follower: IN- tied to the output pin, isolation resistor, capacitive load
        txt = opamp(x + "oa", f"{x}inp", f"{x}out", f"{x}out", p["fp2"], p["ro"], p["cin"], ctl, ideal)
        txt += f"R{x}iso {x}out {x}load {riso:g}\nC{x}l {x}load 0 {load_c:g}\n"
        if drive:
            txt += src
        elif stg == "U301":     # AA filter node: 10 k from the coupling node, 100 nF to VCOM
            txt += f"R{x}aa {x}inp {x}a 10k\nR{x}a {x}a 0 8.5k\nC{x}aa {x}inp 0 100n\n"
        elif stg == "U202":     # IN- of U201: ~1 k (Rg) to AC ground at HF
            txt += f"R{x}in {x}inp 0 1k\n"
        else:                   # bias divider node: 23.5 k || 4700 uF
            txt += f"R{x}dv {x}inp 0 23.5k\nC{x}dv {x}inp 0 4700u\n"
        return txt
    # U201 LMP7721, non-inverting G = 101
    txt = opamp(x + "oa", f"{x}inp", f"{x}inn", f"{x}out", p["fp2"], p["ro"], p["cin"], ctl, ideal)
    txt += (f"R{x}f {x}inn {x}out 100k\nC{x}f {x}inn {x}out 15n\n"
            f"R{x}g {x}inn {x}g 1k\nC{x}g {x}g 0 100u\n"
            f"C{x}u202 {x}inn 0 10p\n"                     # guard buffer input on IN-
            f"C{x}co {x}out {x}a 10u\nR{x}b {x}a 0 47k\nR{x}aa {x}a {x}f2 10k\nC{x}aa {x}f2 0 100n\n"
            f"C{x}u301 {x}f2 0 10p\n")
    if drive:
        txt += src
    else:   # input RC filter and antenna, J202 = 1 G to the bias buffer (AC ground)
        txt += (f"C{x}f2in {x}inp 0 50p\nR{x}3 {x}inp {x}n1 33k\nC{x}f1 {x}n1 0 50p\n"
                f"R{x}1 {x}n1 {x}ant 33k\nC{x}ant {x}ant 0 140p\nR{x}hb {x}inp 0 1G\n")
    return txt


def netlist(stg, p, load_c, riso, wd, t_end):
    return (f"* ELARA stability {stg} {p}\n"
            "Vtst tst 0 dc 0 ac 1\n"
            + stage(stg, p, "L", load_c, riso)
            + stage(stg, p, "S", load_c, riso)
            + stage(stg, p, "I", load_c, riso)
            + ".options reltol=1e-6 abstol=1e-15 vntol=1e-9\n"
            ".control\nset filetype=ascii\n"
            "ac dec 100 1 1e9\n"
            f"write {wd}/ac.raw v(l_inp) v(l_{'inn' if stg == 'U201' else 'out'})\n"
            f"tran 0.1n {t_end:g} 0 0.1n\n"
            f"write {wd}/tr.raw v(s_out) v(i_out) v(s_{'out' if stg == 'U201' else 'load'}) "
            f"v(i_{'out' if stg == 'U201' else 'load'})\n"
            "quit\n.endc\n.end\n")


def parse_raw(path):
    with open(path) as fh:
        lines = fh.read().splitlines()
    i = 0
    nv = npts = 0
    names = []
    cplx = False
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("Flags:"):
            cplx = "complex" in ln
        elif ln.startswith("No. Variables:"):
            nv = int(ln.split(":")[1])
        elif ln.startswith("No. Points:"):
            npts = int(ln.split(":")[1])
        elif ln.startswith("Variables:"):
            names = [lines[i + 1 + k].split()[1].lower() for k in range(nv)]
            i += nv
        elif ln.startswith("Values:"):
            i += 1
            break
        i += 1
    tok = " ".join(lines[i:]).split()
    arr = np.array(tok, dtype=object).reshape(npts, nv + 1)[:, 1:]
    out = {}
    for k, n in enumerate(names):
        col = arr[:, k]
        if cplx:
            v = np.array([complex(*map(float, c.split(","))) for c in col])
            out[n] = v.real if n == "frequency" else v
        else:
            out[n] = col.astype(float)
    return out


# ---------------------------------------------------------------------------
def margins(f, T):
    mag = np.abs(T)
    ph = np.unwrap(np.angle(T))
    ph -= 2 * np.pi * np.round(ph[0] / (2 * np.pi))
    ph = np.degrees(ph)
    idx = np.where((mag[:-1] >= 1) & (mag[1:] < 1))[0]
    if not len(idx):
        return None, None, None, ph
    k = idx[-1]
    fr = np.log10(f[k]) + (np.log10(f[k + 1]) - np.log10(f[k])) * (0 - np.log10(mag[k])) / \
        (np.log10(mag[k + 1]) - np.log10(mag[k]))
    fc = 10 ** fr
    pm = 180.0 + np.interp(fr, np.log10(f[k:k + 2]), ph[k:k + 2])
    j = np.where((ph[:-1] > -180) & (ph[1:] <= -180))[0]
    gm = float(-20 * np.log10(mag[j[0]])) if len(j) else None
    return float(fc), float(pm), gm, ph


def run_case(item):
    stg, load_name, p, riso = item
    load_c = STAGES[stg]["loads"][load_name]
    t_end = 3e-6
    with tempfile.TemporaryDirectory(prefix="elara_stab_") as wd:
        cir = os.path.join(wd, "c.cir")
        with open(cir, "w") as fh:
            fh.write(netlist(stg, p, load_c, riso, wd, t_end))
        r = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True, cwd=wd)
        if not os.path.exists(os.path.join(wd, "tr.raw")):
            raise RuntimeError(r.stdout[-2000:] + r.stderr[-2000:])
        ac = parse_raw(os.path.join(wd, "ac.raw"))
        tr = parse_raw(os.path.join(wd, "tr.raw"))
    f = ac["frequency"]
    inn = "v(l_inn)" if stg == "U201" else "v(l_out)"
    T = -(ac["v(l_inp)"] - ac[inn])
    fc, pm, gm, ph = margins(f, T)
    t = tr["time"]
    nl = "out" if stg == "U201" else "load"
    ov_pin = float(np.max(tr["v(s_out)"] - tr["v(i_out)"]) / STEP)
    ov_load = float(np.max(tr[f"v(s_{nl})"] - tr[f"v(i_{nl})"]) / STEP)
    res = {"stage": stg, "load": load_name, "riso": riso, **p, "fc_Hz": fc, "pm_deg": pm, "gm_dB": gm,
           "overshoot_pin_pct": 100 * ov_pin, "overshoot_load_pct": 100 * ov_load}
    keep = None
    if (p == NOM or p == WORSTP) and riso == STAGES[stg]["riso"] and load_name == list(STAGES[stg]["loads"])[0]:
        keep = {"f": f, "T": T, "ph": ph, "t": t, "s_out": tr["v(s_out)"], "i_out": tr["v(i_out)"],
                "s_load": tr[f"v(s_{nl})"], "i_load": tr[f"v(i_{nl})"]}
    return res, keep


WORSTP = {"fp2": 40e6, "ro": 200.0, "cin": 20e-12}


def jobs():
    out = []
    for stg, sd in STAGES.items():
        for load in sd["loads"]:
            for fp2, ro, cin in itertools.product(FP2, RO, CIN):
                out.append((stg, load, {"fp2": fp2, "ro": ro, "cin": cin}, sd["riso"]))
        # counterfactual: isolation resistor removed (information only)
        if sd["riso"] is not None:
            big = [ld for ld in sd["loads"] if not ld.startswith("FIX")][-1]
            for fp2, ro in itertools.product(FP2, RO):
                out.append((stg, big, {"fp2": fp2, "ro": ro, "cin": 10e-12}, 0.0))
    return out


# ---------------------------------------------------------------------------
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


def plot_bode(traces):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(14, 11), sharex=True)
    fig.patch.set_facecolor(BG)
    for ax in (a1, a2):
        style(ax)
    for (stg, load, tag), k in traces.items():
        col = STAGES[stg]["color"]
        ls = "-" if tag == "nominal" else "--"
        lab = f"{stg} {load}, {tag}"
        a1.semilogx(k["f"], 20 * np.log10(np.abs(k["T"])), color=col, ls=ls, lw=1.6 if ls == "-" else 1.1,
                    label=lab)
        a2.semilogx(k["f"], k["ph"], color=col, ls=ls, lw=1.6 if ls == "-" else 1.1, label=lab)
    a1.axhline(0, color=SUBTLE, lw=1)
    a1.set_ylim(-60, 130)
    a2.axhline(-180 + REQ_PM, color=RED, lw=1.2, ls=":", label=f"PM = {REQ_PM:.0f} deg")
    a2.axhline(-180, color=RED, lw=1)
    a2.set_ylim(-270, 90)
    a1.set_xlim(1, 1e9)
    labels(a1, "Loop gain |T| (return ratio at the op-amp gm stage)", "", "|T| (dB)")
    labels(a2, "Loop-gain phase", "frequency (Hz)", "phase (deg)")
    legend(a1, loc="lower left", ncol=2)
    legend(a2, loc="lower left", ncol=2)
    fig.suptitle("ELARA op-amp stages -- loop gain, nominal (FP2 60 MHz, RO 100 R, CIN 10 pF) "
                 "and worst (40 MHz, 200 R, 20 pF)", fontsize=12, fontweight="bold", color=TEXT,
                 fontfamily="monospace")
    plt.tight_layout()
    save(fig, "stability_bode.svg")


def plot_margins(rows, traces):
    fig = plt.figure(figsize=(16, 12))
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(2, 2)
    ax1 = fig.add_subplot(gs[0, :])
    axs = [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
    for ax in [ax1] + axs:
        style(ax)
    groups = []
    for stg, sd in STAGES.items():
        for load in sd["loads"]:
            groups.append((stg, load, sd["riso"], f"{stg} {load}"))
        if sd["riso"] is not None:
            big = [ld for ld in sd["loads"] if not ld.startswith("FIX")][-1]
            groups.append((stg, big, 0.0, f"{stg} {big}, NO R_iso (info)"))
    for i, (stg, load, riso, lab) in enumerate(groups):
        pms = [r["pm_deg"] for r in rows if r["stage"] == stg and r["load"] == load and r["riso"] == riso]
        nom = [r["pm_deg"] for r in rows if r["stage"] == stg and r["load"] == load and r["riso"] == riso
               and r["fp2"] == NOM["fp2"] and r["ro"] == NOM["ro"] and r["cin"] == NOM["cin"]]
        col = RED if min(pms) < REQ_PM else STAGES[stg]["color"]
        ax1.plot([min(pms), max(pms)], [i, i], color=col, lw=8, alpha=0.6, solid_capstyle="butt")
        if nom:
            ax1.plot(nom[0], i, "o", color=TEXT, ms=6)
        lab = f"{min(pms):.0f}..{max(pms):.0f} deg"
        if max(pms) < REQ_PM < max(pms) + 12:      # a label right of the bar would cross the 45 deg line
            ax1.text(min(pms) - 1, i, lab, va="center", ha="right", fontsize=8, color=TEXT,
                     fontfamily="monospace")
        else:
            ax1.text(max(pms) + 1, i, lab, va="center", fontsize=8, color=TEXT, fontfamily="monospace")
    ax1.set_yticks(range(len(groups)))
    ax1.set_yticklabels([g[3] for g in groups], fontsize=8, color=TEXT, fontfamily="monospace")
    ax1.invert_yaxis()
    ax1.axvline(REQ_PM, color=RED, lw=1.5, ls="--", label=f"requirement {REQ_PM:.0f} deg")
    ax1.plot([], [], "o", color=TEXT, label="nominal corner")
    ax1.set_xlim(0, 100)
    labels(ax1, "Phase margin over FP2 40-80 MHz, RO 50-200 R, CIN 10-20 pF", "phase margin (deg)", "")
    legend(ax1, loc="lower left")

    for (stg, load, tag), k in traces.items():
        if tag != "worst":
            continue
        col = STAGES[stg]["color"]
        tt = (k["t"] - 10e-9) * 1e9
        axs[0].plot(tt, k["s_out"] / STEP, color=col, lw=1.5, label=f"{stg} {load}")
        axs[1].plot(tt, (k["s_load"] - k["i_load"]) / STEP * 100, color=col, lw=1.5, label=f"{stg} {load}")
    axs[0].set_xlim(-20, 600)
    axs[0].set_ylim(-0.1, 1.5)
    labels(axs[0], "Step at op-amp output pin, worst corner", "time after step (ns)", "v_out / step")
    legend(axs[0], loc="lower right")
    axs[1].set_xlim(-20, 600)
    labels(axs[1], "Deviation from ideal op-amp at the load node, worst corner", "time after step (ns)",
           "(v - v_ideal) / step (%)")
    legend(axs[1], loc="upper right")
    fig.suptitle("ELARA op-amp stages -- phase margin and step response",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "stability_margins.svg")


def main():
    js = jobs()
    rows = []
    traces = {}
    with ProcessPoolExecutor(max_workers=4) as ex:
        for res, keep in ex.map(run_case, js):
            rows.append(res)
            if keep is not None:
                tag = "nominal" if all(res[k] == NOM[k] for k in NOM) else "worst"
                traces[(res["stage"], res["load"], tag)] = keep
    summary = {}
    for stg, sd in STAGES.items():
        rr = [r for r in rows if r["stage"] == stg and r["riso"] == sd["riso"] and not r["load"].startswith("FIX")]
        worst = min(rr, key=lambda r: r["pm_deg"])
        nom = [r for r in rr if all(r[k] == NOM[k] for k in NOM)]
        summary[stg] = {
            "title": sd["title"],
            "pm_nominal_deg": {r["load"]: r["pm_deg"] for r in nom},
            "fc_nominal_MHz": {r["load"]: r["fc_Hz"] / 1e6 for r in nom},
            "pm_min_deg": worst["pm_deg"],
            "pm_min_at": {k: worst[k] for k in ("load", "fp2", "ro", "cin")},
            "gm_min_dB": min(r["gm_dB"] for r in rr if r["gm_dB"] is not None),
            "overshoot_pin_max_pct": max(r["overshoot_pin_pct"] for r in rr),
            "overshoot_load_max_pct": max(r["overshoot_load_pct"] for r in rr),
            "pass_pm_45": worst["pm_deg"] >= REQ_PM,
        }
        fx = [r for r in rows if r["stage"] == stg and r["load"].startswith("FIX")]
        if fx:
            w = min(fx, key=lambda r: r["pm_deg"])
            summary[stg]["fix"] = {"load": w["load"], "pm_min_deg": w["pm_deg"],
                                   "overshoot_pin_max_pct": max(r["overshoot_pin_pct"] for r in fx),
                                   "pass_pm_45": w["pm_deg"] >= REQ_PM}
        cf = [r for r in rows if r["stage"] == stg and r["riso"] == 0.0]
        if cf:
            w = min(cf, key=lambda r: r["pm_deg"])
            summary[stg]["without_R_iso_pm_min_deg"] = w["pm_deg"]
            summary[stg]["without_R_iso_overshoot_pin_max_pct"] = max(r["overshoot_pin_pct"] for r in cf)
    results = {"meta": {"tool": "ngspice-42, behavioural two-pole op-amp",
                        "assumptions": {"A0_dB": 120, "GBW_Hz": GBW, "FP2_Hz": FP2, "RO_ohm": RO,
                                        "CIN_F": CIN, "C_pin_F": C_PIN, "step_V": STEP,
                                        "nominal": NOM, "worst": WORSTP},
                        "requirement": f"phase margin >= {REQ_PM} deg"},
               "summary": summary, "sweep": rows}
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(results, fh, indent=1)
    print("results.json written")
    plot_bode(traces)
    plot_margins(rows, traces)
    for stg, s in summary.items():
        # the board carries the fix where there is one (U202: C205, 220 pF C0G on GUARD)
        ok = s['fix']['pass_pm_45'] if 'fix' in s else s['pass_pm_45']
        tag = " (as built, with the fix)" if 'fix' in s else ""
        print(f"  {'PASS' if ok else 'FAIL'}  {stg}{tag}: PM nominal {s['pm_nominal_deg']}, "
              f"min {s['pm_min_deg']:.1f} deg at {s['pm_min_at']}, GM min {s['gm_min_dB']:.1f} dB, "
              f"overshoot pin {s['overshoot_pin_max_pct']:.1f} %, load {s['overshoot_load_max_pct']:.1f} %"
              + (f", without R_iso PM {s['without_R_iso_pm_min_deg']:.1f} deg"
                 if 'without_R_iso_pm_min_deg' in s else "")
              + (f", FIX {s['fix']}" if 'fix' in s else ""))


if __name__ == "__main__":
    main()
