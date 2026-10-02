#!/bin/sh
# SPDX-License-Identifier: CERN-OHL-W-2.0
# Fabrication outputs for one board: Gerbers + Excellon drill (zipped for JLCPCB),
# pick-and-place, BOM CSV, PDF plots, a 3D render and a populated STEP model
# (fitted parts only, origin at the board's top-left corner, as used by mechanical/)
# for the enclosure maker.
#   tools/fab_outputs.sh PCB/antenna_amplifier/antenna_amplifier.kicad_pcb
set -e
PCB="$1"
DIR=$(dirname "$PCB")/fab
NAME=$(basename "$PCB" .kicad_pcb)
SCH=$(dirname "$PCB")/$NAME.kicad_sch
mkdir -p "$DIR/gerbers"
rm -f "$DIR"/gerbers/*

LAYERS="F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
case $(grep -c '"In1.Cu"' "$PCB") in 0) ;; *) LAYERS="$LAYERS,In1.Cu,In2.Cu" ;; esac

kicad-cli pcb export gerbers --layers "$LAYERS" --subtract-soldermask --use-drill-file-origin \
    -o "$DIR/gerbers/" "$PCB" >/dev/null
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map --map-format gerberx2 \
    -o "$DIR/gerbers/" "$PCB" >/dev/null
(cd "$DIR/gerbers" && rm -f "../${NAME}_gerbers.zip" && zip -q "../${NAME}_gerbers.zip" *)

kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp \
    -o "$DIR/${NAME}_pos.csv" "$PCB" >/dev/null
if [ -f "$SCH" ]; then
    kicad-cli sch export bom --fields 'Reference,Value,Footprint,Manufacturer,MPN,Description,${QUANTITY},${DNP}' \
        --group-by 'Value,Footprint,MPN' --exclude-dnp -o "$DIR/${NAME}_bom.csv" "$SCH" >/dev/null
    kicad-cli sch export pdf -o "$DIR/${NAME}_schematic.pdf" "$SCH" >/dev/null
fi
kicad-cli pcb export pdf --mode-single --layers "F.Cu,F.SilkS,F.Fab,Edge.Cuts" \
    -o "$DIR/${NAME}_assembly_top.pdf" "$PCB" >/dev/null
kicad-cli pcb export step --subst-models --no-dnp --user-origin 50x50mm -f -o "$DIR/${NAME}.step" "$PCB" >/dev/null 2>&1 || true
kicad-cli pcb render --side top --quality high -w 2400 -h 1400 -o "$DIR/${NAME}_top.png" "$PCB" >/dev/null 2>&1 || true
# interactive HTML BOM, if InteractiveHtmlBom is unpacked (see tools/ibom.py)
IBOM_PKG=${IBOM_PKG:-/tmp/ibom}
if [ -d "$IBOM_PKG/InteractiveHtmlBom" ]; then
    kicad-py "$(dirname "$0")/ibom.py" "$IBOM_PKG" "$PCB" >/dev/null 2>&1 || true
fi
ls -la "$DIR"
