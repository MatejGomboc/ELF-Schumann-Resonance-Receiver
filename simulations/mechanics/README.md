# ELARA mechanics: modes, microphonics, wind and shock

> **Update 2026-10-31 (shade roof and site):** the site is a stiff post (stilt) in the
> middle of a grassy field at the foot of the vertical down-lead. The sun and rain roof
> (`mechanical/params.py` SHADE_ROOF: white 2 mm aluminium, 500 × 500 mm, centred,
> 15 mm drip flanges, 30 mm above the box) sits on two galvanised 30 × 4 flat-bar arms
> clamped to the same post with M10 U-bolts, never on the box. The model now adds roof
> and arms (**3.1 kg**) at the post top and the drip-edge strip to the frontal area:
> the **114.3 × 6.3 mm, 1 m post's first mode drops from 71 Hz to 62 Hz** (57 Hz with
> ice), still above the Schumann band. Storm uplift on the roof is **about 211 N in
> all, about 105 N per arm** (c_p 1.5 on 0.25 m² at 562.5 Pa); snow on the roof about
> 300 N. The thin poles get worse with the extra mass (48.3 × 3.2: 4.6 Hz, 60.3 × 4.0:
> 6.9 Hz, 76.1 × 5.0: 16.6 Hz): a thin pole or stilt sways at 5-20 Hz, inside the band,
> so the post must still be the stiff 114.3 × 6.3 mm steel one, at most 1 m tall (box
> about 1 m above ground). Microphonics on the 60.3 mm pole at 6 m/s: 31 nV peak (was
> 36); the wall mount stays at 0.18 nV/√Hz at SR1. The 1 mm 500 × 400 roof in the
> tables below (16 Hz on 4 fixings on the box) was the earlier concept and is
> superseded. The model also adds the roof mass to the wall-mount case (rigid-body
> mode 131 -> 106 Hz), which is conservative: on a wall the roof hangs on the wall.

> **Update 2026-10-31 (applied from this study):** plate capacitors on PLATE_RET (only
> 30 mV across the gaps, 1 V worst), two PA66 mid supports under the PE-HD mounting
> plate, a solid 0.8 mm node-2 lead held midway on a PTFE post, the antenna lead tied
> after its gland, and a PEEK + alumina + wave-spring clamp. `results.json` and the
> plots are from the re-run, with these as the "as designed" cases: mounting plate
> **f1 = 114.5 Hz** (transmissibility ~1 in 1-50 Hz; was 27.7 Hz, x6.5), node-2 lead
> threshold 1.8 m/s²/√Hz (was 4.6 mm/s²/√Hz), plate capacitors 0.92 m/s²/√Hz, clamp
> 29-31 N over -20..+60 °C with C drifting 0.18 %. Microphonics: wall mount 0.18 nV/√Hz
> at SR1, pole at 6 m/s 36 nV peak, both under the 45.8 nV floor; Cg (C202) is now the
> largest term. The tables below that quote 27.7 Hz, stranded leads or 2.5 V across
> the plates describe the design before these changes.

This folder looks at the outdoor unit as a mechanical system. ELARA measures a
1–50 Hz electric field with a femtoampere front end, so **any vibration in that band
that changes a capacitance on the input node becomes signal** (microphonics). The
folder covers:

- the modes of both PCBs and of the mounting plate;
- how the air-gap plate capacitors, input leads and Cg respond to acceleration;
- wind on the box (the east Slovenia site), vortex shedding and lock-in;
- transport shock on the heavy parts.

| File | Contents |
|------|----------|
| `plate_fem.py` | Kirchhoff-plate FE solver (conforming Bogner-Fox-Schmit rectangles, non-uniform tensor grid, point/patch supports, point masses, rigid links). Run it on its own for the self-test against Leissa (1969). |
| `run_mechanics.py` | Every case. Writes `results.json` and the plots |
| `modes_amp_pcb_frame.svg`, `modes_amp_pcb_screws.svg` | Amplifier PCB, first 4 modes, two support cases |
| `modes_psu_pcb_clamped.svg`, `modes_psu_pcb_pinned.svg` | PSU PCB, first 4 modes |
| `platecap_mechanics.svg` | Plate modes, sag, gap change per m/s², C drift with temperature, clamp preload |
| `mounting_plate_modes.svg` | Mounting plate modes, transmissibility box → plate capacitor, relative motion at the node2 lead |
| `microphonics.svg` | Threshold accelerations, box acceleration (pole and wall), microphonic EMF against the floor |
| `wind_vortex.svg` | Shedding frequency against structural modes, and pole options |

Run it with `.venv/bin/python simulations/mechanics/run_mechanics.py`. It takes about
90 s on 4 cores. Dimensions come from `mechanical/params.py` and `mechanical/outer_box.py`.
Part positions come from the two `.kicad_pcb` files, so the model follows the design.

