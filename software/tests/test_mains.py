# SPDX-License-Identifier: CERN-OHL-W-2.0
import numpy as np
import pytest

from elara.dsp import MainsCanceller, estimate_mains_frequency

FS = 48000.0


def _hum(t, f_inst, n_harm, rng, amp=0.05):
    phi = 2 * np.pi * np.cumsum(np.broadcast_to(f_inst, t.shape)) / FS
    return sum(amp / k * np.cos(k * phi + rng.uniform(0, 2 * np.pi)) for k in range(1, n_harm + 1))


def _tone_amp(x, t, f):
    w = np.hanning(len(t))
    return 2 * abs(np.sum(x * w * np.exp(-2j * np.pi * f * t))) / w.sum()


def _run(x, nominal=50.0, chunks=7):
    mc = MainsCanceller(FS, nominal, f_max=2000.0,
                        f_init=estimate_mains_frequency(x, FS, nominal))
    return np.concatenate([mc.process(c) for c in np.array_split(x, chunks)]), mc


@pytest.mark.parametrize("nominal, f_true", [(50.0, 50.07), (60.0, 59.94)])
def test_stable_hum_rejection_over_60db(nominal, f_true):
    rng = np.random.default_rng(1)
    t = np.arange(int(12 * FS)) / FS
    n_harm = int(2000 // nominal)                     # harmonics up to 2 kHz
    hum = _hum(t, f_true, n_harm, rng)
    noise = 1e-6 * rng.standard_normal(len(t))
    y, mc = _run(hum + noise, nominal)
    assert mc.n_harm == n_harm
    late = slice(int(6 * FS), None)
    resid = y[late] - noise[late]
    rejection = 10 * np.log10(np.mean(hum[late] ** 2) / np.mean(resid ** 2))
    assert rejection > 60, rejection
    assert abs(mc.freq - f_true) < 1e-3


def test_45hz_schumann_tone_untouched():
    rng = np.random.default_rng(2)
    t = np.arange(int(12 * FS)) / FS
    tone = 1e-3 * np.cos(2 * np.pi * 45.0 * t)
    hum = _hum(t, 50.05, 40, rng)
    y, _ = _run(hum + tone + 1e-6 * rng.standard_normal(len(t)))
    late = slice(int(6 * FS), None)
    change_db = 20 * np.log10(_tone_amp(y[late], t[late], 45.0) / 1e-3)
    assert abs(change_db) < 0.5, change_db
    # And without any hum the canceller must not eat the tone either.
    y0, _ = _run(tone + 1e-6 * rng.standard_normal(len(t)))
    assert abs(20 * np.log10(_tone_amp(y0[late], t[late], 45.0) / 1e-3)) < 0.5


def test_tracks_drifting_mains():
    rng = np.random.default_rng(3)
    t = np.arange(int(20 * FS)) / FS
    f_inst = 50.0 + 0.2 * np.sin(2 * np.pi * t / 120.0)      # slow drift to +0.2 Hz
    hum = _hum(t, f_inst, 20, rng)
    y, mc = _run(hum + 1e-6 * rng.standard_normal(len(t)))
    late = slice(int(8 * FS), None)
    rejection = 10 * np.log10(np.mean(hum[late] ** 2) / np.mean(y[late] ** 2))
    assert rejection > 50, rejection
    assert abs(mc.freq - f_inst[-1]) < 0.01


def test_chunking_does_not_change_output():
    rng = np.random.default_rng(4)
    t = np.arange(int(3 * FS)) / FS
    x = _hum(t, 50.1, 10, rng) + 1e-4 * rng.standard_normal(len(t))
    y1, _ = _run(x, chunks=1)
    y2, _ = _run(x, chunks=13)
    np.testing.assert_allclose(y1, y2, atol=1e-9)


def test_frequency_estimate():
    rng = np.random.default_rng(5)
    t = np.arange(int(4 * FS)) / FS
    x = _hum(t, 49.83, 5, rng) + 1e-3 * rng.standard_normal(len(t))
    assert abs(estimate_mains_frequency(x, FS, 50.0) - 49.83) < 0.01
