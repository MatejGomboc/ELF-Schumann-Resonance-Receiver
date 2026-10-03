# ELARA -- assembly and bring-up (rev 0.2)

This guide covers a hand-soldered prototype. Part numbers and prices are in `bom/`.
Gerbers, drill files, pick-and-place, PDFs and renders are in `PCB/<board>/fab/`.

## 1. What to order

| Item | Files | Fab options |
| --- | --- | --- |
| Antenna amplifier PCB, 200 x 100 mm, 4 layers | `PCB/antenna_amplifier/fab/antenna_amplifier_gerbers.zip` | 1.6 mm FR4, 1 oz, **ENIG** (flat pads for the SSOP/TSSOP parts and flat wall strips), any mask colour, "remove order number" |
| Two-bucket PSU PCB, 150 x 90 mm, 2 layers | `PCB/acdc_converter/fab/acdc_converter_gerbers.zip` | 1.6 mm FR4, 1 oz, HASL is fine |
| Air-gap plate PCB, 64 x 64 mm + two 7 mm solder tongues, 2 layers | `PCB/plate_capacitor/fab/` | 4 plates (2 capacitors x 2 plates); order 5 or 10 |
| Components | `bom/antenna_amplifier_bom.csv`, `bom/psu_bom.csv`, `bom/extras.csv` | buy about 10 % spare 0603 parts |
| Mechanics | `mechanical/` (STEP, DXF), `bom/mechanical_bom.csv` | aluminium, **not anodised** (the contact faces must conduct) |

Check the open items in `STATUS.md` before ordering (a few ordering codes and the
transformer pin numbering).

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
   (24.576 MHz MEMS oscillator, SOT23-5), U301 LMP7715 and the SOT-23 buffers
   U202/U203. Y401 is the no-lead alternative to Y402, wired to the same nets:
   leave it empty unless you fit it *instead of* Y402. Never fit both.
   Check pin 1 on each part against the silkscreen dot.
2. **ADM7150 regulators (U101, U102):** solder the eight pins, then turn the board
   over. Heat the three vias under the exposed pad and feed solder until it wicks
   through.
3. **Passives**, one compartment at a time: 03 DIGITAL, then 02 ANALOG, then
   01 INPUT. Every part has its reference on the silkscreen right next to it
   (rows of parts have rows of labels); only J201 and J202 on the bare guard
   island have none. The assembly drawing `fab/antenna_amplifier_assembly_top.pdf`
   and the interactive BOM give every reference too.
4. **U201 LMP7721 last among the SMD parts.** Hold it by the body, never by the
   pins, and wear the wrist strap.
5. **Through-hole parts:** DIP switches SW302/SW401, the reset button SW301 and
   the test points (TP201-TP204, TP301). Then TR401 (S22083), J101 (power) and
   J401 (the shielded RJ45 for the AES3 cable). Keep J401 square to the board
   edge: it lines up with the wall notch. Then the electrolytics C101 and C207
   (check the polarity) and the film capacitors C301 and C202, which go on last.
6. **Input island:** J201 is the PTFE turret, which takes the antenna lead from
   below. J202 is the bias-resistor link: solder the 1-100 GOhm resistor between
   the two J202 pins, with its body in the air and not touching the board.

### Cleaning the input (do not skip this)