FE self-test (λ = ωa²√(ρh/D), square, ν = 0.3):

| Case | FE | Leissa |
|---|---:|---:|
| SSSS | 19.739 | 19.739 |
| CCCC | 35.985 | 35.99 |
| FFFF | 13.468 | 13.47 |
| 4 corner points | 7.111 | 7.12 |

## Verdicts

| # | Item | Result | Verdict |
|---|---|---|---|
| 1 | Amplifier PCB modes | **890 Hz** clamped by the walls; 556 Hz if only the 24 screws clamp | **OK**: far above 50 Hz |
| 1 | PSU PCB modes | **108 Hz** clamped standoffs; 59 Hz pinned | OK for microphonics (it is a supply board), but marginal for transport fatigue |
| 2 | Plate capacitor: plate modes | **1284 Hz** clamped corners (624 Hz pinned); sag 0.23 µm/g | **OK** |
| 2 | Plate capacitor: microphonic threshold | **9.9 mm/s²/√Hz** nominal, **2.2 mm/s²/√Hz** worst case | **Marginal**: a wall at VC-A already reaches 2 mm/s²/√Hz at 8 Hz |
| 2 | Plate capacitor: thermal | C −0.77 % from −20 to +60 °C (−70…−90 ppm/K); divider changes 0.03 dB | **OK** for the RC filter and gain |
| 2 | Plate capacitor: clamp | 23 N/screw at assembly, 16 N at −20 °C, about 4 N at −20 °C after PTFE/PA66 relaxation | **Weak point**: the stack may come loose and rattle |
| 3 | **Mounting plate, PE-HD 8 mm** | **f1 = 27.7 Hz** (20–37 Hz from +60 to −20 °C); transmissibility ×6.5 at the plate capacitor, ×19 at the amplifier | **FAIL**: the first mode sits in the Schumann band |
| 3 | Node2 lead (stranded, 100 mm span) | own mode **≈ 28 Hz**, threshold 4.6 mm/s²/√Hz | **FAIL**: it lines up with the plate mode |
| 3 | Box on a pole (48–60 mm, 2 m) | f = **4.6 / 6.9 Hz** with the roof (5.5 / 8.1 without); buffeting and pole vortex shedding give 0.2–1.4 m/s²/√Hz at the box | **FAIL** for microphonics; strength is fine (SF 4–7.5) |
| 3 | Box on a wall | rigid-body mode on the lugs ≈ 106 Hz with the roof mass added (≈ 130 Hz without) | Preferred mount; residual set by building vibration |
| 3 | Wind strength (30 m/s gust, 562 Pa) | box 102 N; M6 fixings SF > 100; 60.3×4 pole σ = 31 MPa (SF 7.5) | **OK** |
| 3 | Vortex lock-in, box on a pole | v_crit = 11.6 m/s (48.3 pole), 17.4 m/s (60.3), with the roof; both are below the 30 m/s storm gust | **Avoid**: use a wall or a stiff post (f > 50 Hz) |
| 3 | Shield frame, lid, tray, PSU base | 0.7–10 kHz | OK |
| 3 | Shade roof, earlier concept (1 mm Al 500×400 on the box) | **16 Hz** on 4 fixings, 29 Hz on 6; 146 N net wind force | **FAIL**: in band, and it drums in rain and wind (superseded) |
| 3 | **Shade roof as built** (2 mm Al 500×500 centred, on two arms on the 114.3×6.3 post) | 3.1 kg at the post top: post f1 **71 → 62 Hz**; storm uplift 211 N (105 N per arm), snow 300 N | **OK**: still above the band; never fixed to the box |
| 4 | Shock 5 g / 11 ms | every solder joint has SF ≥ 14 static and ≥ 2 fatigue | OK |
| 4 | Shock 15 g / 11 ms (IEC 60068-2-27) | C202 fatigue SF 0.7. **C202 not seated flush: its lead yields already at 5 g (SF 0.42)** | **Seat C202 flush and bond it** |

**Overall.** The boards and the metalwork are fine. The weak links are:

1. **The 8 mm PE-HD mounting plate and the stranded node2 lead.** Both resonate
   near 28 Hz. The plate is compliant and the units on it are heavy.
2. **The 2.5 V DC across the plate capacitors.** It turns 19 pm/√Hz of gap change
   into the whole noise floor.
3. **Pole mounting.** Every practical pole has its sway mode at 5–20 Hz, and vortex
   shedding falls in band at everyday wind speeds.

With the fixes below (6 mm aluminium plate or extra supports, solid or tied leads, a
wall mount), the modelled microphonics on a quiet wall (VC-C) fall to about the floor
(27 nV/√Hz peak). At VC-A they are about 2× the floor (109 nV/√Hz peak).

## 1. PCB modal analysis

