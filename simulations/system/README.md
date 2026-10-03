# ELARA end-to-end receiver budget

This folder builds the budget from the antenna (140 pF) to the PCM1804 digital
output. It covers:

- input-referred noise at SR1–SR7, including the ADC, driver and reference;
- the 50 Hz clip level and headroom for mains pickup;
- expected Schumann SNR in 0.1 Hz and 1 Hz bins;
- the J202 bias-resistor options as a sweep.

| File | Contents |
|------|----------|
| `run_system.py` | Frequency-domain nodal model of the whole chain; writes `results.json` and `system_budget.svg` |
| `system_budget.svg` | Summary figure: noise against signal, noise breakdown, SNR per mode, and 50 Hz headroom against J202 and atmospheric current |

Run it with `.venv/bin/python simulations/system/run_system.py`. It takes about 2 s.

## 1. Method

```
EMF --C_ant 140p-- ANT --R1 33k-- N1 --R3 33k-- IN_P --> LMP7721, G = 1 + Zf/Zg (101 in band)   (R3 = R2 on the plate-capacitor assembly)
                         Cf1 50p        Cf2 50p |-- J202 R_hb --> BIAS_BUF (U203 + 1 k)
                                                |-- R_leak 1 T (noiseless) + 0.1 fA/rtHz PCB leakage
PREAMP_OUT --C_out 10u-- ADC_A --R_AA 10k-- VINL_F --> U301 x1 --100 R-- VINL  (2.7 nF to VCOM)
                         R_bias 47k -> VCOM   C_AA 100n -> VCOM
PCM1804: VINL+ = VINL, VINL- = VCOML (single-ended), full scale 5 Vpp differential = +-2.5 V on VINL+
```

**How the model works**

- **Nodal analysis.** Complex nodal analysis is used for the input network
  (3 nodes) and for the coupling/AA network (2 nodes), with a finite-GBW preamp.
- **Noise sources.** Each source is injected where it physically sits:
  - thermal noise as a Norton current across each resistor;
  - op-amp e_n in series with IN+;
  - currents at IN_P.
- **Referral.** Every source is propagated to the ADC input (VINL − VCOM), then
  referred to the antenna EMF through the signal gain.

**VCOM with single-ended drive.** VINL+ = VCOM + h_post·(V_out − VCOM) and
VINL− = VCOM. So the differential ADC input contains −h_post·v_com. At ELF,
|h_post| ≈ 1, which means **VCOM noise is not cancelled; it is fully
differential**, unlike in the datasheet's differential-drive measurement.

**Cross-check.** For the nominal front end (no R_hb), the Python model gives
**45.84 / 43.35 / 42.64 / 42.33 / 42.15 / 42.06 / 41.99 nV/√Hz** at SR1–SR7.
ngspice gives 45.80 / 43.32 / 42.61 / 42.30 / 42.12 / 42.03 / 41.95. The gains
match to 0.01 dB (35.10 dB antenna → VINL at SR1).

### Assumptions (datasheet-typical; pessimistic set in brackets)

| Item | Value |
|------|-------|
| LMP7721 e_n / i_n | 6.5 nV/√Hz · √(1 + 10 Hz/f), 0.01 fA/√Hz (as simulations/spice) |
| PCB leakage current noise (guarded island, PLAN §3.3) | 0.1 fA/√Hz |
| LMP7715 (U203, U301) e_n | 5.8 nV/√Hz, 1/f corner **30 Hz** (100 Hz) (assumed) |
| PCM1804 noise | DR 112 dB (A-wtd, 20 kHz) + 2 dB unweighted penalty → **41 nV/√Hz** white at VINL (DR 106 dB + 1/f corner 100 Hz) |
| PCM1804 VCOML noise | 50 nV/√Hz at 10 Hz, 1/√f (500 nV/√Hz) (not specified, assumed) |
| PCM1804 VREF noise (multiplicative) | 0.25 ppm/√Hz at 10 Hz, 1/√f; evaluated as the sideband of a 5 mV rms mains line |
| Output swing (LMP7721, LMP7715) | rail-to-rail within 50 mV (light load) |
| **LMP7715 input CM range** | up to **V+ − 1.0 V = 4.0 V** (datasheet-typical, CMRR spec range; swept V+ − 0.8…1.3 V; **verify**) |
| LMP7721 input CM range | up to V+ − 1.2 V (assumed) |
| LMP7721 input bias | 20 fA (worst over temperature; typ 3 fA) |
| R_leak at IN_P | 1 TΩ to GND (as simulations/spice) |
| Atmospheric conduction current I_atm | 0 (insulated antenna) / 1 / 10 / 100 pA (simulations/spice §5) |
| Signal | simulations/signal_chain/expected_signal.py: h_eff 6.5 m; Lorentzian SR peaks (Q 4.5–7.5); quiet SR1 0.3 µV/m/√Hz, typical 1.0 µV/m/√Hz; the 0.05 µV/m/√Hz background (325 nV/√Hz at the antenna) is treated as natural noise, not signal |

