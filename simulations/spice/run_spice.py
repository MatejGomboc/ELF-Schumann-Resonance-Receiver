#!/usr/bin/env python3
"""
ELARA -- ngspice verification of the analogue front end

Runs ngspice (batch mode) on elara_frontend.cir for:

    1. AC transfer, antenna EMF -> ADC input (VINL) and -> amplifier input
       (IN_P), 0.1 Hz - 1 GHz, for C_ant = 50 / 140 / 300 pF, with and
       without 0.2 pF parasitic capacitance across the 33k filter resistors.
    2. Noise analysis, output noise at VINL referred to the antenna and to
       the amplifier input, 0.5 Hz - 1 kHz, with per-source breakdown.
    3. Parameter sweeps: finite ADC input resistance, R_leak, the optional
       high-value bias resistor R_hb (noise, LF response, DC offset from the
       atmospheric conduction current), Cg return to GND vs BIAS_MID, and an
       assumed op-amp input capacitance.
    4. Numerical check of the synthesised LMP7721 1/f voltage noise against
       the target curve e_n(f) = 6.5 nV * sqrt(1 + 10 Hz / f).

Writes results.json and three SVG plots next to this script.

Author: Matej + Claude, September 2026
Licence: CERN-OHL-W-2.0
"""

import json
import os
import re
import shutil
import subprocess
import tempfile

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
NETLIST = os.path.join(HERE, "elara_frontend.cir")
LIBFILE = os.path.join(HERE, "lmp7721_behav.lib")

# ===========================================================================
# Physical constants and design numbers used by the Python reference budget
# ===========================================================================
k_B = 1.380649e-23
T = 300.0
Q_E = 1.602176634e-19
EPS0 = 8.8541878128e-12

SCHUMANN = [7.83, 14.3, 20.8, 27.3, 33.8, 39.0, 45.0]
SR_LABELS = ["SR1", "SR2", "SR3", "SR4", "SR5", "SR6", "SR7"]

C_ANT_NOM = 140e-12
C_FILT_TOTAL = 100e-12
H_EFF = 6.5            # antenna effective height used in expected_signal.py (m)
E_SR1_QUIET = 0.3e-6   # V/m/rtHz, quiet-condition SR1 field (expected_signal.py)

# Plot style (same palette as the other ELARA simulation scripts)
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


# ===========================================================================
# ngspice plumbing
# ===========================================================================
def build_netlist(params, control, workdir):
    """Return the netlist text with .param overrides and a new .control block."""
    with open(NETLIST) as fh:
        text = fh.read()
    for name, value in params.items():
        pat = re.compile(r"^(\.param\s+%s\s*=\s*)(\S+)" % re.escape(name),
                         re.MULTILINE | re.IGNORECASE)
        if not pat.search(text):
            raise KeyError(f"parameter {name} not found in netlist")
        text = pat.sub(lambda m: m.group(1) + str(value), text)
    text = re.sub(r"^\.control.*?^\.endc", ".control\n" + control + "\n.endc",
                  text, flags=re.MULTILINE | re.DOTALL)
    text = text.replace(".include lmp7721_behav.lib",
                        f".include {os.path.join(workdir, 'lmp7721_behav.lib')}")
    return text


def parse_raw_ascii(path):
    """Parse an ngspice ASCII rawfile (single plot) -> dict name -> ndarray."""
    with open(path) as fh:
        lines = fh.read().splitlines()
    i = 0
    nvars = npts = 0
    names = []
    is_complex = False
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("Flags:"):
            is_complex = "complex" in ln
        elif ln.startswith("No. Variables:"):
            nvars = int(ln.split(":")[1])
        elif ln.startswith("No. Points:"):
            npts = int(ln.split(":")[1])
        elif ln.startswith("Variables:"):
            for k in range(nvars):
                parts = lines[i + 1 + k].split()
                names.append(parts[1])
            i += nvars
        elif ln.startswith("Values:"):
            i += 1
            break
        i += 1
    tokens = []
    for ln in lines[i:]:
        tokens.extend(ln.split())
    data = np.zeros((npts, nvars), dtype=complex if is_complex else float)
    pos = 0
    for p in range(npts):
        pos += 1  # point index
        for v in range(nvars):
            tok = tokens[pos]
            pos += 1
            if is_complex:
                re_, im_ = tok.split(",")
                data[p, v] = complex(float(re_), float(im_))
            else:
                data[p, v] = float(tok)
    out = {}
    for v, n in enumerate(names):
        col = data[:, v]
        if is_complex and n == "frequency":
            col = col.real
        out[n.lower()] = col
    return out


