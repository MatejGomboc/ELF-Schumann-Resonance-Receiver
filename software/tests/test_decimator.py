# SPDX-License-Identifier: CERN-OHL-W-2.0
import numpy as np
import pytest

from elara.dsp import Decimator


@pytest.mark.parametrize("fs_in, factors", [(192000, [4, 4, 4, 3]), (96000, [4, 4, 3, 2]),
                                            (48000, [4, 4, 3])])
def test_stage_plan(fs_in, factors):
    assert Decimator(fs_in, 1000).factors == factors


def test_passband_flat_and_alias_rejection():
    d = Decimator(192000, 1000)
    pb = d.frequency_response(np.linspace(0.5, 400, 200))
    assert np.max(np.abs(20 * np.log10(pb))) < 0.02
    # Everything that would alias into 0..400 Hz at the output is >= 100 dB down.
    alias = np.concatenate([np.linspace(600, 1400, 50), np.linspace(1600, 2400, 50),
                            np.linspace(47600, 48400, 20)])
    assert 20 * np.log10(d.frequency_response(alias).max()) < -99


def test_streaming_equivalence_and_tone():
    fs = 48000
    rng = np.random.default_rng(0)
    t = np.arange(fs * 6) / fs
    x = np.column_stack([np.sin(2 * np.pi * 7.83 * t) + 1e-3 * rng.standard_normal(len(t)),
                         np.sin(2 * np.pi * 3100 * t)])            # 3.1 kHz must vanish
    d = Decimator(fs, 1000)
    y_once = d.process(x)
    d.reset()
    y_chunks = np.concatenate([d.process(c) for c in np.array_split(x, 17)])
    assert y_once.shape == (6000, 2)
    np.testing.assert_allclose(y_chunks, y_once, atol=1e-12)
    # Tone amplitude preserved, delayed by the reported group delay.
    n0 = 1000
    tt = np.arange(len(y_once)) / 1000.0 - d.delay_s
    ref = np.sin(2 * np.pi * 7.83 * tt)
    assert np.max(np.abs(y_once[n0:, 0] - ref[n0:])) < 1e-3
    assert np.max(np.abs(y_once[n0:, 1])) < 1e-5


def test_bad_ratio_rejected():
    with pytest.raises(ValueError):
        Decimator(44100, 1000)
