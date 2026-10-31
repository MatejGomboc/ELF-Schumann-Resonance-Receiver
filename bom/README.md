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
| `psu_bom.csv` | PSU BOM, grouped by MPN, plus the bare PCB. Generated. |
| `mechanical_bom.csv` | Aluminium, plastics, fasteners, glands, outer box, plate capacitors, box heater, wiring, logistics. Maintained by hand. |
| `prices.csv` | MPN → unit price (EUR, ex VAT), buy multiple, supplier, source and confidence. Also holds the alternative parts that the cost-down scenarios use. |
| `extras.csv` | Electronics purchases that are not in a netlist: PCBs, stencil, PCB shipping and optional parts. |
| `build_bom.py` | Regenerates the two electronics CSVs and prints every table in this README. |
| `order_lists.py` | Writes the distributor upload files from the BOM CSVs (run after `build_bom.py`). |
| `order/` | Digi-Key, Mouser and Farnell upload files plus `order_all.csv`. Generated. |
| `ORDERING.md` | How to order the electronics: upload files, checks, what to skip for a battery-first build. |
| `PCB_ORDER.md` | PCB fab options and the note to paste into each board order. |

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
| `DNP` | Listed but not fitted, costs 0 (C406, Y401) |
| `no-part` | PCB feature only (H1–H4), costs 0 |
| `optional` | Priced but not counted |
| `site` | Depends on the site (antenna, 100 m cables, indoor interface), not counted |

## Pricing basis -- read this first

* All prices are **EUR excluding VAT**. USD is converted at ×0.92, GBP at ×1.16
  and SGD at ×0.67. German consumer-shop prices that include 19 % VAT are
  divided by 1.19.
* **Quantity-1 prices** are used, because only one unit is built. The exception
  is the cheap MLCCs and the 10 × 47 k pull-downs, which are bought in tens. The
  "rounding" line covers the extra pieces.
* The distributor sites could not be opened from this environment. Every price
  therefore comes from a **web-search result snippet** or is a **catalogue
  estimate** (typical 2025–26 pricing). The `confidence` column says which.
  * Snippets are the basis for **50 %** of the core total (€356.45 of €713.10
    before rounding).
  * Estimates are the basis for **50 %** (€356.65). This includes the PCB prices, which
    need a real JLCPCB quote, and the box heater.
  * Check every line in the basket before ordering.
* The **Mouser / DigiKey** order is well over €50, so EU delivery is free. JLCPCB
  shipping is a separate line. The metal, plastic and fastener orders share a
  €15 shipping allowance.

## Totals

| Assembly | EUR ex VAT |
| --- | ---: |
| Antenna amplifier: components | 109.71 |
| Antenna amplifier: 4-layer FR4 ENIG PCB (lot of 5), stencil, JLCPCB shipping | 56.60 |
| PSU: components | 122.42 |
| PSU: 2-layer PCB (lot of 5) | 8.30 |
| Amplifier shield (aluminium, PTFE bush, fasteners) | 54.24 |
| PSU enclosure (aluminium, glands, fasteners, nylon standoffs) | 27.15 |
| Plate capacitors (PCBs, 33 k resistors, POM/PTFE/alumina parts, PEEK screws, springs) | 35.22 |
| Outer enclosure (Fibox ARCA 403015, PE-HD plate + supports, studs, glands, vent, desiccant, shade roof + brackets) | 187.46 |
| Internal wiring | 6.70 |
| Box heater (STEGO HG 140 30 W, KTO 111 thermostat, DIN rail, terminals, T 4 A fuse, wiring) | 91.30 |
| Materials shipping allowance | 15.00 |
| Rounding up to buy multiples | 1.61 |
| **Grand total (reference build)** | **715.71** |
| Incl. 22 % VAT (example; use your own rate) | 873.17 |
| **Against the €300 target** | **+415.71 (ex VAT)** |

The M3x8 screws are shared between the amplifier and PSU enclosures, so they
are counted in the amplifier-shield line.

**Not counted:**

