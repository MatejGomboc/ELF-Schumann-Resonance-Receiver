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
- **Indoor unit** -- any USB audio card with SPDIF input, connected to a PC

Both cables (AES/EBU digital audio + 230 V AC mains) use "reverse shielding" --
the shields contain the cables' own emissions to protect the antenna, not the
other way around.

## Signal Chain

| Stage | Component | Key Spec |
| --- | --- | --- |
| Input RF filter | 2-stage RC (air-gap plate caps, 50 pF each) | fc ~96.5 kHz, FM -121 dB, AM -41 dB |
| Electrometer preamp | LMP7721 (40 dB ELF bandpass gain) | 6.5 nV/sqrt(Hz), 0.01 fA/sqrt(Hz) |
| Guard ring driver | LMP7715 | Drives active guard on all PCB layers |
| Antenna bias | LMP7715 (2.5V mid-supply via 47k divider) | Jumper-isolated for zero leakage |
| Anti-aliasing filter | Passive RC (10k + 100nF, C0G/NP0) | fc = 159 Hz |
| ADC | PCM1804 (24-bit delta-sigma, stereo, 192 kHz) | 112 dB dynamic range |
| Digital output | CS8406 SPDIF TX + S22082/S22083 transformers | AES/EBU 110 ohm + S/PDIF coax 75 ohm |
| Master clock | 24.576 MHz MEMS oscillator | Feeds both ADC and SPDIF TX |
| Power supply | 9V DC -> ADM7150 LDOs (5V analog + 3.3V digital) | 1.6 uV RMS noise |

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
             BIAS_MID (2.5V from antenna bias)
```

- **DC gain: 0 dB** -- Cg blocks DC, no offset amplification
- **ELF gain: 40 dB (100x)** -- flat across all 7 Schumann resonances (1.6--106 Hz)
- **Above 106 Hz: rolls off** -20 dB/dec toward unity (Cf shorts Rf)
- **Output coupling:** C_out (10uF film) blocks 2.5V DC to ADC
- **Max amplification is limited by 50 Hz mains E-field pickup** from nearby power
  lines. With 1 Tohm input impedance, the antenna picks up 50 Hz with full
  efficiency. The 40 dB gain keeps worst-case 50 Hz within the ADC's linear range
  (25 mV max input before clipping, 73 dB headroom). Software notch filter
  removes 50 Hz cleanly.

## Noise Performance

At the 1st Schumann resonance (7.83 Hz) with a 140 pF antenna:

| | ELARA (LMP7721) | Romero LNVA (AD820) |
| --- | --- | --- |
| Amplifier input-referred noise | ~17.6 nV/sqrt(Hz) | ~121 nV/sqrt(Hz) |
| System noise (at antenna) | **64.6 nV/sqrt(Hz)** | ~121 nV/sqrt(Hz) |
| ADC noise floor | **16.1 nV/sqrt(Hz)** | N/A (analog output) |
| FM rejection (100 MHz) | **-121 dB** | none |
| AM rejection (1 MHz) | **-41 dB** | none |
| Detection threshold | **0.0099 uV/m/sqrt(Hz)** | 0.0186 uV/m/sqrt(Hz) |
| Improvement | **1.9x voltage, 3.5x power** | baseline |

The filter resistors (2x 33k) dominate the noise budget at 77%. The LMP7721
and feedback components contribute less than 3%. The PCM1804 ADC is transparent
-- its noise floor is below the preamp's, which is the ideal situation.

Expected Schumann resonance SNR (typical daytime conditions, in resonance BW):

| Mode | Frequency | SNR |
| --- | --- | --- |
| SR1 | 7.83 Hz | **40 dB** |
| SR2 | 14.1 Hz | **34 dB** |
| SR3 | 20.3 Hz | **31 dB** |
| SR7 | 44.0 Hz | **20 dB** |

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
| System noise floor @ 7.83 Hz | ~64.6 nV/sqrt(Hz) at antenna |
| ADC dynamic range | 112 dB (PCM1804) |
| ADC resolution | 24-bit, 192 kHz |
| Digital output | AES/EBU (110 ohm STP) + S/PDIF coax (75 ohm RCA) |
| Cable length | Up to 100 m (AES/EBU, transformer-isolated) |
| Power (outdoor unit) | 9V DC -> ADM7150 LDOs (5V + 3.3V) |
| Guard ring | LMP7715 active guard (83x leakage reduction) |
| FM rejection | -121 dB at 100 MHz |
| AM rejection | -41 dB at 1 MHz |

## Repo Structure

```text
PCB/
  antenna_amplifier/   KiCad 9.0 project -- main outdoor unit PCB
  acdc_converter/      KiCad 9.0 project -- separate PSU PCB
simulations/
  preamp_noise/        LMP7721 noise analysis vs AD820/ADA4530-1/OP27
  signal_chain/        Feedback gain analysis, expected Schumann signal levels
  input_filter/        Filter R optimisation, RC cascade Bode plot
  antenna/             Antenna capacitance & signal loss tradeoff
  plate_capacitor/     Air-gap capacitor geometry calculator
tools/
  kicad_wirer.py       Schematic pin position calculator & connectivity checker
FW/                    Firmware (empty, no MCU in current design)
mechanical/            CadQuery STEP models, enclosure design
images/                Matplotlib-generated SVG diagrams
brainstorming/         Early design exploration (historical)
```

## Project Status

Active design on the `ai-augmented-design` branch. See [PLAN.md](PLAN.md) for
the full engineering design document.

## Toolchain

| Tool | Purpose |
| --- | --- |
| KiCad 9.0 | Schematic, PCB layout, component libraries |
| Python + numpy/scipy/matplotlib | Noise modelling, signal analysis, simulations |
| CadQuery (Python) | 3D models (STEP) for components and enclosure |
| kicad_wirer.py | Schematic auto-wiring and connectivity analysis |

## Licence

This project is licensed under the **CERN Open Hardware Licence v2 -- Weakly
Reciprocal (CERN-OHL-W-2.0)**.

See [LICENCE](./LICENCE) for full terms.

Copyright 2025-2026 [MatejGomboc](https://github.com/MatejGomboc/ELF-Schumann-Resonance-Receiver)