Each PCB is a BFS plate model on a 2.5 mm grid. Part masses are lumped at the part's
pads. The masses are estimated from datasheet dimensions × typical density (film caps
1.3 g/cm³, aluminium electrolytics 1.5 g/cm³, potted modules 1.7 g/cm³):

- amplifier: 72 g of parts (C202 43 g);
- PSU: 99 g of parts (IRM-05-15 taken as 40 g, EDLCs 3.6 g each).

FR4 is modelled with E = 22 GPa (4-layer) or 20 GPa (2-layer), ν = 0.14, ρ = 1850 kg/m³,
plus the copper (60 % fill).

| Board, support | f1 | f2 | f3 | f4 (Hz) |
|---|---:|---:|---:|---:|
| Amplifier, clamped under the 7 mm walls and tray rim (notches pinned) | **890** | 1201 | 1365 | 1981 |
| Amplifier, clamped at the 24 screws only (lower bound) | 556 | 750 | 850 | 974 |
| PSU, 4 corner standoffs clamped (5.5 mm hex face) | **108** | 217 | 282 | 400 |
| PSU, 4 corners pinned (lower bound) | 59 | 157 | 202 | 289 |

In the amplifier, mode 1 is in the C2 analogue bay, where C202 sits.

## 2. Air-gap plate capacitor

> **Sections 2.1-2.4 describe the old clamp** of the first run: a 53.1 mm copper
> square, PTFE washers and a loose PTFE centre disc on M3 nylon screws, 2.5 V across
> the gap. The design now has **49.9 mm copper**, 96 % alumina washers (Ø6 / 3.2 x
> 0.5) and an alumina centre disc epoxy-bonded to the lower plate, M3x25 PEEK screws
> with a stainless wave spring under each head (about 30 N), plates paired by
> thickness within 0.02 mm, and the lower plate on PLATE_RET (30 mV across the gap).
> Its results are in the update at the top and in `results.json`: plate-capacitor
> threshold 0.92 m/s²/√Hz, clamp 29-31 N over −20..+60 °C, C drift 0.18 %
> (`mechanical/README.md` section 3).

### 2.1 Geometry and supports

Each capacitor is two 64×64×1.6 FR4 plates with a 53.1 mm copper square and a
**0.5 mm gap set by PTFE washers**. The washers sit on M3 nylon screws at (5, 5) from
each corner. The stack stands on 15 mm PTFE standoffs on the POM base.

- **The gap is set by PTFE, not POM.** The POM base and the standoffs do not set the
  gap.
- **The plates stand vertical when installed.** The mounting plate is vertical and the
  capacitors sit on its face. Gravity therefore acts in the plane of the plates, so the
  installed sag is about zero. **Wind and wall vibration act normal to the plates**,
  which is the sensitive direction.

The corners are modelled as clamped patches of Ø6 mm (washer). The pinned case is a
bound. The node plate carries the R1/R2 and lead masses on its tongues, 0.35 g each.

| Case | f1 (Hz) | Sag at 1 g normal (bench, plates horizontal) |
|---|---:|---|
| Corners clamped | **1284** | 0.23 µm max, 0.14 µm mean over the copper |
| Corners pinned | 624 | 0.91 µm max, 0.64 µm mean |

### 2.2 Gap change under acceleration

Two identical plates on common corner clamps bend together, so the gap does not
change. **Only a mismatch moves it.** Deflection scales as 1/t², so the model uses a
thickness mismatch: 5 % nominal and 10 % worst case. The reason is that IPC-4101 allows
±10 % on 1.6 mm FR4. The model solves both plates together, with or without the loose
centre PTFE disc acting as a spring between them.

| Case (clamped) | Mean copper-gap change per 1 m/s² |
|---|---:|
| Equal plates (tongue masses only) | 0.20 nm |
| 5 % mismatch | **1.77 nm** |
| 5 % mismatch, centre disc in contact | 0.52 nm |
| 10 % mismatch | 3.62 nm |
| 5 % mismatch, pinned corners | 8.9 nm |
| Washer / standoff / screw stack, rigid-body (stack mode 3.3 kHz) | 0.10 nm |

### 2.3 Microphonic signal

At ELF the 33 k resistors are negligible, so ANT, node1 and node2 behave as one node
with C_tot = C_ant + 2 C_plate. A capacitance change dC on a capacitor that carries a
DC voltage V injects a charge V·dC. Referred to the antenna EMF, this gives:

  **e = V_dc · dC / C_ant**, with dC/C_plate = −Δg/g.

The DC across each plate capacitor is the node voltage, because the GND plate is at
0 V and the node plate sits at the **2.5 V** bias through J202. The worst case is
**4 V**: the air-earth current (I_atm × R_hb) offsets the node up to the LMP7715 CM
limit.

- **Nominal:** 5 % mismatch, 2.5 V, two caps with independent mismatch (√2):
  **4.6 µV/(m/s²)**. The threshold is **9.9 mm/s²/√Hz**, flat up to about 1 kHz.
