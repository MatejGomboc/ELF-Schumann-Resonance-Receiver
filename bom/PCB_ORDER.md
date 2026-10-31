# ELARA -- ordering the PCBs (JLCPCB)

Upload the Gerber zip of each board (`PCB/<board>/fab/<board>_gerbers.zip`) and set
the options below. The limits behind them are in `tools/kicadgen/fabrules.py` (every
board passes DRC against JLCPCB's standard process, any mask colour).

| Option | Antenna amplifier | Two-bucket PSU | Air-gap plate |
| --- | --- | --- | --- |
| Layers | 4 | 2 | 2 |
| Size | 200 x 100 mm | 150 x 90 mm | 78 x 64 mm (with the solder tongues) |
| Quantity | 5 | 5 | 5 (4 plates needed) |
| Material / thickness | FR4, 1.6 mm | FR4, 1.6 mm | FR4, 1.6 mm |
| Outer copper | 1 oz | 1 oz | 1 oz |
| Inner copper | 0.5 oz (default) | - | - |
| Surface finish | **ENIG** (flat pads, flat wall strips) | HASL lead-free | HASL lead-free |
| Solder mask colour | any (white or black are fine too) | any | any |
| Remove order number | see the note below | see the note below | see the note below |

## Note to paste into the order ("Remark" field)

Antenna amplifier:

```text
Please do NOT print the order/customer number anywhere on the TOP side, and
never inside the bare-copper (no solder mask) area around the input on the left
of the board: it is a guarded high-impedance input and must stay clean.
If a number must be printed, put it on the BOTTOM side, right-hand half of the
board (digital section), in any free spot clear of pads.
Please also keep the exposed copper strips (no solder mask) free of any ink.
Thank you.
```

Two-bucket PSU:

```text
Please print the order/customer number on the BOTTOM side, away from the mains
area on the left of the board (the part marked "MAINS 230 V" / "PRIMARY").
Thank you.
```

Air-gap capacitor plate:

```text
Please print the order/customer number on the BOTTOM (non-copper) side only,
in a free spot clear of the text. The top side is one large copper plate and
must stay free of any ink. Thank you.
```

If you prefer no number at all, choose "Remove Order Number" (small surcharge)
instead and leave the remark out.

## Traceability

Each board's silkscreen carries `REV <x.y>` and the short git commit hash the Gerbers
were exported from (a `+` after it means they came from a tree with uncommitted
changes). Keep the order number together with that hash in your notes.
