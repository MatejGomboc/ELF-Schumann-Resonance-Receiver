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

Board flow notes:
- Amplifier: `route.py <dsn> <ses> --power "+9V,+5VA,+3V3,+5V_PRE,VIN_RAW" --passes 40`
  (Freerouting 1.9, needs `DISPLAY`, e.g. Xvfb :99). GND fan-out vias are placed before
  routing and GND stays in the router's copy.
- PSU: `kicad-py PCB/acdc_converter/layout.py place`, route, then `finish`.
- `.ses` files are git-ignored. `finish` can reuse an existing SES as long as the placement
  is unchanged (silkscreen, pours and title blocks do not need a re-route).
- Silkscreen is automatic: `text_free()` puts labels on the nearest free spot and
  `tidy_refs()` moves or hides references (fitted parts get priority over DNP ones).
- Fab package: `sh tools/fab_outputs.sh PCB/<board>/<board>.kicad_pcb` (Gerbers, drill,
  pos, BOM, PDFs, render, STEP; interactive BOM if `IBOM_PKG` points at an unpacked
  InteractiveHtmlBom, see `tools/ibom.py`).
- Priced BOM: `.venv/bin/python bom/build_bom.py`. The totals in `bom/README.md` are
  copied by hand from its output.
- Schematic legibility: `.venv/bin/python tools/kicadgen/schcheck.py <root .kicad_sch>`
  checks KiCad's own SVG rendering for text over text, lines through text and text
  outside the frame. Keep it at 0 (fix with `Sheet.join`, `fields_at=`, `stubs=`).
- Footprint variants (no silk on the guard island, mains terminal with 2.3 mm pads):
  `tools/fp_variants.py`.
- 3D models for parts KiCad has none for (or a wrong-size one): `.venv/bin/python
  tools/models3d.py` -> `PCB/elara.3dshapes/`; kicadgen swaps them in by footprint name
  or MPN (`tools/kicadgen/models.py`). A model change does not trip the library check.
- PSU mains gaps: `kicad-py tools/mains_clearance.py PCB/acdc_converter/acdc_converter.kicad_pcb`
  (>= 2.5 mm L-N and to PE, >= 6.4 mm to everything else).
- Mechanics: run `tools/fab_outputs.sh` on the boards first (it writes the STEP files
  with the board corner as origin), then `.venv/bin/python mechanical/build_all.py`,
  which ends with `fit_check.py` (real boards in the shield and the PSU box) and the
  outdoor-box clash check. Exported assembly STEPs use part envelopes to stay small.

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