def run_case(params, analyses, tag):
    """
    Run one netlist variant.

    analyses: list of (kind, spec) with kind in {"op", "ac", "noise", "dc"}.
    Returns dict kind#n -> parsed vectors.
    """
    with tempfile.TemporaryDirectory(prefix="elara_spice_") as wd:
        shutil.copy(LIBFILE, wd)
        ctl = ["set filetype=ascii", "set noaskquit"]
        outputs = []
        for n, (kind, spec) in enumerate(analyses):
            fn = os.path.join(wd, f"{kind}{n}.raw")
            if kind == "op":
                ctl += ["op", f"write {fn} all"]
            elif kind == "ac":
                ctl += [f"ac {spec}", f"write {fn} all"]
            elif kind == "dc":
                ctl += [f"dc {spec}", f"write {fn} all"]
            elif kind == "noise":
                # spec = "<outnode> <src> dec N f1 f2"; pts_per_summary = 1
                # keeps the per-generator contributions at every frequency
                ctl += [f"noise {spec} 1", "setplot previous",
                        f"write {fn} all"]
            outputs.append((f"{kind}{n}", fn))
        ctl.append("quit")
        net = build_netlist(params, "\n".join(ctl), wd)
        cir = os.path.join(wd, "run.cir")
        with open(cir, "w") as fh:
            fh.write(net)
        res = subprocess.run(["ngspice", "-b", cir], capture_output=True,
                             text=True, cwd=wd)
        combined = res.stdout + res.stderr
        if res.returncode != 0 or "error" in combined.lower():
            raise RuntimeError(f"ngspice failed for case {tag}:\n{combined}")
        result = {}
        for key, fn in outputs:
            result[key] = parse_raw_ascii(fn)
        return result


def run_raw_netlist(text, analyses_ctl, fname):
    """Run an ad-hoc netlist (used for the macromodel self-test)."""
    with tempfile.TemporaryDirectory(prefix="elara_spice_") as wd:
        shutil.copy(LIBFILE, wd)
        fn = os.path.join(wd, fname)
        ctl = analyses_ctl.replace("{OUT}", fn)
        net = text.replace("{LIB}", os.path.join(wd, "lmp7721_behav.lib"))
        net = net.replace("{CTL}", ctl)
        cir = os.path.join(wd, "selftest.cir")
        with open(cir, "w") as fh:
            fh.write(net)
        res = subprocess.run(["ngspice", "-b", cir], capture_output=True,
                             text=True, cwd=wd)
        if res.returncode != 0 or "error" in (res.stdout + res.stderr).lower():
            raise RuntimeError(res.stdout + res.stderr)
        return parse_raw_ascii(fn)


# ===========================================================================
# Helpers
# ===========================================================================
def interp_log(f, y, fq):
    """Log-log interpolation of a positive quantity."""
    return float(np.exp(np.interp(np.log(fq), np.log(f), np.log(y))))


def interp_db(f, ydb, fq):
    return float(np.interp(np.log(fq), np.log(f), ydb))


def db(x):
    return 20.0 * np.log10(np.abs(x))


def corners_3db(f, gdb):
    """Lower and upper -3 dB frequencies relative to the peak gain."""
    ipk = int(np.argmax(gdb))
    ref = gdb[ipk] - 3.0
    lo = hi = None
    for k in range(ipk, 0, -1):
        if gdb[k - 1] < ref <= gdb[k]:
            lo = float(np.exp(np.interp(ref, [gdb[k - 1], gdb[k]],
                                        [np.log(f[k - 1]), np.log(f[k])])))
            break
    for k in range(ipk, len(f) - 1):
        if gdb[k] >= ref > gdb[k + 1]:
            hi = float(np.exp(np.interp(ref, [gdb[k + 1], gdb[k]],
                                        [np.log(f[k + 1]), np.log(f[k])])))
            break
    return lo, hi, float(gdb[ipk]), float(f[ipk])


# Grouping of ngspice noise generators into physical sources
SOURCE_GROUPS = [
    ("R1 33k (antenna side)", ["onoise_r1"]),
    ("R3 33k (amplifier side)", ["onoise_r3"]),
    ("LMP7721 e_n (+1/f)", ["onoise_r.xu1.xen.rgen"]),
    ("LMP7721 i_n", ["onoise_r.xu1.xin.rgen"]),
    ("PCB leakage 0.1 fA", ["onoise_r.xpcb.rgen"]),
    ("Rg 1k", ["onoise_rg"]),
    ("Rf 100k", ["onoise_rf"]),
    ("R_AA 10k", ["onoise_raa"]),
    ("R_bias 47k", ["onoise_rbias"]),
    ("R_hb", ["onoise_rhb"]),
    ("BIAS_MID buffer", ["onoise_r.xbm.xen.rgen"]),
    ("R_adc", ["onoise_radc"]),
]


def noise_breakdown(nz, h_vinl):
    """Per-source contributions referred to the antenna (V/rtHz arrays)."""
    out = {}
    for label, keys in SOURCE_GROUPS:
        acc = None
        for k in keys:
            if k in nz:
                v = nz[k] ** 2
                acc = v if acc is None else acc + v
        if acc is not None:
            out[label] = np.sqrt(acc) / np.abs(h_vinl)
    return out


# ===========================================================================
# Python reference budget (same formulae as simulations/preamp_noise/*.py)
# ===========================================================================
def python_budget(f, c_ant=C_ANT_NOM):
    en = 6.5e-9 * np.sqrt(1.0 + 10.0 / f)
    z = 1.0 / (2 * np.pi * f * c_ant)
    e_r = np.sqrt(4 * k_B * T * 33e3)
    e_in = np.sqrt(en**2 + (0.01e-15 * z)**2 + (0.1e-15 * z)**2 + 2 * e_r**2
                   + (np.sqrt(4 * k_B * T * 100e3) / 101)**2
                   + 4 * k_B * T * 1e3)
    div = c_ant / (c_ant + C_FILT_TOTAL)
    return e_in, e_in / div


