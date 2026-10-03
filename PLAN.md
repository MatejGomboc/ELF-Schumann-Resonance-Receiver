# ELARA — ELF Atmospheric Radio Analyser

## Project Vision & Plan

**Goal:** Design and build a professional-grade electric-field receiver for natural ELF
radio signals (1–50 Hz), optimised for Schumann resonance monitoring with exceptional
sensitivity and signal fidelity. The design targets noise performance significantly
beyond existing hobby receivers (e.g., Renato Romero's LNVA_24-20).

**Design philosophy:**
- Engineer every stage for maximum sensitivity and fidelity
- Human-in-the-loop review at every design step
- AI-augmented design using Claude Code for KiCad, SPICE, CadQuery, firmware, and software
- Fully open-source toolchain (KiCad, ngspice, CadQuery, FreeCAD, Python, GCC/ARM)
- Licence: CERN Open Hardware Licence v2 — Weakly Reciprocal (CERN-OHL-W-2.0)

**Inspiration:** Renato Romero's electric-field receiver at vlf.it — same antenna approach,
but with modern electrometer-grade components and professional PCB/mechanical design
to achieve dramatically better noise performance.

---

## 0. Revision 0.2 — changes from the initial plan

Revision 0.2 (branch `claude/cloud-work`) turns this plan into generated, checked
KiCad designs. Where the sections below and this list disagree, **this list wins**.

- **Schematics are generated** from `PCB/antenna_amplifier/design.py` and
  `PCB/acdc_converter/design.py` (KiCad 9 writer in `tools/kicadgen/`); every run
  checks KiCad's own netlist export against the intended nets. Edit the scripts,
  not the sheets.
- **Cg returns to GND, not to the 2.5 V bias buffer.** A buffer reference in the
  gain network would add its own noise with the full ×101 gain (SPICE: +0.9 dB at
  SR1). With a film Cg the DC across it is harmless.
- **Guard buffer senses IN−, not IN+.** In a non-inverting stage IN− follows IN+
  (virtual short), and sensing IN− keeps the LMP7715's bias current off the
  femtoampere node.
- **Antenna bias — the floating input cannot hold a DC point.** An elevated
  antenna in the fair-weather field collects an air–earth conduction current of
  order 10–160 pA (I ≈ σ·Q/ε₀); with no DC path the input reaches a rail in
  seconds. The bias link J202 is therefore a **1–100 GΩ glass-resistor position**
  (shunt = start-up reset only). See `simulations/spice/README.md` for the
  noise-versus-offset trade-off; an insulated antenna element or an HV coupling
  capacitor plus 100 GΩ–1 TΩ bias is the best long-term option.
- **ADC driver added:** unity-gain LMP7715 after the anti-alias RC, then
  100 Ω + 2.7 nF C0G charge reservoir at VINL+ (ADI/TI delta-sigma driving
  practice), so the PCM1804's switched-capacitor input no longer sets the gain.
- **Every PCM1804 and CS8406 mode pin is on a DIP switch** (defaults for 192 kHz
  on the sheets): the PCM1804's FMT/S-M/OSR pins use its internal 51 kΩ
  pull-downs, BYPAS and the CS8406 pins 47 kΩ ones (about 3 mA less on +3V3 than
  10 kΩ pull-downs); CS8406 in hardware mode (H/S high); shared RC + push-button
  reset.
- **No LEDs on the amplifier** (it may run from a battery): the rails and the ADC
  overflow flag are checked at test points with a voltmeter (TP301 = OVFL). The
  only LED is the "mains present" LED on the charger side of the PSU.
- **Two-bucket PSU implemented** (§3.8): IRM-05-15 → CC 0.2 A / CV 10.4 V
  charger → two 4 × 10 F supercap buckets swapped every ~15 s by form-C relays
  (break before make) → LT3045 6.98 V → common-mode choke. A 9–15 V battery
  replaces it.
- **Noise budget revised by SPICE** (`simulations/spice/`): 26.7 nV/√Hz at the
  amplifier input and **45.8 nV/√Hz referred to the antenna at SR1** (the Python
  budget of 37.7 / 64.6 nV/√Hz treated every source as if it saw the full
  capacitive divider, which is pessimistic by ~3 dB).
- **Boards:** amplifier 200 × 100 mm, 4 layers, three compartments on 7 mm
  exposed GND wall strips with 24 M3 holes; PSU 150 × 90 mm, 2 layers; plate
  capacitor 64 × 64 mm (48.9 pF bare / 51.9 pF masked at 0.5 mm).
- **Mechanics** (`mechanical/`): 7 mm flat-bar shield frame, milled tray, lids,
  PSU box, POM/PTFE plate-capacitor base, Fibox ARCA 403015 outer box.
  Do not anodise the shield (contact faces must conduct).
- **One digital output: AES3 on a shielded RJ45** (Amphenol RJHSE-5380) for a
  shielded twisted-pair (Cat5e/6) cable: AES3 on the blue pair (pins 4/5, the
  same in T568A and T568B), transformer isolated (S22083, 2 kV); the jack's shell
  is the cable shield, isolated from GND (10 nF RF bond position, DNP) and kept
  clear of the shield wall. The S/PDIF coax output is gone. The spare pairs are
  reserved for isolated control signals in a later revision.
- **Fit audit (real boards in their enclosures, `mechanical/fit_check.py`):**
  each air-gap plate carries its solder joints on **two tongues outside the
  overlap**; the PSU has cable bays in front of the mains terminal and the
  output header, glands in line with them, the PE stud through the mains-end
  wall, nylon standoffs on the receiver side and tab-down LM317s (no heatsinks).
  The PSU's charger and receiver copper keep at least 1 mm apart.
- **Fab rules and layout polish:** JLCPCB's standard limits are KiCad DRC rules on
  every board (`tools/kicadgen/fabrules.py`); parts sit in functional blocks in
  aligned rows and columns, and every reference label follows its part's row.

---

## 1. System Architecture (Simplified)

The system has been deliberately simplified to minimise custom hardware. The only custom
PCB is the outdoor antenna unit. The indoor side is entirely off-the-shelf.

```
    OUTDOOR UNIT (one custom PCB + two air-gap plate capacitors)
    ┌─────────────────────────────────────────────┐
    │  Marconi T-Antenna (~10m vert, ~15m top)    │
    │  ↓                                          │
    │  Input RF filter (2-stage RC low-pass)      │
    │  (air-gap plate capacitors — see §3.0)      │
    │  ↓                                          │
    │  LMP7721 electrometer buffer                │
    │  (+ LMP7715 guard ring driver)              │
    │  ↓                                          │
    │  Anti-aliasing LPF                          │
    │  ↓                                          │
    │  PCM1804 (24-bit ADC, 192 kSPS)             │
    │  ↓                                          │
    │  CS8406 (AES3 transmitter)                  │
    │  ↓                                          │
    │  Audio transformer (galvanic isolation)     │
    │  ↓                                          │
    │  Power: 6.98 V DC → ADM7150 LDOs (5V+3.3V)  │
    └──────────────┬──────────────────────────────┘
                   │
                   │  Two shielded cables:
                   │  • AES3 digital audio: Cat5e/6 STP, RJ45
                   │  • 230V AC mains power (screened 3-core)
                   │  (both containment-shielded — see §5)
                   │
    ┌──────────────┴──────────────────────────────┐
    │  INDOOR UNIT (off-the-shelf)                │
    │                                              │
    │  USB audio interface, AES3 or S/PDIF input   │
    │  → PC                                        │
    │  → Software: adaptive filtering,             │
    │    spectrograms, data logging                │
    └─────────────────────────────────────────────┘
```

**Key simplification:** By digitising at the antenna and transmitting AES3, the entire
indoor unit is eliminated. No custom indoor PCB, no STM32, no PGA, no dual-ADC
architecture. The indoor side is just a commercial USB audio interface with an AES3
input (RJ45-to-XLR adapter) or an S/PDIF input (through a 110 Ω to 75 Ω balun).

---

## 2. Antenna

- **Type:** Marconi T-antenna (vertical electric field probe)
- **Dimensions:** ~10 m vertical element, ~15 m capacitive top (inverted-L or T shape)
- **Estimated capacitance:** ~140 pF (calculated for 10 m vertical + 15 m top hat;
  50–150 pF depending on geometry and environment)
- **Electrical model:** Almost ideal capacitor at ELF/VLF frequencies
  - At 7.83 Hz: |Z_source| ≈ 145 MΩ (purely capacitive)
  - Radiation resistance: negligible (antenna is ~0.0000003 wavelengths at SR1)
  - Conductor/ground losses: negligible compared to capacitive reactance
- **Rationale:** Electric-field reception avoids the sensitivity-vs-frequency penalty of
  magnetic loops at ELF. Capacitive source requires electrometer-grade preamp, but
  modern silicon (LMP7721) makes this approach superior.

---

## 3. Outdoor Unit — Electronics

### 3.0 Input RF Rejection Filter (Air-Gap Plate Capacitors)

**Problem:** FM broadcast stations (88–108 MHz) are strong enough to drive the LMP7721
into nonlinear operation. The op-amp rectifies/demodulates the FM carrier, producing
spurious signals in the ELF/VLF band. This must be suppressed before the amplifier input.

**Solution:** A 2-stage cascaded RC low-pass filter using air-gap plate capacitors.

```
                   (suspended in air, inside plastic enclosure, OUTSIDE ALU shield)

                          Air cap 1              Air cap 2
                          ~54mm plates            ~54mm plates
                          0.5mm air gap           0.5mm air gap
antenna ──── 33kΩ ──── node1 ──── 33kΩ ──── node2 ──── wire ──→ LMP7721 IN+
                          |                    |                  (inside ALU
                      ┌───┴───┐            ┌───┴───┐               shield)
                      │  Cu   │            │  Cu   │
                      │  AIR  │ ~50pF      │  AIR  │ ~50pF
                      │  Cu   │            │  Cu   │
                      └───┬───┘            └───┬───┘
                          |                    |
                         GND                  GND
```

**Cutoff frequency:** fc = 1/(2π × 33 kΩ × 50 pF) ≈ **96.5 kHz** per stage
(2-stage cascade -3 dB point ≈ 62 kHz)

**Signal loss from capacitive voltage divider:** The filter capacitors
(2 × 50 pF = 100 pF total) form a voltage divider with the antenna capacitance
(140 pF). At ELF: H = C_ant / (C_ant + 2×C_filt) = 140/(140+100) = 0.583
→ **-4.7 dB** (~1/2 signal division).

**Why R=33 kΩ:** Optimised for noise vs AM rejection tradeoff.
The filter resistors dominate the noise budget (74 % of the noise power at SR1:
48 % from the one next to the amplifier, 26 % from the one at the antenna; SPICE).
R=33k gives 23.4 nV/√Hz per resistor (vs 60.4 with old 220k = **2.6× less noise**).
Effective noise at antenna: 45.8 nV/√Hz (SPICE; the first Python budget said 64.6),
**2.6× better than Romero's AD820 (7× in power)**.
AM rejection: -41 dB (adequate for nearby AM tower at 15 km).
FM rejection: -121 dB (FM utterly annihilated).

The flat **-4.7 dB cap-divider loss** (above) applies across the whole band;
the values below are the additional 2-stage RC filter attenuation:

| Frequency        | RC filter attenuation   | Effect                          |
|------------------|-------------------------|---------------------------------|
| 7.83 Hz (SR1)    | ~0 dB                   | Flat passband                   |
| 14.3 Hz (SR2)    | ~0 dB                   | Flat passband                   |
| 20.8 Hz (SR3)    | ~0 dB                   | Flat passband                   |
| 1 kHz (VLF)      | ~0 dB                   | Flat passband                   |
| 10 kHz (VLF)     | -0.09 dB                | Negligible rolloff              |
| 22 kHz (VLF top) | -0.44 dB                | Negligible rolloff              |
| 1 MHz (AM)       | -41 dB                  | Adequate for 15 km AM tower     |
| 100 MHz (FM)     | -121 dB                 | FM utterly annihilated          |
| 900 MHz (GSM)    | -159 dB                 | GSM utterly annihilated         |

**Why R=33 kΩ instead of 220 kΩ:** The filter cutoff (96.5 kHz) is well below
AM broadcast (1 MHz, -41 dB rejection) and far below FM (100 MHz, -121 dB).
There is no need for a low cutoff in the RF filter — the ELF band shaping
is done by the preamp feedback (106 Hz rolloff) and AA filter (159 Hz).
The tradeoff analysis in `simulations/input_filter/filter_resistor_tradeoff.py`
shows R=33k is a good choice: adequate AM rejection (-41 dB for nearby 15 km tower)
with dramatically lower noise (2.3× better than old 220k design).

**Note on the RF filter rolloff:** above 10 kHz the 2-pole RC response is fixed
and stable, so a digital IIR filter could equalise it. In rev 0.2 it does not
matter: the preamp's R201/C201 feedback rolls the gain off above 106 Hz, and the
VLF band is not used (§3.1).

**Plate dimensions for 50 pF** (C = ε₀ × A / d, air dielectric εr ≈ 1.0,
0.5 mm copper pullback from each edge):

| Air gap   | Plate side | Copper side |
|-----------|------------|-------------|
| 0.2 mm    | 34.6 mm    | 33.6 mm     |
| 0.5 mm    | 54.1 mm    | 53.1 mm     |
| 1.0 mm    | 76.1 mm    | 75.1 mm     |

Plate size is flexible — choose based on enclosure constraints. Larger plates
with wider gaps are easier to manufacture mechanically.

See `simulations/plate_capacitor/plate_capacitor_geometry.py` for full sweep.
See `simulations/input_filter/rc_filter_cascade.py` for Bode plot.
See `simulations/input_filter/filter_resistor_tradeoff.py` for R optimisation.
See `simulations/antenna/antenna_capacitance.py` for signal loss model.

**Why air-gap capacitors instead of PCB-substrate capacitors:**
- Air dielectric has R_dc > 10^16 Ω — preserves the LMP7721's femtoampere
  current noise advantage (PCB substrates like FR4 have R_dc ~40 MΩ which
  generates 2000× more current noise than the LMP7721)
- Zero dielectric loss (tan δ = 0) — no ESR, no thermal noise from capacitor
- No moisture absorption — capacitance is perfectly stable
- No commercial capacitor package → no package leakage current paths
- Construction: two solder-masked PCBs facing each other with precision
  spacers (ceramic or PTFE), air as dielectric. Dirt cheap from JLCPCB.

**Legacy comparison (PCB-substrate capacitors — rejected):**

- **FR4** (R_dc ~40 MΩ, tan δ = 0.02): substrate leakage generates 2000× more
  current noise than LMP7721 at Schumann frequencies. Unusable for this design.
- **Rogers 4350B** (R_dc ~389 MΩ, tan δ = 0.0037): 650× worse than LMP7721.
- **Alumina 96%** (R_dc ~8.3 TΩ, tan δ = 0.0002): comparable to LMP7721 but
  expensive and unnecessary when air gap is superior and cheaper.

**Why TWO SEPARATE PCB pieces (not one shared piece):**
- If both caps shared one PCB, surface and volume leakage through the common
  FR4 substrate would create a parasitic resistance between node1 and node2
- This would bypass the second 33 kΩ resistor, degrading both filter performance
  and input impedance
- Physically separate pieces with an air gap between them ensure the only path
  between nodes is through the 33 kΩ resistor
- Air is a near-perfect insulator: no surface leakage, no moisture absorption

**Physical mounting:**
- Both plate capacitors are suspended in air inside the plastic outer enclosure
- NOT mounted on the main PCB — air-wired connections only
- Located outside the ALU EM shield (no shielding needed — this stage is at
  antenna potential, same signal level as the environment)
- The 33 kΩ resistors are also air-mounted (not on the main PCB)

**Antenna bias (J202):**
- The LMP7715 antenna bias buffer reaches the LMP7721 input only through J202 and
  a 1 kΩ isolation resistor
- In operation J202 carries a 1–100 GΩ resistor (soldered across its pins): the
  air–earth current would otherwise drive the floating input to a rail in
  seconds (§0, §3.7)
- **Start-up:** a shunt over the J202 pin tips resets the input to the 2.5 V bias;
  remove it once TP202 has settled. MOUNTING.md section 7 has the procedure.

### 3.1 Electrometer Amplifier (Input Stage)

- **IC:** Texas Instruments LMP7721
  - Input current noise: ~0.01 fA/√Hz (lowest on market)
  - Input voltage noise: 6.5 nV/√Hz at 1 kHz
  - Input bias current: ±20 fA max at 25°C
  - GBW: 17 MHz
  - Supply: 1.8 V to 5.5 V
  - 8-pin SOIC with isolation-optimised pinout (pins 2, 7 for external guard)
- **Configuration:** Non-inverting amplifier with 40 dB ELF gain, rolling off above 106 Hz
  - Rf = 100 kΩ (feedback resistor, IN− to VOUT)
  - Cf = 15 nF C0G (feedback capacitor, across Rf — rolls off gain above ~106 Hz)
  - Rg = 1 kΩ (ground-reference resistor, IN− to Cg)
  - Cg = 100 µF film (DC blocking cap, in series with Rg, returned to GND — rev 0.2;
    WIMA MKS4 63 V, PCM 37.5 mm; the AC voltage across it is < 1 mV)
  - C_out = 10 µF film (output coupling cap, blocks 2.5V DC to ADC)
  - Gain: G(f) = 1 + Rf / (Rg × (1 + jωRfCf)) × jωCg / (jωCg + 1/Rg)
  - At DC: G = 1 (0 dB) — Cg blocks DC, no DC offset amplification
  - At ELF (1.6–106 Hz): G = 1 + 100k/1k = **101 (40.1 dB)** — flat across Schumann band
  - Corner frequency: fc = 1/(2π × 100k × 15nF) = **106 Hz**
  - Above 106 Hz: gain rolls off −20 dB/dec toward unity
  - **Design decision:** VLF band dropped in favour of ELF quality. The 40 dB gain
    maximises signal fidelity while keeping 50 Hz power line hum within the linear
    range (21 mV rms at the antenna before clipping, set by U301's input
    common-mode range; `simulations/system`). The 50 Hz is removed cleanly by a
    digital notch filter in software.
  - **Max amplification is dictated by 50 Hz mains E-field pickup.** The 1–100 GΩ
    input resistance (J202) is far above the antenna's 23 MΩ at 50 Hz, and with a
    6.5 m effective antenna height the 50 Hz E-field from a power line at 100 m
    produces ~1-5 mV at the antenna. The 40 dB gain keeps this inside the clip
    level: 12.5 dB of headroom over 5 mV, 26.5 dB over 1 mV.
  - Rf thermal noise: 40.7 nV/√Hz at output, ÷101 = 0.4 nV/√Hz input-referred
  - Rg thermal noise: 4.1 nV/√Hz (input-referred, negligible)
- **Input impedance:** the J202 bias resistor (1–100 GΩ) in parallel with the guarded
  PCB leakage (≥ 1 TΩ); the amplifier itself is far higher
- **Chosen over ADA4530-1** because:
  - Lower voltage noise (6.5 vs 14 nV/√Hz) — ~2× better
  - Lower current noise (0.01 vs 0.02 fA/√Hz)
  - Amplifier-only noise at 7.83 Hz (first Python budget, at the input pin): 17.6 vs
    25.8 nV/√Hz — ~1.5× voltage, ~2× power
  - Guard ring driven by external LMP7715 (proven in previous design iteration)
- **Chosen over OPA928** because:
  - Much higher current noise (0.07 fA/√Hz) makes it worse at ELF source impedances

### 3.2 Guard Ring Driver

- **IC:** Texas Instruments LMP7715
  - Voltage noise: 5.8 nV/√Hz
  - Input bias current: 100 fA
  - GBW: 17 MHz
  - SOT-23-5 package
- **Configuration:** Unity-gain buffer (U202) that senses IN− (§0) and drives the PCB
  guard ring through R203 = 470 Ω, with C205 = 220 pF C0G from the guard to GND
  for loop stability (`simulations/stability`)
- **Guard ring** surrounds all input traces and component pads on the input section
  of the PCB, driven at the same potential as the input node to eliminate surface
  leakage currents

### 3.3 Noise Budget (System at 7.83 Hz, C_ant = 140 pF)

**SPICE breakdown at SR1, referred to the antenna** (`simulations/spice`, §3.4):

| Noise source                                  | nV/√Hz | Share of power |
|-----------------------------------------------|-------:|---------------:|
| R2 33 kΩ (filter resistor next to the amplifier; R3 in the SPICE netlist) | 31.7 | 48 % |
| R1 33 kΩ (filter resistor at the antenna)     | 23.4   | 26 %           |
| LMP7721 voltage noise (with 1/f)              | 16.8   | 13 %           |
| PCB leakage current noise, 0.1 fA/√Hz (guarded) | 14.5 | 10 %           |
| Rg 1 kΩ                                       | 6.9    | 2 %            |
| LMP7721 current noise                         | 1.5    | 0.1 %          |
| **Effective noise (at antenna)**              | **45.8** |              |
| At the amplifier input (behind the 0.583 cap divider) | 26.7 |        |

The first Python budget (37.7 nV/√Hz at the amplifier input, 64.6 at the antenna)
divided every source by the cap-divider ratio. That is exact only for sources that
reach the input through the signal's own divider, so it was 3.0 dB pessimistic
(`simulations/spice`, §3.5). The J202 bias resistor adds its own noise: with
100 GΩ the floor at SR1 is 74.8 nV/√Hz, still 12.8 dB below the natural ELF
background (`simulations/system`).

**Comparison with Romero LNVA_24-20 (AD820, no input filter):**
- Romero AD820 amplifier noise at 7.83 Hz: ~121 nV/√Hz
- ELARA effective noise at 7.83 Hz: 45.8 nV/√Hz
- ELARA is **2.6× more sensitive at SR1 (7× in power)**, and additionally has
  **−121 dB FM rejection** with ideal parts (about −95 dB with 0.2 pF strays across
  the filter resistors; Romero has none — vulnerable to FM interference)
- With a larger antenna (higher C_ant), the cap divider loss decreases
  and ELARA's advantage grows further

**The design achieves both lower noise than Romero AND complete FM immunity.**
This is the correct engineering outcome for a field-deployable instrument.

### 3.4 Anti-Aliasing Filter

- Placed between LMP7721 output and PCM1804 input
- Topology: simple 1st-order passive RC (combined with preamp rolloff at 106 Hz
  gives effective 2nd-order filtering above 100 Hz)
- R_AA = 10 kΩ (thin film), C_AA = 100 nF (C0G/NP0)
- Cutoff frequency: fc = 1/(2π × 10k × 100n) = **159 Hz**
- Combined with preamp's 106 Hz rolloff, the system gain drops steeply above
  the ELF band, providing ample anti-aliasing protection
- PCM1804's internal 64× oversampling + digital decimation filter handles the rest
- **All capacitors in signal path must be C0G/NP0** — X7R introduces ferroelectric
  distortion at low frequencies (per TI SLYT796A app note), exactly where Schumann
  resonances live

### 3.5 ADC

- **IC:** Texas Instruments PCM1804
  - 24-bit delta-sigma stereo ADC, fully differential analog input
  - Input voltage: ±2.5 V differential (5 Vp-p)
  - Dynamic range: 112 dB typical
  - SNR: 111 dB typical (A-weighted)
  - THD+N: −102 dB typical
  - Sample rates: 32 kHz – 192 kHz (configurable via OSR0/OSR1/OSR2 pins)
  - Oversampling: 128× (single), 64× (dual), 32× (quad rate)
  - System clock: 128/256/384/512/768 × fs on SCKI pin
  - 28-pin SSOP
  - Supply: 5V analog (VCC) + 3.3V digital (VDD)
  - Built-in high-pass filter (HPF) for DC offset rejection (-3 dB at fs/48000)
- **Single-ended input configuration:**
  - VINL+ ← signal (from LMP7721 via C_out and AA filter)
  - VINL- ← VCOML (internal 2.5V common-mode reference)
  - R_bias (47k) from VCOML to the C_out/R_AA node for DC biasing after C_out
  - Rev 0.2: unity-gain LMP7715 driver after the AA filter, 100 Ω + 2.7 nF C0G
    at VINL+; BYPAS = 1 (on-chip HPF off, DC blocking is analog)
- **Stereo channel usage:**
  - Left channel: antenna signal
  - Right channel: **noise reference** — VINR+/VINR- both tied to VCOMR
    (zero differential input = quiet reference). PC software cross-correlates
    L and R channels for real-time coherent noise subtraction.
- **Sample rate:** 192 kHz (quad rate). OSR2=H, OSR1=H, OSR0=H in master mode.
  System clock = 128×fs = 24.576 MHz from MEMS oscillator.
- **ADC noise floor:** about 41 nV/√Hz at VINL (112 dB DR; `simulations/system`),
  0.7 nV/√Hz referred to the antenna behind the 35.1 dB of gain. With the driver,
  VCOM and reference, everything after the preamp adds 1.6–2.0 nV/√Hz at the
  antenna, 27–32 dB below the front end: the ADC is transparent and the system is
  analog-limited.

### 3.6 AES3 Transmitter

- **IC:** Cirrus Logic CS8406
  - SPDIF/AES3 digital audio transmitter, up to 192 kHz
  - **Hardware mode** (no firmware needed) — all configuration via DIP switches
  - DIP switches select: audio format (I2S / left-justified / right-justified),
    sample rate ratio, and other protocol options
  - Supports 24-bit audio data
- **One output, AES3 balanced** (110 Ω, transformer coupled): CS8406 TXP/TXN →
  2 × 22 Ω + 100 nF DC block → S22083 1:1 pulse transformer (2 kV isolation) →
  shielded RJ45 (Amphenol RJHSE-5380), AES3 on the blue pair (pins 4/5). Shielded
  Cat5e/6 (100 Ω pairs) carries it up to 100 m. The jack's shell is the cable
  shield, isolated from GND; the shield is earthed at the indoor end only. The
  other three pairs are unconnected (reserved for isolated control signals later).
- **Source impedance:** the CS8406 drivers have 33.5 Ω each at VL = 3.3 V
  (26.5 Ω at 5 V), so 2 × (22 + 33.5) = 111 Ω, inside AES3's 110 Ω ± 20 %;
  the 6.6 Vpp open-circuit swing gives about 3.3 Vpp into 110 Ω (AES3: 2–7 Vpp).
- Indoors: an RJ45-to-XLR adapter (pin 4 → XLR 2, pin 5 → XLR 3, shield → XLR 1)
  feeds an AES3 input; a 110 Ω to 75 Ω balun feeds a consumer S/PDIF (RCA) input.
- **Master clock:** 24.576 MHz MEMS oscillator (no discrete crystal needed).
  Single IC, lower EMI than crystal + buffer circuit, feeds both PCM1804 SCKI
  and CS8406 OMCK. Supports 48/96/192 kSPS via PCM1804 mode selection.

### 3.7 Antenna Bias

- **Circuit from previous design:** LMP7715 op-amp providing DC bias point to
  antenna through matched precision resistors (2× 47 kΩ, 0.05%, ERA-3VRW4702V)
- Large electrolytic capacitor (4700 µF) for decoupling
- Ensures the antenna DC potential is defined despite the ultra-high impedance
- **Rev 0.2:** the buffer output reaches the input only through J202 and a 1 kΩ
  isolation resistor. For continuous operation J202 carries a 1–100 GΩ glass
  resistor instead of the shunt (see §0: the air–earth current makes a truly
  floating input drift to a rail).

### 3.8 Power Supply

- **Input:** 230V AC mains via shielded twisted pair (containment-shielded — see §5)
- **AC-DC conversion:** Located at the outdoor unit
  - "Two-bucket" switched-capacitor concept for near-complete galvanic isolation
    from mains (charge periodically transferred between capacitors, 99% of the
    time fully isolated)
  - Fully EM-shielded converter compartment to prevent 50 Hz radiation
  - Alternatively: a commercial ultra-quiet isolated DC-DC module if the
    two-bucket approach proves too complex for v1
- **Rev 0.2 implementation (`PCB/acdc_converter/`):** IRM-05-15 → LM317 constant
  current 0.2 A → LM317 constant voltage 10.4 V (2.6 V per cell) → SS34 → two supercap buckets
  (4 × 10 F / 2.7 V in series, 5.1 kΩ balancing) → two Omron G6K-2 DPDT relays
  wired in opposite senses, swapped every ~15 s by a CD4060 → receiver side:
  2200 µF → LT3045 (6.98 V, R_SET 69.8 kΩ, 0.8 µV rms, EN/PGFB to IN, 22 µF C_SET) → common-mode
  choke → Micro-Fit to the amplifier. Form-C contacts break before they make, so
  the receiver is never connected to the charger side; the coupling left is the
  ~1 pF of the open contacts instead of the module's 20–100 pF barrier. Charger
  ground is bonded to PE and the enclosure.
- **Post-regulation:** Ultra-low-noise LDOs (ADM7150, factory-calibrated fixed output)
  - ADM7150-5.0: +5V analog rail (LMP7721, LMP7715, PCM1804 VCC) — 1.6 µV RMS
  - ADM7150-3.3: +3.3V digital rail (PCM1804 VDD, CS8406) — 1.6 µV RMS
  - Input: 6.98 V DC from the two-bucket PSU's LT3045, or a 9–15 V battery
- **No switching regulators in the analog signal path**
- **DC input rationale:**
  - 6.98 V, less the choke and cable (7.2 Ω at about 0.1 A) and the SS34
    reverse-polarity diode, leaves about 6.0 V at the ADM7150s (5.8 V in the
    worst corner, `simulations/psu`): 1.0 V (0.8 V) above the 5.0 V output, clear
    of its dropout, with little heat in the LDOs
  - A 9–15 V battery (for example a 12 V LiFePO4 pack) plugs into the same
    connector for portable or lowest-noise operation
  - 230 V AC mains still enters the outdoor unit, for the PSU only

### 3.9 NO Input Protection — By Design

**There is deliberately NO ESD or overvoltage protection on the antenna input.**

Any protection component (GDT, TVS, clamping diodes, JFETs) would introduce leakage
currents that utterly destroy the femtoampere-level noise floor of the LMP7721. Even
the lowest-leakage protection devices have nanoamp-scale leakage — thousands of times
worse than the amplifier's own 20 fA bias current. Protection and electrometer-grade
sensitivity are fundamentally incompatible.

**⚠ SAFETY WARNING: DISCONNECT THE ANTENNA DURING THUNDERSTORMS ⚠**

- The antenna is a vertical conductor connected to extremely sensitive, unprotected
  electronics. A nearby lightning strike WILL destroy the preamp and may cause fire.
- Before any approaching storm: **physically disconnect the whole preamp unit**
  (unplug mains and AES/EBU cables, disconnect antenna). Take it indoors if possible.
- The operator accepts full responsibility for monitoring weather conditions and
  disconnecting in time.

---

## 4. Outdoor Unit — Mechanical & PCB Design

### 4.1 Compartmentalised EM Shielding (RF Tuner Style)

Inside the plastic enclosure there are **two separate ALU enclosures** side by side:

1. **Antenna amplifier ALU enclosure** — contains the main PCB with three
   compartments (RF tuner-style walls, M3 bolts to PCB copper traces)
2. **PSU ALU enclosure** — separate self-contained unit with its own PCB,
   can be removed and replaced with a battery for the quietest operation

```
    Top view (inside plastic enclosure, ALU lids removed):

    ANTENNA AMPLIFIER ALU ENCLOSURE        PSU ALU ENCLOSURE
    ┌──────────┬──────────────┬──────────┐ ┌──────────────┐
    │          │              │          │ │              │
    │ COMP. 1  │  COMP. 2     │ COMP. 3  │ │   SEPARATE   │
    │ INPUT    │  ANALOG      │ DIGITAL  │ │   UNIT       │
    │          │              │          │ │              │
    │ LMP7721  │ Cg, C_out    │ PCM1804  │ │  IRM-05-15   │
    │ input    │ anti-alias   │ CS8406   │ │  CC/CV       │
    │ node     │ ADC driver   │ MEMS osc │ │  charger     │
    │ J202 bias│ bias buffer  │ xformer  │ │  2 buckets   │
    │ guard    │ 5 V LDO      │ RJ45     │ │  LT3045      │
    │ driver   │              │ DC in    │ │              │
    └──────────┴──────────────┴──────────┘ └──────────────┘
                                            ↕ removable!
                                            swap for battery
```

### Antenna Amplifier — Three Compartments

**Compartment 1 — INPUT (holiest-of-holies):**
- The LMP7721 with its feedback network, the guarded input island (J201 turret,
  J202 bias link) and the LMP7715 guard driver
- Completely isolated from everything else
- Prevents capacitive crosstalk from output back to input (which could cause
  oscillation — LMP7721 has 17 MHz GBW, plenty of gain at high frequencies)
- Prevents digital hash injection from the ADC and AES3 clocks

**Compartment 2 — ANALOG:**
- Cg and the output coupling capacitor, the anti-aliasing filter and the LMP7715
  ADC driver
- The antenna bias buffer (LMP7715, 47k/47k, 4700 µF; its 1 kΩ output reaches J202
  under the wall) and the 5 V LDO with the preamp supply filter
- Clean analog, but not femtoampere-sensitive

**Compartment 3 — DIGITAL:**
- The whole PCM1804 (with the 100 Ω / 2.7 nF C0G at VINL+), CS8406, MEMS
  oscillator, AES3 transformer, RJ45
- The 3.3 V LDO, the DC input and the mode switches
- Digital noise quarantined here; signals cross the walls on In2.Cu only

### PSU — Separate ALU Enclosure

- **Own enclosure, own PCB** — physically separate from the antenna amplifier
- Two-bucket isolated supply (`PCB/acdc_converter/`) with an LT3045 post-regulator,
  6.98 V DC out; the ADM7150-5.0 (+5V analog) and ADM7150-3.3 (+3.3V digital)
  LDOs sit on the amplifier board, after its reverse-polarity diode and TVS
- The noisiest subsystem gets its own cage — switching transients, ripple,
  and magnetic field from the converter are fully contained
- **Removable:** can be swapped for a battery (LiFePO4 or lead-acid) when
  the absolute lowest noise floor is needed (e.g., during critical measurements
  or at a location without mains power)
- DC power cable connects PSU enclosure to antenna amplifier enclosure via
  a simple connector

**Signals pass between compartments through PCB traces underneath the ALU walls.**
The walls block radiated coupling through the air between stages.

### 4.2 Antenna Input on PCB Back Side

- **The antenna input (turret J201) is fed from the BOTTOM of the PCB**, through
  the PTFE feed-through in the tray
- The input signal comes up through the PCB into Compartment 1
- This provides an additional shield layer (PCB ground plane) between the antenna
  input trace and the noisy digital section on top
- The LMP7721's input traces and guard ring are routed on inner/bottom layers
  underneath Compartment 1

### 4.3 PCB Design Rules

- **Main PCB material:** PTFE (Teflon) or Rogers 4350B preferred over FR4.
  Much lower moisture absorption (~0.02% vs FR4's ~0.15%) and higher volume
  resistivity (10¹⁷ vs 10¹⁰–10¹² Ω·cm). This is critical for maintaining
  femtoampere-level performance in an outdoor environment where humidity is
  the biggest enemy. A hybrid stackup (Rogers outer layers, FR4 inner — per
  ADI CN0407 reference design) is also acceptable. FR4 is a fallback only if
  budget is extremely tight, with guard rings compensating for its inferior
  insulation properties.
- **Guard rings:** Active guard driven from LMP7715 output, surrounding all traces
  connected to the input node on ALL PCB layers
- **Clearance:** Minimum 2 mm between input traces and any other signal
- **Via stitching:** Guard ring vias every 2 mm around input zone
- **No solder mask** over input node area (solder mask absorbs moisture → leakage)
- **Conformal coating:** Avoid silicone-based; use acrylic or parylene
- **All passives must be hi-fi / precision grade throughout the entire board:**
  - **Resistors:** Thin-film only (low excess noise, low TCR). No carbon composition,
    no thick-film. Precision tolerance (0.1% or better) in signal path; 1% acceptable
    for non-critical positions (pull-ups, power dividers)
  - **Capacitors (signal path):** C0G/NP0 ceramic only. No X7R/X5R — ferroelectric
    voltage coefficient introduces distortion at low frequencies, exactly where
    Schumann resonances live (per TI SLYT796A app note). Film capacitors
    (polypropylene, polystyrene) also acceptable where size permits
  - **Capacitors (power bypass):** X7R acceptable for bulk decoupling only, not
    in the signal path
  - **Electrolytics:** Low-ESR, long-life types for power supply bulk capacitance
  - At these signal levels, every passive component is a potential noise source
    or nonlinearity — there are no "non-critical" positions in the analog path

### 4.4 Outer Enclosure

- Weatherproof plastic enclosure (IP65 or similar)
- Plastic so it doesn't interfere with electric-field antenna coupling
- Contains the PCB with ALU shield compartments
- Cable glands for: antenna wire, AES3 cable (Cat5e/6 STP), screened mains cable
- Antenna wire enters through the top and goes to the plate capacitors' ANT post;
  their output lead reaches the J201 turret through the shield's PTFE bush

---

## 5. Cabling — "Reverse Shielding" Philosophy

In this project, shielding protects the antenna from the cables' own emissions,
not the other way around. The antenna is deliberately trying to pick up everything
from the environment — the only enemies are things we bring there ourselves.

### 5.1 AES/EBU Digital Audio Cable (~100 m)

- AES3 balanced 110 Ω on one pair of a shielded Cat5e/6 cable (100 Ω pairs), RJ45
  at the outdoor end
- AES3 is rated for 100 m cable runs (unlike consumer S/PDIF coax at ~10 m
  or TOSLINK at ~15 m)
- Transformer at the outdoor end (and in the indoor interface) for galvanic isolation
- **Shield is containment shielding:** prevents the AES3 bit-clock harmonics (~6 MHz+
  at 192 kHz) from radiating out and coupling into the antenna
- Shield grounded at the **indoor end only** to avoid ground loops; at the outdoor
  end the jack's shell floats (an optional 10 nF RF bond keeps the DC isolation)

### 5.2 230V AC Mains Cable (~100 m)

- Screened 3-core mains cable (L, N, PE; never Ethernet cable, which is not
  mains rated): MAINS_CABLE.md
- Twisted (cabled) L and N: their currents flow in opposite directions, magnetic
  fields largely cancel
- **Shield is containment shielding:** prevents 50 Hz electric field from radiating
  out and coupling into the antenna (the reverse of normal cable shielding!)
- Shield grounded at the **mains entry point**
- 230V AC is efficient for long runs (low current → negligible I²R loss)

### 5.3 Cable Summary

Both cables serve the same "reverse shielding" principle: we are shielding against
ourselves, not the environment. The environment IS the signal.

---

## 6. Indoor Unit (Off-the-Shelf)

- **Hardware:** Any USB audio interface with an AES3 input (RJ45-to-XLR adapter), or
  with an S/PDIF coaxial input through a 110 Ω to 75 Ω balun
- **Drivers:** Standard audio drivers (ASIO, WASAPI, ALSA)
- **No custom hardware required**

---

## 7. PC Software

### 7.1 Adaptive Mains Rejection

- NLMS adaptive notch filter tracking 50/60 Hz fundamental
- Harmonic comb rejection up to at least 2 kHz
- Optional: dedicated mains reference channel for Wiener filtering
- Implementation: Python with numpy/scipy, or Rust for real-time performance

### 7.2 Real-Time Spectrogram

- Dual-pane display: ELF (0–300 Hz) and VLF (0–22 kHz)
- Configurable FFT size, overlap, windowing
- Scrolling waterfall + instantaneous spectrum
- Schumann resonance peak tracking and logging

### 7.3 Data Recording

- Continuous raw sample logging (time-stamped)
- Triggered event recording (sferic bursts, whistlers)
- Export: WAV (for compatibility with existing VLF tools like SpectrumLab), HDF5, CSV

---

## 8. Target Specifications

| Parameter                     | Value                              |
|-------------------------------|------------------------------------|
| Frequency range               | 1–50 Hz (ELF, Schumann resonances) |
| Preamp gain                   | 40 dB (100×), flat across ELF band |
| System noise floor @ 7.83 Hz  | 45.8 nV/√Hz at the antenna (SPICE; Python budget 64.6) |
| Noise at the amplifier input  | 26.7 nV/√Hz @ 7.83 Hz (SPICE)     |
| ADC dynamic range             | 112 dB (PCM1804)                  |
| ADC resolution                | 24-bit, 192 kSPS                  |
| Digital output                | AES3 (110 Ω) on RJ45, shielded Cat5e/6 |
| Cable length                  | Up to 100 m (AES/EBU)             |
| FM / AM rejection             | −121 dB @ 100 MHz / −41 dB @ 1 MHz |
| Mains rejection (software)    | > 60 dB adaptive                  |
| Power (outdoor unit)          | 6.98 V DC (two-bucket PSU) or 9–15 V battery → ADM7150 LDOs (5V + 3.3V) |
| Outdoor enclosure             | IP65 plastic + ALU EM shield      |

---

## 9. Key Component List

| Component      | Part Number        | Role                              |
|----------------|--------------------|------------------------------------|
| Electrometer   | LMP7721            | Input buffer (6.5 nV/√Hz, 0.01 fA/√Hz) |
| Guard driver   | LMP7715            | Guard ring buffer (5.8 nV/√Hz)    |
| ADC            | PCM1804            | 24-bit delta-sigma, 192 kSPS      |
| AES3 TX        | CS8406             | Digital audio transmitter          |
| Audio xformer  | S22083             | Galvanic isolation of the AES3 output |
| LDO (analog)   | ADM7150-5.0        | Ultra-low noise, 1.6 µV RMS, +5V  |
| LDO (digital)  | ADM7150-3.3        | Ultra-low noise, 1.6 µV RMS, +3.3V|
| Bias resistors | ERA-3VRW4702V      | 47 kΩ, 0.05%, antenna bias        |
| Feedback R (Rf)| thin-film, 0.1%    | 100 kΩ, preamp feedback (Rg = 1 kΩ) |
| Filter R       | thin-film          | 33 kΩ ×2, air-mounted RF filter   |

---

## 10. Design Toolchain

| Tool                | Purpose                                      |
|---------------------|----------------------------------------------|
| KiCad               | Schematic, PCB layout, component libraries   |
| CadQuery (Python)   | 3D models (STEP) for components & enclosure  |
| FreeCAD + StepUp    | Mechanical review, measurement, ECAD↔MCAD    |
| ngspice             | Analog circuit simulation (noise analysis)   |
| Python + numpy/scipy| Noise modelling, DSP, spectrograms           |
| GCC/ARM             | Firmware (if MCU added in future revision)   |

All artefacts are text files or generated by Python scripts. Claude Code can drive
every tool in the chain.

---

## 11. Project Phases

### Phase 1 — Outdoor Unit Hardware
1. Finalise schematic in KiCad (LMP7721 preamp + PCM1804 + CS8406 + PSU)
2. SPICE noise simulation in ngspice — verify noise budget
3. Component library: KiCad symbols + footprints + CadQuery 3D models
4. PCB layout with compartmentalised guard ring methodology
5. ALU EM shield mechanical design (CadQuery → STEP)
6. Plastic enclosure selection or design
7. BOM finalisation and component procurement
8. Prototype fabrication and assembly

### Phase 2 — PC Software
1. AES3 / S/PDIF audio capture via USB audio interface
2. Adaptive 50/60 Hz notch filter (NLMS)
3. Real-time FFT spectrogram (ELF + VLF bands)
4. Schumann resonance peak detection and logging
5. Data recording and export (WAV, HDF5)

### Phase 3 — Integration & Field Testing
1. Antenna installation (T-antenna, ground stake)
2. Cable routing (AES/EBU + mains, both shielded)
3. End-to-end system test
4. First light: Schumann resonances at 7.83, 14.3, 20.8 Hz
5. VLF sferics and whistler observation
6. Iterative optimisation based on field results

### Phase 4 — Future Enhancements (optional)
- GPS PPS timestamping for cross-station correlation
- Higher-performance ADC (ADS1263 32-bit) for deeper ELF dynamic range
- Dedicated mains reference channel for Wiener filtering
- Second channel for magnetic loop antenna (comparative measurements)
- Web dashboard for remote monitoring

---

*Document revision: 0.2 — generated schematics, two-bucket PSU, layouts (see §0)*
*Author: Matej + Claude, March 2026*
