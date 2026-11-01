# CLAUDE.md

## Project

ELARA -- ELF Atmospheric Radio Analyser. See README.md for overview,
PLAN.md for full engineering design document.

## Repo structure

```text
PCB/
  antenna_amplifier/   main outdoor unit PCB: design.py (schematic), layout.py (board), fab/
  acdc_converter/      two-bucket PSU PCB: design.py, layout.py, fab/
  plate_capacitor/     air-gap input capacitor plates: layout.py, fab/
  elara.pretty, elara.3dshapes   project footprints / 3D models
simulations/
  spice/               front end in ngspice (noise, AC, bias resistor)
  psu/                 two-bucket PSU transient suite (ngspice) + PSRR/leakage
  stability/           guard and preamp loop margins
  system/              whole-chain noise and headroom budget
  em/                  plate capacitor field solve, shielding, coupling (FD solver)
  thermal/             boards, outdoor box over 24 h, front-end temperature
  mechanics/           board / plate modes, microphonics, wind
  preamp_noise/ signal_chain/ input_filter/ antenna/ plate_capacitor/   early Python studies
tools/
  kicadgen/            schematic + board generator, router driver, checks
  check_all.sh         every design check (CI runs it too)
  setup_env.sh         toolchain for a fresh Ubuntu 24.04 (reads requirements.txt)
  pin_audit.py, branch_docs.py, mains_clearance.py, fab_outputs.sh, route_psu.sh, ...
datasheets/ds2sf/      datasheet pin extractions for pin_audit.py
bom/                   priced BOM, order lists
software/              PC capture / analysis package (elara), pytest suite
mechanical/            CadQuery STEP models, DXF, renders, fit check
images/                matplotlib SVG diagrams for README / PLAN
.claude/skills/        project skills (design flow, pin audit, docs sync, env, upkeep)
.github/workflows/     CI checks and release packaging
brainstorming/         early design exploration (git-ignored, historical)
```

## Design authority

PLAN.md is the single source of truth for the current design. Key components:
LMP7721, LMP7715, OPA388, PCM1804, CS8406, ADM7150, TPS3808G01, 24.576 MHz MEMS oscillator.

## Current design parameters

- Preamp gain: 40 dB (Rf=100k, Cf=15nF, Rg=1k, Cg=100uF film returned to GND)
- Input filter: R=33k, C=50pF air-gap (fc=96.5 kHz); plates 49.9 mm copper (50.2 pF incl. fringing)
- Plate return: lower plates on PLATE_RET (BIAS_BUF -> 100k -> 10u film + 100n C0G, J203), not GND:
  no DC across the air gaps (microphonics); earthing of the receiver is mandatory
- ADC: PCM1804, 192 kHz, 112 dB DR, 5 Vpp differential
- AA filter: R=10k, C=100nF (fc=159 Hz)
- Cap divider loss: -4.7 dB (C_ant=140pF, C_filt=100pF total)
- Noise at antenna: 45.8 nV/sqrtHz at SR1 (SPICE, simulations/spice/; old Python budget 64.6)
- Guard buffer senses IN- (LMP7715 U202, bias buffer U203); OPA388 ADC driver (U301,
  rail-to-rail input) + 100R/2.7nF C0G at VINL+; 50 Hz clip 29.5 mV rms at the antenna
- Brown-out reset: TPS3808G01 watches +5VA (R306 100k / R307 9.53k: 4.66 V trip, 300 ms),
  SW301 RESET button on its MR
- Input TVS SMAJ13A (input 6.98-13 V); ADM7150 VIN/VREG/VOUT 22 uF X7R 1210
- J202: 1-100 G glass bias resistor soldered straight into the holes, no header (floating
  input drifts with the air-earth current); reset = a clip lead across the pads
- Current budget ~100 mA at J101
- Outdoor box on a stiff 114.3 x 6.3 mm steel post (<= 1 m) in a field at the foot of the
  down-lead; white 2 mm Al shade roof 500 x 500 centred, 30 mm above the box on two arms
  clamped to the post (never on the box), earthed, grommet for the antenna lead
  (mechanical/params.py SHADE_ROOF): EDLC <= 63.7 C on a record 40 C day, door N or S
- PSU: two-bucket supercap isolation, SS34 in each bucket negative leg, 0.4 A load-path
  limiter, LT3045 (ILIM ~0.3 A), charger CV 10.76 V (PCB/acdc_converter/design.py); or a
  battery up to 13 V
- PSU protection: EDLC overvoltage crowbar on CHG (U6 TL431B, R29 36.5k / R30 10k 0.1 %,
  Q5 MMBT3906, Q6 MCR100-6 SCR) trips at 11.7 V and latches until mains is removed;
  GDT1 Bourns 2051-15-SM 150 V between GND_C (PE) and the receiver GND across the pour
  gap. LM317 tabs on their copper areas, NOT bolted to the base. PSU 103 components
- Box heater (mains side only, never on the receiver supply; none on a battery): STEGO
  HG 140 30 W + KTO 111 NC thermostat at +5 C on a DIN rail on the PSU box lid, T 4 A
  fuse terminal. PCM1804 >= -7.7 C down to -25 C outside under the shade roof (simulations/thermal)

## Python

Always use the project's `.venv` in the repo root: `.venv/Scripts/python` (Windows),
`.venv/bin/python` (Linux / cloud sessions). Keep matplotlib at 3.10.8 so regenerated
plots match the committed SVGs. Every plotting script loads the repo-root `matplotlibrc`
(DejaVu fonts, fixed SVG salt) and sets SOURCE_DATE_EPOCH, so a re-run is byte-identical
on any machine; new plotting scripts must do the same (copy the block from run_psu.py).

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

