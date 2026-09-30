# ELARA op-amp stages -- stability verification

This folder checks phase margin and step response for the four op-amp stages
in `PCB/antenna_amplifier/design.py`, using ngspice-42 and a behavioural
two-pole op-amp model.

| File | Contents |
|------|----------|
| `run_stability.py` | Builds the netlists, runs 189 ngspice cases (AC loop gain + transient in one run each), writes `results.json` and two plots |
| `stability_bode.svg` | Loop gain magnitude and phase for each stage, nominal and worst corner |
| `stability_margins.svg` | Phase-margin range over the full sweep (with "no isolation resistor" counterfactuals), and step responses in the worst corner |

Run it with `.venv/bin/python simulations/stability/run_stability.py`. It takes about 50 s.

## 1. Method

**Op-amp model.** The vendor models are not available, so the op-amp is a
two-pole behavioural model:

- gm stage with A0 = 120 dB and GBW = 17 MHz (LMP7715 and LMP7721 datasheet
  typical);
- a second pole at FP2;
- a unity buffer with open-loop output resistance RO;
- common-mode input capacitance CIN on each input;
- 10 pF of stray on every output pin (trace and test point).

For a follower, the IN− capacitance sits on the output pin as well.

**Loop gain.** The loop is broken inside the op-amp. The gm stage senses a 1 V
AC test source instead of (IN+ − IN−), and the return ratio is
T = −(v(IN+) − v(IN−))/v_test. This is exact for this model: its inputs draw
no current apart from through the explicit input capacitances, and those stay
in the circuit. Phase margin is taken at the last |T| = 1 crossing, and gain
margin at −180°.

**Step response.** A 10 mV, 1 ns step is applied to the non-inverting input.
Overshoot is max(v_real − v_ideal)/step, where v_ideal comes from the same
circuit with a 10 GHz op-amp and RO = 1 mΩ. This way the RC low-pass of the
isolation resistors, and the slow Rg–Cf ramp of U201, are not counted as
overshoot.

| Swept parameter | Values |
|---|---|
| Second pole FP2 | 40 / 60 / 80 MHz |
| Open-loop output resistance RO | 50 / 100 / 200 Ω |
| Input capacitance CIN (each input) | 10 / 20 pF |
| U202 guard capacitance | 20 / 50 / 100 / 200 pF |
| U203 input-node capacitance (J202 shunt fitted) | 240 / 500 pF lumped |

The **nominal** corner is 60 MHz, 100 Ω, 10 pF. The **worst** corner is 40 MHz, 200 Ω, 20 pF.

Circuits modelled (values from design.py):

| Stage | Loop | Load at the output pin |
|---|---|---|
| U301 LMP7715 ADC driver | follower; IN+ = AA node (10 k from 8.5 k source, 100 nF to VCOM) | 100 R + 2.7 nF C0G (plus ADC) |
| U202 LMP7715 guard buffer | follower; IN+ = IN− of U201 (~1 k to AC ground at HF) | 470 R + C_guard |
| U203 LMP7715 bias buffer | follower; IN+ = divider node (23.5 k ‖ 4700 µF) | 1 k + input node C (J202 shunt fitted, the worst case; with a GΩ resistor fitted it is unloaded) |
| U201 LMP7721 G = 101 | Rf 100 k ‖ Cf 15 nF, Rg 1 k + Cg 100 µF to GND; U202 input (10 pF) on IN−; IN+ = full RC filter + 140 pF antenna, J202 = 1 G | C_out 10 µF → 47 k ‖ (10 k + 100 nF), i.e. ≈ 8.5 k at HF, plus the feedback network |

## 2. Results

