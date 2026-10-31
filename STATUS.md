# ELARA -- work status (branch `claude/cloud-work`)

Revision 0.2 of the design, generated from Python sources. Everything below is
committed on this branch; `master` and `ai-augmented-design` are untouched.

## Done
- **Antenna amplifier schematic** (`PCB/antenna_amplifier/design.py`, generator in
  `tools/kicadgen/`). KiCad's netlist export is checked against the design on every
  run: exact match, ERC clean (0 errors, 0 warnings). Changes vs. the old sheet: Cg
  returns to GND, guard buffer senses IN-, 220 pF C0G GUARD-GND for phase margin,
  J202 1-100 G-ohm bias resistor (soldered straight into the holes, no header),
  OPA388 ADC driver (U301), mode pins on DIP switches,
  full LDO support. No LEDs at all (battery use): the ADC overflow flag goes to test
  point TP301. One output: AES3 on a shielded RJ45 for shielded twisted-pair cable,
  transformer isolated (S22083, 2 kV); the cable shield is isolated from GND. The
  AES3 source resistors are 2 x 22 ohm: with the CS8406 drivers' 33.5 ohm each at
  VL = 3.3 V the source is 111 ohm (the old 2 x 39 ohm gave 145 ohm, outside
  AES3's 110 ohm +-20 %).
- **Two-bucket PSU** (`PCB/acdc_converter/`): IRM-05-15 -> LM317 CC 0.2 A / CV 10.76 V
  -> two 4 x 10 F EDLC buckets swapped every ~15 s by four SIL05-1C90-51D reed relays
  (form C, break before make; the arriving bucket switches first, the leaving one
  10-50 ms later, diode-ORed by SS34s, so the load contacts open dry; an SS34 in each
  bucket negative leg) -> 0.4 A limiter -> 2200 uF -> LT3045 6.98 V -> common-mode
  choke. ERC clean, routed, DRC fully clean (0 errors,
  0 warnings), mains clearances checked by `tools/mains_clearance.py`. Charger and
  receiver copper keep at least 1.0 mm apart everywhere (a custom DRC rule, also
  given to Freerouting as class-to-class clearances: `route.py --barrier`,
  `tools/route_psu.sh`). Fab outputs in `fab/`.
- **Air-gap plate capacitor PCB** (`PCB/plate_capacitor/`): 64 x 64 mm plus two solder
  tongues, 49.9 mm copper: 50.2 pF at 0.5 mm with mask and fringing (43.9 pF bare); DRC clean; fab outputs in `fab/`.
- **Simulations**: SPICE front end (`simulations/spice/`), PSU ripple/swap transient,
  guard-loop stability, system noise budget (`simulations/psu|stability|system/`).
  The fixes they found are applied to the schematics (see PLAN.md section 0).
- **BOM** (`bom/`): priced from Farnell / Mouser / Digi-Key / JLCPCB. About 622 EUR ex
  VAT as designed (FR4 amplifier board), about 527 EUR with the listed cost-downs (about 386 EUR for a battery-first build without the PSU).
  300 EUR is not reachable without giving up the PSU's isolation or the outdoor box's
  weatherproofing (about 424 EUR with every further cut); the outdoor box, the boards,
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
  files (the same 94 lines each) to `bom/order/`; see `bom/ORDERING.md`. Local
  mechanical suppliers in eastern Slovenia are in `mechanical/SUPPLIERS_SI.md`
  (from web research: confirm before relying on them).

- **Thermal** (`simulations/thermal/`, 2026-10-31): both boards and the outdoor box
  in an east Slovenian climate. Amplifier at most 3.7 K above its shield (the strips
  bolted to the walls do it), PSU up to 35 K above its box; every part within its
  upper limit on a record 40 C day. Applied from its findings: CS8406-DZZ (-40 C,
  was CZZ -10 C), LM317BTG and L78L12ABUTR (-40 C), a sealed box with an ePTFE vent,
  silica gel and a humidity card, and a white sun/rain shade roof (front end 8 K
  cooler; a black box would push the EDLCs past 65 C). White solder mask makes no
  measurable difference inside the shield. The PSU LM317 tab copper now runs to
  the board edge with 26 thermal vias per tab, but re-simulated it gains only
  0.3-0.5 K; bolting the tabs to the aluminium base was the remaining optional step
  thermally, and the PSU review has since made it required (open check 7). The
  thermal study also leaves two open items: the PCM1804 below -10 C in a cold spell
  and the shade roof, without which the EDLCs exceed 65 C (open checks 10, 11).

- **EM and mechanics** (`simulations/em/`, `simulations/mechanics/`, 2026-10-31).
  Applied: the plate capacitors' lower plates return to PLATE_RET (2.5 V via
  100 k, AC ground through 10 uF film + 100 nF, new turret J203 over a second PTFE
  bush) instead of GND, so only the air-earth current x J202 is left across the
  gaps (30 mV typical): plate microphonics about 80x lower, noise at SR1 unchanged
  (45.8 nV/rtHz, SPICE). Plate copper 49.9 mm for a true 50.2 pF (fringing +6.8 %).
  Receiver earthing mandatory, C406 stays unfitted. Amplifier re-placed and
  re-routed (its SES is now committed). Applied from the mechanics study: two PA66
  mid supports under the PE-HD mounting plate (first mode 27.7 -> 115 Hz; the plate
  stays insulating), a solid 0.8 mm node-2 lead held midway on a PTFE post, the
  antenna lead tied after its gland, wall or stiff-post mounting only, a 2 mm shade
  roof on its own brackets, and a PEEK + alumina + wave-spring plate-capacitor clamp
  (29-31 N over -20..+60 C). Re-simulated: wall mount 0.18 nV/rtHz of microphonics
  at SR1, a pole at 6 m/s 36 nV peak, both under the 45.8 nV floor; Cg (C202) is
  now the largest term, so stake it flush (ASSEMBLY.md).