## 2. Results

### 2.1 Input-referred noise at the antenna (nV/√Hz) against J202

| J202 | HPF at IN_P | SR1 | SR2 | SR3 | SR4 | SR5 | SR6 | SR7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| (none, ngspice reference) | – | 45.8 | 43.3 | 42.6 | 42.3 | 42.1 | 42.0 | 42.0 |
| 1 G | 660 mHz | 592.8 | 326.5 | 226.5 | 174.7 | 143.2 | 125.9 | 111.1 |
| 10 G | 66 mHz | 192.4 | 111.1 | 82.3 | 68.3 | 60.4 | 56.4 | 53.1 |
| **100 G** | 6.6 mHz | **74.8** | 54.1 | 48.1 | 45.6 | 44.3 | 43.7 | 43.2 |
| 1 T | 0.66 mHz | 49.5 | 44.5 | 43.2 | 42.7 | 42.4 | 42.2 | 42.1 |

With the pessimistic ADC/driver/VCOM set, the 100 G figure at SR1 moves only
from 74.8 to 76.1 nV/√Hz. Referred to the amplifier input (IN_P), 100 G gives
43.6 nV/√Hz at SR1.

### 2.2 Breakdown, J202 = 100 G (nV/√Hz at the antenna)

| Source | SR1 | SR3 | SR5 | SR7 |
|---|---:|---:|---:|---:|
| J202 R_hb thermal | 59.1 | 22.2 | 13.7 | 10.3 |
| R3 33k (input filter) | 31.7 | 31.7 | 31.7 | 31.7 |
| R1 33k (input filter) | 23.4 | 23.4 | 23.4 | 23.4 |
| LMP7721 e_n | 16.8 | 13.6 | 12.7 | 12.3 |
| PCB leakage 0.1 fA | 14.5 | 5.46 | 3.36 | 2.53 |
| Rg 1k | 6.91 | 6.91 | 6.91 | 6.91 |
| LMP7721 i_n | 1.45 | 0.55 | 0.34 | 0.25 |
| **PCM1804 modulator/quantisation** | 1.39 | 1.40 | 1.46 | 1.53 |
| **PCM1804 VCOM (single-ended drive)** | 0.98 | 0.60 | 0.49 | 0.44 |
| Rf 100k | 0.71 | 0.69 | 0.69 | 0.69 |
| **PCM1804 VREF × 5 mV mains** | 0.38 | 0.46 | 0.64 | 1.21 |
| R_bias 47k + R_AA 10k | 0.23 | 0.22 | 0.23 | 0.24 |
| **U301 driver e_n + 100 R** | 0.22 | 0.16 | 0.15 | 0.15 |
| U203 bias buffer via R_hb | 0.02 | 0.005 | 0.003 | 0.002 |
| **Total** | **74.8** | **48.1** | **44.3** | **43.2** |

Everything after the preamp (driver, AA resistors, ADC, VCOM, reference)
totals **1.6–2.0 nV/√Hz**. That is 27–32 dB below the front end, so **the ADC
chain is transparent**. The 35 dB of gain in front of it is enough.

### 2.3 Maximum input at 50 Hz and mains headroom

Gains at 50 Hz: antenna → PREAMP_OUT 53.3 (34.5 dB), antenna → VINL 50.4 (34.0 dB).

| Stage limit | Max antenna EMF at 50 Hz |
|---|---:|
| **U301 input CM range (4.0 V − 2.5 V = 1.5 Vpk at VINL_F)** | **21.1 mV rms** ← binding |
| LMP7721 output swing (2.28 V DC ± 2.2 Vpk) | 29.5 mV rms |
| U301 output swing | 34.4 mV rms |
| PCM1804 full scale (±2.5 V on VINL+) | 35.1 mV rms |