# ===========================================================================
# Simulation cases
# ===========================================================================
NOISE_SPEC = "v(vinl,vcom) Vsig dec 100 0.5 1000"
AC_NOISEGRID = "dec 100 0.5 1000"
AC_WIDE = "dec 50 0.1 1e9"
AC_LF = "dec 50 1e-5 1000"
NOISE_LF = "v(vinl,vcom) Vsig dec 50 0.01 1000"


def front_end_case(params, tag, wide=True):
    an = [("op", None)]
    if wide:
        an.append(("ac", AC_WIDE))
    an += [("ac", AC_NOISEGRID), ("noise", NOISE_SPEC)]
    r = run_case(params, an, tag)
    keys = list(r.keys())
    res = {"op": r[keys[0]]}
    if wide:
        res["ac"] = r[keys[1]]
    res["acn"] = r[keys[-2]]
    res["noise"] = r[keys[-1]]
    f = res["noise"]["frequency"]
    h_vinl = res["acn"]["v(vinl)"]
    h_inp = res["acn"]["v(in_p)"]
    res["f_noise"] = f
    res["e_ant"] = res["noise"]["inoise_spectrum"]
    res["e_amp"] = res["e_ant"] * np.abs(h_inp)   # referred to IN_P
    res["breakdown"] = noise_breakdown(res["noise"], h_vinl)
    return res


def summarise_ac(ac):
    f = ac["frequency"]
    g = db(ac["v(vinl)"])
    gi = db(ac["v(in_p)"])
    lo, hi, pk, fpk = corners_3db(f, g)
    sr = [interp_db(f, g, x) for x in SCHUMANN]
    return {
        "gain_vinl_db_at_SR": dict(zip([str(x) for x in SCHUMANN], sr)),
        "gain_inp_db_at_SR1": interp_db(f, gi, 7.83),
        "peak_gain_db": pk, "peak_freq_hz": fpk,
        "f_minus3db_low_hz": lo, "f_minus3db_high_hz": hi,
        "flatness_7p83_to_45_db": max(sr) - min(sr),
        "rf": {
            str(x): {"ant_to_inp_db": interp_db(f, gi, x),
                     "relative_to_inband_inp_db": interp_db(f, gi, x) - interp_db(f, gi, 7.83),
                     "ant_to_vinl_db": interp_db(f, g, x)}
            for x in (1e6, 100e6)},
    }


