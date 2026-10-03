# ELARA PC software

Phase 2 software for **ELARA**, the ELF Atmospheric Radio Analyser (see the
top-level `README.md` and `PLAN.md` §6–§7). The outdoor unit digitises the
antenna with a PCM1804 and sends it as AES3 (on shielded Cat5e/6 with an
RJ45) to a stock USB audio interface: an AES3 input, or an S/PDIF input
through a 110 Ohm to 75 Ohm balun. This package takes that stereo stream (live or recorded) and:

- reads and writes recordings (WAV/FLAC/HDF5) with timestamps and metadata,
  and captures live audio from the interface;
- removes mains hum (50/60 Hz and harmonics up to 2 kHz) adaptively,
  following the mains frequency as it drifts;
- subtracts system noise that is coherent with the **noise-reference (R)
  channel**;
- decimates 192/96/48 kHz to an ELF analysis rate (1 kHz by default);
- refers spectra to the antenna in V/√Hz by undoing the analogue front-end
  response;
- fits Schumann resonance modes (centre frequency, amplitude and Q, each with
  an uncertainty) and detects sferics;
- generates realistic synthetic recordings for demos and tests.

| Channel | Role |
|---------|------|
| Left (0)  | Antenna: 40 dB preamp, ELF band 1–50 Hz, rolls off above 106 Hz and 159 Hz |
| Right (1) | Noise reference: PCM1804 R input tied to VCOMR, so only system noise |

## Install

```bash
cd software
python -m pip install -e ".[all]"      # or: pip install -r requirements.txt
```

The core only needs numpy, scipy and matplotlib. The optional packages are
loaded only when used:

| Package | Used for | Without it |
|---------|----------|------------|
| `soundfile` | FLAC, streaming 24-bit WAV | WAV only, via `scipy.io.wavfile` (writer buffers in memory) |
| `sounddevice` + PortAudio | `capture` | `capture` prints an error and exits with status 1 |
| `h5py` | `.h5` recordings | HDF5 not available |

## Usage

```bash
# Synthetic 60 s recording at 192 kHz (24-bit WAV + JSON sidecar with the true values)
python -m elara simulate demo/sim.wav --duration 60

# Clean, decimate and analyse: PSD + spectrogram (PNG and SVG), fitted modes, sferic list
python -m elara analyse demo/sim.wav --format png svg
#   -> demo/sim_psd.png  demo/sim_spectrogram.png  demo/sim_modes.csv  demo/sim_sferics.csv

# Live capture (192 kHz AES3 / S/PDIF input): list devices, then record 10 minutes to HDF5
python -m elara capture --list-devices
python -m elara capture night.h5 --device 3 --duration 600
```

Useful `analyse` options: `--mains 60` (the default is read from metadata,
otherwise 50), `--elf-rate 500`, `--resolution 0.25` (bin width of the fitted
PSD), `--fmax 60`, and `--no-mains`, `--no-reference` or `--no-sferics` to
switch off individual stages.

From Python:

```python
from elara.pipeline import analyse_file
res = analyse_file("night.h5", mains_hz=50)
for m in res.fit.modes:
    print(m.index, m.freq_hz, m.freq_err_hz, m.q)
```

Every DSP block works on a stream. Feed it chunks of any size and the output
is the same as one call on the whole signal:

```python
from elara.dsp import Decimator, MainsCanceller
mc, dec = MainsCanceller(192000, 50), Decimator(192000, 1000)
for chunk in chunks:                                  # (n, 2) float arrays
    left = mc.process(chunk[:, 0])
    elf = dec.process(np.column_stack([left, chunk[:, 1]]))
```

## Signal flow and algorithms

```
L (fs) -- MainsCanceller --+-- SfericDetector (300 Hz - 20 kHz)
                           +-- Decimator --> L_elf --+
R (fs) --------------------- Decimator --> R_elf --+-- ReferenceCanceller --> L_clean
L_clean -> Welch PSD -> front-end correction (V/sqrt(Hz) at antenna) -> Lorentzian fit
        -> averaged spectrogram
```

**Decimation** (`dsp.Decimator`). The rate ratio is split into stages of 2–5,
for example 192 kHz → 1 kHz is 4·4·4·3. Each stage is a linear-phase
Kaiser-window FIR that only has to protect the final pass band (0–0.4·fs_out),
so the early high-rate stages have just 29–37 taps. The pass band is flat to
±0.02 dB, and everything that would alias into it is attenuated by ≥100 dB.
Filter state and the decimation phase carry over between chunks.
`delay_s` gives the group delay (18 ms).

