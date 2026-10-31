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
| Prices, BOM totals | `bom/build_bom.py` output | bom/README.md (copied BY HAND), STATUS, README |
| Noise / SPICE results | `simulations/spice/` | PLAN.md section 0, CLAUDE.md |
| Bring-up voltages, solder order | ASSEMBLY.md | - |
| Pin audit sources | datasheets/README.md | STATUS item 8 |

Checklist before commit:
1. `grep -rn "<old value>" --include=*.md .` for every number you changed.
2. BOM changed -> rerun `bom/build_bom.py` AND `bom/order_lists.py` (distributor carts in
   bom/order/), copy totals into bom/README.md, STATUS, README.
   Simulation model changed -> `python simulations/psu/psu_model.py` rewrites the .cir.
3. New tool/script -> README repo tree + CLAUDE.md flow + the relevant skill.
4. British English. No model identifiers in repo files.
6. Background agents writing in the tree: stage explicit paths (`git add <dir>`,
   `git add -u -- . ':(exclude)<agent dir>'`), never `git add -A`.
7. New plotting script: copy the matplotlibrc / SOURCE_DATE_EPOCH block (CLAUDE.md).
8. After a regeneration run `tools/normalise_outputs.py`; if it calls a pure-metadata
   change "real", extend its rules (DXF GUIDs/stamps were added 2026-10-31).
10. Simulation dependencies: `simulations/system/run_system.py` and
   `simulations/signal_chain/expected_signal.py` read `simulations/spice/results.json`.
   After re-running SPICE, re-run both (CI regenerates them and fails on a stale SVG).
9. A simulation changes the design -> add a dated "Update" note at the top of that
   suite's README with the new key numbers, and a STATUS bullet.
5. Commit trailers as instructed in the session (Co-Authored-By / Claude-Session).

## Maintaining this skill
Add a row when a new kind of fact appears. Changelog:
- 2026-10-31 created.
- 2026-10-31 agents/staging, plot block, normaliser, simulation update notes.
