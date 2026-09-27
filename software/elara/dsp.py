# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Streaming DSP building blocks.

All classes keep their state between calls, so a recording can be pushed
through in arbitrary chunk sizes and gives the same result as one big call.

* :class:`Decimator`        -- multi-stage FIR decimation to the ELF rate.
* :class:`MainsCanceller`   -- phase-locked harmonic NLMS mains canceller.
* :class:`ReferenceCanceller` -- adaptive Wiener subtraction of the noise
  reference (R) channel from the antenna (L) channel.
"""

from __future__ import annotations

from collections import deque

import numpy as np
from scipy import signal


# ---------------------------------------------------------------------------
# Decimation
# ---------------------------------------------------------------------------

def _stage_factors(m: int) -> list[int]:
    """Split an integer decimation factor into stages of 2..5, largest first."""
    factors, n = [], m
    for p in (2, 3, 5):
        while n % p == 0:
            factors.append(p)
            n //= p
    if n != 1:
        raise ValueError(f"decimation factor {m} has a prime factor > 5")
    twos = factors.count(2)
    stages = [4] * (twos // 2) + [2] * (twos % 2) + [f for f in factors if f != 2]
    return sorted(stages, reverse=True) or [1]


class Decimator:
    """Multi-stage linear-phase FIR decimator (streaming, multi-channel).

    Each stage only has to protect the final pass band ``[0, passband * fs_out]``
    from aliasing, so the early high-rate stages are short and nearly all the
    selectivity sits in the last, low-rate stage.

    Parameters
    ----------
    fs_in, fs_out : input and output sample rates; ``fs_in / fs_out`` must be an
        integer with prime factors <= 5 (192000 -> 1000 is 4*4*4*3).
    passband : fraction of ``fs_out`` kept flat (default 0.4 -> 0..400 Hz at 1 kHz).
    atten_db : stop-band attenuation of every stage.
    """

    def __init__(self, fs_in: float, fs_out: float, passband: float = 0.4,
                 atten_db: float = 100.0, ripple_db: float = 0.01):
        ratio = fs_in / fs_out
        if abs(ratio - round(ratio)) > 1e-9:
            raise ValueError("fs_in / fs_out must be an integer")
        self.fs_in, self.fs_out = float(fs_in), float(fs_out)
        self.factors = _stage_factors(int(round(ratio)))
        f_pass = passband * fs_out
        self.taps: list[np.ndarray] = []
        fs = self.fs_in
        for m in self.factors:
            if m == 1:
                self.taps.append(np.array([1.0]))
                continue
            fs_next = fs / m
            f_stop = fs_next - f_pass               # first frequency aliasing into band
            width = (f_stop - f_pass) / (fs / 2)
            n, beta = signal.kaiserord(atten_db, width)
            n |= 1                                  # odd length -> integer delay
            h = signal.firwin(n, (f_pass + f_stop) / 2, window=("kaiser", beta), fs=fs)
            self.taps.append(h)
            fs = fs_next
        self.ripple_db = ripple_db
        self._zi: list[np.ndarray | None] = [None] * len(self.taps)
        self._phase = [0] * len(self.taps)

    @property
    def delay_s(self) -> float:
        """Group delay of the whole cascade in seconds (linear phase)."""
        d, fs = 0.0, self.fs_in
        for m, h in zip(self.factors, self.taps):
            d += (len(h) - 1) / 2 / fs
            fs /= m
        return d

    def reset(self) -> None:
        self._zi = [None] * len(self.taps)
        self._phase = [0] * len(self.taps)

    def process(self, x: np.ndarray) -> np.ndarray:
        """Decimate a chunk; ``x`` is (n,) or (n, channels)."""
        y = np.asarray(x, dtype=float)
        for i, (m, h) in enumerate(zip(self.factors, self.taps)):
            if self._zi[i] is None:
                self._zi[i] = np.zeros((len(h) - 1,) + y.shape[1:])
            y, self._zi[i] = signal.lfilter(h, 1.0, y, axis=0, zi=self._zi[i])
            start = self._phase[i]
            self._phase[i] = (start - len(y)) % m
            y = y[start::m]
        return y

    def frequency_response(self, f) -> np.ndarray:
        """Overall magnitude response at output-band frequencies ``f`` [Hz]."""
        f = np.asarray(f, dtype=float)
        h_tot = np.ones_like(f, dtype=complex)
        fs = self.fs_in
        for m, h in zip(self.factors, self.taps):
            h_tot *= signal.freqz(h, 1.0, worN=f, fs=fs)[1]
            fs /= m
        return np.abs(h_tot)


# ---------------------------------------------------------------------------
# Mains rejection
# ---------------------------------------------------------------------------

def estimate_mains_frequency(x: np.ndarray, fs: float, nominal: float = 50.0,
                             search_hz: float = 1.0, duration_s: float = 4.0) -> float:
    """Coarse mains-frequency estimate from the start of a recording.

    The signal is mixed down by ``nominal``, averaged over whole nominal
    cycles (which nulls every other harmonic and the image), then a heavily
    zero-padded FFT is searched within ``nominal +/- search_hz``.
    """
    n_cyc = int(round(fs / nominal))
    n_blocks = max(4, int(duration_s * nominal))
    x = np.asarray(x, dtype=float)[: n_cyc * n_blocks]
    n_blocks = len(x) // n_cyc
    if n_blocks < 4:
        return float(nominal)
    x = x[: n_blocks * n_cyc]
    t = np.arange(len(x)) / fs
    bb = (x * np.exp(-2j * np.pi * nominal * t)).reshape(n_blocks, n_cyc).mean(axis=1)
    nfft = 1 << int(np.ceil(np.log2(n_blocks * 64)))
    rate = fs / n_cyc
    spec = np.abs(np.fft.fft(bb * np.hanning(n_blocks), nfft))
    df = np.fft.fftfreq(nfft, 1 / rate)
    sel = np.abs(df) <= search_hz
    idx = np.flatnonzero(sel)[np.argmax(spec[sel])]
    # Parabolic interpolation on the log magnitude.
    a, b, c = np.log(spec[[idx - 1, idx, (idx + 1) % nfft]] + 1e-300)
    denom = a - 2 * b + c
    delta = 0.5 * (a - c) / denom if denom != 0 else 0.0
    return float(nominal + (df[idx] + delta * rate / nfft))


class MainsCanceller:
    """Adaptive mains-hum canceller for one channel.

    A harmonic-reference NLMS canceller (Widrow's adaptive noise canceller with
    synthesised references) whose reference oscillator is phase-locked to the
    mains fundamental:

    * references ``exp(j k phi)`` for k = 1..K (all harmonics up to ``f_max``);
    * complex weights ``w_k`` hold amplitude and phase of each harmonic; the
      estimate ``Re(sum w_k exp(j k phi))`` is subtracted sample by sample;
    * every nominal mains cycle (block of L samples) the weights take a
      normalised gradient step ``w_k += mu * (2/L) sum e * exp(-j k phi)``;
    * a second-order (PI) phase-locked loop drives the phase of the fundamental
      error-plus-weight phasor to zero, so a drifting mains frequency is tracked
      with zero steady-state frequency error and the weights stay stationary.

    * blocks whose error power jumps above ``gate_db`` over its running mean
      (sferics, clipping) do not update the weights or the loop, so impulsive
      interference cannot kick the oscillator.

    Each harmonic behaves as a notch of -3 dB half-width about
    ``mu * f_mains / (2 pi)`` (0.16 Hz for mu = 0.02 at 50 Hz), so a
    Schumann mode 5 Hz away is left untouched.

    Parameters
    ----------
    fs : sample rate [Hz].
    nominal : mains frequency, 50 or 60 Hz.
    f_max : highest harmonic frequency to cancel (clipped to 0.45 fs).
    mu : NLMS step size per mains cycle (sets notch width / convergence time).
    pll_bw_hz : natural frequency of the phase-locked loop.
    f_init : starting frequency estimate (e.g. from :func:`estimate_mains_frequency`).
    max_dev_hz : clamp on the tracked frequency deviation from nominal.
    gate_db : impulse-blanking threshold for the block error power.
    """

    def __init__(self, fs: float, nominal: float = 50.0, f_max: float = 2000.0,
                 mu: float = 0.02, pll_bw_hz: float = 0.5,
                 f_init: float | None = None, max_dev_hz: float = 1.0,
                 gate_db: float = 10.0, zeta: float = 1.0):
        self.fs, self.nominal = float(fs), float(nominal)
        self.n_harm = max(1, int(min(f_max, 0.45 * fs) // nominal))
        self.block = int(round(fs / nominal))
        self.mu = mu
        self.max_dev = max_dev_hz
        self.freq = float(f_init if f_init is not None else nominal)
        self.phase = 0.0                              # reference phase at next sample
        self.w = np.zeros(self.n_harm, dtype=complex)
        self._k = np.arange(1, self.n_harm + 1)
        self._acc = np.zeros(self.n_harm, dtype=complex)
        self._n_acc = 0
        self._n_updates = 0
        self._e2 = 0.0
        self._p_ref = 0.0
        self._gate = 10 ** (gate_db / 10)
        self._n_blanked_run = 0
        self.n_blanked = 0
        # Discrete 2nd-order PLL gains, updated once per block.
        wn_t = 2 * np.pi * pll_bw_hz * self.block / fs
        t_blk = self.block / fs
        self._kp_hz = 2 * zeta * wn_t / (2 * np.pi * t_blk)
        self._ki_hz = wn_t ** 2 / (2 * np.pi * t_blk)
        self._f_int = self.freq
        # Boxcar over 0.2 s of detector output: nulls phase modulation at
        # 5, 10, 15 ... Hz offsets, i.e. Schumann modes near the mains lines.
        self._psi_hist: deque[float] = deque(maxlen=max(1, int(round(0.2 * nominal))))
        self.freq_track: list[float] = []       # tracked frequency, one entry per cycle

    @property
    def harmonics(self) -> np.ndarray:
        """Current complex amplitude of each harmonic (FS units)."""
        return self.w.copy()

    def process(self, x: np.ndarray) -> np.ndarray:
        """Cancel mains from a 1-D chunk; returns an array of the same length."""
        x = np.asarray(x, dtype=float)
        out = np.empty_like(x)
        pos = 0
        while pos < len(x):
            n = min(self.block - self._n_acc, len(x) - pos)
            seg = x[pos:pos + n]
            phi = self.phase + 2 * np.pi * self.freq / self.fs * np.arange(n)
            # exp(j k phi) for all k by repeated multiplication (cheaper than exp).
            ref = np.cumprod(np.broadcast_to(np.exp(1j * phi), (self.n_harm, n)), axis=0)
            e = seg - (self.w @ ref).real
            out[pos:pos + n] = e
            self._acc += ref.conj() @ e
            self._e2 += float(e @ e)
            self._n_acc += n
            self.phase = (self.phase + 2 * np.pi * self.freq / self.fs * n) % (2 * np.pi)
            pos += n
            if self._n_acc == self.block:
                self._update()
        return out

    def _update(self) -> None:
        grad = self._acc * (2.0 / self.block)
        p_err = self._e2 / self.block
        self._acc[:] = 0
        self._e2 = 0.0
        self._n_acc = 0
        # Impulse blanking (after a short settling period; never for > 0.5 s).
        if (self._n_updates > 10 and p_err > self._gate * self._p_ref
                and self._n_blanked_run < int(0.5 * self.nominal)):
            self._n_blanked_run += 1
            self.n_blanked += 1
            self.freq_track.append(self._f_int)
            return
        self._n_blanked_run = 0
        self._n_updates += 1
        self._p_ref += max(0.05, 1.0 / self._n_updates) * (p_err - self._p_ref)
        # Gear-shift start: behave like a running LS average until 1/n < mu.
        mu = max(self.mu, 1.0 / self._n_updates)
        # Phase detector: phase of the fundamental measured in this block.
        self._psi_hist.append(float(np.angle(self.w[0] + grad[0])))
        psi = float(np.mean(self._psi_hist))
        self.w += mu * grad
        if self._n_updates == 1:
            # Align the oscillator with the mains phase once, without a frequency kick.
            self.phase = (self.phase + psi) % (2 * np.pi)
            self.w *= np.exp(-1j * self._k * psi)
            self._psi_hist.clear()
        else:
            # PI loop: the integrator tracks the frequency, the proportional term
            # nudges the oscillator frequency for the next block.  In steady state
            # the relative phase of every harmonic is constant, so the weights
            # never have to chase a rotating phasor.
            self._f_int = float(np.clip(self._f_int + self._ki_hz * psi,
                                        self.nominal - self.max_dev,
                                        self.nominal + self.max_dev))
            self.freq = float(np.clip(self._f_int + self._kp_hz * psi,
                                      self.nominal - self.max_dev,
                                      self.nominal + self.max_dev))
        self.freq_track.append(self._f_int)


# ---------------------------------------------------------------------------
# Noise-reference (R channel) subtraction
# ---------------------------------------------------------------------------

class ReferenceCanceller:
    """Adaptive frequency-domain Wiener subtraction of the noise-reference channel.

    The R channel of ELARA carries only system noise (ADC input shorted).  Any
    part of the L channel coherent with it is instrument noise, so per STFT
    bin the transfer function ``H = S_LR / S_RR`` is estimated from
    exponentially averaged cross-spectra and ``H * R`` is subtracted from L.
    ``H`` is updated *after* each frame is processed, so a frame never
    cancels itself (no self-subtraction bias).

    Uses sqrt-Hann windows at 50 % overlap (perfect reconstruction).  The
    output is delayed by ``latency`` samples; :func:`subtract_reference`
    handles the alignment for whole arrays.
    """

    def __init__(self, nfft: int = 1024, tau_frames: float = 64.0, reg: float = 1e-30):
        if nfft % 2:
            raise ValueError("nfft must be even")
        self.nfft, self.hop = nfft, nfft // 2
        self.alpha = 1.0 / tau_frames
        self.reg = reg
        self.win = np.sqrt(signal.windows.hann(nfft, sym=False))
        nb = nfft // 2 + 1
        self.s_lr = np.zeros(nb, dtype=complex)
        self.s_rr = np.zeros(nb)
        self.s_ll = np.zeros(nb)
        self._n_frames = 0
        self._inbuf = np.zeros((nfft, 2))
        self._fill = nfft - self.hop           # zero-primed history
        self._outbuf = np.zeros(nfft)

    @property
    def latency(self) -> int:
        return self.nfft - self.hop

    @property
    def transfer(self) -> np.ndarray:
        return self.s_lr / (self.s_rr + self.reg)

    @property
    def coherence(self) -> np.ndarray:
        """Magnitude-squared coherence between L and R per bin."""
        return np.abs(self.s_lr) ** 2 / (self.s_ll * self.s_rr + self.reg)

    def process(self, left: np.ndarray, right: np.ndarray) -> np.ndarray:
        x = np.column_stack([left, right]).astype(float)
        out = []
        pos = 0
        while pos < len(x):
            n = min(self.nfft - self._fill, len(x) - pos)
            self._inbuf[self._fill:self._fill + n] = x[pos:pos + n]
            self._fill += n
            pos += n
            if self._fill == self.nfft:
                out.append(self._frame())
                self._inbuf[:-self.hop] = self._inbuf[self.hop:]
                self._fill = self.nfft - self.hop
        return np.concatenate(out) if out else np.zeros(0)

    def _frame(self) -> np.ndarray:
        spec = np.fft.rfft(self._inbuf * self.win[:, None], axis=0)
        sl, sr = spec[:, 0], spec[:, 1]
        y = sl - (self.transfer * sr if self._n_frames else 0)
        # Update the averaged spectra (fast start: running mean for the first frames).
        self._n_frames += 1
        a = max(self.alpha, 1.0 / self._n_frames)
        self.s_lr += a * (sl * sr.conj() - self.s_lr)
        self.s_rr += a * (np.abs(sr) ** 2 - self.s_rr)
        self.s_ll += a * (np.abs(sl) ** 2 - self.s_ll)
        self._outbuf += np.fft.irfft(y, self.nfft) * self.win
        ready = self._outbuf[:self.hop].copy()
        self._outbuf[:-self.hop] = self._outbuf[self.hop:]
        self._outbuf[-self.hop:] = 0
        return ready


def subtract_reference(left: np.ndarray, right: np.ndarray, **kwargs) -> np.ndarray:
    """Offline helper: :class:`ReferenceCanceller` with output aligned to input."""
    rc = ReferenceCanceller(**kwargs)
    pad = np.zeros(rc.nfft)
    y = np.concatenate([rc.process(left, right), rc.process(pad, pad)])
    return y[rc.latency:rc.latency + len(left)]
