# Datasheet pin extractions

`ds2sf/<MPN>/` holds the pin tables of every IC whose symbol we made or modified. They are
read from the manufacturers' PDFs by [Adom DS2SF](https://wiki.adom.inc/adom/adom-ds2sf),
one of the AI EDA tools in the [Adom apps catalogue](https://wiki.adom.inc/apps).

| File | Contents |
|------|----------|
| `<MPN>-symbol.extracted.json` | pins: number, name, electrical type, functional group |
| `<MPN>-extraction.provenance.json` | the datasheet page each pin was read from |
| `<MPN>-extraction.result.json` | run summary, warnings (e.g. non-standard pinouts) |
| `<MPN>-*-mode.json` | hand-read overrides for another pin mode (CS8406 hardware mode, DS580F6 p.29) |

The PDFs themselves are not committed (manufacturer copyright); each JSON names its
source URL.

`tools/pin_audit.py` compares these tables with the symbol pins embedded in the generated
schematics and with the nets in `design_netlist.json`. It runs in `tools/check_all.sh`.

## Adding a part

1. Get the manufacturer PDF and read the pin table yourself first
   (`pdftotext -layout -f N -l N part.pdf -`): it is the reference, the extraction is
   the second opinion.
2. `adom-ds2sf --ai-thread "elara pin audit" extract <dir> --pdf <dir>/<MPN>.pdf
   --mpn <MPN> --manufacturer "<maker>" --source-tier mfr --symbol-only`
   (needs the `claude` CLI; costs about $0.5 per part).
3. Copy the JSON into `ds2sf/<MPN>/`, replace local paths with the basename and add the
   datasheet URL, then add the reference designators to `PARTS` in `tools/pin_audit.py`.
4. `.venv/bin/python tools/pin_audit.py` must report 0 errors.
