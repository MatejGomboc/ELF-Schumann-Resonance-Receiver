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
  routed, DRC fully clean (0 errors, 0 warnings), mains clearances checked by
  `tools/mains_clearance.py`; fab outputs in `fab/`.
- **Air-gap plate capacitor PCB** (`PCB/plate_capacitor/`): 64 x 64 mm plus two solder
  tongues, ~49 pF bare at 0.5 mm; DRC clean; fab outputs in `fab/`.
- **Simulations**: SPICE front end (`simulations/spice/`), PSU ripple/swap transient,
  guard-loop stability, system noise budget (`simulations/psu|stability|system/`).
  The fixes they found are applied to the schematics (see PLAN.md section 0).
- **BOM** (`bom/`): priced from Farnell / Mouser / Digi-Key / JLCPCB. About 516 EUR ex
  VAT as designed, about 411 EUR with the listed cost-downs; 300 EUR is not reachable
  without giving up noise performance (PTFE board, LMP7721, LT3045, EDLCs dominate).
- **PC software** (`software/elara/`, 27 tests pass).
- **Mechanics** (`mechanical/`, CadQuery -> STEP/DXF/renders). The real boards are
  imported from KiCad and fit-checked inside the shield and the PSU box
  (`fit_check.py`), and the units, glands and cables in the outdoor box: no clashes.
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
- **Mounting and site guide**: `MOUNTING.md` covers the shield, PSU box, plate
  capacitors, outdoor box, antenna, local earth, lightning and commissioning.
- **Mains feed**: `MAINS_CABLE.md` covers the screened cable, the building end
  (RCD, screen bonded to PE there only) and preparing the PSU end.
- **Ordering**: `bom/order_lists.py` writes Digi-Key, Mouser and Farnell upload
  files (the same 85 lines each) to `bom/order/`; see `bom/ORDERING.md`. Local
  mechanical suppliers in eastern Slovenia are in `mechanical/SUPPLIERS_SI.md`
  (from web research: confirm before relying on them).

## Before ordering -- open checks
1. Newava S22083 (TR401/TR402): the body (12.7 x 8.89 x 6.35 mm, 4-pin THT) matches
   the footprint, and its slotted pads take 5.08-10.16 mm row spacing. The pin pitch
   and the winding numbering (1-2 / 3-4) still need the datasheet.
2. LMP7715 (U301) input common-mode ceiling: V+ - 1 V = 4.0 V (typical, TI). The
   system budget (`simulations/system/`) already clips there and still has 12.5 dB
   of 50 Hz headroom over 5 mV of pickup; confirm the guaranteed (min) figure.
3. Relay endurance: a 15 s swap is ~2 M operations a year per relay; G6K-2 is rated
   for 100 M mechanical but check the low-level contact rating, or slow the swap.
4. Earth the receiver GND locally at the mast; J202 100 G-ohm bias + insulated antenna.
   Do not anodise the enclosures (contact faces must conduct).
5. Consider a gas discharge tube between PE and the receiver GND at the PSU: the
   two-bucket isolation (relays, board gaps) is not rated for the kV ground-potential
   differences a nearby lightning strike causes between the building PE and the
   mast's earth rod. A GDT stays open (about 1 pF) in normal use.
6. D301 (red overflow LED, ADC sheet) is the one LED outside the mains side: it lights
   only when the ADC clips. Leave it unfitted if no LED at all should be on the
   receiver side.

## Fit and placement audit (2026-10-02)
The boards were checked against their enclosures with the real KiCad geometry
(`mechanical/fit_check.py`, `tools/mains_clearance.py`). Fixed:
- PSU: J1's wire entry faced the fuse 5 mm away and the mains gland sat in front of
  the IRM-05; J2's mating face was 6 mm from the box wall; the PE stud was under the
  board. Now: cable bays in front of J1 and J2, glands in line with them, the PE stud
  through the mains-end bar, and the mains hand-routed so L and N never cross.
- PSU: H2/H4 standoffs (on PE) sat on the receiver GND pour behind only the mask:
  5 mm copper keep-outs and nylon standoffs now. LM317s tab-down (no heatsinks).
  C16 was on a D10 footprint for a 12.5 mm can.
- Amplifier: J402 was a dual stacked BNC 29 mm tall (031-6575), now a single
  B6252HB-NPP3G-50; J401's screws sat under the wall, now a pluggable Phoenix MC
  header; C202's order code was the 100 VDC WIMA (24 x 45.5 mm), now the 63 VDC
  MKS4C061007G00KSSD (20 x 39.5 mm); J101 centred in its notch; C101/C205/TR402 off
  the walls.
- Mechanics: the feed-through was 4 mm off the J201 axis; the Micro-Fit's PCB-lock peg
  sat on the tray rim (relief pocket now); the models were placeholders.
- Plates: the solder hole faced the other plate across the 0.5 mm gap; now two
  tongues per plate, every joint outside the overlap.
- Parts data: SiT2001B pinout confirmed; SRF1260 is -102M with 6.8 R for the DC loop
  (PSU simulation re-run with it: 0.8 V of ADM7150 headroom in the worst corner).

## Environment notes (cloud container)
KiCad 9 runs from the `kicad/kicad:9.0-full` Docker image (`kicad-cli`, `kicad-py`
wrappers around `docker run`); Freerouting 1.9 (batch mode, needs an X display, Xvfb
:99); ngspice 42; the `.venv` pins matplotlib 3.10.8 so regenerated plots match.
