#!/usr/bin/env python3
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Interactive HTML BOM for hand assembly (InteractiveHtmlBom, headless).

  pip download --no-deps -d /tmp/ibom InteractiveHtmlBom
  unzip -o /tmp/ibom/interactivehtmlbom-*.whl -d /tmp/ibom
  kicad-py tools/ibom.py /tmp/ibom PCB/antenna_amplifier/antenna_amplifier.kicad_pcb

Writes <board>/fab/<board>_ibom.html: click a BOM line to highlight its parts,
tick them off as sourced and placed. Mounting holes are left out.
"""

import os
import sys

pkg, pcb = sys.argv[1], sys.argv[2]
os.environ['INTERACTIVE_HTML_BOM_NO_DISPLAY'] = '1'
sys.path.insert(0, os.path.abspath(pkg))
from InteractiveHtmlBom.generate_interactive_bom import main  # noqa: E402

sys.argv = ['generate_interactive_bom', '--no-browser', '--dest-dir', 'fab', '--name-format', '%f_ibom',
            '--dark-mode', '--highlight-pin1', 'all', '--extra-fields', 'MPN,Manufacturer',
            '--blacklist', 'H*,NP*', pcb]
main()
