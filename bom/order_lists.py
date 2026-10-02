#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Distributor order lists (Farnell, Mouser, Digi-Key) from the priced BOM.

  .venv/bin/python bom/build_bom.py      # first: refreshes the per-board BOMs
  .venv/bin/python bom/order_lists.py

Writes bom/order/:
  order_all.csv    every electronic line to buy, merged across both boards
  digikey_bom.csv  upload in Digi-Key "BOM Manager"
  mouser_bom.csv   upload in Mouser "BOM Tool" (Projects -> BOM import)
  farnell_bom.csv  upload in Farnell "BOM Upload"
Each distributor file holds the same lines (manufacturer part number + quantity),
so the three quotes can be compared directly; see bom/ORDERING.md.

Rules: DNP parts and PCBs (JLCPCB) are left out; quantities are rounded up to
the buy multiple in prices.csv (passives in tens) after merging both boards;
combined BOM lines (fuse + clips, header + plug) are split into orderable parts; the mating
Micro-Fit parts and the plate-capacitor resistors come from mechanical_bom.csv.
"""

import csv
import math
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "order"
BOARDS = (("AMP", HERE / "antenna_amplifier_bom.csv"), ("PSU", HERE / "psu_bom.csv"))
TAKE_MECH = {"R1 R2", "W2", "W3"}                 # electronic items listed with the mechanics
SPLIT = {                                          # combined BOM lines -> orderable parts
    "5ST 500-R + 2x FC-203-22 clips": [
        ("Bel Fuse", "5ST 500-R", 2, "Fuse 5 x 20 mm T500 mA 250 V (1 + 1 spare)"),
        ("Bel Fuse", "FC-203-22", 2, "Fuse clip 5 x 20 mm, PCB"),
    ],
    "1803280 + 1803581 plug": [
        ("Phoenix Contact", "1803280", 1, "MC 1,5/3-G-3,81 right-angle header (J401 AES3)"),
        ("Phoenix Contact", "1803581", 1, "MC 1,5/3-ST-3,81 screw plug for the AES3 cable"),
    ],
    "PRPC002SAAN-RC + SPC02SYAN shunt": [
        ("Sullins", "PRPC002SAAN-RC", 1, "2-pin 2.54 mm header (J202 bias link)"),
        ("Sullins", "SPC02SYAN", 1, "Shunt jumper 2.54 mm (J202 reset link)"),
    ],
}
ORDER_CODE = {}                                    # descriptive BOM names -> manufacturer order codes
ALTERNATIVE = {                                    # in order_all.csv only, not in the upload files
    "RX-1M1007FE": "alternative to HVC1206Z1008KET for J202 (glass 1 G, lower surface leakage)",
}
NOT_ORDERED = {
    "PTFE press-fit turret or direct wire": "solder the node-2 lead directly, or use a PTFE stand-off terminal",
}
GENERIC = {}                                       # no single part number: choose one (see ORDERING.md)


def load_prices():
    with open(HERE / "prices.csv", newline="", encoding="utf-8") as f:
        return {r["mpn"]: r for r in csv.DictReader(f)}


def lines():
    """(board, refs, qty, manufacturer, mpn, description) for everything to buy."""
    for board, path in BOARDS:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["status"] not in ("core", "optional") or r["manufacturer"] == "JLCPCB":
                    continue
                if r["mpn"] in SPLIT:
                    for man, mpn, qty, desc in SPLIT[r["mpn"]]:
                        yield board, r["refs"], qty, man, mpn, desc
                    continue
                yield board, r["refs"], int(r["qty"]), r["manufacturer"], r["mpn"], r["description"]
    with open(HERE / "mechanical_bom.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["refs"] in TAKE_MECH:
                yield "MECH", r["refs"], int(r["qty"]), r["manufacturer"], r["mpn"], r["description"]


def main():
    prices = load_prices()
    merged = OrderedDict()
    skipped = []
    for board, refs, qty, man, mpn, desc in lines():
        if mpn in NOT_ORDERED:
            skipped.append((refs, NOT_ORDERED[mpn]))
            continue
        price_key = mpn
        mpn = ORDER_CODE.get(mpn, mpn)
        m = merged.setdefault(mpn, dict(man=man, mpn=mpn, key=price_key, qty=0, refs=[], desc=desc))
        m["qty"] += qty
        m["refs"].append(f"{board}:{refs}")
    rows = []
    for m in merged.values():
        p = prices.get(m["key"], {})
        mult = int(p.get("buy_multiple") or 1)
        order = math.ceil(m["qty"] / mult) * mult
        note = GENERIC.get(m["mpn"]) or ALTERNATIVE.get(m["mpn"]) or p.get("notes", "")
        rows.append(dict(manufacturer=m["man"], mpn=m["mpn"], qty_needed=m["qty"], qty_order=order,
                         refs=" ".join(m["refs"]), description=m["desc"],
                         preferred=p.get("supplier", ""), notes=note))
    OUT.mkdir(exist_ok=True)

    def ref_short(r, n=40):
        s = r["refs"]
        return s if len(s) <= n else s[:n - 3] + "..."

    with open(OUT / "order_all.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    specs = {
        "digikey_bom.csv": ("Quantity", "Manufacturer Part Number", "Manufacturer", "Customer Reference", "Description"),
        "mouser_bom.csv": ("Mfr Part Number", "Manufacturer", "Quantity", "Customer Part Number", "Description"),
        "farnell_bom.csv": ("Manufacturer Part Number", "Manufacturer", "Quantity", "Line Note", "Description"),
    }
    for name, head in specs.items():
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(head)
            for r in rows:
                if r["mpn"] in GENERIC or r["mpn"] in ALTERNATIVE:
                    continue                    # no single part number / not needed: see ORDERING.md
                vals = {"Quantity": r["qty_order"], "Manufacturer Part Number": r["mpn"],
                        "Mfr Part Number": r["mpn"], "Manufacturer": r["manufacturer"],
                        "Customer Reference": ref_short(r), "Customer Part Number": ref_short(r),
                        "Line Note": ref_short(r), "Description": r["description"][:60]}
                w.writerow([vals[h] for h in head])
    print(f"{len(rows)} lines ({sum(r['qty_order'] for r in rows)} parts) -> {OUT.relative_to(HERE.parent)}/")
    for refs, why in skipped:
        print(f"  not ordered: {refs}: {why}")
    for r in rows:
        if r["mpn"] in GENERIC:
            print(f"  generic, buy separately: {r['refs']}: {GENERIC[r['mpn']]}")


if __name__ == "__main__":
    main()
