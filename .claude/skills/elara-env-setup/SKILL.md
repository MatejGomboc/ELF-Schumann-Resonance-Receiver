---
name: elara-env-setup
description: Set up or repair the ELARA toolchain in a fresh cloud container (KiCad 9 native, kicad-py, ngspice, Freerouting, Xvfb, the .venv). Use at session start when kicad-cli, kicad-py, .venv or Freerouting is missing, or when a check fails for environment reasons.
---

# Environment setup

`sh tools/setup_env.sh` (as root, Ubuntu 24.04), then
`export KICAD9_SYMBOL_DIR=/usr/share/kicad/symbols DISPLAY=:99`.

Verify: `sh tools/check_all.sh` must end "all checks passed"; regenerated schematics
must be byte-identical to the committed ones (`git status` clean after design.py).

## Traps
- `add-apt-repository` needs apt_pkg, only in /usr/bin/python3.12 (default python3 is 3.11).
- `kicad-py` is a shim to /usr/bin/python3.12 (pcbnew lives there); the `.venv` is 3.11.
- matplotlib must stay 3.10.8 or the plot SVGs churn.
- Freerouting 1.9 needs an X display (Xvfb :99) even in batch mode.
- The container may be reset to another branch: `git fetch origin claude/cloud-work &&
  git checkout -B claude/cloud-work origin/claude/cloud-work` before working.
- Disk is a fixed allowance; delete build leftovers on "no space left".
- Adom DS2SF binary is not installed by the script (see elara-pin-audit).

## Maintaining this skill
Changelog:
- 2026-10-31 created (Docker wrappers replaced by the PPA install).
