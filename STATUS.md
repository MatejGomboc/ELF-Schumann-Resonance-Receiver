# ELARA -- work status (branch `master`)

Revision 0.2 of the design, generated from Python sources. Everything below is
committed on `master`. The work grew on `claude/cloud-work` out of
`ai-augmented-design`; both were merged into `master` on 2026-11-01 (the original
2021 VLF design that `master` held before stays in its history and on the `v2` branch).

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
  `tools/route_psu.sh`). Fab outputs in `fab/`. Since 2026-10-31 also an EDLC
  overvoltage crowbar and a GDT across the barrier (PSU protection below); 103
  components.
- **Air-gap plate capacitor PCB** (`PCB/plate_capacitor/`): 64 x 64 mm plus two solder
  tongues, 49.9 mm copper: 50.2 pF at 0.5 mm with mask and fringing (43.9 pF bare); DRC clean; fab outputs in `fab/`.
- **Simulations**: SPICE front end (`simulations/spice/`), PSU ripple/swap transient,
  guard-loop stability, system noise budget (`simulations/psu|stability|system/`).
  The fixes they found are applied to the schematics (see PLAN.md section 0).
- **BOM** (`bom/`): priced from Farnell / Mouser / Digi-Key / JLCPCB. 790.91 EUR ex
  VAT as designed (FR4 amplifier board; 964.91 EUR incl. 22 % VAT), 695.98 EUR with the
  listed cost-downs (849.10 EUR incl. VAT; about 461 EUR for a battery-first build
  without the PSU and the box heater). 300 EUR is not reachable without giving up the
  PSU's isolation or the outdoor box's weatherproofing (591.65 EUR with every further
  cut); the outdoor box, the box heater (91.30 EUR), the boards, the EDLCs and the
  aluminium are the largest lines.
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
  For the planned site: `simulations/antenna/site_antenna.py` gives capacitance and
  h_eff against top-wire length. `simulations/antenna/site_wire.py` covers the wire
  mechanics: sag and tension from -25 to +40 C (thermal change under 2 cm), ice and
  storm loads (a ~1 kN weak link), modes, and wind noise through the fair-weather
  field. Wind noise is the antenna's main limit above ~2 m/s, so record in calm
  weather and log the wind.
- **Mains feed**: `MAINS_CABLE.md` covers the screened cable, the building end
  (RCD, screen bonded to PE there only) and preparing the PSU end.
- **Ordering**: `bom/order_lists.py` writes Digi-Key, Mouser and Farnell upload
  files (the same 101 lines each) to `bom/order/`; see `bom/ORDERING.md`. Local
  mechanical suppliers in eastern Slovenia are in `mechanical/SUPPLIERS_SI.md`
  (from web research: confirm before relying on them). PCBs from JLCPCB:
  `bom/PCB_ORDER.md`. The amplifier shield from JLCCNC (2026-11-01): `bom/CNC_ORDER.md`
  with `mechanical/jlccnc/`, generated by `mechanical/jlccnc.py`. That is five milled
  parts (the three identical short bars share one), a laser-cut lid, 64 M3 threads
  on the PDF drawings, and every feature probed against its STEP solid in check_all.

- **Thermal** (`simulations/thermal/`, 2026-10-31): both boards and the outdoor box
  in an east Slovenian climate. Amplifier at most 3.7 K above its shield (the strips
  bolted to the walls do it), PSU up to 35 K above its box; every part within its
  upper limit on a record 40 C day. Applied from its findings: CS8406-DZZ (-40 C,
  was CZZ -10 C), LM317BTG and L78L12ABUTR (-40 C), a sealed box with an ePTFE vent,
  silica gel and a humidity card, and a white sun/rain shade roof (front end 8 K
  cooler; a black box would push the EDLCs past 65 C). White solder mask makes no
  measurable difference inside the shield. The PSU LM317 tab copper now runs to
  the board edge with 26 thermal vias per tab, but re-simulated it gains only
  0.3-0.5 K; the tabs are not bolted to the base (PSU protection below). The shade
  roof is now built ("Site and shade roof" below): every design verdict passes.

