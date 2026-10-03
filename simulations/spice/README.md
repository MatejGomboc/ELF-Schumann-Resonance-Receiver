# ELARA front end -- ngspice verification

Circuit-level check of the analogue chain from the antenna EMF to the PCM1804
input (VINL), using ngspice-42. It cross-checks the analytical noise budget in
`simulations/preamp_noise/`, `simulations/input_filter/` and
`simulations/antenna/` (PLAN.md §3.0–§3.5).

| File | Contents |
|------|----------|
| `elara_frontend.cir` | Parameterised, commented netlist. It runs on its own: `ngspice -b elara_frontend.cir` |
| `lmp7721_behav.lib` | Behavioural LMP7721 macromodel, LMP7715-class noisy buffer, and noise-generator subcircuits |
| `run_spice.py` | Runs every analysis and sweep, then writes `results.json` and the three SVG plots |
| `results.json` | All numerical results |
| `frontend_ac.svg` | AC transfer from 0.1 Hz to 1 GHz, with C_ant, ADC-load and parasitic-C variants |
| `frontend_noise.svg` | Noise breakdown, design variants, and a self-test of the macromodel noise |
| `bias_resistor_tradeoff.svg` | Input DC bias: noise, low-frequency response and DC offset against R_hb |

Run it with:

```bash
.venv/bin/python simulations/spice/run_spice.py      # Linux
.venv/Scripts/python simulations/spice/run_spice.py  # Windows
```

The script needs `ngspice` on the PATH. A full run takes about 5 s.

---

## 1. Circuit simulated

This is the front end as built, up to the anti-alias filter. The ADC driver
(U301, then 100 Ω + 2.7 nF C0G at VINL+) and the PCM1804 are left out: with the
driver in place the ADC no longer loads the filter (section 4.2), and
`simulations/system` adds their noise. The two items marked ★ started as
changes to the original PLAN text and are now part of it (PLAN §0): Cg returns
to GND instead of BIAS_MID, and R_hb is the J202 bias resistor. R3 in this
netlist is R2 on the plate-capacitor assembly (`mechanical/platecap.py`).

```
Vsig --||-- ANT --R1 33k-- N1 --R3 33k-- IN_P ----> LMP7721 IN+
     C_ant           Cf1 50p        Cf2 50p  |- R_leak 1T to GND (noiseless)
                                             |- PCB leakage noise 0.1 fA/rtHz
                                             |- [R_hb to 2.5 V REF]   ★ optional
LMP7721: Rf 100k || Cf 15n (IN- to VOUT); Rg 1k -- Cg 100u -- GND    ★ (originally BIAS_MID)
VOUT --C_out 10u-- A --R_AA 10k-- VINL --C_AA 100n-- VCOM ; R_bias 47k A to VCOM
[R_adc from VINL to VCOM]  (optional; stands in for the unknown PCM1804 input load)
```

- **Antenna.** An ideal EMF source in series with C_ant. The nominal value is
  140 pF; 50 pF and 300 pF are also swept.
- **Filter capacitors.** The air-gap capacitors are ideal and lossless.
  Optionally, 0.2 pF of parasitic capacitance can be placed across each 33 kΩ
  resistor.
- **Guard buffer.** It is driven from IN− and does not load IN_P, so it is left
  out of the small-signal model.
- **R_leak.** A DC-convergence element with `noisy=0`. Leakage current noise is
  modelled only by the explicit 0.1 fA/√Hz PCB source (PLAN §3.3), so it is
  not counted twice. For reference, a *thermal* 1 TΩ resistor would contribute
  √(4kT/R) = 0.13 fA/√Hz.
- **Temperature.** All runs use T = 300 K (`.options temp=26.85`), the same as
  the Python scripts.

## 2. LMP7721 behavioural macromodel

TI's vendor model could not be downloaded, so the op-amp is a behavioural
model:

- **Gain stage.** A single-pole transconductance stage with A0 = 120 dB and
  GBW = 17 MHz, followed by an ideal output buffer. The model has no rails,
  no slew limit and no input capacitance. Input capacitance can be added with
  `CIN_EN`.
- **Voltage noise.** e_n(f) = 6.5 nV/√Hz · √(1 + 10 Hz / f), in series with IN+.
  These are the same numbers `preamp_noise_analysis.py` and
  `passive_noise_budget.py` use, and they give e_n(7.83 Hz) = 9.81 nV/√Hz.
