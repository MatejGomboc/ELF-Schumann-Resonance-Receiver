# ELARA electromagnetic studies

> **Update 2026-10-31 (applied from this study):** the plate capacitors' lower plates
> now return to PLATE_RET (BIAS_BUF via 100 kΩ, AC-grounded by 10 µF film + 100 nF
> C0G, J203) instead of GND, and the copper square is 49.9 mm. `results.json` and the
> plate-capacitor plot are from the re-run: **C = 50.2 pF** (fringing +6.8 %), divider
> −4.70 dB, RC corner 96 kHz; DC across each gap now only the air-earth current × J202
> (30 mV typical, 1 V at 100 pA), so **1 nm of gap motion gives 13 nV at IN_P (was
> 0.98 µV)** and the floor needs 2.1 nm/√Hz of gap motion (was 25 pm/√Hz). Text
> below that quotes 55.7 pF or 2.27 V across the gap describes the design before
> the change. Earthing is now a hard installation requirement (MOUNTING.md §6).

This folder checks how the outdoor unit couples to electric and magnetic fields,
both its own and its surroundings'. It covers:

- capacitive coupling into the guarded femtoampere input, from a 3-D field
  solve of the real board;
- shielding effectiveness of the aluminium shield, 1 Hz to 100 MHz;
- 50 Hz magnetic induction into the front-end loops and the AES3 cable;
- clock and AES3 emissions, aliasing and RF rectification, and the PSU box as a
  magnetic source;
- the air-gap plate capacitor: fringing and dC/dgap.

| File | Contents |
|------|----------|
| `run_em.py` | Runs every study; writes `results.json` and the five plots |
| `em_lib.py` | KiCad `.kicad_pcb` copper reader and the finite-difference Laplace solver |
| `em_guard_coupling.svg` | Field around the island (plan and cross-section), C from IN_P per net for three guard variants, injected levels against the floor, nearest approach of every net |
| `em_shielding.svg` | Shielding effectiveness against frequency (sheet, closed box, apertures), and 50 Hz E-field reaching IN_P against the field at the shield |
| `em_magnetic.svg` | 50 Hz EMF against B for each loop, and the PSU relays / IRM-05 / charger loops as sources |
| `em_digital.svg` | Alias table of every synchronous clock, and RF levels at IN+ with their rectified part |
| `em_plate_capacitor.svg` | C against gap (3-D solve against the formula), and the contributions at 0.5 mm |

Run it with `.venv/bin/python simulations/em/run_em.py`. It takes about 70–95 s.
It uses **pyamg** (pinned in `requirements.txt`). Without pyamg it falls back to Jacobi-preconditioned CG,
which gives the same answer but takes about ten times as long.

## 1. Method and assumptions

### 1.1 Field solver (`em_lib.py`)

- **Discretisation.** Finite-difference Laplace on a non-uniform tensor grid.
  The permittivity is defined per cell; at each grid edge it is weighted by the
  parts of the dual face that lie in each cell.
- **Conductors and boundaries.** Conductors are sets of grid nodes held at fixed
  potentials. Open domain faces are zero-flux (Neumann) boundaries.
- **Capacitance.** Holding IN_P at 1 V with every other conductor at 0 V, the
  charge on each conductor gives one row of the Maxwell capacitance matrix
  (discrete Gauss law).
- **Linear solver.** Ruge-Stüben AMG-preconditioned CG, about 9 iterations on 2.4 M
  nodes.
- **Validation.**
  - A layered parallel plate (air plus εr 4) matches the analytic value to
    1 × 10⁻⁹.
  - A bare 49.9 mm square at 0.5 mm gives 45.38 pF, against 46.21 pF from
    Palmer's formula for an isolated plate pair. The 1.8 % difference is expected:
    in the model, the grounded box at 30–40 mm takes some of the outer-face flux.
  - **Grid convergence.**
    - Plate capacitor (full model, 0.5 mm gap): 49.66 pF at a 0.125 mm grid,
      49.64 pF at 0.0625 mm.
    - Island self-capacitance: 3.57 pF at a 0.125 mm grid, 3.31 pF at
      0.1875 mm (−7 %).
    - Island couplings to the aggressors: within 3–13 % between the two grids.
      Treat the island figures as ±15 %.

