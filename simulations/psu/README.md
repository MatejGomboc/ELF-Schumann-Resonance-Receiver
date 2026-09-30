# ELARA two-bucket PSU -- simulation-based verification

This folder checks the isolated "two-bucket" supply in `PCB/acdc_converter/design.py`
together with the power sheet of `PCB/antenna_amplifier/design.py`. The transient
simulations run in ngspice-42 with behavioural parts. The rest (PSRR chain,
spectra, leakage) is done in Python.

| File | Contents |
|------|----------|
| `psu_model.py` | Netlist generator and ngspice runner. Every assumed value is a parameter in `NOMINAL` / `RELAY_NOMINAL` |
| `psu_two_bucket.cir` | Nominal steady-state netlist written by `python psu_model.py`. It runs on its own with `ngspice -b` |
| `run_psu.py` | Runs every case, the PSRR/leakage analysis, and writes `results.json` and four plots |
| `psu_sawtooth.svg` | Bucket sawtooth, swap transient, relay contact currents, and dropout headroom for every corner |
| `psu_artefact_spectrum.svg` | Swap/sawtooth spectrum along the supply chain compared with the receiver noise, plus the assumed PSRR curves |
| `psu_startup_holdup.svg` | Cold start from empty buckets, and hold-up after mains failure |
| `psu_leakage.svg` | 50 Hz ground bounce of the receiver: direct AC-DC module compared with two-bucket |

Run it with `.venv/bin/python simulations/psu/run_psu.py`. It takes about 1.5–4.5 minutes on 4 cores.

## 1. Circuit and model

```
IRM-05-15 --LM317 CC 0.2 A--LM317 CV 10.9 V--(10u)--SS34--+--2.2R--K1 NC--[bucket A 2.5 F]--K1 NO--2.2R--+
                                                          +--2.2R--K2 NO--[bucket B 2.5 F]--K2 NC--2.2R--+
     LOAD_P: 2200u + 10u -> LT3045 (R_SET 84.5k = 8.45 V, C_SET 22u) -> 10u -> CMC + cable (0.5 R)
     -> amplifier: SS34 -> 100u + ~30u -> ADM7150-5.0 (+5VA, 40 mA) and ADM7150-3.3 (+3V3, 45 mA)
     +5VA -> 10 R -> 22u + 10u + 4 x 100n = +5V_PRE (LMP7721, U202, U203, bias divider)
```

The negative contacts switch the bucket between GND_C and the receiver GND in the
same way. The two grounds are joined only by 1 GΩ, which sets the DC reference in
the simulation. Each relay contact is a conductance ramped 0→1 over 20 µs, with
R_contact = 50 mΩ. Nodes that float while a relay is in transit carry 1–10 nF
strays; these exist only for numerical reasons.

### Assumptions (all sweepable in `psu_model.NOMINAL` / `run_psu.py`)

| Item | Value | Basis |
|------|-------|-------|
| IRM-05-15 output | 15.0 V (corner 14.7 V) | datasheet ±1–2 % |
| LM317 dropout (U1 and U2 each) | 1.55 V + 0.6 Ω·I (corner +0.3 V, cold) | datasheet typ. curve at 25 °C |
| CC set / CV set | 1.25 V/6.2 Ω = 0.2016 A / 10.9 V, R_out 20 mΩ | design.py |
| Charger reach | min(CC, CV, dropout); **dropout-limited to ≈10.6 V at the bucket** | follows from the two dropouts |
| Bucket | 4 × 10 F in series = 2.5 F (corners 2.0 / 3.0 F), ESR 4 × 50 mΩ (sweep 30–75 mΩ/cell), 4 × 5.1 k balancing | design.py, EDLC −10/+30 % tolerance and ageing |
| Series resistors | 2.2 Ω in every bucket path (charger side and load side) | design.py |
| Relay timing (G6K-2F-Y) | break 2.0 ms after coil on, 1.5 ms after coil off; transit 3 ms (corner 5 ms) | datasheet operate/release ≤ 3 ms |
| Overlap case | K1 makes 1.5 ms after the edge, K2 breaks at 4 ms: both buckets on LOAD_P for 2.5 ms | deliberately abnormal |
| Swap period | half-period 30.1 s (CD4060: 1/(2.3·160k·10n) = 272 Hz, Q14) | design.py |
| LT3045 | V_OUT = 100 µA·R_SET; dropout 0.3 V at 0.1 A, modelled as 3 Ω; I_Q 2.3 mA | datasheet typical |
| Loads | 40 mA at 5 V, 45 mA at 3.3 V, plus 2 × 5 mA ADM7150 ground current (corner +25 %) | design.py budget text |
| ADM7150 | ideal regulator with 0.15 V dropout | datasheet typ. at 50 mA |
| CMC + cable | 0.5 Ω loop | Bourns SRF1260 DCR + short cable |

