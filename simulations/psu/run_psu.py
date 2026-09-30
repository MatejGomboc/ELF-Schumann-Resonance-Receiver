#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA -- verification of the "two-bucket" isolated PSU

Runs the ngspice transient model in psu_model.py (PCB/acdc_converter/design.py
+ the power sheet of PCB/antenna_amplifier/design.py) and post-processes it:

  1. Steady-state bucket sawtooth over several swap periods, relay transit
     (break-before-make 3 ms and 5 ms) and a both-on-load overlap case:
     LT3045 dropout margin and relay contact currents.
  2. Parameter corners (bucket C, ESR, load, LM317 dropout, IRM voltage).
  3. Swap/sawtooth artefact propagated through behavioural PSRR curves
     (LT3045 -> ADM7150 -> LMP7721 / bias divider) and compared with the
     receiver noise floor in 0.1 Hz and 1 Hz bins.
  4. Cold start from fully discharged buckets.
  5. Hold-up after mains failure (best and worst swap phase).
  6. 50 Hz leakage-current injection: direct IRM module vs two-bucket.

Writes results.json and four SVG plots next to this script.

Licence: CERN-OHL-W-2.0
"""

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import psu_model as pm  # noqa: E402

# ---------------------------------------------------------------------------
# Plot style (same palette as simulations/spice/run_spice.py)
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

SCHUMANN = [7.83, 14.3, 20.8, 27.3, 33.8, 39.0, 45.0]
SR_LABELS = ["SR1", "SR2", "SR3", "SR4", "SR5", "SR6", "SR7"]

# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------
REQ_RELAY_I = 1.0          # G6K-2F-Y rated carry / switching current (A)
VOUT_LT = pm.NOMINAL["VSETLT"]

# ---------------------------------------------------------------------------
# Behavioural PSRR / noise assumptions (datasheet-typical, see README)
# ---------------------------------------------------------------------------
PSRR = {
    # LT3045: SET-pin current line regulation dI_SET/dV_IN x R_SET, low-passed by
    # R_SET*C_SET, plus the error-amplifier floor rising towards 1 MHz
    "lt_iset_nA_per_V": 0.1,          # typ (bound 1 nA/V)
    "lt_floor_db": -115.0,            # 10 Hz..1 kHz (typ curve ~ -110..-120 dB)
    "lt_floor_zero_hz": 5e3,          # -> about -73 dB at 1 MHz
    # ADM7150: flat to ~30 kHz, -60 dB at 1 MHz
    "adm_db": -90.0,
    "adm_zero_hz": 30e3,
    # LMP7721 input-referred supply rejection at ELF (datasheet PSRR typ ~ 100 dB, low f)
    "lmp7721_db": -100.0,
    # LMP7715 (U301 ADC driver on +5VA) input-referred PSRR at ELF (datasheet typ ~ 100 dB;
    # 90 dB assumed), and the PCM1804 VCOM = VCC/2 path (assumed unfiltered, 0.5 V/V):
    # with VINL- tied to VCOM and VINL+ referenced to GND through C_out, VCOM ripple is
    # fully differential at the ADC input.  Both are referred to the antenna through the
    # antenna -> VINL gain (35.1 dB at SR1, simulations/spice).
    "lmp7715_db": -90.0,
    "vcom_frac": 0.5,
    "g_ant_vinl": 10 ** (35.1 / 20),
    # preamp rail filter 10 R into 22u + 10u + 4 x 100n on +5V_PRE
    "r_pre": 10.0, "c_pre": 32.4e-6,
    # bias divider 47k/47k + 4700u, into IN_P via the J202 resistor (worst: 1 G)
    "r_div": 23.5e3, "c_div": 4700e-6, "r_hb": 1e9, "c_node": 240e-12,
}
PSRR_SWEEP = {  # pessimistic bounds used for the robustness check
    "lt_iset_nA_per_V": 1.0, "lt_floor_db": -100.0, "adm_db": -66.0, "lmp7721_db": -75.0,
    "lmp7715_db": -70.0,
}
# LDO output-noise densities at 10 Hz (assumed 1/f^0.5 shape below the floor)
NOISE = {"lt_10Hz": 30e-9, "lt_floor": 2e-9, "adm_10Hz": 100e-9, "adm_floor": 1.7e-9}

# Receiver noise floor (simulations/spice/results.json, nominal build)
NOISE_ANT_SR1 = 45.8e-9
NOISE_INP_SR1 = 26.7e-9
CAP_DIV = 140.0 / 240.0


# ===========================================================================
# helpers
# ===========================================================================
def vdiff(d, a, b):
    return d[a] - d[b]


def bucket_v(d):
    return vdiff(d, "v(a_p)", "v(a_n)"), vdiff(d, "v(b_p)", "v(b_n)")


def lt_in(d):
    return vdiff(d, "v(load_p)", "v(rgnd)")


def lt_out(d):
    return vdiff(d, "v(vreg)", "v(rgnd)")


def lt_margin(d):
    """Headroom above LT3045 dropout: V_IN - V_SET - I*R_do (V)."""
    rdo = pm.NOMINAL["VDOLT"] / pm.NOMINAL["IDOLT"]
    return lt_in(d) - vdiff(d, "v(set)", "v(rgnd)") - rdo * np.maximum(d["i(vlt)"], 0)


def window(d, t0, t1):
    m = (d["time"] >= t0) & (d["time"] <= t1)
    return {k: v[m] for k, v in d.items() if isinstance(v, np.ndarray)}


def contact_peak(d):
    return {k: float(np.max(np.abs(d[k]))) for k in ("i(vk1nc)", "i(vk1no)", "i(vk2nc)", "i(vk2no)")}


SS_IC = {"va": 9.43, "vb": 10.61, "vres": 10.39, "vset": 8.45, "vreg": 8.45, "vp9": 8.10, "vchg": 10.03}
TH = pm.NOMINAL["THALF"]
N_SETTLE = 10           # half periods discarded (settling from the nominal ICs)
N_KEEP = 4              # half periods analysed (2 full periods)
T_SS = (N_SETTLE + N_KEEP) * TH + 0.05


def contact_avg_peak(d, tavg=1e-3):
    """Peak of the contact current averaged over a sliding 1 ms window (A).
    Separates sustained current from microsecond capacitor-discharge spikes."""
    t = d["time"]
    out = {}
    for k in ("i(vk1nc)", "i(vk1no)", "i(vk2nc)", "i(vk2no)"):
        a = np.abs(d[k])
        q = np.concatenate(([0.0], np.cumsum(0.5 * (a[1:] + a[:-1]) * np.diff(t))))
        m = t <= t[-1] - tavg
        out[k] = float(np.max((np.interp(t[m] + tavg, t, q) - q[m]) / tavg)) if m.any() else 0.0
    return out


def steady(params=None, relays=None, ic=None, tmax=20e-3):
    th = (params or {}).get("THALF", TH)
    t_ss = (N_SETTLE + N_KEEP) * th + 0.05
    d = pm.run(t_ss, tmax=tmax, p=params, relays=relays, ic=ic or SS_IC)
    w = window(d, N_SETTLE * th - 0.2, t_ss)
    va, vb = bucket_v(w)
    marg = lt_margin(w)
    k = np.argmin(marg)
    out = {
        "bucket_max_V": float(max(va.max(), vb.max())),
        "bucket_min_V": float(min(va.min(), vb.min())),
        "lt_in_min_V": float(lt_in(w).min()),
        "lt_in_max_V": float(lt_in(w).max()),
        "lt_margin_min_V": float(marg[k]),
        "lt_margin_min_at_s": float(w["time"][k]),
        "lt_out_min_V": float(lt_out(w).min()),
        "p5_min_V": float(vdiff(w, "v(p5)", "v(rgnd)").min()),
        "p9_min_V": float(vdiff(w, "v(p9)", "v(rgnd)").min()),
        "contact_peak_A": contact_peak(w),
        "charger_I_end_of_phase_A": float(np.interp(t_ss - 0.3, d["time"], d["i(vchg)"])),
        "half_period_s": th,
    }
    out["contact_peak_max_A"] = max(out["contact_peak_A"].values())
    out["contact_1ms_avg_peak_max_A"] = max(contact_avg_peak(w).values())
    out["solver"] = d.get("_options", "")
    # periodicity check: bucket extremes in the last vs the previous full period
    w2 = window(d, (N_SETTLE + 2) * th, t_ss)
    w1 = window(d, N_SETTLE * th, (N_SETTLE + 2) * th)
    out["settled_dV_V"] = float(abs(lt_in(w2).min() - lt_in(w1).min()))
    out["lt_dropout"] = bool(out["lt_margin_min_V"] < 0)
    return out, d


# ---------------------------------------------------------------------------
WORST = {"CB": 2.0, "RESRB": 0.30, "ILOAD5": 50e-3, "ILOAD33": 56e-3, "VDO0": 1.85, "VIRM": 14.7}
T5 = {"K1": {"transit": 5e-3}, "K2": {"transit": 5e-3}}
FIX_V = {"RSET": 75.0e3, "VSETLT": 7.5}
FIX_D = {"RSET": 69.8e3, "VSETLT": 6.98}
CASES_SS = {
    "nominal (3 ms transit)": {},
    "transit 5 ms": {"relays": T5},
    # K1 faster than K2 on operate, K2 faster than K1 on release: the arriving bucket
    # makes before the leaving bucket breaks -> both buckets on LOAD_P for 2.5 ms
    "overlap: both on load 2.5 ms": {"relays": {
        "K1": {"op_break": 0.5e-3, "transit": 1.0e-3, "rel_break": 4.0e-3},
        "K2": {"op_break": 4.0e-3, "transit": 1.0e-3, "rel_break": 0.5e-3}}},
    "C_bucket 2.0 F (-20 %)": {"params": {"CB": 2.0}},
    "C_bucket 3.0 F (+20 %)": {"params": {"CB": 3.0}},
    "ESR 30 mOhm/cell": {"params": {"RESRB": 0.12}},
    "ESR 75 mOhm/cell": {"params": {"RESRB": 0.30}},
    "load +25 % (50/56 mA)": {"params": {"ILOAD5": 50e-3, "ILOAD33": 56e-3}},
    "LM317 dropout +0.3 V (cold)": {"params": {"VDO0": 1.85}},
    "IRM output 14.7 V (-2 %)": {"params": {"VIRM": 14.7}},
    "worst corner": {"params": dict(WORST), "relays": T5},
    "FIX A: LT3045 7.5 V, nominal": {"params": dict(FIX_V)},
    "FIX A: LT3045 7.5 V, worst corner": {"params": dict(WORST, **FIX_V), "relays": T5},
    "FIX B: 7.5 V + 4 x 25 F cells, worst corner (5.0 F)": {
        "params": dict(WORST, **FIX_V, CB=5.0), "relays": T5},
    # FIX C: no new parts -- R_SET 84.5k -> 75.0k and swap every 15 s
    # (CD4060 Rt 160k -> 80.6k, or take Q13 (pin 2) instead of Q14 (pin 3))
    "FIX C: 7.5 V + 15 s swap, nominal": {"params": dict(FIX_V, THALF=15.05)},
    "FIX C: 7.5 V + 15 s swap, worst corner": {"params": dict(WORST, **FIX_V, THALF=15.05), "relays": T5},
    # FIX D: FIX C with R_SET 69.8k (6.98 V); ADM7150 inputs still >= 6.4 V (1.4 V headroom)
    "FIX D: 7.0 V + 15 s swap, nominal": {"params": dict(FIX_D, THALF=15.05)},
    "FIX D: 7.0 V + 15 s swap, worst corner": {"params": dict(WORST, **FIX_D, THALF=15.05), "relays": T5},
}


def _run_ss(item):
    name, spec = item
    p = spec.get("params")
    ic = dict(SS_IC)
    if p and "VSETLT" in p:
        ic["vset"] = p["VSETLT"]
        ic["vreg"] = p["VSETLT"]
        ic["vp9"] = p["VSETLT"] - 0.35
        p = {k: v for k, v in p.items() if k != "VSETLT"}
    res, d = steady(p, spec.get("relays"), ic)
    keep = None
    if name in ("nominal (3 ms transit)", "overlap: both on load 2.5 ms", "transit 5 ms",
                "worst corner", "FIX B: 7.5 V + 4 x 25 F cells, worst corner (5.0 F)",
                "FIX C: 7.5 V + 15 s swap, worst corner", "FIX D: 7.0 V + 15 s swap, worst corner"):
        keep = {k: d[k] for k in ("time", "v(a_p)", "v(a_n)", "v(b_p)", "v(b_n)", "v(load_p)",
                                  "v(rgnd)", "v(vreg)", "v(set)", "v(p5)", "i(vk1nc)", "i(vk1no)",
                                  "i(vk2nc)", "i(vk2no)", "i(vlt)", "i(vchg)", "v(chg)")}
    return name, res, keep


def _run_cold(which):
    ic = {"va": 0.0, "vb": 0.0, "vres": 0.0, "vset": 0.0, "vreg": 0.0, "vp9": 0.0, "vchg": 0.0}
    if which == "design":
        d = pm.run(1500.0, tmax=50e-3, ic=ic)
    else:
        d = pm.run(1500.0, tmax=50e-3, ic=ic, p={"RSET": 69.8e3, "THALF": 15.05})
    return which, d


def _run_hold(which):
    # coil ON phases: [30.1, 60.2], [90.3, 120.4], [150.5, 180.6] ...
    t_fail = 150.5 + 0.5 if which == "worst" else 180.6 - 0.5
    d = pm.run(t_fail + 200.0, tmax=50e-3, ic=SS_IC, t_fail=t_fail)
    return which, (t_fail, d)


# ===========================================================================
# PSRR chain (frequency domain)
# ===========================================================================
def h_lt(f, a=PSRR):
    k_iset = a["lt_iset_nA_per_V"] * 1e-9 * pm.NOMINAL["RSET"]
    f_set = 1.0 / (2 * np.pi * pm.NOMINAL["RSET"] * pm.NOMINAL["CSET"])
    kf = 10 ** (a["lt_floor_db"] / 20)
    s = 1j * f
    return k_iset / (1 + s / f_set) + kf * (1 + s / a["lt_floor_zero_hz"]) / (1 + s / 10e6)


def h_adm(f, a=PSRR):
    return 10 ** (a["adm_db"] / 20) * (1 + 1j * f / a["adm_zero_hz"]) / (1 + 1j * f / 10e6)


def h_pre(f, a=PSRR):
    return 1.0 / (1 + 1j * 2 * np.pi * f * a["r_pre"] * a["c_pre"])


def h_to_inp(f, a=PSRR):
    """+5V_PRE -> equivalent voltage at LMP7721 IN+ (op-amp PSRR + bias divider path)."""
    w = 2 * np.pi * f
    k = 10 ** (a["lmp7721_db"] / 20)
    div = 0.5 / (1 + 1j * w * a["r_div"] * a["c_div"])
    hb = 1.0 / (1 + 1j * w * a["r_hb"] * a["c_node"])
    return np.abs(k) + np.abs(div * hb)      # worst case: add magnitudes


def h_adc_path(f, a=PSRR):
    """+5VA -> antenna-equivalent voltage via the ADC driver PSRR and the VCOM path."""
    k = 10 ** (a["lmp7715_db"] / 20) + a["vcom_frac"]
    return k / a["g_ant_vinl"] * np.ones_like(np.asarray(f, dtype=float))


def artefact_spectrum(d, fs=4000.0):
    """Uniformly resample LT3045 input over exactly 2 full periods, return FFT."""
    t0 = N_SETTLE * TH
    t1 = t0 + N_KEEP * TH
    n = int(round((t1 - t0) * fs))
    t = t0 + np.arange(n) / fs
    x = np.interp(t, d["time"], lt_in(d))
    X = np.fft.rfft(x) / n
    X[1:] *= 2                    # single-sided peak amplitudes
    f = np.fft.rfftfreq(n, 1 / fs)
    return t, x, f, X


def binned_density(f, amp, bw, fmax=100.0):
    """Sum line powers (rms^2 = amp^2/2) inside bins of width bw, return equivalent density."""
    edges = np.arange(0.0, fmax + bw, bw)
    p = (np.abs(amp) ** 2) / 2
    idx = np.digitize(f, edges) - 1
    out = np.zeros(len(edges) - 1)
    for k in range(len(out)):
        out[k] = p[(idx == k) & (f > 0)].sum()
    centres = edges[:-1] + bw / 2
    return centres, np.sqrt(out / bw)


def ldo_noise(f):
    e_lt = np.sqrt(NOISE["lt_floor"] ** 2 + NOISE["lt_10Hz"] ** 2 * 10 / f)
    e_adm = np.sqrt(NOISE["adm_floor"] ** 2 + NOISE["adm_10Hz"] ** 2 * 10 / f)
    rail = np.sqrt((e_lt * np.abs(h_adm(f))) ** 2 + e_adm ** 2) * np.abs(h_pre(f))
    return e_lt, e_adm, rail


# ===========================================================================
# 50 Hz leakage injection
# ===========================================================================
def leakage():
    w = 2 * np.pi * 50.0
    res = {}
    # (a) receiver powered directly from an IRM module
    for cb in (50e-12, 100e-12):
        for vcm, lab in ((115.0, "V_L/2"), (230.0, "V_L")):
            res[f"direct IRM, C_barrier {cb*1e12:.0f} pF, source {lab}"] = {
                "C_eff_pF": cb * 1e12, "V_src_rms": vcm, "I_rms_A": w * cb * vcm}
    # (b1) two-bucket as designed: GND_C bonded to PE -> source is the PE potential
    #      relative to the receiver's earth; coupling = open contacts + coil + PCB
    for cx in (2e-12, 10e-12):
        for vpe in (0.3, 3.0):
            res[f"two-bucket, GND_C=PE, C_x {cx*1e12:.0f} pF, V_PE {vpe:g} V"] = {
                "C_eff_pF": cx * 1e12, "V_src_rms": vpe, "I_rms_A": w * cx * vpe}
    # receiver-side circuit inside the PE-bonded PSU box (C to box, assumed 30 pF)
    res["two-bucket, receiver side to PE box 30 pF, V_PE 3 V"] = {
        "C_eff_pF": 30.0, "V_src_rms": 3.0, "I_rms_A": w * 30e-12 * 3.0}
    # (b2) GND_C left floating (no PE bond): C_x in series with the module barrier
    for cx in (2e-12, 10e-12):
        cb = 100e-12
        ce = cx * cb / (cx + cb)
        res[f"two-bucket, GND_C floating, C_x {cx*1e12:.0f} pF + 100 pF barrier, V_L/2"] = {
            "C_eff_pF": ce * 1e12, "V_src_rms": 115.0, "I_rms_A": w * ce * 115.0}
    # ground bounce: (i) receiver earthed via stake + lead, R_e = 10..100 Ohm
    #                (ii) receiver floating: C_stray to earth 300 pF (enclosure, cables)
    #                     in parallel with the antenna path C_ant in series with the
    #                     100 pF of filter capacitors (58 pF)
    c_ant_path = 140e-12 * 100e-12 / 240e-12
    for k, v in res.items():
        v["Vg_earthed_10R_V"] = v["I_rms_A"] * 10
        v["Vg_earthed_100R_V"] = v["I_rms_A"] * 100
        ce = v["C_eff_pF"] * 1e-12
        v["Vg_floating_300pF_V"] = v["V_src_rms"] * ce / (ce + 300e-12 + c_ant_path)
    return res


def ground_bounce_to_input(c_ant=140e-12, c_filt=100e-12):
    """Receiver GND moving by V_g w.r.t. earth appears at IN+ as -V_g*C_ant/(C_ant+C_f),
    i.e. exactly like an antenna EMF of -V_g (the signal sees the same divider)."""
    return c_ant / (c_ant + c_filt)


# ===========================================================================
# plotting helpers
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


def sr_markers(ax, ytext=None, fs=6):
    for lab, fx in zip(SR_LABELS, SCHUMANN):
        ax.axvline(fx, color=SUBTLE, alpha=0.3, linestyle="--", linewidth=0.8)
        if ytext is not None:
            ax.text(fx, ytext, lab, fontsize=fs, ha="center", va="bottom", color=SUBTLE,
                    fontfamily="monospace")


def save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("Plot saved:", path)


# ===========================================================================
def main():
    results = {"meta": {"tool": "ngspice-42 (batch), behavioural models",
                        "source": "PCB/acdc_converter/design.py, PCB/antenna_amplifier/design.py",
                        "nominal_params": pm.NOMINAL, "relay_timing_s": pm.RELAY_NOMINAL,
                        "psrr_assumptions": PSRR, "psrr_pessimistic": PSRR_SWEEP,
                        "ldo_noise_assumptions": NOISE}}
    jobs_ss = list(CASES_SS.items())
    with ProcessPoolExecutor(max_workers=4) as ex:
        fut_ss = [ex.submit(_run_ss, j) for j in jobs_ss]
        fut_cold = [ex.submit(_run_cold, w) for w in ("design", "fix D")]
        fut_hold = [ex.submit(_run_hold, w) for w in ("worst", "best")]
        ss = {}
        keep = {}
        for fu in fut_ss:
            name, res, k = fu.result()
            ss[name] = res
            if k is not None:
                keep[name] = k
            print(f"  {name:40s} margin {res['lt_margin_min_V']:+.3f} V  "
                  f"bucket {res['bucket_min_V']:.2f}..{res['bucket_max_V']:.2f} V  "
                  f"contact {res['contact_peak_max_A']:.3f} A")
        colds = dict(fu.result() for fu in fut_cold)
        hold = dict(fu.result() for fu in fut_hold)
    results["steady_state"] = ss

    # ---- verdicts on the sawtooth -------------------------------------------
    single = [k for k in ss if not (k.startswith("worst") or k.startswith("FIX"))]
    results["verdict_sawtooth"] = {
        "LT3045 never drops out (nominal)": not ss["nominal (3 ms transit)"]["lt_dropout"],
        "LT3045 never drops out (every single-parameter corner)": all(not ss[k]["lt_dropout"] for k in single),
        "LT3045 never drops out (worst corner, as designed)": not ss["worst corner"]["lt_dropout"],
        "LT3045 never drops out (worst corner, FIX A 7.5 V)": not ss["FIX A: LT3045 7.5 V, worst corner"]["lt_dropout"],
        "LT3045 never drops out (worst corner, FIX B 7.5 V + 25 F cells)":
            not ss["FIX B: 7.5 V + 4 x 25 F cells, worst corner (5.0 F)"]["lt_dropout"],
        "LT3045 never drops out (FIX C nominal, 7.5 V + 15 s swap)":
            not ss["FIX C: 7.5 V + 15 s swap, nominal"]["lt_dropout"],
        "LT3045 never drops out (worst corner, FIX C 7.5 V + 15 s swap)":
            not ss["FIX C: 7.5 V + 15 s swap, worst corner"]["lt_dropout"],
        "LT3045 never drops out (FIX D nominal, 7.0 V + 15 s swap)":
            not ss["FIX D: 7.0 V + 15 s swap, nominal"]["lt_dropout"],
        "LT3045 never drops out (worst corner, FIX D 7.0 V + 15 s swap)":
            not ss["FIX D: 7.0 V + 15 s swap, worst corner"]["lt_dropout"],
        "relay contacts < 1 A, steady state (all cases, instantaneous)":
            all(v["contact_peak_max_A"] < REQ_RELAY_I for v in ss.values()),
    }

    # ---- swap transient details (nominal and overlap) ------------------------
    swap_detail = {}
    for name in ("nominal (3 ms transit)", "transit 5 ms", "overlap: both on load 2.5 ms"):
        d = keep[name]
        ts = (N_SETTLE + 1) * TH      # a coil ON edge (A to load)
        w = window(d, ts - 0.01, ts + 0.2)
        vin = lt_in(w)
        pre = float(np.interp(ts - 0.005, d["time"], lt_in(d)))
        swap_detail[name] = {
            "lt_in_before_swap_V": pre,
            "lt_in_dip_min_V": float(vin.min()),
            "lt_in_after_swap_V": float(np.interp(ts + 0.2, d["time"], lt_in(d))),
            "reservoir_inrush_peak_A": float(max(np.abs(w["i(vk1no)"]).max(), np.abs(w["i(vk2nc)"]).max())),
            "bucket_to_bucket_peak_A": float(min(np.abs(w["i(vk1no)"]).max(), np.abs(w["i(vk2nc)"]).max())),
        }
    results["swap_transient"] = swap_detail

    # ---- artefact spectrum ---------------------------------------------------
    spec = {}
    spec_plot = {}
    for name in ("nominal (3 ms transit)", "overlap: both on load 2.5 ms"):
        t, x, f, X = artefact_spectrum(keep[name])
        spec_plot[name] = (t, x, f, X)
    t, x, f, X = spec_plot["nominal (3 ms transit)"]
    fpos = np.maximum(f, 1e-6)
    stages = {}
    for tag, a in (("typ", PSRR), ("pessimistic", dict(PSRR, **PSRR_SWEEP))):
        y_lt = X * h_lt(fpos, a)
        y_adm = y_lt * h_adm(fpos, a)
        y_pre = y_adm * h_pre(fpos, a)
        y_inp = np.abs(y_pre) * h_to_inp(fpos, a)
        y_ant_pre = y_inp / CAP_DIV
        y_ant_adc = np.abs(y_adm) * h_adc_path(fpos, a)
        y_ant = y_ant_pre + y_ant_adc          # worst case: add magnitudes
        stages[tag] = {"lt_in": X, "lt_out": y_lt, "adm_out": y_adm, "inp": y_inp, "ant": y_ant,
                       "ant_pre": y_ant_pre, "ant_adc": y_ant_adc}
        rows = {}
        for bw in (0.1, 1.0):
            fc, dens = binned_density(f, y_ant, bw)
            fc_in, dens_in = binned_density(f, X, bw)
            fc_lo, dens_lo = binned_density(f, y_lt, bw)
            fc_ad, dens_ad = binned_density(f, y_adm, bw)
            band = (fc >= 1) & (fc <= 50)
            rows[f"bin_{bw:g}Hz"] = {
                "max_in_1_50Hz_at_antenna_nV_per_rtHz": float(dens[band].max() * 1e9),
                "max_in_1_50Hz_lt_in_uV_per_rtHz": float(dens_in[band].max() * 1e6),
                "max_in_1_50Hz_lt_out_nV_per_rtHz": float(dens_lo[band].max() * 1e9),
                "max_in_1_50Hz_adm_out_pV_per_rtHz": float(dens_ad[band].max() * 1e12),
                "margin_below_receiver_noise_dB": float(20 * np.log10(NOISE_ANT_SR1 * 0.9 / dens[band].max())),
            }
        spec[tag] = rows
    # time-domain: LT3045 and ADM7150 output deviation around the swap
    Yl = np.fft.irfft(np.r_[stages["typ"]["lt_out"][0], stages["typ"]["lt_out"][1:] / 2] * len(t), n=len(t))
    Ya = np.fft.irfft(np.r_[stages["typ"]["adm_out"][0], stages["typ"]["adm_out"][1:] / 2] * len(t), n=len(t))
    spec["time_domain_typ"] = {
        "lt_out_pp_uV": float((Yl.max() - Yl.min()) * 1e6),
        "adm_out_pp_nV": float((Ya.max() - Ya.min()) * 1e9),
        "lt_in_pp_V": float(x.max() - x.min()),
    }
    # LDO noise referred to the preamp input, for the system budget
    fn = np.array(SCHUMANN)
    e_lt, e_adm, rail = ldo_noise(fn)
    rail_5va = np.sqrt((e_lt * np.abs(h_adm(fn))) ** 2 + e_adm ** 2)
    inp_typ = rail * h_to_inp(fn, PSRR)
    inp_pes = rail * h_to_inp(fn, dict(PSRR, **PSRR_SWEEP))
    ant_typ = inp_typ / CAP_DIV + rail_5va * h_adc_path(fn, PSRR)
    ant_pes = inp_pes / CAP_DIV + rail_5va * h_adc_path(fn, dict(PSRR, **PSRR_SWEEP))
    spec["ldo_noise_input_referred"] = {
        "rail_5V_PRE_nV_per_rtHz": dict(zip([str(v) for v in SCHUMANN], (rail * 1e9).tolist())),
        "at_IN_P_typ_nV_per_rtHz": dict(zip([str(v) for v in SCHUMANN], (inp_typ * 1e9).tolist())),
        "at_IN_P_pessimistic_nV_per_rtHz": dict(zip([str(v) for v in SCHUMANN], (inp_pes * 1e9).tolist())),
        "at_antenna_incl_ADC_VCOM_path_typ_nV_per_rtHz": dict(zip([str(v) for v in SCHUMANN], (ant_typ * 1e9).tolist())),
        "at_antenna_incl_ADC_VCOM_path_pessimistic_nV_per_rtHz":
            dict(zip([str(v) for v in SCHUMANN], (ant_pes * 1e9).tolist())),
    }
    results["artefact_spectrum"] = spec
    results["verdict_artefact"] = {
        "swap artefact below receiver noise in 1-50 Hz (typ PSRR)":
            spec["typ"]["bin_0.1Hz"]["margin_below_receiver_noise_dB"] > 0,
        "swap artefact below receiver noise in 1-50 Hz (pessimistic PSRR)":
            spec["pessimistic"]["bin_0.1Hz"]["margin_below_receiver_noise_dB"] > 0,
    }

    # ---- cold start ------------------------------------------------------------
    results["cold_start"] = {}
    for which, cold in colds.items():
        tc = cold["time"]
        vset_final = vdiff(cold, "v(set)", "v(rgnd)")[-1]
        reg_ok = (lt_margin(cold) >= 0) & (lt_out(cold) >= 0.99 * vset_final)
        adm_ok = (vdiff(cold, "v(p5)", "v(rgnd)") >= 4.99) & (vdiff(cold, "v(p9)", "v(rgnd)") >= 5.5)

        def first_and_last_bad(ok):
            first = float(tc[np.argmax(ok)]) if ok.any() else None
            bad = np.where(~ok)[0]
            if not len(bad):
                return first, 0.0
            return first, (float(tc[bad[-1] + 1]) if bad[-1] + 1 < len(tc) else None)

        f_lt, c_lt = first_and_last_bad(reg_ok)
        f_adm, c_adm = first_and_last_bad(adm_ok)
        cp = contact_peak(window(cold, 1.0, tc[-1]))
        cpa = contact_avg_peak(window(cold, 1.0, tc[-1]))
        results["cold_start"][which] = {
            "first_LT3045_in_regulation_s": f_lt, "LT3045_continuously_in_regulation_from_s": c_lt,
            "first_ADM7150_rails_valid_s": f_adm, "ADM7150_rails_continuously_valid_from_s": c_adm,
            "contact_peak_A": cp, "contact_peak_max_A": max(cp.values()),
            "contact_1ms_avg_peak_max_A": max(cpa.values()),
            "simulated_s": float(tc[-1]), "solver": cold.get("_options", ""),
        }
    results["verdict_sawtooth"]["relay contacts < 1 A, cold start (instantaneous)"] = all(
        v["contact_peak_max_A"] < REQ_RELAY_I for v in results["cold_start"].values())
    results["verdict_sawtooth"]["relay contacts < 1 A, cold start (1 ms average)"] = all(
        v["contact_1ms_avg_peak_max_A"] < REQ_RELAY_I for v in results["cold_start"].values())
    results["cold_start"]["note"] = ("Relay timer starts with the coil off; first swap at 30.1 s. "
                                     "'Valid' ADM7150 rails = +5VA >= 4.99 V and amplifier input >= 5.5 V. "
                                     "'fix D' = LT3045 at 7.0 V (R_SET 69.8k) and 15 s swap half-period. "
                                     "contact_1ms_avg = sliding 1 ms average (sustained current); the "
                                     "instantaneous peak is the 10 uF charger capacitor discharging into an "
                                     "empty bucket through 2.2 R (tens of us).")

    # ---- hold-up ---------------------------------------------------------------
    hu = {}
    for which, (tf, d) in hold.items():
        m = d["time"] >= tf
        tt = d["time"][m] - tf
        marg = lt_margin(d)[m]
        p9 = vdiff(d, "v(p9)", "v(rgnd)")[m]
        p5 = vdiff(d, "v(p5)", "v(rgnd)")[m]
        t_lt = float(tt[np.argmax(marg < 0)]) if (marg < 0).any() else None
        t_adm = float(tt[np.argmax((p5 < 4.99) | (p9 < 5.5))]) if ((p5 < 4.99) | (p9 < 5.5)).any() else None
        hu[which] = {"t_fail_s": tf, "LT3045_regulates_for_s": t_lt, "ADM7150_rails_valid_for_s": t_adm,
                     "bucket_on_load_at_fail_V": float(np.interp(tf + 0.05, d["time"],
                                                                 vdiff(d, "v(b_p)", "v(b_n)")))}
    results["hold_up"] = hu

    # ---- leakage -----------------------------------------------------------------
    lk = leakage()
    results["leakage_50Hz"] = {"cases": lk,
                               "ground_bounce_to_IN_P_factor": ground_bounce_to_input(),
                               "note": "A ground bounce V_g appears at the input exactly like an antenna "
                                       "EMF of -V_g (same capacitive divider as the signal)."}

    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=float)
    print("results.json written")

    plot_sawtooth(keep, ss)
    plot_spectrum(spec_plot, stages, f, Yl, Ya, t)
    plot_start_hold(colds['design'], hold)
    plot_leakage(lk)
    print_summary(results)


# ===========================================================================
def plot_sawtooth(keep, ss):
    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor(BG)
    for ax in axs.flat:
        style(ax)
    ax1, ax2, ax3, ax4 = axs.flat
    d = keep["nominal (3 ms transit)"]
    va, vb = bucket_v(d)
    t = d["time"]
    ax1.plot(t, va, color=BLUE, lw=1.6, label="bucket A")
    ax1.plot(t, vb, color=PURPLE, lw=1.6, label="bucket B")
    ax1.plot(t, lt_in(d), color=GREEN, lw=1.4, label="LT3045 input (LOAD_P)")
    lim = vdiff(d, "v(set)", "v(rgnd)") + 3.0 * np.maximum(d["i(vlt)"], 0)
    ax1.plot(t, lim, color=RED, lw=1.2, ls="--", label="LT3045 dropout limit (8.45 V + 0.3 V)")
    ax1.plot(t, lt_out(d), color=YELLOW, lw=1.2, label="LT3045 output")
    dw = keep["worst corner"]
    ax1.plot(dw["time"], lt_in(dw), color=ORANGE, lw=1.0, ls=":", label="LT3045 input, worst corner")
    ax1.set_xlim(N_SETTLE * TH - 5, T_SS)
    ax1.set_ylim(7.5, 11.2)
    labels(ax1, "Bucket sawtooth, steady state (nominal)", "time (s)", "voltage (V)")
    legend(ax1, loc="lower left")

    ts = (N_SETTLE + 1) * TH
    for name, col in (("nominal (3 ms transit)", GREEN), ("transit 5 ms", YELLOW),
                      ("overlap: both on load 2.5 ms", RED)):
        dd = keep[name]
        m = (dd["time"] > ts - 0.01) & (dd["time"] < ts + 0.06)
        ax2.plot((dd["time"][m] - ts) * 1e3, lt_in(dd)[m], color=col, lw=1.6, label=name)
    ax2.axhline(8.45 + 0.285, color=RED, lw=1, ls="--", label="dropout limit")
    labels(ax2, "Swap transient at LT3045 input (coil ON edge)", "time after coil edge (ms)", "LOAD_P (V)")
    legend(ax2, loc="lower right")

    for name, ls in (("nominal (3 ms transit)", "-"), ("overlap: both on load 2.5 ms", "--")):
        dd = keep[name]
        m = (dd["time"] > ts - 0.005) & (dd["time"] < ts + 0.05)
        tt = (dd["time"][m] - ts) * 1e3
        tag = "nom" if ls == "-" else "overlap"
        ax3.plot(tt, np.abs(dd["i(vk1no)"][m]), color=BLUE, lw=1.5, ls=ls, label=f"K1 NO (A -> load), {tag}")
        ax3.plot(tt, np.abs(dd["i(vk2nc)"][m]), color=PURPLE, lw=1.5, ls=ls, label=f"K2 NC (B leaving load), {tag}")
        ax3.plot(tt, np.abs(dd["i(vk2no)"][m]), color=ORANGE, lw=1.2, ls=ls, label=f"K2 NO (B -> charger), {tag}")
    ax3.axhline(REQ_RELAY_I, color=RED, lw=1, ls=":", label="G6K rating 1 A")
    ax3.set_ylim(0, 1.1)
    labels(ax3, "Relay contact currents during the swap", "time after coil edge (ms)", "|I| (A)")
    legend(ax3, loc="upper right")

    names = list(ss.keys())
    marg = [ss[n]["lt_margin_min_V"] for n in names]
    cols = [RED if m < 0 else (YELLOW if m < 0.2 else GREEN) for m in marg]
    y = np.arange(len(names))
    ax4.barh(y, marg, color=cols, alpha=0.85, edgecolor=BORDER)
    ax4.set_yticks(y)
    ax4.set_yticklabels(names, fontsize=8, color=TEXT, fontfamily="monospace")
    ax4.invert_yaxis()
    ax4.axvline(0, color=RED, lw=1)
    for yi, m in zip(y, marg):
        ax4.text(m + (0.02 if m >= 0 else -0.02), yi, f"{m:+.2f} V", va="center",
                 ha="left" if m >= 0 else "right", fontsize=8, color=TEXT, fontfamily="monospace")
    ax4.set_xlim(min(-0.6, min(marg) - 0.25), max(marg) + 0.4)
    labels(ax4, "Minimum LT3045 headroom above dropout", "V_IN - (V_OUT + V_DO)  (V)", "")
    fig.suptitle("ELARA two-bucket PSU -- sawtooth, relay transit and dropout margin",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "psu_sawtooth.svg")


def plot_spectrum(spec_plot, stages, f, Yl, Ya, t):
    fig = plt.figure(figsize=(16, 13))
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1])
    ax1 = fig.add_subplot(gs[0, :])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[1, 1])
    for ax in (ax1, ax2, ax3):
        style(ax)
    fb = None
    for key, col, lab in (("lt_in", GREY, "LT3045 input (bucket sawtooth + swap step)"),
                          ("lt_out", BLUE, "LT3045 output"),
                          ("adm_out", PURPLE, "ADM7150 +5VA output"),
                          ("ant", GREEN, "input-referred, at antenna (typ PSRR)")):
        fb, dens = binned_density(f, stages["typ"][key], 0.1)
        ax1.loglog(fb, dens, color=col, lw=1.5, label=lab)
    fb, dens = binned_density(f, stages["pessimistic"]["ant"], 0.1)
    ax1.loglog(fb, dens, color=ORANGE, lw=1.2, ls="--", label="input-referred, pessimistic PSRR")
    ax1.axhline(NOISE_ANT_SR1, color=RED, lw=1.5, ls=":", label="receiver noise at antenna ~46 nV/rtHz")
    ax1.axvspan(1, 50, color=GREEN, alpha=0.05)
    sr_markers(ax1, ytext=1e-21)
    ax1.set_xlim(0.05, 100)
    ax1.set_ylim(1e-21, 10)
    labels(ax1, "Swap artefact spectrum along the supply chain (0.1 Hz bins, equivalent density)",
           "frequency (Hz)", "V/rtHz (line power per bin / bin width)")
    legend(ax1, loc="upper right")

    ts = (N_SETTLE + 1) * TH
    m = (t > ts - 0.05) & (t < ts + 0.3)
    ax2.plot((t[m] - ts) * 1e3, (Yl[m] - np.median(Yl)) * 1e6, color=BLUE, lw=1.5, label="LT3045 output (uV)")
    ax2.plot((t[m] - ts) * 1e3, (Ya[m] - np.median(Ya)) * 1e9, color=PURPLE, lw=1.5, label="ADM7150 output (nV)")
    labels(ax2, "Swap step after the regulators (typ PSRR)", "time after coil edge (ms)", "deviation (uV / nV)")
    legend(ax2, loc="upper right")

    fg = np.logspace(-3, 6, 600)
    ax3.semilogx(fg, 20 * np.log10(np.abs(h_lt(fg))), color=BLUE, lw=1.8, label="LT3045 (typ)")
    ax3.semilogx(fg, 20 * np.log10(np.abs(h_lt(fg, dict(PSRR, **PSRR_SWEEP)))), color=BLUE, lw=1, ls="--",
                 label="LT3045 (pessimistic)")
    ax3.semilogx(fg, 20 * np.log10(np.abs(h_adm(fg))), color=PURPLE, lw=1.8, label="ADM7150 (typ)")
    ax3.semilogx(fg, 20 * np.log10(np.abs(h_adm(fg, dict(PSRR, **PSRR_SWEEP)))), color=PURPLE, lw=1, ls="--",
                 label="ADM7150 (pessimistic)")
    ax3.semilogx(fg, 20 * np.log10(h_to_inp(fg)), color=GREEN, lw=1.8, label="+5V_PRE -> IN+ (LMP7721 + bias path)")
    ax3.set_ylim(-170, -40)
    labels(ax3, "Behavioural PSRR curves (assumed)", "frequency (Hz)", "transfer (dB)")
    legend(ax3, loc="upper left")
    fig.suptitle("ELARA two-bucket PSU -- is the swap visible in the ELF band?",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "psu_artefact_spectrum.svg")


def plot_start_hold(cold, hold):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
    fig.patch.set_facecolor(BG)
    for ax in (ax1, ax2):
        style(ax)
    va, vb = bucket_v(cold)
    t = cold["time"]
    ax1.plot(t, va, color=BLUE, lw=1.2, label="bucket A")
    ax1.plot(t, vb, color=PURPLE, lw=1.2, label="bucket B")
    ax1.plot(t, lt_out(cold), color=YELLOW, lw=1.5, label="LT3045 output")
    ax1.plot(t, vdiff(cold, "v(p5)", "v(rgnd)"), color=GREEN, lw=1.5, label="ADM7150 +5VA")
    ax1.axhline(8.45 + 0.3, color=RED, lw=1, ls="--", label="LT3045 needs 8.75 V")
    labels(ax1, "Cold start from fully discharged buckets", "time (s)", "voltage (V)")
    legend(ax1, loc="lower right")
    for which, col in (("worst", RED), ("best", GREEN)):
        tf, d = hold[which]
        m = d["time"] >= tf - 5
        tt = d["time"][m] - tf
        ax2.plot(tt, lt_in(d)[m], color=col, lw=1.6, label=f"LT3045 input, {which} phase")
        ax2.plot(tt, lt_out(d)[m], color=col, lw=1.0, ls="--", label=f"LT3045 output, {which} phase")
        ax2.plot(tt, vdiff(d, "v(p5)", "v(rgnd)")[m], color=col, lw=1.0, ls=":", label=f"+5VA, {which} phase")
    ax2.axhline(8.45 + 0.3, color=YELLOW, lw=1, ls="--", label="LT3045 dropout limit")
    ax2.axvline(0, color=SUBTLE, lw=1)
    labels(ax2, "Hold-up after mains failure at t = 0", "time after mains failure (s)", "voltage (V)")
    legend(ax2, loc="upper right")
    fig.suptitle("ELARA two-bucket PSU -- cold start and hold-up",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "psu_startup_holdup.svg")


def _clip_level():
    """Max 50 Hz antenna EMF before clipping, from simulations/system (fallback 21 mV rms)."""
    try:
        with open(os.path.join(HERE, "..", "system", "results.json")) as fh:
            return json.load(fh)["headroom_50Hz"]["max_input_50Hz_V_rms"]
    except (OSError, KeyError, ValueError):
        return 21e-3


CLIP_50HZ = _clip_level()


def plot_leakage(lk):
    fig, ax = plt.subplots(1, 1, figsize=(16, 9))
    fig.patch.set_facecolor(BG)
    style(ax)
    names = list(lk.keys())
    y = np.arange(len(names))
    v10 = np.array([lk[n]["Vg_earthed_10R_V"] for n in names])
    v100 = np.array([lk[n]["Vg_earthed_100R_V"] for n in names])
    vfl = np.array([lk[n]["Vg_floating_300pF_V"] for n in names])
    ax.barh(y - 0.25, v100, height=0.25, color=ORANGE, alpha=0.85, label="earthed receiver, R_e = 100 Ohm")
    ax.barh(y, v10, height=0.25, color=YELLOW, alpha=0.85, label="earthed receiver, R_e = 10 Ohm")
    ax.barh(y + 0.25, vfl, height=0.25, color=RED, alpha=0.6, label="floating receiver, 300 pF + 58 pF antenna path to earth")
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8, color=TEXT, fontfamily="monospace")
    ax.invert_yaxis()
    refs = ((5e-3, RED, "mains pickup 5 mV"), (1e-3, ORANGE, "mains pickup 1 mV"),
            (CLIP_50HZ, PURPLE, f"50 Hz clip level {CLIP_50HZ*1e3:.0f} mV rms (simulations/system)"), (1.95e-6, GREEN, "quiet SR1, 1 Hz bin (1.95 uV)"),
            (46e-9 * np.sqrt(0.1), BLUE, "receiver noise, 0.1 Hz bin"))
    for v, c, lab in refs:
        ax.axvline(v, color=c, lw=1.2, ls="--", label=lab)
    ax.set_xlim(1e-12, 100)
    labels(ax, "50 Hz ground bounce of the receiver (= equivalent antenna EMF, V rms)", "V rms at 50 Hz", "")
    legend(ax, loc="lower right")
    plt.tight_layout()
    save(fig, "psu_leakage.svg")


def print_summary(r):
    print("\n==== PSU summary ====")
    for k, v in r["verdict_sawtooth"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    for k, v in r["verdict_artefact"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print("  swap:", json.dumps(r["swap_transient"], indent=1))
    print("  artefact:", json.dumps({k: r["artefact_spectrum"][k] for k in ("typ", "pessimistic", "time_domain_typ")}, indent=1))
    print("  cold start:", r["cold_start"])
    print("  hold-up:", r["hold_up"])


if __name__ == "__main__":
    main()
