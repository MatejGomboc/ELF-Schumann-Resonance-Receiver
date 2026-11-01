# ELARA two-bucket PSU -- simulation-based verification

**Status:** every simulation below runs on the PSU **as built**: LT3045 at 6.98 V
(R_SET 69.8 kΩ), a 15.2 s swap (CD4060 Rt 80.6 kΩ), 100 nF on CHG, the charger at
10.76 V (R3/R4 120 Ω / 909 Ω), four SIL05-1C90-51D reed relays with a staggered swap
and SS34 diodes in the load paths (section 1), and since the review of 2026-10-31
SS34s in every bucket negative leg (one way only), 1 Ω load resistors and a 0.4 A
load-path limiter (R26/Q3/Q4; the leg diodes are modelled as a fixed 0.38 V drop). History cases: rev 0.1 (8.45 V, 30 s, 10 µF, 11.08 V), which dropped
out, and the G6K scheme (both relays at once, no load diodes).

The EDLC overvoltage crowbar on CHG (U6/Q5/Q6, trip 11.7 V) and GDT1 across the
barrier (both 2026-10-31) are not in the model: in normal operation the crowbar stays
off (CV at most 11.24 V) and its divider draws about 0.23 mA from CHG, and the GDT is
open (150 V sparkover, < 0.5 pF).

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

Run it with `.venv/bin/python simulations/psu/run_psu.py`. It takes about 20 s on 4 cores.

## 1. Circuit and model

```
IRM-05-15 --LM317 CC 0.2 A--LM317 CV 10.76 V--(100n)--SS34--+--2.2R--NC [bucket A 2.5 F] NO--SS34--1R--+
                                                           +--2.2R--NO [bucket B 2.5 F] NC--SS34--1R--+-- OR_P
     bucket negatives: NC/NO to GND_C or GND through an SS34 each (one way only)
     OR_P -> 0.4 A limiter (1R5 + Si2319CDS + MMBT3906) -> LOAD_P
     LOAD_P: 2200u + 10u -> LT3045 (R_SET 69.8k = 6.98 V, C_SET 22u, ILIM 499R) -> 22u -> CMC + cable (7.2 R)
     -> amplifier: SS34 -> 100u + ~54u -> ADM7150-5.0 (+5VA, 40 mA) and ADM7150-3.3 (+3V3, 45 mA)
     +5VA -> 10 R -> 22u + 10u + 4 x 100n = +5V_PRE (LMP7721, U202, U203, bias divider)
```

"K1" in the model is bucket A's pair of reeds (K1 + K2 on the board, coils in
series), "K2" is bucket B's pair (K3 + K4); the negative contacts switch the bucket
between GND_C and the receiver GND in the same way. **Stagger:** bucket A's driver
gate charges at once and holds for 30–50 ms when SWAP falls (100 kΩ / 220 nF);
bucket B's gate charges slowly (470 kΩ / 220 nF, 10–30 ms) and drops at once. So
at every swap the arriving bucket switches first and the leaving one `STAGGER`
(30 ms nominal, 10 ms case) later: both buckets sit on LOAD_P through their SS34s
for a moment, the leaving bucket's diode is reverse biased, and its load contacts
open with no current. The two buckets are never on the charger together. The two grounds are joined only by 1 GΩ, which sets the DC reference in
the simulation. Each relay contact is a conductance ramped 0→1 over 20 µs, with
R_contact = 50 mΩ. Nodes that float while a relay is in transit carry 1–10 nF
strays; these exist only for numerical reasons.

### Assumptions (all sweepable in `psu_model.NOMINAL` / `run_psu.py`)