| Stage | PM nominal | PM min (corner) | GM min | Overshoot at pin, max | Overshoot at load node, max | Without R_iso (info) | Verdict (PM ≥ 45°) |
|---|---:|---|---:|---:|---:|---:|:---:|
| U301 ADC driver | 77.0° | 69.8° (40 MHz, 50 Ω, 20 pF) | 24.6 dB | 5.1 % | 0.7 % | 4.3° / 89 % overshoot | **PASS** |
| U202 guard buffer | 61.4° (20 pF) … 68.1° (200 pF) | **42.9°** (20 pF, 40 MHz, 200 Ω, 20 pF) | 15.0 dB | 26 % | 17 % | 15.7° / 64 % | **FAIL** (worst corner only) |
| U202 + proposed 220 pF C0G on GUARD | – | 56.4° (worst corner) | – | 12.6 % | – | – | **PASS** |
| U203 bias buffer | 66.3° | 50.6° (240 pF, worst corner) | 14.0 dB | 18 % | 0.0 % | 10.0° / 76 % | **PASS** |
| U201 LMP7721 G = 101 | 62.8° | 47.3° (worst corner) | 13.2 dB | 21 % | 21 % | – | **PASS** (small margin) |

Crossover frequencies are 8.4 MHz (U301) and 13.5–14.8 MHz (the others).

Observations:

- **The isolation resistors are essential.** With 0 Ω, U301 driving 2.7 nF
  directly has 4–12° of phase margin, and U203 driving 500 pF directly has
  10–27°. The 100 Ω / 470 Ω / 1 k values in the design fix this.
- **The guard buffer is least stable when the guard is lightly loaded.** At HF,
  470 R in series with a small C_guard barely loads the pin. The op-amp then
  sees only its own RO driving the pin capacitance (IN− input C plus stray,
  20–30 pF): 200 Ω × 30 pF puts a pole at 27 MHz, close to the 12–15 MHz
  crossover. A larger guard capacitance damps this through the 470 Ω.
- **U201.** At HF, Cf shorts Rf, so the noise gain falls to ≈1 above
  1/(2π·Rg·Cf) = 10.6 kHz. The stage therefore behaves like a follower loaded by
  Rg (1 k) and 8.5 k. The added U202 input capacitance on IN− and the 20 pF
  CIN are what bring it down to 47°. It passes, but with little margin in the
  stacked corner.

## 3. Verdict and fix

| Stage | Requirement PM ≥ 45° over the whole sweep |
|---|---|
| U301 | PASS |
| U202 | **FAIL** (42.9° in the stacked worst corner with a 20 pF guard) |
| U203 | PASS |
| U201 | PASS (47.3° worst) |

**Proposed fix for U202.** Add a **220 pF C0G capacitor from GUARD to GND**,
beside the 470 Ω (R-GUARD). This gives a guaranteed minimum load of ≥ 240 pF.
In the worst corner the phase margin rises from 42.9° to 56.4°, and pin
overshoot falls from 26 % to 12.6 %.

The capacitor has no effect at ELF: 220 pF is 14 MΩ at 50 Hz, against the
buffer's < 1 Ω closed-loop output impedance. It also does not load the
electrometer input, because the guard is driven from IN−. Leakage from a
C0G part to GND is harmless on the driven guard node.

If the guard ring turns out to have ≥ 100 pF to the planes, it already
passes (53.5° worst), but that depends on the layout.

**Recommendation for U201.** The stage passes, but keep the IN− node small:
short traces to Rf, Cf, Rg and the U202 input. Its capacitance, together with
the op-amp output resistance, sets the worst-case margin. Do not add
capacitance to IN−.

## 4. Limitations

- The op-amp model has no slew limit, no output-stage crossover, no
  load-dependent RO and no internal zeros. The real LMP7715/LMP7721 open-loop
  output impedance is not specified in the datasheets, so the 50–200 Ω sweep
  is an assumption.
- The PCM1804 switched-capacitor input is not modelled. The 2.7 nF reservoir
  dominates it.
- The guard-to-input capacitance, which is positive feedback from GUARD onto
  IN_P, is not included. With C_gi ≪ 50 pF (Cf2) its loop gain stays below
  0.1, so it cannot oscillate.
