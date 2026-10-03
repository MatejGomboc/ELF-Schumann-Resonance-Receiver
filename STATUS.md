# ELARA -- work status (branch `claude/cloud-work`)

Revision 0.2 of the design, generated from Python sources. Everything below is
committed on this branch; `master` and `ai-augmented-design` are untouched.

## Done
- **Antenna amplifier schematic** (`PCB/antenna_amplifier/design.py`, generator in
  `tools/kicadgen/`). KiCad's netlist export is checked against the design on every
  run: exact match, ERC clean (0 errors, 0 warnings). Changes vs. the old sheet: Cg
  returns to GND, guard buffer senses IN-, 220 pF C0G GUARD-GND for phase margin,
  J202 1-100 G-ohm bias resistor, LMP7715 ADC driver, mode pins on DIP switches,
  full LDO support. No LEDs at all (battery use): the ADC overflow flag goes to test
  point TP301. One output: AES3 on a shielded RJ45 for shielded twisted-pair cable,
  transformer isolated (S22083, 2 kV); the cable shield is isolated from GND. The
  AES3 source resistors are 2 x 22 ohm: with the CS8406 drivers' 33.5 ohm each at
  VL = 3.3 V the source is 111 ohm (the old 2 x 39 ohm gave 145 ohm, outside
  AES3's 110 ohm +-20 %).
- **Two-bucket PSU** (`PCB/acdc_converter/`): IRM-05-15 -> LM317 CC 0.2 A / CV 10.4 V
  -> two 4 x 10 F EDLC buckets swapped every ~15 s by G6K-2 relays in opposite sense
  (break before make) -> 2200 uF -> LT3045 6.98 V -> common-mode choke. ERC clean,
  routed, DRC fully clean (0 errors, 0 warnings), mains clearances checked by
  `tools/mains_clearance.py`. Charger and receiver copper keep at least 1.0 mm apart
  everywhere (a custom DRC rule; the relays' own pins put a bucket pin between the
  two sides). Fab outputs in `fab/`.
- **Air-gap plate capacitor PCB** (`PCB/plate_capacitor/`): 64 x 64 mm plus two solder
  tongues, ~49 pF bare at 0.5 mm; DRC clean; fab outputs in `fab/`.
- **Simulations**: SPICE front end (`simulations/spice/`), PSU ripple/swap transient,
  guard-loop stability, system noise budget (`simulations/psu|stability|system/`).
  The fixes they found are applied to the schematics (see PLAN.md section 0).
- **BOM** (`bom/`): priced from Farnell / Mouser / Digi-Key / JLCPCB. About 502 EUR ex
  VAT as designed (FR4 amplifier board), about 407 EUR with the listed cost-downs.
  300 EUR is not reachable without giving up the PSU's isolation or the outdoor box's
  weatherproofing (about 319 EUR with every further cut); the outdoor box, the boards,
  the EDLCs and the aluminium are the largest lines.
- **PC software** (`software/elara/`, 27 tests pass).
- **Mechanics** (`mechanical/`, CadQuery -> STEP/DXF/renders). The real boards are
  imported from KiCad and fit-checked inside the shield and the PSU box
  (`fit_check.py`), and the units, glands and cables in the outdoor box: no clashes.
- **Amplifier PCB** (`PCB/antenna_amplifier/layout.py place|finish`): 200 x 100 mm,
  4 layers, 3 compartments with 7 mm exposed wall strips, guarded input island,
  GND fan-out to the In1 plane before routing, Freerouting 1.9, pours + stitching.
  Fully routed: 0 DRC errors, 0 unconnected. The only remaining warnings are the
  intended mask bridges on the bare guard island. Parts sit in functional blocks
  in aligned rows and columns (0.5 mm grid): the PCM1804 and CS8406 side by side so
  the I2S lines run straight, each IC's capacitors in a cell around it, the DIP
  pull-downs in line with the switch pins. Fab outputs are in `fab/`.
- **Fab rules**: JLCPCB's standard-process limits are KiCad rules on every board
  (`tools/kicadgen/fabrules.py`, written on each save: project-file minimums plus a
  `.kicad_dru`): track/gap, drill range, PTH and via rings, NPTH, hole-to-hole,
  inner hole-to-copper, mask dam (0.13 mm, any colour), silkscreen. All three boards
  pass with them.
- **Silkscreen**: board labels go to the nearest free spot. References follow the
  part's shape (vertical labels in line with small vertical parts, horizontal ones
  over horizontal or large parts), so rows of parts get rows of labels; footprint
  outlines are widened to 0.15 mm and cut back 0.15 mm from the pads. Only J201 and
  J202 on the bare guard island have no silk label; their fab-layer references sit
  beside them. Every other part drops its fab-layer copy of the reference, so the
  assembly drawings (fab + silk) name each part once.