PSRR and noise assumptions (datasheet-typical, **pessimistic set in brackets**):

| Path at ELF (1–50 Hz) | Typical | Pessimistic |
|------|---------|-------------|
| LT3045: SET-pin line regulation dI_SET/dV_IN × R_SET, low-passed by R_SET·C_SET (0.086 Hz) | 0.1 nA/V → −101 dB at DC | 1 nA/V → −81 dB |
| LT3045 error-amplifier floor (zero at 5 kHz) | −115 dB | −100 dB |
| ADM7150 (flat to 30 kHz) | −90 dB | −66 dB |
| LMP7721 PSRR (input-referred) | **−100 dB** | **−75 dB** |
| LMP7715 PSRR, U301 ADC driver on +5VA | **−90 dB** | **−70 dB** |
| Bias divider (47k/47k + 4700 µF) → J202 (worst 1 G) → IN_P (240 pF) | computed | computed |
| PCM1804 VCOM = VCC/2, not filtered (worst case). With VINL− = VCOM, it is fully differential at the ADC | 0.5 V/V, divided by the 35.1 dB antenna→VINL gain | same |
| LT3045 / ADM7150 output noise at 10 Hz (1/√f), white floor | 30 nV / 2 nV; 100 nV / 1.7 nV | – |

Receiver floor for comparison: 45.8 nV/√Hz at the antenna at SR1, which is 26.7 nV/√Hz
at IN_P behind the 0.583 capacitive divider (see `simulations/spice`).

## 2. Results

### 2.1 Sawtooth, dropout and relay currents (steady state, periodic to < 2 mV)

Headroom is V_IN − (V_SET + 3 Ω·I), taken at its minimum over two full swap periods.

| Case | Bucket min..max (V) | LT3045 V_IN min (V) | Headroom above dropout (V) | Contact peak / 1 ms avg (A) | Dropout? |
|---|---:|---:|---:|---:|:---:|
| nominal (3 ms transit) | 9.11..10.31 | 8.76 | **+0.02** | 0.61 / 0.57 | no |
| transit 5 ms | 9.11..10.31 | 8.67 | **-0.05** | 0.65 / 0.60 | yes |
| overlap: both on load 2.5 ms | 9.11..10.31 | 8.89 | **+0.15** | 0.56 / 0.51 | no |
| C_bucket 2.0 F (-20 %) | 8.85..10.34 | 8.50 | **-0.22** | 0.73 / 0.68 | yes |
| C_bucket 3.0 F (+20 %) | 9.28..10.29 | 8.93 | **+0.19** | 0.54 / 0.50 | no |
| ESR 30 mOhm/cell | 9.13..10.32 | 8.77 | **+0.03** | 0.63 / 0.58 | no |
| ESR 75 mOhm/cell | 9.10..10.31 | 8.74 | **+0.01** | 0.59 / 0.55 | no |
| load +25 % (50/56 mA) | 8.82..10.28 | 8.39 | **-0.38** | 0.74 / 0.69 | yes |
| LM317 dropout +0.3 V (cold) | 8.51..9.71 | 8.16 | **-0.55** | 0.61 / 0.57 | yes |
| IRM output 14.7 V (-2 %) | 8.81..10.01 | 8.46 | **-0.26** | 0.61 / 0.57 | yes |
| worst corner (all of the above, 5 ms) | 7.58..9.41 | 7.05 | **-1.72** | 0.89 / 0.83 | yes |
| FIX A: LT3045 7.5 V, nominal | 9.11..10.31 | 8.76 | **+0.97** | 0.61 / 0.57 | no |
| FIX A: LT3045 7.5 V, worst corner | 7.58..9.41 | 7.05 | **-0.77** | 0.89 / 0.83 | yes |
| FIX B: 7.5 V + 4 x 25 F cells, worst corner (5.0 F) | 8.50..9.27 | 7.96 | **+0.11** | 0.49 / 0.46 | no |
| FIX C: 7.5 V + 15 s swap, nominal | 9.59..10.21 | 9.24 | **+1.45** | 0.38 / 0.36 | no |
| FIX C: 7.5 V + 15 s swap, worst corner | 8.36..9.31 | 7.82 | **-0.02** | 0.56 / 0.52 | yes |
| **FIX D: 7.0 V + 15 s swap, nominal** | 9.59..10.21 | 9.24 | **+1.97** | 0.38 / 0.36 | no |
| **FIX D: 7.0 V + 15 s swap, worst corner** | 8.36..9.31 | 7.82 | **+0.49** | 0.56 / 0.52 | no |