- **Current noise.** i_n = 0.01 fA/√Hz (white), on IN+.

**How the 1/f noise is generated (`VNOISE_1F`).** ngspice has no noise voltage
source, so the noise is made in an isolated loop and injected with noiseless
controlled sources:

1. A 1 kΩ resistor with a flicker-noise model (`kf`, `af = 2`) is biased by
   1 V DC and shorted through a 0 V sense source.
2. In `.noise`, the resistor's short-circuit current PSD is
   4kT/R + KF·I²/f.
3. A CCVS (`H` element) with transresistance RT = EN/√(4kT/R) turns this into a
   series voltage noise EN²·(1 + FC/f), with KF = (4kT/R)·FC/I².
4. A noiseless DC current sink cancels the 1 mA bias in the sense source, so
   the H element produces noise only and no DC offset.

White current noise (`INOISE`) uses the same trick: the thermal current of a
shorted 1 kΩ resistor is scaled by a CCCS.

**Self-test.** The op-amp is run as a unity follower with IN+ grounded, and its
output noise is compared with the target curve (bottom panel of
`frontend_noise.svg`). From 0.1 Hz to 10 kHz the maximum relative error is
**1.3 × 10⁻⁶**, and e_n(7.83 Hz) = 9.809 nV/√Hz against a target of
9.809 nV/√Hz.

## 3. Results, nominal design

The nominal case is C_ant = 140 pF, Cg returned to GND, ADC input at high
impedance and no R_hb.

### 3.1 At the Schumann frequencies

"Amp input" means the noise referred to LMP7721 IN+, which is the same
reference point as the Python budget's "total at amplifier input". "Antenna"
means the noise referred to the antenna EMF (the ngspice `inoise`).

| Mode | f (Hz) | Gain ant→VINL (dB) | Noise, amp input (nV/√Hz) | Noise, antenna (nV/√Hz) | Python, amp input | Python, antenna |
|------|-------:|------:|------:|------:|------:|------:|
| SR1 | 7.83 | 35.10 | **26.7** | **45.8** | 37.7 | 64.6 |
| SR2 | 14.3 | 35.15 | 25.3 | 43.3 | 35.3 | 60.5 |
| SR3 | 20.8 | 35.06 | 24.9 | 42.6 | 34.7 | 59.5 |
| SR4 | 27.3 | 34.90 | 24.7 | 42.3 | 34.4 | 59.0 |
| SR5 | 33.8 | 34.70 | 24.6 | 42.1 | 34.3 | 58.8 |
| SR6 | 39.0 | 34.51 | 24.5 | 42.0 | 34.2 | 58.7 |
| SR7 | 45.0 | 34.27 | 24.5 | 42.0 | 34.2 | 58.6 |

Integrated noise from 3 to 45 Hz, referred to the antenna, is **0.28 µV rms**.

### 3.2 Frequency response

- **Peak gain.** 35.16 dB at 12 Hz. PLAN's figure of 40.1 − 4.7 = 35.4 dB
  ignores the Rg·Cg and Rf·Cf corners.
- **−3 dB corners.** **1.61 Hz** (set by Rg·Cg) and **83.9 Hz** (the 106 Hz
  preamp pole and the 159 Hz AA pole combined).
- **In-band flatness.** **0.88 dB** from SR1 to SR7. The response is highest at
  12 Hz and falls by 0.9 dB at 45 Hz. This is a fixed, known droop and can be
  equalised in software.
- **Cap-divider loss.** Antenna → IN+ is −4.68 dB, which matches PLAN.

### 3.3 RF rejection, antenna EMF → LMP7721 IN+

| Frequency | Ideal parts | 0.2 pF across each 33 kΩ | PLAN §3.0 |
|-----------|------------:|--------------------------:|-----------|
| 1 MHz   | **−40.9 dB** | −41.0 dB | −41 dB (RC) plus a flat −4.7 dB |
| 100 MHz | **−120.6 dB** | **−95.5 dB** | −121 dB (RC) plus a flat −4.7 dB |

- **The −4.7 dB divider does not apply at RF.** At 1 MHz, C_ant is only 1.1 kΩ,
  which is small next to the filter input impedance, so the capacitive-divider
  loss vanishes. The total rejection equals PLAN's "RC-only" figures, not
  those figures plus 4.7 dB.
