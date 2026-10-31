# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Branch model in the documents: consistent now, and impossible to forget on a merge.

The working branch (``claude/cloud-work``) is named in STATUS.md, README.md (text and
CI badge), PLAN.md, CLAUDE.md and the env-setup skill. This check fails when

1. those files name different working branches (one was edited, the others not), or
2. the code being checked is going into, or already sits on, ``master``: a pull request
   with base ``master`` or a push to ``master`` (GitHub's ``GITHUB_BASE_REF`` /
   ``GITHUB_REF_NAME``; locally the checked-out branch) while the documents still say
   the work lives on a side branch and ``master`` is untouched.

So a merge into master cannot go green until the branch text is rewritten: then name
``master`` as the working branch in every file below (and drop "master ... untouched").

    .venv/bin/python tools/branch_docs.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = "master"

# file -> regex whose group 1 is the working branch named there
CLAIMS = {
    "STATUS.md": r"work status \(branch `([^`]+)`\)",
    "README.md": r"badge\.svg\?branch=([^)\s]+)\)",
    "README.md#text": r"Revision 0\.2 on the `([^`]+)` branch",
    "PLAN.md": r"Revision 0\.2 \(branch `([^`]+)`\)",
    "CLAUDE.md": r"`([^`]+)` is the working branch",
    ".claude/skills/elara-env-setup/SKILL.md": r"git checkout -B (\S+) origin/",
}
UNTOUCHED = re.compile(r"`master`[^.\n]*untouched|master[^.\n]*untouched", re.I)


def current_target() -> tuple[str, str]:
    """(branch the code is going to or is on, how we know)."""
    base = os.environ.get("GITHUB_BASE_REF")
    if base:
        return base, "pull request base"
    ref = os.environ.get("GITHUB_REF_NAME")
    if ref and os.environ.get("GITHUB_EVENT_NAME") == "push":
        return ref, "push"
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        return out, "checkout"
    except (OSError, subprocess.CalledProcessError):
        return "", "unknown"


def main() -> int:
    named, problems = {}, []
    for key, rx in CLAIMS.items():
        path = ROOT / key.split("#")[0]
        m = re.search(rx, path.read_text(encoding="utf-8"))
        if not m:
            problems.append(f"{key}: working-branch sentence not found (pattern {rx!r})")
        else:
            named[key] = m.group(1)
    branches = set(named.values())
    if len(branches) > 1:
        problems.append("documents disagree on the working branch: "
                        + ", ".join(f"{k}={v}" for k, v in named.items()))

    target, how = current_target()
    side = branches - {DEFAULT}
    claims_untouched = bool(UNTOUCHED.search((ROOT / "STATUS.md").read_text(encoding="utf-8")))
    if target == DEFAULT and (side or claims_untouched):
        problems.append(
            f"this code is on / going to `{DEFAULT}` ({how}) but the documents still name "
            f"{sorted(side) or 'a side branch'} as the working branch"
            + (" and say master is untouched" if claims_untouched else "")
            + ": rewrite the branch text (see tools/branch_docs.py)")

    for p in problems:
        print("branch docs:", p)
    if problems:
        return 1
    print(f"branch docs: consistent (working branch {', '.join(sorted(branches))}; "
          f"target {target or '?'} by {how})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
