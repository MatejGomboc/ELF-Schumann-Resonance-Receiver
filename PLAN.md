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
    │  PCM1804 (24-bit ADC, up to 96 kSPS)        │
    │  ↓                                          │
    │  CS8406 (SPDIF transmitter)                 │
    │  ↓                                          │
    │  Audio transformer (galvanic isolation)      │
    │  ↓                                          │
    │  Power: 9V DC → ADM7150 LDOs (5V + 3.3V)   │
    └──────────────┬──────────────────────────────┘
                   │
                   │  Two shielded twisted pairs:
                   │  • AES/EBU digital audio (110Ω STP)
                   │  • 230V AC mains power
                   │  (both containment-shielded — see §5)
                   │
    ┌──────────────┴──────────────────────────────┐
    │  INDOOR UNIT (off-the-shelf)                │
    │                                              │
    │  USB audio card with SPDIF input             │
    │  → PC                                        │
    │  → Software: adaptive filtering,             │
    │    spectrograms, data logging                │
    └─────────────────────────────────────────────┘
```

**Key simplification:** By digitising at the antenna and transmitting via SPDIF, the entire
indoor unit is eliminated. No custom indoor PCB, no STM32, no PGA, no dual-ADC
architecture. The indoor side is just a commercial USB audio card with SPDIF input.

---

## 2. Antenna

- **Type:** Marconi T-antenna (vertical electric field probe)
- **Dimensions:** ~10 m vertical element, ~15 m capacitive top (inverted-L or T shape)
- **Estimated capacitance:** ~100 pF (50–150 pF depending on geometry and environment)
- **Electrical model:** Almost ideal capacitor at ELF/VLF frequencies
  - At 7.83 Hz: |Z_source| ≈ 203 MΩ (purely capacitive)
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
The filter resistors dominate the noise budget (69% of total at SR1).
R=33k gives 23.4 nV/√Hz per resistor (vs 60.4 with old 220k = **2.6× less noise**).
Effective noise at antenna: 64.6 nV/√Hz (**3.2× better than Romero AD820**).
AM rejection: -41 dB (adequate for nearby AM tower at 15 km).
FM rejection: -121 dB (FM utterly annihilated).

| Frequency        | Attenuation (2 stages)  | Effect                          |
|------------------|-------------------------|---------------------------------|
| 7.83 Hz (SR1)    | -4.3 dB (cap divider)   | Fixed loss, gain-compensated    |
| 14.3 Hz (SR2)    | -4.3 dB                 | Fixed loss, gain-compensated    |
| 20.8 Hz (SR3)    | -4.3 dB                 | Fixed loss, gain-compensated    |
| 1 kHz (VLF)      | -4.4 dB                 | Negligible extra rolloff        |
| 10 kHz (VLF)     | -7.7 dB                 | Moderate rolloff                |
| 22 kHz (VLF top) | -13.3 dB                | Known rolloff, compensate in SW |
| 100 MHz (FM)     | -151.9 dB               | FM utterly annihilated          |
| 900 MHz (GSM)    | -190.1 dB               | GSM utterly annihilated         |

**Why R=33 kΩ instead of 220 kΩ:** The filter cutoff (96.5 kHz) is well below
AM broadcast (1 MHz, -41 dB rejection) and far below FM (100 MHz, -121 dB).
There is no need for a low cutoff in the RF filter — the ELF band shaping
is done by the preamp feedback (117 Hz rolloff) and AA filter (159 Hz).
The tradeoff analysis in `simulations/preamp_noise/filter_resistor_tradeoff.py`
shows R=33k is optimal: adequate AM rejection (-41 dB for nearby 15 km tower)
with dramatically lower noise (2.3× better than old 220k design).

**Note on VLF rolloff:** The rolloff above 10 kHz is a fixed, stable transfer
function (2-pole RC) that can be trivially compensated by a digital IIR
correction filter in the PC software. The R2/C3 feedback network in the
LMP7721 stage also provides frequency-dependent gain that partially
compensates the rolloff at VLF frequencies.

**Plate dimensions for 45 pF** (C = ε₀ × A / d, air dielectric εr ≈ 1.0):

| Air gap   | Plate side | Copper area |
|-----------|------------|-------------|
| 0.2 mm    | 33.0 mm    | 32.0 mm     |
| 0.5 mm    | 52.0 mm    | 51.0 mm     |
| 1.0 mm    | 73.0 mm    | 72.0 mm     |

Plate size is flexible — choose based on enclosure constraints. Larger plates
with wider gaps are easier to manufacture mechanically.

See `simulations/plate_capacitor/plate_capacitor_geometry.py` for full sweep.
See `simulations/rc_filter_cascade/rc_filter_cascade.py` for Bode plot.
See `simulations/preamp_noise/filter_resistor_tradeoff.py` for R optimisation.
See `simulations/preamp_noise/antenna_capacitance.py` for signal loss model.

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
- This would bypass the second 220 kΩ resistor, degrading both filter performance
  and input impedance
- Physically separate pieces with an air gap between them ensure the only path
  between nodes is through the 220 kΩ resistor
- Air is a near-perfect insulator: no surface leakage, no moisture absorption

**Physical mounting:**
- Both plate capacitors are suspended in air inside the plastic outer enclosure
- NOT mounted on the main PCB — air-wired connections only
- Located outside the ALU EM shield (no shielding needed — this stage is at
  antenna potential, same signal level as the environment)
- The 220 kΩ resistors are also air-mounted (not on the main PCB)

**Antenna bias at startup (jumper-based):**
- The LMP7715 antenna bias circuit connects to the LMP7721 input trace via a
  **physical jumper** on the PCB
- With teraohm input impedance, any initial static charge on the antenna/input
  would otherwise take extremely long to dissipate
- **Startup procedure:** insert jumper → power on → wait for settling → remove jumper
- Once removed, there is literally nothing there — air gap gives infinite isolation,
  zero leakage, zero thermoelectric EMF. No relay or semiconductor switch can
  match a physically absent connection.

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
  - Rg = 1 kΩ (ground-reference resistor, IN− to BIAS_MID via antenna bias 2.5V ref)
  - Cg = 100 µF polypropylene (DC blocking cap, in series with Rg)
  - C_out = 10 µF film (output coupling cap, blocks 2.5V DC to ADC)
  - Gain: G(f) = 1 + Rf / (Rg × (1 + jωRfCf)) × jωCg / (jωCg + 1/Rg)
  - At DC: G = 1 (0 dB) — Cg blocks DC, no DC offset amplification
  - At ELF (1.6–106 Hz): G = 1 + 100k/1k = **101 (40.1 dB)** — flat across Schumann band
  - Corner frequency: fc = 1/(2π × 100k × 15nF) = **106 Hz**
  - Above 106 Hz: gain rolls off −20 dB/dec toward unity
  - **Design decision:** VLF band dropped in favour of ELF quality. The 40 dB gain
    maximises signal fidelity while keeping 50 Hz power line hum within the ADC's
    linear range (~25 mV max input before clipping). The 50 Hz is removed cleanly
    by a digital notch filter in software.
  - **Max amplification is dictated by 50 Hz mains E-field pickup.** With 1 TΩ input
    impedance and 6.5m effective antenna height, the 50 Hz E-field from a power
    line at 100m distance produces ~1-5 mV at the antenna. The 40 dB gain keeps
    this within the ADC's 73 dB headroom.
  - Rf thermal noise: 40.7 nV/√Hz at output, ÷101 = 0.4 nV/√Hz input-referred
  - Rg thermal noise: 4.1 nV/√Hz (input-referred, negligible)
- **Input impedance:** ≥100 GΩ (set by PCB leakage, not amplifier)
- **Chosen over ADA4530-1** because:
  - Lower voltage noise (6.5 vs 14 nV/√Hz) — ~2× better
  - Lower current noise (0.01 vs 0.02 fA/√Hz)
  - Total amplifier noise at 7.83 Hz: 6.8 vs 14.6 nV/√Hz — ~2× voltage, ~4× power
  - Guard ring driven by external LMP7715 (proven in previous design iteration)
- **Chosen over OPA928** because:
  - Much higher current noise (0.07 fA/√Hz) makes it worse at ELF source impedances

### 3.2 Guard Ring Driver

- **IC:** Texas Instruments LMP7715
  - Voltage noise: 5.8 nV/√Hz
  - Input bias current: 100 fA
  - GBW: 17 MHz
  - SOT-23-5 package
- **Configuration:** Unity-gain buffer driving the PCB guard ring through a resistor
  (470Ω as in previous design, or value to be optimised)
- **Guard ring** surrounds all input traces and component pads on the input section
  of the PCB, driven at the same potential as the input node to eliminate surface
  leakage currents

### 3.3 Noise Budget (System at 7.83 Hz, C_ant = 140 pF)

**Amplifier-only noise (LMP7721 at the input pin):**

| Noise source                          | Contribution         |
|---------------------------------------|----------------------|
| LMP7721 voltage noise (+ 1/f)        | 9.8 nV/√Hz          |
| LMP7721 current noise × Z_source     | 0.01 fA × 145 MΩ = 1.5 nV/√Hz |
| PCB leakage current noise (guarded)   | 0.1 fA × 145 MΩ = 14.5 nV/√Hz |
| **Amplifier input-referred total**    | **~17.6 nV/√Hz**    |

**System noise (including input filter, referred to antenna):**

| Noise source                          | Contribution         |
|---------------------------------------|----------------------|
| LMP7721 voltage + current + PCB       | 17.6 nV/√Hz         |
| R_filt ×2 (220 kΩ each, thermal)     | 2 × 60.4 = 85.4 nV/√Hz (RSS) |
| R_fb (1 kΩ, thermal)                 | 4.1 nV/√Hz          |
| **Total at amplifier input**          | **89.1 nV/√Hz**     |
| Signal loss (cap divider, -4.3 dB)    | ÷ 0.61              |
| **Effective noise (at antenna)**      | **~147 nV/√Hz**     |

**Comparison with Romero LNVA_24-20 (AD820, no input filter):**
- Romero AD820 amplifier noise at 7.83 Hz: ~121 nV/√Hz
- ELARA effective noise at 7.83 Hz: ~147 nV/√Hz
- ELARA is ~1.2× noisier at SR1, but has **-152 dB FM rejection**
  (Romero has none — vulnerable to FM interference)
- With a larger antenna (C_ant > 250 pF), the cap divider loss
  decreases and ELARA matches or beats Romero
- At VLF frequencies (1–22 kHz), the R2/C3 feedback provides gain
  that compensates for the filter rolloff

**The design trades ~3 dB of noise floor for complete FM immunity.**
This is the correct engineering choice for a field-deployable instrument.

### 3.4 Anti-Aliasing Filter

- Placed between LMP7721 output and PCM1804 input
- Topology: simple 1st-order passive RC (combined with preamp rolloff at 117 Hz
  gives effective 2nd-order filtering above 100 Hz)
- R_AA = 10 kΩ (thin film), C_AA = 100 nF (C0G/NP0)
- Cutoff frequency: fc = 1/(2π × 10k × 100n) = **159 Hz**
- Combined with preamp's 117 Hz rolloff, the system gain drops steeply above
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
  - R_bias (47k) from VCOML to VINL+ for DC biasing after C_out
- **Stereo channel usage:**
  - Left channel: antenna signal
  - Right channel: **noise reference** — VINR+/VINR- both tied to VCOMR
    (zero differential input = quiet reference). PC software cross-correlates
    L and R channels for real-time coherent noise subtraction.
- **Sample rate:** 192 kHz (quad rate). OSR2=H, OSR1=H, OSR0=H in master mode.
  System clock = 128×fs = 24.576 MHz from MEMS oscillator.
- **ADC noise floor:** 16.1 nV/√Hz at 192 kHz — below the preamp's noise,
  making the ADC transparent. The system is entirely analog-limited.

### 3.6 SPDIF Transmitter

- **IC:** Cirrus Logic CS8406
  - SPDIF/AES3 digital audio transmitter, up to 192 kHz
  - **Hardware mode** (no firmware needed) — all configuration via DIP switches
  - DIP switches select: audio format (I2S / left-justified / right-justified),
    sample rate ratio, and other protocol options
  - Supports 24-bit audio data
- **Dual outputs** (active simultaneously via separate transformers):
  - **AES/EBU balanced** (110Ω STP): via S22083 audio transformer → XLR or
    Cat6 STP cable, up to 100 m. Primary output for long cable runs.
  - **S/PDIF coax** (75Ω unbalanced): via S22082 audio transformer → RCA jack.
    For short runs to nearby equipment.
- **Master clock:** 24.576 MHz MEMS oscillator (no discrete crystal needed).
  Single IC, lower EMI than crystal + buffer circuit, feeds both PCM1804 SCKI
  and CS8406 OMCK. Supports 48/64/96 kSPS via PCM1804 MD pin selection.

### 3.7 Antenna Bias

- **Circuit from previous design:** LMP7715 op-amp providing DC bias point to
  antenna through matched precision resistors (2× 47 kΩ, 0.05%, ERA-3VRW4702V)
- Large electrolytic capacitor (4700 µF) for decoupling
- Ensures the antenna DC potential is defined despite the ultra-high impedance

### 3.8 Power Supply

- **Input:** 230V AC mains via shielded twisted pair (containment-shielded — see §5)
- **AC-DC conversion:** Located at the outdoor unit
  - "Two-bucket" switched-capacitor concept for near-complete galvanic isolation
    from mains (charge periodically transferred between capacitors, 99% of the
    time fully isolated)
  - Fully EM-shielded converter compartment to prevent 50 Hz radiation
  - Alternatively: a commercial ultra-quiet isolated DC-DC module if the
    two-bucket approach proves too complex for v1
- **Post-regulation:** Ultra-low-noise LDOs (ADM7150, factory-calibrated fixed output)
  - ADM7150-5.0: +5V analog rail (LMP7721, LMP7715, PCM1804 VCC) — 1.6 µV RMS
  - ADM7150-3.3: +3.3V digital rail (PCM1804 VDD, CS8406) — 1.6 µV RMS
  - Input: 9V DC unregulated bus (from AC-DC converter or 9V battery)
- **No switching regulators in the analog signal path**
- **9V DC bus rationale:**
  - Standard 9V battery for portable/lowest-noise operation
  - AC-DC converter (in separate PSU enclosure) outputs 9V DC
  - Sufficient headroom for both 5V and 3.3V LDOs (ADM7150 dropout ~350 mV)
  - 230V AC mains still enters the outdoor unit for the AC-DC converter

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
    │ LMP7721  │ LMP7715      │ CS8406   │ │  AC-DC       │
    │ input    │ guard driver │ SPDIF TX │ │  converter   │
    │ node     │ anti-alias   │ crystal  │ │              │
    │ bias R   │ filter       │ PCM1804  │ │  ADM7150     │
    │ guard    │ LMP7721 out  │ xformer  │ │  LDOs        │
    │ ring     │              │          │ │              │
    └──────────┴──────────────┴──────────┘ └──────────────┘
                                            ↕ removable!
                                            swap for battery
```