- **FM rejection is limited by parasitic capacitance.** About 0.2 pF across each
  33 kΩ resistor, typical for a 1206 or MELF body, limits FM rejection to about
  −95 dB. Real rejection at 100 MHz depends on layout and parasitics, not on
  the ideal RC values.
- **Antenna → VINL.** The ideal model gives −117 dB at 1 MHz and −252 dB at
  100 MHz, but these figures are meaningless beyond a few MHz. The model has
  no output impedance, no parasitics and no RF rectification. Treat the IN+
  values above as the relevant figures.

### 3.4 Noise breakdown at SR1, referred to the antenna

| Source | ngspice (nV/√Hz) | Share of power | Python budget, referred to antenna |
|--------|------:|------:|------:|
| R3 33k (amplifier side) | 31.7 | 48 % | 40.1 |
| R1 33k (antenna side) | 23.4 | 26 % | 40.1 |
| LMP7721 e_n (with 1/f) | 16.8 | 13 % | 16.8 |
| PCB leakage 0.1 fA/√Hz | 14.5 | 10 % | 24.9 |
| Rg 1k | 6.9 | 2 % | 7.0 |
| LMP7721 i_n | 1.45 | 0.1 % | 2.5 |
| Rf 100k | 0.70 | – | 0.7 |
| R_AA 10k and R_bias 47k | 0.22 and 0.02 | – | – |
| **Total** | **45.8** | | **64.6** |

### 3.5 Why ngspice is 29 % lower than PLAN (45.8 vs 64.6 nV/√Hz)

The Python budget adds every source at IN+ and then divides the total by the
cap-divider ratio 0.583. That is exact only for sources whose transfer to IN+
is the same as the signal's. Two groups of sources are different:

1. **R1.** Its noise EMF is in series with the antenna, so it reaches IN+
   through exactly the same divider as the signal. Referred to the antenna it
   is 23.4 nV/√Hz, not 23.4 / 0.583 = 40.1 nV/√Hz.
2. **R3.** It sees (C_ant + Cf1) = 190 pF on one side and Cf2 = 50 pF on the
   other. Its transfer to IN+ is 190/240 = 0.79, so referred to the antenna it
   is 23.4 × 0.79 / 0.583 = 31.7 nV/√Hz.
3. **Current noise at IN+.** The PCB leakage and i_n see the whole node
   capacitance C_ant + 100 pF = 240 pF, not C_ant alone. At IN+ that gives
   0.1 fA × 84.7 MΩ = 8.5 nV/√Hz. Referred to the antenna it is i·|Z_Cant| =
   14.5 nV/√Hz, whereas Python divides 14.5 by 0.583 again to get 24.9 nV/√Hz.

Only e_n, Rg and Rf are truly "at IN+", and those agree to within 1 %. The
Python model is therefore **pessimistic by 3.0 dB** at SR1. The real design is
better than PLAN claims, and the ranking of sources changes: R3 dominates, and
R1, e_n and PCB leakage follow.

The error grows at small C_ant:

| C_ant | ngspice, antenna (nV/√Hz) | Python (nV/√Hz) | Gain at SR1 |
|------:|------:|------:|------:|
| 50 pF | 73.6 | 160.9 | 30.24 dB |
| 140 pF | 45.8 | 64.6 | 35.10 dB |
| 300 pF | 39.2 | 47.2 | 37.28 dB |

## 4. Design variants

### 4.1 ★ Cg returned to GND instead of BIAS_MID

The alternative is a BIAS_MID return driven by an LMP7715-class buffer. Its
noise reaches the output through −Rf/(Rg + Z_Cg), which is the same magnitude
as the non-inverting noise gain, so it adds to e_n almost 1:1.

The buffer is assumed to have **5.8 nV/√Hz white noise with a 30 Hz 1/f
corner**. The 30 Hz corner is my assumption, deliberately more pessimistic
than the 10 Hz used for the LMP7721.

| Cg return | Total at SR1, antenna | Buffer contribution, antenna | Amp input |
|-----------|------:|------:|------:|
| GND (build) | 45.8 | – | 26.7 |
| BIAS_MID, corner 30 Hz | 50.7 (+0.9 dB) | 21.6 | 29.5 |
| BIAS_MID, corner 10 Hz | 48.1 (+0.4 dB) | 14.9 | 28.1 |