- **The charger cannot reach its 10.9 V CV point.** Two LM317 dropouts plus the
  1.25 V sense drop take ≈4.4 V out of 15 V, and the SS34 costs another ≈0.3 V.
  The bucket therefore tops out at ≈10.3 V instead of 10.6 V. The droop is 1.2 V
  per 30 s (0.1 A from 2.5 F), and the 2.2 Ω + ESR drop is ≈0.25 V. That leaves
  the 8.45 V LT3045 only **20 mV** above dropout at the nominal point. Any single
  adverse corner (5 ms transit, −20 % cells, +25 % load, cold LM317, −2 % IRM)
  pushes it into dropout at the end of every discharge half-period.
- **Swap transient.** In the 3–5 ms relay transit the 2200 µF reservoir carries
  the load. LOAD_P dips by only 0.13–0.22 V (the ESR and inrush dominate). The
  fresh bucket then charges the reservoir through 2.2 Ω, which is the 0.61 A
  contact peak.
- **Overlap (both buckets on load).** This case is benign, and actually better
  than the nominal break-before-make. The 2200 µF reservoir holds LOAD_P
  (τ = 2.2 Ω·2200 µF = 4.8 ms), so the leaving bucket's current falls to ≈0 A.
  Less than 0.1 A flows back into it, so there is no significant bucket-to-bucket
  current.
- **Relay contacts in steady state.** Every case stays below 1 A. The highest
  is 0.89 A instantaneous (0.83 A averaged over 1 ms), in the stacked worst corner.

### 2.2 Swap artefact spectrum (`psu_artefact_spectrum.svg`)

The LT3045 input waveform is taken over exactly two steady-state periods, fed
through an FFT, passed through the PSRR chain, and binned (0.1 Hz and 1 Hz
bins, line power / bin width). The worst bin in 1–50 Hz is shown.

| Point | 0.1 Hz bins | 1 Hz bins |
|-------|------:|------:|
| LT3045 input (sawtooth + step) | 45 mV/√Hz | 34 mV/√Hz |
| LT3045 output | 89 nV/√Hz | 64 nV/√Hz |
| ADM7150 +5VA output | 2.8 pV/√Hz | 2.0 pV/√Hz |
| Referred to antenna, typical PSRR | 2 × 10⁻¹⁵ V/√Hz | – |
| **Margin below the 46 nV/√Hz floor, typical** | **124 dB** | **127 dB** |
| **Margin, pessimistic PSRR** | **83 dB** | **87 dB** |

In the time domain, the swap step is 9.6 µV p-p at the LT3045 output and
0.3 nV p-p at the ADM7150 output. **Nothing from the swap is visible in 1–50 Hz**,
even with every PSRR 20–25 dB worse than typical.

