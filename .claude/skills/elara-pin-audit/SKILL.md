---
name: elara-pin-audit
description: Verify IC pinouts and pin usage against manufacturer datasheets with Adom DS2SF and tools/pin_audit.py. Use when adding or changing an IC, making or deriving a symbol, or when asked whether a part is wired correctly.
---

# Pin audit

1. Get the manufacturer PDF (if a download is blocked, ask the user to upload it; do
   not spoof user agents). Read the pin table yourself first:
   `pdftotext -layout -f N -l N part.pdf - | less`. That is the reference.
2. Extract: `adom-ds2sf --ai-thread "elara pin audit" extract <dir> --pdf <pdf> --mpn <MPN>
   --manufacturer "<maker>" --source-tier mfr --symbol-only` (binary from
   https://wiki.adom.inc/download/adom/adom-ds2sf/latest?platform=linux&arch=x64,
   uses the `claude` CLI, ~$0.5/part). The "service-kicad unreachable" health
   warning is harmless for extraction.
3. Copy the three JSON files to `datasheets/ds2sf/<MPN>/`, scrub local paths to basenames,
   add the datasheet URL, add refdes -> MPN to `PARTS` in `tools/pin_audit.py`.
4. Parts with mode-dependent pin names (CS8406 hardware mode): hand-read the mode table
   into `<MPN>-<mode>-mode.json` (`{"source": "...p.N", "pins": {"1": "COPY/C", ...}}`).
5. `.venv/bin/python tools/pin_audit.py` -> 0 errors. A name mismatch in a stock KiCad
   symbol is fixed with `derived(..., pin_names={...})` in design.py, never by hand.

## Lessons
- Stock KiCad symbols can be wrong: Audio:CS8406 swaps pin 17/18 names (V/U) in
  hardware mode (DS580F6 p.29).
- LMP7721 is non-standard: 1 IN+, 3 V-, 4 OUT, 6 V+, 8 IN-; pins 2 and 7 go to guard.
  An "SOIC-8 op-amp" assumption is how the original design got it wrong.
- Negative-supply pins on GND (single-supply op-amps) are legitimate; the rule exempts
  datasheet names V-/VEE/GND.
- Add name aliases (`ALIAS` in pin_audit.py) rather than loosening the match.
- pin_audit checks names and nets, not logic levels: check every mode strap's
  default against the datasheet's mode table by hand. PCM1804 S/M is LOW = master
  (Table 4); the docs had it inverted, which gives no clock at all.
- Mode-table defaults are where datasheets bite: CS8406 hardware mode HWCK1..0 = 11 is
  256 fs (not 128 fs); TPS3808 CT to VDD goes through 40-200 k. Read the table, not
  the pin name. Hand-read extractions (no DS2SF) are fine: same JSON layout, a note
  saying so (datasheets/ds2sf/TPS3808G01, OPA388).
- Passive parts with numbered windings or pins (chokes, transformers, relays) are not
  in the audit: check them against the maker's drawing by hand.
- A fresh-eyes review agent (schematic + layout + datasheets) found five real issues
  the checks cannot see; run one before ordering after larger changes.

## Maintaining this skill
Update the lessons whenever an audit finds something. Changelog:
- 2026-10-31 created; 9 ICs audited, CS8406 label fix.
- 2026-10-31 strap-polarity lesson (PCM1804 S/M), CS8406 TCBLD high.
- 2026-10-31 mode-table and passive-pinout lessons (CS8406 HWCK, TPS3808 CT, SRF1260).
- 2026-10-31 hand-read extractions for discretes and regulators (LM317, L78L, Si2319, TL431,
  MCR100): directory name = the MPN in design.py exactly; datasheet words (Adjust, CATHODE,
  Gate) map to symbol names through ALIAS in pin_audit.py.
