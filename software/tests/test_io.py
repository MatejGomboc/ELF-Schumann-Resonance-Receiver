# SPDX-License-Identifier: CERN-OHL-W-2.0
import json

import numpy as np
import pytest

from elara import io


def _data(n=4800):
    rng = np.random.default_rng(0)
    return np.clip(0.3 * rng.standard_normal((n, 2)), -0.99, 0.99)


def test_wav24_roundtrip_with_sidecar(tmp_path):
    pytest.importorskip("soundfile")
    d = _data()
    p = tmp_path / "rec.wav"
    io.write_wav(p, d, 48000, metadata=io.default_metadata(48000, note="x"))
    back, fs = io.read_audio(p)
    assert fs == 48000 and back.shape == d.shape
    assert np.max(np.abs(back - d)) < 2 ** -22
    meta = json.loads((tmp_path / "rec.json").read_text())
    assert meta["channel_roles"] == ["antenna", "noise_reference"]
    assert meta["note"] == "x" and meta["preamp_gain"] == 101.0
    fs2, it = io.iter_chunks(p, chunk_s=0.03)
    np.testing.assert_allclose(np.concatenate(list(it)), back)


def test_scipy_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "_soundfile", lambda: None)
    d = _data()
    p = tmp_path / "fallback.wav"
    io.write_wav(p, d, 48000)
    back, fs = io.read_audio(p)
    assert fs == 48000 and np.max(np.abs(back - d)) < 1e-6
    _, it = io.iter_chunks(p, chunk_s=0.01)
    np.testing.assert_allclose(np.concatenate(list(it)), back)


def test_hdf5_roundtrip_with_timestamps(tmp_path):
    pytest.importorskip("h5py")
    import h5py
    d = _data()
    p = tmp_path / "rec.h5"
    with io.open_writer(p, 48000) as w:
        w.write(d[:2000], timestamp=1000.0)
        w.write(d[2000:], timestamp=1000.0 + 2000 / 48000)
    back, fs = io.read_audio(p)
    assert fs == 48000
    np.testing.assert_allclose(back, d, atol=1e-7)
    with h5py.File(p) as f:
        np.testing.assert_allclose(f["timestamps"][:], [[0, 1000.0], [2000, 1000.0 + 2000 / 48000]])
    assert io.read_metadata(p)["sample_rate"] == 48000
    _, it = io.iter_chunks(p, chunk_s=0.01)
    np.testing.assert_allclose(np.concatenate(list(it)), back)
