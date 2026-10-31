# ELARA -- assembly and bring-up (rev 0.2)

This guide covers a hand-soldered prototype. Part numbers and prices are in `bom/`.
Gerbers, drill files, pick-and-place, PDFs and renders are in `PCB/<board>/fab/`.

## 1. What to order

| Item | Files | Fab options |
| --- | --- | --- |
| Antenna amplifier PCB, 200 x 100 mm, 4 layers | `PCB/antenna_amplifier/fab/antenna_amplifier_gerbers.zip` | 1.6 mm FR4, 1 oz, **ENIG** (flat pads for the SSOP/TSSOP parts and flat wall strips), any mask colour |
| Two-bucket PSU PCB, 150 x 90 mm, 2 layers | `PCB/acdc_converter/fab/acdc_converter_gerbers.zip` | 1.6 mm FR4, 1 oz, HASL is fine |
| Air-gap plate PCB, 64 x 64 mm + two 7 mm solder tongues, 2 layers | `PCB/plate_capacitor/fab/` | 4 plates (2 capacitors x 2 plates); order 5 or 10 |
| Components | `bom/antenna_amplifier_bom.csv`, `bom/psu_bom.csv`, `bom/extras.csv` | buy about 10 % spare 0603 parts |
| Mechanics | `mechanical/` (STEP, DXF), `bom/mechanical_bom.csv` | aluminium, **not anodised** (the contact faces must conduct) |

**PCB order options and the note to paste into the order:** `bom/PCB_ORDER.md`.
The silkscreen reads `REV 0.2` and the short git commit the Gerbers were exported from.

Check the open items in `STATUS.md` before ordering (among them a bench endurance
test of the PSU relays, the GDT between PE and the receiver GND, and the cold-spell
limit of the PCM1804).

## 2. Tools and materials

- Temperature-controlled iron with a fine chisel tip; hot air is optional.
- No-clean flux (use it sparingly), 0.5 mm solder, and braid.
- Isopropyl alcohol (99 %), a clean soft brush, lint-free wipes and nitrile gloves.
- ESD mat and wrist strap. The LMP7721 inputs have almost no ESD margin.
- Multimeter, a bench supply with current limit and, ideally, an oscilloscope.

## 3. Antenna amplifier: soldering order

Keep `PCB/antenna_amplifier/fab/antenna_amplifier_ibom.html` open in a browser
while you solder. Clicking a BOM line highlights its parts on the board, and you
can tick each line off as sourced and placed. The PSU has its own copy,
`PCB/acdc_converter/fab/acdc_converter_ibom.html`.

Solder the flat, fine-pitch parts first, while the board lies flat, and the tall ones last.

1. **Fine-pitch ICs:** U302 PCM1804 (SSOP-28), U401 CS8406 (TSSOP-28), Y402
   (24.576 MHz MEMS oscillator, SOT23-5), U301 OPA388 (the ADC driver, SOT-23-5),
   the SOT-23-5 buffers U202/U203 (LMP7715) and U303 TPS3808G01 (the brown-out
   supervisor, SOT-23-6). Y401 is the no-lead alternative to Y402, wired to the
   same nets: leave it empty unless you fit it *instead of* Y402. Never fit both.
   Check pin 1 on each part against the silkscreen dot.
2. **ADM7150 regulators (U101, U102):** tin the exposed pad and its footprint
   lightly, place the part and reflow it with hot air (or on a hot plate), then
   touch up the eight pins with the iron. The three 0.3 mm vias under the pad
   only carry heat to the GND plane; they are too small to solder through from
   the back with an iron. The pad is thermal (pin 4 is GND), about 0.4 W at 13 V
   in.
3. **Passives**, one compartment at a time: 03 DIGITAL, then 02 ANALOG, then
   01 INPUT. The reset button SW301 (TL3342, SMD) goes on with the 03 DIGITAL
   parts. The PCM1804's VCOM 10 uF footprints stay empty (DNP: the data sheet asks
   for 0.1 uF on VCOM only). Every part has its reference on the silkscreen
   right next to it (rows of parts have rows of labels); only J201 and J202 on the bare guard
   island have none. The assembly drawing `fab/antenna_amplifier_assembly_top.pdf`
   and the interactive BOM give every reference too.
4. **U201 LMP7721 last among the SMD parts.** Hold it by the body, never by the
   pins, and wear the wrist strap.