- **Box heater** (2026-10-31, `simulations/thermal`, `mechanical/`): a mains-side
  STEGO HG 140 30 W PTC heater with a STEGO KTO 111 NC thermostat (set to +5 C, 7 K
  differential; the KTO 011 is discontinued) on a 160 mm DIN rail screwed to the PSU
  box lid, with Phoenix UT 2.5 terminals for L, N and PE and a UT 4-HESI fuse
  terminal (T 4 A ceramic). The incoming mains lands on the rail; one branch goes on
  to the PSU box gland, the other through the fuse and the thermostat to the heater.
  Never on the receiver supply; a battery-powered unit has none. PCM1804 minimum
  -3.98 C in the -18 C cold spell (-17.2 C without) and -8.76 C at -25 C outside with
  5 m/s wind (-22.0 C without): "PCM1804 >= -10 C down to -25 C outside" now passes.
  Duty 49 % (351 Wh/day) at -18 C, 79 % (571 Wh/day) at -25 C, about 5 % on the
  autumn clear night (all before the shade roof; under the roof -2.92 C / -7.72 C,
  42 % / 77 % duty, 2 % on the autumn night), 0 all summer (new verdict "heater off all summer"). An on/off
  thermostat run gives ~3 min cycles, 4.9 K pp in the box air, 9 mK pp at the
  LMP7721 (new verdict "LMP7721 ripple < 0.05 K pp"). The rail parts reach
  z = 117.5 mm in the 144 mm deep box (`params.check()`: >= 5 mm to the door); fit
  check and clash check clean. The EDLC on a record 40 C day without the shade roof
  was the last thermal FAIL; the roof (next item) settles it.

- **Site and shade roof** (2026-10-31, `mechanical/`, `simulations/thermal`,
  `simulations/mechanics`, `bom/`). The site is known (Matej is recording a video;
  details may still be refined): the outdoor box stands on a stiff post (stilt) in the
  middle of a grassy field, right where the vertical down-lead hangs; the far ends of
  the horizontal wire go to the house and to a tree near the forest. The post must be
  the 114.3 x 6.3 mm steel one, at most 1 m (box about 1 m above ground): a thin
  pole sways at 5-20 Hz, inside the band. The sun and rain roof is built in CAD and
  the BOM: white 2 mm aluminium, 500 x 500 mm, centred over the box (on a
  free-standing post the sun reaches the back too), 15 mm drip flange on all four
  edges, 30 mm above the box on two galvanised 30 x 4 flat-bar arms (L: 500 arm,
  200 leg) clamped to the post with M10 U-bolts, never fixed to the box. A 20 mm
  hole with an EPDM grommet (B15) over the antenna gland: the lead rises through it
  (about 0.05 pF to the roof) with a drip loop below the roof. The roof is bonded to
  the receiver earth with a 4 mm2 green-yellow lead (B16): a floating roof charges up
  in wind and rain next to the antenna lead. `mechanical/params.py` SHADE_ROOF,
  ROOF_BRACKET_*; `outer_box.shade_roof()` / `roof_brackets()`; in the full assembly
  and the renders; clash check clean.
  * Thermal: the roof is modelled geometrically (ray casting from each box face to
    the roof plane, from its real size) instead of "all beam blocked", on in every
    case, with no-roof references. Record 40 C day, light grey box: EDLC 62.0 C (door
    S), 62.2 C (N), 62.8 C (W), 63.7 C (E, the worst), against 65.4 C without the
    roof. "EDLC <= 65 C (light grey, record summer, shade roof, door any way)" passes;
    every design verdict now passes, only the rejected vented box still fails (by
    design). Door north or south recommended. A wall-flush 500 x 400 roof would have
    left only 0.4 K of margin with an east door, hence the centred 500 x 500.
  * Mechanics: roof and arms add 3.1 kg at the post top: first mode 71 -> 62 Hz, still
    above the Schumann band. Storm uplift about 211 N (about 105 N per arm), snow
    about 300 N.
  * BOM: B11 Al sheet 530 x 530 (24.00), B14 two arms (8.00), B14a two U-bolts (8.00),
    B15 grommet (0.50), B16 roof earth lead (2.00): +20.50 EUR.