- **Headroom:** **26.5 dB** over 1 mV of mains pickup, **12.5 dB** over 5 mV.
- **Sensitivity to the CM-range assumption:** the result is 16.9 / 21.1 /
  23.9 mV rms for CM limits of V+ − 1.3 / 1.0 / 0.8 V.
- **With a rail-to-rail-input driver,** the limit becomes the LMP7721 swing:
  29.5 mV rms, +2.9 dB.

### 2.4 J202 DC operating point and 50 Hz clip level vs atmospheric current

DC at IN_P = 2.5 V·R_leak/(R_hb + R_leak) + (I_atm + I_b)·(R_hb ‖ R_leak). The
LMP7721 output sits at the same DC level, because Cg blocks DC.

| J202 | I_atm = 0 (insulated) | 1 pA | 10 pA | 100 pA |
|---|---|---|---|---|
| 1 G | 2.50 V / 21.1 mV | 2.50 V / 21.1 mV | 2.51 V / 21.1 mV | 2.60 V / 21.1 mV |
| 10 G | 2.48 V / 21.1 mV | 2.49 V / 21.1 mV | 2.57 V / 21.1 mV | 3.47 V / 19.7 mV |
| 100 G | 2.27 V / 21.1 mV | 2.37 V / 21.1 mV | 3.18 V / 21.1 mV | 11.4 V / **saturated** |
| 1 T | 1.26 V / 16.1 mV | 1.76 V / 21.1 mV | 6.3 V / **saturated** | 51 V / **saturated** |

(Each entry is the IN_P DC level / the maximum 50 Hz antenna EMF in mV rms.)

### 2.5 Expected Schumann SNR (dB), 0.1 Hz bin / 1 Hz bin centred on each mode

| J202 | Conditions | SR1 | SR2 | SR3 | SR4 | SR5 | SR6 | SR7 |
|---|---|---|---|---|---|---|---|---|
| 1 G | quiet | 10.3 / 9.5 | 9.5 / 9.2 | 9.2 / 8.9 | 8.3 / 8.2 | 7.1 / 7.0 | 6.3 / 6.2 | 4.9 / 4.8 |
| 1 G | typical | 20.8 / 20.0 | 20.0 / 19.6 | 20.0 / 19.8 | 19.4 / 19.2 | 18.2 / 18.1 | 16.5 / 16.4 | 15.3 / 15.3 |
| 10 G | quiet | 20.1 / 19.3 | 18.9 / 18.5 | 17.9 / 17.7 | 16.5 / 16.3 | 14.6 / 14.5 | 13.3 / 13.2 | 11.3 / 11.2 |
| 10 G | typical | 30.6 / 29.8 | 29.3 / 29.0 | 28.8 / 28.6 | 27.5 / 27.4 | 25.7 / 25.6 | 23.5 / 23.4 | 21.8 / 21.7 |
| **100 G** | quiet | 28.3 / 27.5 | 25.1 / 24.8 | 22.6 / 22.4 | 20.0 / 19.8 | 17.3 / 17.2 | 15.5 / 15.4 | 13.1 / 13.0 |
| **100 G** | typical | 38.8 / 38.0 | 35.6 / 35.2 | 33.5 / 33.3 | 31.0 / 30.9 | 28.4 / 28.3 | 25.7 / 25.6 | 23.5 / 23.5 |
| 1 T | quiet | 31.9 / 31.1 | 26.8 / 26.5 | 23.5 / 23.3 | 20.6 / 20.4 | 17.7 / 17.6 | 15.8 / 15.7 | 13.3 / 13.2 |
| 1 T | typical | 42.4 / 41.5 | 37.3 / 36.9 | 34.4 / 34.2 | 31.6 / 31.5 | 28.8 / 28.7 | 26.0 / 25.9 | 23.8 / 23.7 |

**Why the two bin widths give almost the same SNR.** The resonances and the
noise are both continuous spectra, so their power scales the same way with bin
width. The 0.1 Hz bin is at most 0.8 dB better, at SR1, because the 1 Hz bin
also averages the Lorentzian skirts. Bin width matters for mains and PSU
*lines* (which concentrate in one bin), and for how many averages a stable
spectrum needs. It does not change the resonance SNR.

- **Quiet SR1 in absolute terms (100 G):** 1.78 µV rms of signal against
  0.075 µV rms of noise in a 1 Hz bin.
- **Against the natural background:** receiver noise with 100 G is 12.8 dB below
  the natural ELF background at SR1 (325 nV/√Hz), and 17.5 dB below it at SR7.

