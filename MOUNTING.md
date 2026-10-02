# ELARA -- mechanical assembly and site mounting (rev 0.2)

This guide takes you from machined parts to a working outdoor unit on site. It
covers the shield, the PSU box, the plate capacitors, the outdoor box, the
antenna and earthing, and commissioning. Soldering and bring-up of the boards
are in [ASSEMBLY.md](ASSEMBLY.md). Part numbers and drawings are in
[mechanical/README.md](mechanical/README.md), and local suppliers in
[mechanical/SUPPLIERS_SI.md](mechanical/SUPPLIERS_SI.md). The mains feed is in
[MAINS_CABLE.md](MAINS_CABLE.md).

```text
                         antenna (T: ~10 m vertical, ~15 m top wire)
                               |
   +---------------------------|----------- outdoor box (Fibox ARCA 403015) ---+
   |   [ plate capacitors C_A, C_B on the POM base ]   <- M12 gland (top)      |
   |   [ amplifier shield: 3 compartments, lid on the mounting plate ]         |
   |   [ PSU box: two-bucket supply ]                                          |
   +----- M20 mains gland --------------------------------- M16 AES3 gland ----+
            |                                                  |
   shielded mains cable (MAINS_CABLE.md)          AES3 110 Ohm STP to the indoor PC
```

## 1. Tools and consumables

- Hex keys 2 and 2.5 mm, and a torque screwdriver (0.5-1.5 N·m).
- An M3 tap and holder, in case a thread needs chasing.
- A flat reference surface (glass or a surface plate) and P240 / P400 wet
  abrasive paper, for lapping the shield frame.
- A multimeter with a milliohm range, or a 4-wire method, and an LCR meter
  (100 kHz range, pF resolution) for the plate capacitors.
- IPA (99 %), lint-free wipes, nitrile gloves.
- Cable ties (UV-stabilised), ferrule crimper, heat-shrink, silica-gel
  desiccant bag.
- For the site: spade, earth rod and clamp (section 6), a ladder or mast
  hardware, and insulators for the antenna wire.

## 2. Amplifier shield

Parts A1-A9 are listed in `mechanical/README.md` section 1. The frame is 7 mm
aluminium bars sitting on the exposed 7 mm GND strips of the board.

1. **Check the parts.** Every contact face must be bare metal: **no anodising
   or paint**. Deburr all holes. The right-hand end bar (A2) carries the AES3
   notch and the BNC notch, and the top long bar (A1) the Micro-Fit notch.
   All three are notches down to the PCB face, not holes.
2. **Build the frame.** Join the six bars with the 16 M3x16 socket caps on
   the flat surface, snug but not tight. Press the frame down so all bottoms
   lie on the surface, then tighten crosswise to **1.0 N·m**.
3. **Check and lap the bottom face.** This face is the RF seal against the GND
   strip. With the frame bottom-down on glass, a 0.05 mm feeler must not enter
   anywhere. If it does, lap on P240 then P400 abrasive paper on the glass with
   figure-of-eight strokes until it doesn't. Clean with IPA.
4. **Fit the PTFE feed-through bush** into the tray's Ø10 hole from the
   outside, flange out. Touch it only with gloves.
5. **Stack it, upside down:** frame (lid side down) on the bench, then the
   assembled and cleaned PCB (component side down, so the walls land on the
   strips), then the tray (A5) on top.
   - The Micro-Fit, the AES3 header and the BNC must sit in their notches.
   - Look into the BNC notch: the nut and barrel must not touch the bar (the
     shell is the isolated S/PDIF return).
   - The tray has a small relief pocket in its rim for the Micro-Fit's PCB-lock
     peg: make sure the board sits flat on the tray all round.
6. **Screw it together.** Fit the 24 M3x25 button heads through the tray and
   tighten crosswise in two passes to **0.8 N·m**. Do not use threadlocker; it
   would insulate the thread contact.
7. **Continuity check.** Measure from each wall bar to the GND test point
   (TP204). Expect well under 0.1 Ohm. Also measure from the tray to the frame,
   which should read about the same.
8. **Fit the lid** (A4) with the 24 M3x8 button heads, crosswise, to
   **0.6 N·m**. The lid's four ears are the mounting face (section 5).