- **Stock PTFE feed-throughs** (2026-11-01): the two lathe-turned PTFE bushes are
  replaced by Keystone 11157 press-fit PTFE feed-through terminals (DigiKey
  36-11157-ND). They sit in 3.45 mm holes in Ø8 spot-faces that leave the 1.6 mm
  panel the part is rated for. The node-2 lead solders to the outer pin, and a short
  0.8 mm stub joins the inner pin to J201 (J203 alike). EM: the hole leaks about 100x
  less of an outside field (0.31 nV per V/m), and IN_P's unguarded load is 0.401 pF
  (+0.002 dB). The fit check accepts the pin-to-lead joint, capped below 1 mm³.

- **L-shaped guard island** (2026-11-01): the island hugs J202, the J201 turret and
  IN_P to U201 pins 1/2; the empty corner is masked (less bare board to clean).
  Input-to-guard gaps unchanged; re-routed, DRC clean; IN_P's unbootstrapped load
  0.357 pF (was 0.335, `simulations/em`); 0.401 pF since the Keystone feed-through. ASSEMBLY.md: deionised-water rinse, a
  silica-gel bag in compartment 1, and the optional air-wired input.

- **Branch model check** (2026-10-31, merged 2026-11-01): `master` is the working
  branch. `tools/branch_docs.py`, run by `tools/check_all.sh` and so in CI, fails when
  the documents disagree on the working branch, and fails a pull request into master
  or a push to master while they still name a side branch.

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
  roof on its own supports (now arms on the post, see the site item), and a PEEK + alumina + wave-spring plate-capacitor clamp
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
  on the ADM7150 rails. The GDT, the EDLC clamp and the LM317 tab question were
  settled afterwards (next item); the rest not changed in hardware is open checks
  7-8 below.

- **PSU protection** (2026-10-31; re-placed and re-routed: DRC 0 / 0 unconnected /
  0 parity, mains clearances pass, schematic legibility 0):
  * EDLC overvoltage crowbar on CHG: U6 TL431BIDBZR (0.5 %), R29 36.5 k / R30 10 k
    (0.1 % thin film), C23 100 nF, R31 680 R B-E + R32 1 k base, Q5 MMBT3906, R33
    470 R gate, R34 1 k + C24 100 nF gate-cathode, Q6 MCR100-6 SCR (TO-92,
    staggered footprint). Trips at CHG = 11.7 V (11.5-11.9 V over tolerance and
    temperature; normal CV at most 11.24 V; 2.8-2.9 V per cell at the trip, against
    3.75 V per cell with a shorted LM317). The SCR latches CHG down on the CC
    stage's 0.2 A (or the IRM-05's own limit) until mains is removed; D1 keeps the
    buckets out of it. False trip: D2 mains LED on, buckets not charging; remove
    mains for about 10 s. Placed in the charger corner right of D1.
  * GDT1 Bourns 2051-15-SM-RPLF (150 V +-30 % DC sparkover, < 0.5 pF, 2 kA 8/20)
    between GND_C (PE-bonded via R1) and the receiver GND across the 5 mm gap
    between the pours: a strike's kV between mains PE and the receiver's earth rod
    goes through it, not through the 1 mm barrier or a reed. New footprint
    `elara:GDT_Bourns_2051`.
  * LM317 tabs: not bolted to the aluminium base. Normal dissipation is 0.17-0.22 W
    per LM317 (junction at most about 78 C on a record summer day); in the crowbar
    fault the CC LM317 dissipates about 2.5 W and goes into its internal thermal
    limit. Bolting would need an insulated tab (tab = OUT, base = PE) for no gain.
  * Datasheets (sent by Matej) checked: onsemi LM317 (TO-220: 1 ADJ, 2 OUT, 3 IN,
    tab = OUT; minimum load 3.5 mA typ / 10 mA max, the CV divider draws about
    10.4 mA), ST L78L SOT-89 (1 OUT, 2 GND, 3 IN), Vishay Si2319CDS (1 G, 2 S, 3 D;
    VGS +-20 V; the limiter's ~1.9 W x 27 ms pulse is inside its ~5 W / 30 ms SOA),
    TI TL431 DBZ (1 K, 2 REF, 3 A), UTC MCR100 (1 K, 2 G, 3 A), Bourns 2051, STEGO
    KTO 111 and HG 140. `tools/pin_audit.py` now also audits U1, U2, U3, Q3, U6 and
    Q6 from hand-read extractions: 0 errors, 0 warnings.

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
4. Earth the receiver GND locally at the box's post (and bond the shade roof to the
   same earth, B16). J202: 100 G-ohm with an insulated antenna
   is best (special order); the BOM's stocked 10 G-ohm also holds a bare antenna (to 100 pA).
   Do not anodise the enclosures (contact faces must conduct).
