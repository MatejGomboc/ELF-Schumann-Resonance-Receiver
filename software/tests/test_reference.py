# SPDX-License-Identifier: CERN-OHL-W-2.0
import numpy as np
from scipy import signal

from elara.dsp import ReferenceCanceller, subtract_reference


def test_correlated_noise_removed_signal_kept():
    rng = np.random.default_rng(0)
    fs, n = 1000.0, 400_000
    s = rng.standard_normal(n)                              # antenna signal
    r = signal.lfilter(*signal.butter(1, 30, fs=fs), rng.standard_normal(n)) * 5
    b, a = signal.butter(2, 120, fs=fs)
    coupled = 0.8 * signal.lfilter(b, a, r)                 # system noise leaking into L
    y = subtract_reference(s + coupled, r, nfft=1000, tau_frames=100)
    late = slice(n // 4, None)
    resid_db = 10 * np.log10(np.var(y[late] - s[late]) / np.var(coupled[late]))
    assert resid_db < -18, resid_db
    assert abs(10 * np.log10(np.var(y[late]) / np.var(s[late]))) < 0.2


def test_uncorrelated_reference_is_harmless_and_aligned():
    rng = np.random.default_rng(1)
    s = rng.standard_normal(100_000)
    y = subtract_reference(s, rng.standard_normal(len(s)), nfft=512)
    assert len(y) == len(s)
    assert abs(10 * np.log10(np.var(y[10_000:]) / np.var(s[10_000:]))) < 0.2
    # A zero reference is an exact identity (perfect-reconstruction WOLA).
    np.testing.assert_allclose(subtract_reference(s, np.zeros_like(s), nfft=512), s, atol=1e-12)


def test_streaming_latency():
    rc = ReferenceCanceller(nfft=256)
    x = np.zeros(1000)
    x[100] = 1.0
    out = np.concatenate([rc.process(c, np.zeros_like(c)) for c in np.array_split(x, 7)])
    assert np.argmax(out) == 100 + rc.latency
