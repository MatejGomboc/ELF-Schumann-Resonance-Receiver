# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Synthetic ELARA recordings for demos and tests.

The antenna voltage is built from

* a pink-ish (1/f) natural background plus the instrument noise floor,
* seven Lorentzian Schumann modes,
* mains hum with harmonics to 2 kHz and a slow, bounded frequency drift,
* Poisson-distributed sferics (damped VLF bursts with a slow ELF tail),

then passed through the modelled analogue front-end (:mod:`elara.frontend`)
in the frequency domain.  The R channel is correlated "system" noise (1/f
noise plus two spurious tones) that also leaks into L through a coupling
filter, plus independent ADC noise on each channel.  Output is in ADC
full-scale units, shape ``(n, 2)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import signal

from .frontend import DEFAULT_FRONTEND, SCHUMANN_MODES_HZ, FrontEnd

#: Default mode Q factors and peak amplitude spectral densities at the antenna [V/sqrt(Hz)].
DEFAULT_Q = (4.5, 5.0, 6.0, 6.5, 7.0, 7.0, 7.5)
DEFAULT_SR_ASD = (4.0e-6, 3.2e-6, 2.8e-6, 2.3e-6, 2.0e-6, 1.7e-6, 1.5e-6)


@dataclass
class SimConfig:
    duration_s: float = 30.0
    fs: float = 192000.0
    mains_hz: float = 50.0
    seed: int = 0
    sr_freqs: tuple = SCHUMANN_MODES_HZ
    sr_q: tuple = DEFAULT_Q
    sr_asd: tuple = DEFAULT_SR_ASD
    bg_asd_10hz: float = 1.5e-6          # natural background at 10 Hz [V/sqrt(Hz)], ~1/f PSD
    instrument_asd: float = 45.8e-9      # antenna-referred front-end noise floor at SR1 (SPICE, PLAN.md 3.3)
    hum_v: float = 2e-3                  # mains fundamental at the antenna [V peak]
    hum_harmonics: dict = field(default_factory=lambda: {3: 0.3, 5: 0.15, 7: 0.08, 9: 0.04})
    hum_other_rel: float = 0.01          # other harmonics, relative to fundamental / k
    hum_fmax: float = 2000.0
    drift_hz: float = 0.15               # peak slow mains-frequency deviation
    sferic_rate_hz: float = 3.0
    sferic_v: float = 20e-3              # median sferic (VLF burst) peak at the antenna [V]
    sysnoise_asd_10hz: float = 3e-5      # correlated system noise at 10 Hz [FS/sqrt(Hz)]
    sys_tones: tuple = ((17.5, 1e-4), (31.0, 6e-5))   # (Hz, FS peak) spurs in system noise
    adc_asd: float = 41e-9 / 2.5         # ADC noise [FS/sqrt(Hz)]: 41 nV/sqrt(Hz) at VINL, FS +-2.5 V (simulations/system)
    frontend: FrontEnd = DEFAULT_FRONTEND


def _coloured_noise(rng, n, fs, psd_fn):
    """Gaussian noise with one-sided PSD ``psd_fn(f)`` (units^2/Hz) via FFT shaping."""
    f = np.fft.rfftfreq(n, 1 / fs)
    spec = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
    spec *= np.sqrt(psd_fn(f) * fs * n / 4.0)
    spec[0] = 0.0
    return f, spec


def simulate(cfg: SimConfig | None = None, **overrides):
    """Generate a synthetic recording.  Returns ``(data, fs, truth)``."""
    cfg = cfg or SimConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    rng = np.random.default_rng(cfg.seed)
    fs, n = cfg.fs, int(round(cfg.duration_s * cfg.fs))
    t = np.arange(n) / fs

    # --- natural field + instrument noise at the antenna (frequency domain) ---
    def antenna_psd(f):
        fc = np.maximum(f, 0.5)
        p = cfg.bg_asd_10hz ** 2 * (10.0 / fc) + cfg.instrument_asd ** 2
        for f0, q, a in zip(cfg.sr_freqs, cfg.sr_q, cfg.sr_asd):
            g = f0 / (2 * q)
            p = p + a ** 2 / (1 + ((f - f0) / g) ** 2)
        return p

    f, spec = _coloured_noise(rng, n, fs, antenna_psd)

    # --- mains hum with slow bounded drift (time domain) ---
    f_mains = (cfg.mains_hz + cfg.drift_hz * np.sin(2 * np.pi * t / max(120.0, 4 * cfg.duration_s)
                                                  + rng.uniform(0, 2 * np.pi)))
    phi = 2 * np.pi * np.cumsum(f_mains) / fs
    x_ant = np.zeros(n)
    kmax = int(min(cfg.hum_fmax, 0.45 * fs) // cfg.mains_hz)
    for k in range(1, kmax + 1):
        rel = 1.0 if k == 1 else cfg.hum_harmonics.get(k, cfg.hum_other_rel / k)
        x_ant += cfg.hum_v * rel * np.cos(k * phi + rng.uniform(0, 2 * np.pi))

    # --- sferics ---
    n_sf = rng.poisson(cfg.sferic_rate_hz * cfg.duration_s)
    sf_times = np.sort(rng.uniform(0.02, cfg.duration_s - 0.02, n_sf)) if n_sf else np.zeros(0)
    sf_len = int(0.01 * fs)
    ts = np.arange(sf_len) / fs
    for t0 in sf_times:
        a = cfg.sferic_v * rng.lognormal(0.0, 0.7)
        fc = min(rng.uniform(3e3, 12e3), 0.4 * fs)
        tau = rng.uniform(0.2e-3, 0.5e-3)
        burst = np.exp(-ts / tau) * np.sin(2 * np.pi * fc * ts)
        tail = 0.002 * (ts / 1.5e-3) * np.exp(1 - ts / 1.5e-3)       # ELF "slow tail"
        i0 = int(t0 * fs)
        seg = slice(i0, min(n, i0 + sf_len))
        x_ant[seg] += a * (burst + tail)[: seg.stop - seg.start]

    spec += np.fft.rfft(x_ant)
    left = np.fft.irfft(spec * cfg.frontend.response(f), n)   # antenna V -> ADC FS

    # --- correlated system noise (appears in R, and via a coupling filter in L) ---
    _, sspec = _coloured_noise(rng, n, fs,
                               lambda f: cfg.sysnoise_asd_10hz ** 2 * 10.0 / np.maximum(f, 0.5))
    sysn = np.fft.irfft(sspec, n)
    for ft, a in cfg.sys_tones:
        sysn += a * np.sin(2 * np.pi * ft * t + rng.uniform(0, 2 * np.pi))
    b, a_ = signal.butter(1, min(300.0, 0.4 * fs), fs=fs)
    left += 0.8 * signal.lfilter(b, a_, sysn)
    right = sysn.copy()

    adc_sigma = cfg.adc_asd * np.sqrt(fs / 2)
    left += adc_sigma * rng.standard_normal(n)
    right += adc_sigma * rng.standard_normal(n)

    truth = {
        "sample_rate": fs,
        "duration_s": cfg.duration_s,
        "mains_hz_nominal": cfg.mains_hz,
        "mains_hz_start": float(f_mains[0]),
        "mains_hz_end": float(f_mains[-1]),
        "sr_freqs_hz": list(cfg.sr_freqs),
        "sr_q": list(cfg.sr_q),
        "sr_asd_v_rthz": list(cfg.sr_asd),
        "sferic_times_s": [float(x) for x in sf_times],
        "system_tones_hz": [ft for ft, _ in cfg.sys_tones],
    }
    return np.column_stack([left, right]), fs, truth