The GND return removes a source that would have been the third-largest at
SR1 with a 30 Hz corner, or the fourth-largest with a 10 Hz corner. The change is justified.

**DC note.** Cg blocks DC with either return, so V_OUT,DC = V_IN+,DC. The DC
level at IN+ must therefore be set near 2.5 V from the input side (see §5).

### 4.2 Finite ADC input resistance (R_adc from VINL to AC ground)

| R_adc | Gain at SR1 | −3 dB corners | Flatness SR1–SR7 |
|------:|------:|------|------:|
| ∞ | 35.10 dB | 1.61 / 83.9 Hz | 0.88 dB |
| 100 kΩ | 34.28 dB | 1.67 / 86.6 Hz | 0.83 dB |
| 20 kΩ | 31.59 dB | 1.89 / 94.4 Hz | 0.71 dB |
| 5 kΩ | 25.52 dB | 2.25 / 105 Hz | 0.59 dB |

- **Noise.** Noise referred to the antenna does not change (45.8 nV/√Hz),
  because the loss comes after 40 dB of gain.
- **Loading.** The AA filter's 10 kΩ source impedance makes the gain depend on
  the ADC's input load. A PCM1804 switched-capacitor input driven from 10 kΩ
  will also suffer charge kickback. That is why rev 0.2 fits a driver: U301
  (LMP7715, unity gain) after the AA filter, then 100 Ω + 2.7 nF C0G at VINL+,
  so the ADC's input no longer loads the filter.

### 4.3 Op-amp input capacitance (assumed 10 pF, not from the datasheet)

A 10 pF common-mode input capacitance adds to Cf2. At SR1 the gain drops to
34.75 dB (−0.35 dB) and the noise referred to the antenna rises to
46.1 nV/√Hz. This effect is small.

## 5. ★ DC bias of the input node, and the bias resistor

### 5.1 The atmospheric conduction current

A conductor held near ground potential in the fair-weather field
(E ≈ 100 V/m) sits in air whose ambient potential at the antenna height is
V_amb ≈ E·h. The antenna therefore carries a bound charge
Q = C_ant·V_amb. Gauss's law and Ohm's law in the air (conductivity
σ ≈ 10⁻¹⁴ S/m) then give a conduction current collected by the antenna:

  I = σ·∮E·dA = σ·Q/ε₀

For the 10 m ELARA antenna with C_ant = 140 pF:

- **Charge-weighted height 6.5 m.** V_amb ≈ 650 V, Q = 91 nC, **I ≈ 100 pA**.
- **Full height 10 m.** V_amb ≈ 1000 V, Q = 140 nC, **I ≈ 160 pA**.

This current varies with σ (pollution, humidity, fog) and E (weather) by
roughly ×0.3 to ×5 in fair weather, and by orders of magnitude under disturbed
conditions. The design value is therefore around **100 pA**, with 1–10 pA only
for a sheltered or insulated antenna.

### 5.2 The floating input cannot hold a DC operating point

With the jumper removed and no DC path, 100 pA charges the
240 pF input node at **0.42 V/s**, so IN+ leaves a ±1 V window in about 2.4 s.

A 1 TΩ leakage would allow an offset of I × R_leak = 100 V, and 10 TΩ would
allow 1 kV. Either way the input rails within seconds, and it then sits
wherever leakage and clamping put it. The input only stops charging when the
antenna reaches ambient potential, with τ = ε₀/σ ≈ 15 min, which means
hundreds of volts.

**The jumper-only "floating input" scheme cannot hold a DC operating point
while the antenna collects conduction current.** A permanent DC path is
required, or the conduction current must be kept off the input (§5.4).

### 5.3 Bias resistor R_hb from IN+ to a 2.5 V reference

The ngspice results below assume R_leak = 1 TΩ to GND in parallel.

| R_hb | High-pass at IN+ | Noise at SR1, antenna (total) | R_hb share | Offset at 1 / 10 / 100 pA |
|-----:|------:|------:|------:|------|
| none | 0.66 mHz (R_leak) | 45.8 | – | 1 V / 10 V / 100 V |
| 1 TΩ | 1.3 mHz | 49.5 | 18.7 | 0.5 V / 5 V / 50 V |
| 100 GΩ | 7.3 mHz | 74.8 | 59.1 | 0.09 V / 0.9 V / 9.1 V |
| 10 GΩ | 67 mHz | 192 | 187 | 0.01 V / 0.1 V / 0.99 V |
| 1 GΩ | 0.66 Hz | 593 | 591 | 1 mV / 10 mV / 0.1 V |