5. **Through-hole parts:** DIP switches SW302/SW401 and the test points
   (TP101-TP104 rails, TP201-TP204, TP301, TP401-TP405 clocks, reset and
   digital GND). Then TR401 (S22083), J101 (power) and
   J401 (the shielded RJ45 for the AES3 cable). Keep J401 square to the board
   edge: it lines up with the wall notch. Then the electrolytics C101 and C207
   (check the polarity) and the film capacitors C301, C210 and C202, which go on
   last. Seat C202 (43 g) and C210 **flush on the board** and stake them with a bead
   of MS-polymer (B13a) along the body: a C202 standing on its leads yields them at
   5 g of transport shock, and its vibration is now the largest microphonic term
   (`simulations/mechanics`). C202 is turned so that its GND pad is at the wall
   end. J203 is the second PTFE turret, below the input island.
6. **Input island:** J201 is the PTFE turret, which takes the antenna lead from
   below. J202 has **no pin header** (a header's plastic body would leak across
   the G-ohm resistor): solder the 1-100 GOhm glass resistor straight into the two
   J202 holes, standing off the board, with its body in the air and touching
   nothing. To reset the input, short the two J202 pads briefly with a clip lead.

### Cleaning the input (do not skip this)

Flux residue and fingerprints on the guarded island create leakage paths and
tiny galvanic cells, which ruin the femtoampere input
([ADI AN-1373](https://www.analogue.com/en/resources/app-notes/an-1373.html),
[ADA4530-1 data sheet](https://www.analogue.com/media/en/technical-documentation/data-sheets/ADA4530-1.pdf)).

1. Scrub the whole board with IPA and the brush, then scrub the island again
   with fresh IPA. Do a final rinse of the island with clean IPA from a bottle.
2. Do **not** put the finished board in an ultrasonic bath: the MEMS oscillator
   does not like it. If you want ultrasonic cleaning,
   do it before those parts are fitted.
3. Dry the board for several hours, or bake it for about 2 h at 60-70 °C. The
   electrolytics, film capacitors and DIP switches set that limit.
4. From now on, handle the board only by its edges or the exposed wall strips.
   Never touch the island. Leave it bare: no conformal coating.

## 4. DIP switch defaults (192 kHz, I2S, AES3)

ON = logic 1 (the switch ties the pin to +3.3 V). OFF = logic 0: the PCM1804's
own 51 kOhm pull-downs hold FMT0 to OSR2 low, and 47 kOhm resistors hold BYPAS and
the CS8406 pins low. Two CS8406 straps are fixed on the board, not on the switch:
COPY/C (pin 1) and TCBLD are tied to +3V3 (consumer format, copying permitted;
channel-status blocks generated on chip). Change switches with the power off, or press RESET afterwards.

**SW302 -- PCM1804 mode**

| Switch | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pin | FMT0 | FMT1 | S/M | OSR0 | OSR1 | OSR2 | BYPAS | -- |
| Default | ON | OFF | **OFF** | ON | ON | ON | ON | OFF |

Switch 3 must be **OFF**: S/M low makes the ADC the master (PCM1804 data sheet,
Table 4: low = master, high = slave). With it ON both chips wait for the other
to clock them and there is no audio at all. The defaults are printed beside
the switches on the board. This makes the ADC the master with SCKI = 128 fs (OSR = 111), I2S
format (FMT = 01) and the digital high-pass filter off (BYPAS = 1). The high-pass
filter must stay off: the Schumann band starts at a few hertz.

**SW401 -- CS8406 hardware mode**

| Switch | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pin | HWCK0 | HWCK1 | SFMT0 | SFMT1 | APMS | CEN | EMPH_N | AUDIO_N |
| Default | ON | **OFF** | ON | OFF | OFF | OFF | ON | OFF |

Switch 2 must be **OFF**: in hardware mode HWCK1/HWCK0 = 01 is OMCK = 128 fs
(CS8406 data sheet DS580F6, Table 4). With both ON (11) the chip expects 256 fs,
a 49.152 MHz clock at 192 kHz, and the AES3 stream comes out at the wrong rate
or not at all. This sets OMCK = 128 fs, I2S input and serial-port slave (APMS = 0). It also
turns channel-status control off, sets no pre-emphasis (EMPH_N = 1) and flags
the stream as audio (AUDIO_N = 0).

## 5. Amplifier bring-up

1. **Before power:** measure the resistance from each rail to GND (J101 input,
   +5VA, +3V3, +5V_PRE). None may read as a short.
2. **Power it from a bench supply first:** 7.0 V into J101, current limit
   150 mA. Expect about 85 mA (about 42 mA on +5VA, 38 mA on +3V3 and about 4 mA
   ground current in each ADM7150), about 15 mA more with a terminated AES3 cable
   (about 100 mA in all). No bench supply: use a PP3 with a multimeter on its
   200 mA range in series, and disconnect at once if it reads above 150 mA.
3. **Rails:**

   | Net (test point) | Expected |
   | --- | --- |
   | +9V (TP101, after the SS34 reverse-polarity diode) | VIN - 0.3 V |
   | +5VA (TP102) | 5.00 V |
   | +5V_PRE (TP103, behind 10 Ohm) | about 4.95 V |
   | +3V3 (TP104) | 3.30 V |
   | RESET_N (TP404) | about 2.8 V (10 k against the PCM1804's 51 k pull-down); 0 V for 300 ms after power-up or a RESET press |

   Use TP405 (digital) or TP204 (analogue) as the meter's GND.

4. **Bias:** TP202 (BIAS_BUF) climbs slowly to 2.50 V. The 4700 uF divider
   filter charges through 23.5 kOhm (tau about 110 s), so allow about 10 minutes.
5. **Front end:** once the bias has settled, TP201 (PREAMP_OUT) and TP203
   (GUARD_DRV) both sit near 2.5 V DC. Without the J202 bias resistor the input
   floats and drifts, which is expected: fit the resistor.
6. **Overflow flag:** TP301 (OVFL) reads 0 V. It goes high while the left channel
   clips: a voltmeter shows the average, an oscilloscope each event. There is no
   LED for it (battery use).
7. **Clocks and output (oscilloscope, ground on TP405):** 24.576 MHz on TP401
   (MCLK_ADC), 12.288 MHz on TP402 (BCK, 64 fs) and 192 kHz on TP403 (LRCK). No
   BCK and LRCK at all means SW302-3 (S/M) is ON: turn it OFF and press RESET. If LRCK runs at another rate, compare SW302's OSR switches with
   the master-mode table in the PCM1804 data sheet (the default is OSR2..0 = 111
   for quad rate with SCKI = 128 fs), then press RESET. The AES3 output gives about 3.3 Vpp into 110 Ohm between J401 pins
   4 and 5 (the blue pair); the source impedance is 111 Ohm (2 x 22 Ohm plus the
   CS8406 drivers).
8. **To the PC:** connect an AES3 input set to 192 kHz through an RJ45-to-XLR
   adapter (pin 4 to XLR 2, pin 5 to XLR 3, shield to XLR 1), or an S/PDIF
   coaxial input through a 110 Ohm to 75 Ohm balun, then run
   the capture (see `software/README.md`):

   ```bash
   cd software && python -m pip install -e ".[all]"
   python -m elara capture --list-devices
   python -m elara capture first.h5 --device N --duration 600
   ```

   `N` is the interface's index from the device list. A synthetic recording tests
   the analysis chain without any hardware:

   ```bash
   python -m elara simulate demo/sim.wav --duration 60
   python -m elara analyse demo/sim.wav
   ```

## 5a. Running on a battery (the first build)

The receiver runs from any 6.98-13 V source on J101 (under load a battery may run
down to about 6 V before it counts as empty); the PSU can come later. J101 has
an SS34 reverse-polarity diode behind it and an SMAJ13A clamp after that, so a
wrongly wired lead does no harm. Keep the input at 13 V or less (a PP3, 6-8 AA
cells, a 3S Li-ion pack): above that the TVS starts to conduct. Never run it from a
battery that sits on its charger. A brown-out supervisor (U303) holds the ADC and
the AES3 transmitter in reset while +5VA is below 4.66 V and for 300 ms after it
recovers, so a sagging battery cannot leave them in an undefined state.

**Lead:** a 9 V snap (or a 6 x AA holder) crimped into a Micro-Fit 43645-0200
receptacle with two Micro-Fit crimp terminals 43030-0007 (`bom/mechanical_bom.csv`
W3; they need a Micro-Fit crimp tool, O4): red to pin 1 (VIN_RAW), black to pin 2
(GND). Check the polarity with
a meter at the plug before the first connection. There is no power switch: the
plug is the switch.

**How long it lasts.** The board draws about 100 mA at J101 (about 42 mA on +5VA,
53 mA on +3V3 including 15 mA of AES3 line current, and about 4 mA ground current
in each ADM7150). The ADM7150-5.0 needs about 5.5 V at J101 (5.0 V, its dropout
and the SS34); below about 6 V its supply rejection falls, so treat 6 V under load
as empty. Estimates from typical discharge curves, scaled to ~100 mA (measure your
own):

| Source | Usable to 6 V | Notes |
| --- | ---: | --- |
| 9 V PP3, alkaline | about 2.5-3.5 h | voltage sags steadily; good enough for a first test |
| 9 V PP3, lithium (e.g. Energizer L522) | about 5.5-6 h | flat ~7.5 V for most of its life |
| 2 x PP3 lithium in parallel (two leads into one plug) | about 11 h | only identical, fresh cells |
| 6 x AA alkaline holder (9 V) | about 18-22 h | the best runtime per euro |
| 6 x AA NiMH (7.2 V) | about 16-18 h | rechargeable; 7.2 V is enough |

A battery is also the quietest supply there is: no mains anywhere, so it makes
the best reference for judging the PSU later. Record a few hours on a battery
before connecting the PSU, and compare the two noise floors.

**Each time you connect power**, the bias network needs about 10 minutes to settle
(section 5, step 4) before the recording is meaningful.

## 6. PSU bring-up

The PSU has a **mains primary** (IRM-05-15, F1, RV1, J1). Test it only in its
closed, earthed enclosure on mains, and bond PE before anything else. Only the
15 V bench steps 1-4 below are done with the lid off.

0. **Mechanical first:** the two LM317s (U1, U2) must be **bolted to the
   aluminium base** of the PSU box, each with an insulating pad and a shoulder
   washer, *before* their legs are soldered, so the legs are not stressed. This
   is required, not optional: at a cold start or with a shorted bucket U1
   dissipates about 2.25 W for minutes. Both tabs are live (U1's is CC_SET, U2's
   is CHG) and the base is PE / GND_C, so check with a meter that neither tab
   touches the base. The pad and washer parts are not in the BOM yet (open check
   in `STATUS.md`). Mount the board on **metal standoffs at H1/H3**
   (the plated PE holes, mains end) and **nylon standoffs and nylon screws at
   H2/H4** (receiver end). A metal standoff at H2/H4 would tie the receiver side
   to PE through the box. C16 is a 12.5 x 20 mm can; the EDLCs stand upright.
   Seat them flush and stake C16 and the EDLC bank with MS-polymer (B13a).

1. **Before mains:** feed 15 V from a bench supply into the module's DC output
   pins, current limit 0.3 A, with the IRM-05-15 not yet fitted. Check the
   charger: constant current 0.2 A into empty cells, then the voltage levels off
   at the 10.76 V set point on CHG
   (R3 120 R / R4 909 R; the 10.5 mA divider keeps the LM317 above its minimum
   load). Anything higher overcharges the 2.7 V cells: check R3 and R4 (an open
   R4 or a shorted U2 puts 3.0-3.3 V on each cell, and nothing on the board
   clamps it). Only the green LED on the charger side lights. There is
   deliberately no LED on the receiver side. Test points: TP1 CHG_D, TP2 +12V_C,
   TP3 SWAP, TP4 GND_C (charger side); TP5 LOAD_P, TP6 VREG, TP7 GND (receiver
   side).
2. **Buckets:** each bucket is 4 x 10 F in series (2.5 F). From empty, it takes
   about 2 minutes at 0.2 A to reach 10 V (about 4.3 minutes from cold to the
   first valid amplifier rails), and with no load it then floats near 10.3 V
   behind its two SS34s (charger leg and negative leg: 2.6 V per cell). The
   balancing resistors take about 14 h to even out the cells, so pre-charge each
   EDLC to about 2.5 V before assembly if you can. Check the balancing: the four cells
   should read within about 0.1 V of each other, and none above 2.7 V.
3. **Swap:** the relays click every ~15 s (CD4060). Each click moves the load to
   the other bucket.
4. **Output:** J2 gives 6.98 V (LT3045, current limit about 0.3 A). Measure it
   through a full swap cycle under a 100 mA load. If you have a shunt and a
   scope, measure the current between GND and GND_C during the swaps and write
   it down (open check in `STATUS.md`).
5. **Then fit the IRM-05-15 and repeat on mains**, in the closed, earthed box.
   Fit the GDT between PE and the receiver GND first (`STATUS.md`): the reed
   contacts only stand off about 200 V when open.

**Service warning:** the two buckets hold about 2 x 125 J. Discharge them before
working on the board, even with the mains unplugged.

A battery of up to 13 V can feed the amplifier's J101 directly instead of the
PSU (section 5a). The amplifier has its own reverse-polarity diode and a 13 V
TVS. It has no LEDs, so
nothing drains the battery needlessly: check the rails at the test points with a
voltmeter instead.

## 7. Installation notes

- Earth the receiver GND locally at the mast, and use an insulated antenna.
- J401 is a shielded RJ45 whose face sits 1.2 mm inside the right wall; the STP
  plug goes in through the 20 x 16 mm notch. The jack's shell is the AES3 cable
  shield, isolated from GND: it must never touch the wall. Leave C406 (10 nF RF
  bond) unfitted unless RF tests ask for it; the DC isolation stays either way.
- AES3 runs on the blue pair (pins 4 and 5, the same in T568A and T568B); its
  polarity does not matter. The other pairs are unconnected (kept for v2 control
  signals, which must be isolated too).
- Cables follow PLAN section 5. The mains cable is a screened 3-core cable with
  its screen grounded at the mains entry point (MAINS_CABLE.md). The AES3 cable is
  shielded Cat5e/6 with its shield grounded at the indoor end only. The
  PSU-to-amplifier lead is a shielded pair into the Micro-Fit.

## 8. Debugging

Work from the supply towards the output; each step depends on the one before.

| Symptom | Likely cause | Check / fix |
| --- | --- | --- |
| Current above 150 mA, or the supply limits | solder bridge, a part the wrong way round (SMAJ13A, D101, an LDO, U201-U203, U303) | power off; feel for a warm part with a finger after a few seconds on; check the orientation against the iBOM |
| No current at all | D101 reversed, or a reversed battery lead | measure VIN_RAW at J101 and +9V after D101 |
| +9V fine, +5VA or +3V3 missing | ADM7150 exposed pad (pin 9, GND) not soldered, a REF/BYP capacitor missing, a shorted output | reflow the pad with hot air; measure the rail's resistance to GND with power off |
| +5VA fine, +5V_PRE low (more than 0.2 V below) | something on the preamp rail draws current (10 Ohm feed: 0.1 V per 10 mA) | U201/U202/U203 orientation; a bridge at an SOT-23-5 |
| TP202 BIAS_BUF not 2.50 V after 15 min | 4700 uF reversed or leaky, divider resistor wrong, U203 (bias buffer) | measure the divider midpoint against BIAS_BUF |
| TP201 PREAMP_OUT stuck at a rail | J202 not fitted (the input floats), contamination on the guard island, guard loop oscillating | fit J202; re-clean the island (section 3, then dry 1 h at 50 °C); look at TP203 with a scope: it must be quiet DC |
| TP201 swings by volts at 50 Hz | strong mains field: shield lid off, the antenna lead unscreened, the PSU's mains too close | close the shield; try on battery outdoors, away from buildings |
| TP201 noisy, hissy, or drifts with breath or hand | leakage on the femtoamp island, humidity | re-clean with fresh IPA, no flux residue; keep the box sealed with a desiccant bag |
| No 24.576 MHz at the oscillator | Y402 orientation, OE (pin 3) not high, or both Y401 and Y402 fitted | fit only one; check +3V3 at its supply pin |
| TP404 RESET_N stays at 0 V | +5VA below 4.66 V (battery flat: the 5 V LDO needs about 5.2 V in), SW301 shorted, R306 open or missing, R307 the wrong value | measure +5VA at TP102 and the U303 SENSE pin (0.435 V at 5.0 V) |
| No BCK / LRCK at all (TP402 / TP403 flat) but 24.576 MHz on TP401 | SW302-3 (S/M) ON puts the ADC in slave mode, and the CS8406 is a slave too | turn SW302-3 OFF, press SW301 RESET |
| PC sees no lock or the wrong rate, LRCK fine at 192 kHz | SW401-2 (HWCK1) ON: the CS8406 then expects 256 fs | SW401 = 1 ON, 2 OFF (HWCK = 01, 128 fs), press SW301 RESET |
| LRCK not 192 kHz | SW302 OSR/mode switches | set them per section 4 with power off, or press SW301 RESET afterwards |
| The PC does not lock to the AES3 stream | the input cannot do 192 kHz, SW401 mode switches, the wrong pair in the RJ45 | test with an input known to take 192 kHz; AES3 is pins 4/5 (blue pair); try the S/PDIF balun |
| TP301 OVFL often high | the input clips: too much 50 Hz or a local interferer | move the antenna away from wiring, earth the receiver locally (MOUNTING.md section 6) |
| Recording fine but Schumann peaks missing | local noise above the natural background | record at night, on battery, far from mains; compare with `python -m elara simulate` |

Useful habits: write down the current drawn and the TP voltages at each power-up
(a drift over weeks shows a leaking capacitor or contamination early), and keep one
known-good recording as a reference.