`kicad-cli` / `kicad-py` come from the native KiCad 9 install (official PPA) that
`tools/setup_env.sh` sets up; `kicad-py` is a shim to `/usr/bin/python3.12`, which has
`pcbnew`. On a desktop run the same scripts with KiCad 9's own python.
The symbol loader needs `KICAD9_SYMBOL_DIR` pointing at KiCad's stock `symbols/` folder.
See STATUS.md for the current state and next steps.

Board flow notes:
- Amplifier: `route.py <dsn> <ses> --power "+9V,+5VA,+3V3,+5V_PRE,VIN_RAW" --passes 40`
  (Freerouting 1.9, needs `DISPLAY`, e.g. Xvfb :99). GND fan-out vias are placed before
  routing and GND stays in the router's copy.
- PSU: `sh tools/route_psu.sh` (place, Freerouting, finish). The charger and receiver
  copper keep 1 mm apart: a custom KiCad rule (`layout.py`, checked by DRC) that the
  script also hands to Freerouting as class-to-class clearances (`route.py --barrier`).
  `finish` rebuilds the placement itself, so it can be re-run on its own (SES reused).
- Fab limits: `tools/kicadgen/fabrules.py` writes JLCPCB's standard-process limits into every
  board's project file and `.kicad_dru` on each save; `Board.silk_for_fab()` widens footprint
  silk to 0.15 mm and cuts it 0.15 mm clear of the pads. Footprints therefore differ from the
  library on purpose ("footprint differs from library" is set to ignore).
- Placement: parts in aligned rows/columns on a 0.5 mm grid, IC capacitors in cells
  (`row()`, `ldo_cell()` in the amplifier `layout.py`); `tidy_refs()` puts every reference
  in line with its row. Check a placement before routing with
  `kicad-cli pcb export svg` (F.Fab, F.Courtyard, F.Silkscreen) rendered at ~20 px/mm.
- CI (`.github/workflows/checks.yml`) runs `setup_env.sh` + `check_all.sh` on every push, then
  fails if a generated sheet, netlist or BOM file was committed stale; a `v*` tag publishes
  the fab package (`release.yml`).
- All checks in one go: `sh tools/check_all.sh` (netlists, ERC, schcheck, DRC with parity,
  mains clearances, fit check and `params.check()`, pin audit, branch model in the docs
  (`tools/branch_docs.py`), software tests).
- `.ses` files are committed (the router's output). `finish` reuses the SES as long as the
  placement is unchanged (silkscreen, pours and title blocks do not need a re-route).
- Silkscreen carries `REV ${REVISION}  ${GIT_HASH}`: REVISION from the title block,
  GIT_HASH set by `fab_outputs.sh` at export (commit, `+` if the tree was dirty). Export
  fab outputs from a clean tree (commit the board first); a `v*` tag re-exports them in CI.
- Silkscreen is automatic: `text_free()` puts labels on the nearest free spot and
  `tidy_refs()` moves or hides references (fitted parts get priority over DNP ones).
- Fab package: `sh tools/fab_outputs.sh PCB/<board>/<board>.kicad_pcb` (Gerbers, drill,
  pos, BOM, PDFs, render, STEP; interactive BOM if `IBOM_PKG` points at an unpacked
  InteractiveHtmlBom, see `tools/ibom.py`).
- Priced BOM: `.venv/bin/python bom/build_bom.py`, then `.venv/bin/python bom/order_lists.py`
  (distributor upload files in `bom/order/`). The totals in `bom/README.md` are copied by
  hand from its output.
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

## Skills

Project skills in `.claude/skills/` (load on demand): `elara-design-flow`,
`elara-pin-audit`, `elara-docs-sync`, `elara-env-setup`, `elara-site-survey`, `elara-skill-upkeep`.
Refine them whenever a session finds a new trap or a stale command (changelog in each).
**At the end of every working session with Matej, run `elara-skill-upkeep`** on what the
session touched (no scheduled runs: refinement follows real work).
Datasheet pin checks: `tools/pin_audit.py` with Adom DS2SF extractions in
`datasheets/ds2sf/` (other AI EDA tools: https://wiki.adom.inc/apps).

## Running simulations

```bash
.venv/bin/python simulations/spice/run_spice.py       # front end (ngspice)
# ORDER MATTERS: system/ and signal_chain/expected_signal.py read spice/results.json,
# so after a SPICE change re-run them too (CI fails on stale outputs)
.venv/bin/python simulations/psu/run_psu.py           # PSU transient suite, ~20 s on 4 cores
.venv/bin/python simulations/stability/run_stability.py
.venv/bin/python simulations/system/run_system.py
.venv/bin/python simulations/em/run_em.py             # ~70-95 s
.venv/bin/python simulations/thermal/run_thermal.py   # ~25 s
.venv/bin/python simulations/mechanics/run_mechanics.py
for f in simulations/{preamp_noise,signal_chain,input_filter,antenna,plate_capacitor}/*.py; do
    .venv/bin/python "$f"; done                        # early studies
```

## KiCad format rules (from the hand-edited rev 0.1 sheets; kicadgen handles them now)

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

`master` is the working branch. The design grew on `claude/cloud-work` out of
`ai-augmented-design`; Matej had both merged into `master` on 2026-11-01 (the
original 2021 VLF design master held before is in its history and on `v2`). Work on
`master` or a short-lived branch merged back into it. `tools/branch_docs.py` (in
`check_all.sh`, so in CI) checks that STATUS / README / PLAN / this file / the
env-setup skill all name the same working branch, and fails anything going into
master while they name a side branch.
