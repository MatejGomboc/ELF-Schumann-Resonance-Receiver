#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""ELARA -- the antenna at the planned site: capacitance, effective height, noise, 50 Hz.

Geometry from the national LiDAR, stored only relative to the box foot (no
coordinates): the gable window (5.5 m up) to a tree at the forest edge, 95.7 m, the
box 53.6 m from the window under the line, the ground falling 13.7 m along it. The
anchor is ~10 m up a 14 m edge tree; 10 m insulating ropes at both ends.

Method: thin-wire electrostatic method of moments over the local ground (images),
exact self term; at ELF the antenna is a pure capacitance at one potential, so
    C_ant = Q / V,   h_eff = sum(q z) / sum(q)   (charge-weighted height),
and the open-circuit voltage is E_z * h_eff. Checked against a 10 m monopole
(textbook 2 pi e0 h / (ln(h/a) - 1)) and the design T (10 m + 15 m: 138 pF, the
140 pF the front end was designed for).

Receiver side (simulations/spice): the input sees C_ant against C_in = 100 pF (the
plate capacitors), divider k = C_ant / (C_ant + C_in); the noise at the input is
26.7 nV/rtHz at SR1 for the design antenna and is held fixed here (conservative: a
larger C_ant also shunts more of the bias-resistor current noise); the input clips at
29.5 mV rms of 50 Hz at the design antenna, i.e. 29.5 mV * k_design at the input.
Field-referred: noise N_in / (k h_eff), 50 Hz clip level V_clip,in / (k h_eff).

    .venv/bin/python simulations/antenna/site_antenna.py
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
EPS0 = 8.854e-12
WIRE_A = 1.0e-3            # insulated antenna wire, 2 mm conductor
# site, relative to the box foot (m): distance along the line from the window, height
L_SPAN, S_BOX = 95.7, 53.6
GROUND = np.array([(0.0, 7.92), (10.8, 6.54), (16.2, 5.35), (32.6, 3.17), (53.6, 0.0), (71.0, -2.71), (95.7, -5.79)])
Z_WINDOW = 7.92 + 5.56     # window 5.6 m above its ground (measured 5.5 m)
Z_ANCHOR = -5.79 + 10.0    # ~10 m up the 14 m anchor tree
ROPE, SAG_FULL, BOX_TOP = 10.0, 1.0, 1.4
C_IN, N_IN, CLIP_DESIGN = 100e-12, 26.7e-9, 29.5e-3


def solve(segs, n_per_m=1.5):
    """C (F) and h_eff (m) of wire segments [(p0, p1), ...] above ground z = 0."""
    a0, a1 = [], []
    for p0, p1 in segs:
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        n = max(2, int(np.linalg.norm(p1 - p0) * n_per_m))
        t = np.linspace(0, 1, n + 1)
        a0 += [p0 + (p1 - p0) * t[i] for i in range(n)]
        a1 += [p0 + (p1 - p0) * t[i + 1] for i in range(n)]
    P0, P1 = np.array(a0), np.array(a1)
    M, Ls = 0.5 * (P0 + P1), np.linalg.norm(P1 - P0, axis=1)
    g, w = np.polynomial.legendre.leggauss(8)
    g, w = 0.5 * (g + 1), 0.5 * w

    def pot(A, B):
        out = np.zeros((len(M), len(A)))
        for gi, wi in zip(g, w):
            S = A + (B - A) * gi
            r = np.linalg.norm(M[:, None, :] - S[None, :, :], axis=2)
            out += wi * Ls[None, :] / np.sqrt(r ** 2 + WIRE_A ** 2)
        return out / (4 * np.pi * EPS0)
    D = pot(P0, P1)
    np.fill_diagonal(D, 2 * np.arcsinh(Ls / (2 * WIRE_A)) / (4 * np.pi * EPS0))     # exact self term
    flip = np.array([1.0, 1.0, -1.0])
    Q = np.linalg.solve(D - pot(P0 * flip, P1 * flip), np.ones(len(M))) * Ls
    return float(Q.sum()), float((Q * M[:, 2]).sum() / Q.sum())


def ground(s):
    return float(np.interp(s, GROUND[:, 0], GROUND[:, 1]))


def site_antenna(top):
    """Top wire of length `top` centred on the down-lead (shifted towards the house where
    the forest-end rope runs out); heights above the local ground."""
    a, b = S_BOX - top / 2, S_BOX + top / 2
    if b > L_SPAN - ROPE:
        a, b = a - (b - (L_SPAN - ROPE)), L_SPAN - ROPE
    a = max(a, ROPE)
    sag = SAG_FULL * ((b - a) / (L_SPAN - 2 * ROPE)) ** 2

    def zw(s):
        t = (s - a) / (b - a)
        return Z_WINDOW + (Z_ANCHOR - Z_WINDOW) * s / L_SPAN - 4 * sag * t * (1 - t)
    s = np.linspace(a, b, max(3, int(b - a) + 1))
    pts = [(si, 0.0, zw(si) - ground(si)) for si in s]
    h_box = zw(S_BOX) - ground(S_BOX)
    C, h = solve([(pts[i], pts[i + 1]) for i in range(len(pts) - 1)] + [((S_BOX, 0, BOX_TOP), (S_BOX, 0, h_box))])
    return dict(top_m=b - a, wire_from_m=a, wire_to_m=b, height_at_box_m=h_box, C_pF=C * 1e12, h_eff_m=h)