Flux residue and fingerprints on the guarded island create leakage paths and
tiny galvanic cells, which ruin the femtoampere input
([ADI AN-1373](https://www.analog.com/en/resources/app-notes/an-1373.html),
[ADA4530-1 data sheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ADA4530-1.pdf)).

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
the CS8406 pins low. Change switches with the power off, or press RESET afterwards.

**SW302 -- PCM1804 mode**

| Switch | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pin | FMT0 | FMT1 | S/M | OSR0 | OSR1 | OSR2 | BYPAS | -- |
| Default | ON | OFF | ON | ON | ON | ON | ON | OFF |

This makes the ADC the master (S/M = 1) with SCKI = 128 fs (OSR = 111), I2S
format (FMT = 01) and the digital high-pass filter off (BYPAS = 1). The high-pass
filter must stay off: the Schumann band starts at a few hertz.

**SW401 -- CS8406 hardware mode**

| Switch | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pin | HWCK0 | HWCK1 | SFMT0 | SFMT1 | APMS | CEN | EMPH_N | AUDIO_N |
| Default | ON | ON | ON | OFF | OFF | OFF | ON | OFF |

This sets OMCK = 128 fs, I2S input and serial-port slave (APMS = 0). It also
turns channel-status control off, sets no pre-emphasis (EMPH_N = 1) and flags
the stream as audio (AUDIO_N = 0).

## 5. Amplifier bring-up

1. **Before power:** measure the resistance from each rail to GND (J101 input,
   +5VA, +3V3, +5V_PRE). None may read as a short.
2. **Power it from a bench supply first:** 7.0 V into J101, current limit
   150 mA. Expect about 80 mA (roughly 40 mA each on +5VA and +3V3), a few mA
   more with a terminated AES3 cable.
3. **Rails:**

   | Net | Expected |
   | --- | --- |
   | +9V (after the SS34 reverse-polarity diode) | VIN - 0.3 V |
   | +5VA | 5.00 V |
   | +3V3 | 3.30 V |
   | +5V_PRE (behind 10 Ohm) | about 4.95 V |

4. **Bias:** TP202 (BIAS_BUF) climbs slowly to 2.50 V. The 4700 uF divider
   filter charges through 23.5 kOhm (tau about 110 s), so allow about 10 minutes.
5. **Front end:** once the bias has settled, TP201 (PREAMP_OUT) and TP203
   (GUARD_DRV) both sit near 2.5 V DC. Without the J202 bias resistor the input
   floats and drifts, which is expected: fit the resistor.
6. **Overflow flag:** TP301 (OVFL) reads 0 V. It goes high while the left channel
   clips: a voltmeter shows the average, an oscilloscope each event. There is no
   LED for it (battery use).
7. **Clocks and output (oscilloscope):** 24.576 MHz at the oscillator and LRCK
   at 192 kHz. The AES3 output gives about 3 Vpp into 110 Ohm between J401 pins
   4 and 5 (the blue pair).
8. **To the PC:** connect an AES3 input set to 192 kHz through an RJ45-to-XLR
   adapter (pin 4 to XLR 2, pin 5 to XLR 3, shield to XLR 1), or an S/PDIF
   coaxial input through a 110 Ohm to 75 Ohm balun, then run
   `python -m elara capture` (see `software/README.md`). A synthetic recording
   from `python -m elara simulate` tests the analysis chain without any
   hardware.

## 6. PSU bring-up

The PSU has a **mains primary** (IRM-05-15, F1, RV1, J1). Test it only in its
closed, earthed enclosure, and bond PE before anything else.

0. **Mechanical first:** bolt the two LM317s (U1, U2) flat onto their copper
   areas with an M3x8 screw, washers and nut each *before* soldering their legs,
   so the legs are not stressed. Mount the board on **metal standoffs at H1/H3**
   (the plated PE holes, mains end) and **nylon standoffs and nylon screws at
   H2/H4** (receiver end). A metal standoff at H2/H4 would tie the receiver side
   to PE through the box. C16 is a 12.5 x 20 mm can; the EDLCs stand upright.

1. **Before mains:** feed 15 V from a bench supply into the module's DC output
   pins, current limit 0.3 A, with the IRM-05-15 not yet fitted. Check the
   charger: constant current 0.2 A into empty cells, then constant voltage
   10.9 V. Only the green LED on the charger side lights. There is deliberately
   no LED on the receiver side.
2. **Buckets:** each bucket is 4 x 10 F in series (2.5 F). From empty, it takes
   about 2 minutes at 0.2 A to reach 10.6 V. Check the balancing: the four cells
   should read within about 0.1 V of each other.
3. **Swap:** the relays click every ~15 s (CD4060). Each click moves the load to
   the other bucket.
4. **Output:** J2 gives 6.98 V (LT3045). Measure it through a full swap cycle
   under a 100 mA load.
5. **Then fit the IRM-05-15 and repeat on mains**, in the closed box.

A 9-15 V battery can feed the amplifier's J101 directly instead of the PSU. The
amplifier has its own reverse-polarity diode and a 15 V TVS. It has no LEDs, so
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
