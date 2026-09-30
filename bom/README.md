<!-- SPDX-License-Identifier: CERN-OHL-W-2.0 -->

# ELARA -- priced bill of materials

This is a priced BOM and cost estimate for **one hand-soldered ELARA outdoor unit**.
It covers the antenna amplifier, the two-bucket PSU, the enclosures, the plate
capacitors and the internal wiring. The owner builds the enclosures in a local
workshop.

Prices were collected on 30 September 2026. The target is about €300.

## Files

| File | Content |
| --- | --- |
| `antenna_amplifier_bom.csv` | Amplifier BOM, grouped by MPN, plus the bare PCB, stencil and PCB shipping. Generated. |
| `psu_bom.csv` | PSU BOM, grouped by MPN, plus the bare PCB and heatsinks. Generated. |
| `mechanical_bom.csv` | Aluminium, plastics, fasteners, glands, outer box, plate capacitors, wiring, logistics. Maintained by hand. |
| `prices.csv` | MPN → unit price (EUR, ex VAT), buy multiple, supplier, source and confidence. Also holds the alternative parts that the cost-down scenarios use. |
| `extras.csv` | Electronics purchases that are not in a netlist: PCBs, stencil, PCB shipping, heatsinks and optional parts. |
| `build_bom.py` | Regenerates the two electronics CSVs and prints every table in this README. |

```bash
.venv/Scripts/python bom/build_bom.py     # Windows
.venv/bin/python bom/build_bom.py         # Linux / macOS
```

To change a price, edit `prices.csv` (electronics) or `mechanical_bom.csv`
(mechanics), then re-run the script. The script warns about any MPN that has no
price.

### Line status

| Status | Meaning |
| --- | --- |
| `core` | Counted in the totals |
| `DNP` | Listed but not fitted, costs 0 (C406, R414) |
| `no-part` | PCB feature only (H1–H4), costs 0 |
| `optional` | Priced but not counted |
| `site` | Depends on the site (antenna, 100 m cables, indoor interface), not counted |

## Pricing basis -- read this first

* All prices are **EUR excluding VAT**. USD is converted at ×0.92, GBP at ×1.16
  and SGD at ×0.67. German consumer-shop prices that include 19 % VAT are
  divided by 1.19.
* **Quantity-1 prices** are used, because only one unit is built. The exception
  is the cheap MLCCs and the 17 × 10 k pull-downs, which are bought in tens. The
  "rounding" line covers the extra pieces.
* The distributor sites could not be opened from this environment. Every price
  therefore comes from a **web-search result snippet** or is a **catalogue
  estimate** (typical 2025–26 pricing). The `confidence` column says which.
  * Snippets are the basis for **64 %** of the core total.
  * Estimates are the basis for **36 %**. This includes the PCB prices, which
    need a real JLCPCB quote.
  * Check every line in the basket before ordering.
* The **Mouser / DigiKey** order is well over €50, so EU delivery is free. JLCPCB
  shipping is a separate line. The metal, plastic and fastener orders share a
  €15 shipping allowance.

## Totals

| Assembly | EUR ex VAT |
| --- | ---: |
| Antenna amplifier: components | 107.24 |
| Antenna amplifier: 4-layer FR4 ENIG PCB (lot of 5), stencil, JLCPCB shipping | 56.60 |
| PSU: components and heatsinks | 76.85 |
| PSU: 2-layer PCB (lot of 5) | 8.30 |
| Amplifier shield (aluminium, PTFE bush, fasteners) | 54.24 |
| PSU enclosure (aluminium, glands, fasteners) | 24.95 |
| Plate capacitors (PCBs, 33 k resistors, POM/PTFE parts) | 23.72 |
| Outer enclosure (Fibox ARCA 403015, PE-HD plate, studs, glands) | 140.26 |
| Internal wiring | 6.70 |
| Materials shipping allowance | 15.00 |
| Rounding up to buy multiples | 2.16 |
| **Grand total (reference build)** | **516.02** |
| Incl. 22 % VAT (example; use your own rate) | 629.54 |
| **Against the €300 target** | **+216.02 (ex VAT)** |

The M3x8 screws are shared between the amplifier and PSU enclosures, so they
are counted in the amplifier-shield line.

**Not counted:**

* Optional lines, €94.66:
  * 1 GΩ glass bias resistor
  * 10 GΩ chip bias resistor
  * spare LMP7721
  * bead-blasting
  * conformal coating
  * consumables
  * crimp tool
* Site-dependent lines, €476:
  * about 30 m of insulated antenna wire plus insulators
  * 100 m of Cat6 S/FTP for AES3
  * 100 m of shielded mains cable (about €250 on its own)
  * a USB audio interface with S/PDIF input
  * an AES3-to-S/PDIF adapter