- **Worst case:** 10 % mismatch, 4 V, coherent: 20.8 µV/(m/s²), threshold
  **2.2 mm/s²/√Hz**.
- **The floor is reached by only 19 pm/√Hz** of mean gap change in each capacitor.
- The in-plane sensitivity is 100× smaller: 1.9·10⁻⁵ per µm of overlap shift.
  Friction holds the plate up to about 270 g at the nominal preload.

### 2.4 Thermal (−20…+60 °C)

The model uses these expansion figures:

- **PTFE:** 100 ppm/K below 19 °C and 120 ppm/K above 30 °C, plus about 0.15 % across
  the 19/30 °C phase transitions (Chemours/DuPont handbook order). This is uncertain
  to ±30 %.
- **FR4:** 15 ppm/K in the plane.

| | −20 °C | 23 °C | 60 °C |
|---|---:|---:|---:|
| C per capacitor (pF) | 49.15 | 48.94 | 48.77 |
| Gap (µm) | 497.3 | 500 | 502.3 |
| Clamp force per screw, as assembled (N) | 15.9 | 23.1 | 29.2 |

- dC/dT is **−70 ppm/K at 0 °C** and **−90 ppm/K at 40 °C**. The total is −0.77 % over
  the range, with a jump around 19 °C.
- The RC corner moves by 0.8 % and the divider gain by 0.03 dB: **harmless**.
- Temperature fluctuation becomes signal at 0.22 mV/K of EMF. Reaching the floor
  would need **0.21 mK/√Hz** at 1–50 Hz in the washers. That is impossible inside a
  sealed box, because the thermal diffusion length in PTFE at 8 Hz is about 70 µm.
- **Washer alternatives:** alumina gives +23 ppm/K, and POM washers −80 ppm/K, no
  better than PTFE.
- **The clamp is the real thermal issue.** The 15.5 mm of PTFE in each clamp shrinks
  more than the PA66 screw. That costs 7 N at −20 °C. PTFE (cold flow) and PA66 also
  relax, perhaps by 50 % over months. Together they leave about **4 N per corner at
  −20 °C**. The calculation is only 1D, so this may well be zero. A loose node plate
  rattles, which gives impulsive and non-linear microphonics.

## 3. Mounting plate, box and wind

### 3.1 Mounting plate

The mounting plate is 240×350 mm, held on 4 box bosses (Ø14 clamped patches at
±110, ±165 mm). The units sit on their M4 studs:

| Unit | Mass (kg) |
|---|---:|
| Amplifier | 1.32 |
| PSU | 0.90 |
| Plate capacitors | 0.29 |
| PE-HD plate | 0.64 |
| **Whole box** | **5.9** |

The aluminium masses come from `mechanical/README.md`. The Fibox ARCA 403015 is taken
as 2.3 kg (catalogue order; verify).

- **Nominal model:** each unit is a rigid body on its 4 studs (w-plane plus common
  slopes).
- **Lower bound:** point masses only.
- **Damping:** ζ = 0.03 for PE-HD, 0.02 for aluminium with bolted joints.

| Plate | f1 | f2 | f3 (Hz) | Max \|T\| at plate cap, 1–50 Hz | Max \|T\| at amplifier |
|---|---:|---:|---:|---:|---:|
| PE-HD 8 mm, units flexible (bound) | 22.9 | 27.4 | 70.0 | 5.7 | 18.5 |
| **PE-HD 8 mm (as designed)** | **27.7** | 81.3 | 88.8 | **6.5** | **18.7** |
| PE-HD 8 mm at −20 °C (E 1.6 GPa) | 36.9 | 108 | 118 | 6.4 | 18.8 |
| PE-HD 8 mm at +60 °C (E 0.45 GPa) | 19.6 | 57.5 | 62.8 | 6.5 | 18.7 |
| PE-HD 15 mm | 66.7 | 196 | 222 | 1.5 | 2.4 |
| Al 3 mm | 54.5 | 159 | 174 | 2.8 | 6.3 |
| **Al 6 mm** | **143** | 417 | 476 | 1.05 | 1.16 |
| PE-HD 8 mm + 2 supports at (±110, +50) | 115 | 203 | 224 | 1.02 | 1.0 |

Mode 1 is the amplifier and PSU bouncing together on the plate.

**Mechanical consequence:**

- 1 g deflects the plate by 0.41 mm.
- A 5 g / 11 ms shock gives 2.2 mm and 5.9 MPa von Mises. That is fine against the
  22 MPa yield, but above a 4 MPa long-term creep level.
- Each boss screw carries 41 N at 5 g.

**Also, the units move relative to each other:** 25 µm per m/s² quasi-static, up to
0.4 mm per m/s² at the plate mode. This flexes the node2 lead between the IN+ post
and the PTFE bush.