**Mains cancellation** (`dsp.MainsCanceller`). This is a harmonic-reference
NLMS canceller whose reference oscillator is phase-locked to the mains:

- Complex weights `w_k` for k = 1…K (all harmonics up to 2 kHz) model each
  harmonic. The estimate `Re Σ w_k e^{jkφ}` is subtracted from every sample.
- Once per nominal mains cycle, the weights take a normalised gradient step
  with μ = 0.02. Each harmonic then becomes a notch about 0.16 Hz wide
  (half-width). The notch gets there by the steady-state tracking, not by a
  fixed filter.
- A second-order (PI) phase-locked loop (0.5 Hz, critically damped) holds the
  oscillator on the phase of the fundamental. A ±0.2 Hz drift therefore leaves
  every harmonic's weight stationary.
- The phase detector is averaged over 0.2 s. This nulls phase modulation at
  offsets of 5, 10, 15 … Hz, so a Schumann mode at 45 Hz cannot pull the loop.
- Blocks whose error power jumps by more than 10 dB (sferics, clipping) do
  not update anything.
- The initial frequency comes from a zoom FFT of the first 4 s.

Measured results (see `tests/test_mains.py`):

| Case | Result |
|------|--------|
| Stable hum, 40 harmonics | > 100 dB rejection |
| 45 Hz tone | changed by < 0.1 dB |
| Slow ±0.2 Hz drift | ≈ 55–70 dB rejection |
| Speed | ≈ 12× real time at 192 kHz with 40 harmonics, on one core |

**Noise-reference subtraction** (`dsp.ReferenceCanceller`). This is an
adaptive Wiener filter in the STFT domain (sqrt-Hann windows, 50 % overlap,
perfect reconstruction):

- `H(f) = S_LR/S_RR` comes from exponentially averaged cross-spectra, over
  about 30 s in the pipeline.
- `H·R` is subtracted from L.
- `H` is updated only after each frame has been processed, so no frame
  cancels itself.

Only the part of L that is coherent with R is removed, and that part is
system noise by construction. The pipeline runs this stage at the ELF rate.
It drops the first 3 s (while the mains canceller converges) so that start-up
hum cannot bias the cross-spectra.

**Front-end model** (`frontend.FrontEnd`). **All hardware constants live
here.** The antenna → ADC response has these sections:

- capacitive divider: 0.583 (−4.7 dB);
- LMP7721 non-inverting stage `1 + Zf/Zg`: 101× in band, Rg·Cg corner at
  1.59 Hz, Rf·Cf pole at 106 Hz;
- C_out/R_bias coupling high-pass: 0.34 Hz;
- R_AA/C_AA anti-alias pole: 159 Hz;
- PCM1804 full scale: 2.5 V differential peak = 1.0.

It provides:

- `response(f)`: the complex response H(f) from antenna volts to ADC
  full-scale units.
- `to_antenna_psd()`: refers a PSD to the antenna, in V²/Hz.
- `correction_sos(fs)`: a regularised inverse IIR filter. It is flat to
  ±0.2 dB over 2–50 Hz at fs = 1 kHz and gives time series in antenna volts.

The PCM1804's own DC-removal high-pass (fs/48000, which is 4 Hz at 192 kHz)
is assumed bypassed (BYPAS pin). If it is enabled, set `adc_hpf_hz`.

**Schumann fit** (`analysis.fit_schumann`). The model is a power-law
background `B·(f/10)^−α` plus seven Lorentzians
`A_i / (1 + ((f − f_i)/γ_i)²)`:

- It is fitted over 3–48 Hz, excluding mains ±1 Hz.
- It minimises the squared log-PSD difference with `scipy.optimize.least_squares`.
  This is the right metric for averaged periodograms, whose scatter is
  multiplicative.
- Centre frequencies may move ±2.5 Hz from nominal, and Q is bounded to 2–15.
- Uncertainties come from the Jacobian at the optimum, scaled by the residual
  variance.
- Output per mode: `f`, `HWHM = γ`, `Q = f/2γ` and the peak ASD, each with
  1σ errors.