- **The resistor's noise, referred to the antenna,** is exactly
  e = √(4kT/R_hb) / (ω·C_ant) at all frequencies. It falls as 1/f and is
  independent of the filter capacitors. It is shown dashed in
  `bias_resistor_tradeoff.svg`.
- **The low-frequency effect** is a first-order high-pass at
  1/(2π·R_hb·240 pF). Even at 1 GΩ this is 0.66 Hz, below the 1.6 Hz Rg·Cg
  corner, so the signal band is unaffected for every value tested.
- **Divider with the leakage resistance.** The zero-current DC point is set by
  R_hb against the leakage resistance. With R_hb = 1 TΩ against a 1 TΩ leakage
  to GND, IN+ sits at 1.25 V, not 2.5 V. R_hb must be at least 10 times smaller
  than the leakage resistance to ground. A guard at input potential helps,
  because the leakage then returns to the guard.

**Trade-off.** Keeping the R_hb noise contribution no larger than the rest of
the budget needs R_hb ≳ 170 GΩ. Keeping the offset within ±1 V at 100 pA needs
R_hb ≲ 10 GΩ. These requirements only overlap when **I_atm ≲ 6 pA**.

- For the expected ~100 pA, a DC-coupled bias of **1–10 GΩ** is the only
  workable choice. It raises the noise at SR1 to 190–590 nV/√Hz.
- For I_atm ≲ 5 pA, **100 GΩ–1 TΩ** is right. It adds only 0.7–4.3 dB at SR1.

### 5.4 The underlying limit: ion-current shot noise

The resistor is not really the fundamental problem. If the ion arrivals are
Poissonian, a collected current I carries shot noise √(2qI). Referred to the
antenna this is √(2qI) / (ωC_ant):

| I_atm | Shot noise | At SR1, referred to antenna |
|------:|-----------:|-------------:|
| 100 pA | 5.7 fA/√Hz | **820 nV/√Hz** |
| 10 pA | – | 260 nV/√Hz |
| 1 pA | – | 82 nV/√Hz |

For comparison, the electronics floor is 45.8 nV/√Hz, and the quiet SR1
signal (0.3 µV/m × 6.5 m) is 1950 nV/√Hz.

A bias resistor sized for a 1 V drop, R = 1 V / I, has a thermal-noise PSD of
only 2kT/(q·1 V) = **5 %** of this shot-noise PSD. So once the antenna
collects conduction current, the ion shot noise dominates, not the resistor.
This is plotted in `bias_resistor_tradeoff.svg`.

**Recommendation.** Stop the steady-state conduction current from reaching the
input, then bias IN+ with **R_hb ≈ 100 GΩ–1 TΩ** to the 2.5 V reference. The
added noise is +0.7 to +4.3 dB at SR1, and the offset from the 20 fA LMP7721
bias current is only 2–20 mV. Two ways to keep the conduction current off the
input:

- Use an **insulated antenna element**, such as PE- or PTFE-jacketed wire and
  an insulated top hat.
- DC-block the antenna with a high-voltage, very low-leakage coupling capacitor
  and let the element float to the local air potential. The time constant is
  ε₀/σ ≈ 15 min, well below the ELF band.

In either case the surface charges to the local potential and the net
conduction current dies away. If the antenna must stay DC-coupled and
uninsulated, expect a fair-weather floor of several hundred nV/√Hz at SR1
whatever the bias resistor. In that case use R_hb ≈ 1–10 GΩ.

The shot-noise estimate is an upper bound, since it assumes uncorrelated,
singly charged ions. It should be checked in the field, for example by
comparing the noise with the antenna insulated and uninsulated.

## 6. Limitations

- The op-amp is behavioural. It has no rails, output impedance, input
  capacitance, RF rectification or slew limit. RF numbers beyond the input
  filter (antenna → VINL above a few MHz) are not physical.
- Passives are ideal. There is no excess (1/f) resistor noise, no capacitor
  dielectric loss, and no leakage apart from R_leak. GΩ-range bias resistors
  often show significant excess noise; check this with the vendor.
- The PCM1804 input is modelled only as a resistance.
- The 1/f corner of the LMP7715 is assumed, not taken from the datasheet.