def main():
    results = {"meta": {
        "tool": "ngspice-42 (batch)", "temperature_K": 300.0,
        "notes": "behavioural LMP7721 macromodel, see lmp7721_behav.lib"}}

    # ------------------------------------------------------------------
    # 0. Macromodel self-test: e_n(f) of the synthesised noise source
    # ------------------------------------------------------------------
    selftest = """* LMP7721 macromodel noise self-test (unity follower, IN+ grounded)
.options temp=26.85
.include {LIB}
Vin inp 0 dc 0 ac 1
XU1 inp out out LMP7721_BEHAV
Rload out 0 10k noisy=0
.control
set filetype=ascii
{CTL}
.endc
.end
"""
    st = run_raw_netlist(selftest,
                         "noise v(out) Vin dec 50 0.1 100k 1\nsetplot previous\n"
                         "write {OUT} all\nquit", "st.raw")
    f_st = st["frequency"]
    en_sim = st["onoise_spectrum"]  # unity gain -> equals e_n (i_n x 0 Ohm = 0)
    en_tgt = 6.5e-9 * np.sqrt(1 + 10.0 / f_st)
    mask = f_st <= 1e4        # above ~10 kHz the finite GBW lifts the follower's noise gain
    err = en_sim / en_tgt - 1
    results["macromodel_selftest"] = {
        "en_at_7p83_sim_nV": interp_log(f_st, en_sim, 7.83) * 1e9,
        "en_at_7p83_target_nV": 6.5 * np.sqrt(1 + 10 / 7.83),
        "en_at_1k_sim_nV": interp_log(f_st, en_sim, 1e3) * 1e9,
        "max_rel_error_0p1Hz_10kHz": float(np.max(np.abs(err[mask]))),
    }
    print("Macromodel self-test:", results["macromodel_selftest"])

    # ------------------------------------------------------------------
    # 1. Nominal design, C_ant sweep, parasitic C across the 33k resistors
    # ------------------------------------------------------------------
    nominal = front_end_case({}, "nominal")
    cases_cant = {}
    for c in (50, 140, 300):
        cases_cant[c] = nominal if c == 140 else \
            front_end_case({"CANT": f"{c}p"}, f"cant{c}")
    par = run_case({"CPAR_EN": 1}, [("ac", AC_WIDE)], "cpar")["ac0"]

    f = nominal["f_noise"]
    py_in, py_ant = python_budget(f)

    sr_table = []
    for fx, lab in zip(SCHUMANN, SR_LABELS):
        sr_table.append({
            "label": lab, "f_hz": fx,
            "gain_ant_to_vinl_db": interp_db(nominal["ac"]["frequency"],
                                             db(nominal["ac"]["v(vinl)"]), fx),
            "noise_amp_input_nV": interp_log(f, nominal["e_amp"], fx) * 1e9,
            "noise_antenna_nV": interp_log(f, nominal["e_ant"], fx) * 1e9,
            "python_amp_input_nV": interp_log(f, py_in, fx) * 1e9,
            "python_antenna_nV": interp_log(f, py_ant, fx) * 1e9,
        })
    results["nominal"] = {
        "params": "C_ant=140p, R_leak=1T (noiseless), no R_hb, Cg->GND, ADC Rin=inf",
        "dc_op": {k: float(v[0]) for k, v in nominal["op"].items()
                  if k in ("v(in_p)", "v(vout)", "v(vinl)")},
        "ac": summarise_ac(nominal["ac"]),
        "schumann_table": sr_table,
        "breakdown_at_SR1_antenna_nV": {
            k: interp_log(f, v, 7.83) * 1e9 for k, v in nominal["breakdown"].items()},
        "integrated_noise_3_45Hz_antenna_uVrms": float(np.sqrt(np.trapezoid(
            nominal["e_ant"][(f >= 3) & (f <= 45)]**2, f[(f >= 3) & (f <= 45)])) * 1e6),
    }
    results["rf_with_0p2pF_parasitics"] = summarise_ac(par)["rf"]
    results["c_ant_sweep"] = {
        f"{c}pF": {"ac": summarise_ac(r["ac"]),
                   "noise_antenna_SR1_nV": interp_log(r["f_noise"], r["e_ant"], 7.83) * 1e9,
                   "noise_amp_input_SR1_nV": interp_log(r["f_noise"], r["e_amp"], 7.83) * 1e9,
                   "python_antenna_SR1_nV": float(python_budget(np.array([7.83]), c * 1e-12)[1][0] * 1e9)}
        for c, r in cases_cant.items()}

    # ------------------------------------------------------------------
    # 2. ADC input resistance sweep
    # ------------------------------------------------------------------
    adc = {"inf": nominal}
    for rv in ("100k", "20k", "5k"):
        adc[rv] = front_end_case({"RADC_EN": 1, "RADC": rv}, f"adc{rv}")
    results["adc_input_resistance"] = {
        k: {"gain_SR1_db": interp_db(r["ac"]["frequency"], db(r["ac"]["v(vinl)"]), 7.83),
            "ac": summarise_ac(r["ac"]),
            "noise_antenna_SR1_nV": interp_log(r["f_noise"], r["e_ant"], 7.83) * 1e9}
        for k, r in adc.items()}

    # ------------------------------------------------------------------
    # 3. Cg return: GND (build) vs BIAS_MID from an LMP7715-class buffer
    # ------------------------------------------------------------------
    cg = {}
    for fc in (10, 30):
        cg[fc] = front_end_case({"CG_RET": 1, "FC_BUF": fc}, f"cgret{fc}", wide=False)
    results["cg_return"] = {
        "assumption": "LMP7715: 5.8 nV/rtHz white, 1/f corner 30 Hz (10 Hz shown for reference)",
        "gnd": {"antenna_SR1_nV": interp_log(f, nominal["e_ant"], 7.83) * 1e9,
                "amp_input_SR1_nV": interp_log(f, nominal["e_amp"], 7.83) * 1e9},
    }
    for fc, r in cg.items():
        b = r["breakdown"]["BIAS_MID buffer"]
        results["cg_return"][f"bias_mid_fc{fc}Hz"] = {
            "antenna_SR1_nV": interp_log(f, r["e_ant"], 7.83) * 1e9,
            "amp_input_SR1_nV": interp_log(f, r["e_amp"], 7.83) * 1e9,
            "buffer_contrib_antenna_SR1_nV": interp_log(f, b, 7.83) * 1e9,
            "per_SR_antenna_nV": {str(x): interp_log(f, r["e_ant"], x) * 1e9 for x in SCHUMANN},
        }

    # ------------------------------------------------------------------
    # 4. Assumed op-amp common-mode input capacitance (10 pF)
    # ------------------------------------------------------------------
    cin = front_end_case({"CIN_EN": 1}, "cin", wide=True)
    results["input_capacitance_10pF"] = {
        "gain_SR1_db": interp_db(cin["ac"]["frequency"], db(cin["ac"]["v(vinl)"]), 7.83),
        "noise_antenna_SR1_nV": interp_log(f, cin["e_ant"], 7.83) * 1e9,
    }

    # ------------------------------------------------------------------
    # 5. DC path: R_leak sweep and optional bias resistor R_hb
    # ------------------------------------------------------------------
    bias_cases = {"none (R_leak 1T)": {}, "none (R_leak 10T)": {"RLEAK": "10T"}}
    for rv in ("1T", "100G", "10G", "1G"):
        bias_cases[f"R_hb {rv}"] = {"RHB_EN": 1, "RHB": rv}
    bias = {}
    for name, p in bias_cases.items():
        r = run_case(p, [("ac", AC_LF), ("noise", NOISE_LF),
                         ("ac", "dec 50 0.01 1000"),
                         ("dc", "Iatm 0 100p 1p")], name)
        k = list(r.keys())
        ac_lf, nz, acn, dc = r[k[0]], r[k[1]], r[k[2]], r[k[3]]
        fn = nz["frequency"]
        e_ant = nz["inoise_spectrum"]
        bd = noise_breakdown(nz, acn["v(vinl)"])
        fl = ac_lf["frequency"]
        g_inp = db(ac_lf["v(in_p)"])
        # IN_P high-pass corner: -3 dB below the in-band cap-divider level
        ref = interp_db(fl, g_inp, 10.0) - 3.0
        hp = None
        for j in range(len(fl) - 1):
            if g_inp[j] < ref <= g_inp[j + 1]:
                hp = float(np.exp(np.interp(ref, [g_inp[j], g_inp[j + 1]],
                                            [np.log(fl[j]), np.log(fl[j + 1])])))
                break
        idc = dc[[kk for kk in dc if "sweep" in kk][0]]
        vin = dc["v(in_p)"]
        v0 = float(vin[0])
        offs = {f"{int(round(i * 1e12))}pA": float(np.interp(i, idc, vin) - v0)
                for i in (1e-12, 10e-12, 100e-12)}
        bias[name] = {"f": fn, "e_ant": e_ant, "bd": bd, "f_lf": fl,
                      "g_inp": g_inp, "g_vinl": db(ac_lf["v(vinl)"])}
        entry = {
            "dc_in_p_V_at_zero_current": v0,
            "dc_offset_at_in_p_V": offs,
            "in_p_highpass_minus3db_hz": hp,
            "noise_antenna_nV": {str(x): interp_log(fn, e_ant, x) * 1e9 for x in SCHUMANN},
        }
        if "R_hb" in bd:
            entry["r_hb_contrib_antenna_nV"] = {
                str(x): interp_log(fn, bd["R_hb"], x) * 1e9 for x in SCHUMANN}
        results.setdefault("bias_resistor", {})[name] = entry

    # Atmospheric conduction current estimate (fair weather)
    sigma_air, e_fw = 1e-14, 100.0
    atm = {}
    for h_desc, v_amb in (("h_eff 6.5 m (650 V)", 650.0), ("10 m (1000 V)", 1000.0)):
        q = C_ANT_NOM * v_amb
        i = sigma_air * q / EPS0
        atm[h_desc] = {"Q_C": q, "I_A": i}
    c_tot = C_ANT_NOM + C_FILT_TOTAL
    i_ref = 100e-12
    w1 = 2 * np.pi * 7.83 * C_ANT_NOM
    results["atmospheric_current"] = {
        "sigma_air_S_per_m": sigma_air, "E_fair_weather_V_per_m": e_fw,
        "estimates": atm,
        "relaxation_time_eps0_over_sigma_s": EPS0 / sigma_air,
        "floating_input_slew_V_per_s_at_100pA": i_ref / c_tot,
        "time_to_move_1V_at_100pA_s": c_tot / i_ref,
        "shot_noise_fA_at_100pA": np.sqrt(2 * Q_E * i_ref) * 1e15,
        "shot_noise_antenna_SR1_nV_at_100pA": np.sqrt(2 * Q_E * i_ref) / w1 * 1e9,
        "shot_noise_antenna_SR1_nV_at_10pA": np.sqrt(2 * Q_E * 10e-12) / w1 * 1e9,
        "shot_noise_antenna_SR1_nV_at_1pA": np.sqrt(2 * Q_E * 1e-12) / w1 * 1e9,
        "sr1_signal_quiet_antenna_nV": E_SR1_QUIET * H_EFF * 1e9,
        "resistor_to_shot_psd_ratio_at_1V_drop": 2 * k_B * T / (Q_E * 1.0),
    }

    # ------------------------------------------------------------------
    # Write JSON
    # ------------------------------------------------------------------
    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.floating, float)):
            return float(f"{float(o):.6g}")
        if isinstance(o, np.integer):
            return int(o)
        return o
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(clean(results), fh, indent=2)
    print_summary(results)

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------
    plot_ac(cases_cant, par, adc)
    plot_noise(nominal, cases_cant, adc, cg, cin, py_ant, py_in, f_st, en_sim, en_tgt)
    plot_bias(bias, results)