- **Assembly and bring-up guide**: `ASSEMBLY.md` covers the soldering order,
  cleaning the femtoamp island, DIP-switch defaults and the expected voltages.
- **Mounting and site guide**: `MOUNTING.md` covers the shield, PSU box, plate
  capacitors, outdoor box, antenna, local earth, lightning and commissioning.
- **Mains feed**: `MAINS_CABLE.md` covers the screened cable, the building end
  (RCD, screen bonded to PE there only) and preparing the PSU end.
- **Ordering**: `bom/order_lists.py` writes Digi-Key, Mouser and Farnell upload
  files (the same 80 lines each) to `bom/order/`; see `bom/ORDERING.md`. Local
  mechanical suppliers in eastern Slovenia are in `mechanical/SUPPLIERS_SI.md`
  (from web research: confirm before relying on them).

## Before ordering -- open checks
1. Newava S22083 (TR401): the body (12.7 x 8.89 x 6.35 mm, 4-pin THT) matches
   the footprint, and its slotted pads take 5.08-10.16 mm row spacing. Distributor
   data confirms the windings (1-2 primary, 3-4 secondary, 1:1, 225 uH, 0.4 ohm,
   2000 Vac hipot); only the pin pitch still needs Newava's drawing.
2. LMP7715 (U301) input common-mode ceiling -- confirmed: the datasheet's CMVR at
   5 V is -0.3 to 4.0 V (V+ - 1 V) for CMRR >= 80 dB. The system budget
   (`simulations/system/`) clips at exactly that and still has 12.5 dB of 50 Hz
   headroom over 5 mV of pickup.
3. Relay endurance -- the main reliability risk. A 15.2 s swap is ~2 M operations a
   year per relay. The G6K-2F-Y is rated for 50 M mechanical operations, but only
   100 k electrical at its rated 1 A / 30 VDC resistive load. Our contacts see much
   less (make 0.3-0.6 A into the reservoir, break ~0.1 A, at about 10 V), so wear
   should be far below the rated-load figure, but Omron gives no number for this
   duty. The swap can be slowed to halve the wear: with R6 = 160 k (30 s) the
   LT3045 still keeps 0.36 V of headroom with every corner stacked (1.05 V at
   15.2 s), at a 0.9 A worst-case make current (`simulations/psu`). Run a bench
   endurance test first, at the real make current (a rig that pulls the reservoir
   down by ~0.6 V between operations; at one operation a second it reaches 1.2 M
   in two weeks), and consider dry reed relays, rated for 10^8 or more low-level
   operations, in a later revision.
4. Earth the receiver GND locally at the mast. J202: 100 G-ohm with an insulated antenna
   is best (special order); the BOM's stocked 10 G-ohm also holds a bare antenna (to 100 pA).
   Do not anodise the enclosures (contact faces must conduct).
5. Consider a gas discharge tube between PE and the receiver GND at the PSU: the
   two-bucket isolation (relays, board gaps) is not rated for the kV ground-potential
   differences a nearby lightning strike causes between the building PE and the
   mast's earth rod. A GDT stays open (about 1 pF) in normal use.
