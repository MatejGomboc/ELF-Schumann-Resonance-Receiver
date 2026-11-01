#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""ELARA -- mechanics of the site antenna: thermal and load statics, modes, wind noise.

Span (relative to the box, from simulations/antenna/site_antenna.py): window anchor
13.48 m, tree anchor 4.21 m, 95.7 m apart horizontally; ropes, then the top wire
centred on the down-lead, then ropes. Installed at +15 C with 1.0 m mid-span sag.

1. Statics, parabolic elastic cable (state-change equation): the anchor-to-anchor
   length must equal the sum of the segments, each stretched by H/EA and by
   alpha * dT. Cases: -25 C, +40 C, 10 mm radial ice at -5 C, ice + 20 m/s wind,
   30 m/s storm gust. Tension, sag, safety factors; installed sag 1.0 / 1.5 / 2.0 m.
   (A counterweight is not needed: the thermal tension change is a few per cent,
   and under ice it would let the wire down to the ground unless it hits a stop.)
2. Modes: taut-cable out-of-plane and antisymmetric in-plane f_n = n c / (2 L),
   c = sqrt(H / mu); first symmetric in-plane mode from Irvine's lambda^2.
3. Aeolian shedding: f = St U / D, St = 0.2: in band (7.8-33.8 Hz) only at
   U = 0.1-0.5 m/s, where the forcing (~U^2) is negligible against the damping.
4. Buffeting, the one that matters: vertical turbulence w' (von Karman, sigma_w =
   0.5 sigma_u, I_u = 0.2) drives the wire's vertical modes through the quasi-steady
   drag, F_z = 0.5 rho C_D D U w' per metre; exponential spanwise coherence; structural
   + aerodynamic damping. Each mode's vertical motion changes h_eff by the charge-
   weighted mean displacement over the top wire, and the fair-weather field turns it
   into an EMF: e = E0 dh_eff (E0 = 130 V/m: 1 mm = 130 mV). Compared with the receiver
   floor referred to the antenna EMF. Order-of-magnitude model: coherence, damping and
   turbulence near a forest edge are each uncertain by x2-3.

    .venv/bin/python simulations/antenna/site_wire.py
