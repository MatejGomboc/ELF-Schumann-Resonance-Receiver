---
name: elara-docs-sync
description: Keep ELARA's documents consistent after a design change - which file holds which fact (PLAN.md, STATUS.md, README.md, CLAUDE.md, bom/README.md, ASSEMBLY.md) and what must be updated together. Use before committing any change that alters a number, part, tool or result.
---

# Docs sync

Where facts live (one owner each; others summarise and point to it):
| Fact | Owner | Also mentioned in |
|------|-------|-------------------|
| Design parameters, rationale | PLAN.md | CLAUDE.md "Current design parameters", README |
| Work state, open items, environment | STATUS.md | README "Project Status" |
| Repo layout, toolchain | README.md | CLAUDE.md "Repo structure" |
| Commands, flow, conventions for agents | CLAUDE.md, `.claude/skills/` | - |
| Prices, BOM totals | `bom/build_bom.py` output | bom/README.md (copied BY HAND), STATUS.md, bom/ORDERING.md (README.md has no totals) |
| Noise / SPICE results | `simulations/spice/` | PLAN.md section 0, CLAUDE.md |
| Bring-up voltages, solder order | ASSEMBLY.md | - |
| Pin audit sources | datasheets/README.md | STATUS open check 6 |
| Mechanical parts and build | mechanical/README.md | MOUNTING.md, SUPPLIERS_SI.md |

Checklist before commit:
1. `grep -rn "<old value>" --include=*.md .` for every number you changed.
2. BOM changed -> rerun `bom/build_bom.py` AND `bom/order_lists.py` (distributor carts in
   bom/order/), copy totals into bom/README.md, STATUS.md and bom/ORDERING.md (line count).
   Simulation model changed -> `python simulations/psu/psu_model.py` rewrites the .cir.
   ngspice "timestep too small at the initial timepoint" after a topology change: give
   every new node a 1 nF stray with a consistent `ic=` (uic starts uncapped nodes at
   0 V) and keep exp()/squares bounded (`clp()`); do not just tune solver options.
   Order: spice -> system -> psu (the PSU leakage plot reads the system clip level).
3. New tool/script -> README repo tree + CLAUDE.md flow + the relevant skill.
4. British English. No model identifiers in repo files.
5. Commit trailers as instructed in the session (Co-Authored-By / Claude-Session).
6. Background agents writing in the tree: stage explicit paths (`git add <dir>`,
   `git add -u -- . ':(exclude)<agent dir>'`), never `git add -A`.
7. New plotting script: copy the matplotlibrc / SOURCE_DATE_EPOCH block (CLAUDE.md).
8. After a regeneration run `tools/normalise_outputs.py`; if it calls a pure-metadata
   change "real", extend its rules (DXF GUIDs/stamps were added 2026-10-31).
9. A simulation changes the design -> add a dated "Update" note at the top of that
   suite's README with the new key numbers, and a STATUS bullet.
10. Simulation dependencies: `simulations/system/run_system.py` and
   `simulations/signal_chain/expected_signal.py` read `simulations/spice/results.json`.
   After re-running SPICE, re-run both (CI regenerates them and fails on a stale SVG).
11. A hardware review item left open (not changed on the board) -> STATUS.md "Before
   ordering -- open checks" AND the how-to doc where a builder would hit it
   (ASSEMBLY.md, MOUNTING.md, MAINS_CABLE.md).

## Maintaining this skill
Add a row when a new kind of fact appears. Changelog:
- 2026-10-31 created.
- 2026-10-31 agents/staging, plot block, normaliser, simulation update notes.
- 2026-10-31 checklist renumbered 1..11; BOM-totals row names bom/README.md, STATUS.md,
  ORDERING.md; mechanical row; open review items go to STATUS and the how-to docs.
- 2026-10-31 PSU model start-up lesson and the spice -> system -> psu order.
