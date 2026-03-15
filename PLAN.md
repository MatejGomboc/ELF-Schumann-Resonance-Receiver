# ELARA — ELF/VLF Atmospheric Radio Analyser

## Project Vision & Plan

**Goal:** Design and build a professional-grade electric-field receiver for natural ELF/VLF
radio signals (1 Hz – 22 kHz), optimised for Schumann resonance monitoring, sferic
detection, and whistler observation. The design targets noise performance significantly
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
    OUTDOOR UNIT (one custom PCB + two PCB-capacitor pieces)
    ┌─────────────────────────────────────────────┐
    │  Marconi T-Antenna (~10m vert, ~15m top)    │
    │  ↓                                          │
    │  Input RF filter (2-stage RC low-pass)      │
    │  (air-suspended PCB capacitors — see §3.0)  │
    │  ↓                                          │
    │  LMP7721 electrometer buffer                │
    │  (+ LMP7715 guard ring driver)              │
    │  ↓                                          │
    │  Anti-aliasing LPF                          │
    │  ↓                                          │
    │  PCM1808 (24-bit ADC, up to 96 kSPS)        │
    │  ↓                                          │
    │  CS8406 (SPDIF transmitter)                 │
    │  ↓                                          │
    │  Audio transformer (galvanic isolation)      │
    │  ↓                                          │
    │  Power: 230V AC → AC-DC → LT3042 LDO       │
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

### 3.0 Input RF Rejection Filter (Air-Suspended PCB Capacitors)

**Problem:** FM broadcast stations (88–108 MHz) are strong enough to drive the LMP7721
into nonlinear operation. The op-amp rectifies/demodulates the FM carrier, producing
spurious signals in the ELF/VLF band. This must be suppressed before the amplifier input.

**Solution:** A 2-stage cascaded RC low-pass filter using PCB-material capacitors.

```
                   (suspended in air, inside plastic enclosure, OUTSIDE ALU shield)

                          PCB cap 1              PCB cap 2
                          ~1.5cm square           ~1.5cm square
                          (separate PCB)          (separate PCB)
antenna ──── 1MΩ ──── node1 ──── 1MΩ ──── node2 ──── wire ──→ LMP7721 IN+
                        |                    |                  (inside ALU
                    ┌───┴───┐            ┌───┴───┐               shield)
                    │  Cu   │            │  Cu   │
                    │  FR4  │ ~10pF      │  FR4  │ ~10pF
                    │  Cu   │            │  Cu   │
                    └───┬───┘            └───┬───┘
                        |                    |
                       GND                  GND
```

**Cutoff frequency:** fc = 1/(2π × 1 MΩ × 10 pF) ≈ **15.9 kHz** per stage

| Frequency        | Attenuation (2 stages) | Effect                        |
|------------------|------------------------|-------------------------------|
| 7.83 Hz (SR1)    | ~0 dB                  | Signal passes unaffected      |
| 22 kHz (VLF top) | ~few dB                | Acceptable rolloff            |
| 100 MHz (FM)     | ~152 dB                | FM utterly annihilated        |

**Why PCB-material capacitors:**
- Two copper planes on a small PCB piece form a parallel plate capacitor
- ~1.5 cm × 1.5 cm with standard substrate thickness gives roughly 5–10 pF
  (C = ε₀ × εr × A / d)
- No commercial capacitor package → no package leakage current paths
- Substrate dielectric leakage provides a path for the LMP7721's femtoampere
  bias current to drain (producing only µV-level offset) while maintaining
  teraohm-class input impedance
- Turning the substrate's dielectric leakage "defect" into a design feature

**Cap PCB material options (independent choice from main PCB):**
- **Rogers 4350B** (preferred): stable εr over temperature (~50 ppm/°C vs FR4's
  200+ ppm/°C), very low moisture absorption — filter cutoff stays put regardless
  of weather. Readily available, modest cost for two tiny pieces.
- **Alumina (ceramic) substrate:** virtually zero moisture absorption, extremely
  stable εr, available from RF substrate vendors. The gold standard for stability.
- **FR4** (fallback): acceptable for prototyping. Higher εr drift with temperature
  and humidity means the filter cutoff will wander, but with ~150 dB of margin
  at FM frequencies this is tolerable.
- Cost difference between FR4 and Rogers for two 1.5 cm squares is negligible.

**Why TWO SEPARATE PCB pieces (not one shared piece):**
- If both caps shared one PCB, surface and volume leakage through the common
  FR4 substrate would create a parasitic resistance between node1 and node2
