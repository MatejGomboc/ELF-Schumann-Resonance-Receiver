# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Regenerate the ELARA electronics BOMs with prices, and print the cost summary.

Usage (from the repo root)::

    .venv/Scripts/python bom/build_bom.py      # Windows
    .venv/bin/python bom/build_bom.py          # Linux / macOS

Standard library only.

Reads
    PCB/antenna_amplifier/design_netlist.json
    PCB/acdc_converter/design_netlist.json
    bom/prices.csv          MPN -> unit price (EUR, ex VAT), buy multiple, source, confidence
    bom/extras.csv          purchased electronics lines that are not in a netlist
                            (bare PCBs, stencil, PCB shipping, optional parts)
    bom/mechanical_bom.csv  hand-maintained mechanical BOM (read for the totals only)

Writes
    bom/antenna_amplifier_bom.csv
    bom/psu_bom.csv

Prints the per-assembly subtotals, the grand total against the target, the top
cost drivers and the cost-down scenarios quoted in bom/README.md.

Line status values
    core      counted in the totals
    DNP       fitted footprint left empty: listed, costs 0
    no-part   PCB feature only (mounting holes): costs 0
    optional  priced but not counted
    site      site-dependent (antenna, long cables, indoor unit): not counted
"""

import csv
import json
import math
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

ASSEMBLIES = OrderedDict([
    ("antenna_amplifier", (ROOT / "PCB/antenna_amplifier/design_netlist.json",
                           HERE / "antenna_amplifier_bom.csv")),
    ("psu", (ROOT / "PCB/acdc_converter/design_netlist.json", HERE / "psu_bom.csv")),
])
PRICES = HERE / "prices.csv"
EXTRAS = HERE / "extras.csv"
MECHANICAL = HERE / "mechanical_bom.csv"

TARGET_EUR = 300.0
VAT_EXAMPLE = 0.22          # illustrative only; EU rates run from 17 to 27 %

COLUMNS = ["status", "group", "refs", "qty", "value", "footprint", "manufacturer", "mpn",
           "description", "unit_price_eur", "extended_eur", "source", "confidence",
           "supplier", "order_code", "notes"]
STATUS_ORDER = {"core": 0, "no-part": 1, "DNP": 2, "optional": 3, "site": 4}
COUNTED = ("core",)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def natural_key(ref):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", ref)]


def expand(spec):
    """'R10-R13 C8' -> ['R10', 'R11', 'R12', 'R13', 'C8']."""
    out = []
    for tok in spec.split():
        m = re.fullmatch(r"([A-Z]+)(\d+)-\1?(\d+)", tok)
        if m:
            out += [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)]
        else:
            out.append(tok)
    return out


def eur(x):
    return f"{x:.2f}"


def load_prices():
    prices = {}
    with open(PRICES, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["unit"] = float(r["unit_price_eur"])
            r["buy_multiple"] = int(r["buy_multiple"] or 1)
            prices[r["mpn"]] = r
    return prices


def price_row(prices, mpn):
    if mpn in prices:
        return prices[mpn]
    print(f"WARNING: no price for MPN '{mpn}'", file=sys.stderr)
    return {"unit": 0.0, "buy_multiple": 1, "source": "", "confidence": "MISSING",
            "supplier": "", "order_code": "", "notes": "no price in prices.csv"}


# ---------------------------------------------------------------------------
# electronics
# ---------------------------------------------------------------------------
def load_components(assembly, netlist, prices):
    """One dict per placed component (plus the extras for this assembly)."""
    comps = []
    for c in json.loads(netlist.read_text(encoding="utf-8"))["components"]:
        f = c.get("fields", {})
        mpn = (f.get("MPN") or "").strip() or "-"
        status = "DNP" if c.get("dnp") else ("no-part" if mpn == "-" else "core")
        comps.append(dict(assembly=assembly, status=status, group=c.get("sheet", ""),
                          ref=c["ref"], qty=1, value=c.get("value", ""),
                          footprint=c.get("footprint", "").split(":")[-1],
                          manufacturer=f.get("Manufacturer", ""), mpn=mpn,
                          description=f.get("Description", "")))
    with open(EXTRAS, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["assembly"] != assembly:
                continue
            comps.append(dict(assembly=assembly, status=r["status"], group=r["group"],
                              ref=r["refs"], qty=int(r["qty"]), value=r["value"],
                              footprint=r["footprint"], manufacturer=r["manufacturer"],
                              mpn=r["mpn"], description=r["description"], extra=True))
    for c in comps:
        c["unit"] = price_row(prices, c["mpn"])["unit"]
    return comps


def group_lines(comps, prices):
    """Group placed components by (status, MPN); extras stay one line each."""
    groups = OrderedDict()
    for c in comps:
        key = (c["status"], c["mpn"], c["ref"] if c.get("extra") else "")
        groups.setdefault(key, []).append(c)
    lines = []
    for (status, mpn, _), cs in groups.items():
        p = price_row(prices, mpn)
        refs = sorted((c["ref"] for c in cs), key=natural_key)
        qty = sum(c["qty"] for c in cs)
        uniq = lambda k: " / ".join(OrderedDict.fromkeys(c[k] for c in cs if c[k]))
        ext = qty * p["unit"] if status in ("core", "optional") else 0.0
        lines.append(dict(status=status, group=uniq("group"), refs=" ".join(refs), qty=qty,
                          value=uniq("value"), footprint=uniq("footprint"),
                          manufacturer=uniq("manufacturer"), mpn=mpn,
                          description=cs[0]["description"], unit=p["unit"], extended=ext,
                          source=p["source"], confidence=p["confidence"],
                          supplier=p["supplier"], order_code=p["order_code"],
                          notes=p["notes"]))
    lines.sort(key=lambda l: STATUS_ORDER.get(l["status"], 9))   # stable: netlist order kept
    return lines


def write_bom(path, lines):
    total = sum(l["extended"] for l in lines if l["status"] in COUNTED)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for l in lines:
            w.writerow([l["status"], l["group"], l["refs"], l["qty"], l["value"],
                        l["footprint"], l["manufacturer"], l["mpn"], l["description"],
                        eur(l["unit"]), eur(l["extended"]), l["source"], l["confidence"],
                        l["supplier"], l["order_code"], l["notes"]])
        w.writerow(["total", "", "", "", "", "", "", "", "Subtotal of core lines (EUR, ex VAT)",
                    "", eur(total), "", "", "", "", ""])
    return total


# ---------------------------------------------------------------------------
# mechanical (hand-maintained CSV)
# ---------------------------------------------------------------------------
def load_mechanical():
    lines = []
    with open(MECHANICAL, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["status"] == "total":
                continue
            qty, unit, ext = float(r["qty"]), float(r["unit_price_eur"]), float(r["extended_eur"])
            if abs(qty * unit - ext) > 0.011:
                print(f"WARNING: mechanical line {r['refs']}: qty x unit != extended", file=sys.stderr)
            lines.append(dict(status=r["status"], group=r["group"], refs=r["refs"], qty=qty,
                              value=r["value"], mpn=r["mpn"], description=r["description"],
                              unit=unit, extended=ext, confidence=r["confidence"]))
    return lines


# ---------------------------------------------------------------------------
# cost-down scenarios (cumulative) and upgrades (each against the reference)
# ---------------------------------------------------------------------------
# (label, assembly, refs removed, [(price MPN, qty) added], cancels tags, tag, impact)
# Electronics refs are space-separated and may use ranges (R10-R13); mechanical refs
# are the literal 'refs' field of mechanical_bom.csv, separated by ';'.
AMP, PSU, MECH = "antenna_amplifier", "psu", "mechanical"
PSU_TWO_BUCKET = ("U1 R2 U2 R3 R4 C3 D1 U3 C4 C5 U4 C6 R6 R7 C7 R8 R9 Q1 K1 D3 K2 D4 "
                  "R10-R13 C8-C15 R14-R21 C16")
RECOMMENDED = [
    ("Outer box: Gewiss GW44220 (IP56, inner 380 x 300 x 180) instead of Fibox ARCA 403015",
     MECH, "B1", [("GW44220", 1)], (), "box",
     "IP56 instead of IP66, screwed lid, technopolymer; re-drill the plate fixing; more room"),
    ("EDLC: generic 10 F 2.7 V radial cells, buy 10 and match to 5 %",
     PSU, "C8-C15", [("EDLC-10F-2V7-GENERIC", 8)], (), "edlc",
     "none if matched; check leakage against the 5k1 balancing resistors"),
    ("Aluminium: 6060 bar or offcuts by weight for the 60 x 8 walls",
     MECH, "A1-A3", [("AL-60x8-6060-OFFCUT-1M", 1)], (), "alu",
     "none electrically; 6060 is softer, tap the M3 threads with care"),
    ("Fit the J202 bias resistor: HVC1206 10 GOhm (cost increase)",
     AMP, "", [("HVC1206Z1008KET", 1)], (), "bias",
     "needed for a stable DC operating point (SPICE README section 5)"),
]
FURTHER = [
    ("PSU: drop the two-bucket stage, IRM-05-15 feeds the LT3045 directly",
     PSU, PSU_TWO_BUCKET, [], ("edlc",), "psu",
     "loses the galvanic isolation that is the point of the PSU: SMPS leakage and "
     "common-mode hash reach the outdoor ground; board change (link)"),
    ("Amplifier PCB: lead-free HASL instead of ENIG",
     AMP, "PCB-AMP", [("JLC-4L-200x100-FR4-HASL-5", 1)], (), "hasl",
     "uneven GND strips (lap the wall faces); tin on the unmasked guard island"),
    ("No stencil (iron and hot air; solder the exposed pads through vias)",
     AMP, "STENCIL", [], (), "stencil", "assembly effort only"),
    ("Unbranded IP65 ABS box instead of the Gewiss box",
     MECH, "", [("BOX-GENERIC-IP65", 1)], ("box",), "box2",
     "UV resistance and IP rating unverified; shorter outdoor life"),
    ("+3V3 digital LDO: ADP7118ARDZ-3.3 instead of ADM7150",
     AMP, "U102", [("ADP7118ARDZ-3.3", 1)], (), "ldo",
     "digital rail only, 11 uV rms; different pinout: schematic and layout change"),
    ("DIP switches replaced by wire links (modes fixed at build)",
     AMP, "SW302 SW401", [], (), "dip", "modes can no longer be changed without soldering"),
    ("Test points replaced by bare pads",
     AMP, "TP201-TP204 TP301", [], (), "tp", "probing is less convenient"),
]
UPGRADES = [
    ("Amplifier PCB in Rogers RO4350B (PLAN 4.3 preferred material)",
     AMP, "PCB-AMP", [("JLC-4L-200x100-RO4350B-5", 1)]),
    ("DHL Express instead of economy PCB shipping", AMP, "SHIP-JLC", [("JLC-SHIP-DHL", 1)]),
    ("Spare LMP7721", AMP, "", [("LMP7721MA/NOPB", 1)]),
    ("Glass RX-1M 1 GOhm bias resistor", AMP, "", [("RX-1M1007FE", 1)]),
]


def cost_map(elec_comps, mech_lines):
    """(assembly, ref) -> cost, core lines only.

    An extras line with several refs is split evenly between them.
    Mechanical lines are keyed by their literal refs field ('A1-A3').
    """
    m = {}
    for c in elec_comps:
        if c["status"] in COUNTED:
            refs = c["ref"].split()
            for r in refs:
                m[(c["assembly"], r)] = c["qty"] * c["unit"] / len(refs)
    for l in mech_lines:
        if l["status"] in COUNTED:
            m[(MECH, l["refs"])] = l["extended"]
    return m


def run_scenarios(steps, base, costs, prices, removed=None, added=None):
    removed = set() if removed is None else removed
    added = {} if added is None else added
    total = base
    rows = []
    for label, asm, refs, adds, cancels, tag, impact in steps:
        delta = 0.0
        keys = [r.strip() for r in refs.split(";") if r.strip()] if asm == MECH else expand(refs)
        for r in keys:
            key = (asm, r)
            if key not in costs:
                print(f"WARNING: scenario ref {key} not found", file=sys.stderr)
            elif key not in removed:
                removed.add(key)
                delta -= costs[key]
        for t in cancels:
            delta -= added.pop(t, 0.0)
        a = sum(price_row(prices, mpn)["unit"] * q for mpn, q in adds)
        if a:
            added[tag] = a
            delta += a
        total += delta
        rows.append((label, delta, total, impact))
    return rows, removed, added


# ---------------------------------------------------------------------------
def main():
    prices = load_prices()
    all_comps, subtotals, all_lines = [], OrderedDict(), []
    optional = {}
    for asm, (netlist, out) in ASSEMBLIES.items():
        comps = load_components(asm, netlist, prices)
        lines = group_lines(comps, prices)
        subtotals[asm] = write_bom(out, lines)
        optional[asm] = sum(l["extended"] for l in lines if l["status"] == "optional")
        all_comps += comps
        all_lines += [dict(l, assembly=asm) for l in lines]
        print(f"wrote {out.relative_to(ROOT)}  ({len(lines)} lines)")

    mech = load_mechanical()
    subtotals[MECH] = sum(l["extended"] for l in mech if l["status"] in COUNTED)
    optional[MECH] = sum(l["extended"] for l in mech if l["status"] == "optional")
    site = sum(l["extended"] for l in mech if l["status"] == "site")
    all_lines += [dict(l, assembly=MECH) for l in mech]

    # rounding up to the buy multiple (passives bought in tens), across both boards
    need = defaultdict(int)
    for c in all_comps:
        if c["status"] in COUNTED:
            need[c["mpn"]] += c["qty"]
    rounding = 0.0
    for mpn, n in need.items():
        p = price_row(prices, mpn)
        rounding += (math.ceil(n / p["buy_multiple"]) * p["buy_multiple"] - n) * p["unit"]

    grand = sum(subtotals.values()) + rounding

    print("\n## Subtotals (EUR, ex VAT)\n")
    print("| Assembly | EUR |\n| --- | ---: |")
    names = {"antenna_amplifier": "Antenna amplifier (parts + PCB + stencil + PCB shipping)",
             "psu": "PSU (parts + PCB)", MECH: "Mechanical, plate capacitors, wiring, logistics"}
    for k, v in subtotals.items():
        print(f"| {names[k]} | {eur(v)} |")
    print(f"| Rounding up to buy multiples (passives in tens) | {eur(rounding)} |")
    print(f"| **Grand total, ex VAT** | **{eur(grand)}** |")
    print(f"| Grand total incl. {VAT_EXAMPLE:.0%} VAT (example) | {eur(grand * (1 + VAT_EXAMPLE))} |")
    print(f"| Difference to the {TARGET_EUR:.0f} EUR target (ex VAT) | {eur(grand - TARGET_EUR)} |")
    print(f"\nNot counted: optional lines {eur(sum(optional.values()))} "
          f"({', '.join(f'{k} {eur(v)}' for k, v in optional.items())}); "
          f"site-dependent lines {eur(site)}")

    split = defaultdict(float)
    for l in all_lines:
        if l["status"] in COUNTED:
            c = l["confidence"]
            split["search snippet" if c.startswith("search snippet") else
                  "catalogue estimate" if c.startswith("catalogue estimate") else c] += l["extended"]
    print("Price basis of the core total: " + ", ".join(
        f"{k} {eur(v)} ({v / (grand - rounding):.0%})" for k, v in sorted(split.items())))

    print("\n## Top 10 cost drivers (core lines)\n")
    print("| # | Assembly | Refs | Item | Qty | EUR | Confidence |\n| --- | --- | --- | --- | ---: | ---: | --- |")
    core = [l for l in all_lines if l["status"] in COUNTED]
    for i, l in enumerate(sorted(core, key=lambda l: -l["extended"])[:10], 1):
        item = l["mpn"] if l["mpn"] not in ("-", "") else l["value"]
        print(f"| {i} | {l['assembly']} | {l['refs']} | {item} | {l['qty']:g} | "
              f"{eur(l['extended'])} | {l['confidence']} |")

    costs = cost_map(all_comps, mech)
    rec = [s for s in RECOMMENDED]
    rows, removed, added = run_scenarios(rec, grand, costs, prices)
    print("\n## Recommended cost-down set (cumulative, EUR ex VAT)\n")
    print("| Step | Delta | Running total | Performance impact |\n| --- | ---: | ---: | --- |")
    print(f"| Reference build | | {eur(grand)} | |")
    for label, d, t, imp in rows:
        print(f"| {label} | {d:+.2f} | {eur(t)} | {imp} |")
    rec_total = rows[-1][2]
    print(f"| **Recommended build, incl. {VAT_EXAMPLE:.0%} VAT (example)** | | "
          f"**{eur(rec_total * (1 + VAT_EXAMPLE))}** | |")

    rows2, _, _ = run_scenarios(FURTHER, rec_total, costs, prices, removed, added)
    print("\n## Further cuts (cumulative on top of the recommended set)\n")
    print("| Step | Delta | Running total | Performance impact |\n| --- | ---: | ---: | --- |")
    for label, d, t, imp in rows2:
        print(f"| {label} | {d:+.2f} | {eur(t)} | {imp} |")

    print("\n## Upgrades (each against the reference build)\n")
    print("| Option | Delta |\n| --- | ---: |")
    for label, asm, refs, adds in UPGRADES:
        (r,), _, _ = run_scenarios([(label, asm, refs, adds, (), "u", "")], grand, costs, prices)
        print(f"| {label} | {r[1]:+.2f} |")


if __name__ == "__main__":
    main()