**One-off costs.** About €82 of the reference build is one-off:

* the PCB lots of 5
* the stencil
* PCB shipping
* the materials shipping allowance

A second unit, built from the spare boards, costs roughly €80 less.

## Top 10 cost drivers

| # | Assembly | Refs | Item | Qty | EUR | Confidence |
| --- | --- | --- | --- | ---: | ---: | --- |
| 1 | mechanical | B1 | Fibox ARCA 403015 outer box | 1 | 120.31 | search snippet |
| 2 | amplifier | PCB-AMP | JLCPCB 4-layer 200 × 100 FR4 ENIG, 5 pcs | 1 | 40.00 | catalogue estimate |
| 3 | psu | C8–C15 | EDLC 10 F 2.7 V (Eaton HV class) | 8 | 33.92 | snippet, similar part |
| 4 | mechanical | A1–A3 | 60 × 8 EN AW-6082 flat bar, 1 m | 1 | 28.74 | search snippet |
| 5 | mechanical | L1 | materials shipping allowance | 1 | 15.00 | catalogue estimate |
| 6 | amplifier | C202 | WIMA MKS4 100 µF PET (Cg) | 1 | 14.02 | search snippet |
| 7 | mechanical | A5 | 15 mm 6082 plate for the tray | 1 | 10.00 | search snippet |
| 8 | amplifier | J402 | Amphenol 031-6575 R/A BNC | 1 | 9.43 | search snippet |
| 9 | amplifier | SHIP-JLC | JLCPCB economy shipping | 1 | 9.20 | catalogue estimate |
| 10 | psu | U5 | LT3045EMSE | 1 | 8.44 | search snippet |

The table ranks single BOM lines. Some part families add up to more when
counted together:

* ADM7150 ×2: €15.94
* G6K-2F-Y relays: €8.28
* IRM-05-15: €7.58
* LMP7715 ×3: €7.26
* PCM1804: €6.27
* LMP7721: €6.02
* CS8406: €5.89

The active parts (ICs, AC-DC module, relays, diodes) come to about €70 in total.

## Cost-down options

The scenarios are cumulative and are computed by `build_bom.py` from the same
price table.

### Recommended set -- the golden middle

These changes do not measurably affect the signal chain.

| Step | Δ EUR | Running total | Performance impact |
| --- | ---: | ---: | --- |
| Reference build | | 516.02 | |
| Outer box: **Gewiss GW44220** (IP56, deep screwed lid, inner 380 × 300 × 180) instead of the Fibox ARCA 403015 | −72.31 | 443.71 | IP56 instead of IP66, screwed lid instead of a lock. Technopolymer instead of PC. More room for cable bends and the BNC. Re-drill the plate fixings. |
| EDLC: **generic 10 F 2.7 V radial cells**. Buy 10 and match 8 to within 5 % | −13.92 | 429.79 | None if matched. Check the leakage against the 5k1 balancing resistors. |
| Aluminium: **6060 bar or 60 × 8 offcuts** bought by weight | −14.74 | 415.05 | None electrically. 6060 is softer, so tap the M3 holes with care. |
| **Leave the S/PDIF coax path unfitted** (TR402, J402, R415–R417, C407) | −14.95 | 400.10 | None on AES3, which is the 100 m path. There is no coax bench port, but the footprints stay and can be fitted later. |
| **Fit the J202 bias resistor** (Ohmite HVC1206Z1008KET, 10 GΩ) | +6.04 | 406.14 | Needed for a DC operating point (`simulations/spice/README.md` §5). It is a cost *increase*. |
| **Recommended build** | | **406.14** | €495 incl. 22 % VAT |

### Further cuts

These are cumulative on top of the recommended set, and each one costs
something.

| Step | Δ EUR | Running total | Performance impact |
| --- | ---: | ---: | --- |
| PSU: drop the two-bucket stage, so the IRM-05-15 feeds the LT3045 directly. Removes K1/K2, C8–C15, the charger, timer and heatsinks | −39.15 | 366.99 | **Not recommended.** It loses the galvanic isolation that the PSU exists for. SMPS leakage and common-mode hash reach the outdoor ground all the time. Needs a board change (link). |
| Amplifier PCB: lead-free HASL instead of ENIG | −15.00 | 351.99 | GND strips less flat (lap the wall faces). Tin on the unmasked guard island. Small. |
| No stencil (iron and hot air, solder the exposed pads through vias) | −7.40 | 344.59 | Assembly effort only. |
| Unbranded IP65 ABS box instead of the Gewiss | −20.00 | 324.59 | UV resistance and IP rating unverified. Shorter outdoor life. |
| +3V3 digital LDO: ADP7118ARDZ-3.3 instead of ADM7150 | −5.37 | 319.22 | Digital rail only, 11 µV rms. **Pinout differs**, so the schematic and layout change. |
| DIP switches replaced by wire links (modes fixed at build) | −1.78 | 317.44 | Modes can no longer be changed without soldering. |
| Test points replaced by bare pads | −1.20 | 316.24 | Probing is less convenient. |

