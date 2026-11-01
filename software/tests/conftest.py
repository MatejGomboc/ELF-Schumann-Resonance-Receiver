# SPDX-License-Identifier: CERN-OHL-W-2.0
import sys
from pathlib import Path

# Allow ``pytest`` from a plain checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