| Item | Value | Basis |
|------|-------|-------|
| IRM-05-15 output | 15.0 V (corner 14.7 V) | datasheet ±1–2 % |
| LM317 dropout (U1 and U2 each) | 1.55 V + 0.6 Ω·I (corner +0.3 V, cold) | datasheet typ. curve at 25 °C |
| CC set / CV set | 1.25 V/6.2 Ω = 0.2016 A / 10.76 V = 1.25 V·(1 + 909/120) + 50 µA·909, R_out 20 mΩ, 100 nF on CHG (rev 0.1: 11.08 V, 10 µF) | design.py, LM317 I_ADJ typ. |
| Charger reach | min(CC, CV, dropout), dropout = 15 V − 2·(1.55 V + 0.6 Ω·I) − 6.2 Ω·I: the CC stage drops its full 1.25 V only at 0.2 A. Nominal: CC, then CV at 10.76 V. Cold or low-mains corners: dropout-limited | follows from the two dropouts |
| Bucket | 4 × 10 F in series = 2.5 F (corners 2.0 / 3.0 F), ESR 4 × 50 mΩ (sweep 30–75 mΩ/cell), 4 × 5.1 k balancing | design.py, EDLC −10/+30 % tolerance and ageing |
| Series resistors | 2.2 Ω in each charger path, SS34 + 1 Ω in each load path, then the 0.4 A limiter (1.6 Ω below its limit) | design.py |
| Relay timing (SIL05-1C90-51D) | break 0.3 ms after coil on, 2.0 ms after coil off (built-in coil diode); transit 0.5 ms (corner 2 ms) | Standex SIL datasheet V03: operate ≤ 0.7 ms incl. bounce, release ≤ 1.5 ms unsuppressed |
| Stagger | leaving bucket 30 ms after the arriving one (case: 10 ms) | gate RCs, 2N7002 V_th 1–2.5 V |
| Swap period | half-period 15.2 s (CD4060: 1/(2.3·80.6k·10n) = 539 Hz, Q14); rev 0.1: 30.1 s | design.py |
| LT3045 | V_OUT = 100 µA·R_SET; dropout 0.3 V at 0.1 A, modelled as 3 Ω; I_Q 2.3 mA | datasheet typical |
| Loads | 40 mA at 5 V, 45 mA at 3.3 V, plus 2 × 5 mA ADM7150 ground current (corner +25 %) | design.py budget text |
| ADM7150 | ideal regulator with 0.15 V dropout | datasheet typ. at 50 mA |
| CMC + cable | 7.2 Ω loop | Bourns SRF1260-102M: 6.78 Ω for both windings in series (datasheet), + 0.4 Ω cable |

PSRR and noise assumptions (datasheet-typical, **pessimistic set in brackets**):

| Path at ELF (1–50 Hz) | Typical | Pessimistic |
|------|---------|-------------|
| LT3045: SET-pin line regulation dI_SET/dV_IN × R_SET, low-passed by R_SET·C_SET (0.10 Hz) | 0.1 nA/V → −103 dB at DC | 1 nA/V → −83 dB |
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

| Case | Bucket min..max (V) | LT3045 V_IN min (V) | Headroom above dropout (V) | Contact peak / 1 ms avg (A) | Break current load / charger (mA) | Dropout? |
|---|---:|---:|---:|---:|---:|:---:|
| nominal | 9.41..10.03 | 8.46 | **+1.20** | 0.29 / 0.27 | 0.0 / 35 | no |
| transit 2 ms | 9.41..10.03 | 8.46 | **+1.20** | 0.29 / 0.27 | 0.0 / 35 | no |
| stagger 10 ms (fast gate) | 9.41..10.03 | 8.46 | **+1.20** | 0.29 / 0.27 | 0.0 / 34 | no |
| C_bucket 2.0 F (-20 %) | 9.28..10.05 | 8.34 | **+1.07** | 0.33 / 0.32 | 0.0 / 28 | no |
| C_bucket 3.0 F (+20 %) | 9.49..10.01 | 8.54 | **+1.27** | 0.25 / 0.24 | 0.0 / 41 | no |
| ESR 30 mOhm/cell | 9.42..10.03 | 8.47 | **+1.21** | 0.29 / 0.28 | 0.0 / 34 | no |
| ESR 75 mOhm/cell | 9.39..10.02 | 8.44 | **+1.18** | 0.28 / 0.27 | 0.0 / 36 | no |
| load +25 % (50/56 mA) | 9.24..9.99 | 8.23 | **+0.90** | 0.35 / 0.33 | 0.0 / 46 | no |
| LM317 dropout +0.3 V (cold) | 9.22..9.86 | 8.28 | **+1.01** | 0.29 / 0.27 | 0.0 / 72 | no |
| IRM output 14.7 V (-2 %) | 9.38..10.00 | 8.43 | **+1.17** | 0.29 / 0.27 | 0.0 / 43 | no |
| **worst corner (all of the above, 2 ms)** | 8.51..9.48 | 7.50 | **+0.17** | 0.40 / 0.38 | 0.0 / 81 | no |
| *history: G6K scheme (no stagger, no load or leg diodes, no limiter)* | 9.79..10.41 | 9.43 | *+2.17* | 0.38 / 0.36 | 97.2 / 34 | no |
| *option: 30 s swap (R_t 160 k), nominal* | 8.90..10.10 | 7.95 | *+0.69* | 0.40 / 0.40 | 97.2 / 15 | no |
| *option: 30 s swap, worst corner* | 7.89..9.73 | 6.88 | *-0.44* | 0.40 / 0.40 | 118.2 / 54 | yes |
| *history: rev 0.1 (8.45 V, 30 s swap), nominal* | 9.58..10.78 | 9.22 | *+0.49* | 0.61 / 0.57 | 97.2 / 19 | no |
| *history: rev 0.1, worst corner* | 8.32..10.15 | 7.79 | *-0.99* | 0.89 / 0.83 | 118.2 / 54 | yes |

