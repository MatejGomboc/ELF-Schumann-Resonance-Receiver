#!/usr/bin/env python3
"""
ELARA — Gerber Export Script for capacitor_square PCB

Exports manufacturing files (Gerbers + drill) using kicad-cli and packages
them into a zip ready for upload to JLCPCB or any other fab house.

Usage:
    python export_gerbers.py                    # export to gerbers/ subdir
    python export_gerbers.py --output build/    # custom output dir

CI/CD usage:
    python generate_pcb.py                      # regenerate PCB if needed
    python export_gerbers.py                    # export gerbers
    # -> gerbers/capacitor_square_gerbers.zip   ready for fab upload

Requirements:
    kicad-cli (ships with KiCad 9.0)
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile


# Layers to export for a 2-layer board
GERBER_LAYERS = [
    "F.Cu",         # top copper
    "B.Cu",         # bottom copper
    "F.Mask",       # top solder mask
    "B.Mask",       # bottom solder mask
    "F.SilkS",      # top silkscreen
    "B.SilkS",      # bottom silkscreen (even if empty — fab expects it)
    "Edge.Cuts",    # board outline
    "F.Fab",        # fabrication notes (optional but useful)
]

# Protel file extensions (what JLCPCB expects)
PROTEL_EXTENSIONS = {
    "F.Cu":      ".GTL",
    "B.Cu":      ".GBL",
    "F.Mask":    ".GTS",
    "B.Mask":    ".GBS",
    "F.SilkS":   ".GTO",
    "B.SilkS":   ".GBO",
    "Edge.Cuts": ".GKO",
    "F.Fab":     ".GTP",  # reused extension, fab layer
}


def find_kicad_cli():
    """Find kicad-cli executable."""
    # Common install locations
    candidates = [
        "kicad-cli",  # on PATH (Linux, macOS)
        r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
        r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
        "/usr/bin/kicad-cli",
        "/usr/local/bin/kicad-cli",
        "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    ]

    for candidate in candidates:
        if shutil.which(candidate) or os.path.isfile(candidate):
            return candidate

    return None


def export_gerbers(kicad_cli, pcb_file, output_dir):
    """Export Gerber files using kicad-cli."""
    cmd = [
        kicad_cli, "pcb", "export", "gerbers",
        "--output", output_dir,
        "--layers", ",".join(GERBER_LAYERS),
        "--subtract-soldermask",    # no silkscreen on pads
        "--precision", "6",         # 4.6 format (mm)
        pcb_file,
    ]

    print(f"  Exporting Gerbers...")
    print(f"    Layers: {', '.join(GERBER_LAYERS)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ERROR: kicad-cli gerber export failed:")
        print(result.stderr)
        return False

    if result.stdout.strip():
        print(result.stdout.strip())

    return True


def export_drill(kicad_cli, pcb_file, output_dir):
    """Export drill files using kicad-cli."""
    cmd = [
        kicad_cli, "pcb", "export", "drill",
        "--output", output_dir,
        "--format", "excellon",
        "--drill-origin", "absolute",
        "--excellon-zeros-format", "decimal",
        "--excellon-oval-format", "alternate",
        "--excellon-units", "mm",
        pcb_file,
    ]

    print(f"  Exporting drill files...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ERROR: kicad-cli drill export failed:")
        print(result.stderr)
        return False

    if result.stdout.strip():
        print(result.stdout.strip())

    return True


def make_zip(output_dir, zip_name):
    """Package all gerber and drill files into a zip."""
    zip_path = os.path.join(output_dir, zip_name)

    extensions = {".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo",
                  ".gko", ".gtp", ".gbp", ".gm1",
                  ".drl", ".xln", ".exc", ".gbr"}

    files = []
    for f in os.listdir(output_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in extensions or ext == ".gbr":
            files.append(f)

    if not files:
        print("  WARNING: No gerber/drill files found to zip")
        return None

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(files):
            zf.write(os.path.join(output_dir, f), f)

    print(f"  Packaged {len(files)} files into {zip_path}")
    return zip_path


def main():
    parser = argparse.ArgumentParser(
        description="ELARA — Export Gerbers for capacitor_square PCB",
    )
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory (default: gerbers/)")
    parser.add_argument("--pcb", type=str, default=None,
                        help="PCB file path (default: capacitor_square.kicad_pcb)")
    parser.add_argument("--kicad-cli", type=str, default=None,
                        help="Path to kicad-cli executable")
    parser.add_argument("--no-zip", action="store_true",
                        help="Don't create zip file")
    args = parser.parse_args()

    # Find kicad-cli
    kicad_cli = args.kicad_cli or find_kicad_cli()
    if kicad_cli is None:
        print("ERROR: kicad-cli not found. Install KiCad 9.0 or pass --kicad-cli")
        sys.exit(1)
    print(f"  kicad-cli: {kicad_cli}")

    # Resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pcb_file = args.pcb or os.path.join(script_dir, "capacitor_square.kicad_pcb")
    output_dir = args.output or os.path.join(script_dir, "gerbers")

    if not os.path.isfile(pcb_file):
        print(f"ERROR: PCB file not found: {pcb_file}")
        sys.exit(1)

    # Create output dir
    os.makedirs(output_dir, exist_ok=True)

    print(f"  PCB file:  {pcb_file}")
    print(f"  Output:    {output_dir}")
    print()

    # Export
    if not export_gerbers(kicad_cli, pcb_file, output_dir):
        sys.exit(1)

    if not export_drill(kicad_cli, pcb_file, output_dir):
        sys.exit(1)

    # Package
    if not args.no_zip:
        print()
        zip_name = "capacitor_square_gerbers.zip"
        zip_path = make_zip(output_dir, zip_name)
        if zip_path:
            print(f"\n  Ready for upload to JLCPCB: {zip_path}")

    print()


if __name__ == "__main__":
    main()