def receiver(C, h, k_design, h_design):
    k = C / (C + C_IN)
    return dict(divider=k, noise_nV_m_rtHz=N_IN / (k * h) * 1e9,
                snr_vs_design_dB=20 * np.log10(k * h / (k_design * h_design)),
                clip_50Hz_mV_m=CLIP_DESIGN * k_design / (k * h) * 1e3)


def rnd(o):
    if isinstance(o, dict):
        return {k: rnd(v) for k, v in o.items()}
    if isinstance(o, list):
        return [rnd(v) for v in o]
    return float(f"{o:.4g}") if isinstance(o, float) else o


def main():
    mono = solve([((0, 0, 0.01), (0, 0, 10))])[0]
    textbook = 2 * np.pi * EPS0 * 10 / (np.log(10 / WIRE_A) - 1)
    Cd, hd = solve([((0, 0, BOX_TOP), (0, 0, 10)), ((-7.5, 0, 10), (7.5, 0, 10))])
    kd = Cd / (Cd + C_IN)
    res = {"check": {"monopole_10m_pF": mono * 1e12, "textbook_pF": textbook * 1e12},
           "design_T_10m_15m": dict(C_pF=Cd * 1e12, h_eff_m=hd, **receiver(Cd, hd, kd, hd))}
    sweep = []
    for top in np.arange(5.0, L_SPAN - 2 * ROPE + 0.1, 5.0):
        r = site_antenna(float(top))
        r.update(receiver(r["C_pF"] * 1e-12, r["h_eff_m"], kd, hd))
        sweep.append(r)
    full = site_antenna(L_SPAN - 2 * ROPE)
    full.update(receiver(full["C_pF"] * 1e-12, full["h_eff_m"], kd, hd))
    res["site_sweep"] = sweep
    res["site_full_span"] = full
    best = max(sweep, key=lambda r: r["snr_vs_design_dB"])
    res["notes"] = {"best_snr_top_m": best["top_m"],
                    "recommended": "30-50 m top wire centred on the down-lead: +0.6..+1.6 dB over the design "
                                   "antenna; the full span adds only ~0.1 dB more but the most 50 Hz pickup"}
    with open(_os.path.join(HERE, "site_antenna.json"), "w") as f:
        json.dump(rnd(res), f, indent=1)

    t = np.array([r["top_m"] for r in sweep])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    ax1.plot(t, [r["C_pF"] for r in sweep], color="C0", lw=2, label="C_ant (pF)")
    ax1.axhline(Cd * 1e12, color="C0", ls=":", lw=1, label=f"design T: {Cd*1e12:.0f} pF")
    ax1.set_xlabel("top wire length (m), centred on the down-lead")
    ax1.set_ylabel("antenna capacitance (pF)")
    ax1b = ax1.twinx()
    ax1b.plot(t, [r["h_eff_m"] for r in sweep], color="C1", lw=2, label="h_eff (m)")
    ax1b.axhline(hd, color="C1", ls=":", lw=1, label=f"design T: {hd:.2f} m")
    ax1b.set_ylabel("effective height (m)")
    ax1b.set_ylim(5, 9)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax1b.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="lower right", fontsize=9)
    ax1.set_title("Site antenna (LiDAR geometry): capacitance and effective height")
    ax1.grid(alpha=0.3)
    ax2.plot(t, [r["snr_vs_design_dB"] for r in sweep], color="C2", lw=2, label="SNR vs the design antenna (dB)")
    ax2.set_xlabel("top wire length (m), centred on the down-lead")
    ax2.set_ylabel("SNR change at SR1 (dB)")
    ax2.axhline(0, color="k", lw=0.8)
    ax2b = ax2.twinx()
    ax2b.plot(t, [r["clip_50Hz_mV_m"] for r in sweep], color="C3", lw=2, label="50 Hz field that clips the input (mV/m)")
    ax2b.axhline(CLIP_DESIGN * kd / (kd * hd) * 1e3, color="C3", ls=":", lw=1, label="design T")
    ax2b.set_ylabel("50 Hz clip level (mV/m rms)")
    ax2.axvspan(30, 50, color="C2", alpha=0.08, label="recommended 30-50 m")
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2b.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="center right", fontsize=9)
    ax2.set_title("What the extra wire buys: SNR, and what it costs: 50 Hz headroom")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(_os.path.join(HERE, "site_antenna.svg"))
    print(f"check: 10 m monopole {mono*1e12:.1f} pF (textbook {textbook*1e12:.1f}); design T {Cd*1e12:.0f} pF, h_eff {hd:.2f} m")
    for r in sweep[::2] + [full]:
        print(f"top {r['top_m']:5.1f} m: C {r['C_pF']:5.0f} pF, h_eff {r['h_eff_m']:.2f} m, SNR {r['snr_vs_design_dB']:+.1f} dB, "
              f"50 Hz clip {r['clip_50Hz_mV_m']:.2f} mV/m")


if __name__ == "__main__":
    main()
