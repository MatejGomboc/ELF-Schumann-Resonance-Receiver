# ELARA -- work status (branch `claude/cloud-work`)

Paused checkpoint. Everything below is committed on this branch.

## Done
- **Antenna amplifier schematic** rebuilt from `PCB/antenna_amplifier/design.py`
  (generator in `tools/kicadgen/`). KiCad's netlist export is checked against the
  design on every run: exact match, ERC clean (one harmless CS8406 COPY/C warning).
  Changes vs. the old sheet: Cg returns to GND, guard buffer senses IN-, LMP7715 ADC
  driver, all mode pins on DIP switches, full LDO support, no power LED.
- **Two-bucket PSU schematic** (`PCB/acdc_converter/design.py`): IRM-05-15 -> CC/CV
  supercap charger -> two 4 x 10 F buckets swapped by G6K-2 relays every ~30 s ->
  LT3045 -> common-mode choke. ERC clean, netlist check passes.
- **SPICE front-end model** (`simulations/spice/`): 45.8 nV/rtHz at the antenna at SR1;
  the floating input needs a G-ohm bias resistor on J202 (atmospheric ion current).
- **PC software** (`software/elara/`, 27 tests pass).
- **Mechanics** (`mechanical/`, CadQuery -> STEP/DXF/renders, clash-free assembly).
- **Amplifier PCB placement** (`PCB/antenna_amplifier/layout.py place`): 200 x 100 mm,
  4 layers, 3 compartments, wall strips, guarded input island. Not yet routed.

## Next steps
1. Route the amplifier: `kicad-py PCB/antenna_amplifier/layout.py place`, then
   `.venv/bin/python tools/kicadgen/route.py PCB/antenna_amplifier/antenna_amplifier.dsn
   PCB/antenna_amplifier/antenna_amplifier.ses --power +9V,+5VA,+3V3,+5V_PRE,VIN_RAW`
   (Freerouting; slow, run in the background), then write the `finish` stage: import
   the SES, delete the `ko *` rule areas, GND pours on F/B/In2, strip copper and
   stitching vias, fill zones, DRC.
2. PSU layout: `PCB/acdc_converter/layout.py` holds a first placement table (not yet run).
3. Plate-capacitor PCB: copper relief R4.8 at the corner holes, bare landing rings under
   the PTFE washers, 53.8 mm square for 50 pF on bare copper (see `mechanical/README.md`).
4. Re-run the PSU / stability / system simulations (that agent was stopped mid-way).
5. BOM with prices (Farnell / Mouser / Digi-Key / JLCPCB), target under 300 EUR.
6. Verify the Newava S22082/S22083 pinout against the DIP-6 footprint.
7. Mechanics notes: do not anodise (contact faces must conduct); the BNC needs a
   barrel projecting >= 13 mm through the 7 mm wall, or treat it as a bench-only port.

## Environment notes (cloud container)
KiCad 9 runs from the `kicad/kicad:9.0-full` Docker image (`kicad-cli`, `kicad-py`
wrappers around `docker run`); Freerouting 2.1.0 jar; ngspice 42; the `.venv` pins
matplotlib 3.10.8 so regenerated plots match the committed ones.
