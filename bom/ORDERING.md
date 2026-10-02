# ELARA -- ordering the electronics (Farnell, Mouser, Digi-Key)

Everything electronic that has a manufacturer part number is in
[`order/`](order/), generated from the priced BOM:

| File | Use it with | Columns to map |
| --- | --- | --- |
| [`order/digikey_bom.csv`](order/digikey_bom.csv) | Digi-Key **BOM Manager** (upload CSV, map columns) | Quantity, Manufacturer Part Number, Customer Reference |
| [`order/mouser_bom.csv`](order/mouser_bom.csv) | Mouser **BOM Tool** (import, map columns) | Mfr Part Number, Quantity, Customer Part Number |
| [`order/farnell_bom.csv`](order/farnell_bom.csv) | Farnell **BOM Upload** | Manufacturer Part Number, Quantity, Line Note |
| [`order/order_all.csv`](order/order_all.csv) | your own checklist | all lines, with the preferred source and notes |

The three distributor files hold **the same 85 lines**, identified by the
manufacturer part number, so the three quotes are directly comparable. The
reference field carries the board and the reference designators (`AMP:` for
the antenna amplifier, `PSU:` for the supply, `MECH:` for the plate-capacitor
resistors and the Micro-Fit mating parts), so every bag arrives labelled.

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
  oscillator), C406 and R414.

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
  €50 or €75, so check at checkout. It has broad Murata, Panasonic, WIMA and
  Omron stock.
- **Farnell:** a minimum order value has been reported (about €75). Check it.
  It is useful for WIMA, Bel Fuse and Phoenix Contact.

Prices in `prices.csv` are catalogue estimates or search snippets. The
distributor quote is the real price.

## Lines to watch

| Part | Why |
| --- | --- |
| SiT2001BI-S2-33E-24.576000 (Y402) | A programmable part: the distributor programs 24.576 MHz, which adds a few days. The SOT23-5 pinout (1 GND, 2 NC, 3 OE, 4 VDD, 5 OUT) matches SiTime's datasheet summary. If it is unavailable, order SiT1602BI-33-33E-24.576000 for Y401 instead (3.2 x 2.5 mm, no leads). |
| S22083 (TR401, TR402) | Newava, mainly Digi-Key. Check the winding pin numbers against the footprint (1-2 / 3-4). |
| MKS4C061007G00KSSD (C202) | WIMA MKS4 100 uF / 63 VDC, 41.5 x 20 x 39.5 mm. Not the MKS4D... code: that is the 100 VDC part, 24 x 45.5 mm, which no longer fits the footprint. |
| HV1030-2R7106-R (C8-C15) | 8 cells for the buckets. Buy 10 and match the 8 closest in capacitance (within 5 %). |
| SRF1260-102M (L1) | 1 mH per line; 6.8 Ohm for the DC loop (both windings) and 0.28 A in common-mode use. The PSU simulation uses these values. |
| 1803280 + 1803581 (J401) | Phoenix MC 1,5/3 header on the board and its screw plug: the AES3 cable is wired into the plug outside the shield and pushed in through the wall notch. |
| B6252HB-NPP3G-50 (J402) | Single right-angle BNC (the old 031-6575 was a dual, 29 mm tall part). Its shell is the S/PDIF return: it must not touch the shield wall. |
| HVC1206Z1008KET (J202 bias) | 10 GOhm chip resistor, soldered across the J202 pins with its body in the air. The glass Ohmite RX-1M1007FE (1 GOhm) is listed in `order_all.csv` as an alternative with lower surface leakage. Order one of the two. |
| IRM-05-15 (PS1), B72210S0271K101 (RV1), 5ST 500-R (F1) | Mains parts: buy only genuine parts from the distributor, never from marketplaces. |

## Not in the upload files

- **PCBs and the stencil:** order from JLCPCB with the Gerber zips in
  `PCB/*/fab/` (see `ASSEMBLY.md`).
- **No heatsinks:** the two LM317s lie tab-down on copper areas of the PSU board
  (an M3x8 screw and nut each, in `mechanical_bom.csv`).
- **Nylon M3x10 standoffs and M3x6 nylon screws for PSU holes H2/H4** (receiver
  side): in `mechanical_bom.csv`. Never use metal there; the standoffs stand on
  the PE-bonded base.
- **J201 input turret:** solder the node-2 lead straight into the plated hole,
  or use a PTFE stand-off terminal (see `mechanical/README.md`).
- **Mechanics, cable glands, the outdoor box and cable:** see
  `mechanical/SUPPLIERS_SI.md` (local suppliers in eastern Slovenia),
  `bom/mechanical_bom.csv` and `MAINS_CABLE.md`. The Lapp SKINTOP glands can
  also come from an electrical wholesaler.
