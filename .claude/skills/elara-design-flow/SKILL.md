---
name: elara-design-flow
description: Regenerate, place, route, finish and verify ELARA's KiCad schematics and boards (antenna_amplifier, acdc_converter, plate_capacitor), produce fab outputs and STEP, and run every check. Use for any change to a schematic, footprint, placement, routing, silkscreen or fab package in PCB/.
---

# ELARA design flow

Schematics and boards are GENERATED. Edit `PCB/<board>/design.py` / `layout.py` or
`tools/kicadgen/`, never the `.kicad_sch` / `.kicad_pcb`.

## Environment
`export KICAD9_SYMBOL_DIR=/usr/share/kicad/symbols DISPLAY=:99` (Xvfb :99 for
Freerouting). Missing tools: run the `elara-env-setup` skill.

## Order of work
1. Schematic: `.venv/bin/python PCB/<board>/design.py` -> last line must say
   "matches design". Then `tools/kicadgen/schcheck.py <root sch>` must be 0.
2. Placement: `kicad-py PCB/<board>/layout.py place`. Look at it before routing:
   `kicad-cli pcb export svg --layers F.Fab,F.Courtyard,F.Silkscreen ...`, render at
   ~20 px/mm (`rsvg-convert`) and READ the PNG. Rows/columns on a 0.5 mm grid.
3. Route (only if placement changed; `.ses` is git-ignored and reusable otherwise):
   - amplifier: `.venv/bin/python tools/kicadgen/route.py <dsn> <ses> --power "+9V,+5VA,+3V3,+5V_PRE,VIN_RAW" --passes 40`
   - PSU: the `--cls mains/contact/current` line from CLAUDE.md, `--passes 60`.
4. `kicad-py PCB/<board>/layout.py finish` (loads the placed board, so `place` first).
   It imports the SES, re-adds fixed tracks, removes dangling router stubs, pours, stitches.
5. `sh tools/fab_outputs.sh PCB/<board>/<board>.kicad_pcb`, then
   `.venv/bin/python mechanical/build_all.py` if the outline/parts/heights changed.
6. `.venv/bin/python tools/normalise_outputs.py` reverts metadata-only churn
   (STEP entity numbers, PNG render noise, PDF dates) so the commit shows real changes.
7. `sh tools/check_all.sh` -> "all checks passed". Commit only then.

## Known traps (keep adding)
- Freerouting 1.9 sometimes fails to finish HWCK1 (SW401.15 -> U401.27); it is
  pre-routed in `layout.py` on the path the router once found.
- Wire connectivity needs shared endpoints; no T-junctions from file.
- Guard island (15.5..33.0, 36.4..54.6 mm) is unmasked on purpose: its mask-bridge
  DRC hits are filtered in check_all, nothing else is.
- PSU charger vs receiver copper >= 1 mm (custom rule); mains gaps via
  `tools/mains_clearance.py`.
- Pin names don't reach copper: a symbol-name-only fix needs no re-route.
- Render every output you change and look at it before claiming it is fine.

## Maintaining this skill
After any session that hits a new trap or a changed command, edit this file in the same
commit. Keep it short: commands and traps, not history. Log below.

### Changelog
- 2026-10-31 created (native KiCad 9.0.9 flow, normalise_outputs.py).
