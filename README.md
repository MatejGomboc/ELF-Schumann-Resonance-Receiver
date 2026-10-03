# ELARA -- ELF Atmospheric Radio Analyser

A professional-grade electric-field receiver for natural ELF radio signals
(1--50 Hz), optimised for Schumann resonance monitoring with exceptional
sensitivity. Inspired by [Renato Romero's](http://www.vlf.it/cumiana/livedata.html)
electric-field receiver work, engineered for dramatically better noise
performance using modern electrometer-grade components.

## Architecture

The system is deliberately simplified: the only custom PCB is the outdoor
antenna unit. The indoor side is entirely off-the-shelf.

- **Marconi T-antenna** (~10 m vertical, ~15 m capacitive top, ~140 pF)
- **Outdoor unit** -- single custom PCB inside a compartmentalised ALU EM shield,
  housed in a weatherproof plastic enclosure
- **Indoor unit** -- any USB audio interface with an AES3 input (or an S/PDIF input
  through a 110 ohm to 75 ohm balun), connected to a PC

Both cables (AES3 digital audio on shielded Cat5e/6 with an RJ45, and the
screened 230 V AC mains cable) use "reverse shielding" --
the shields contain the cables' own emissions to protect the antenna, not the
other way around.

## Signal Chain

| Stage | Component | Key Spec |
| --- | --- | --- |
| Input RF filter | 2-stage RC (air-gap plate caps, 50 pF each) | fc ~96.5 kHz, FM -121 dB, AM -41 dB |
| Electrometer preamp | LMP7721 (40 dB ELF bandpass gain) | 6.5 nV/sqrt(Hz), 0.01 fA/sqrt(Hz) |
| Guard ring driver | LMP7715 | Drives active guard on all PCB layers |
| Antenna bias | LMP7715 (2.5V mid-supply via 47k divider) | Through a 1-100 Gohm glass resistor at J202 (100 Gohm recommended); a shunt there resets the input at start-up |
| Anti-aliasing filter | Passive RC (10k + 100nF, C0G/NP0) | fc = 159 Hz |
| ADC | PCM1804 (24-bit delta-sigma, stereo, 192 kHz) | 112 dB dynamic range |
| Digital output | CS8406 AES3 TX + S22083 transformer + shielded RJ45 | AES3 110 ohm on pins 4/5, galvanically isolated |
| Master clock | 24.576 MHz MEMS oscillator | Feeds both ADC and AES3 TX |
| Power supply | 6.98 V DC from the two-bucket PSU (or a 9-15 V battery) -> ADM7150 LDOs (5V analog + 3.3V digital) | 1.6 uV RMS noise |

## Preamp Topology

Non-inverting amplifier with bandpass gain and DC blocking:

```text
        Cf (15nF, C0G)
    +----||----+
    |  Rf=100k |
VOUT-+--/\/\/--+--IN-  (LMP7721)
                |
              Rg=1k
                |
            Cg=100uF (film, DC block)
                |
               GND
```

- **DC gain: 0 dB** -- Cg blocks DC, no offset amplification
- **ELF gain: 40 dB (100x)** -- flat across all 7 Schumann resonances (1.6--106 Hz)
- **Above 106 Hz: rolls off** -20 dB/dec toward unity (Cf shorts Rf)
- **Output coupling:** C_out (10uF film) blocks 2.5V DC to ADC
- **Max amplification is limited by 50 Hz mains E-field pickup** from nearby power
  lines. The input resistance is the 1-100 Gohm J202 bias resistor, far above the
  antenna's 23 Mohm at 50 Hz, so the antenna picks up 50 Hz with full efficiency.
  The 40 dB gain keeps worst-case 50 Hz within the linear range: 21 mV rms at the
  antenna before clipping (set by the ADC driver's input common-mode range), 12.5 dB
  of headroom over 5 mV of pickup (`simulations/system`). A software notch filter
  removes 50 Hz cleanly.

## Noise Performance

At the 1st Schumann resonance (7.83 Hz) with a 140 pF antenna:

| | ELARA (LMP7721) | Romero LNVA (AD820) |
| --- | --- | --- |
| Noise at the amplifier input | 26.7 nV/sqrt(Hz) (behind the 0.583 cap divider) | ~121 nV/sqrt(Hz) |
| System noise (at antenna) | **45.8 nV/sqrt(Hz)** | ~121 nV/sqrt(Hz) |
| ADC noise floor, referred to the antenna | **0.7 nV/sqrt(Hz)** (41 nV/sqrt(Hz) at the ADC input) | N/A (analog output) |
| FM rejection (100 MHz) | **-121 dB** (ideal RC; strays limit it to about -95 dB) | none |
| AM rejection (1 MHz) | **-41 dB** | none |
| Detection threshold | **0.0070 uV/m/sqrt(Hz)** | 0.0186 uV/m/sqrt(Hz) |
| Improvement | **2.6x voltage, 7x power** | baseline |

The ELARA figures are from the SPICE model (`simulations/spice`). The filter
resistors (2x 33k) dominate the noise budget: 48 % from the one next to the
amplifier and 26 % from the one at the antenna. The LMP7721's own voltage noise
adds 13 %, PCB leakage current 10 % and Rg 2 %. (The first Python budget, 64.6
nV/sqrt(Hz), was 3 dB pessimistic.) The recommended 100 Gohm J202 bias resistor
raises the floor to 74.8 nV/sqrt(Hz) at SR1, still 12.8 dB below the natural ELF
background. Everything after the preamp (driver, ADC, references) adds only
1.6-2.0 nV/sqrt(Hz) at the antenna, so the PCM1804 is transparent.

Expected Schumann resonance SNR (typical daytime conditions, 0.1 Hz bins, J202 =
100 Gohm; `simulations/system`):

| Mode | Frequency | SNR |
| --- | --- | --- |
| SR1 | 7.83 Hz | **38.8 dB** |
| SR2 | 14.3 Hz | **35.6 dB** |
| SR3 | 20.8 Hz | **33.5 dB** |
| SR7 | 45.0 Hz | **23.5 dB** |

## Stereo Noise Reference Channel

The PCM1804 is a stereo ADC. The right channel input (VINR) is tied to the
internal common-mode voltage (VCOMR), providing a **noise reference**. PC software
cross-correlates L and R channels: correlated noise is system noise (PSU, ADC
clock jitter, ground loops), uncorrelated signal on L only is the antenna signal.
This enables real-time coherent noise subtraction.

## No Input Protection -- By Design

There is deliberately no ESD or overvoltage protection on the antenna input. Any
protection component would introduce leakage currents that destroy the
femtoampere-level noise floor. Protection and electrometer-grade sensitivity are
fundamentally incompatible.

**Disconnect the antenna during thunderstorms.**

## Target Specifications

| Parameter | Value |
| --- | --- |
| Frequency range | 1--50 Hz (ELF, Schumann resonances) |
| Preamp gain | 40 dB (100x) flat across ELF band |
| System noise floor @ 7.83 Hz | 45.8 nV/sqrt(Hz) at the antenna (SPICE); 74.8 with the 100 Gohm bias resistor |
| ADC dynamic range | 112 dB (PCM1804) |
| ADC resolution | 24-bit, 192 kHz |
| Digital output | AES3 (110 ohm) on an RJ45 for shielded Cat5e/6 |
| Cable length | Up to 100 m (AES3, transformer-isolated) |
| Power (outdoor unit) | 6.98 V DC (two-bucket PSU) or 9-15 V battery -> ADM7150 LDOs (5V + 3.3V) |
| Guard ring | LMP7715 active guard (83x leakage reduction) |
| FM rejection | -121 dB at 100 MHz (ideal RC; about -95 dB with strays) |
| AM rejection | -41 dB at 1 MHz |

## Repo Structure

```text
PCB/
  antenna_amplifier/   KiCad 9 project -- main outdoor unit (design.py -> schematic, layout.py -> PCB)
  acdc_converter/      KiCad 9 project -- two-bucket isolated PSU (design.py, layout.py)
  plate_capacitor/     64 x 64 mm air-gap capacitor plate (layout.py)
  elara.pretty/        project footprints (PTFE input turret, 4-pin pulse transformer, strip holes)
  */fab/               Gerbers + drill (JLCPCB zip), pick-and-place, BOM, PDFs, 3D render,
                       populated STEP, interactive HTML BOM
simulations/
  preamp_noise/        LMP7721 noise analysis vs AD820/ADA4530-1/OP27
  signal_chain/        Feedback gain analysis, expected Schumann signal levels
  input_filter/        Filter R optimisation, RC cascade Bode plot
  antenna/             Antenna capacitance & signal loss tradeoff
  plate_capacitor/     Air-gap capacitor geometry calculator
  spice/               ngspice front-end AC/noise model, antenna bias resistor trade-off
  psu/                 Two-bucket PSU: dropout, swap artefacts, cold start, 50 Hz leakage
  stability/           Phase margin of every op-amp stage
  system/              End-to-end noise, headroom and Schumann SNR budget
software/elara/        PC software: capture, decimation, mains canceller, Schumann fit
mechanical/            CadQuery shield, PSU box, plate-cap assembly, outer box (STEP/DXF)
bom/                   Priced BOM (build_bom.py) and cost-down options
tools/
  kicadgen/            KiCad 9 schematic/PCB generators, netlist check, Freerouting driver
  fab_outputs.sh       Fabrication package per board
  ibom.py              Interactive HTML BOM (InteractiveHtmlBom, headless)
  kicad_wirer.py       Legacy schematic pin tool (superseded by kicadgen)
FW/                    Firmware (empty, no MCU in current design)
images/                Matplotlib-generated SVG diagrams
```

## Project Status

Revision 0.2 on the `claude/cloud-work` branch is ready for fabrication. It has:

- generated schematics, netlist-checked and ERC clean
- all three boards routed, with 0 DRC errors and 0 unconnected items, and fab packages
- simulations, mechanics with a clash check, PC software and a priced BOM

What remains to check before ordering is listed in [STATUS.md](STATUS.md).
[ASSEMBLY.md](ASSEMBLY.md) covers hand assembly and bring-up of the boards,
[MOUNTING.md](MOUNTING.md) the mechanical build, site and earthing, and
[MAINS_CABLE.md](MAINS_CABLE.md) the shielded mains feed. Ordering is in
[bom/ORDERING.md](bom/ORDERING.md) (Farnell, Mouser and Digi-Key upload files), and
local mechanical suppliers in [mechanical/SUPPLIERS_SI.md](mechanical/SUPPLIERS_SI.md).
[PLAN.md](PLAN.md) section 0 lists the rev 0.2 design changes.

## Toolchain

| Tool | Purpose |
| --- | --- |
| KiCad 9.0 | Schematic, PCB layout, component libraries |
| Python + numpy/scipy/matplotlib | Noise modelling, signal analysis, simulations |
| CadQuery (Python) | 3D models (STEP) for components and enclosure |
| tools/kicadgen | Generated schematics and boards, netlist check, Freerouting 1.9 driver |
| Freerouting 1.9 | Autorouter (batch mode, needs an X display, e.g. Xvfb) |

## Licence

This project is licensed under the **CERN Open Hardware Licence v2 -- Weakly
Reciprocal (CERN-OHL-W-2.0)**.

See [LICENCE](./LICENCE) for full terms.

Copyright 2025-2026 [MatejGomboc](https://github.com/MatejGomboc/ELF-Schumann-Resonance-Receiver)