### Antenna Amplifier — Three Compartments

**Compartment 1 — INPUT (holiest-of-holies):**
- Only the LMP7721 input pin, antenna bias components, and guard ring
- Completely isolated from everything else
- Prevents capacitive crosstalk from output back to input (which could cause
  oscillation — LMP7721 has 17 MHz GBW, plenty of gain at high frequencies)
- Prevents digital hash injection from ADC/SPDIF clock

**Compartment 2 — ANALOG:**
- LMP7715 guard driver, LMP7721 output side, anti-aliasing filter
- Analog input side of PCM1804
- Clean analog, but not femtoampere-sensitive

**Compartment 3 — DIGITAL:**
- CS8406, crystal oscillator, SPDIF transformer
- PCM1804 digital side
- Digital noise quarantined here

### PSU — Separate ALU Enclosure

- **Own enclosure, own PCB** — physically separate from the antenna amplifier
- AC-DC converter (two-bucket or commercial module) outputting 9V DC
- ADM7150-5.0 (+5V analog) and ADM7150-3.3 (+3.3V digital) ultra-low-noise LDOs
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

- **Antenna connector (J1) is on the BOTTOM of the PCB**
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
- Cable glands for: antenna wire, AES/EBU twisted pair, mains twisted pair
- Antenna wire enters through the top, connects to J1 on PCB bottom