- **Amplifier review** (fresh-eyes pass over schematic and layout, 2026-10-31).
  Fixed:
  * PCM1804 S/M: low = master (data sheet Table 4). The docs said ON = master,
    which would have left both chips waiting for a clock. SW302-3 now defaults
    OFF (ASSEMBLY.md, schematic note, silkscreen legend, debug table).
  * AES3 isolation: no GND copper on any layer around TR401's secondary, J401 and
    its shell (>= 1.5 mm on In2, >= 2.6 mm on the outer layers and the In1
    plane; was 0.25-0.3 mm), and the router keeps the pair inside that area.
    Only the do-not-fit RF bond C406 bridges it (its own 0603 pad gap).
  * Bias buffer: 10 k (R208) between the 4700 uF C207 and U203's input, so C207
    cannot feed the dead +5V_PRE rail through the input ESD diode after power-off.
  * Test points for bring-up: +9V, +5VA, +5V_PRE, +3V3 (TP101-TP104), MCLK_ADC,
    BCK, LRCK, RESET_N and a digital GND (TP401-TP405).
  * CS8406 TCBLD (pin 11) to +3V3: TCBL is an output, channel-status blocks are
    generated on chip (data sheet p.26).
  * Brown-out reset: TPS3808G01 (U303) holds RESET_N low while +5VA < 4.66 V
    (R306 100 k / R307 9.53 k, SENSE 0.435 V at 5.0 V) and for 300 ms after (CT to
    +3V3 through R308 100 k); SW301 (SMD push button) drives its manual-reset
    input. Open-drain output, R304 10 k pull-up (about 2.8 V high against the
    PCM1804's 51 k pull-down; its input is TTL, 2.0 V); C317 100 nF decoupling.
  * Input TVS SMAJ15A -> SMAJ13A: the SMAJ15A's breakdown reaches 18.5 V, the
    ADM7150's absolute maximum is 18 V; the SMAJ13A breaks down at 14.4-15.9 V and
    clamps 21.5 V only at its full 18.6 A. Input range now 6.98-13 V.
  * ADM7150 VIN, VREG and VOUT: 10 uF X7R 1206 -> 22 uF 25 V X7R 1210
    (GRM32ER71E226KE15L), so the effective capacitance stays above the 7 uF
    minimum after DC bias, temperature and tolerance. REF: 2.2 uF 0805 (C107, C112).
  * PCM1804 VCOM: the 10 uF footprints are DNP (data sheet: 0.1 uF on VCOM).
  * CS8406 COPY/C (pin 1) to +3V3 (consumer format, copy permitted); SW401-2
    (HWCK1) defaults OFF (HWCK = 01 = 128 fs; 11 would be 256 fs, DS580F6 Table 4).
  * J202 has no pin header any more (its plastic body leaked across the G-ohm
    resistor): the resistor is soldered straight into the holes, reset is a clip
    lead across the pads.
  * C202 (Cg) turned so its GND pad is at the wall end.
  * Current budget about 100 mA at J101 (42 mA +5VA, 53 mA +3V3 including 15 mA of
    AES3 line current, 2 x ~4 mA LDO ground current).
  * PCM1804 VCC 100 nF (C314) moved next to pins 22/23.
  * DIP switch legends with the 192 kHz defaults on the silkscreen.
  * ADM7150 exposed pads: soldered with hot air or a hot plate (the 0.3 mm vias
    only carry heat); ASSEMBLY.md corrected.
  The ADM7150 figures (18 V maximum, 7 uF effective) come from the review; the ADI
  site refused downloads this session, so re-read them in the datasheet once.

- **PSU review** (2026-10-31). Fixed:
  * L1 (Bourns SRF1260): windings 1-3 and 2-4 on a project symbol CMC_SRF1260; the
    old symbol shorted the rail.
  * An SS34 in each bucket negative leg (D8-D11, bottom side): current flows one way
    only, so there is no charger-receiver loop through earth during reed skew or
    with a welded reed.
  * 0.4 A load-path limiter (R26 1R5, Q3 Si2319CDS, Q4 MMBT3906); load resistors
    R12/R13 1 R (were 3.3 R). The make current after an outage is 0.40 A (was
    1.33 A unprotected).
  * LT3045 ILIM 499 R (about 0.3 A), output capacitor 22 uF 1210; charger divider
    R3 120 R / R4 909 R -> CV 10.76 V (10.5 mA keeps the LM317 above its minimum
    load and makes up for the extra leg diode); C22 100 nF at U2's input; relay
    coil resistors 47 R.
  * Mains fuse: ceramic high-breaking Littelfuse 0215.500MXP (1500 A; a glass
    5 x 20 mm fuse breaks only about 35 A).
  * Test points TP1-TP7 (CHG_D, +12V_C, SWAP, GND_C, LOAD_P, VREG, GND).
  Re-simulated (`simulations/psu`): LT3045 headroom +1.20 V nominal, >= +0.90 V in
  single corners, only +0.17 V with every corner stacked (was +0.88 V: the leg
  diodes and the limiter cost about 0.7 V); cold start 258 s to the first valid
  rails, LT3045 regulating for good from 319 s; hold-up 32-46 s regulated, 44-58 s
  on the ADM7150 rails. Items not changed in hardware are open checks 5, 7 and
  9-13 below.

## Before ordering -- open checks
1. Newava S22083 (TR401) -- resolved 2026-10-31 from Newava's drawing: pins 1-4
   10.16 mm along the body, 1-2 5.08 mm across (the old footprint had a 7.62 mm
   square, which would not have fitted). New footprint `Transformer_Newava_S22083`
   and 3D model; TR401 turned 270 deg beside J401. Interwinding capacitance
   < 15 pF (the EM study assumed 20 pF, so it is conservative).
2. ADC driver input range -- fixed (2026-10-31): the LMP7715's input stopped at
   V+ - 1 V (clip at -4.4 dBFS, OVFL could never fire); U301 is now an OPA388
   (rail-to-rail input, same pinout). Clip level 29.5 mV rms at the antenna, set by
   the LMP7721 swing: 15.4 dB over 5 mV of 50 Hz pickup (`simulations/system/`).
3. Relay endurance -- addressed with reed relays (2026-10-31). Standex
   SIL05-1C90-51D (rhodium, 10 W / 0.5 A, 1.5 pF open) and a staggered swap: the
   load contacts open at < 2 mA (datasheet ~10^8 operations), the charger contacts
   at 25-81 mA near 10 V (~7*10^6 to 5*10^7), every make <= 0.35 A (`simulations/psu`).
   At ~1 M cycles a year that is 7+ years for the weakest contact. A bench run (one
   swap a second reaches a year's worth in two weeks) is still worth doing. Cost: four
   reeds about EUR 45, against EUR 8 for the two G6Ks. Hold-up after mains loss is
   32-46 s regulated, 44-58 s on the ADM7150 rails (`simulations/psu`).
4. Earth the receiver GND locally at the mast. J202: 100 G-ohm with an insulated antenna
   is best (special order); the BOM's stocked 10 G-ohm also holds a bare antenna (to 100 pA).
   Do not anodise the enclosures (contact faces must conduct).
5. **GDT between PE and the receiver GND at the PSU -- required before mains
   operation, not on the board yet.** The reed relays' open-contact breakdown is
   only 200 V, and the two-bucket isolation (relays, board gaps) is not rated for the
   kV ground-potential differences a nearby lightning strike causes between the
   building PE and the mast's earth rod. A GDT with a DC sparkover of at most about
   150 V and about 1 pF stays open in normal use.
6. The charger / receiver barrier on the PSU board is functional insulation (1.0 mm
   of copper spacing, the relays' contact isolation), not a safety barrier: the
   IRM-05's reinforced insulation is. Surges between the building PE and the mast
   earth need the GDT of item 5.
7. **LM317 tabs bolted to the aluminium base -- required.** At a cold start or with
   a shorted bucket U1 dissipates about 2.25 W for minutes, too much for the tab
   copper alone. Both tabs are live (U1: CC_SET, U2: CHG) and the base is PE /
   GND_C, so each needs an insulating pad and a shoulder washer (ASSEMBLY.md
   section 6, MOUNTING.md section 3). The pads and washers are not in
   `bom/mechanical_bom.csv` yet.
8. Datasheet pin audit -- done (2026-10-31). `tools/pin_audit.py` checks every custom
   or derived IC symbol (LMP7721, 2 x LMP7715, OPA388, PCM1804, CS8406, 2 x ADM7150, SiT2001B,
   TPS3808G01, CD4060) pin by pin against the manufacturers' PDFs, through Adom DS2SF extractions
   kept in `datasheets/ds2sf/`, and checks the nets too (no output on a rail, power
   pins powered). 0 errors. The LMP7721 pin table was also read straight from TI's PDF
   (rev. E, p.3): 1 IN+, 2 N/C, 3 V-, 4 VOUT, 5 N/C, 6 V+, 7 N/C, 8 IN-, pins 2/7
   "recommended to connect to system guard trace" -- exactly the corrected design.
   It found one more slip: KiCad's stock CS8406 symbol swaps the hardware-mode names
   of pins 17 (V) and 18 (U); both are tied to GND, so only the labels were wrong, now
   fixed in CS8406_HW. Not covered yet: LT3045, LM317, L78L12, IRM-05-15 (stock
   symbols, checked by hand in the second audit).
9. **Charger-fault overvoltage on the EDLCs.** A shorted U2 or an open R4 puts
   3.0-3.3 V on each 2.7 V cell, and nothing clamps it. Proposed, not fitted: a
   TL431 + power PNP shunt clamp on CHG_D at about 10.9 V (about 2 W, needs
   heatsinking).
10. **PCM1804 below its rated -10 C.** The board reaches -17.2 C in the -18 C cold
   spell (`simulations/thermal`). Options: a bench freezer test of the board,
   closed-cell foam inside the outdoor box, or a PSU-powered thermostat heater.
11. **Shade roof required.** Without it the EDLCs reach 65.4 C on a record grey day,
   0.45 K over their rating (`simulations/thermal`); MOUNTING.md section 5 step 7.
12. **Measure the GND <-> GND_C current** with a shunt during swaps on the bench
   (ASSEMBLY.md section 6, step 4).
13. Optional PSU improvements, not fitted: Schmitt-squared relay-gate edges
   (CD40106), an EN/UV undervoltage divider on the LT3045 (about 8 V), pre-charging
   each EDLC to about 2.5 V before assembly (balancing takes about 14 h), and a
   service warning label: the buckets hold about 2 x 125 J.
14. v2 idea: the RJ45 carries AES3 on one pair (pins 4/5); pins 1-3 and 6-8 are
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
  cell nominal, 2.70 V at the limits (since 2026-10-31: 120 R / 909 R, 10.76 V, with a
  second SS34 in each bucket leg). The PSU model's charger was corrected at the
  same time (below 0.2 A the CC stage drops 6.2 ohm x I, not a fixed 1.25 V); the
  results and the relay note above are re-run with it.
- **LMP7721 pinout corrected.** The project symbol had IN- on pin 3, GND on 4, OUT
  on 6 and V+ on 8. The LMP7721 has both inputs at one end (1 = +IN, 8 = -IN), the
  N/C isolation pins 2 and 7 next to them (tied to the guard), V- on 3, OUT on 4 and
  V+ on 6 (TI datasheet and evaluation-board notes). As drawn, the board would have
  shorted the op-amp output to GND. The guard ring already suited the real pinout
  (inputs at the pin 1/8 end, guard bar under the body joining pins 2 and 7); the
  parts around U201 were re-placed: Rf, Cf, Rg and the guard buffer in one column
  north-east of the chip on a single spine from pin 8, the guard drive entering the
  ring at its north-east corner, the V+ decoupling beside pin 6, and the V- via under
  the body. Re-routed: Freerouting then walled in one CS8406 mode line (HWCK1), which
  is now pre-routed on its previous path, and 'finish' deletes the router's dangling
  stubs (KiCad's own connectivity test).
- Pinouts re-checked pin by pin against KiCad's exported netlists and the
  datasheets: reed relay SIL05-1C90-51D pin 7 common, 2 NC, 1 NO, coil + on 3 (Standex
  datasheet V03 p.3, as KiCad's SILxx-1Cxx-51x), both TVS cathodes on the positive rail, LT3045 EN/UV and PGFB to
  IN and ILIM to GND (the datasheet's settings for unused functions), CD4060 RC
  pins and Q14, LM317 and L78L12 (SOT-89) pinouts, CS8406 hardware-mode pins.

## Environment notes (cloud container)
`sh tools/setup_env.sh` installs everything on a fresh Ubuntu 24.04 container: KiCad
9.0.9 natively from the official PPA (`kicad-cli`; `kicad-py` runs the distro
python3.12, which has `pcbnew`), ngspice 42, Freerouting 1.9 (batch mode, needs an X
display, Xvfb :99) and the `.venv` (matplotlib pinned to 3.10.8 so regenerated plots
match). Then `export KICAD9_SYMBOL_DIR=/usr/share/kicad/symbols`. The native install
reproduces the earlier Docker-based outputs byte for byte. Add the script to the
cloud environment's setup script so every session starts ready.