- This would bypass the second 1 MΩ resistor, degrading both filter performance
  and input impedance
- Physically separate pieces with an air gap between them ensure the only path
  between nodes is through the 1 MΩ resistor
- Air is a near-perfect insulator: no surface leakage, no moisture absorption

**Physical mounting:**
- Both PCB-cap pieces are suspended in air inside the plastic outer enclosure
- NOT mounted on the main PCB — air-wired connections only
- Located outside the ALU EM shield (no shielding needed — this stage is at
  antenna potential, same signal level as the environment)
- The 1 MΩ resistors are also air-mounted (not on the main PCB)

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
- **Configuration:** Unity-gain buffer (voltage follower)
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

### 3.3 Noise Budget (Preamp at 7.83 Hz, C_ant = 100 pF)

| Noise source                          | Contribution         |
|---------------------------------------|----------------------|
| LMP7721 voltage noise                 | 6.5 nV/√Hz          |
| LMP7721 current noise × Z_source     | 0.01 fA × 203 MΩ    |
|                                       | = 2.0 nV/√Hz        |
| PCB leakage current noise (guarded)   | Target: < 1 nV/√Hz  |
| **Total input-referred noise**        | **~6.8 nV/√Hz**     |

Compare Romero LNVA_24-20 with AD820:
- AD820 total at 7.83 Hz: ~163 nV/√Hz
- **Improvement: ~24× in voltage, ~575× in noise power**

### 3.4 Anti-Aliasing Filter

- Placed between LMP7721 output and PCM1808 input
- Topology: Sallen-Key or passive RC, Butterworth or Bessel (phase linearity
  preferred for time-domain sferic analysis)
- Cutoff frequency: set to match ADC sample rate (e.g., ~22 kHz for 48 kSPS)
- **All capacitors in signal path must be C0G/NP0** — X7R introduces ferroelectric
  distortion at low frequencies (per TI SLYT796A app note), exactly where Schumann
  resonances live

### 3.5 ADC

- **IC:** Texas Instruments PCM1808
  - 24-bit delta-sigma stereo ADC
  - Single-ended voltage input, 3 Vp-p
  - SNR: 99 dB typical
  - THD+N: −93 dB typical
  - Sample rates: 8 kHz – 96 kHz
  - Oversampling: 64×, includes digital decimation filter and high-pass filter
  - 14-pin TSSOP
  - Supply: 5V analog + 3.3V digital

### 3.6 SPDIF Transmitter

- **IC:** Cirrus Logic CS8406
  - SPDIF/AES3 digital audio transmitter
  - I2C control (address 0x11 as in previous design)
  - Supports 24-bit audio data
- **Output:** Through audio transformer (e.g., S22083) for galvanic isolation
- **Physical layer:** AES3 (AES/EBU) balanced 110Ω — rated for up to 100 m cable runs
- **Crystal oscillator:** Required for master clock generation

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
- **Post-regulation:** Ultra-low-noise LDO
  - LT3042 (0.8 µV RMS noise) or similar (ADM7150)
  - Separate regulators for analog (5V) and digital (3.3V) sections
- **No switching regulators in the analog signal path**
- **Rationale for mains over battery:**
  - 230V AC is efficient over 100m cable (minimal I²R loss)
  - No battery voltage droop or recharge cycles
  - Enables continuous long-term Schumann resonance monitoring

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
    │ bias R   │ filter       │ PCM1808  │ │  LT3042      │
    │ guard    │ LMP7721 out  │ xformer  │ │  LDO         │
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
- Analog input side of PCM1808
- Clean analog, but not femtoampere-sensitive

**Compartment 3 — DIGITAL:**
- CS8406, crystal oscillator, SPDIF transformer
- PCM1808 digital side
- Digital noise quarantined here

### PSU — Separate ALU Enclosure

- **Own enclosure, own PCB** — physically separate from the antenna amplifier
- AC-DC converter (two-bucket or commercial module)
- LT3042 / ADM7150 ultra-low-noise LDOs
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
| ADC dynamic range             | 99 dB (PCM1808)                   |
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
| ADC            | PCM1808            | 24-bit delta-sigma, 96 kSPS       |
| SPDIF TX       | CS8406             | Digital audio transmitter          |
| Audio xformer  | S22083             | Galvanic isolation for AES/EBU    |
| LDO (analog)   | LT3042             | Ultra-low noise, 0.8 µV RMS       |
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
1. Finalise schematic in KiCad (LMP7721 preamp + PCM1808 + CS8406 + PSU)
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