- **Charger and cell voltage.** The CV point is 10.76 V (120 Ω / 909 Ω plus the
  LM317's 50 µA adjust current; the 10.5 mA divider keeps the LM317 above its 10 mA
  minimum load). A bucket with no load floats two SS34s lower (the charger diode and
  its negative-leg diode, ≈0.2 V each at the tail current), ≈10.3 V: 2.6 V per 2.7 V
  cell, and about 2.7 V at the LM317's limits (V_REF 1.30 V, I_ADJ 100 µA). Rev 0.1's 1.87 kΩ set 11.08 V, which
  floats the cells at 2.72 V with no load (2.83 V at the limits).
- **Sawtooth.** On the charger a bucket takes the full 0.2 A until CHG reaches
  its set point, then tapers off in CV, and tops out at 10.03 V after 15.2 s. In
  15.2 s the 0.1 A load drains 0.6 V from 2.5 F; the load path (SS34, 1 Ω, the
  limiter's 1.6 Ω, the negative-leg SS34, ESR) drops ≈1.0 V. That leaves the 6.98 V
  LT3045 **1.20 V** above dropout at the nominal point, **≥ 0.90 V** in every single
  corner and only **+0.17 V** with every corner stacked, where the two LM317
  dropouts, not the CV point, limit the charge. The leg diodes and the limiter cost
  about 0.7 V of the earlier +0.88 V: the stacked corner still passes, but thinly.
  If bench measurements show less, lower R12/R13 (1 Ω → 0.47 Ω, +0.05 V) or swap the
  leg SS34s for lower-drop Schottkys. (The
  G6K scheme had 0.27 V more, without the diode.) (Rev 0.1,
  at 8.45 V with a 30 s swap, had 0.49 V nominal and dropped out with the
  corners stacked.)
- **Option: a 30 s swap.** At 6.98 V the swap could be slowed to 30 s (CD4060
  R_t 160 kΩ), which halves the relay operations (STATUS.md, relay endurance).
  The bucket then swings 1.2 V and the headroom falls to 1.02 V nominal and
  0.19 V with every corner stacked, and the worst-corner contact peak (0.58 A)
  passes the reed's 0.5 A rating. The as-built 15.2 s stays.
- **Swap transient.** The arriving bucket makes onto LOAD_P while the leaving
  one is still connected, so LOAD_P never dips. The fresh bucket charges the
  reservoir through its SS34, 1 Ω and the limiter: the 0.29 A contact peak.
- **Dry load break.** 30 ms later (10 ms in the fast-gate case) the leaving
  bucket's load contacts open dry (0 mA): its diode is reverse biased. With
  the G6K scheme they broke the full ~0.1 A load current at ~10 V.
- **Charger break.** The arriving bucket leaves the charger at the tail of its
  CV taper: 25–40 mA in the single corners, 81 mA stacked.
- **Relay contacts in steady state.** Every design case stays below the reed's
  0.5 A switching rating: 0.25 A nominal, 0.35 A in the stacked worst corner.

### 2.2 Swap artefact spectrum (`psu_artefact_spectrum.svg`)

The LT3045 input waveform is taken over exactly two steady-state periods, fed
through an FFT, passed through the PSRR chain, and binned (0.1 Hz and 1 Hz
bins, line power / bin width). The worst bin in 1–50 Hz is shown.

| Point | 0.1 Hz bins | 1 Hz bins |
|-------|------:|------:|
| LT3045 input (sawtooth + step) | 34 mV/√Hz | 24 mV/√Hz |
| LT3045 output | 66 nV/√Hz | 45 nV/√Hz |
| ADM7150 +5VA output | 2.1 pV/√Hz | 1.4 pV/√Hz |
| Referred to antenna, typical PSRR | 2 × 10⁻¹⁴ V/√Hz | 1.3 × 10⁻¹⁴ V/√Hz |
| **Margin below the 46 nV/√Hz floor, typical** | **126 dB** | **130 dB** |
| **Margin, pessimistic PSRR** | **86 dB** | **90 dB** |

In the time domain, the swap step is 3.8 µV p-p at the LT3045 output and
0.12 nV p-p at the ADM7150 output (0.74 V p-p at the LT3045 input). **Nothing from the swap is visible in 1–50 Hz**,
even with every PSRR 20–25 dB worse than typical.

The dominant coupling path turns out to be the PCM1804 VCOM (VINL− = VCOM, see
`simulations/system`), not the LMP7721 PSRR. Along that path the LDO noise, not
the swap, sets the level: ≈1.0 nV/√Hz at the antenna at SR1, which is 33 dB
below the floor.

### 2.3 Cold start (both buckets empty, relay timer starts with the coil off)

| | As built | History: rev 0.1 |
|---|---:|---:|
| ADM7150 rails valid (5 V ≥ 4.99 V, input ≥ 5.5 V), continuously from | 289 s | 271 s |
| LT3045 in regulation, continuously from | 319 s | 391 s |
| Contact peak, instantaneous | 1.09 A | 3.2 A |
| Contact peak, 1 ms average | 0.39 A | 1.0 A |

**Cold start takes about 5 minutes** to valid amplifier rails and 5.3 minutes to
a regulated LT3045 output (rev 0.1: 6.5 minutes). This follows from the charge budget:
0.2 A CC into 2 × 2.5 F while 0.1 A is drawn.

Rev 0.1's 3.3 A instantaneous peaks came from the 10 µF on CHG (the LM317
output) discharging into an empty bucket through 2.2 Ω: ≈24 µs and ≈90 µC,
whenever a nearly empty bucket reached the charger during start-up. With 100 nF
on CHG the spike carries ≤ 1 µC and lasts well under a microsecond. The model's
20 µs contact-closure ramp stretches it into the 0.96 A instantaneous peak
above, after which the contact carries the 0.2 A charging current. The largest
sustained current, 0.40 A over 1 ms (the limiter), flows when a bucket makes onto the
reservoir, within the reed's 0.5 A.