### Where the €300 target stands

Even with every change above, the build comes to about **€316 ex VAT**. The
full design comes to **€516**. The golden middle is **about €406 ex VAT
(about €495 incl. VAT)**.

The €300 target is only within reach if you also do one or more of these:

* collect the metal and plastics locally (−€15)
* buy the commodity parts from LCSC (below, about −€10 to −€15 net)
* accept the not-recommended PSU simplification

At one-off quantities, the ALU shield, the IP-rated box and the PCB lot
overheads (about €82) set a floor near €300 however much the electronics are
trimmed.

### Other options

**FR4 vs Rogers.** The reference uses FR4, which PLAN §4.3 calls the fallback.

* **Rogers RO4350B for the whole 4-layer board adds about €360.** This is a
  catalogue estimate: JLCPCB Rogers starts at US$99.5 for 5 pcs within
  100 × 100 mm, and 200 × 100 × 4 layers is estimated at US$350–500. It
  would break the budget on its own.
* A Rogers/FR4 hybrid (CN0407 style) is not much cheaper for 5 pieces.
* The golden middle is FR4 plus the features that already keep the substrate
  out of the femtoampere path:
  * the node2 lead lands on the **PTFE turret J201** from the PCB bottom, so
    the input is air-wired
  * guard rings on every layer
  * no solder mask over the guard island
  * thorough flux removal, then acrylic coating outside the island
* Rogers is worth revisiting only if field leakage measurements show the FR4
  island limiting the noise floor.

**Cheaper outer box.**

| Box | Price (ex VAT) |
| --- | --- |
| Fibox ARCA 403015 (reference; IP66/IK10, lockable, UV-stable PC) | €120 |
| Gewiss GW44220 (inner 380 × 300 × 180, IP56) | ≈ €48 |
| Gewiss GW44210 (380 × 300 × 120, IP56). Only 120 mm deep: check the 70 mm shield + 13 mm plate/spacer stack and the gland domes | ≈ €46 (Italian shops, VAT removed) |
| Unbranded ABS | ≈ €28 |

Whatever box you choose, it must stay plastic, because the E-field antenna has
to see through it.

For the PSU box, the bar-built box costs about €25 against €25–35 for a
Hammond 1590E (mechanical README estimate). There is no saving there, so keep whichever suits the workshop.

**Fewer DIP switches.** SW302 and SW401 cost only €1.78. Replacing the
17 × 10 k 0.1 % thin-film logic resistors (the DIP pull-downs R306–R312 and
R404–R411, plus R305 and R403) with 1 % thick film saves about another €2.
Both changes are harmless, because these are static logic pins, not signal
path. Both are worth doing only if the modes
are frozen.

**Transformer choice (applied).** The **Newava S22082 could not be found at any
distributor**, so rev 0.2 fits a second S22083 for S/PDIF. The options were:

* Fit a second **S22083** (1:1, 225 µH, same price). The 75 Ω source
  impedance is set by R415–R417, not by the transformer.
* Use a Pulse PE-65612-class part. This needs a footprint change.
* Leave the coax path unfitted, as in the recommended set.

Keep the S22083 on AES3: its galvanic isolation is part of the
reverse-shielding scheme.

**Film-capacitor alternatives.**

* **C202 (Cg, WIMA MKS4 100 µF, €14.02): keep it.**
  * An electrolytic (even a low-leakage or bipolar one) breaks the
    signal-path rule. It would put leakage current through Rf (DC offset) and
    excess LF noise into the gain network at SR1, where Cg's 203 Ω reactance
    is comparable to Rg.
  * Scaling to Rg = 10 k and Cg = 10 µF would cut the capacitor cost. But it
    raises Rg's thermal noise from 4.1 to 12.9 nV/√Hz, twice the LMP7721's
    6.5 nV/√Hz.
  * Buying it from TME (the price used) rather than Mouser is the only saving.
* **C301 (C_out, MKS4 10 µF, €5.45).** Two options:
  * Buy it in the same TME order: expect about €3–4.
  * Use a KEMET R60-class PET 10 µF: about €2, catalogue estimate. Check the
    pitch against the 22.5 mm footprint.

  Both are the same PET dielectric, so there is no performance change. This
  saves €2–3.

**Sourcing.** LCSC quantity-1 prices seen in search results:

* LMP7721: US$4.72
* CS8406: US$3.08
* ADM7150-5.0: US$6.51
* Panasonic ERA / Murata GRM passives: a fraction of the Mouser qty-1 prices