On one hour of synthetic data, all seven modes are recovered to within
0.1 Hz and agree with their error bars. On 60 s, SR1–SR4 are typically
recovered to within 0.1–0.3 Hz, but SR6 and SR7 are poorly constrained, and
the reported errors say so.

**Sferic detector** (`analysis.SfericDetector`). The mains-cleaned full-rate
L channel goes through a 4th-order band-pass (300 Hz – 20 kHz), and its energy
is measured in 1 ms windows. An event is any window more than 15 dB above the
local median, which is taken over 1 s blocks. Events closer than 5 ms are
merged. The detector streams, and it ignores the first 1.5 s while the mains
canceller converges.

**Simulator** (`simulate.simulate`). The antenna-level components are:

- a 1/f natural background;
- the 64.6 nV/√Hz instrument floor;
- seven Lorentzian modes with Q 4.5–7.5;
- 2 mV of mains with odd-heavy harmonics up to 2 kHz and a slow ±0.15 Hz
  drift;
- Poisson sferics (3 per second), each a damped VLF burst with a weak ELF
  tail.

These are passed through `FrontEnd.response` in the frequency domain. Then
the simulator adds correlated system noise (1/f plus spurs at 17.5 Hz and
31 Hz) to R, and through a coupling filter to L, plus ADC noise on both
channels. The true values are written to the JSON sidecar.

## Recording formats

- **WAV**: 24-bit PCM (or float), in ADC full-scale units, with a
  `<name>.json` sidecar. The sidecar holds the sample rate, the UTC start
  time, `channel_roles`, the preamp gain and every front-end constant. It is
  compatible with SpectrumLab and similar tools.
- **HDF5**:
  - `/samples`: (n, 2) float32, gzip-compressed and appendable.
  - `/timestamps`: rows of (first sample index, Unix time), one per captured
    block, so wall-clock timing can be reconstructed.
  - Root attributes: `sample_rate`, plus `metadata` (the same JSON).

## Tests

```bash
cd software
python -m pytest            # 27 tests, ~7 s
```

The tests cover:

- decimator plan, flatness, alias rejection, and that chunked and whole-array
  processing agree;
- mains rejection above 60 dB at 50 and 60 Hz with harmonics up to 2 kHz;
- a 45 Hz tone changed by less than 0.5 dB;
- drift tracking;
- reference subtraction: coherent noise down by more than 18 dB, and the
  signal changed by less than 0.2 dB;
- Lorentzian recovery;
- sferic detection;
- I/O round trips (soundfile, scipy fallback, HDF5);
- a CLI smoke test (`simulate` then `analyse`).

## Limitations

- **The drifting-mains canceller trades tracking against noise.** A faster
  loop follows the frequency better but adds phase noise, which shows up as
  small sidebands within about ±1.5 Hz of 50 Hz. The Schumann fit therefore
  excludes 49–51 Hz. Fast grid-frequency excursions (≳ 0.015 Hz/s) reduce
  rejection to about 45–50 dB.
- **Mains is cancelled on L only.** If the R channel picks up hum, the
  reference stage sees no coherence at the mains lines and leaves them alone.
  This is harmless.
- **The reference canceller needs averaging.** It uses about 30 s of spectra.
  Each strong line that is left in L, and not in R, adds a small estimation
  error in the bins next to it.
- **The front-end correction uses nominal component values.** Real
  tolerances (for example ±10 % on Cg or C_out) move the low-frequency
  corners, which matters below about 3 Hz. Calibrate against a known
  injected signal when the hardware exists.
- **`capture` is untested against real hardware.** No audio device was
  available during development. The USB interface must be locked to the
  incoming AES3 / S/PDIF rate: the PCM1804 is the clock master, so avoid sample-rate
  conversion in the OS mixer (use exclusive or ASIO mode, or ALSA `hw:`).
  Block timestamps come from the host clock, not GPS.
- **Short records give weak fits.** Records under a few minutes give poorly
  constrained fits for SR5–SR7. For monitoring, average 10–30 min per fit.
- **The pipeline is offline.** It holds the ELF-rate data (1 kS/s) in
  memory, which is fine for hours of data. A real-time scrolling display
  (PLAN §7.2) is not implemented yet. The blocks are streaming, so it can be
  built on top of them.

## Licence

CERN-OHL-W-2.0, the same as the rest of the repository.