---

## 5. Cabling — "Reverse Shielding" Philosophy

In this project, shielding protects the antenna from the cables' own emissions,
not the other way around. The antenna is deliberately trying to pick up everything
from the environment — the only enemies are things we bring there ourselves.

### 5.1 AES/EBU Digital Audio Cable (~100 m)

- AES3 balanced 110Ω shielded twisted pair
- AES/EBU is rated for 100 m cable runs (unlike consumer SPDIF coax at ~10 m
  or TOSLINK at ~15 m)
- Audio transformers at each end for galvanic isolation
- **Shield is containment shielding:** prevents SPDIF bit-clock harmonics (~3 MHz+)
  from radiating out and coupling into the antenna
- Shield grounded at the **indoor end only** to avoid ground loops

### 5.2 230V AC Mains Cable (~100 m)

- Shielded twisted pair
- Twisted pair: live and neutral currents flow in opposite directions, magnetic
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

- **Hardware:** Any USB audio card / audio interface with SPDIF (coaxial or optical) input
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
| Frequency range               | 1 Hz – 22 kHz                     |
| Input noise floor @ 7.83 Hz   | < 7 nV/√Hz (input-referred)       |
| ADC dynamic range             | 99 dB (PCM1804)                   |
| ADC resolution                | 24-bit                            |
| Sample rate                   | Up to 96 kSPS                     |
| Digital output                | AES/EBU (SPDIF) over 110Ω STP    |
| Cable length                  | Up to 100 m                       |
| Mains rejection (software)    | > 60 dB adaptive                  |
| Power (outdoor unit)          | 230V AC mains, locally regulated  |
| Outdoor enclosure             | IP65 plastic + ALU EM shield      |