Moving the commodity passives and the non-critical ICs saves about €10–15 net
after LCSC shipping. Keep the **LMP7721 from an authorised distributor**
(DigiKey, Mouser or TI.com): fake or reworked electrometer op-amps are not
worth the risk.

**Aluminium shield.** A soldered tinplate fence, as used on RF tuners, instead
of the machined bars and tray saves only about €20 once the offcut price is
used. It gives up the bolted, serviceable, lapped GND-strip seal, so it is not
recommended.

### Upgrades (each against the reference)

| Option | Δ EUR |
| --- | ---: |
| Amplifier PCB in Rogers RO4350B | +360.00 |
| DHL Express instead of economy PCB shipping | +15.80 |
| Spare LMP7721 (recommended for hand soldering) | +6.02 |
| Glass Ohmite RX-1M1007FE 1 GΩ bias resistor | +8.60 (special order, low confidence) |
| Bead-blast + chromate conversion (local) | +15.00 |
| Acrylic conformal coating | +14.00 |

## Verify before ordering

1. **Newava S22083 (x2).** Check the pinout and slot pitch against
   `elara:Transformer_Pulse_4Pin_W7.62mm` (pins 1 and 3 in one row, 7.62 mm apart;
   2 and 4 in slots 7.62 mm away).
2. **SiT1602 ordering code `SiT1602BI-33-33E-24.576000`.** This exact code was
   not found. Per the SiT1602 ordering guide:
   * the first digit after `BI-` is the package: 3 = 3.2 × 2.5 mm, which
     matches the footprint
   * the second digit is the stability: 3 = ±50 ppm
   * `33` is the supply voltage
   * `E` = output-enable pin
   * no suffix = bulk

   Stocked 24.576 MHz variants use other package or voltage codes (for
   example `-12-XXN-`, which is 2.0 × 1.6 mm). Keep the package digit at 3,
   or have DigiKey program the part.
3. **EDLC MPN.** `HV1245-2R7106-R` was not found. The Eaton 10 F 2.7 V HV cell
   is **HV1030-2R7106-R, 10 × 30 mm**, priced here. **Height (resolved):** the
   PSU walls are now 50 × 6 mm bar, which leaves about **38 mm above the PCB**
   on 10 mm standoffs. The 30 mm cells stand upright, and C16 (EEU-FR1C222,
   25–30 mm) and the TO-220 LM317s with clip-on heatsinks fit under the same
   38 mm. The D12.5 footprint takes the 10 mm cells (5 mm lead pitch).
4. **SRF1260-102Y.** Not found; the 1 mH SRF1260 part may be `-102M`. Confirm
   the MPN and the current rating.
5. **WIMA MKS4 100 µF.** Order code MKS4D061007H00KSSD (100 VDC / 63 VAC,
   PCM 37.5). Check the body against the 41.5 × 35 mm footprint, and the
   height against the 52 mm shield walls: the mechanics assume about 49 mm.
6. **EEU-FR1C472.** Order the 16 × 25 mm, P7.5 case, not the 12.5 × 35 mm,
   P5 one.
7. **Amphenol 031-6575.** If you fit it, it is 50 Ω and needs its barrel to
   project at least 13 mm through the 7 mm wall (mechanical README).
8. **ADM7150ARDZ-3.3-R7.** Priced at the DigiKey -5.0 figure; Mouser lists it
   at €12.71. Check which distributor holds the lower price on the day.
9. **Bias resistor.** The Ohmite RX-1M series is a factory special order at
   Mouser, and 10 G and 100 G quotes can reach hundreds of euros. The HVC1206
   10 GΩ is stocked but needs a small 2-pin carrier to plug into J202.
10. **JLCPCB.** Get real quotes for the 4-layer 200 × 100 ENIG board. It is the
    second-largest line and only an estimate. Also check:
    * the unmasked GND strips and guard island in the Gerbers
    * whether the upper and lower 64 × 64 plates are one design or two (two
      designs add €1.84)
11. **Lapp SKINTOP article numbers.** Check 53111000 (M12) and 53111020 (M20),
    and check each gland's clamping range against the real cable diameters.
12. **Fibox ARCA 403015 variant.** The "NO MP" version is enough, because the
    PE-HD mounting plate is made locally.
13. **Mating parts.**
    * Micro-Fit receptacles 43645-0200, crimps 43030-0007, and a crimp tool.
    * Fuse clips FC-203-22 for the 5 × 20 mm 5ST 500-R fuse.
14. **Hand-soldering note.** A hot-air station or hotplate is assumed for:
    * the exposed pads of the ADM7150 ×2 and the LT3045
    * the no-lead SiT1602

    Tools are not included.