* Optional lines, €97.91:
  * battery lead parts: a 9 V snap, a 6 x AA holder and a Micro-Fit plug (ASSEMBLY.md 5a)
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
  * a USB audio interface with an S/PDIF coax input (or one with AES3)
  * an AES3-to-S/PDIF balun, or an RJ45-to-XLR adapter for an AES3 input

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
| 2 | psu | K1–K4 | Standex SIL05-1C90-51D reed relay | 4 | 45.24 | search snippet |
| 3 | mechanical | HT1 | STEGO HG 140 30 W PTC box heater (14001.0-00) | 1 | 45.00 | catalogue estimate |
| 4 | amplifier | PCB-AMP | JLCPCB 4-layer 200 × 100 FR4 ENIG, 5 pcs | 1 | 40.00 | catalogue estimate |
| 5 | psu | C8–C15 | EDLC 10 F 2.7 V (Eaton HV class) | 8 | 33.92 | snippet, similar part |
| 6 | mechanical | A1–A3 | 60 × 8 EN AW-6082 flat bar, 1 m | 1 | 28.74 | search snippet |
| 7 | mechanical | HT2 | STEGO KTO 111 NC thermostat (11100.0-00) | 1 | 25.00 | catalogue estimate |
| 8 | mechanical | B11 | 2 mm aluminium sheet for the shade roof | 1 | 18.00 | catalogue estimate |
| 9 | amplifier | C202 | WIMA MKS4 100 µF 63 VDC PET (Cg) | 1 | 15.06 | search snippet |
| 10 | mechanical | L1 | materials shipping allowance | 1 | 15.00 | catalogue estimate |

The table ranks single BOM lines. Some part families add up to more when
counted together:

* SIL05-1C90-51D reed relays ×4: €45.24
* ADM7150 ×2: €15.94
* LT3045: €8.44
* IRM-05-15: €7.58
* CS8406-DZZ: €6.80
* PCM1804: €6.27
* LMP7721: €6.02
* LMP7715 ×2: €4.84
* OPA388: €2.60

These come to €103.73. All active parts together (ICs, oscillator, AC-DC module,
relays, transistors, thyristor, diodes, GDT) come to about €116.

## Cost-down options

The scenarios are cumulative and are computed by `build_bom.py` from the same
price table.

### Recommended set -- the golden middle

These changes do not measurably affect the signal chain.

| Step | Δ EUR | Running total | Performance impact |
| --- | ---: | ---: | --- |
| Reference build | | 715.71 | |
| Outer box: **Gewiss GW44220** (IP56, deep screwed lid, inner 380 × 300 × 180) instead of the Fibox ARCA 403015 | −72.31 | 643.40 | IP56 instead of IP66, screwed lid instead of a lock. Technopolymer instead of PC. More room for cable bends. Re-drill the plate fixings. |
| EDLC: **generic 10 F 2.7 V radial cells**. Buy 10 and match 8 to within 5 % | −13.92 | 629.48 | None if matched. Check the leakage against the 5k1 balancing resistors. |
| Aluminium: **6060 bar or 60 × 8 offcuts** bought by weight | −14.74 | 614.74 | None electrically. 6060 is softer, so tap the M3 holes with care. |
| **Fit the J202 bias resistor** (Ohmite HVC1206Z1008KET, 10 GΩ) | +6.04 | 620.78 | Needed for a DC operating point (`simulations/spice/README.md` §5). It is a cost *increase*. 10 GΩ is the largest stocked value: the floor stays 4.6 dB below the natural background at SR1 and the DC point holds up to 100 pA of air-earth current. 100 GΩ (special order) gives 12.8 dB with an insulated antenna (`simulations/system`). |
| **Recommended build** | | **620.78** | €757.35 incl. 22 % VAT |

### Further cuts

These are cumulative on top of the recommended set, and each one costs
something.

| Step | Δ EUR | Running total | Performance impact |
| --- | ---: | ---: | --- |
| PSU: drop the two-bucket stage, so the IRM-05-15 feeds the LT3045 directly. Removes K1–K4, C8–C15, the charger and timer | −51.58 | 569.20 | **Not recommended.** It loses the galvanic isolation that the PSU exists for. SMPS leakage and common-mode hash reach the outdoor ground all the time. Needs a board change (link). |
| Amplifier PCB: lead-free HASL instead of ENIG | −15.00 | 554.20 | GND strips less flat (lap the wall faces). Tin on the unmasked guard island. Small. |
| No stencil (iron and hot air; the exposed pads with hot air) | −7.40 | 546.80 | Assembly effort only. |
| Unbranded IP65 ABS box instead of the Gewiss | −20.00 | 526.80 | UV resistance and IP rating unverified. Shorter outdoor life. |
| +3V3 digital LDO: ADP7118ARDZ-3.3 instead of ADM7150 | −5.37 | 521.43 | Digital rail only, 11 µV rms. **Pinout differs**, so the schematic and layout change. |
| DIP switches replaced by wire links (modes fixed at build) | −1.78 | 519.65 | Modes can no longer be changed without soldering. |
| Test points replaced by bare pads | −1.50 | 518.15 | Probing is less convenient. |