The dominant coupling path turns out to be the PCM1804 VCOM (VINL− = VCOM, see
`simulations/system`), not the LMP7721 PSRR. Along that path the LDO noise, not
the swap, sets the level: ≈1.0 nV/√Hz at the antenna at SR1, which is 33 dB
below the floor.

### 2.3 Cold start (both buckets empty, relay timer starts with the coil off)

| | As designed | FIX D (7.0 V, 15 s) |
|---|---:|---:|
| ADM7150 rails valid (5 V ≥ 4.99 V, input ≥ 5.5 V), continuously from | 271 s | 256 s |
| LT3045 in regulation, continuously from | 452 s | 316 s |
| Contact peak, instantaneous | 3.1 A | 3.1 A |
| Contact peak, 1 ms average | 1.01 A | 0.57 A |

**Cold start takes about 7.5 minutes** to a regulated LT3045 output (5.3 minutes
with FIX D), and about 4.5 minutes to valid amplifier rails. This follows from
the charge budget: 0.2 A CC into 2 × 2.5 F while 0.1 A is drawn.

The 3.1 A instantaneous peaks come from the 10 µF on CHG (the LM317 output)
discharging into an empty bucket through 2.2 Ω. The spike lasts ≈24 µs and
carries ≈90 µC. It happens only during start-up, when a nearly empty bucket
reaches the charger.

### 2.4 Hold-up after mains failure (as designed)

When the coil supply fails, the relays fall back to "A on charger, B on load".
Only bucket B then feeds the receiver.

| Swap phase at failure | LT3045 regulates for | ADM7150 rails valid for |
|---|---:|---:|
| Worst (B was just drained) | 5.1 s | 72 s |
| Best (B just charged) | 34 s | 101 s |

After the LT3045 drops out, the ADM7150s still regulate for 1–1.5 minutes. The
bucket droop then reaches the amplifier with only the ADM7150 PSRR in its way.

### 2.5 50 Hz leakage and ground bounce (`psu_leakage.svg`)

Each coupling path is a capacitance C_eff from a 50 Hz source V_src into the
receiver ground. Two ground conditions are modelled:

- **Earthed receiver** (stake plus lead, R_e = 10–100 Ω): V_g = ωC_eff·V_src·R_e.
- **Floating receiver**: V_g = V_src·C_eff/(C_eff + 300 pF + 58 pF). Here 300 pF
  is the enclosure and cable stray, and 58 pF is C_ant = 140 pF in series with
  the 100 pF of filter capacitors.

A ground bounce V_g reaches IN_P through the same capacitive divider as the
signal. It therefore acts exactly like an antenna EMF of −V_g, and can be
compared directly with the 21 mV rms 50 Hz clip level (`simulations/system`)
and the 1–5 mV mains pickup.

| Coupling | I_leak (rms) | V_g earthed, 100 Ω | V_g floating |
|---|---:|---:|---:|
| Direct IRM module, 50 pF barrier, V_L/2 | 1.8 µA | 0.18 mV | 14 V |
| Direct IRM module, 100 pF barrier, V_L | 7.2 µA | 0.72 mV | 50 V |
| Two-bucket as built (GND_C = PE), open contacts + coil–contact C_x = 2 pF, PE 0.3 V | 0.19 nA | 19 nV | 1.7 mV |
| same, C_x = 10 pF, PE 3 V | 9.4 nA | 0.94 µV | 81 mV |
| Receiver-side circuit to the PE-bonded PSU box, 30 pF, PE 3 V | 28 nA | 2.8 µV | 0.23 V |
| Two-bucket, GND_C floating: C_x 2 pF in series with a 100 pF barrier, V_L/2 | 71 nA | 7.1 µV | 0.63 V |
| same, C_x 10 pF | 330 nA | 33 µV | 2.9 V |

- The two-bucket supply cuts the injected current by **4–5 orders of magnitude**
  compared with a direct AC-DC module.
- **Earthed receiver.** The ground bounce is 19 nV–2.8 µV. That is well below the
  mains pickup, and at 50 Hz only (a line, not broadband noise).