# ===========================================================================
# Console summary
# ===========================================================================
def print_summary(r):
    n = r["nominal"]
    print("=" * 90)
    print("ELARA front end -- ngspice results (C_ant = 140 pF)")
    print("=" * 90)
    print(f"{'':6}{'f (Hz)':>8}{'gain dB':>10}{'amp in':>10}{'antenna':>10}"
          f"{'py amp':>10}{'py ant':>10}   (noise in nV/rtHz)")
    for row in n["schumann_table"]:
        print(f"{row['label']:6}{row['f_hz']:>8.2f}{row['gain_ant_to_vinl_db']:>10.2f}"
              f"{row['noise_amp_input_nV']:>10.1f}{row['noise_antenna_nV']:>10.1f}"
              f"{row['python_amp_input_nV']:>10.1f}{row['python_antenna_nV']:>10.1f}")
    ac = n["ac"]
    print(f"\n-3 dB corners: {ac['f_minus3db_low_hz']:.2f} Hz / {ac['f_minus3db_high_hz']:.1f} Hz,"
          f" peak {ac['peak_gain_db']:.2f} dB at {ac['peak_freq_hz']:.1f} Hz,"
          f" flatness 7.83-45 Hz {ac['flatness_7p83_to_45_db']:.2f} dB")
    for fx, v in ac["rf"].items():
        print(f"RF {float(fx)/1e6:g} MHz: ANT->IN_P {v['ant_to_inp_db']:.1f} dB "
              f"(rel. in-band {v['relative_to_inband_inp_db']:.1f} dB), ANT->VINL {v['ant_to_vinl_db']:.1f} dB, "
              f"with 0.2 pF parasitics ANT->IN_P "
              f"{r['rf_with_0p2pF_parasitics'][fx]['ant_to_inp_db']:.1f} dB")
    print("\nBreakdown at SR1, referred to antenna (nV/rtHz):")
    for k, v in n["breakdown_at_SR1_antenna_nV"].items():
        print(f"   {k:<28}{v:8.2f}")
    print("\nADC input resistance:", {k: round(v["gain_SR1_db"], 2)
                                     for k, v in r["adc_input_resistance"].items()})
    print("Cg return:", json.dumps({k: v.get("antenna_SR1_nV") for k, v in r["cg_return"].items()
                                    if isinstance(v, dict)}))
    print("C_in 10 pF:", r["input_capacitance_10pF"])
    print("\nBias resistor:")
    for k, v in r["bias_resistor"].items():
        print(f"   {k:<20} HP {v['in_p_highpass_minus3db_hz']} Hz, "
              f"noise SR1 {v['noise_antenna_nV']['7.83']:.1f} nV, offsets {v['dc_offset_at_in_p_V']}"
              f", V0 {v['dc_in_p_V_at_zero_current']:.3f}")
    print("\nAtmospheric:", json.dumps(r["atmospheric_current"], indent=1))


