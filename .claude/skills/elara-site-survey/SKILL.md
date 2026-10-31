---
name: elara-site-survey
description: Turn site information from Matej (photos, map screenshots, national LiDAR points, his measurements) into ELARA's site model - antenna line, ground profile, tree and house heights, the site diagrams, MOUNTING.md section 6 and the site antenna simulation - without ever putting his location in the repo. Use whenever he sends site photos, map or LiDAR points, or asks about the antenna spot, heights, power lines or transmitters nearby.
---

# Site survey

**Privacy first.** Matej's coordinates (lat/lon, D96/TM E/N, map links) are private.
- Work with them only in the scratchpad (`scratchpad/elev/`, `scratchpad/site/`); never in
  repo files, commit messages, docs, diagrams or PR text. Store everything relative to
  the box foot (distances along the line, heights).
- Before committing: `grep -rn "<first 4-5 digits of E/N or lat/lon>"` over the repo
  (SVG path numbers give false hits; check them).
- External lookups (elevation, OSM) only with his consent; say so.

## Sources, best first
1. **National LiDAR** (he reads it in https://clss.si, D96/TM E / N / H). Ask for points
   ON THE GROUND (a roof or canopy point by mistake skews everything: ask which surface).
   Fit a plane (least squares) to all ground points; check leave-one-out before trusting
   curvature (here: plane 0.19 m rms, quadratic overfit). Canopy-top minus plane = tree
   height; window point minus plane = anchor height.
2. **His measurements** (window height, the tan strip is grass not arable, ...).
3. EU-DEM 25 m via `https://api.opentopodata.org/v1/eudem25m?locations=lat,lon|...`
   (100 pts/request, 1 req/s). Smooths slopes: it gave 6 m where LiDAR gave 13.7 m.
4. OSM for power lines / masts: Overpass is blocked by the proxy; use
   `https://api.openstreetmap.org/api/0.6/map?bbox=` in ~3 x 3 km tiles (larger: HTTP 400).
   Rural LV lines are usually not mapped.
5. Photos: EXIF is stripped by his zip; trig from a single photo with an assumed lens and
   a distant ridge as horizon gave 25 m for a 15 m forest. Use only as a cross-check.

## Where the model lives (update together)
- `images/generate_diagrams.py` `SITE` dict (window, forest_end, box, house, ground
  profile, slope, heights) -> `05_site_plan.svg`, `06_site_elevation.svg`.
- `simulations/antenna/site_antenna.py` constants (L_SPAN, S_BOX, GROUND, Z_WINDOW,
  Z_ANCHOR) -> json/svg; MOUNTING.md section 6 numbers and the top-wire table.
- `simulations/antenna/site_wire.py` (LH, DZ, S_BOX copy the same geometry: change
  both) -> wire tension / thermal sag / ice loads / wind-noise table in MOUNTING.md.
- Render both diagrams and READ them: labels collide with lines after geometry changes.

## Antenna solver traps
- Thin-wire MoM: the self term must be analytic (`2 asinh(L/2a)`); Gauss quadrature of the
  reduced kernel over a 0.7 m segment misses the 1 mm peak and gave +60 % capacitance.
  Always re-check the 10 m monopole against 2 pi e0 h / (ln(h/a) - 1) (67.8 pF) and the
  design T (138 pF).

## Wire mechanics traps
- Thermal sag: never estimate it inextensibly (gives +30 cm); the elastic state-change
  equation with the ropes' compliance gives cm. Dyneema has a NEGATIVE alpha (-12 ppm/K).
- Ice load barely depends on the installed sag (stiff span): protect with a weak link,
  not by installing slacker. A counterweight without a stop drops the wire under ice.
- Wind noise via E0 x dh_eff dwarfs board microphonics; the Aeolian "above the band"
  rule of thumb fails for 3 mm wires at < 0.5 m/s (harmless there, but say why).

### Changelog
- 2026-10-31 wire mechanics (site_wire.py): thermal, ice, modes, wind noise.
- 2026-10-31 created after the site survey session (LiDAR plane fit, diagrams, antenna).
