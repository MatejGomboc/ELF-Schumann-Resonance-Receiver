# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Matplotlib figures for :class:`elara.pipeline.AnalysisResult`."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d9d8d3"
RAW = "#a3a29c"
CLEAN = "#2a78d6"
FIT = "#eb6834"

plt.rcParams.update({
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
})


def _db(psd):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(psd)


def plot_psd(res, path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.2), layout="constrained")
    uv = 1e6
    ax.semilogy(res.f, np.sqrt(res.psd_raw) * uv, color=RAW, lw=1.0,
                label="raw (L channel)")
    ax.semilogy(res.f, np.sqrt(res.psd_clean) * uv, color=CLEAN, lw=1.4,
                label="mains + reference cancelled")
    if res.fit is not None:
        ff = np.linspace(res.fit.f.min(), res.fit.f.max(), 1200)
        ax.semilogy(ff, np.sqrt(res.fit.model(ff)) * uv, color=FIT, lw=2.0,
                    label="Lorentzian fit")
        ax.semilogy(ff, np.sqrt(res.fit.background(ff)) * uv, color=FIT, lw=1.0, ls="--",
                    label="fitted background")
        top = np.nanmax(np.sqrt(res.psd_clean[res.f > 3])) * uv
        for m in res.fit.modes:
            ax.axvline(m.freq_hz, color=MUTED, lw=0.6, ls=":")
            ax.text(m.freq_hz, top * 1.25, f"SR{m.index}\n{m.freq_hz:.2f} Hz",
                    ha="center", va="bottom", fontsize=8, color=INK)
        ax.set_ylim(top=top * 3)
    ax.set_xlim(0, res.f.max())
    lo = np.nanpercentile(np.sqrt(res.psd_clean[res.f > 2]) * uv, 1)
    ax.set_ylim(bottom=lo / 3)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("Antenna-referred ASD [µV/√Hz]")
    ax.set_title(f"ELARA spectrum — {res.duration_s:.0f} s, "
                 f"{res.f[1] - res.f[0]:.2f} Hz resolution", loc="left", color=INK)
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return Path(path)


def plot_spectrogram(res, path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.2), layout="constrained")
    db = _db(res.spec)
    finite = db[np.isfinite(db) & (res.spec_f[:, None] > 2)]
    vmin, vmax = np.percentile(finite, [2, 99.8]) if finite.size else (None, None)
    mesh = ax.pcolormesh(res.spec_t, res.spec_f, db, shading="nearest", cmap="magma",
                         vmin=vmin, vmax=vmax, rasterized=True)
    cb = fig.colorbar(mesh, ax=ax, pad=0.01)
    cb.set_label("PSD [dB re 1 V²/Hz at antenna]")
    ax.grid(False)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Frequency [Hz]")
    ax.set_title("ELARA spectrogram — mains and reference-channel noise cancelled",
                 loc="left", color=INK)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return Path(path)
