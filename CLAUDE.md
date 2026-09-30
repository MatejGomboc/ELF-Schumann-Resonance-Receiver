# CLAUDE.md

## Project

ELARA -- ELF Atmospheric Radio Analyser. See README.md for overview,
PLAN.md for full engineering design document.

## Repo structure

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

## Design authority

PLAN.md is the single source of truth for the current design. Key components:
LMP7721, LMP7715, PCM1804, CS8406, ADM7150, 24.576 MHz MEMS oscillator.

## Current design parameters

- Preamp gain: 40 dB (Rf=100k, Cf=15nF, Rg=1k, Cg=100uF film returned to GND)
- Input filter: R=33k, C=50pF air-gap (fc=96.5 kHz)
- ADC: PCM1804, 192 kHz, 112 dB DR, 5 Vpp differential
- AA filter: R=10k, C=100nF (fc=159 Hz)
- Cap divider loss: -4.7 dB (C_ant=140pF, C_filt=100pF total)
- Noise at antenna: 45.8 nV/sqrtHz at SR1 (SPICE, simulations/spice/; old Python budget 64.6)
- Guard buffer senses IN-; LMP7715 ADC driver + 100R/2.7nF C0G at VINL+
- J202: 1-100 G glass bias resistor (floating input drifts with the air-earth current)
- PSU: two-bucket supercap isolation + LT3045 (PCB/acdc_converter/design.py); or 9-15 V battery

## Python

Always use the project's `.venv` in the repo root: `.venv/Scripts/python` (Windows),
`.venv/bin/python` (Linux / cloud sessions). Keep matplotlib at 3.10.8 so regenerated
plots match the committed SVGs.

## Generated design files (rev 0.2)

Schematics and boards are GENERATED -- edit the scripts, never the sheets/boards by hand:

```bash
.venv/bin/python PCB/antenna_amplifier/design.py   # schematic + netlist check (must match)
.venv/bin/python PCB/acdc_converter/design.py
kicad-py PCB/antenna_amplifier/layout.py place     # footprints, strips, guard island, DSN
.venv/bin/python tools/kicadgen/route.py <dsn> <ses> --power ...   # Freerouting
kicad-py PCB/antenna_amplifier/layout.py finish    # import SES, pours, stitching
kicad-py PCB/plate_capacitor/layout.py
```

`kicad-cli` / `kicad-py` are wrappers around the `kicad/kicad:9.0-full` Docker image in
cloud sessions; on a desktop run the same scripts with KiCad 9's own python.
The symbol loader needs `KICAD9_SYMBOL_DIR` pointing at KiCad's stock `symbols/` folder.
See STATUS.md for the current state and next steps.

## Running simulations

```bash
# Run all 8 simulations
for f in simulations/preamp_noise/*.py simulations/signal_chain/*.py \
         simulations/input_filter/*.py simulations/antenna/*.py \
         simulations/plate_capacitor/*.py; do
    .venv/Scripts/python "$f"
done

# Check schematic connectivity
.venv/Scripts/python tools/kicad_wirer.py PCB/antenna_amplifier/antenna_amplifier.kicad_sch --connectivity

# Show specific component pin positions
.venv/Scripts/python tools/kicad_wirer.py PCB/antenna_amplifier/antenna_amplifier.kicad_sch -c U3
```

## KiCad format rules (discovered during development)

- Sub-symbols in lib_symbols: NO library prefix (e.g., `R_0_1` not `Device:R_0_1`)
- Wire connectivity requires shared endpoints -- no T-junction auto-detect from file
- Segmented vertical bus wires needed for multi-pin power connections
- All coordinates on 1.27mm (50 mil) grid

## Conventions

- KiCad 9.0 S-expression format
- All 3D models via CadQuery Python scripts exporting STEP
- Simulation: Python (numpy/scipy/matplotlib)
- Licence: CERN-OHL-W-2.0
- Signal path capacitors: C0G/NP0 only, resistors: thin-film only
- PCB substrate: PTFE/Rogers preferred, FR4 fallback

## Branch model

`ai-augmented-design` is the working branch. Do NOT merge into master unless
Matej explicitly says so.
