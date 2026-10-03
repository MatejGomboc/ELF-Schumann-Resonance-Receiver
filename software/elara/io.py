# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Reading, writing and live capture of ELARA recordings.

Samples are float arrays of shape ``(n, channels)`` in ADC full-scale units
(channel 0 = antenna, channel 1 = noise reference).

Optional dependencies are imported lazily:

* ``soundfile`` -- WAV/FLAC reading and streaming WAV writing (otherwise
  ``scipy.io.wavfile`` is used for WAV only);
* ``sounddevice`` -- live capture from the USB audio interface (AES3 or S/PDIF input);
* ``h5py`` -- HDF5 recordings with timestamps and metadata.

WAV recordings get a ``<name>.json`` sidecar holding the metadata
(sample rate, start time, gain, channel roles, front-end constants).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import numpy as np

from .frontend import CHANNEL_ROLES, DEFAULT_FRONTEND, FrontEnd


def _soundfile():
    try:
        import soundfile
        return soundfile
    except (ImportError, OSError):
        return None


def default_metadata(fs: float, frontend: FrontEnd = DEFAULT_FRONTEND,
                     start_time: float | None = None, **extra) -> dict:
    start = time.time() if start_time is None else start_time
    meta = {
        "instrument": "ELARA",
        "sample_rate": float(fs),
        "start_time_unix": start,
        "start_time_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "channel_roles": list(CHANNEL_ROLES),
        "units": "ADC full scale (1.0 = 2.5 V differential peak)",
        "preamp_gain": frontend.midband_gain,
        "frontend": frontend.as_dict(),
    }
    meta.update(extra)
    return meta


def sidecar_path(path) -> Path:
    return Path(path).with_suffix(".json")


def read_metadata(path) -> dict:
    """Metadata from an HDF5 file's attributes or a WAV/FLAC JSON sidecar."""
    path = Path(path)
    if path.suffix.lower() in (".h5", ".hdf5"):
        import h5py
        with h5py.File(path, "r") as f:
            return json.loads(f.attrs.get("metadata", "{}"))
    side = sidecar_path(path)
    return json.loads(side.read_text()) if side.exists() else {}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _int_to_float(data: np.ndarray) -> np.ndarray:
    if data.dtype.kind == "f":
        return data.astype(float)
    if data.dtype == np.uint8:
        return (data.astype(float) - 128) / 128
    return data.astype(float) / float(np.iinfo(data.dtype).max + 1)


def read_audio(path) -> tuple[np.ndarray, float]:
    """Read a whole WAV/FLAC/HDF5 file.  Returns ``(data (n, ch), fs)``."""
    path = Path(path)
    if path.suffix.lower() in (".h5", ".hdf5"):
        import h5py
        with h5py.File(path, "r") as f:
            return f["samples"][:].astype(float), float(f.attrs["sample_rate"])
    sf = _soundfile()
    if sf is not None:
        data, fs = sf.read(str(path), dtype="float64", always_2d=True)
        return data, float(fs)
    from scipy.io import wavfile
    fs, data = wavfile.read(path)
    data = _int_to_float(data)
    return (data[:, None] if data.ndim == 1 else data), float(fs)


def iter_chunks(path, chunk_s: float = 1.0) -> tuple[float, Iterator[np.ndarray]]:
    """Stream a recording in chunks of ``chunk_s`` seconds.

    Returns ``(fs, iterator)``; memory use is bounded by one chunk for
    WAV/FLAC (with soundfile) and HDF5.
    """
    path = Path(path)
    if path.suffix.lower() in (".h5", ".hdf5"):
        import h5py
        with h5py.File(path, "r") as f:
            fs = float(f.attrs["sample_rate"])

        def gen_h5():
            with h5py.File(path, "r") as f:
                ds, step = f["samples"], int(chunk_s * fs)
                for i in range(0, len(ds), step):
                    yield ds[i:i + step].astype(float)
        return fs, gen_h5()

    sf = _soundfile()
    if sf is not None:
        fs = float(sf.info(str(path)).samplerate)
        blocks = sf.blocks(str(path), blocksize=int(chunk_s * fs), dtype="float64",
                           always_2d=True)
        return fs, blocks

    from scipy.io import wavfile
    fs_i, data = wavfile.read(path, mmap=True)
    step = int(chunk_s * fs_i)

    def gen_wav():
        for i in range(0, len(data), step):
            d = _int_to_float(np.asarray(data[i:i + step]))
            yield d[:, None] if d.ndim == 1 else d
    return float(fs_i), gen_wav()


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