## 3. Verdict

| Check | Requirement | Result |
|---|---|---|
| C1 ADC, driver and reference noise | post-preamp ≥ 10 dB below the front end, SR1–SR7 | **PASS**: 27–32 dB below (1.6–2.0 nV/√Hz at the antenna) |
| C2 50 Hz clip level | 5 mV rms mains with ≥ 6 dB headroom | **PASS**: 21.1 mV rms max, 12.5 dB over 5 mV, 26.5 dB over 1 mV |
| C3 Schumann SNR, typical, SR1–SR7 (100 G) | ≥ 10 dB | **PASS** (23.5–38.8 dB) |
| C3 Schumann SNR, quiet, SR1–SR3 (100 G) | ≥ 10 dB | **PASS** (22.4–28.3 dB) |
| C4 J202 1 G | background-limited (≥ 6 dB below 325 nV/√Hz) | **FAIL** (593 nV/√Hz at SR1, 5 dB *above* the background) |
| C4 J202 10 G | background-limited | **FAIL** (192 nV/√Hz, only 4.6 dB below) |
| C4 J202 100 G | background-limited; DC valid up to 10 pA | **PASS** (12.8 dB below; saturates at 100 pA) |
| C4 J202 1 T | background-limited; DC valid | **PASS** on noise (16.3 dB below). DC point **marginal**: 1.26 V with R_leak 1 T; saturates at ≥ 10 pA |

### Design findings and proposed changes

1. **J202: fit 100 GΩ, and use an insulated antenna element.**
   - With 100 GΩ, the floor at SR1 is 74.8 nV/√Hz (+4.3 dB over the
     resistor-less 45.8 nV/√Hz) and the output stays in range for I_atm ≤ 10 pA.
   - 1 TΩ gains only 3.6 dB at SR1. But its DC point depends on the unknown
     leakage resistance (1.26 V with 1 TΩ leakage), and it saturates at 10 pA.
   - If the antenna must stay bare, so that I_atm ≈ 100 pA, use **10 GΩ** (1 V
     offset, 19.7 mV clip level). The ion shot noise (≈ 820 nV/√Hz at SR1,
     simulations/spice §5.4) then dominates regardless of the resistor.
   - 100 GΩ is a special order (`bom/README.md`), so the BOM fits the largest
     stocked value, 10 GΩ (Ohmite HVC1206Z1008KET). With an insulated antenna it
     is 4.6 dB below the background at SR1, 1.4 dB short of C4; with a bare one
     it is the right value anyway.
2. **U301 input CM range limits the 50 Hz clip level to 21 mV rms**, 4.4 dB
   below the PCM1804 full scale (if the LMP7715 CM range tops out at V+ − 1 V).
   The headroom is still adequate (12.5 dB over 5 mV). If more is wanted,
   replace U301 with a pin-compatible rail-to-rail-input op-amp in SOT-23-5
   (the same 1 OUT / 2 V− / 3 + / 4 − / 5 V+ pinout, for example an OPA365-class
   part). The limit then becomes the LMP7721 swing, 29.5 mV rms. Re-run
   `simulations/stability` with that part's GBW.
3. **VCOM noise is not rejected with single-ended drive.** VINL− = VCOM, while
   VINL+ is referenced to GND through C_out. It contributes ≈1 nV/√Hz here and
   is the dominant coupling path from +5VA into the ADC (`simulations/psu`).
   This is harmless at the assumed levels, but decouple VCOML well (10 µF +
   100 nF are fitted) and keep +5VA quiet.
4. The in-band gain droop (35.15 → 34.27 dB from SR2 to SR7) and the 1.6 Hz
   low corner are as in `simulations/spice`. They are equalised in software.

## 4. Limitations

- **Linear, small-signal model.** Slew rate, distortion and PCM1804 digital
  filter ripple are not modelled. The ADC is represented by an equivalent input
  noise density.
- **Unspecified PCM1804 parameters.** VCOM and VREF noise are not in the
  datasheet; the values used are assumptions. Even ×10 pessimism moves the
  total by < 1 %.
- **Unverified CM-range figures.** The LMP7715/LMP7721 input CM-range limits
  are datasheet-typical recollections and must be checked. They set the 50 Hz
  clip level, but not the noise.
- **Ion shot noise not included.** Shot noise of the atmospheric conduction
  current is left out of the main tables (insulated antenna assumed); see
  simulations/spice §5.4.