# ===========================================================================
# Plotting
# ===========================================================================
def style(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=SUBTLE, labelsize=9)
    ax.grid(True, which="both", alpha=0.15, color=SUBTLE)
    for s in ax.spines.values():
        s.set_color(BORDER)


def labels(ax, title, xl, yl):
    ax.set_title(title, fontsize=12, fontweight="bold", color=TEXT,
                 fontfamily="monospace", pad=8)
    ax.set_xlabel(xl, fontsize=10, color=TEXT, fontfamily="monospace")
    ax.set_ylabel(yl, fontsize=10, color=TEXT, fontfamily="monospace")


def legend(ax, loc="best", **kw):
    lg = ax.legend(loc=loc, fontsize=8, facecolor=PANEL, edgecolor=BORDER,
                   labelcolor=TEXT, **kw)
    lg.get_frame().set_alpha(0.9)


def sr_markers(ax, ytext=None, fs=6):
    for lab, fx in zip(SR_LABELS, SCHUMANN):
        ax.axvline(fx, color=SUBTLE, alpha=0.3, linestyle="--", linewidth=0.8)
        if ytext is not None:
            ax.text(fx, ytext, lab, fontsize=fs, ha="center", va="bottom",
                    color=SUBTLE, fontfamily="monospace")


def save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("Plot saved:", path)


def plot_ac(cases_cant, par, adc):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
    fig.patch.set_facecolor(BG)
    for ax in (ax1, ax2):
        style(ax)
    cols = {50: BLUE, 140: GREEN, 300: PURPLE}
    for c, r in cases_cant.items():
        fa = r["ac"]["frequency"]
        ax1.semilogx(fa, db(r["ac"]["v(vinl)"]), color=cols[c], lw=2.5 if c == 140 else 1.5,
                     label=f"C_ant {c} pF: antenna -> ADC input (VINL)")
        ax1.semilogx(fa, db(r["ac"]["v(in_p)"]), color=cols[c], lw=1.2, ls="--",
                     label=f"C_ant {c} pF: antenna -> LMP7721 IN+")
    ax1.semilogx(par["frequency"], db(par["v(in_p)"]), color=ORANGE, lw=1.5, ls=":",
                 label="140 pF, 0.2 pF across each 33k: antenna -> IN+")
    for fx, lab in ((1e6, "1 MHz AM"), (100e6, "100 MHz FM")):
        ax1.axvline(fx, color=RED, alpha=0.4, ls="--", lw=0.8)
        ax1.text(fx, 45, lab, color=RED, fontsize=8, ha="center", fontfamily="monospace")
    sr_markers(ax1)
    ax1.set_xlim(0.1, 1e9)
    ax1.set_ylim(-260, 55)
    labels(ax1, "ELARA front end (ngspice) -- transfer from antenna EMF\n"
           "RC filter 2 x 33k/50 pF, LMP7721 40 dB (Cg to GND), AA 10k/100 nF",
           "Frequency (Hz)", "Gain (dB)")
    legend(ax1, loc="lower left")

    cols2 = {"inf": GREEN, "100k": BLUE, "20k": YELLOW, "5k": RED}
    for k, r in adc.items():
        fa = r["ac"]["frequency"]
        ax2.semilogx(fa, db(r["ac"]["v(vinl)"]), color=cols2[k], lw=2.5 if k == "inf" else 1.5,
                     label=f"ADC input resistance {'infinite' if k == 'inf' else k + 'Ohm'}")
    for c in (50, 300):
        r = cases_cant[c]
        ax2.semilogx(r["ac"]["frequency"], db(r["ac"]["v(vinl)"]), color=cols[c], lw=1.2,
                     ls="--", label=f"C_ant {c} pF (ADC infinite)")
    sr_markers(ax2, ytext=18.3)
    ax2.set_xlim(0.1, 1000)
    ax2.set_ylim(18, 40)
    labels(ax2, "In-band detail: C_ant and ADC input-resistance sweeps",
           "Frequency (Hz)", "Gain antenna -> VINL (dB)")
    legend(ax2, loc="upper right")
    plt.tight_layout()
    save(fig, "frontend_ac.svg")