---

## 9. Key Component List

| Component      | Part Number        | Role                              |
|----------------|--------------------|------------------------------------|
| Electrometer   | LMP7721            | Input buffer (6.5 nV/√Hz, 0.01 fA/√Hz) |
| Guard driver   | LMP7715            | Guard ring buffer (5.8 nV/√Hz)    |
| ADC            | PCM1804            | 24-bit delta-sigma, 96 kSPS       |
| SPDIF TX       | CS8406             | Digital audio transmitter          |
| Audio xformer  | S22083             | Galvanic isolation for AES/EBU    |
| LDO (analog)   | ADM7150-5.0        | Ultra-low noise, 1.6 µV RMS, +5V  |
| LDO (digital)  | ADM7150-3.3        | Ultra-low noise, 1.6 µV RMS, +3.3V|
| Bias resistors | ERA-3VRW4702V      | 47 kΩ, 0.05%, antenna bias        |
| Feedback R     | RG1608N-202-B-T5   | 2 kΩ, 0.1%, signal path           |
| Bias R (high-Z)| MCT0603MD2004BP500 | 2 MΩ, 1%, input bias              |

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
1. SPDIF audio capture via USB audio card
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

*Document revision: 0.1 — Initial plan*
*Author: Matej + Claude, March 2026*
