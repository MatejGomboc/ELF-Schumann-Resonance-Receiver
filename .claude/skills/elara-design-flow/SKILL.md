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
2. Placement: `kicad-py PCB/<board>/layout.py place` (amplifier and PSU; the stage
   argument `place|finish` applies to those two only: `PCB/plate_capacitor/layout.py`
   takes no stage argument and builds the whole plate in one run). Look at it before routing:
   `kicad-cli pcb export svg --layers F.Fab,F.Courtyard,F.Silkscreen ...`, render at
   ~20 px/mm (`rsvg-convert`) and READ the PNG. Rows/columns on a 0.5 mm grid.
3. Route (only if placement changed; the committed `.ses` is reused otherwise):
   - amplifier: `.venv/bin/python tools/kicadgen/route.py <dsn> <ses> --power "+9V,+5VA,+3V3,+5V_PRE,VIN_RAW" --passes 40`
   - PSU: `sh tools/route_psu.sh` does place + route + finish.
4. `kicad-py PCB/<board>/layout.py finish` (both boards rebuild the placement first, so
   finish can be re-run alone while the placement is unchanged).
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
- Guard island (an L: `ISLAND_RECTS` in the amplifier layout.py; the bbox `ISLAND` is what
  check_all and the sims read) is unmasked on purpose: its mask-bridge
  DRC hits are filtered in check_all, nothing else is.
- PSU charger vs receiver copper >= 1 mm (custom rule); mains gaps via
  `tools/mains_clearance.py`.
- Pin names don't reach copper (a name-only fix needs no re-route). Render every output
  you change and look at it before claiming it is fine.
- Freerouting never sees KiCad custom rules (.kicad_dru). Isolation gaps must go in as
  `route.py --barrier "um:sideA:sideB"` (class_class rules), else DRC fails afterwards.
  A blanket big clearance on GND instead blocks fine-pitch ICs (LT3045 MSOP).
- A board rebuilt from scratch in Python has no project rules until saved and reloaded:
  `build().save(); b = Board.load(path)` before `fill()`, or pours ignore custom rules.
- Schematic legibility: relay/IC values are long; put them with `fields_at` under the
  body (`(7.0, 13.3, 'left')`) and space parts >= 25.4 mm for horizontal 2-pin parts
  with labels at both ends. Check with schcheck after every move; render the sheet SVG
  (`kicad-cli sch export svg`, the sub-sheet file, not the root) and crop the block.

- Changed placement -> place, route, finish (never patch a finished board). Commit the
  board, then `fab_outputs.sh` from a clean tree (no `+` in the hash), then the outputs.
- Stitch vias: skip other nets' copper (else they dangle); thermal vias under a part need
  `avoid_courtyards=False`; near a barrier `stitch(..., clearance=BARRIER + 0.05)`.
- New footprint: take every pad position from the maker's dimensioned drawing, never
  from a "similar" part (TR401 sat on a 7.62 mm square; S22083 is 10.16 x 5.08).
- A part added mid-sheet renumbers the later refs of that sheet (R207 -> R208 breaks
  PLACE and the docs): create new parts LAST in the sheet function.
- Galvanic isolation (AES3 secondary): pour keep-out on all four layers incl. the In1
  plane, filter stitch vias out of it, and a temporary routing keep-out so the router
  keeps the pair inside; then MEASURE item-to-pour gaps with a pcbnew script.
- Wide router classes cannot enter fine-pitch pads (0.6 mm into an MSOP 0.65 mm pitch
  failed): give such nets their own narrower class (`--cls "mid:400:200:..."`).
- A net newly tied next to a crowded pin row can wall in its neighbours (COPY/C high
  blocked SFMT0/1): pre-route a short stub to its own via, as for HWCK1.
- Part pin numbering that differs from KiCad's symbol (Bourns SRF1260 windings 1-3 /
  2-4): `symlib.derived(..., pin_numbers={...})`, never just swap nets by eye.
- `fields_at` offsets live in the symbol's frame: on a rotated or mirrored symbol they
  move and flip justification. Nudge, re-run schcheck, repeat. `join()` between pins
  that are not aligned bends straight through the bodies: align them or keep a label.
- JLC annular ring >= 0.25 mm: `TO-92_Inline` (0.15) fails DRC; use `TO-92` or `_Wide`.
  `Device:GDT_2Pin` uses pins 1 and 3: number the footprint pads to match.
- Simulation JSON is diffed byte for byte in CI: store floats rounded (spice/em 6 g,
  system/stability 9 g); full precision differs in the last digit between machines.
- New THT turret / feed-through on the amplifier: add the PTFE bush in mechanical/params.py
  (fit_check compares the axes) and a pour keep-out ring round its unmasked pad.

- Waiting on a background job with `while pgrep -f <name>` matches the loop's own command
  line and never ends: wait on the task notification or check the output file instead.
- Shield mechanics changed -> `build_all.py` also rewrites `mechanical/jlccnc/` (STEP + thread
  drawings for JLCCNC); check_all probes each drawn feature in its solid. Threads exist only
  on the PDFs (STEP holes are tap-drill size): an order without the PDFs gets no threads.
- Feed-throughs are bought Keystone 11157 (3.45 mm press-fit, 1.6 mm panel, spot-faced
  tray): their inner pin meets the J201/J203 lead by design; fit_check whitelists that
  joint below 1 mm^3. A tray-hole change also changes the EM solve (aperture, C to tray).
- Island shape changes the EM solve (it reads the board copper) and the thermal ENIG area:
  re-run `simulations/em` and `simulations/thermal` after any island edit.

## Maintaining this skill
After any session that hits a new trap or a changed command, edit this file in the same
commit. Keep it short: commands and traps, not history. Log below.

### Changelog
- 2026-10-31 created; reed, plate-return, review, debug and protection revisions folded in
  (details in git log of this file). Crowbar/GDT: new parts LAST, TO-92 annular, GDT pins
  1/3, fields_at in rotated symbols, rounded simulation JSON.
- 2026-11-01 L-shaped island (ISLAND_RECTS), pgrep self-match, sims to re-run after it.
- 2026-11-01 JLCCNC shield package (jlccnc.py), its probe in check_all.
- 2026-11-01 Keystone 11157 feed-throughs, the intended pin-lead joint in fit_check.