### 3.2 Site wind (east Slovenia)

The wind model follows EN 1991-1-4 with the Slovenian NA (SIST EN 1991-1-4/oA101):

- **Basic wind velocity:** wind zone 1 (lowland < 800 m, includes Prekmurje and
  Pomurje), **v_b,0 = 20 m/s**. The zone value comes from memory of the NA map; check it
  against the NA. 25 m/s is run as a sensitivity case.
- **Terrain:** category II (open farmland, z0 = 0.05 m), box centre z = 2 m (= z_min).
- **Result:** v_m = 14.0 m/s, I_v = 0.27, **q_p = 356 Pa**. That is a 23.9 m/s
  equivalent peak; with 25 m/s, q_p = 556 Pa.
- **Thunderstorm downburst gust:** 30 m/s taken as a peak velocity, **q = 562.5 Pa.
  This governs.**
- **Force coefficients** (EN 7.6, Fig. 7.23 and 7.36): c_f = c_f,0 × ψ_λ.
  - Wind on the door: d/b = 0.5, c_f,0 = 2.35, ψ_λ = 0.64, so **c_f = 1.51**.
  - Side wind: c_f = 1.11.
  - The 1.05–1.2 of a free cube is lower. EN's 2D value with end effects is the
    conservative choice.
- **Forces:** F_door = **102 N**, F_side = 37 N.
- **Box fixings:** assumed 4 × M6 A2-70 through the box lugs, 260 × 430 mm pattern.
  - Tension: 42 N per screw. Shear: 24 N (with the roof's mass and drip strip).
  - SF > 100 on the screw. SF about 130 on PC pull-through (Ø12, 4 mm wall, 60 MPa).
- **Ice and snow are minor:** 10 mm glaze adds 2.6 kg and drops the pole mode by
  about 13 %. Snow on the top face is about 54 N.

| Pole (S235, box at the top) | f (Hz) | f with ice | σ_base at design gust (MPa) | SF yield | Deflection (mm) | v_crit box (m/s) | v_crit pole |
|---|---:|---:|---:|---:|---:|---:|---:|
| 48.3×3.2, 2.0 m | **4.6** | 4.2 | 58 | 4.1 | 11 | **11.6** (EN E.1.3.1 check needed: < 1.25 v_m) | 1.2 |
| 60.3×4.0, 2.0 m | **6.9** | 6.3 | 31 | 7.5 | 4.6 | 17.4 (EN E.1.3.1 check needed) | 2.3 |
| 76.1×5.0, 1.5 m | 16.6 | 15.1 | 12 | 20 | 0.8 | 42 | 7.0 |
| **114.3×6.3, 1.0 m (the site's post)** | **62** | 57 | 2.7 | 86 | 0.05 | 155 | 39 |
| Wall, 4 lugs (k ≈ 1e6 N/m each, estimate) | ≈106 | | | | | | |

All with the shade roof and its arms (3.1 kg) at the top. Without the roof the
frequencies were 5.5 / 8.1 / 19.3 / 71 Hz and the wall ≈ 130 Hz.

**Vortex shedding:**

- **Box:** St = 0.12 on 0.30 m, so **f_s = 0.4 Hz per m/s**: 1–4 Hz in everyday wind
  and 12 Hz in a storm. Edge-on, d/b = 2 gives St = 0.06 on 0.15 m, which is the same
  frequency.
- **48 mm pole:** 3.7 Hz per m/s, so a 3–10 m/s wind sheds at **11–37 Hz**, inside the
  band.
- **Lock-in:** a pole of 1.5–2 m locks in with the box in storms (v_crit 14–20 m/s,
  Sc ≈ 17–19). The pole's own shedding crosses its sway mode at 1.5–3 m/s.
- **To keep both out of the band:** the support needs f > 50 Hz. That means a wall, or
  a short heavy post such as 114×6.3 mm, 1 m.

### 3.3 Shield, panels and roof

| Part | f1 (Hz) |
|---|---:|
| Amplifier lid / tray floor, C1 / C2 / C3 bays (2 mm Al, clamped) | 9849 / 3179 / 3088 |
| Shield as a free-free beam (two 7×52 bars) | 3048 |
| Shield on its 4 ear studs (ear bending + stud in PE-HD) | 739 |
| PSU base panel (3 mm Al) | 2108 |
| Shade roof, earlier concept: 1 mm Al 500×400 on the box, 4 fixings | 16 |
| Same, 6 fixings | 29 |

Stud loads at 5 g are 28 N (amplifier) and 19 N (PSU) per stud, with < 1 MPa bearing
on the PE-HD. The weight moment from the 30–40 mm CG offset is only 2–4 N per stud.
The earlier 500×400 roof concept saw 146 N net wind force (c_f 1.3 on 0.2 m²), about
1.4× the box itself. The roof as built (2 mm, 500×500, drip flanges on all four
edges, on two 30×4 flat-bar arms clamped to the post) is not fixed to the box; it
adds 3.1 kg at the post top and sees about 211 N of storm uplift (105 N per arm) and
about 300 N of snow (section 3.2 and the update note).

## 4. Microphonics budget

### 4.1 Threshold acceleration at SR1

This is the acceleration *at the part* that gives 45.8 nV/√Hz at the antenna. The
sources are, in short: the plate capacitors (section 2); a lead over a ground plane
(C' = 2πε₀/acosh(h/r), driven by its first bending mode); and Cg, from inertial
pressure on the PET winding (E_eff 0.5–5 GPa, 2.5 V across it).

| Source | V/(m/s²) | Threshold (m/s²/√Hz) |
|---|---:|---:|
| Plate capacitors, 5 % mismatch, 2.5 V | 4.6e-6 | **0.0099** |
| Plate capacitors, worst (10 %, 4 V, coherent) | 2.1e-5 | **0.0022** |
| Node2 lead, stranded 0.5 mm² (19×0.18), 100 mm span, f1 = 28 Hz | 1.0e-5 | **0.0046** |
| Node2 lead, solid Ø0.8, f1 = 94 Hz | 8.1e-7 | 0.056 |
| Antenna lead (gland → ANT post), stranded, f1 = 44 Hz | 1.5e-6 | 0.031 |
| C202 Cg film (E_eff 1 GPa; 0.5…5 GPa) | 5.9e-8 | 0.78 (0.39…3.9) |
| Guarded IN+ node (guard follows IN−, V_dc < 0.2 mV) | – | negligible |

For comparison, the building-vibration criteria at 7.8 Hz are:

| Criterion (1/3-octave velocity) | Acceleration ASD |
|---|---:|
| VC-C (12.5 µm/s) | 0.00047 m/s²/√Hz |
| VC-A (50 µm/s) | 0.0019 m/s²/√Hz |
| ISO residential day (200 µm/s) | 0.0075 m/s²/√Hz |

### 4.2 Spectra

There are two excitation cases:

- **Pole** (60.3×4, 2 m). Buffeting uses the EN B.1 spectrum (L = 27 m, I_v = 0.27)
  with Vickery's admittance. Vortex shedding uses a Gaussian lift spectrum: box
  c_L,rms 0.3, pole 0.25, bandwidth 0.2 f_s. The SDOF has δ_s = 0.05 plus aerodynamic
  damping.
- **Wall.** Constant 1/3-octave velocity criteria.

Both pass through the mounting-plate transmissibility. The table gives peak values in
3–50 Hz.

| Case | Box a, max (m/s²/√Hz) | EMF at SR1 | EMF max (nV/√Hz) | at (Hz) | Band above floor | With Al 6 mm + solid lead |
|---|---:|---:|---:|---:|---:|---:|
| Pole, 3 m/s | 0.22 | 639 | 3 231 | 8.1 | 26 % | 1 089 |
| Pole, 6 m/s | 0.37 | 1 324 | 5 365 | 8.1 | 85 % | 1 808 |
| Pole, 10 m/s | 1.4 | 5 613 | 77 200 | 27.8 | 94 % | 7 016 |
| Wall, VC-C | 0.0011 | 6.6 | 2 486 | 27.8 | 17 % | **27** |
| Wall, VC-A | 0.0046 | 27 | 9 944 | 27.8 | 43 % | **109** |
| Wall, ISO residential day | 0.018 | 106 | 39 780 | 27.8 | 100 % | 435 |

**How to read the peaks.** The 28 Hz peaks are the product of two Q ≈ 17 resonances:
the PE-HD plate mode and the stranded lead mode. Both frequencies are uncertain to
±30 %, so the coincidence (and its 1e4 nV/√Hz height) is *indicative*. The robust
conclusion is that **both resonances sit in the band** and have to be moved out.

### 4.3 The antenna itself (context, out of scope here)

The fair-weather field E₀ ≈ 130 V/m puts **E₀·h_eff ≈ 850 V** on the antenna's charge.
Moving the effective height by **0.35 nm/√Hz** therefore equals the floor, and 1 mm of
vertical motion is about 130 mV. Wind-driven motion of the top wire will dominate
every effect in this folder. `simulations/antenna/site_wire.py` models it for the
planned site: the wire's vertical string modes start at 0.55 Hz and fill the band
(47 modes from 7.8 to 34 Hz). Gust buffeting puts the SR1 noise above the floor at
any wind over ~0.3 m/s, and above a typical signal over ~2 m/s. Aeolian shedding of
a 3.2 mm wire (f = 0.2 U / D) is in band only at 0.1–0.5 m/s, where the forcing is
negligible. Damping and tension hardly help, so record in calm weather and log the
wind. The same script gives the wire's thermal sag change (under 2 cm from −25 to
+40 °C) and its ice and storm loads (MOUNTING.md section 6).

## 5. Transport shock (half-sine, 11 ms)

The board response comes from modal superposition (ζ = 0.03), using the weaker
support case: the amplifier on its screws only, the PSU pinned. In-plane loads take
1.7 × the pulse, the SRS peak for the parts' rocking.

Solder check:

- Shear area per lead: the PTH barrel, π·d·1.6 mm.
- Allowables: **20 MPa static** and **3 MPa fatigue** (SAC305, > 1e6 cycles).
- Seated parts: the body edge is the fulcrum.
- Not seated: the leads bend. Lead yield is taken as 150 MPa.

| Part | Normal a at 5 g (g) | SF solder static / fatigue, 5 g | 15 g | SF lead if *not* seated, 5 g |
|---|---:|---:|---:|---:|
| C202 WIMA MKS4 100 µF, 43 g, 39.5 mm tall | 5.2 | 14 / 2.1 | 4.7 / **0.71** | **0.42** |
| C301 MKS4 10 µF | 5.0 | 83 / 12 | 28 / 4.1 | 3.7 |
| C207 4700 µF 16×25 | 5.1 | 81 / 12 | 27 / 4.1 | 1.9 |
| PS1 IRM-05-15 (40 g assumed) | 6.3 | 71 / 11 | 24 / 3.6 | 1.6 |
| C8–C15 EDLC 10×31.5 | 9.8 | 64 / 9.6 | 21 / 3.2 | 1.3 |
| C16 2200 µF 12.5×20 | 6.1 | 108 / 16 | 36 / 5.4 | 1.8 |
| K1–K4 SIL05 reed relay | 9.9 | 397 / 60 | 132 / 20 | 9.4 |
| L1 SRF1260 (SMD) | 5.4 | 1919 / 288 | 640 / 96 | – |

**Board deflection:**

- **PSU pinned:** 0.81 mm at 5 g, against the Steinberg allowable of 0.84 mm for an
  SOIC-16 over a 150 mm span (fatigue-based). That is marginal for long transport
  vibration. Clamped, it is 0.24 mm: OK. At 15 g it is 2.4 mm.
- **Amplifier:** < 0.02 mm. OK.

## 6. Recommended design changes (not made here)

1. **Mounting plate.** Replace the 8 mm PE-HD with **6 mm aluminium** (f1 143 Hz),
   or keep the PE-HD and add two supports at (±110, +50). The supports could be
   insulating standoffs to the box back or to a back-plate stiffener (f1 115 Hz). The
   README already offers 3 mm aluminium, but at f1 54 Hz it is still marginal. A metal
   plate adds about 2–3 pF at ANT: keep the ANT post 20 mm clear.
2. **Node2 and antenna leads.**
   - Use solid silver-plated wire (Ø0.8–1.0 mm) instead of stranded PTFE hook-up
     wire, kept short and straight. Better still, support the lead midway on a PTFE
     post so its first mode is > 150 Hz.
   - Move the IN+ post and the PTFE bush close together. At 12 mm over the tray,
     each mm of lead adds 0.28 fF per mm of lead motion.
   - Tie the antenna lead to a PTFE post right after the gland.
3. **Plate-capacitor DC.** Remove the DC across the gap: return the "GND" plates of
   C_A/C_B to the 2.5 V bias reference (the quiet BIAS_BUF/VCOM node) instead of GND.
   - This cuts the plate microphonics by V_dc/V_offset, about 1000×.
   - Check the noise first: the reference noise couples in at about
     2 C_plate / C_ant (0.7× EMF-referred). An LMP7715 at 5.8 nV/√Hz behind the
     4700 µF filter is acceptable, but run a SPICE check.
   - It also makes J202's offset (I_atm × R_hb) the only DC left. A smaller R_hb, or
     the insulated antenna option, helps here too.
4. **Plate-capacitor clamp.** Replace the PA66 screws with **PEEK** (47 ppm/K, low
   creep) and the PTFE washers with **0.5 mm alumina or quartz spacers**:
   - +23 ppm/K and no 19 °C step;
   - no cold flow;
   - lapped thickness makes plate matching easier.
   Add a wave or Belleville washer under each head to hold the preload from −20 to
   +60 °C. Either glue the loose centre PTFE disc, or remove it. Contact without
   preload can rattle; bonded, it cuts the mismatch response 3–4×. Match the two
   plates of each capacitor (same panel) so the thickness mismatch stays < 3 %.
5. **Mounting.** Mount the box on a **building wall**, or on a short, heavy post with
   its sway mode > 50 Hz (e.g. 114×6.3 mm, ≤ 1 m). Do not use a 1.5–2 m pipe or the
   antenna mast: the sway mode is at 5–20 Hz, and box and pole shedding fall in band at
   everyday wind speeds. Before installing, measure the wall with a geophone or
   accelerometer. The threshold to beat is a few mm/s²/√Hz at 5–50 Hz.
6. **Shade roof (B11).** Stiffen the 1 mm sheet with folded 15 mm edges and a centre
   crease, or use 2 mm, aiming for f1 > 60 Hz. **Fix it to the wall or post, not to
   the box**, with rubber-free rigid brackets, so rain drumming and flutter do not
   reach the box. Design its fixings for about 150 N of net wind force, either sign.
   (Done 2026-10-31: 2 mm, 500 × 500, 15 mm drip flanges on all four edges, on two
   30 × 4 flat-bar arms clamped to the post with M10 U-bolts; uplift about 105 N per
   arm; post f1 62 Hz with it.)
7. **C202 (Cg, 43 g, 39.5 mm tall).** Seat it flush and bond it to the board with a
   neutral-cure silicone or epoxy fillet, or a strap. If it stands off, its leads
   yield at 5 g lateral, and seated it has fatigue SF 0.7 at 15 g. Bond the EDLC bank
   and C16 to each other or to the board in the same way.
8. **PSU PCB.** Add a fifth standoff near the board centre, between the EDLC rows, if
   the layout allows. Otherwise make sure all four standoffs clamp (not just locate) the
   board. That lifts f1 from 59–108 Hz to > 200 Hz and keeps the deflection within
   Steinberg's allowable.

## 7. The least certain assumptions

**Electrical**

- **V_dc = 2.5 V across the plate capacitors** (GND plate at 0 V). The microphonic
  numbers scale linearly with it.

**Plate capacitor**

- **Plate thickness mismatch** of 5 % nominal and 10 % worst. It is unmeasured and sets
  the plate-capacitor sensitivity linearly.
- **The corner clamps** are modelled as clamped. A pinned (worn or loose) clamp is
  5× more sensitive.
- **PTFE expansion**, including the 19 °C step, and **relaxation** (50 % assumed).
- **Air permittivity** changes with humidity (Δε_r ≈ 1e-4). This is not modelled.
  It is slow and small.

**Part data**

- **Masses:** IRM-05-15 taken as 40 g (the task suggested about 30 g; check the Mean
  Well datasheet). C202 is 43 g, estimated from volume. The Fibox ARCA 403015 is
  2.3 kg.

**Mounting plate and leads**

- **PE-HD:** modulus 0.9 GPa at 23 °C (0.45–1.6 GPa over the range) and damping
  ζ 0.03.
- **Node2 lead:** stranded 19×0.18 with a 100 mm free span and 50 mm at 12 mm over the
  tray. The geometry is estimated from `mechanical/README.md`; the real route is not
  drawn.
- **Cg microphonics:** effective winding modulus 0.5–5 GPa. This is order-of-magnitude
  only; even the worst case is 40× below the plate capacitors.

**Wind and mounting**

- **Wind and vortex parameters:** c_L,rms 0.3 (box) and 0.25 (pole), shedding
  bandwidth 0.2, δ_s 0.05.
- **Slovenian NA:** zone 1, v_b,0 = 20 m/s for NE Slovenia (from memory of the NA map).
  It does not govern; the 30 m/s storm gust does.
- **Box mounting:** the box is designed for a wall (Fibox lugs). The pole cases assume
  a generic bracket. The wall lug stiffness (1e6 N/m) is a guess.
- **Vibration levels:** building vibration is taken from the VC / ISO criteria curves,
  not measured.

## Sources

- **EN 1991-1-4:2005:** §4 and Annex B (wind profile and turbulence), §7.6 with
  Fig. 7.23/7.36 (rectangular sections), Annex E (vortex shedding and Strouhal),
  Annex F (damping). Slovenian NA: SIST EN 1991-1-4:2005/oA101.
- **Plates:** A. W. Leissa, *Vibration of Plates*, NASA SP-160 (1969), for the FE
  self-test. Bogner, Fox & Schmit (1965), for the element.
- **Vibration criteria:** C. G. Gordon, "Generic criteria for vibration-sensitive
  equipment", SPIE 1619 (1991).
- **Vortex shedding:** B. J. Vickery & A. W. Clark, "Lift or across-wind response of
  tapered stacks", J. Struct. Div. ASCE (1972), for the shedding bandwidth.
- **Shock and fatigue:** D. S. Steinberg, *Vibration Analysis for Electronic
  Equipment*, 3rd ed. (2000), for the board-deflection criterion and solder allowables.
  IEC 60068-2-27 for shock.
- **Materials:** IPC-4101 (laminate thickness tolerance); Chemours Teflon PTFE
  handbook (thermal expansion and creep); PA66, PEEK and PE-HD datasheet-typical
  values.
- **ELARA:** PLAN.md §3.0, simulations/system (45.8 / 74.8 nV/√Hz floor, divider
  0.583), mechanical/params.py and README.
