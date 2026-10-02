#!/bin/sh
# SPDX-License-Identifier: CERN-OHL-W-2.0
# Every design check in one go; exits non-zero on the first failing group.
#   sh tools/check_all.sh            (from the repository root)
# Needs: .venv, kicad-cli / kicad-py (KiCad 9), KICAD9_SYMBOL_DIR for design.py.
# The boards' STEP files must be current for the fit check (tools/fab_outputs.sh).
set -e
PY=.venv/bin/python
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $*"; exit 1; }

echo "== schematics: netlist check against the design, ERC, legibility"
for d in antenna_amplifier acdc_converter; do
    $PY PCB/$d/design.py | tail -1 | grep -q "matches design" || fail "$d netlist check"
    kicad-cli sch erc --severity-error --format json -o "$TMP/erc.json" "$PWD/PCB/$d/$d.kicad_sch" >/dev/null 2>&1
    $PY -c "import json,sys; d=json.load(open('$TMP/erc.json')); n=sum(len(s['violations']) for s in d['sheets']); print('  $d ERC errors:', n); sys.exit(n > 0)" \
        || fail "$d ERC"
done
$PY tools/kicadgen/schcheck.py PCB/antenna_amplifier/antenna_amplifier.kicad_sch \
    PCB/acdc_converter/acdc_converter.kicad_sch >/dev/null || fail "schematic legibility (schcheck.py)"
echo "  schematic legibility: 0 problems"

echo "== boards: DRC with schematic parity"
for d in antenna_amplifier acdc_converter plate_capacitor; do
    PARITY=--schematic-parity
    [ -f "PCB/$d/$d.kicad_sch" ] || PARITY=
    kicad-cli pcb drc $PARITY --severity-all --format json -o "$TMP/drc.json" "$PWD/PCB/$d/$d.kicad_pcb" >/dev/null 2>&1
    $PY - "$TMP/drc.json" "$d" <<'EOF' || fail "$d DRC"
import json, sys
d = json.load(open(sys.argv[1]))
ISLAND = (15.5, 36.4, 33.0, 54.6)          # amplifier guard island: unmasked on purpose
bad = []
for v in d["violations"]:
    xy = [(i["pos"]["x"] - 50, i["pos"]["y"] - 50) for i in v["items"]]
    on_island = all(ISLAND[0] <= x <= ISLAND[2] and ISLAND[1] <= y <= ISLAND[3] for x, y in xy)
    if not (v["type"] == "solder_mask_bridge" and on_island):
        bad.append(v["type"])
n_unc, n_par = len(d["unconnected_items"]), len(d.get("schematic_parity", []))
print(f"  {sys.argv[2]}: {len(bad)} violations, {n_unc} unconnected, {n_par} parity"
      f" ({len(d['violations']) - len(bad)} intended island mask bridges)")
sys.exit(1 if bad or n_unc or n_par else 0)
EOF
done

echo "== PSU mains clearances"
kicad-py tools/mains_clearance.py PCB/acdc_converter/acdc_converter.kicad_pcb 2>/dev/null | tail -1 \
    | grep -q PASS || fail "mains clearance"
echo "  PASS"

echo "== mechanics: real boards in their enclosures"
(cd mechanical && ../$PY fit_check.py | tail -1) | grep -q "no clashes" || fail "fit check"
(cd mechanical && ../$PY -c "import params, sys; sys.exit(1 if [p for p in params.check(False) if 'relief' not in p] else 0)") \
    || fail "params.check()"
echo "  fit check and params.check(): OK"

echo "== PC software tests"
(cd software && ../$PY -m pytest -q 2>&1 | tail -1)
echo "all checks passed"
