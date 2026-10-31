# ELARA -- ordering the electronics (Farnell, Mouser, Digi-Key)

Everything electronic that has a manufacturer part number is in
[`order/`](order/), generated from the priced BOM:

| File | Use it with | Columns to map |
| --- | --- | --- |
| [`order/digikey_bom.csv`](order/digikey_bom.csv) | Digi-Key **BOM Manager** (upload CSV, map columns) | Quantity, Manufacturer Part Number, Customer Reference |
| [`order/mouser_bom.csv`](order/mouser_bom.csv) | Mouser **BOM Tool** (import, map columns) | Mfr Part Number, Quantity, Customer Part Number |
| [`order/farnell_bom.csv`](order/farnell_bom.csv) | Farnell **BOM Upload** | Manufacturer Part Number, Quantity, Line Note |
| [`order/order_all.csv`](order/order_all.csv) | your own checklist | all lines, with the preferred source and notes |

The three distributor files hold **the same 101 lines**, identified by the
manufacturer part number, so the three quotes are directly comparable. The
reference field carries the board and the reference designators (`AMP:` for
the antenna amplifier, `PSU:` for the supply, `MECH:` for the plate-capacitor
resistors and the Micro-Fit mating parts), so every bag arrives labelled.

**Battery-first build:** delete the `PSU:` lines before uploading (the receiver
runs from a battery on J101 and the PSU comes later; ASSEMBLY.md section 5a).

Regenerate after any design change:

```bash
.venv/bin/python bom/build_bom.py     # per-board BOMs from the netlists
.venv/bin/python bom/order_lists.py   # the order files
```

## Quantities

- Both boards are merged first, then each line is rounded up to its buy
  multiple from `prices.csv`. Cheap passives are bought in tens, which leaves
  spares for hand soldering.
- Included spares: one extra LMP7721 (ESD-sensitive, hand-soldered), one extra
  fuse, and 10 Micro-Fit crimps where 4 are needed.
- The do-not-fit parts are left out: Y401 (SiT1602, the no-lead alternative
  oscillator) and C406.

## Which distributor

Put the whole list into one distributor. That keeps shipping to one parcel and
clears the free-delivery threshold easily (the parts come to roughly €200
ex VAT). Upload all three files, compare, then decide on the basis of which
lines each one cannot supply.

