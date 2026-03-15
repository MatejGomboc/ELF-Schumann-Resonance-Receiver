# CLAUDE.md

## Project

ELARA — ELF/VLF Atmospheric Radio Analyser. See README.md for overview,
PLAN.md for full engineering design document.

## Repo structure

```text
PCB/
  antenna_amplifier/   KiCad 9.0 project — main outdoor unit PCB
  acdc_converter/      KiCad 9.0 project — separate PSU PCB
FW/                    Firmware (empty, no MCU in current design)
simulations/           ngspice and Python simulation files
mechanical/            CadQuery STEP models, enclosure design
images/                Matplotlib-generated diagrams (generate_diagrams.py)
```

## Design authority

PLAN.md is the single source of truth for the current design. Key components:
LMP7721, LMP7715, PCM1808, CS8406, LT3042.

## Conventions

- KiCad 9.0 S-expression format
- All 3D models via CadQuery Python scripts exporting STEP
- Simulation: ngspice (.cir) and Python (numpy/scipy)
- Licence: CERN-OHL-W-2.0
- Signal path capacitors: C0G/NP0 only, resistors: thin-film only
- PCB substrate: PTFE/Rogers preferred, FR4 fallback

## Branch model

`ai-augmented-design` is the working branch. Do NOT merge into master unless
Matej explicitly says so.
