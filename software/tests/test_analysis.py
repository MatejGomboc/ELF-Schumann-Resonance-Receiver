# SPDX-License-Identifier: CERN-OHL-W-2.0
import numpy as np

from elara.analysis import SfericDetector, fit_schumann, welch_psd
from elara.analysis import _model
from elara.frontend import DEFAULT_FRONTEND, SCHUMANN_MODES_HZ
from elara.simulate import simulate


def test_fit_recovers_noise_free_model():
    f = np.arange(0, 60, 0.1)
    p = [np.log(1e-12), 1.0]
    for f0, q in zip(SCHUMANN_MODES_HZ, (4.5, 5, 6, 6.5, 7, 7, 7.5)):
        p += [f0 + 0.1, np.log(4e-12), np.log(f0 / (2 * q))]
    fit = fit_schumann(f, _model(np.maximum(f, 0.1), np.array(p)))
    for m, f0 in zip(fit.modes, SCHUMANN_MODES_HZ):
        assert abs(m.freq_hz - (f0 + 0.1)) < 1e-3
    assert abs(fit.bg_exponent - 1.0) < 1e-3


def test_fit_recovers_simulated_schumann_modes():
    # One hour of clean ELF-rate data (no hum, sferics or system noise).
    x, fs, truth = simulate(duration_s=3600, fs=250, hum_v=0, sferic_rate_hz=0,
                            sysnoise_asd_10hz=0, sys_tones=(), seed=2)
    f, p = welch_psd(x[:, 0], fs, resolution_hz=0.25)
    fit = fit_schumann(f, DEFAULT_FRONTEND.to_antenna_psd(f, p))
    assert len(fit.modes) == 7
    for m, f0, q, asd in zip(fit.modes, truth["sr_freqs_hz"], truth["sr_q"],
                             truth["sr_asd_v_rthz"]):
        err = abs(m.freq_hz - f0)
        assert err < 0.1, (m.index, m.freq_hz, f0)
        assert err < 3 * m.freq_err_hz + 0.02                   # honest error bars
        assert abs(m.q / q - 1) < 0.3
        assert abs(np.sqrt(m.amplitude) / asd - 1) < 0.15


def test_sferic_detector_finds_impulses():
    fs = 48000.0
    rng = np.random.default_rng(0)
    x = 1e-4 * rng.standard_normal(int(10 * fs))
    times = np.array([1.2345, 3.5, 3.52, 7.777, 9.1])
    ts = np.arange(int(0.005 * fs)) / fs
    burst = np.exp(-ts / 3e-4) * np.sin(2 * np.pi * 6000 * ts)
    for t0 in times:
        i = int(t0 * fs)
        x[i:i + len(burst)] += 5e-3 * burst
    det = SfericDetector(fs)
    for c in np.array_split(x, 9):
        det.process(c)
    ev = det.events()
    assert len(ev) == len(times)
    for e, t0 in zip(ev, times):
        assert abs(e.time_s - t0) < 2e-3
        assert e.snr_db > 15


def test_welch_psd_level():
    fs = 1000.0
    rng = np.random.default_rng(1)
    x = rng.standard_normal(200_000) * np.sqrt(fs / 2 * 4e-6)      # 4e-6 /Hz white
    f, p = welch_psd(x, fs, 0.5)
    assert abs(np.median(p[5:]) / 4e-6 - 1) < 0.05
