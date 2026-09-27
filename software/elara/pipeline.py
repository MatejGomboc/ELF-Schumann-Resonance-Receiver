# SPDX-License-Identifier: CERN-OHL-W-2.0
"""End-to-end processing of a recording: clean, decimate, analyse.

Signal flow (the full-rate part is streamed chunk by chunk)::

    L (fs) --MainsCanceller--+--SfericDetector (300 Hz .. 20 kHz)
                             +--Decimator--> L_elf --+
    R (fs) ------------------------Decimator--> R_elf --+--ReferenceCanceller--> L_clean
    L (fs) ------------------------Decimator--> L_raw (for comparison only)

    L_clean --> Welch PSD --> front-end correction (V/sqrt(Hz) at antenna)
            --> Lorentzian fit;  spectrogram
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field

import numpy as np

from .analysis import SchumannFit, Sferic, SfericDetector, fit_schumann, spectrogram, welch_psd
from .dsp import Decimator, MainsCanceller, estimate_mains_frequency, subtract_reference
from .frontend import DEFAULT_FRONTEND, FrontEnd
from .io import iter_chunks


@dataclass
class AnalysisResult:
    fs: float
    elf_rate: float
    mains_hz: float
    mains_tracked_hz: float | None
    f: np.ndarray                   # PSD frequency axis [Hz]
    psd_raw: np.ndarray             # antenna-referred PSD before cleaning [V^2/Hz]
    psd_clean: np.ndarray           # after mains + reference cancellation [V^2/Hz]
    fit: SchumannFit | None
    spec_f: np.ndarray
    spec_t: np.ndarray
    spec: np.ndarray                # antenna-referred spectrogram [V^2/Hz]
    sferics: list[Sferic] = field(default_factory=list)
    duration_s: float = 0.0


def analyse_file(path, mains_hz: float = 50.0, elf_rate: float = 1000.0,
                 resolution_hz: float = 0.25, spec_resolution_hz: float = 0.5,
                 fmax: float = 60.0, cancel_mains: bool = True, use_reference: bool = True,
                 detect_sferics: bool = True, fit: bool = True,
                 frontend: FrontEnd = DEFAULT_FRONTEND, chunk_s: float = 4.0) -> AnalysisResult:
    fs, chunks = iter_chunks(path, chunk_s)
    dec_raw = Decimator(fs, elf_rate)
    dec = Decimator(fs, elf_rate)
    mc = det = None
    raw_parts, clean_parts = [], []
    n_total = 0
    for chunk in chunks:
        left = chunk[:, 0]
        right = chunk[:, 1] if chunk.shape[1] > 1 else np.zeros_like(left)
        n_total += len(left)
        raw_parts.append(dec_raw.process(left))
        if cancel_mains:
            if mc is None:
                f0 = estimate_mains_frequency(left, fs, mains_hz)
                mc = MainsCanceller(fs, mains_hz, f_init=f0)
            left = mc.process(left)
        if detect_sferics:
            det = det or SfericDetector(fs, holdoff_s=1.5 if cancel_mains else 0.0)
            det.process(left)
        clean_parts.append(dec.process(np.column_stack([left, right])))

    # Discard the start-up transient (decimator fill, canceller convergence) before
    # the reference stage, so start-up hum cannot bias its cross-spectra.
    skip = min(sum(len(p) for p in raw_parts) // 5, int(3.0 * elf_rate))
    l_raw = np.concatenate(raw_parts)[skip:]
    elf = np.concatenate(clean_parts)[skip:]
    l_clean = elf[:, 0]
    if use_reference and np.any(elf[:, 1]):
        # 1 Hz STFT bins, two frames per second -> cross-spectra averaged over ~30 s.
        l_clean = subtract_reference(l_clean, elf[:, 1], nfft=2 * int(elf_rate // 2),
                                     tau_frames=60.0)

    f, p_raw = welch_psd(l_raw, elf_rate, resolution_hz, fmax=fmax)
    _, p_clean = welch_psd(l_clean, elf_rate, resolution_hz, fmax=fmax)
    p_raw = frontend.to_antenna_psd(f, p_raw)
    p_clean = frontend.to_antenna_psd(f, p_clean)

    column_s = max(5.0, len(l_clean) / elf_rate / 200)       # at most ~200 columns
    sf, st, sxx = spectrogram(l_clean, elf_rate, spec_resolution_hz, column_s, fmax=fmax)
    sxx = frontend.to_antenna_psd(sf, sxx)
    st = st + skip / elf_rate

    fit_res = None
    if fit:
        excl = ((mains_hz - 1.0, mains_hz + 1.0),)
        try:
            fit_res = fit_schumann(f, p_clean, fmax=min(48.0, fmax), exclude=excl)
        except (ValueError, RuntimeError):
            fit_res = None

    return AnalysisResult(
        fs=fs, elf_rate=elf_rate, mains_hz=mains_hz,
        mains_tracked_hz=None if mc is None else mc.freq,
        f=f, psd_raw=p_raw, psd_clean=p_clean, fit=fit_res,
        spec_f=sf, spec_t=st, spec=sxx,
        sferics=det.events() if det else [], duration_s=n_total / fs)


def write_modes_csv(path, fit: SchumannFit) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["mode", "freq_hz", "freq_err_hz", "hwhm_hz", "hwhm_err_hz", "q", "q_err",
                    "peak_asd_uV_rtHz", "peak_asd_err_uV_rtHz"])
        for m in fit.modes:
            asd = np.sqrt(m.amplitude)
            w.writerow([f"SR{m.index}", f"{m.freq_hz:.3f}", f"{m.freq_err_hz:.3f}",
                        f"{m.width_hz:.3f}", f"{m.width_err_hz:.3f}", f"{m.q:.2f}",
                        f"{m.q_err:.2f}", f"{asd * 1e6:.4f}",
                        f"{0.5 * asd * m.amplitude_err / m.amplitude * 1e6:.4f}"])


def write_sferics_csv(path, sferics: list[Sferic]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time_s", "peak_fs", "snr_db", "duration_ms"])
        for s in sferics:
            w.writerow([f"{s.time_s:.4f}", f"{s.peak:.3e}", f"{s.snr_db:.1f}",
                        f"{s.duration_s * 1e3:.1f}"])