### 2.4 Hold-up after mains failure

When the coil supply fails, the relays fall back to "A on charger, B on load"
(bucket B's relays are wired the other way round for this). Only bucket B then
feeds the receiver.

| Swap phase at failure | LT3045 regulates for | ADM7150 rails valid for |
|---|---:|---:|
| Worst (B was just drained) | 32 s | 44 s |
| Best (B just charged) | 46 s | 58 s |

After the LT3045 drops out, the ADM7150s still regulate for about 12 s.

### 2.4a Mains back after an outage

Through an outage bucket B alone feeds the load and drains the reservoir; bucket A
sits full on the idle charger. At the first swap after the mains returns, A makes
onto the drained reservoir. A small dedicated circuit (bucket A, the reed contact,
SS34, load resistor, limiter, 2200 µF with a 0.1 A load; reservoir at 4.5 V, A at
9.95 V) gives the make current:

| Load path | Contact peak | 1 ms average |
|---|---:|---:|
| as built: 1 Ω + 0.4 A limiter | 0.45 A | **0.40 A** |
| earlier: 3.3 Ω, no limiter | 1.41 A | 1.33 A |

The reed's switching rating is 0.5 A; without the limiter every restore after a
longer outage overloaded the contact. The
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
compared directly with the 29.5 mV rms 50 Hz clip level (`simulations/system`)
and the 1–5 mV mains pickup.

| Coupling | I_leak (rms) | V_g earthed, 100 Ω | V_g floating |
|---|---:|---:|---:|
| Direct IRM module, 50 pF barrier, V_L/2 | 1.8 µA | 0.18 mV | 14 V |
| Direct IRM module, 100 pF barrier, V_L | 7.2 µA | 0.72 mV | 50 V |
| Two-bucket (GND_C = PE), open contacts + coil–contact C_x = 2 pF, PE 0.3 V | 0.19 nA | 19 nV | 1.7 mV |
| same, C_x = 10 pF (as built: 4 reeds, ≈8 pF), PE 3 V | 9.4 nA | 0.94 µV | 81 mV |
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
| A1 sawtooth | LT3045 never drops out, including the stacked worst corner | **PASS** (+1.20 V nominal, ≥ +0.90 V in every single corner, **+0.17 V** stacked: thin) |
| A1 relay contacts, steady state | ≤ 0.5 A (reed switching rating) | **PASS** (0.29 A nominal, 0.40 A worst corner) |
| A1 load contacts open dry | < 10 mA at opening | **PASS** (0 mA in every design case; G6K scheme: 97–118 mA) |
| A1 relay contacts, cold start | ≤ 0.5 A sustained | **PASS** (0.40 A over 1 ms; the ≤ 1 µC make spike from the 100 nF on CHG shows as 0.96 A through the model's 20 µs contact ramp) |
| A1 relay contacts, mains back after an outage | ≤ 0.5 A | **PASS** (0.40 A over 1 ms with the limiter; 1.33 A without) |
| A2 swap artefact in 1–50 Hz | below receiver floor | **PASS**, ≥ 126 dB (typ) / ≥ 86 dB (pessimistic) below |
| A3 cold start | report | 258 s to the first valid rails, LT3045 in regulation for good from 319 s |
| A4 hold-up | report | 32–46 s regulated, 44–58 s ADM7150 rails |
| A5 50 Hz leakage | ≪ direct module; below mains pickup | **PASS** when the receiver is earthed (≤ 3 µV). Marginal when floating (up to 0.23 V > 29.5 mV clip) |

### Findings and their status

1. **LT3045 dropout margin (A1) -- fixed in rev 0.2.** Rev 0.1 (8.45 V, 30 s)
   had 0.49 V of headroom and dropped out with the corners stacked (−0.99 V).
   Two resistors changed, no new parts:
   - **R_SET 84.5 k → 69.8 k** (V_OUT 8.45 → 6.98 V). The amplifier's ADM7150
     inputs stay at ≥ 5.8 V in the worst corner (the choke's 6.8 Ω and the SS34
     included), which leaves 0.8 V of headroom for the 5.0 V part (dropout 0.15 V).
   - **CD4060 R_t 160 k → 80.6 k**: a swap every 15.2 s instead of 30 s halves
     the droop, and the 33 mHz swap rate is still far below the ELF band.
   - Verified then: +0.88 V with every corner stacked; +0.17 V since the review's
     leg diodes and limiter (2.1).
2. **Relay contact endurance -- addressed (2026-10-31).** A swap every 15.2 s is
   about 1 M operate/release cycles per relay per year. The G6K-2F-Y had no
   datasheet figure for its duty (make 0.3–0.6 A, break ~0.1 A at ~10 V). Now:
   Standex SIL05-1C90-51D reeds (rhodium, 10 W / 0.5 A, 1.5 pF open), and the
   staggered swap makes the load contacts open dry (< 2 mA; the datasheet's
   "< 5 V / 10 mA" bar is ~10⁸ operations, about 100 years). The charger contacts
   open at 25–81 mA near 10 V, between the "10 V / 4 mA" (~5·10⁷) and
   "10 V / 100 mA" (~7·10⁶) bars: 7–50 years. Makes are into a resistor-limited
   capacitor at ≤ 0.35 A. Still worth a bench endurance run before deployment. A
   photo-MOS switch would not do: its off-state capacitance (tens of pF) defeats
   the isolation the open contacts provide.
3. **Cold-start inrush -- fixed in rev 0.2.** C on CHG went from 10 µF to 100 nF
   (C3; the LM317 needs no output capacitor for stability), which cuts the make
   spike from ≈90 µC to ≤ 1 µC.
4. **Floating receiver -- by installation.** Earth the outdoor receiver ground
   locally (MOUNTING.md section 6), and keep the PSU box and its PE bond away
   from the receiver side. Otherwise PE-to-local-earth voltage couples through
   the 2–30 pF strays.
5. **EDLC float voltage -- fixed in rev 0.2.** The 240 Ω / 1.87 kΩ divider set
   the charger to 11.08 V (it was labelled 10.9 V). Whenever the receiver draws
   nothing, that floats the 2.7 V cells at 2.72 V, and at 2.83 V at the LM317's
   limits. R4 became 1.74 kΩ: 10.4 V, 2.55 V per cell nominal and 2.70 V at
   the limits. Since the 2026-10-31 review it is 120 Ω / 909 Ω (10.76 V, 10.5 mA, above
   the LM317's minimum load), compensating the second SS34 now in each bucket's
   charger leg; the cells see the same voltage. That also helps the life of cells that sit in a warm outdoor
   box. In service it costs little (section 2.1). At the same time the charger
   model was corrected: below 0.2 A the CC stage drops 6.2 Ω·I, not the full
   1.25 V, which is why the cold and low-mains corners improved.

## 4. Limitations

- All regulators are behavioural. There is no LT3045 current-limit foldback or
  PGOOD, no ADM7150 start-up sequencing, and no LM317 thermal limit.
- EDLCs are ideal C + ESR. There is no charge redistribution, no leakage beyond
  the balancing resistors, and no voltage coefficient.
- The PSRR curves are simplified fits to datasheet-typical plots. The
  conclusion (≥ 86 dB margin) is insensitive to them.
- The leakage model uses lumped strays. Real values depend on the enclosure,
  cable routing and site earthing.