5. The charger / receiver barrier on the PSU board is functional insulation (1.0 mm
   of copper spacing, the relays' contact isolation), not a safety barrier: the
   IRM-05's reinforced insulation is. Surges between the building PE and the mast
   earth go through GDT1 (150 V, on the board since 2026-10-31).
6. Datasheet pin audit -- done (2026-10-31). `tools/pin_audit.py` checks every custom
   or derived IC symbol (LMP7721, 2 x LMP7715, OPA388, PCM1804, CS8406, 2 x ADM7150, SiT2001B,
   TPS3808G01, CD4060) pin by pin against the manufacturers' PDFs, through Adom DS2SF extractions
   kept in `datasheets/ds2sf/`, and checks the nets too (no output on a rail, power
   pins powered). 0 errors. The LMP7721 pin table was also read straight from TI's PDF
   (rev. E, p.3): 1 IN+, 2 N/C, 3 V-, 4 VOUT, 5 N/C, 6 V+, 7 N/C, 8 IN-, pins 2/7
   "recommended to connect to system guard trace" -- exactly the corrected design.
   It found one more slip: KiCad's stock CS8406 symbol swaps the hardware-mode names
   of pins 17 (V) and 18 (U); both are tied to GND, so only the labels were wrong, now
   fixed in CS8406_HW. PSU parts added 2026-10-31 from hand-read extractions: LM317BTG
   (U1, U2), L78L12ABUTR (U3), Si2319CDS (Q3), TL431BIDBZR (U6), MCR100-6 (Q6).
   Not covered yet: LT3045 and IRM-05-15 (stock symbols, checked by hand in the
   second audit).
7. **Measure the GND <-> GND_C current** with a shunt during swaps on the bench
   (ASSEMBLY.md section 6, step 4).
8. Optional PSU improvements, not fitted: Schmitt-squared relay-gate edges
   (CD40106), an EN/UV undervoltage divider on the LT3045 (about 8 V), pre-charging
   each EDLC to about 2.5 V before assembly (balancing takes about 14 h), and a
   service warning label: the buckets hold about 2 x 125 J.
9. v2 idea: the RJ45 carries AES3 on one pair (pins 4/5); pins 1-3 and 6-8 are
   unconnected, reserved for control signals in a later revision. Anything added
   there must be galvanically isolated as well (digital isolators and an isolated
   supply), or the receiver stops floating.
10. Winter battery operation: there is no heater without mains, and the amplifier
   board reaches -16.8 C in the -18 C cold spell under the shade roof (-19.3 C
   without), below the PCM1804's -10 C rating
   (`simulations/thermal`). Run on a battery in winter only out of spec, or check
   the board in a freezer first.

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
