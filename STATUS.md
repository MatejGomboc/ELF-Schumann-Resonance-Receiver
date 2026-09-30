# ELARA -- work status (branch `claude/cloud-work`)

Revision 0.2 of the design, generated from Python sources. Everything below is
committed on this branch; `master` and `ai-augmented-design` are untouched.

## Done
- **Antenna amplifier schematic** (`PCB/antenna_amplifier/design.py`, generator in
  `tools/kicadgen/`). KiCad's netlist export is checked against the design on every
  run: exact match, ERC clean (one harmless CS8406 COPY/C warning). Changes vs. the
  old sheet: Cg returns to GND, guard buffer senses IN-, 220 pF C0G GUARD-GND for
  phase margin, J202 1-100 G-ohm bias resistor, LMP7715 ADC driver, mode pins on DIP
  switches, full LDO support, no power LED.
- **Two-bucket PSU** (`PCB/acdc_converter/`): IRM-05-15 -> LM317 CC 0.2 A / CV 10.9 V
  -> two 4 x 10 F EDLC buckets swapped every ~15 s by G6K-2 relays in opposite sense
  (break before make) -> 2200 uF -> LT3045 6.98 V -> common-mode choke. ERC clean,
  routed, DRC fully clean (0 errors, 0 warnings); fab outputs in `fab/`.
- **Air-gap plate capacitor PCB** (`PCB/plate_capacitor/`): 64 x 64 mm, ~49 pF bare at
  0.5 mm; DRC clean; fab outputs in `fab/`.
- **Simulations**: SPICE front end (`simulations/spice/`), PSU ripple/swap transient,
  guard-loop stability, system noise budget (`simulations/psu|stability|system/`).
  The fixes they found are applied to the schematics (see PLAN.md section 0).
- **BOM** (`bom/`): priced from Farnell / Mouser / Digi-Key / JLCPCB. About 518 EUR ex
  VAT as designed, about 408 EUR with the listed cost-downs; 300 EUR is not reachable
  without giving up noise performance (PTFE board, LMP7721, LT3045, EDLCs dominate).
- **PC software** (`software/elara/`, 27 tests pass).
- **Mechanics** (`mechanical/`, CadQuery -> STEP/DXF/renders, clash-free assembly).
- **Amplifier PCB** (`PCB/antenna_amplifier/layout.py place|finish`): 200 x 100 mm,
  4 layers, 3 compartments with 7 mm exposed wall strips, guarded input island,
  GND fan-out to the In1 plane before routing, Freerouting 1.9, pours + stitching.
  Fully routed: 0 DRC errors, 0 unconnected. The remaining warnings are intended:
  mask bridges and clipped footprint silk at the deliberate mask openings (bare
  guard island, exposed wall strips). Fab outputs are in `fab/`.
- **Silkscreen**: board labels go to the nearest free spot, and references move
  clear of pads, silk and mask openings. Where no spot is free, a reference is
  hidden and stays on the F.Fab assembly drawing.
- **Assembly and bring-up guide**: `ASSEMBLY.md` covers the soldering order,
  cleaning the femtoamp island, DIP-switch defaults and the expected voltages.

## Before ordering -- open checks
1. Oscillator: confirm the SiT2001B SOT23-5 pinout (1 GND, 2 NC, 3 OE, 4 VDD, 5 OUT),
   which comes from datasheet summaries (the datasheet site was blocked here). Y401
   (SiT1602, no-lead) is a do-not-fit alternative on the same nets.
2. Confirm ordering codes: Bourns SRF1260 suffix, and WIMA MKS4 code and body size
   (50 mm tall under the 52 mm amplifier walls). Newava S22083: the body (12.7 x 8.89
   x 6.35 mm, 4-pin THT, per distributor data) matches the footprint outline, and
   the slotted pads take 5.08-10.16 mm row spacing. Only the winding pin numbering
   (1-2 / 3-4) still needs the datasheet.
3. LMP7715 (U301) input common-mode ceiling: V+ - 1 V = 4.0 V (typical, TI). The
   system budget (`simulations/system/`) already clips there and still has 12.5 dB
   of 50 Hz headroom over 5 mV of pickup; confirm the guaranteed (min) figure.
4. Relay endurance: a 15 s swap is ~2 M operations a year per relay; G6K-2 is rated
   for 100 M mechanical but check the low-level contact rating, or slow the swap.
5. Earth the receiver GND locally at the mast; J202 100 G-ohm bias + insulated antenna.
6. BNC needs a barrel projecting >= 13 mm through the 7 mm wall, or treat it as a
   bench-only port. Do not anodise the enclosure (contact faces must conduct).

Resolved this session: the EDLC cells (HV1030, 10 x 30 mm) now stand upright in
the PSU box, whose walls are 50 x 6 mm bar.

## Environment notes (cloud container)
KiCad 9 runs from the `kicad/kicad:9.0-full` Docker image (`kicad-cli`, `kicad-py`
wrappers around `docker run`); Freerouting 1.9 (batch mode, needs an X display, Xvfb
:99); ngspice 42; the `.venv` pins matplotlib 3.10.8 so regenerated plots match.
