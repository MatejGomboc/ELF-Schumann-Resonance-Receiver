# SPDX-License-Identifier: CERN-OHL-W-2.0
"""
Regenerate every ELARA mechanical output: STEP models (step/), DXF flat
patterns (dxf/) and preview renders (renders/, SVG + PNG).

    .venv/bin/python mechanical/build_all.py            # everything
    .venv/bin/python mechanical/build_all.py --no-clash # skip the slow clash check
"""

import os
import runpy
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import params  # noqa: E402

SCRIPTS = [
    "amp_frame.py",
    "amp_lid.py",
    "amp_tray.py",
    "amp_pcb.py",
    "amp_assembly.py",
    "psu_box.py",
    "platecap.py",
    "outer_box.py",
    "full_assembly.py",
    "layout_drawing.py",
]


def main():
    t0 = time.time()
    problems = params.check()
    c, lost = params.plate_capacitance_pf()
    print(f"plate capacitor: {c:.2f} pF each (corner reliefs remove {lost:.1f} mm^2)\n")
    for s in SCRIPTS:
        t = time.time()
        print(f"--- {s}")
        runpy.run_path(os.path.join(HERE, s), run_name="__main__")
        print(f"    ({time.time() - t:.1f} s)")
    if "--no-clash" not in sys.argv:
        import full_assembly
        problems += [f"clash {a} x {b}" for (a, b, _) in full_assembly.clash_check()]
    print(f"\nbuild_all finished in {time.time() - t0:.0f} s; "
          f"{len([p for p in problems if p.startswith('clash')])} clashes")


if __name__ == "__main__":
    main()