Service access is from the tray side. Undo the 24 tray screws and the board
lifts out while the lid and frame stay on the mounting plate.

## 3. PSU box

Parts P1-P6 are in `mechanical/README.md` section 2. The box has 50 x 6 mm
bar walls on a 3 mm base.

1. Screw the four bars together (M3 into the short-bar ends), then onto the
   base with the M3x8 screws.
2. **PE stud first.** Fit the M4 x 20 button head from outside through the
   Ø4.5 hole in the mains-end bar (above the IRM-05, 40 mm up), with a serrated
   washer under the head and, inside, a serrated washer and nut. The mains PE
   ring terminal, a washer, a nut and the lock nut go on later. Scrape any
   coating off under the washers. **PE continuity from the stud to every bar
   and to the base must read under 0.1 Ohm.**
3. Screw the standoffs onto the base: **metal M3x10 at the mains end** (H1/H3,
   the board's plated PE holes) and **nylon M3x10 with nylon screws at the
   receiver end** (H2/H4). Never metal at H2/H4: the receiver side must not
   touch PE. Fit the PSU board, mains end (J1) to the M16 gland.
4. **Check the cells before fitting** C8-C15, the 10 x 31.5 mm EDLCs. Measure
   and match them (within 5 %), and observe polarity. They stand upright with
   about 6.5 mm to spare under the lid.
5. **Fit the glands:** M16 at the mains end (low, in line with J1), M12 at the
   DC-output end (high, in line with J2), with their locknuts inside.
6. **Wire it.** The mains cable goes to J1 (L, N) across the free bay in front
   of it, and its PE conductor to the stud, with a short link from the stud to
   J1 pin 3; see MAINS_CABLE.md. The DC cable's Micro-Fit plug goes into J2
   across the free channel in front of it, and the cable out through the M12
   gland to the amplifier.
7. **Fit the lid** only after the bring-up in ASSEMBLY.md section 6.

## 4. Plate capacitors

The capacitor section is described in `mechanical/README.md` section 3. Each
capacitor is two 64 x 64 plates, copper facing copper, 0.5 mm apart.

1. **Clean the plates.** Wash all 4 plates, washers and discs in IPA and let
   them dry. From here on, handle them only by the edges and with gloves.
2. **Build each capacitor** on its 4 PTFE standoffs on the POM base.
   - Lower plate first, copper up: this is GND.
   - Then the four Ø6 x 0.5 PTFE washers on the copper landing rings, plus
     the loose centre disc.
   - Then the upper plate, copper down, turned over left-right: its two solder
     tongues must sit where the lower plate has none (the four tongues of a
     pair alternate, two on each side).
   - Then the 4 nylon M3x25 screws: finger-tight plus 1/8 turn. Too tight
     bows the plates and raises C.
3. **Measure each capacitor** with the LCR meter at 100 kHz, leads as short as
   possible. Expect **49-52 pF**. Adjust the screws evenly if one reads high,
   which is a sign of bowing.
4. **Wire the section.** Solder only on the tongues.
   - R1 (33k): ANT post to the node1 (C_A upper) tongue on the ANT side.
   - R2 (33k): node1's other tongue to the node2 (C_B upper) tongue across the
     gap, in air.
   - Then the short GND wires from the gap-side tongue of each lower plate down
     to the GND post.
   - Then the node-2 lead from the IN+ turret.
   - Nothing may touch the POM between node pads. Clean with IPA after
     soldering.

## 5. Outdoor box

1. **Mounting plate.** Press the M4 studs into the 8 mm PE-HD plate from the
   back, per `dxf/mounting_plate.dxf`. Fix the plate into the box with
   4 x M4 screws into the floor bosses.
2. **Glands.** M12 (antenna) at the top, M20 (mains) and M16 (AES3) at the
   bottom, from `mechanical/README.md` section 4. Fit them with their seals,
   locknuts inside, and tighten to the gland maker's torque.
3. **Drop the units onto their studs**, top to bottom:
   - capacitor base, directly on the plate
   - amplifier shield, lid down, on 5 mm spacers
   - PSU box, on 5 mm spacers

   Fit the M4 nyloc or knurled nuts.
4. **Wire the box** in this order:
   1. The GND wire from the capacitor GND post to the amplifier tray (ring
      terminal under a tray screw).
   2. The node-2 lead from the IN+ turret through the PTFE bush to J201.
      Keep it at least 10 mm from any metal and free of kinks.
   3. The DC cable from the PSU's J2 to the amplifier's J101: a shielded
      pair. Connect the shield at the amplifier end only, to a tray screw.
      Never connect it to the PSU box, which is on mains PE: that would bond
      PE to the receiver ground and defeat the two-bucket isolation.
   4. The AES3 cable: 110 Ohm STP, wired into the MC 1,5/3-ST-3,81 plug
      (pin 1 shield, 2 hot, 3 cold) outside the box, then pushed into J401
      through the notch. Per PLAN section 5 the far (indoor) end grounds the
      shield, and R414 / C406 stay unfitted.
   5. The mains cable into the PSU box (MAINS_CABLE.md).
   6. The antenna wire, last (section 6).
5. **Dress the cables** with UV-stabilised ties. Give each cable a drip loop
   before its gland, so water runs off below the entry and not along the cable.
6. **Condensation.** Put a fresh silica-gel bag in the box and replace it at
   every visit. A pressure-equalising vent (ePTFE membrane plug, M12) in the
   bottom wall is recommended for a sealed polycarbonate box in the sun.

## 6. Site mounting

**Where.** Choose an open site as far as practicable from mains overhead lines,
transformers, fences with electric energisers and buildings. PLAN section 3.1
sizes the 50 Hz headroom for a power line about 100 m away. Keep trees and
masts well clear of the antenna, because they distort the vertical E-field.

**The antenna** is a Marconi T: about 10 m vertical, with about 15 m of top
wire.
- Use insulated wire on proper insulators at both ends of the top wire.
- The down-lead runs vertically to the M12 gland at the top of the box, with a
  drip loop just above the gland.
- Keep the down-lead away from the mast by stand-off insulators, at least
  30 cm.

**The outdoor box** mounts on a post or wall at the foot of the down-lead,
about 1 m above ground. Keep the antenna gland on top and the other glands at
the bottom, as designed. Fix it through the box's own mounting points; never
drill the lid.

**Local earth.** Drive a copper-clad earth rod (1.5-2 m) next to the box.
- Connect it with a short 6-16 mm² copper conductor to the amplifier's GND:
  the tray or the capacitor GND post.
- This is the receiver's reference earth. Keep it separate from the mains PE,
  which bonds only to the PSU enclosure (MAINS_CABLE.md).
- Measure the earth resistance if you can.

**Lightning.** A tall wire antenna attracts strikes. There is no surge arrester
on the femtoamp input: any practical arrester would add leakage and capacitance
there.
- Disconnect the antenna lead at the box and earth it when thunderstorms are
  forecast, or fit a knife switch to earth at the foot of the down-lead.
- For permanent installations, have a lightning-protection installer advise on
  the mast and the earthing.

## 7. Commissioning

1. With the door open and the antenna **not yet connected**, power up. Check
   the rails and the test points as in ASSEMBLY.md section 5.
2. **Bias reset.** Fit the J202 shunt over the pin tips, above the soldered
   G-ohm resistor. Connect the antenna. Wait about 10 minutes for the 2.5 V
   bias filter to settle (TP202), then **remove the shunt**. The resistor now
   holds the DC operating point against the air-earth current.
3. Check the stream on the PC (`python -m elara capture`). With the software
   notch on, the Schumann peaks near 7.8, 14.3, 20.8 and 27.3 Hz should
   appear within an hour of averaging on a quiet day.
4. Put in a fresh desiccant bag, close the door, and log the date.

## 8. Periodic checks

- **Every 3 months:** replace the desiccant, and look for condensation and
  corrosion on the strips and the plate capacitors.
- **Every year:** check the gland seals, re-torque the shield screws and the
  earth clamp, and measure the plate capacitors again.
- **Relays** (PSU K1/K2) switch about 2 million times a year at the 15 s swap.
  Check them yearly for contact noise, visible as swap-period steps in the
  data.
