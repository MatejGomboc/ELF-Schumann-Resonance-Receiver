#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
ELARA -- end-to-end receiver budget: antenna -> PCM1804

Frequency-domain nodal model of the whole analogue chain
(PCB/antenna_amplifier/design.py):

  EMF --C_ant 140p-- ANT --R1 33k-- N1 --R3 33k-- IN_P --> LMP7721 (G = 101)
                           Cf1 50p        Cf2 50p |-- J202 R_hb -> BIAS_BUF (U203, 1 k)
                                                  |-- R_leak (noiseless), PCB leakage noise
  LMP7721: Rf 100k || Cf 15n, Rg 1k + Cg 100u to GND
  PREAMP_OUT --C_out 10u-- ADC_A --R_AA 10k-- VINL_F --> U301 LMP7715 x1 --100 R-- VINL
                           R_bias 47k to VCOM   C_AA 100n to VCOM          2.7 nF to VCOM
  PCM1804: VINL+ = VINL, VINL- = VCOML (single-ended drive), 5 Vpp differential FS

Every noise source is propagated to the ADC input (VINL - VCOM) and referred
back to the antenna EMF through the signal gain.  The front-end part is
cross-checked against simulations/spice (ngspice, 45.8 nV/rtHz at SR1).

Outputs: results.json, system_budget.svg (summary figure).
"""

import json
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))

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

kT = 1.380649e-23 * 300.0
Q_E = 1.602176634e-19
SCHUMANN = [7.83, 14.3, 20.8, 27.3, 33.8, 39.0, 45.0]
SR_LABELS = ["SR1", "SR2", "SR3", "SR4", "SR5", "SR6", "SR7"]

# ---------------------------------------------------------------------------
# Circuit (design.py) and assumptions
# ---------------------------------------------------------------------------
CKT = dict(C_ANT=140e-12, R1=33e3, R3=33e3, CF1=50e-12, CF2=50e-12, R_LEAK=1e12,
           RF=100e3, CFB=15e-9, RG=1e3, CG=100e-6, GBW=17e6, A0=1e6,
           C_OUT=10e-6, R_BIAS=47e3, R_AA=10e3, C_AA=100e-9, R_ISO=100.0, C_RES=2.7e-9,
           R_BUF=1e3, V_BIAS=2.5, VCC=5.0)
A = dict(
    en_oa=6.5e-9, fc_oa=10.0,          # LMP7721 e_n (same as simulations/spice)
    in_oa=0.01e-15,                    # LMP7721 i_n
    i_pcb=0.1e-15,                     # guarded PCB leakage current noise (PLAN 3.3)
    en_715=5.8e-9, fc_715=30.0,        # LMP7715 (U203, U301): 5.8 nV/rtHz, 1/f corner 30 Hz (assumed)
    adc_dr_db=112.0,                   # PCM1804 dynamic range, A-weighted, 20 kHz BW
    adc_aw_penalty_db=2.0,             # unweighted noise is ~2 dB worse than A-weighted
    adc_bw=20e3,                       # bandwidth the DR figure refers to
    adc_fc=0.0,                        # 1/f corner of the modulator (not specified; 0 nominal)
    vcom_10hz=50e-9,                   # PCM1804 VCOML noise at 10 Hz (1/f^0.5 shape, assumed)
    vref_rel_10hz=1e-6 / 4.0,          # VREF noise / VREF at 10 Hz (multiplicative, assumed)
    swing_margin=0.05,                 # rail-to-rail output: within 50 mV of the rails
    cmvr_715_top=1.0,                  # LMP7715 input CM range: up to V+ - 1.0 V (datasheet-typ, verify)
    cmvr_7721_top=1.2,                 # LMP7721 input CM range: up to V+ - 1.2 V (assumed, verify)
    ib_7721=20e-15,                    # LMP7721 input bias, worst over temperature (typ 3 fA)
    adc_fs_pk=2.5,                     # PCM1804 FS: 5 Vpp differential -> +-2.5 V on VINL+ alone
)
PESSIMISTIC = dict(fc_715=100.0, adc_dr_db=106.0, adc_fc=100.0, vcom_10hz=500e-9)
R_HB = {"1 G": 1e9, "10 G": 10e9, "100 G": 100e9, "1 T": 1e12}
I_ATM = {"0 (insulated)": 0.0, "1 pA": 1e-12, "10 pA": 10e-12, "100 pA": 100e-12}
MAINS = (1e-3, 5e-3)

# expected signal (simulations/signal_chain/expected_signal.py)
H_EFF = 6.5
SR_Q = [4.5, 5.0, 6.0, 6.5, 7.0, 7.0, 7.5]
E_QUIET = [0.3e-6, 0.15e-6, 0.10e-6, 0.07e-6, 0.05e-6, 0.04e-6, 0.03e-6]
E_TYPICAL = [1.0e-6, 0.5e-6, 0.35e-6, 0.25e-6, 0.18e-6, 0.13e-6, 0.10e-6]
E_FLOOR = 0.05e-6
BINS = (0.1, 1.0)


def e_field(f, peaks):
    """Amplitude density (V/m/rtHz): Lorentzian peaks on the background floor (expected_signal.py)."""
    out = np.full_like(f, E_FLOOR)
    for f0, q, e in zip(SCHUMANN, SR_Q, peaks):
        lor = 1.0 / (1.0 + ((f - f0) / (f0 / q / 2)) ** 2)
        out = np.maximum(out, e * lor + E_FLOOR)
    return out


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
def chain(f, r_hb, a=A, c=CKT):
    """Return the signal gains and every noise contribution at the ADC input (V/rtHz)."""
    f = np.asarray(f, dtype=float)
    w = 2 * np.pi * f
    s = 1j * w
    n = len(f)
    # --- input network: nodes ANT, N1, IN_P ---
    g1, g3 = 1 / c["R1"], 1 / c["R3"]
    ghb = 0.0 if r_hb is None else 1 / r_hb
    Y = np.zeros((n, 3, 3), dtype=complex)
    Y[:, 0, 0] = s * c["C_ANT"] + g1
    Y[:, 0, 1] = Y[:, 1, 0] = -g1
    Y[:, 1, 1] = g1 + g3 + s * c["CF1"]
    Y[:, 1, 2] = Y[:, 2, 1] = -g3
    Y[:, 2, 2] = g3 + s * c["CF2"] + ghb + 1 / c["R_LEAK"]
    Z = np.linalg.inv(Y)
    h_in = Z[:, 2, 0] * s * c["C_ANT"]                    # EMF -> IN_P
    z_inp = Z[:, 2, 2]
    # --- preamp ---
    zf = c["RF"] / (1 + s * c["RF"] * c["CFB"])
    zg = c["RG"] + 1 / (s * c["CG"])
    g_ideal = 1 + zf / zg
    aol = c["A0"] / (1 + s * c["A0"] / (2 * np.pi * c["GBW"]))
    g_pre = g_ideal / (1 + g_ideal / aol)
    # --- coupling + AA: nodes ADC_A, VINL_F (VCOM = AC reference) ---
    Y2 = np.zeros((n, 2, 2), dtype=complex)
    Y2[:, 0, 0] = s * c["C_OUT"] + 1 / c["R_BIAS"] + 1 / c["R_AA"]
    Y2[:, 0, 1] = Y2[:, 1, 0] = -1 / c["R_AA"]
    Y2[:, 1, 1] = 1 / c["R_AA"] + s * c["C_AA"]
    Z2 = np.linalg.inv(Y2)
    h_aa = Z2[:, 1, 0] * s * c["C_OUT"]                   # PREAMP_OUT -> VINL_F
    h_iso = 1 / (1 + s * c["R_ISO"] * c["C_RES"])          # U301 x1, 100 R + 2.7 nF
    h_post = h_aa * h_iso                                 # PREAMP_OUT -> VINL
    h_ant = h_in * g_pre * h_post                         # EMF -> VINL
    h_ant_out = h_in * g_pre
    h_ant_f = h_in * g_pre * h_aa

    def en(e, fc):
        return e * np.sqrt(1 + fc / f)

    g_inp = np.abs(g_pre * h_post)                         # IN_P -> VINL
    nz = {}
    nz["R1 33k (input filter)"] = np.sqrt(4 * kT / c["R1"]) * np.abs(Z[:, 2, 0] - Z[:, 2, 1]) * g_inp
    nz["R3 33k (input filter)"] = np.sqrt(4 * kT / c["R3"]) * np.abs(Z[:, 2, 1] - Z[:, 2, 2]) * g_inp
    nz["PCB leakage 0.1 fA"] = a["i_pcb"] * np.abs(z_inp) * g_inp
    nz["LMP7721 e_n"] = en(a["en_oa"], a["fc_oa"]) * g_inp
    nz["LMP7721 i_n"] = a["in_oa"] * np.abs(z_inp) * g_inp
    if r_hb is not None:
        nz["J202 R_hb thermal"] = np.sqrt(4 * kT / r_hb) * np.abs(z_inp) * g_inp
        # bias buffer U203 (e_n + 1 k) and the divider (47k||47k, 4700 uF) reach IN_P through R_hb
        e_div = np.sqrt(4 * kT * 23.5e3) / np.abs(1 + s * 23.5e3 * 4700e-6)
        e_buf = np.sqrt(en(a["en_715"], a["fc_715"]) ** 2 + 4 * kT * c["R_BUF"] + e_div ** 2)
        nz["U203 bias buffer via R_hb"] = e_buf / r_hb * np.abs(z_inp) * g_inp
    nz["Rg 1k"] = np.sqrt(4 * kT * c["RG"]) * np.abs(zf / zg) * np.abs(h_post)
    nz["Rf 100k"] = np.sqrt(4 * kT / c["RF"]) * np.abs(zf) * np.abs(h_post)
    nz["R_bias 47k + R_AA 10k"] = np.sqrt(
        (np.sqrt(4 * kT / c["R_BIAS"]) * np.abs(Z2[:, 1, 0])) ** 2
        + (np.sqrt(4 * kT / c["R_AA"]) * np.abs(Z2[:, 1, 0] - Z2[:, 1, 1])) ** 2) * np.abs(h_iso)
    nz["U301 driver e_n + 100 R"] = np.sqrt((en(a["en_715"], a["fc_715"]) * np.abs(h_iso)) ** 2
                                            + 4 * kT * c["R_ISO"] * np.abs(1 - h_iso) ** 2)
    # VINL+ = VCOM + h_post (V_out - VCOM) and VINL- = VCOM, so the differential ADC input
    # contains -h_post * v_com: at ELF (|h_post| ~ 1) VCOM noise is fully differential
    nz["PCM1804 VCOM (single-ended drive)"] = a["vcom_10hz"] * np.sqrt(10 / f) * np.abs(h_post)
    fs_rms = 2 * a["adc_fs_pk"] / np.sqrt(2)
    e_adc_w = fs_rms * 10 ** (-(a["adc_dr_db"] - a["adc_aw_penalty_db"]) / 20) / np.sqrt(a["adc_bw"])
    nz["PCM1804 modulator/quantisation"] = en(e_adc_w, a["adc_fc"])
    # VREF noise multiplies the signal: evaluate with 5 mV mains at 50 Hz on the input
    v_mains_adc = 5e-3 * np.abs(np.interp(50.0, f, np.abs(h_ant))) if f.min() < 50 < f.max() else 0.25
    # (sideband of the 50 Hz line: reference noise at |50 - f| Hz lands at f)
    nz["PCM1804 VREF x 5 mV mains"] = (a["vref_rel_10hz"] * np.sqrt(10 / np.maximum(np.abs(50 - f), 0.1))
                                       * v_mains_adc / np.sqrt(2))
    tot = np.sqrt(sum(v ** 2 for v in nz.values()))
    return {"h_in": h_in, "g_pre": g_pre, "h_ant": h_ant, "h_ant_out": h_ant_out, "h_ant_f": h_ant_f,
            "noise_adc": nz, "total_adc": tot, "z_inp": z_inp}


def refer(res):
    g = np.abs(res["h_ant"])
    return {k: v / g for k, v in res["noise_adc"].items()}, res["total_adc"] / g


def dc_offset(r_hb, i_in, r_leak=CKT["R_LEAK"]):
    """DC voltage at IN_P: V_BIAS through R_hb against R_leak to GND, plus I x (R_hb || R_leak)."""
    rp = r_hb * r_leak / (r_hb + r_leak)
    return CKT["V_BIAS"] * r_leak / (r_hb + r_leak) + i_in * rp


def headroom(v_inp_dc, a=A):
    """Max 50 Hz antenna EMF (V rms) before any stage clips; limits per stage."""
    r = chain(np.array([50.0]), 1e11, a)
    g_out = abs(r["h_ant_out"][0])
    g_f = abs(r["h_ant_f"][0])
    g_vinl = abs(r["h_ant"][0])
    vcc = CKT["VCC"]
    lim = {}
    lim["LMP7721 output swing"] = max(0.0, min(vcc - a["swing_margin"] - v_inp_dc,
                                               v_inp_dc - a["swing_margin"])) / g_out / np.sqrt(2)
    lim["LMP7721 input CM range (DC)"] = np.inf if (-0.3 <= v_inp_dc <= vcc - a["cmvr_7721_top"]) else 0.0
    lim["U301 input CM range"] = (vcc - a["cmvr_715_top"] - CKT["V_BIAS"]) / g_f / np.sqrt(2)
    lim["U301 output swing"] = (vcc - a["swing_margin"] - CKT["V_BIAS"]) / g_vinl / np.sqrt(2)
    lim["PCM1804 full scale"] = a["adc_fs_pk"] / g_vinl / np.sqrt(2)
    k = min(lim, key=lim.get)
    return lim[k], k, lim, {"ant_to_out": g_out, "ant_to_vinl_f": g_f, "ant_to_vinl": g_vinl}


def snr_bins(f0, q, e_pk, noise_fn, bw):
    # resonance only (as expected_signal.py): the 0.05 uV/m background is natural noise, not signal
    ff = np.linspace(f0 - bw / 2, f0 + bw / 2, 201)
    sig = (H_EFF * e_pk / (1.0 + ((ff - f0) / (f0 / q / 2)) ** 2)) ** 2
    nse = noise_fn(ff) ** 2
    ps, pn = np.trapezoid(sig, ff), np.trapezoid(nse, ff)
    return 10 * np.log10(ps / pn), np.sqrt(ps), np.sqrt(pn)


# ---------------------------------------------------------------------------
def style(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=SUBTLE, labelsize=9)
    ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
    for sp in ax.spines.values():
        sp.set_color(BORDER)


def labels(ax, title, xl, yl):
    ax.set_title(title, fontsize=12, fontweight="bold", color=TEXT, fontfamily="monospace", pad=8)
    ax.set_xlabel(xl, fontsize=10, color=TEXT, fontfamily="monospace")
    ax.set_ylabel(yl, fontsize=10, color=TEXT, fontfamily="monospace")


def legend(ax, loc="best", **kw):
    lg = ax.legend(loc=loc, fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT, **kw)
    lg.get_frame().set_alpha(0.9)


def main():
    fsr = np.array(SCHUMANN)
    f = np.logspace(np.log10(0.5), 2, 800)
    res = {"meta": {"model": "frequency-domain nodal analysis (numpy), front end cross-checked with ngspice",
                    "circuit": CKT, "assumptions": A, "pessimistic": PESSIMISTIC,
                    "signal_model": "simulations/signal_chain/expected_signal.py: h_eff 6.5 m, Lorentzian SR "
                                    "peaks, 0.05 uV/m/rtHz background"}}

    # ---- cross-check with ngspice (no R_hb, R_leak 1 T) ----------------------
    r0 = chain(fsr, None)
    _, t0 = refer(r0)
    sp_path = os.path.join(HERE, "..", "spice", "results.json")
    xc = {"python_antenna_nV": dict(zip(map(str, SCHUMANN), (t0 * 1e9).round(2).tolist())),
          "python_gain_vinl_dB": dict(zip(map(str, SCHUMANN), (20 * np.log10(np.abs(r0["h_ant"]))).round(3).tolist()))}
    try:
        with open(sp_path) as fh:
            sp = json.load(fh)
        xc["ngspice_antenna_nV"] = sp["bias_resistor"]["none (R_leak 1T)"]["noise_antenna_nV"]
        xc["ngspice_gain_vinl_dB"] = sp["nominal"]["ac"]["gain_vinl_db_at_SR"]
    except (OSError, KeyError):
        pass
    res["crosscheck_vs_spice"] = xc

    # ---- J202 sweep ----------------------------------------------------------------
    sweep = {}
    curves = {}
    for name, rhb in R_HB.items():
        rr = chain(fsr, rhb)
        parts, tot = refer(rr)
        rp = chain(fsr, rhb, dict(A, **PESSIMISTIC))
        _, tot_p = refer(rp)
        rf = chain(f, rhb)
        _, curve = refer(rf)
        curves[name] = curve
        fe = np.sqrt(sum(parts[k] ** 2 for k in parts if k.startswith(("R1", "R3", "PCB", "LMP7721", "Rg", "Rf"))))
        post = np.sqrt(sum(parts[k] ** 2 for k in parts if k.startswith(("R_bias", "U301", "PCM1804"))))
        ent = {"R_hb_ohm": rhb,
               "highpass_at_IN_P_Hz": 1 / (2 * np.pi * rhb * (CKT["C_ANT"] + CKT["CF1"] + CKT["CF2"])),
               "noise_antenna_nV": dict(zip(SR_LABELS, (tot * 1e9).round(2).tolist())),
               "noise_antenna_pessimistic_nV": dict(zip(SR_LABELS, (tot_p * 1e9).round(2).tolist())),
               "noise_amp_input_nV": dict(zip(SR_LABELS, (tot * np.abs(rr["h_in"]) * 1e9).round(2).tolist())),
               "breakdown_antenna_nV": {k: dict(zip(SR_LABELS, (v * 1e9).round(3).tolist())) for k, v in parts.items()},
               "front_end_only_nV": dict(zip(SR_LABELS, (fe * 1e9).round(2).tolist())),
               "post_preamp_incl_ADC_nV": dict(zip(SR_LABELS, (post * 1e9).round(3).tolist())),
               "gain_ant_to_vinl_dB": dict(zip(SR_LABELS, (20 * np.log10(np.abs(rr["h_ant"]))).round(2).tolist()))}
        # DC operating point and 50 Hz headroom
        dc = {}
        for iname, ia in I_ATM.items():
            v = dc_offset(rhb, ia + A["ib_7721"])
            vmax, lim_by, lims, gains = headroom(v)
            dc[iname] = {"V_IN_P_dc": v, "max_50Hz_input_mV_rms": vmax * 1e3, "limited_by": lim_by,
                         "headroom_1mV_dB": 20 * np.log10(vmax / 1e-3) if vmax > 0 else None,
                         "headroom_5mV_dB": 20 * np.log10(vmax / 5e-3) if vmax > 0 else None,
                         "pass_5mV_mains": bool(vmax > 5e-3)}
        ent["dc_and_headroom"] = dc
        # SNR
        snr = {}
        for cond, peaks in (("quiet", E_QUIET), ("typical", E_TYPICAL)):
            snr[cond] = {}
            for bw in BINS:
                row = {}
                for lab, f0, q, e in zip(SR_LABELS, SCHUMANN, SR_Q, peaks):
                    val, s_rms, n_rms = snr_bins(f0, q, e, lambda x, _r=rhb: refer(chain(x, _r))[1], bw)
                    row[lab] = {"snr_dB": round(float(val), 2), "signal_uV_rms": float(s_rms * 1e6),
                                "noise_uV_rms": float(n_rms * 1e6)}
                snr[cond][f"bin_{bw:g}Hz"] = row
        ent["snr"] = snr
        sweep[name] = ent
    res["j202_sweep"] = sweep

    # ---- headroom, nominal (100 G, insulated antenna) --------------------------------
    vdc = dc_offset(100e9, A["ib_7721"])
    vmax, lim_by, lims, gains = headroom(vdc)
    vmax_rr, lim_rr, lims_rr, _ = headroom(vdc, dict(A, cmvr_715_top=-10.0))   # RRIO driver
    res["headroom_50Hz"] = {"max_input_50Hz_V_rms": vmax, "limited_by": lim_by,
                            "limits_V_rms": lims, "gains_at_50Hz": gains,
                            "headroom_over_1mV_dB": 20 * np.log10(vmax / 1e-3),
                            "headroom_over_5mV_dB": 20 * np.log10(vmax / 5e-3),
                            "with_RRIO_driver_V_rms": vmax_rr, "with_RRIO_driver_limited_by": lim_rr,
                            "cmvr_sweep_V_rms": {f"V+ - {t:.1f} V": headroom(vdc, dict(A, cmvr_715_top=t))[0]
                                                 for t in (0.8, 1.0, 1.3)}}
    bg = H_EFF * E_FLOOR * 1e9
    res["natural_background_at_antenna_nV"] = bg
    res["requirements_per_J202"] = {
        name: {"background-limited: noise >= 6 dB below the natural ELF background (325 nV/rtHz), SR1..SR7":
               all(v <= bg / 2 for v in e["noise_antenna_nV"].values()),
               "DC point valid (no clipping of 5 mV mains) at I_atm = 0 / 1 / 10 / 100 pA":
               {k: v["pass_5mV_mains"] for k, v in e["dc_and_headroom"].items()},
               "margin_below_background_SR1_dB": 20 * np.log10(bg / e["noise_antenna_nV"]["SR1"])}
        for name, e in sweep.items()}
    res["requirements"] = {
        "post-preamp (driver + ADC + VCOM + REF) >= 10 dB below front end at SR1..SR7":
            all(sweep["100 G"]["post_preamp_incl_ADC_nV"][k] < sweep["100 G"]["front_end_only_nV"][k] / np.sqrt(10)
                for k in SR_LABELS),
        "5 mV rms 50 Hz mains fits with >= 6 dB headroom (J202 100 G, insulated antenna)": res["headroom_50Hz"]["headroom_over_5mV_dB"] >= 6,
        "quiet SR1..SR3 SNR >= 10 dB in 1 Hz bins (100 G)":
            all(sweep["100 G"]["snr"]["quiet"]["bin_1Hz"][k]["snr_dB"] >= 10 for k in ("SR1", "SR2", "SR3")),
        "typical SR1..SR7 SNR >= 10 dB in 1 Hz bins (100 G)":
            all(v["snr_dB"] >= 10 for v in sweep["100 G"]["snr"]["typical"]["bin_1Hz"].values()),
    }
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    print("results.json written")
    plot(f, curves, sweep, res)
    print("cross-check (antenna nV/rtHz):", xc.get("python_antenna_nV"), xc.get("ngspice_antenna_nV"))
    for k, v in res["requirements"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    for k, v in res["requirements_per_J202"].items():
        print("  J202", k, v)
    print("headroom:", {k: v for k, v in res["headroom_50Hz"].items() if k != "gains_at_50Hz"})
    for name, e in sweep.items():
        print(name, "SR1..7 nV:", list(e["noise_antenna_nV"].values()),
              "SNR quiet 1Hz:", [e["snr"]["quiet"]["bin_1Hz"][k]["snr_dB"] for k in SR_LABELS],
              "typ:", [e["snr"]["typical"]["bin_1Hz"][k]["snr_dB"] for k in SR_LABELS])
        print("    dc:", {k: (round(v["V_IN_P_dc"], 3), round(v["max_50Hz_input_mV_rms"], 1), v["limited_by"])
                          for k, v in e["dc_and_headroom"].items()})


def plot(f, curves, sweep, res):
    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor(BG)
    for ax in axs.flat:
        style(ax)
    ax1, ax2, ax3, ax4 = axs.flat
    cols = {"1 G": RED, "10 G": ORANGE, "100 G": GREEN, "1 T": BLUE}
    ax1.loglog(f, H_EFF * e_field(f, E_TYPICAL) * 1e9, color=YELLOW, lw=2, label="signal, typical (day)")
    ax1.loglog(f, H_EFF * e_field(f, E_QUIET) * 1e9, color=PURPLE, lw=2, label="signal, quiet (night)")
    for name, c in curves.items():
        ax1.loglog(f, c * 1e9, color=cols[name], lw=1.5, ls="--", label=f"receiver noise, J202 = {name}")
    _, t_none = refer(chain(f, None))
    ax1.loglog(f, t_none * 1e9, color=GREY, lw=1, ls=":", label="receiver noise, no R_hb (ngspice ref.)")
    for lab, fx in zip(SR_LABELS, SCHUMANN):     # tags on the bottom edge, lines start above them
        ax1.axvline(fx, ymin=0.06, color=SUBTLE, alpha=0.3, ls="--", lw=0.8)
        ax1.text(fx, 0.012, lab, fontsize=7, ha="center", va="bottom", color=SUBTLE, fontfamily="monospace",
                 transform=ax1.get_xaxis_transform())
    ax1.set_xlim(0.5, 100)
    ax1.set_ylim(10, 2e4)
    labels(ax1, "Input-referred noise vs expected signal (at antenna EMF)", "frequency (Hz)", "nV/rtHz")
    legend(ax1, loc="upper right")

    e = sweep["100 G"]["breakdown_antenna_nV"]
    keys = sorted(e, key=lambda k: -e[k]["SR1"])
    x = np.arange(len(SR_LABELS))
    palette = [GREEN, BLUE, PURPLE, ORANGE, YELLOW, RED, GREY, "#56d4dd", "#e3b341", "#f778ba", "#a5d6ff",
               "#ffdfb6", "#bc8cff", "#3fb950"]
    for i, k in enumerate(keys):
        ax2.semilogy(x, [e[k][s] for s in SR_LABELS], marker="o", ls="-" if i < 7 else "--",
                     color=palette[i % 7], lw=1.2, ms=4, label=k)
    ax2.semilogy(x, list(sweep["100 G"]["noise_antenna_nV"].values()), "s-", color=TEXT, lw=2.2, ms=6,
                 label="total")
    ax2.set_xticks(x)
    ax2.set_xticklabels(SR_LABELS, color=TEXT, fontfamily="monospace")
    ax2.set_ylim(1e-7, 200)     # room under the lowest trace for the legend
    labels(ax2, "Noise breakdown at the Schumann modes, J202 = 100 G", "", "nV/rtHz at antenna")
    legend(ax2, loc="lower center", ncol=2)

    for name, c in cols.items():
        for cond, ls in (("typical", "-"), ("quiet", "--")):
            ax3.plot(x, [sweep[name]["snr"][cond]["bin_1Hz"][s]["snr_dB"] for s in SR_LABELS], ls, marker="o",
                     color=c, lw=1.5, ms=4, label=f"{name}, {cond}")
    ax3.axhline(0, color=RED, lw=1)
    ax3.axhline(10, color=SUBTLE, lw=1, ls=":")
    ax3.set_xticks(x)
    ax3.set_xticklabels(SR_LABELS, color=TEXT, fontfamily="monospace")
    labels(ax3, "SNR in a 1 Hz bin centred on each mode (0.1 Hz bins within 0.1 dB)", "", "SNR (dB)")
    legend(ax3, loc="upper right", ncol=2)

    names = list(R_HB)
    width = 0.2
    icol = [GREEN, YELLOW, ORANGE, RED]
    for j, (iname, c) in enumerate(zip(I_ATM, icol)):
        vals = [max(sweep[n]["dc_and_headroom"][iname]["max_50Hz_input_mV_rms"], 1e-3) for n in names]
        ax4.bar(np.arange(len(names)) + (j - 1.5) * width, vals, width, color=c, alpha=0.85,
                label=f"I_atm = {iname}")
        for k, v in enumerate(vals):
            if v <= 1e-3:
                ax4.text(k + (j - 1.5) * width, 0.6, "SAT", rotation=90, ha="center", va="bottom", fontsize=8,
                         color=c, fontfamily="monospace")
    for v, c, lab in ((5, RED, "mains pickup 5 mV rms"), (1, ORANGE, "mains pickup 1 mV rms")):
        ax4.axhline(v, color=c, lw=1.2, ls="--", label=lab)
    ax4.set_yscale("log")
    ax4.set_ylim(0.5, 100)
    ax4.set_xticks(np.arange(len(names)))
    ax4.set_xticklabels([f"J202 {n}" for n in names], color=TEXT, fontfamily="monospace")
    hr = res["headroom_50Hz"]
    labels(ax4, f"Max 50 Hz input before clipping (limit: {hr['limited_by']})", "",
           "antenna EMF, mV rms")
    legend(ax4, loc="upper right")
    fig.suptitle("ELARA end-to-end budget -- antenna (140 pF) to PCM1804, J202 bias-resistor options",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    path = os.path.join(HERE, "system_budget.svg")
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("Plot saved:", path)


if __name__ == "__main__":
    main()