def plot_noise(nominal, cases_cant, adc, cg, cin, py_ant, py_in, f_st, en_sim, en_tgt):
    fig = plt.figure(figsize=(14, 17))
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(3, 1, height_ratios=[1.25, 1, 0.8])
    ax1, ax2, ax3 = (fig.add_subplot(gs[i]) for i in range(3))
    for ax in (ax1, ax2, ax3):
        style(ax)

    f = nominal["f_noise"]
    colmap = {
        "R1 33k (antenna side)": RED, "R3 33k (amplifier side)": ORANGE,
        "LMP7721 e_n (+1/f)": GREEN, "LMP7721 i_n": BLUE,
        "PCB leakage 0.1 fA": PURPLE, "Rg 1k": YELLOW, "Rf 100k": GREY,
        "R_AA 10k": "#56d4dd", "R_bias 47k": "#a5d6ff"}
    for k, v in nominal["breakdown"].items():
        ax1.loglog(f, v * 1e9, color=colmap.get(k, SUBTLE), lw=1.4, ls="--", label=k)
    ax1.loglog(f, nominal["e_ant"] * 1e9, color=GREEN, lw=3, label="TOTAL (ngspice), referred to antenna")
    ax1.loglog(f, py_ant * 1e9, color=TEXT, lw=1.5, ls=":", label="Python budget, referred to antenna")
    ax1.loglog(f, nominal["e_amp"] * 1e9, color=BLUE, lw=2, label="TOTAL (ngspice), at amplifier input IN+")
    ax1.loglog(f, py_in * 1e9, color=BLUE, lw=1.2, ls=":", label="Python budget, at amplifier input")
    sr_markers(ax1, ytext=0.012)
    ax1.set_xlim(0.5, 1000)
    ax1.set_ylim(0.01, 1000)
    e1 = interp_log(f, nominal["e_ant"], 7.83) * 1e9
    p1 = interp_log(f, py_ant, 7.83) * 1e9
    ax1.annotate(f"{e1:.1f} nV/rtHz @ 7.83 Hz\n(Python: {p1:.1f})",
                 xy=(7.83, e1), xytext=(60, 250), fontsize=9,
                 color=GREEN, fontfamily="monospace",
                 arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.2))
    labels(ax1, "ELARA front-end noise (ngspice .noise) -- C_ant = 140 pF\n"
           "per-source contributions referred to the antenna EMF",
           "Frequency (Hz)", "Noise density (nV/sqrtHz)")
    legend(ax1, loc="lower left", ncol=2)

    cols = {50: BLUE, 140: GREEN, 300: PURPLE}
    for c, r in cases_cant.items():
        ax2.loglog(f, r["e_ant"] * 1e9, color=cols[c], lw=2.5 if c == 140 else 1.5,
                   label=f"C_ant {c} pF")
    for fc, ls in ((30, "--"), (10, ":")):
        ax2.loglog(f, cg[fc]["e_ant"] * 1e9, color=ORANGE, lw=1.5, ls=ls,
                   label=f"140 pF, Cg to BIAS_MID (LMP7715 5.8 nV, 1/f corner {fc} Hz)")
    ax2.loglog(f, adc["5k"]["e_ant"] * 1e9, color=RED, lw=1.2, ls="-.",
               label="140 pF, ADC input resistance 5 kOhm")
    ax2.loglog(f, cin["e_ant"] * 1e9, color=YELLOW, lw=1.2, ls="--",
               label="140 pF, +10 pF op-amp input capacitance (assumed)")
    sr_markers(ax2, ytext=10.5)
    ax2.set_xlim(0.5, 1000)
    ax2.set_ylim(10, 1000)
    labels(ax2, "Total noise referred to antenna -- design variants",
           "Frequency (Hz)", "Noise density (nV/sqrtHz)")
    legend(ax2, loc="upper right")

    ax3.semilogx(f_st, en_sim * 1e9, color=GREEN, lw=3, label="ngspice macromodel e_n (follower, IN+ grounded)")
    ax3.semilogx(f_st, en_tgt * 1e9, color=TEXT, lw=1.5, ls="--",
                 label="target 6.5 nV x sqrt(1 + 10 Hz / f)")
    ax3.set_yscale("log")
    ax3b = ax3.twinx()
    ax3b.semilogx(f_st, (en_sim / en_tgt - 1) * 100, color=YELLOW, lw=1, ls=":",
                  label="deviation (%)")
    ax3b.set_ylim(-1, 5)
    ax3b.tick_params(colors=YELLOW, labelsize=9)
    ax3b.set_ylabel("Deviation from target (%)", color=YELLOW, fontsize=10, fontfamily="monospace")
    for s in ax3b.spines.values():
        s.set_color(BORDER)
    ax3.axvline(7.83, color=SUBTLE, alpha=0.3, ls="--", lw=0.8)
    ax3.set_xlim(0.1, 1e5)
    labels(ax3, "Macromodel check: synthesised LMP7721 voltage noise (1/f-resistor + CCVS)",
           "Frequency (Hz)", "e_n (nV/sqrtHz)")
    h1, l1 = ax3.get_legend_handles_labels()
    h2, l2 = ax3b.get_legend_handles_labels()
    lg = ax3.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8, facecolor=PANEL,
                    edgecolor=BORDER, labelcolor=TEXT)
    lg.get_frame().set_alpha(0.9)
    plt.tight_layout()
    save(fig, "frontend_noise.svg")