### 1.2 Geometry of the guarded input (read from the board file)

- **Board copper.** The script parses every track, via, pad (with footprint
  rotation) and filled zone of `PCB/antenna_amplifier/antenna_amplifier.kicad_pcb`.
  The file's +50 mm page offset is removed.
- **Solve window.** Compartment 1, between the inner wall faces x = 7…41.5 mm
  (`mechanical/params.py`), with y = 27…64 mm. The island is at x 15.5–33,
  y 36.4–54.6.
- **Boundaries.**
  - The walls, the lid (52 mm above the board) and the tray floor (12 mm below)
    are separate grounded conductors.
  - The y ends of the window are Neumann.
  - The Ø3.45 mm feed-through hole in the tray floor (the Keystone 11157 PTFE terminal) is left open.
- **Extra conductors.**
  - The J202 header pins: 0.64 mm square, 8.5 mm tall.
  - The node-2 lead (Ø1 mm), from J201 down through the tray space.
- **Not modelled.** Component bodies (SOIC mould compound, header plastic), the
  J202 glass resistor body and solder mask. Mask matters little, because the
  island is unmasked.

| Item | Value | Source |
|---|---|---|
| Stack-up | F.Cu / 0.2104 mm 7628 prepreg / In1 / 1.065 mm core / In2 / 0.2104 mm prepreg / B.Cu; inner Cu 15.2 µm | JLCPCB JLC04161H-7628 (the board's fab, `tools/kicadgen/fabrules.py`) |
| εr | 4.4 prepreg, 4.6 core | JLCPCB impedance-calculator values (1 GHz; at ELF FR4 is ~4.7–5, so couplings are up to ~10 % low) |
| Grid | 0.125 mm in x 13.5–39.5, y 32.5–58.5; graded to 0.8 mm outside; 47 z planes | convergence above |
| Variants | **guard**: as built. **gnd**: guard copper removed, In1/In2 under the island filled with GND (a normal layout). **bare**: guard copper removed, nothing under the island | — |

### 1.3 Front-end transfer used for injection

An aggressor at voltage V coupled by C_c injects jωC_c·V into IN_P. This is
multiplied by the IN_P node impedance and referred to the antenna through the
EMF → IN_P gain. Both come from the 3-node network of `simulations/system`:

- C_ant = 140 pF, R1 = R3 = 33 kΩ, Cf1 = Cf2 = 50 pF, R_hb = 100 GΩ,
  R_leak = 1 TΩ;
- the non-bootstrapped board strays are added to Cf2.

At ELF, the antenna-referred injection simplifies to V·C_c/C_ant. The effective
node capacitance at SR1 is 240 pF.

| Quantity | Value | Source |
|---|---|---|
| Receiver floor at the antenna | 45.8 / 43.3 / 42.6 / 42.3 / 42.1 / 42.0 / 42.0 nV/√Hz at SR1–SR7 | `simulations/spice` (nominal, no R_hb) |
| Line comparisons | the floor in a 0.1 Hz bin (14.5 nV at SR1, 13.3 nV at 50 Hz) | `simulations/system` |
| 50 Hz clip level | 21.06 mV rms at the antenna | `simulations/system/results.json` |
| Mains pickup by the antenna | 1–5 mV rms | PLAN §3.1 |
| +5V_PRE noise | 100 nV/√Hz at 10 Hz, 1/f (ADM7150) | `simulations/psu` |
| +5V_PRE 50 Hz | 1 µV rms, an assumed bound (`simulations/psu` finds pV) | assumption |
| LMP7721 / LMP7715 e_n | 6.5 nV/√Hz with a 10 Hz corner / 5.8 nV/√Hz with a 30 Hz corner | `simulations/system` |
| LMP7721 input C | 10 pF | assumption, as in `simulations/spice` §4.3 |
| LMP7721 EMIRR | 30 dB at 6–100 MHz | **not specified**; a pessimistic assumption for an older CMOS part. Formula from TI SBOA128 |

### 1.4 Shield

| Item | Value | Source |
|---|---|---|
| Material | EN AW-6082 T6, σ = 25 MS/m (42–45 % IACS) | `mechanical/README.md` part list; typical handbook conductivity |
| Thickness | lid 2 mm, tray floor 2 mm, walls 7 mm | `mechanical/params.py` |
| Sheet SE | exact transmission-line (Schelkunoff) form: absorption, reflection and the multiple-reflection term. Electric- and magnetic-dipole wave impedances at 0.1 m and 1 m | Schelkunoff; Ott, *EMC Engineering*, ch. 6 |
| Closed box, magnetic | \|cosh kt + (ka/3) sinh kt\|, for a sphere of equal volume: a = 68 mm (whole shield) or 36 mm (C1). Assumes the eddy currents can circulate across the screwed seams | Kaden thin-shell result |
| Apertures, RF | 20 log(λ/2L) + 27.3 d/L. RJ45 notch: L = 20 mm, d = 7 mm. Lid seam: L = 41.5 mm (the largest screw pitch), no depth credit | Ott |
| Apertures, quasi-static | Bethe dipole: α_e ≈ (π/16)·L·w² for a slot, 2c³/3 for a round hole; image doubling; decay exp(−π d/w) along the depth (exp(−2.405 d/c) for a hole). Lid seam: gap 0.05 mm (machined faces, no gasket), 7 mm deep | Bethe / Collin |
| External 50 Hz E at the shield | 1 / 10 / 100 V/m (rural / domestic / unscreened 230 V conductor close by) | assumption (ICNIRP-type ranges) |

### 1.5 Magnetic

| Item | Value | Source |
|---|---|---|
| B at 50 Hz | 0.1–1 µT rms | assumed (typical near houses) |
| Board loop | 127 mm². Projected polygon J201 → IN_P → U201 pin 1, pin 8 → IN_N → R202 (Rg) → CG track (41 mm, followed through the board's segment graph) → C202 (Cg), closed by a straight return in the GND plane | board file |
| Lead loop | 6650 mm² (vector area). Node-2 post → 109 mm flying lead → PTFE bush → tray → 50 mm GND wire → GND post → base → C_B GND plate. Points from `mechanical/params.py` LAYOUT, PLATECAP_*, TERMINAL_POST and GND_POST; the amplifier is mounted lid-down | mechanics |
| AES3 cable | 100 m STP. Differential area: one uncancelled half twist (15 mm pitch × 1 mm). Common-mode area: 100 m × 1 m (cable on the ground, earth path to the rod) | assumption |
| Transformer interwinding C | 20 pF (S22083; Newava's drawing gives < 15 pF, so 20 pF is conservative) | assumption, checked |
| Floating receiver | V_g = V·C/(C + 358 pF) | `simulations/psu` §2.5 |
| PSU sources | K1–K4 and PS1 centres from `PCB/acdc_converter/acdc_converter.kicad_pcb`, placed with the PSU-box transform in `params.py`. 126 mm (IRM-05) and 164–182 mm (relays) from the input | board file + mechanics |
| Relay coil | 40 AT (about twice a 15–20 AT reed pull-in), Ø5 mm, ×2 for the reed blades: m = 1.6 × 10⁻³ A·m²; L/R ≈ 1 ms | assumption |
| IRM-05 input current | 0.2 A peak pulses in 5 cm² of wiring | assumption |
| Charger/load loops | 0.25 A in 3 cm², switched at each swap | assumption |

### 1.6 Plate capacitor

- **Geometry.** 49.9 mm copper square with four R4.8 corner reliefs, on 64 mm
  FR4 plates (εr 4.4, 1.6 mm) behind each copper face. Each copper face carries
  20 µm of solder mask (εr 3.5), the same values as
  `PCB/plate_capacitor/layout.py`. The gap is copper to copper (the washers sit
  on unmasked landing rings).
- **Model.** Quarter symmetry inside a grounded box at ±60 mm, z ±40 mm. Grid
  0.125 mm around the copper edge, graded outside.
- **Added analytically.** The Ø6 mm centre disc (0.55 pF as modelled, with the
  PTFE εr 2.1 of the old clamp; the alumina disc of the current clamp adds a
  little more).
- **Not modelled.** The solder tongues and the floating landing rings.

## 2. Results

### 2.1 Coupling into the guarded input (`em_guard_coupling.svg`)

Capacitance from IN_P (fF) from the 3-D solve:

| To | guard (as built) | gnd (no guard, GND planes) | bare (no guard, bare inner layers) |
|---|---:|---:|---:|
| GUARD (driven, bootstrapped) | **3207** | – | – |
| GND (board) | 100 | 3306 | 830 |
| TRAY (the feed-through pin in its 3.45 mm hole, and the lead) | 163 | 163 | 191 |
| WALL / LID | 57 / 1.7 | 57 / 1.8 | 85 / 2.5 |
| ANT_BIAS (J202 pins) | 78 | 79 | 197 |
| IN_N | 0.39 | 0.40 | 1.17 |
| PREAMP_OUT | 0.43 | 0.43 | 1.23 |
| +5V_PRE | 0.23 | 0.23 | 0.57 |
| GUARD_DRV / CG | 0.12 / 0.03 | 0.12 / 0.03 | 0.18 / 0.06 |
| **Load on IN_P that is not bootstrapped** | **0.40 pF** | 3.61 pF | 1.31 pF |
| Extra cap-divider loss | 0.014 dB | 0.13 dB | 0.05 dB |

**How close other nets come to IN_P copper** (edge to edge):

- ANT_BIAS 0.84 mm; GND 1.9 mm; PREAMP_OUT 3.2 mm; IN_N 4.3 mm; +5V_PRE 5.0 mm.
- The nearest digital net (MCLK_ADC, BCK, TXP) is **≥ 107 mm** away, behind two
  walls. No digital copper enters compartment 1.

**What the guard does.**

- **Bootstrapping.** It bootstraps 3.2 pF of the node's own capacitance and the
  surface leakage. This is its purpose, and it works: only 0.40 pF of the
  node's capacitance is not bootstrapped.
- **Aggressor screening.** Here a grounded plane would do exactly as well. The
  couplings to PREAMP_OUT, +5V_PRE and IN_N are the same with the guard as with
  GND planes under the island. Removing all inner copper ("bare") raises them
  three- to five-fold.

**Injected signal, as built** (referred to the antenna):

| Aggressor | Level at the aggressor | Injected | Margin below the floor |
|---|---|---:|---:|
| GUARD (LMP7721 + U202 e_n, which the guard carries) | 16 nV/√Hz at SR1 | 0.37 nV/√Hz | **42 dB** |
| ANT_BIAS (U203 e_n, bypassing J202 through the pin capacitance) | 13 nV/√Hz | 7 pV/√Hz | 76 dB |
| +5V_PRE, 50 Hz line | 1 µV rms (bound) | 1.8 pV | 77 dB (0.1 Hz bin) |
| +5V_PRE, ADM7150 noise | 113 nV/√Hz at SR1 | 0.2 pV/√Hz | 107 dB |
| PREAMP_OUT, in-band positive feedback | — | gain error 1.6 × 10⁻⁴ (0.001 dB) | — |
| PREAMP_OUT at RF (preamp at unity gain) | — | loop gain 6 × 10⁻⁶ (C_c / 63.6 pF) | no oscillation risk |

- **J202 header pins.** They add 78 fF across the bias resistor. With 100 GΩ the
  corner 1/(2π R C) is 20 Hz, so above 20 Hz J202 is capacitive rather than
  resistive. This is harmless: ANT_BIAS is an AC ground (4700 µF), the 78 fF is
  0.03 % of the 240 pF node, and the resistor's noise current is unchanged.
- **Digital lines.** At ≥ 107 mm, behind two GND walls and with In1 as a solid
  plane, the direct capacitance is zero in the model by construction. It is at
  most attofarads physically. The digital path is conducted (section 2.4).

### 2.2 Shielding effectiveness (`em_shielding.svg`)

SE in dB:

| Frequency | E-source 0.1 m, 2 mm | H-source 0.1 m, 2 mm | H-source 0.1 m, 7 mm wall | H, closed box (a = 68 mm) | RJ45 notch | lid seam |
|---|---:|---:|---:|---:|---:|---:|
| 1 Hz | 313 | 0.1 | 0.3 | 0.0 | 207 | 191 |
| 8 Hz | 295 | 0.2 | 1.5 | 0.0 | 189 | 173 |
| **50 Hz** | **279** | **3.1** | 11.5 | **0.8** | 173 | 157 |
| 1 kHz | 253 | 26 | 40 | 19 | 147 | 131 |
| 100 kHz | 243 | 96 | 232 | 89 | 107 | 91 |
| 24.576 MHz | > 900 | > 900 | > 900 | > 900 | **59** | **43** |
| 100 MHz | > 1800 | > 1800 | > 1800 | > 1800 | 47 | **31** |

At 50 Hz the skin depth is 14.2 mm, so the 2 mm lid absorbs only 1.2 dB.

**The key insight is confirmed.**

- **H-field at ELF.** The shield is transparent: < 1 dB as a closed box at
  50 Hz, 0 dB below 10 Hz. Eddy-current shielding of 2 mm aluminium starts only
  above about 100 Hz (box corner f = 1/(2π μ0 σ t a/3)).
- **E-field.** At every frequency the walls themselves give > 240 dB. The
  shield is limited only by apertures, and those are seams above about 10 MHz.

**50 Hz E-field reaching IN_P, per V/m at the shield** (the result scales
linearly with the field):

| Path | V at IN_P per V/m |
|---|---:|
| Lid seam (0.05 mm × 41.5 mm, 7 mm deep) | ~10⁻²⁰⁴ V (zero) |
| RJ45 notch (in C3, no credit for the two internal walls) | 5.6 pV |
| PTFE feed-through (Ø3.45 hole under C1, uses C(IN_P, tray) = 163 fF) | 0.31 nV |
| **IN_P / node-1 metal outside the shield** (109 mm lead plus two node plates, ≈ 5 pF exposed, at about 30 mm from grounded metal) | **≈ 0.6 mV** |

- **Through the shield.** At an extreme 100 V/m the shield passes at most
  0.33 µV. That is 99 dB below the 29.5 mV clip level: **PASS**.
- **Outside the shield.** The real local 50 Hz path is the input metal outside
  the shield: the lead and the plate capacitors. It is outside by design, as part
  of the antenna. At the 0.3–1.3 mV/m site field implied by 1–5 mV of antenna
  pickup it adds only ≈ 0.2–0.8 µV. Near an unscreened 230 V conductor (10–100 V/m)
  it would give 6–60 mV, which is at or above the clip level.

### 2.3 Magnetic coupling (`em_magnetic.svg`)

| Loop | Area | EMF at 0.1 µT | EMF at 1 µT |
|---|---:|---:|---:|
| Board input loop | 127 mm² | 4 nV | 40 nV |
| Node-2 lead + GND wire | 6650 mm² | 0.21 µV | **2.1 µV** |
| Same, untidy wiring (×3) | 20 000 mm² | 0.63 µV | 6.3 µV |
| AES3 pair, differential (into the AES3 receiver) | 7.5 mm² | 0.2 nV | 2.4 nV |
| AES3 cable vs earth, common mode (at the outdoor transformer) | 100 m² | 3.1 mV | 31 mV |

**Front-end loops.** The worst front-end EMF, 6.3 µV, is 70 dB below the clip
level and 44–58 dB below the 1–5 mV E-field mains pickup. It is a 50 Hz line,
removed by the notch with the rest of the mains. **PASS.**

**AES3 common mode reaching the receiver GND:**

| Path | Source | Earthed receiver (100 Ω) | Floating receiver |
|---|---|---:|---:|
| Transformer interwinding, 20 pF | induced CM at 1 µT | 20 nV | 1.7 mV |
| Transformer interwinding, 20 pF | PE-to-local-earth 3 V | 1.9 µV | **0.16 V** |
| Optional 10 nF shell bond (C406, DNP) | induced CM at 1 µT | 9.9 µV | 30 mV |
| Optional 10 nF shell bond (C406, DNP) | PE-to-local-earth 3 V | **0.94 mV** | **2.9 V** |

- **Earth potential difference dominates.** Ground-potential differences between
  the indoor PE and the outdoor earth are orders of magnitude larger than the
  magnetically induced CM. The earthed-receiver numbers are fine.
- **A floating receiver is not viable.** It fails on the AES3 transformer alone
  (0.16 V > 29.5 mV), in addition to the PSU paths in `simulations/psu`.
- **C406 must stay DNP.** Fitting the 10 nF RF bond raises the earthed case to
  0.9 mV, which then becomes the largest 50 Hz injection after the antenna.

**PSU box as a magnetic source** (at its real distance, into the lead loop):

| Source | Distance | Field at the input | Effect |
|---|---:|---:|---|
| Relays K1–K4, per swap edge | 164–182 mm | ΔB = 0.12 µT | flux 0.8 nV·s per edge → spike ≈ 0.8 µV peak for about 1 ms. Each 1/30.4 s spectral line is 54 pV rms, **108 dB below** the 0.1 Hz-bin floor (14.5 nV) |
| Charger/load loop step | — | 2.9 nT | lines of 1.3 pV |
| IRM-05 50 Hz input current | 126 mm | 7 nT | 15 nV at 50 Hz (negligible against mains pickup) |

The relay spike energy (0.8 nV·s) is about 47 dB below one 15 s record of
receiver noise. Because the spikes are periodic, they can be blanked or
averaged out if they are ever seen. **PASS.**

### 2.4 Clock and digital emissions (`em_digital.svg`)

**Synchronous clocks.**

- **One master clock.** Every clock on the board comes from the one 24.576 MHz
  oscillator: MCLK = 128 fs, BCK = 64 fs, LRCK = fs, PCM1804 modulator 32 fs,
  AES3 cell rate 128 fs, subframe 2 fs.
- **Where the harmonics land.** All harmonics up to 1 GHz alias exactly to
  **DC** after sampling at 192 kHz. The AES3 block rate (192 frames → 1 kHz) and
  its harmonics land at multiples of 1 kHz.
- **Result.** **No synchronous product can fall in 1–50 Hz.** This is
  arithmetic, not attenuation (about 1 million harmonics checked).

**Asynchronous sources.** A tone must lie within 50 Hz of k·192 kHz to alias
into band.

- **Analog attenuation first.** The preamp, AA filter and 100 Ω/2.7 nF already
  give 102 / 109 / 152 dB at 192 kHz / 384 kHz / 6.144 MHz, before the PCM1804
  decimation filter.
- **Candidates.** The only free-running sources are the IRM-05 converter, which
  is galvanically disconnected from the load by the two-bucket scheme, the
  CD4060 swap timer, and broadcast transmitters.

**RF rectification at the LMP7721 input** (EMIRR 30 dB assumed):

| Source | RF at IN+ | Rectified shift |
|---|---:|---:|
| MCLK loop (55 mm of track, 11.6 mm²), through the RJ45-aperture SE of 59 dB, into the lead loop | 3.5 nV | 4 × 10⁻¹⁸ V |
| AES3 cable field 100 µV/m at 6.1 MHz, picked up by the antenna, after the RC filter | 0.23 µV | 2 × 10⁻¹⁴ V |
| FM 1 V/m (PLAN §3.0) | 8.6 µV | 2 × 10⁻¹¹ V |
| Bound: 1 mV of MCLK on the C1 GND | 1.4 mV | 0.63 µV |

- **Constant envelope means DC.** A clock with a constant envelope rectifies to
  **DC**, which C_out and the analogue HPF remove. Only envelope modulation
  inside 1–50 Hz would land in band.
- **AES3 envelope.** The AES3 stream's envelope changes with the audio data,
  but its rectified level is 10⁻¹⁴ V.
- **Two-tone beat.** A beat between two independent RF lines within 50 Hz of
  each other (for example FM and AES3) is V1·V2/100 mV × 10^(−EMIRR/20) =
  6 × 10⁻¹³ V. **PASS.**

### 2.5 Air-gap plate capacitor (`em_plate_capacitor.svg`)

| At 0.5 mm, 49.9 mm copper | C (pF) |
|---|---:|
| Parallel plate, air (49.9² − 4 reliefs = 2477 mm²) | 43.86 |
| Parallel plate, with 2 × 20 µm mask (the `layout.py` formula) | 46.52 |
| 3-D, bare square, no reliefs, FR4 or mask (validation) | 45.38 |
| 3-D, no mask | 46.89 |
| 3-D, no FR4 | 47.90 |
| **3-D, full (FR4 backing, mask, reliefs)** | **49.66** |
| **+ centre disc** | **50.22** |

- **Fringing.** It adds **6.8 %** over the mask-corrected parallel-plate formula.
  About half of that comes from the FR4 behind the copper, which concentrates the
  edge field.
- **Effect on the design.** The copper square was shrunk from 53.1 mm (55.7 pF)
  to 49.9 mm, so the capacitor is now **50.2 pF**: the cap divider is −4.70 dB
  against −4.68 dB designed, and the RC corner 96.0 kHz.
- **dC/dgap = −0.103 pF/µm** at 0.5 mm. That is 5 % steeper than the
  parallel-plate −C/d_eff (−0.099 pF/µm).
- **C to the surroundings.** The node plate has 1.9 pF to the surroundings
  inside the model box (this depends on the installation).

**Microphonics** (for the mechanical study). Each air capacitor carries the
IN_P DC bias across its gap: 2.27 V with J202 = 100 GΩ. A gap change Δg
therefore injects a charge V_dc·(dC/dg)·Δg into the 240 pF node.

| Sensitivity | Value |
|---|---:|
| At IN_P | 1.09 µV per nm of gap change |
| At the antenna | 1.86 µV per nm |
| Gap motion equal to the SR1 floor | **25 pm/√Hz** (per capacitor; Cf1 and Cf2 add) |

This is a demanding mechanical requirement; see recommendation 1.

## 3. Verdict

| Check | Requirement | Result |
|---|---|---|
| E1 Board aggressors into IN_P | every injection ≥ 20 dB below the floor | **PASS**: the worst is the guard carrying the amplifiers' own e_n, 42 dB below. Supplies are 77–107 dB below. Digital nets are ≥ 107 mm away, behind two walls |
| E2 Guard effectiveness | non-bootstrapped node C ≪ C_filt | **PASS**: 0.40 pF against 3.61 pF without the guard; −0.014 dB |
| E3 Stability via board coupling | out → in coupling ≪ 1 | **PASS**: 6 × 10⁻⁶ at RF, 1.6 × 10⁻⁴ in band |
| E4 Shield, 50 Hz E-field through the shield | ≪ 29.5 mV clip | **PASS**: ≤ 0.33 µV even at 100 V/m |
| E5 Shield, ELF H-field | (informational) | ~0 dB at 1–50 Hz, as expected. **The receiver relies on loop-area control, not on the shield** |
| E6 50 Hz magnetic into the front end | ≪ mains pickup | **PASS**: ≤ 6.3 µV at 1 µT, 44 dB below 1 mV |
| E7 AES3 cable, 50 Hz | ≪ 29.5 mV clip | **PASS when earthed** (≤ 2 µV). **FAIL when floating** (0.16 V). **Marginal with C406 fitted** (0.9 mV earthed) |
| E8 Clock and AES3 into 1–50 Hz | no in-band product | **PASS**: everything aliases to DC or 1 kHz multiples; rectified RF ≤ 10⁻¹¹ V |
| E9 PSU swap and relays, magnetic | below the floor in a 0.1 Hz bin | **PASS**: 108 dB below |
| E10 Plate capacitor value | 50 pF nominal | **PASS**: 50.2 pF with 49.9 mm copper (was 55.7 pF with 53.1 mm) |
| E11 Plate capacitor microphonics | gap noise below the floor | **OPEN / RISK**: 1.1 µV/nm at IN_P. The gap must be stable to < 25 pm/√Hz in 1–50 Hz |

### Risks: real or negligible

- **Real.**
  - **Plate-capacitor microphonics** (E11).
  - **Receiver earthing** (E7). The AES3 transformer path alone puts 0.16 V on a
    floating receiver, independently of the PSU.
  - **Unscreened mains near the plate capacitors or flying lead** inside the
    plastic box. Exposed node metal gives ~6 mV per 10 V/m.
- **Negligible.**
  - Digital and clock coupling, aliasing and rectification.
  - Shield seams and apertures at ELF.
  - Supply-borne injection through board capacitance.
  - 50 Hz magnetic fields in the front-end loops.
  - PSU relay and IRM-05 fields.
  - The AES3 differential pickup.

### Recommended design changes

Items 1 (PLATE_RET), 2 (49.9 mm copper), 3, 4 (the plate-return wire runs beside
the node-2 lead) and 6 have since been applied (see the update at the top).


1. **Microphonics of the air-gap capacitors.** Either:
   - remove the DC across the gaps by returning the "GND" plates of Cf1/Cf2 to
     the buffered antenna bias (2.5 V, AC-grounded by 4700 µF) instead of GND.
     This makes the injection second order in V_dc. It adds the bias buffer's
     ≈ 6 nV/√Hz through Cf2/C_node, about −20 dB on the floor, so check it in
     `simulations/system`;
   - or set a mechanical gap-stability target of < 5–10 pm/√Hz (1–50 Hz) for the
     separate microphonics study.
2. **Plate capacitor value.** Shrink the copper square to about 50.3 mm (or
   widen the gap to about 0.56 mm) if exactly 50 pF is wanted. Otherwise update
   PLAN §3.0 and CLAUDE.md to about 56 pF per capacitor (C_filt ≈ 111 pF,
   −5.1 dB, fc ≈ 87 kHz). The parallel-plate figures in `layout.py` and
   `params.py` undercount by 6–11 %.
3. **Keep C406 (AES3 shell RF bond) DNP**, and make outdoor earthing a hard
   installation requirement in MOUNTING.md. That agrees with `simulations/psu`.
4. **Dress the node-2 flying lead along the plate-capacitor GND wire** (or run
   the GND wire right beside it to the bush). This shrinks the 6650 mm² loop.
   It is not needed for 50 Hz, but it costs nothing and helps against local
   impulsive H-fields.
5. **Keep every 230 V conductor in the outdoor box screened and away from the
   plate-capacitor assembly.** That assembly is the one part of the input that
   no metal protects.
6. Add `pyamg` to `requirements.txt` (done: pinned).

## 4. Limitations

- **Electrostatic only.** The board solve is electrostatic. That is exact at ELF;
  at RF it gives the capacitive part only, and inductive board coupling at
  24.576 MHz is estimated with dipole formulas.
- **Island model gaps.**
  - Component bodies and the J202 glass resistor are omitted, and εr is the
    1 GHz value.
  - The island couplings carry about ±15 % grid and model uncertainty. None of
    the margins is close enough for that to matter.
- **Shield idealisations.**
  - The closed-box magnetic SE assumes the eddy currents cross the screwed seams.
    Real seams make the ELF SE even closer to 0 dB.
  - The aperture formulas are order-of-magnitude for a single aperture.
- **Assumed values.** Several inputs are assumptions rather than datasheet
  values:
  - LMP7721 EMIRR;
  - relay ampere-turns;
  - IRM-05 wiring loop;
  - local 50 Hz E-field;
  - AES3 cable common-mode loop area.

  Each sits in the constants at the top of `run_em.py`.
- **Plate capacitor model.** It includes the FR4 plates but not the POM base,
  the PTFE standoffs, the second capacitor 16 mm away, or the tongues. The
  environment C (1.9 pF) depends on the installation.
