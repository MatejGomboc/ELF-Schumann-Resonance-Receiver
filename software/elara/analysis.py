# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Spectral analysis, Schumann-resonance fitting and sferic detection."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize, signal

from .frontend import SCHUMANN_MODES_HZ


# ---------------------------------------------------------------------------
# Spectra
# ---------------------------------------------------------------------------

def welch_psd(x: np.ndarray, fs: float, resolution_hz: float = 0.1,
              fmax: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """One-sided Welch PSD (Hann, 50 % overlap) with the requested bin spacing.

    The segment length is shortened when the record is too short for at least
    four averages.
    """
    x = np.asarray(x, dtype=float)
    nperseg = int(round(fs / resolution_hz))
    nperseg = max(16, min(nperseg, len(x) // 2 or len(x)))
    f, p = signal.welch(x, fs, window="hann", nperseg=nperseg, noverlap=nperseg // 2,
                        detrend="constant", axis=0)
    if fmax is not None:
        keep = f <= fmax
        f, p = f[keep], p[keep]
    return f, p


def spectrogram(x: np.ndarray, fs: float, resolution_hz: float = 0.5,
                column_s: float = 5.0, overlap: float = 0.75, fmax: float | None = None):
    """Averaged spectrogram: Hann periodograms averaged into ``column_s`` columns.

    Raw single-segment periodograms have a 100 % standard deviation, which
    hides the broad Schumann modes; averaging the frames within each column
    (Welch-style) makes them visible.  Returns ``(f, t, Sxx)`` with Sxx
    shaped (f, t) in units^2/Hz and ``t`` the column centres.
    """
    x = np.asarray(x, dtype=float)
    nperseg = max(16, min(int(round(fs / resolution_hz)), len(x)))
    f, t, s = signal.spectrogram(x, fs, window="hann", nperseg=nperseg,
                                 noverlap=int(nperseg * overlap),
                                 scaling="density", mode="psd")
    hop = t[1] - t[0] if len(t) > 1 else column_s
    per_col = max(1, int(round(column_s / hop)))
    n_col = max(1, len(t) // per_col)
    s = s[:, :n_col * per_col].reshape(len(f), n_col, -1).mean(axis=2)
    t = t[:n_col * per_col].reshape(n_col, -1).mean(axis=1)
    if fmax is not None:
        keep = f <= fmax
        f, s = f[keep], s[keep]
    return f, t, s


# ---------------------------------------------------------------------------
# Schumann resonance fit
# ---------------------------------------------------------------------------

@dataclass
class ModeFit:
    """One fitted Schumann mode.  ``width_hz`` is the half-width at half-maximum."""

    index: int
    freq_hz: float
    freq_err_hz: float
    amplitude: float           # peak PSD above background [input units^2/Hz]
    amplitude_err: float
    width_hz: float
    width_err_hz: float

    @property
    def q(self) -> float:
        return self.freq_hz / (2 * self.width_hz)

    @property
    def q_err(self) -> float:
        return self.q * np.hypot(self.freq_err_hz / self.freq_hz, self.width_err_hz / self.width_hz)


@dataclass
class SchumannFit:
    modes: list[ModeFit]
    bg_amplitude: float        # background PSD at 10 Hz
    bg_exponent: float         # background ~ f**(-exponent)
    f: np.ndarray              # frequencies used in the fit
    psd: np.ndarray            # data used in the fit
    rms_log_residual: float    # rms residual in log10(PSD)

    def model(self, f) -> np.ndarray:
        return _model(np.asarray(f, float), self._params())

    def background(self, f) -> np.ndarray:
        return self.bg_amplitude * (np.asarray(f, float) / 10.0) ** (-self.bg_exponent)

    def _params(self) -> np.ndarray:
        p = [np.log(self.bg_amplitude), self.bg_exponent]
        for m in self.modes:
            p += [m.freq_hz, np.log(m.amplitude), np.log(m.width_hz)]
        return np.array(p)


def _model(f: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Power-law background + sum of Lorentzians.

    Parameter vector: [ln B10, alpha, (f_i, ln A_i, ln gamma_i) * n].
    """
    out = np.exp(p[0]) * (f / 10.0) ** (-p[1])
    for fi, ln_a, ln_g in p[2:].reshape(-1, 3):
        out = out + np.exp(ln_a) / (1.0 + ((f - fi) / np.exp(ln_g)) ** 2)
    return out


def fit_schumann(f: np.ndarray, psd: np.ndarray, modes=SCHUMANN_MODES_HZ,
                 fmin: float = 3.0, fmax: float = 48.0,
                 exclude: tuple[tuple[float, float], ...] = ((49.0, 51.0),),
                 max_shift_hz: float = 2.5, q_range=(2.0, 15.0)) -> SchumannFit:
    """Fit a sum of Lorentzians plus a power-law background to an averaged PSD.

    The fit minimises the squared difference of log PSDs, which is the natural
    metric for averaged periodograms (their scatter is multiplicative).
    Uncertainties come from the Jacobian at the optimum, scaled by the residual
    variance.  Only modes whose nominal frequency lies inside ``[fmin, fmax]``
    are fitted; ``exclude`` bands (e.g. residual mains) are masked out.
    Centre frequencies may move ``max_shift_hz`` from nominal and quality
    factors are bounded to ``q_range`` (observed Schumann Q is ~3..10), which
    stops a mode latching onto a single noisy bin in short records.
    """
    f = np.asarray(f, float)
    psd = np.asarray(psd, float)
    sel = (f >= fmin) & (f <= fmax) & np.isfinite(psd) & (psd > 0)
    for lo, hi in exclude:
        sel &= ~((f >= lo) & (f <= hi))
    fs_, ps_ = f[sel], psd[sel]
    modes = [m for m in modes if fmin < m < fmax]
    if len(fs_) < 3 * len(modes) + 4:
        raise ValueError("not enough spectral points in the fit range")
    y = np.log(ps_)

    # Initial guesses: background through the lower envelope, amplitudes from the peaks.
    lo_env = np.percentile(ps_, 20)
    p0 = [np.log(lo_env), 1.0]
    lb, ub = [-np.inf, -1.0], [np.inf, 4.0]
    for fm in modes:
        near = np.abs(fs_ - fm) < 1.0
        peak = ps_[near].max() if near.any() else lo_env
        p0 += [fm, np.log(max(peak - lo_env, 0.1 * lo_env)), np.log(fm / 12.0)]
        lb += [fm - max_shift_hz, -np.inf, np.log(fm / (2 * q_range[1]))]
        ub += [fm + max_shift_hz, np.inf, np.log(fm / (2 * q_range[0]))]
    p0 = np.clip(p0, np.array(lb) + 1e-9, np.array(ub) - 1e-9)

    res = optimize.least_squares(lambda p: np.log(_model(fs_, p)) - y, p0,
                                 bounds=(lb, ub), x_scale="jac", method="trf")
    dof = max(1, len(y) - len(res.x))
    s2 = 2 * res.cost / dof
    try:
        cov = np.linalg.pinv(res.jac.T @ res.jac) * s2
        err = np.sqrt(np.clip(np.diag(cov), 0, None))
    except np.linalg.LinAlgError:
        err = np.full(len(res.x), np.nan)

    fitted = []
    for i, (fm, (fi, ln_a, ln_g), (efi, eln_a, eln_g)) in enumerate(
            zip(modes, res.x[2:].reshape(-1, 3), err[2:].reshape(-1, 3))):
        a, g = np.exp(ln_a), np.exp(ln_g)
        fitted.append(ModeFit(index=SCHUMANN_MODES_HZ.index(fm) + 1 if fm in SCHUMANN_MODES_HZ else i + 1,
                              freq_hz=fi, freq_err_hz=efi,
                              amplitude=a, amplitude_err=a * eln_a,
                              width_hz=g, width_err_hz=g * eln_g))
    return SchumannFit(modes=fitted, bg_amplitude=float(np.exp(res.x[0])),
                       bg_exponent=float(res.x[1]), f=fs_, psd=ps_,
                       rms_log_residual=float(np.sqrt(np.mean(res.fun ** 2)) / np.log(10)))


# ---------------------------------------------------------------------------
# Sferic / transient detection
# ---------------------------------------------------------------------------

@dataclass
class Sferic:
    time_s: float        # time of the envelope peak from the start of the record
    peak: float          # peak absolute band-passed amplitude (input units)
    snr_db: float        # peak window energy over the median background
    duration_s: float


class SfericDetector:
    """Streaming energy detector for impulsive events (sferics).

    The signal is band-passed (default 300 Hz .. 0.45 fs, above the ELF band and
    the bulk of the mains energy), squared and integrated in ``window_s``
    windows.  Windows whose energy exceeds the local background (median window
    energy of the surrounding ``background_s`` block) by ``threshold_db`` are
    grouped into events, merging detections closer than ``merge_s``.  The
    first ``holdoff_s`` seconds (e.g. while the mains canceller converges) are
    ignored.  :meth:`process` can be fed chunk by chunk; :meth:`events`
    evaluates the detections so far.
    """

    def __init__(self, fs: float, band=(300.0, 20e3), window_s: float = 1e-3,
                 threshold_db: float = 15.0, merge_s: float = 5e-3,
                 background_s: float = 1.0, holdoff_s: float = 0.0):
        self.fs = float(fs)
        lo, hi = band[0], min(band[1], 0.45 * fs)
        self.sos = signal.butter(4, (lo, hi), btype="bandpass", fs=fs, output="sos")
        self.win = max(1, int(round(window_s * fs)))
        self.dt = self.win / self.fs
        self.threshold = 10 ** (threshold_db / 10)
        self.merge = max(1, int(round(merge_s / self.dt)))
        self.bg_len = max(10, int(round(background_s / self.dt)))
        self.holdoff = int(round(holdoff_s / self.dt))
        self._zi = np.zeros((self.sos.shape[0], 2))
        self._carry = np.zeros(0)
        self._energy: list[np.ndarray] = []
        self._peak: list[np.ndarray] = []

    def process(self, x: np.ndarray) -> None:
        y, self._zi = signal.sosfilt(self.sos, np.asarray(x, float), zi=self._zi)
        y = np.concatenate([self._carry, y])
        n = len(y) // self.win * self.win
        blocks = y[:n].reshape(-1, self.win)
        self._energy.append(np.mean(blocks ** 2, axis=1))
        self._peak.append(np.max(np.abs(blocks), axis=1))
        self._carry = y[n:]

    def _background(self, e: np.ndarray) -> np.ndarray:
        """Median energy per background block, linearly interpolated."""
        nb = max(1, len(e) // self.bg_len)
        edges = np.linspace(0, len(e), nb + 1).astype(int)
        med = np.array([np.median(e[a:b]) for a, b in zip(edges[:-1], edges[1:])])
        centres = (edges[:-1] + edges[1:]) / 2
        return np.interp(np.arange(len(e)), centres, med) + 1e-300

    def events(self) -> list[Sferic]:
        if not self._energy:
            return []
        e = np.concatenate(self._energy)[self.holdoff:]
        pk = np.concatenate(self._peak)[self.holdoff:]
        if not len(e):
            return []
        ratio = e / self._background(e)
        hot = np.flatnonzero(ratio > self.threshold)
        out: list[Sferic] = []
        if not len(hot):
            return out
        groups = np.split(hot, np.flatnonzero(np.diff(hot) > self.merge) + 1)
        for g in groups:
            i = g[np.argmax(ratio[g])]
            out.append(Sferic(time_s=(i + self.holdoff + 0.5) * self.dt, peak=float(pk[g].max()),
                              snr_db=float(10 * np.log10(ratio[i])),
                              duration_s=float((g[-1] - g[0] + 1) * self.dt)))
        return out