### Where the €300 target stands

Even with every change above, the build comes to about **€517 ex VAT**. The
full design comes to **€715**. The golden middle is **about €620 ex VAT
(about €756 incl. VAT)**. The mains-side box heater (2026-10-31: STEGO HG 140,
KTO 111 thermostat, DIN rail and terminals on the PSU box lid; it keeps the PCM1804
above −10 °C down to −25 °C outside) adds €91.30, the largest single addition. The anti-microphonics changes from `simulations/mechanics`
(plate supports, PEEK/alumina/spring clamp, solid leads, stiff shade roof on
brackets) add €29.70. The plate-return network (R207, C209, the 10 µF film C210)
adds €8.72. The amplifier reviews' changes (nine bring-up test points, the bias-buffer
resistor, the brown-out supervisor, 22 µF LDO and 2.2 µF REF capacitors, the
SMAJ13A, the OPA388 ADC driver; J202's header dropped) add €6.70. The PSU review's changes (negative-leg Schottkys,
the 0.4 A load-path limiter, a ceramic fuse, test points, the 22 µF LT3045 output
capacitor) add €6.43; the EDLC overvoltage crowbar (TL431B, MMBT3906, MCR100-6 SCR and
their resistors) and the GDT across the charger/receiver barrier add €2.87. The outdoor-box items from the thermal study (ePTFE
vent, desiccant, humidity card, white shade roof) add €29. The four reed relays (2026-10-31, about €45) cost
€37 more than the two G6K relays they replaced, for contacts that switch dry.

**Battery first.** The first build runs the receiver from a 9 V battery and adds
the PSU later. Without the PSU board, its box and the mains-side box heater
(€130.72 + €27.15 + €91.30) the golden middle is about **€386 ex VAT** (the EDLC cut
no longer applies), plus a PP3 and its clip. With no mains there is no heater: the
PCM1804 then sees the outdoor cold (`simulations/thermal`).

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
10 × 47 k 0.1 % thin-film logic resistors (the DIP pull-downs R305 and
R404–R411, and R403 on TCBL) with 1 % thick film saves about another €1.
Both changes are harmless, because these are static logic pins, not signal
path. Both are worth doing only if the modes
are frozen.

**Transformer.** One Newava S22083 (1:1, 225 µH, 2 kV) isolates the AES3
output; its galvanic isolation is part of the reverse-shielding scheme. (The
S/PDIF coax branch with its second transformer is gone.)

**Film-capacitor alternatives.**

* **C202 (Cg, WIMA MKS4 100 µF, €15.06): keep it.**
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
* CS8406 (the CZZ grade; the design uses the -40 °C DZZ): US$3.08
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
| Glass Ohmite RX-1M1007FE 1 GΩ bias resistor (only for a bare antenna above ~100 pA; noisier than 10 GΩ) | +8.60 (special order, low confidence) |
| Bead-blast + chromate conversion (local) | +15.00 |
| Acrylic conformal coating | +14.00 |

## Verify before ordering

1. **Newava S22083 (TR401)** -- checked against Newava's drawing (2026-10-31):
   pins 1-4 10.16 mm along the body, 1-2 5.08 mm across, windings 1-2 and 3-4
   (dots on 1 and 3), < 15 pF between windings, 2000 Vac hipot. The footprint
   `elara:Transformer_Newava_S22083` follows the drawing.