- **Digi-Key:** free delivery to Slovenia from €50, otherwise €20
  ([delivery page](https://www.digikey.si/en/help-support/delivery-information/delivery-time-and-cost)).
  It stocks the Newava S22083 and programs SiTime oscillators to frequency.
  It is the likeliest single source.
- **Mouser:** sources disagree on whether the free-delivery threshold is now
  €50 or €75, so check at checkout. It has broad Murata, Panasonic and WIMA
  stock.
- **Farnell:** a minimum order value has been reported (about €75). Check it.
  It is useful for WIMA, Bel Fuse and Phoenix Contact.

Prices in `prices.csv` are catalogue estimates or search snippets. The
distributor quote is the real price.

## Lines to watch

| Part | Why |
| --- | --- |
| SiT2001BI-S2-33E-24.576000 (Y402) | A programmable part: the distributor programs 24.576 MHz, which adds a few days. The SOT23-5 pinout (1 GND, 2 NC, 3 OE, 4 VDD, 5 OUT) matches SiTime's datasheet summary. If it is unavailable, order SiT1602BI-33-33E-24.576000 for Y401 instead (3.2 x 2.5 mm, no leads). |
| S22083 (TR401) | Newava, mainly Digi-Key. Settled against Newava's drawing: windings 1-2 and 3-4, pins 10.16 x 5.08 mm, footprint `elara:Transformer_Newava_S22083` with round holes. |
| MKS4C061007G00KSSD (C202) | WIMA MKS4 100 uF / 63 VDC, 41.5 x 20 x 39.5 mm. Not the MKS4D... code: that is the 100 VDC part, 24 x 45.5 mm, which no longer fits the footprint. |
| HV1030-2R7106-R (C8-C15) | 8 cells for the buckets. Buy 10 and match the 8 closest in capacitance (within 5 %). |
| SRF1260-102M (L1) | 1 mH per line; 6.8 Ohm for the DC loop (both windings) and 0.28 A in common-mode use. The PSU simulation uses these values. |
| RJHSE-5380 (J401) | Amphenol shielded right-angle RJ45 without LEDs (not the -02/-04 LED versions). AES3 on pins 4/5; the shell is the cable shield, isolated from GND. The shielded RJ45 plug and the Cat5e/6 cable are bought locally. |
| HVC1206Z1008KET (J202 bias) | 10 GOhm chip resistor (the largest stocked value), soldered straight into the two J202 holes with its body in the air (J202 has no header: nothing else to buy for it). 100 GOhm is better with an insulated antenna but is a special order (`simulations/system`). The glass Ohmite RX-1M1007FE (1 GOhm) in `order_all.csv` is only for a bare antenna with more than about 100 pA of air-earth current; it is noisier. |
| 2051-15-SM-RPLF (GDT1) | Bourns 150 V SMD gas discharge tube across the PSU's charger/receiver barrier (GND_C/PE to the receiver GND); footprint `elara:GDT_Bourns_2051`. Do not substitute a higher-voltage GDT. |
| MCR100-6G (Q6), TL431BIDBZR (U6) | EDLC overvoltage crowbar: SCR in TO-92 (UTC's MCR100-6 has the same 1 K, 2 G, 3 A pinout) and the 0.5 % B-grade TL431 in SOT-23 (DBZ: 1 K, 2 REF, 3 A). Keep the B grade: the trip tolerance (11.5-11.9 V) depends on it. |
| IRM-05-15 (PS1), B72210S0271K101 (RV1), 0215.500MXP (F1) | Mains parts: buy only genuine parts from the distributor, never from marketplaces. F1 is the ceramic high-breaking fuse (1500 A); do not substitute a glass 5 x 20 mm fuse (about 35 A). |

## Not in the upload files

- **PCBs and the stencil:** order from JLCPCB with the Gerber zips in
  `PCB/*/fab/` (see `ASSEMBLY.md`).
- **LM317 mounting:** the two LM317s lie tab-down on copper areas of the PSU board,
  each screwed flat onto its copper (an M3x8 screw and nut each in
  `mechanical_bom.csv`). They are not bolted to the aluminium base (decided
  2026-10-31: 0.17-0.22 W each in normal use; the tabs are live and the base is PE),
  so no insulating pads or shoulder washers are needed.
- **Box heater (HT1-HT13, mains side only):** STEGO HG 140 30 W (14001.0-00), STEGO
  KTO 111 thermostat (11100.0-00; the KTO 011 is discontinued), a 160 mm DIN rail,
  Phoenix UT 2.5 terminals (3044076, 3044089 PE, 3046100 fuse terminal), a ceramic
  T 4 A 5 x 20 fuse (Littelfuse 0215004.MXP), end clamps and an end cover. Listed in
  `mechanical_bom.csv`, not in the upload files: Distrelec, RS or TME. Skip it for a
  battery-first build.
- **Nylon M3x10 standoffs and M3x6 nylon screws for PSU holes H2/H4** (receiver
  side): in `mechanical_bom.csv`. Never use metal there; the standoffs stand on
  the PE-bonded base.
- **J201 input turret:** solder the node-2 lead straight into the plated hole,
  or use a PTFE stand-off terminal (see `mechanical/README.md`).
- **Mechanics, cable glands, the outdoor box and cable:** see
  `mechanical/SUPPLIERS_SI.md` (local suppliers in eastern Slovenia),
  `bom/mechanical_bom.csv` and `MAINS_CABLE.md`. The Lapp SKINTOP glands can
  also come from an electrical wholesaler.