- **Floating receiver.** Even the two-bucket supply produces 1.7–230 mV of ground
  bounce, depending on the PE-to-local-earth voltage. A direct module would
  produce tens of volts, which destroys the operating point.

## 3. Verdict

| Check | Requirement | Result |
|-------|-------------|--------|
| A1 sawtooth, as designed | LT3045 never drops out | **FAIL**: +0.02 V nominal; dropout in 5 of 9 single corners and in the stacked worst corner (−1.72 V) |
| A1 sawtooth, FIX D | LT3045 never drops out, including the stacked worst corner | **PASS** (+1.97 V nominal, +0.49 V worst) |
| A1 relay contacts, steady state | < 1 A | **PASS** (0.61 A nominal, 0.89 A worst corner) |
| A1 relay contacts, cold start | < 1 A | **FAIL** instantaneous (3.1 A, 24 µs capacitor spike); 1 ms average 1.01 A as designed, 0.57 A with FIX D |
| A2 swap artefact in 1–50 Hz | below receiver floor | **PASS**, ≥ 124 dB (typ) / ≥ 83 dB (pessimistic) below |
| A3 cold start | report | 4.5 min to valid rails, 7.5 min to LT3045 regulation (5.3 min with FIX D) |
| A4 hold-up | report | 5–34 s regulated, 72–101 s ADM7150 rails |
| A5 50 Hz leakage | ≪ direct module; below mains pickup | **PASS** when the receiver is earthed (≤ 3 µV). Marginal when floating (up to 0.23 V > 21 mV clip) |

### Design problems and proposed fixes

1. **LT3045 dropout margin (A1).** Change two resistors, no new parts:
   - **R_SET 84.5 k → 69.8 k** (V_OUT 8.45 → 6.98 V). The amplifier's ADM7150
     inputs stay at ≥ 6.4 V, which leaves 1.4 V of headroom for the 5.0 V part.
   - **Swap every 15 s instead of 30 s.** Either change CD4060 R_t 160 k → 80.6 k,
     or take Q13 (pin 2) instead of Q14 (pin 3). This halves the droop, and the
     17 → 33 mHz swap rate is still far below the ELF band.
   - This combination (FIX D) passes the stacked worst corner with +0.49 V.
   - Also update the design.py note, which says "10.6 → 9.3 V": the simulated
     bucket peaks at 10.3 V because the charger is dropout-limited.
2. **Relay contact endurance.** Swapping every 30 s already means about 1 million
   operations per relay per year, each making 0.4–0.6 A into the reservoir. The
   G6K electrical endurance is typically rated around 10⁵ operations at rated
   load (check the datasheet), and halving the swap period doubles the
   operation count. Contact life is not
   simulated here. Qualify the relay at this duty, or consider a mercury-wetted
   or solid-state (photo-MOS) switch rated for many millions of operations.
3. **Cold-start inrush.** The make spike is set by the 10 µF on CHG (LM317
   output), discharging through 2.2 Ω into a nearly empty bucket: about 4 A,
   24 µs, 90 µC. The sustained current is limited to 0.2 A by the CC stage U1
   anyway. Reduce **C on CHG from 10 µF to ≤ 100 nF**: the LM317 needs no output
   capacitor for stability. That cuts the spike charge to ≤ 1 µC. This is **not
   re-simulated**, because the 20 µs contact-closure ramp in the model cannot
   resolve a sub-microsecond spike.
4. **Floating receiver.** Earth the outdoor receiver ground locally, or keep the
   PSU box and its PE bond away from the receiver side. Otherwise PE-to-local-earth
   voltage couples through the 2–30 pF strays.

## 4. Limitations

- All regulators are behavioural. There is no LT3045 current-limit foldback or
  PGOOD, no ADM7150 start-up sequencing, and no LM317 thermal limit.
- EDLCs are ideal C + ESR. There is no charge redistribution, no leakage beyond
  the balancing resistors, and no voltage coefficient.
- The PSRR curves are simplified fits to datasheet-typical plots. The
  conclusion (≥ 83 dB margin) is insensitive to them.
- The leakage model uses lumped strays. Real values depend on the enclosure,
  cable routing and site earthing.