2. **Oscillator.** Y402 is the fitted part: SiT2001BI-S2-33E-24.576000, SOT23-5 and
   leaded, for hand soldering. Its pinout (1 GND, 2 NC, 3 OE, 4 VDD, 5 OUT)
   matches SiTime's SiT2001B pin table (confirmed in the 2026-10-03 audit).
   Y401 (SiT1602, 3.2 × 2.5 mm, no leads) is the do-not-fit
   alternative on the same nets. Fit exactly one of them.
   **SiT1602 ordering code `SiT1602BI-33-33E-24.576000`** (only if you fit Y401). This exact code was
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
3. **EDLC MPN (resolved).** `HV1245-2R7106-R` was not found, so the design now
   specifies the Eaton 10 F 2.7 V HV cell **HV1030-2R7106-R, 10 × 30 mm**. **Height (resolved):** the
   PSU walls are now 50 × 6 mm bar, which leaves about **38 mm above the PCB**
   on 10 mm standoffs. The 31.5 mm (max) cells stand upright with 6.5 mm to
   the lid (`mechanical/fit_check.py`, with a 10.5 × 31.5 mm model). C16
   (EEU-FR1C222, 12.5 × 20 mm) now has its real D12.5 footprint (it was on a
   D10 one). The LM317s lie tab-down on copper areas and are **not** bolted to the
   aluminium base (decided 2026-10-31): 0.17-0.22 W each in normal use, and in a
   crowbar fault the CC LM317 goes into its own thermal limit.
4. **SRF1260-102M (resolved).** The 1 mH part is `-102M` (no `-102Y` exists).
   In common-mode use the DC loop sees both windings, 6.8 Ω, and 0.28 A; the
   PSU simulation now uses 7.2 Ω for choke plus cable (worst-corner amplifier
   input 5.8 V, still 0.8 V above the 5 V LDO).
5. **WIMA MKS4 100 µF (resolved).** The old order code MKS4D061007H00KSSD is the
   100 VDC part, 24 × 45.5 × 41.5 mm. Cg sees about 2.5 V, so the design now
   uses the 63 VDC **MKS4C061007G00KSSD, 20 × 39.5 × 41.5 mm** on the matching
   W20 footprint (C301: MKS4C051005F00KSSD on its real W8.5 footprint).
6. **EEU-FR1C472.** Order the 16 × 25 mm, P7.5 case, not the 12.5 × 35 mm,
   P5 one.
7. **Outputs (resolved).** One AES3 output on a shielded right-angle RJ45,
   **Amphenol RJHSE-5380** (no LEDs), for shielded Cat5e/6 cable: AES3 on pins
   4/5, the shell isolated from GND. It replaces the pluggable Phoenix MC header
   (AES3) and the B6252HB BNC (S/PDIF), and saves about €12.
8. **ADM7150ARDZ-3.3-R7.** Priced at the DigiKey -5.0 figure; Mouser lists it
   at €12.71. Check which distributor holds the lower price on the day.
9. **Bias resistor.** The Ohmite RX-1M series is a factory special order at
   Mouser, and 10 G and 100 G quotes can reach hundreds of euros. The HVC1206
   10 GΩ is stocked. J202 has no pin header (nothing to buy for J202 but the
   resistor): solder the resistor straight into the two J202 holes, standing off
   the board with its body in the air (ASSEMBLY.md); a clip lead across the pads
   is the start-up reset.
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
    * Fuse clips FC-203-22 for the 5 × 20 mm ceramic Littelfuse 0215.500MXP fuse
      (1500 A breaking capacity; a glass fuse breaks only about 35 A).
14. **Hand-soldering note.** A hot-air station or hotplate is assumed for:
    * the exposed pads of the ADM7150 ×2 and the LT3045
    * the no-lead SiT1602, only if it is fitted instead of the SOT23-5 SiT2001B (Y402)

    Tools are not included.
15. **Box heater (HT1–HT13, mains side only).** STEGO HG 140 30 W (14001.0-00) and
    the NC thermostat **KTO 111** (11100.0-00; the KTO 011 is discontinued), Phoenix
    UT 2.5 (3044076) ×2, UT 2.5-PE (3044089), UT 4-HESI (5X20) (3046100) with a
    ceramic T 4 A fuse (Littelfuse 0215004.MXP; STEGO recommends a T 4 A pre-fuse,
    3 A inrush), E/UK end clamps ×2 and a D-UT 2.5/10 end cover. All prices are
    catalogue estimates; these lines are not in the distributor upload files
    (Distrelec, RS or TME carry them). A battery-only build leaves them out.