class WavWriter:
    """Streaming WAV writer (24-bit PCM or 32-bit float) with a JSON sidecar.

    Without ``soundfile`` the samples are buffered in memory and written with
    ``scipy.io.wavfile`` on close (24-bit is then stored as 32-bit PCM).
    """

    def __init__(self, path, fs: float, channels: int = 2, subtype: str = "PCM_24",
                 metadata: dict | None = None):
        self.path, self.fs = Path(path), float(fs)
        self.subtype = subtype
        self.meta = metadata if metadata is not None else default_metadata(fs)
        self.meta.setdefault("wav_subtype", subtype)
        self._sf = _soundfile()
        self._buf: list[np.ndarray] = []
        if self._sf is not None:
            self._f = self._sf.SoundFile(str(self.path), "w", samplerate=int(fs),
                                         channels=channels, subtype=subtype, format="WAV")

    def write(self, data: np.ndarray) -> None:
        data = np.clip(np.asarray(data, float), -1.0, 1.0 - 2.0 ** -23)
        if self._sf is not None:
            self._f.write(data)
        else:
            self._buf.append(data)

    def close(self) -> None:
        if self._sf is not None:
            self._f.close()
        else:
            from scipy.io import wavfile
            data = np.concatenate(self._buf) if self._buf else np.zeros((0, 2))
            if self.subtype == "FLOAT":
                wavfile.write(self.path, int(self.fs), data.astype(np.float32))
            else:
                wavfile.write(self.path, int(self.fs), np.round(data * 2 ** 31).astype(np.int32))
        sidecar_path(self.path).write_text(json.dumps(self.meta, indent=2))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Hdf5Writer:
    """Append-only HDF5 recording.

    Layout: ``/samples`` (n, channels) float32, resizable; ``/timestamps``
    (m, 2) float64 rows of ``(first sample index, unix time)`` for every
    appended block, so capture-clock jitter can be reconstructed; the root
    attribute ``metadata`` is a JSON string, ``sample_rate`` a float.
    """

    def __init__(self, path, fs: float, channels: int = 2, metadata: dict | None = None,
                 compression: str | None = "gzip"):
        import h5py
        self.meta = metadata if metadata is not None else default_metadata(fs)
        self._f = h5py.File(path, "w")
        self._f.attrs["sample_rate"] = float(fs)
        self._f.attrs["metadata"] = json.dumps(self.meta)
        self._f.attrs["channel_roles"] = json.dumps(self.meta.get("channel_roles", CHANNEL_ROLES))
        self._s = self._f.create_dataset("samples", shape=(0, channels), maxshape=(None, channels),
                                         dtype="f4", chunks=(min(65536, int(fs)), channels),
                                         compression=compression)
        self._t = self._f.create_dataset("timestamps", shape=(0, 2), maxshape=(None, 2),
                                         dtype="f8", chunks=(1024, 2))

    def write(self, data: np.ndarray, timestamp: float | None = None) -> None:
        data = np.asarray(data, np.float32)
        n0 = self._s.shape[0]
        self._s.resize(n0 + len(data), axis=0)
        self._s[n0:] = data
        self._t.resize(self._t.shape[0] + 1, axis=0)
        self._t[-1] = (n0, time.time() if timestamp is None else timestamp)

    def close(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open_writer(path, fs: float, channels: int = 2, metadata: dict | None = None,
                subtype: str = "PCM_24"):
    """Pick :class:`Hdf5Writer` for ``.h5``/``.hdf5`` paths, else :class:`WavWriter`."""
    if Path(path).suffix.lower() in (".h5", ".hdf5"):
        return Hdf5Writer(path, fs, channels, metadata)
    return WavWriter(path, fs, channels, subtype, metadata)


def write_wav(path, data: np.ndarray, fs: float, subtype: str = "PCM_24",
              metadata: dict | None = None) -> None:
    with WavWriter(path, fs, data.shape[1] if data.ndim == 2 else 1, subtype, metadata) as w:
        w.write(data)


# ---------------------------------------------------------------------------
# Live capture
# ---------------------------------------------------------------------------

def list_devices() -> str:
    import sounddevice as sd
    return str(sd.query_devices())


def capture(fs: float = 192000, chunk_s: float = 0.5, device=None, channels: int = 2,
            duration_s: float | None = None) -> Iterator[tuple[float, np.ndarray]]:
    """Yield ``(unix_time_of_first_sample, chunk)`` from an audio input.

    Requires ``sounddevice`` (PortAudio).  The interface must be set to the
    same rate as the incoming digital stream (the PCM1804 is the clock master).
    """
    import queue

    import sounddevice as sd

    q: queue.Queue = queue.Queue()
    block = int(chunk_s * fs)

    def callback(indata, frames, t_info, status):
        if status:
            q.put(("status", str(status)))
        # Wall-clock time of the first sample of this block (callback latency ignored).
        q.put((time.time() - frames / fs, indata.copy()))

    total = None if duration_s is None else int(duration_s * fs)
    got = 0
    with sd.InputStream(samplerate=fs, blocksize=block, device=device, channels=channels,
                        dtype="float32", callback=callback):
        while total is None or got < total:
            ts, data = q.get()
            if ts == "status":
                import warnings
                warnings.warn(f"audio input: {data}")
                continue
            if total is not None:
                data = data[: total - got]
            got += len(data)
            yield ts, data.astype(float)