"""

import json
import os as _os

_os.environ.setdefault("SOURCE_DATE_EPOCH", "0")   # fixed SVG date: no churn on re-runs
import matplotlib  # noqa: E402
matplotlib.use("Agg")
matplotlib.rc_file(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "matplotlibrc"))
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = _os.path.dirname(_os.path.abspath(__file__))
G, RHO_AIR, RHO_ICE, CD = 9.81, 1.25, 900.0, 1.2
LH, DZ = 95.7, 13.48 - 4.21                  # horizontal span, anchor height difference
LC = float(np.hypot(LH, DZ))                 # chord
S_BOX = 53.6 * LC / LH                       # down-lead position along the chord
T0, SAG0 = 15.0, 1.0                         # installed at +15 C with 1 m mid-span sag
E0 = 130.0                                   # fair-weather field, V/m
C_TOP_FRACTION = 0.85                        # share of the antenna charge on the top wire
FLOOR_EMF = 26.7e-9 / 0.75                   # input noise / divider (~45 m top wire), V/rtHz
SIGNAL_EMF = 1.0e-6 * 7.3                    # typical SR1, 1 uV/m/rtHz (signal_chain) x h_eff 7.3 m

WIRES = {   # D (m), mu (kg/m), EA (N), alpha (1/K), breaking load (N)
    "copper-clad steel 1.6 mm, PE-insulated": dict(D=3.2e-3, mu=0.0224, EA=3.3e5, alpha=13e-6, brk=1400.0),
    "copper 1.5 mm2 stranded, PE-insulated": dict(D=3.0e-3, mu=0.0180, EA=1.5e5, alpha=17e-6, brk=330.0),
}
ROPES = {
    "Dyneema 4 mm": dict(D=4.0e-3, mu=0.010, EA=2.5e5, alpha=-12e-6, brk=15000.0),
    "polyester 6 mm": dict(D=6.0e-3, mu=0.025, EA=4.0e4, alpha=0.0, brk=6000.0),
}
CASES = {   # temperature (C), radial ice (m), wind (m/s)
    "installed +15 C": (15.0, 0.0, 0.0), "-25 C": (-25.0, 0.0, 0.0), "+40 C": (40.0, 0.0, 0.0),
    "ice 10 mm, -5 C": (-5.0, 0.010, 0.0), "ice 10 mm + wind 20 m/s": (-5.0, 0.010, 20.0),
    "storm gust 30 m/s, +15 C": (15.0, 0.0, 30.0),
}


def segments(top, wire, rope):
    """[(length along the chord, props), ...] house rope, wire, tree rope."""
    a = max(10.0, S_BOX - top / 2)
    b = min(LC - 10.0, a + top)
    a = b - top if b - top >= 10.0 else a
    return [(a, rope), (b - a, wire), (LC - b, rope)]


def loads(segs, ice, wind):
    """Mean vertical and horizontal (wind) load per metre of chord."""
    wv = wh = 0.0
    for s, p in segs:
        mu_ice = RHO_ICE * np.pi * ((p["D"] / 2 + ice) ** 2 - (p["D"] / 2) ** 2)
        wv += s * (p["mu"] + mu_ice) * G
        wh += s * 0.5 * RHO_AIR * wind ** 2 * CD * (p["D"] + 2 * ice)
    return wv / LC, wh / LC


def statics(segs, case, sag0=SAG0):
    T, ice, wind = case
    wv0, _ = loads(segs, 0.0, 0.0)
    H0 = wv0 * LC ** 2 / (8 * sag0)
    wv, wh = loads(segs, ice, wind)
    w = float(np.hypot(wv, wh))
    S_ref = LC + wv0 ** 2 * LC ** 3 / (24 * H0 ** 2)
    unstr = [(s * S_ref / LC) / (1 + H0 / p["EA"]) for s, p in segs]

    def f(H):
        have = sum(u * (1 + H / p["EA"] + p["alpha"] * (T - T0)) for u, (s, p) in zip(unstr, segs))
        return LC + w ** 2 * LC ** 3 / (24 * H ** 2) - have
    lo, hi = 1.0, 1e5
    for _ in range(200):
        mid = np.sqrt(lo * hi)
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    H = float(np.sqrt(lo * hi))
    sag = w * LC ** 2 / (8 * H)
    Tmax = float(np.hypot(H, w * LC / 2 + H * DZ / LH))          # at the high (window) anchor
    sf = min(p["brk"] for _, p in segs) / Tmax
    return dict(H_N=H, T_anchor_N=Tmax, sag_m=sag, sag_vertical_m=sag * wv / w, safety_factor=sf)


def modes(segs, H):
    mu = sum(s * p["mu"] for s, p in segs) / LC
    c = np.sqrt(H / mu)
    w, _ = loads(segs, 0.0, 0.0)
    EAe = LC / sum(s / p["EA"] for s, p in segs)
    lam2 = (w * LC / H) ** 2 * LC / (H * LC / EAe)
    x = np.linspace(0.01, 3 * np.pi, 20000)                      # tan(x/2) = x/2 - (4/lam2)(x/2)^3
    r = np.tan(x / 2) - (x / 2 - 4 / lam2 * (x / 2) ** 3)
    i = np.flatnonzero((np.sign(r[:-1]) != np.sign(r[1:])) & (np.abs(r[:-1]) < 50))
    f_sym1 = float(x[i[0]] * c / (2 * np.pi * LC)) if len(i) else float("nan")
    return mu, float(c), float(c / (2 * LC)), f_sym1, float(lam2)


def buffeting(segs, H, U, f, zeta_s=0.01):
    """EMF ASD (V/rtHz) from vertical buffeting of all modes up to f.max()."""
    mu, c, f1, _, _ = modes(segs, H)
    sw, wire = next((s, p) for s, p in segs if p in WIRES.values())
    a = segs[0][0]
    Lw = 7.0                                                     # turbulence length scale near ground, m
    sig_w = 0.5 * 0.2 * U
    n_f = f * Lw / U
    Sw = sig_w ** 2 * (4 * Lw / U) * (1 + 755.2 * n_f ** 2) / (1 + 283.2 * n_f ** 2) ** (11 / 6)
    Dm = sum(s * p["D"] for s, p in segs) / LC
    SF = (0.5 * RHO_AIR * CD * Dm * U) ** 2 * Sw
    lc = U / (8.0 * f)                                           # vertical coherence length
    xs = np.linspace(a, a + sw, 400)
    S_e = np.zeros_like(f)
    for n in range(1, int(f.max() / f1) + 2):
        k = n * np.pi / LC
        fn = n * f1
        J = np.minimum(LC * lc / (1 + (k * lc) ** 2), (2 * LC / (n * np.pi)) ** 2)
        M = mu * LC / 2
        zeta = zeta_s + 0.5 * RHO_AIR * U * Dm * CD / (2 * mu * 2 * np.pi * fn)
        w_, wn = 2 * np.pi * f, 2 * np.pi * fn
        Sq = SF * J / (M ** 2 * ((wn ** 2 - w_ ** 2) ** 2 + (2 * zeta * wn * w_) ** 2))
        an = C_TOP_FRACTION * float(np.mean(np.sin(k * xs)))
        S_e += (E0 * an) ** 2 * Sq
    return np.sqrt(S_e)


def rnd(o):
    if isinstance(o, dict):
        return {k: rnd(v) for k, v in o.items()}
    if isinstance(o, list):
        return [rnd(v) for v in o]
    return float(f"{o:.4g}") if isinstance(o, float) else o


def main():
    res = {"statics": {}, "modes": {}, "wind_noise": {}}
    for wn, wire in WIRES.items():
        for rn, rope in ROPES.items():
            for top in (45.0, 75.7):
                segs = segments(top, wire, rope)
                key = f"{wn} / {rn} / top {top:g} m"
                res["statics"][key] = {c: statics(segs, v) for c, v in CASES.items()}
    # dynamics for the recommended build: CCS wire, Dyneema rope, 45 m top wire
    wire, rope = WIRES["copper-clad steel 1.6 mm, PE-insulated"], ROPES["Dyneema 4 mm"]
    segs = segments(45.0, wire, rope)
    H0 = statics(segs, CASES["installed +15 C"])["H_N"]
    res["install_sag_sweep"] = {f"sag {sg:g} m at +15 C": {c: statics(segs, CASES[c], sg) for c in
                                ("installed +15 C", "ice 10 mm, -5 C", "ice 10 mm + wind 20 m/s", "storm gust 30 m/s, +15 C")}
                                for sg in (1.0, 1.5, 2.0)}
    mu, c, f1, fs1, lam2 = modes(segs, H0)
    band = (7.8, 33.8)
    res["modes"] = dict(H0_N=H0, wave_speed_m_s=c, f1_Hz=f1, f_sym1_inplane_Hz=fs1, irvine_lambda2=lam2,
                        modes_in_band=int(band[1] / f1) - int(band[0] / f1),
                        aeolian_in_band_wind_m_s=[band[0] * wire["D"] / 0.2, band[1] * wire["D"] / 0.2])
    f = np.linspace(0.2, 40.0, 793)
    winds = (1.0, 3.0, 6.0, 10.0)
    asd = {U: buffeting(segs, H0, U, f) for U in winds}
    for U in winds:
        i = int(np.argmin(np.abs(f - 7.83)))
        res["wind_noise"][f"{U:g} m/s"] = dict(emf_at_SR1_nV_rtHz=float(asd[U][i] * 1e9),
                                               emf_at_SR1_over_floor_dB=float(20 * np.log10(asd[U][i] / FLOOR_EMF)),
                                               emf_at_2Hz_uV_rtHz=float(asd[U][int(np.argmin(np.abs(f - 2.0)))] * 1e6))
    i = int(np.argmin(np.abs(f - 7.83)))
    band_i = (f >= 7.0) & (f <= 35.0)
    damped = buffeting(segs, H0, 3.0, f, zeta_s=0.05)
    res["wind_noise"]["3 m/s, damped (zeta 5 %)"] = dict(
        emf_at_SR1_nV_rtHz=float(damped[i] * 1e9),
        band_rms_reduction_dB=float(10 * np.log10(np.mean(asd[3.0][band_i] ** 2) / np.mean(damped[band_i] ** 2))))
    calm = [U for U in np.linspace(0.1, 1.0, 46) if buffeting(segs, H0, float(U), f)[i] < FLOOR_EMF]
    res["wind_noise"]["wind below which SR1 stays under the floor (m/s)"] = float(max(calm)) if calm else 0.0
    below_sig = [U for U in np.linspace(0.5, 5.0, 46) if buffeting(segs, H0, float(U), f)[i] < SIGNAL_EMF]
    res["wind_noise"]["wind below which SR1 noise stays under the typical signal (m/s)"] = float(max(below_sig))
    res["floor_emf_nV_rtHz"] = FLOOR_EMF * 1e9
    res["typical_SR1_signal_emf_nV_rtHz"] = SIGNAL_EMF * 1e9
    with open(_os.path.join(HERE, "site_wire.json"), "w") as fh:
        json.dump(rnd(res), fh, indent=1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.8))
    temps = np.linspace(-25, 40, 27)
    for (wn, wire_), ls in zip(WIRES.items(), ("-", "--")):
        for (rn, rope_), col in zip(ROPES.items(), ("C0", "C1")):
            sg = segments(45.0, wire_, rope_)
            sags = [statics(sg, (t, 0.0, 0.0))["sag_m"] for t in temps]
            ax1.plot(temps, sags, ls=ls, color=col, lw=2, label=f"{wn.split(',')[0]} + {rn}")
    ax1.axhline(SAG0, color="k", lw=0.8, ls=":")
    ax1.set_xlabel("temperature (C)")
    ax1.set_ylabel("mid-span sag (m), fixed anchors")
    ax1.set_title("Thermal sag change (installed +15 C, 1.0 m sag; 45 m top wire)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)
    for U, col in zip(winds, ("C2", "C0", "C1", "C3")):
        ax2.semilogy(f, asd[U], color=col, lw=1.2, label=f"wind {U:g} m/s")
    ax2.semilogy(f, damped, color="C0", lw=1.0, ls=":", label="wind 3 m/s, dampers (zeta 5 %)")
    ax2.axhline(FLOOR_EMF, color="k", lw=1.5, ls="--", label="receiver floor (antenna EMF)")
    ax2.axhline(SIGNAL_EMF, color="C4", lw=1.5, ls="-.", label="typical SR1 signal (1 uV/m/rtHz x h_eff)")
    for fr in (7.83, 14.3, 20.8, 27.3, 33.8):
        ax2.axvline(fr, color="C4", alpha=0.25, lw=0.8)
    ax2.set_xlabel("frequency (Hz)")
    ax2.set_ylabel("EMF from wire motion in the fair-weather field (V/rtHz)")
    ax2.set_title("Wind buffeting: vertical wire modes x E0 = 130 V/m (order of magnitude)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3, which="both")
    ax2.set_xlim(0, 40)
    fig.tight_layout()
    fig.savefig(_os.path.join(HERE, "site_wire.svg"))
    print("modes:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res["modes"].items()})
    for k in ("copper-clad steel 1.6 mm, PE-insulated / Dyneema 4 mm / top 45 m",
              "copper 1.5 mm2 stranded, PE-insulated / polyester 6 mm / top 45 m",
              ):
        print(k)
        for c_, v in res["statics"][k].items():
            print(f"   {c_:26s} H {v['H_N']:7.0f} N  anchor {v['T_anchor_N']:7.0f} N  sag {v['sag_m']:5.2f} m  SF {v['safety_factor']:5.1f}")
    for k, d in res["install_sag_sweep"].items():
        print(k, {c_: (round(v["T_anchor_N"]), round(v["sag_m"], 2), round(v["safety_factor"], 1)) for c_, v in d.items()})
    for U, v in res["wind_noise"].items():
        print("wind", U, v if isinstance(v, float) else {k: round(x, 2) for k, x in v.items()})


if __name__ == "__main__":
    main()