6. The charger / receiver barrier on the PSU board is functional insulation (1.0 mm
   of copper spacing, the relays' contact isolation), not a safety barrier: the
   IRM-05's reinforced insulation is. Surges between the building PE and the mast
   earth need the GDT of item 5.
7. LM317 dissipation at a cold start: with both buckets empty the CC stage drops up
   to about 12 V at 0.2 A, 2.4 W, for about a minute, on the tab copper (no
   heatsink). Warm but within the TO-220's rating; check the tab temperature at the
   first power-up.
8. v2 idea: the RJ45 carries AES3 on one pair (pins 4/5); pins 1-3 and 6-8 are
   unconnected, reserved for control signals in a later revision. Anything added
   there must be galvanically isolated as well (digital isolators and an isolated
   supply), or the receiver stops floating.

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
- Amplifier: J402 was a dual stacked BNC 29 mm tall (031-6575), then a single
  B6252HB-NPP3G-50; J401's screws sat under the wall, then a pluggable Phoenix MC
  header (both outputs became the one shielded RJ45 in the second audit, below);
  C202's order code was the 100 VDC WIMA (24 x 45.5 mm), now the 63 VDC
  MKS4C061007G00KSSD (20 x 39.5 mm); J101 centred in its notch; C101/C205 and the
  old TR402 off the walls.
- Mechanics: the feed-through was 4 mm off the J201 axis; the Micro-Fit's PCB-lock peg
  sat on the tray rim (relief pocket now); the models were placeholders.
- Plates: the solder hole faced the other plate across the 0.5 mm gap; now two
  tongues per plate, every joint outside the overlap.
- Parts data: SiT2001B pinout confirmed; SRF1260 is -102M with 6.8 R for the DC loop
  (PSU simulation re-run with it: 0.8 V of ADM7150 headroom in the worst corner).

## Second audit (2026-10-03)
- Battery use: no LED on the receiver side (D301 overflow LED -> test point TP301);
  the PCM1804 mode pins use its internal 51 k pull-downs (6 resistors gone), BYPAS
  and the CS8406 mode pins 47 k: about 3 mA less on +3V3 with the default switches.
- Output: one AES3 output on a shielded RJ45 (Amphenol RJHSE-5380, blue pair 4/5) for
  shielded twisted-pair cable; the S/PDIF coax branch (BNC, second transformer, 5.6 mA
  of standing current) and the DC shield bond are gone, the 10 nF RF bond stays DNP.
- JLCPCB limits as KiCad rules on all boards; footprint silk to 0.15 mm.
- Placement tidied (rows, columns, cells); reference labels placed by shape, every
  one on silk except on the guard island. Found and fixed on the way: the label
  placer counted each label as its own obstacle (SWIG proxies compared with `is`), and
  labels not yet placed blocked their neighbours.
- PSU: the charger / receiver copper came within 0.30 mm beside the relays; now >= 1.0
  mm (custom rule, 1 mm router class for the relay contact nets, hand-routed GND and
  GND_C at the relays). The guard-drive link on the amplifier is re-routed for the
  new column (C205 above R203, one straight GUARD link).
- PSU charger: the CV divider (240 R / 1.87 k) set 11.08 V, not the 10.9 V it was
  labelled with, which floats the 2.7 V EDLC cells at 2.72 V whenever the receiver
  draws nothing (2.83 V at the LM317's limits). R4 is now 1.74 k: 10.4 V, 2.55 V per
  cell nominal, 2.70 V at the limits. The PSU model's charger was corrected at the
  same time (below 0.2 A the CC stage drops 6.2 ohm x I, not a fixed 1.25 V); the
  results and the relay note above are re-run with it.
- Pinouts re-checked pin by pin against KiCad's exported netlists and the
  datasheets: G6K-2F-Y NC on pins 2/7 and coil + on pin 1 (as Omron's latching G6KU
  symbol marks it), both TVS cathodes on the positive rail, LT3045 EN/UV and PGFB to
  IN and ILIM to GND (the datasheet's settings for unused functions), CD4060 RC
  pins and Q14, LM317 and L78L12 (SOT-89) pinouts, CS8406 hardware-mode pins.

## Environment notes (cloud container)
KiCad 9 runs from the `kicad/kicad:9.0-full` Docker image (`kicad-cli`, `kicad-py`
wrappers around `docker run`); Freerouting 1.9 (batch mode, needs an X display, Xvfb
:99); ngspice 42; the `.venv` pins matplotlib 3.10.8 so regenerated plots match.