def plot_bias(bias, results):
    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor(BG)
    for ax in axs.flat:
        style(ax)
    ax1, ax2, ax3, ax4 = axs.flat
    cols = {"none (R_leak 1T)": GREEN, "none (R_leak 10T)": "#56d4dd",
            "R_hb 1T": BLUE, "R_hb 100G": PURPLE, "R_hb 10G": ORANGE, "R_hb 1G": RED}
    w = None
    for name, d in bias.items():
        ax1.loglog(d["f"], d["e_ant"] * 1e9, color=cols[name], lw=2, label=f"total, {name}")
        if "R_hb" in d["bd"]:
            ax1.loglog(d["f"], d["bd"]["R_hb"] * 1e9, color=cols[name], lw=1, ls="--")
        ax2.semilogx(d["f_lf"], d["g_inp"], color=cols[name], lw=2, label=name)
        w = d["f"]
    wa = 2 * np.pi * w * C_ANT_NOM
    for i_atm, ls in ((100e-12, ":"), (1e-12, "-.")):
        ax1.loglog(w, np.sqrt(2 * Q_E * i_atm) / wa * 1e9, color=TEXT, lw=1.2, ls=ls,
                   label=f"ion-current shot noise, {i_atm*1e12:.0f} pA (if Poissonian)")
    ax1.axhline(E_SR1_QUIET * H_EFF * 1e9, color=YELLOW, lw=1, alpha=0.6)
    ax1.text(0.012, E_SR1_QUIET * H_EFF * 1e9 * 1.1, "SR1 signal, quiet (0.3 uV/m x 6.5 m)",
             color=YELLOW, fontsize=8, fontfamily="monospace")
    sr_markers(ax1)
    ax1.set_xlim(0.01, 1000)
    ax1.set_ylim(10, 1e6)
    labels(ax1, "Noise referred to antenna vs bias resistor\n(dashed: R_hb thermal share)",
           "Frequency (Hz)", "Noise density (nV/sqrtHz)")
    legend(ax1, loc="upper right")

    sr_markers(ax2)
    ax2.set_xlim(1e-5, 1000)
    ax2.set_ylim(-40, 0)
    labels(ax2, "Low-frequency response antenna -> IN+\n(high-pass R_hb x (C_ant + 100 pF))",
           "Frequency (Hz)", "Gain (dB)")
    legend(ax2, loc="lower right")

    br = results["bias_resistor"]
    rvals = np.array([1e9, 1e10, 1e11, 1e12])
    names = ["R_hb 1G", "R_hb 10G", "R_hb 100G", "R_hb 1T"]
    for ia, col in (("1pA", GREEN), ("10pA", YELLOW), ("100pA", RED)):
        offs = [abs(br[n]["dc_offset_at_in_p_V"][ia]) for n in names]
        ax3.loglog(rvals, offs, "o-", color=col, lw=2, label=f"I_atm = {ia[:-2]} pA")
    ax3.axhspan(1.0, 1e3, color=RED, alpha=0.08)
    ax3.axhline(1.0, color=RED, lw=1, ls="--")
    ax3.text(1.1e9, 1.3, "assumed usable window: +/-1 V around 2.5 V", color=RED,
             fontsize=8, fontfamily="monospace")
    ax3.set_ylim(1e-3, 200)
    labels(ax3, "DC offset at IN+ from the air-earth conduction current\n"
           "(R_hb || R_leak 1T, ngspice .dc)", "R_hb (Ohm)", "|Offset| (V)")
    legend(ax3, loc="upper left")

    tot = [br[n]["noise_antenna_nV"]["7.83"] for n in names]
    rhb = [br[n]["r_hb_contrib_antenna_nV"]["7.83"] for n in names]
    base = br["none (R_leak 1T)"]["noise_antenna_nV"]["7.83"]
    ax4.loglog(rvals, tot, "o-", color=GREEN, lw=2, label="total noise at SR1 (antenna)")
    ax4.loglog(rvals, rhb, "s--", color=ORANGE, lw=1.5, label="R_hb thermal share at SR1")
    ax4.axhline(base, color=BLUE, lw=1, ls=":", label=f"no R_hb: {base:.1f} nV/rtHz")
    for i_atm, col in ((1e-12, GREEN), (10e-12, YELLOW), (100e-12, RED)):
        ax4.axhline(np.sqrt(2 * Q_E * i_atm) / (2 * np.pi * 7.83 * C_ANT_NOM) * 1e9,
                    color=col, lw=1, ls="-.", alpha=0.7,
                    label=f"shot noise of {i_atm*1e12:.0f} pA at SR1")
    ax4.set_ylim(10, 2000)
    labels(ax4, "Noise at SR1 (7.83 Hz) vs R_hb", "R_hb (Ohm)", "Noise at antenna (nV/sqrtHz)")
    legend(ax4, loc="upper right")
    fig.suptitle("ELARA -- input DC bias: bias-resistor noise vs atmospheric-current offset",
                 fontsize=13, fontweight="bold", color=TEXT, fontfamily="monospace")
    plt.tight_layout()
    save(fig, "bias_resistor_tradeoff.svg")


if __name__ == "__main__":
    main()
