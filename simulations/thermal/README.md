# ELARA outdoor unit -- thermal simulations

> **Update 2026-10-31 (shade roof, as built):** the sun and rain roof is now modelled
> geometrically: the sunlit fraction of each box face comes from ray casting from a
> grid on the face to the roof plane, using the roof's real size and position
> (`mechanical/params.py` SHADE_ROOF: 500 × 500 mm, centred over the box, 30 mm above
> it), instead of "all beam blocked". The roof is on in every case, with "no roof"
> references; the old ideal "beam blocked" case is kept as a reference. Record 40 °C
> day, light grey box: **EDLC 62.0 °C (door S), 62.2 °C (N), 62.8 °C (W), 63.7 °C
> (E, the worst)**, against 65.4 °C without the roof. The verdict "EDLC ≤ 65 °C (light
> grey, record summer, shade roof, door any way)" **passes**: every design verdict now
> passes, and only the rejected vented box ("no condensation on the inner walls,
> autumn clear night") still fails, by design. Face the door north or south. A
> wall-flush 500 × 400 roof would have left only 0.4 K of margin with an east door,
> hence the centred 500 × 500 (on a free-standing post the sun reaches the back too).
> With the roof the heater works less: PCM1804 minimum **−2.92 °C** in the −18 °C cold
> spell (duty 42 %, 299 Wh/day) and **−7.72 °C** at −25 °C with 5 m/s wind (77 %,
> 553 Wh/day); on a battery the amplifier board reaches −16.8 °C in the cold spell.
> The heater figures in the notes below are the earlier values without the roof.

> **Update 2026-10-31 (box heater):** a mains-side **STEGO HG 140 30 W** PTC heater
> (art. 14001.0-00) on a DIN rail on the PSU box lid, switched by a **STEGO KTO 111**
> NC thermostat (art. 11100.0-00, set to +5 °C, 7 K ± 4 K switching differential),
> heats the outdoor-box air. It runs on mains only, never from the receiver supply,
> so a battery-powered unit has none. It is on in every mains-powered case (as
> built; the thermostat keeps it off above +5 °C box air), with reference cases
> without it. **PCM1804 minimum −3.98 °C** in the −18 °C cold spell (−17.2 °C without)
> and **−8.76 °C at −25 °C outside with 5 m/s wind** (−22.0 °C without): the verdict
> "PCM1804 ≥ −10 °C down to −25 °C outside" now passes. Heater duty 49 % (351 Wh/day)
> at −18 °C, 79 % (571 Wh/day) at −25 °C, about 5 % (36 Wh) on the autumn clear night,
> 0 in every summer case. A run with a real on/off thermostat gives ~3 min cycles
> with 4.9 K pp in the box air but only **9 mK pp at the LMP7721**, at mHz. The only
> remaining FAIL then was the EDLC at 65.4 °C on a record 40 °C day without the shade
> roof (settled by the roof, above).
> The heater also lifts the amplifier board above the dew point on the autumn night
> in a vented box (+1.6 K), but the sealed box with silica gel stays the design.
> The LM317 tabs are **not** bolted to the aluminium base (PSU decision 2026-10-31):
> 0.17–0.22 W each in normal use, junction at most about 78 °C on a record summer
> day; in the crowbar fault the CC LM317 (about 2.5 W) protects itself with its
> internal thermal limit.
>
> **Earlier update 2026-10-31 (applied from this study):** CS8406-DZZ, LM317BTG and
> L78L12ABUTR (all −40 °C), a sealed box with an ePTFE vent and silica gel, and a white
> shade roof. Every design check now passes; the two "vented box" failures describe the
> rejected option. The PSU's LM317 tab copper was grown to the board edge with 26
> thermal vias per tab: re-simulated, it lowers the LM317s by only 0.3–0.5 K (the PSU
> board's rise is set by the whole board heating its box air, not by local spreading).
> Bolting the tabs to the base was considered and rejected (see above). Charger now
> CV 10.76 V (R4 909 R).

This folder checks the outdoor unit thermally at three levels:

- **the two PCBs**: a steady-state 2-D heat-spreading model with the real copper
  and parts;
- **the outdoor box**: a 24 h transient with sun, sky, wind and the three
  enclosures inside it, for east Slovenia;
- **the front end**: the LMP7721 bias current against temperature, swing
  rates, and whether clouds or gusts can reach the input below 1 Hz.

It also answers a direct question: **does white solder mask help?** (section 2.4)

| File | Contents |
|------|----------|
| `run_thermal.py` | Every model. Writes `results.json` and four plots |
| `thermal_boards.svg` | Temperature rise maps of the amplifier board (above its shield) and the PSU board (above its box) |
| `thermal_enclosure_24h.svg` | Summer design day for grey, white and black boxes under the shade roof and the ideal beam-blocked shade; PSU contents; front-end dT/dt; daily ranges on every design day |
| `thermal_frontend.svg` | LMP7721 Ib and SR1 noise against temperature; transfer from sun and wind to the LMP7721 temperature; equivalent voltage at IN_P |
| `thermal_cold_condensation.svg` | Autumn condensation night, and winter cold (−18 °C with and without the heater, −25 °C with 5 m/s wind, battery without heater, the on/off thermostat's box air) against the parts' minimum temperatures |

Run it with `.venv/bin/python simulations/thermal/run_thermal.py`. It takes about 25 s.

## 1. Models

### 1.1 Board level (2-D finite differences, 0.5 mm grid)

- **Copper.** The script reads `PCB/<board>/<board>.kicad_pcb` with a small
  S-expression parser. It rasterises every zone fill and track on every copper
  layer, so each cell's in-plane conductance is
  Σ k_Cu·t_Cu·(coverage) + k_FR4·t_board. Coverage comes out as:
  - amplifier: F 93 %, In1 93 %, In2 90 %, B 97 %;
  - PSU: F 41 %, B 47 %, because the primary and bucket areas have no pour.
- **Heat sources.** Each part's dissipation is spread over its courtyard at its
  real position on the board. Its junction (or case) temperature is the local
  board maximum + P·θ_JB.
- **Heat loss.** Each face of the board loses heat to the aluminium enclosure
  across its air gap. Convection uses an enclosed vertical slot (Nu ≥ 1); the
  amplifier has 52 mm above the board and 12 mm to the tray, the PSU 38 mm and
  10 mm. Radiation runs between the board (ε 0.9; ENIG island 0.05) and the
  bead-blasted aluminium (ε 0.25).
- **Amplifier walls.** The exposed GND strips are bolted to the shield walls
  (`mechanical/params.wall_rects()`). The perimeter strips are clamped by both
  the frame and the tray rim, the two internal strips by the frame only. Both
  use h_contact = 300 W/m²K, swept from 100 to 1000.
- **PSU extras.** The IRM-05 case and the eight EDLC cans shed heat from their
  own surfaces. The two metal M3 standoffs (H1/H3) conduct 0.1 W/K each, the
  nylon ones (H2/H4) almost nothing.
- **Reference temperature.** Every board result is a rise above its enclosure
  wall. The enclosure model then supplies the wall temperature.

### 1.2 Enclosure level (lumped transient network, 12 nodes, LSODA, 3 days to periodic)

```
sun (beam + diffuse + ground-reflected) -> 6 box faces (PC 4 mm, alpha, eps 0.9)
     faces <-> ambient (wind convection), sky (Berdahl-Martin), ground (T_a + 8 K at 1000 W/m2)
     faces <-> box air (natural convection) <-> mounting plate, amplifier shield, PSU box
     all inner surfaces <-> mean-radiant-temperature star node (Walton)
     plate <-> back wall (10 mm boss gap); shield lid / PSU base <-> plate (5 mm spacers + studs)
     amplifier board <-> shield, PSU board <-> PSU box   (conductances from the 2-D models)
```

Each board's temperature map rides on its enclosure temperature from this
network. For example, T_U201 = T_shield + κ·(T_board − T_shield), where κ is
taken from the 2-D field.

The frequency response (section 2.6) comes from the network's Jacobian,
linearised at 13:00 on a summer day, with the sun or the wind as the input.

### 1.3 Assumptions

| Item | Value | Source / basis |
|------|-------|----------------|
| PCB | 1.6 mm FR4, k 0.3 W/mK; 35 µm outer, 17.5 µm inner copper | ASSEMBLY.md (FR4, 1 oz, ENIG); JLCPCB default 4-layer stack (inner 0.5 oz, **assumed**) |
| Mask IR emissivity | 0.90 (any colour; white 0.88) | typical solder-mask / paint IR values (0.85–0.95) |
| Aluminium | ε 0.25 (bead-blast + chromate) | mechanical/README.md finish; textbook 0.2–0.4 for blasted Al |
| Strip-to-wall contact | 300 W/m²K average (100–1000 swept) | M3 bolts every ~35 mm at 0.6 N·m on ENIG/Al, no interface material (**assumed**) |
| +5VA / +3V3 load | 40 / 45 mA | design.py power-sheet budget |
| ADM7150 ground current | 5 mA each | as simulations/psu |
| LMP7721 / LMP7715 I_S | 1.3 / 1.15 mA | datasheet typ. |
| PCM1804 | 35.2 mA from 5 V (the rest of the 40 mA budget), 15 mA from 3.3 V at 192 kHz = 225 mW | datasheet ~220 mW typ.; split **assumed** |
| CS8406 + AES3 | 15 mA through 2×33.5 Ω driver + 2×22 Ω + 110 Ω line; core takes the rest of the 45 mA budget (50 mW in the IC) | design.py note |
| SiT2001B | 4.5 mA | datasheet typ. with load |
| Amplifier input | 6.0 V from the PSU (6.98 V − 7.2 Ω × 95 mA − 0.3 V SS34); 9.3 V fresh PP3; 14.7 V for the "13 V battery (upper bound)" case (modelled at 15 V, kept as a conservative bound) | simulations/psu, design.py |
| PSU charger | periodic bucket model: CC 0.2016 A → CV 10.4 V (10.76 V since the review: not re-modelled here), 2.2 Ω + ESR 0.2 Ω, SS34 V_F = 0.27 + 0.33·I, 15.2 s half period, 97.8 mA drain; LM317 dropout 1.55 V + 0.6 Ω·I | design.py, psu_model.NOMINAL (reproduces its 9.46–10.05 V sawtooth) |
| IRM-05-15 efficiency | 75 % at 2.0 W out (41 % load) | datasheet 80 % at full load; light-load value **assumed** |
| Relay coils | 2 strings of 2 × 200 Ω + 82 Ω from 12 V = 24.9 mA, both strings energised in the same half period (50 % duty) | design.py |
| θ_JB / θ_JC | ADM7150 15, PCM1804/CS8406 45, SOIC-8 60–90, LM317 θ_JC + tab 6, LT3045 10, L78L12 SOT-89 40 K/W | package-typical (**assumed**, datasheets give θ_JA) |
| Box | Fibox ARCA 403015, 300 × 400 × 150 mm, PC 4 mm (ρc_p 1.5 MJ/m³K), IR ε 0.9, wall-free on a post in a field, door facing N, E, S or W | mechanical/params.py, bom |
| Shade roof | 500 × 500 mm, centred over the box, 30 mm above its top; sunlit fraction of each face by ray casting (12 × 12 points) to the roof plane, drip flange ignored (a little conservative); under the roof the top face sees no sky and the sides half their sky | mechanical/params.py SHADE_ROOF, BOX_OUTER |
| Box solar absorptance | light grey RAL 7035 **0.55**, white paint 0.25, black 0.95 | ASHRAE / paint tables (light grey 0.45–0.6, white 0.2–0.3) |
| Units inside | shield 1.09 kg Al, PSU box 0.70 kg Al, plate 1.2 kJ/K, boards 130 / 160 J/K; areas from params.py | mechanical/params.py |
| Inside convection | h = 1.42·(ΔT/L)^0.25, ≥ 1 W/m²K | laminar natural convection, air |
| Outside convection | (h_nat³ + (2.8 + 3.0·v)³)^(1/3) | Watmuff/Duffie-Beckman flat-plate wind correlation |
| Site | 46.5 N, 16.0 E (Maribor / Ptuj / Murska Sobota) | user |
| Sun | Meinel/ASHRAE clear sky, DNI = 1361 × 0.7^(AM^0.678), diffuse 0.12 × DNI, albedo 0.2; 15 Jul gives GHI 1000 W/m² at solar noon | consistent with PVGIS clear-sky July values for this location (≈ 950–1000 W/m²; not fetched) |
| Summer design day | 37 °C max (16:00 CEST), 21 °C min, T_d 18 °C, wind 1 m/s (calm, worst); record case 40/24 °C | ARSO normals: Pannonian summer peaks 35–38 °C, record ~40 °C (approximate); ASHRAE daily-range shape |
| Winter cold spell | 15 Jan, −18 °C at dawn, −6 °C max, T_d −21 °C, clear, 1 m/s | ARSO cold extremes −15 to −20 °C (approximate) |
| Record cold | as the cold spell, −25 °C at dawn, −13 °C max, T_d −28 °C, 5 m/s wind | a rare extreme for the Pannonian lowlands (approximate) |
| Box heater | 30 W into the box air, every mains-powered case; cycle-averaged duty: full below −2 °C box air, off above +5 °C, linear between. One run with a real on/off thermostat (on below −2 °C, off above +5 °C) | STEGO HG 140 30 W (PTC: a little more in the cold, so 30 W is conservative); KTO 111 set to +5 °C, 7 K differential |
| Autumn condensation night | 1 Nov, 2–11 °C, clear night, air saturated at dawn (T_d = 2 °C), 0.5 m/s | typical radiation-fog night in the Mura/Drava plains |
| Sealed box + silica gel | inside dew point −10 °C | **assumed** (RH ≈ 20–25 % at 15 °C) |
| Sky temperature | Berdahl & Martin ε_sky = 0.711 + 0.56 T_d/100 + 0.73 (T_d/100)² | standard clear-sky correlation |
| LMP7721 I_b | 3 fA typ / 20 fA max at 25 °C, doubles every 10 K | datasheet; doubling is the usual rule |
| LMP7721 TCV_os | 4 µV/K (bound) | datasheet typ. ≈ 1.5 µV/K |
| Input node | 240 pF, J202 = 100 G; antenna transfer 1.45 × 10⁸ Ω (0.01 fA/√Hz → 1.452 nV/√Hz) at SR1 | simulations/system |

## 2. Results

### 2.1 Dissipation

| Board | Case | Total | Main contributors |
|---|---|---:|---|
| Amplifier | PSU, 6.0 V after SS34 | **0.57 W** | PCM1804 226 mW, ADM7150-3.3 151 mW, ADM7150-5.0 70 mW, CS8406 50 mW, SS34 29 mW, oscillator 15 mW, each op-amp 6 mW |
| Amplifier | fresh PP3, 9.3 V | 0.89 W | LDOs 219 + 317 mW |
| Amplifier | 13 V battery (upper bound), modelled at 14.7 V | 1.40 W | LDOs 462 + 587 mW |
| PSU | mains | **2.08 W** (2.69 W from mains) | IRM-05 loss 672 mW, LT3045 224 mW, LM317 CV 221 mW, LM317 CC 171 mW, L78L12 134 mW, 4 coils 248 mW + 2 × 82 Ω 50 mW, 6.2 Ω 86 mW, 1.74 k 48 mW, CMC 61 mW |

As a check, the bucket model reproduces the ngspice sawtooth of
simulations/psu: 9.46–10.05 V, LOAD_P mean 9.11 V, and 0.104 A mean charger
current.

### 2.2 Board temperature rise (above the enclosure walls, steady state)

| Amplifier (rise in K) | PSU-fed | PP3 9.3 V | 13 V battery (upper bound) |
|---|---:|---:|---:|
| Board maximum (under PCM1804, or ADM7150-3.3 on the upper-bound battery) | 3.7 | 4.5 | 7.8 |
| PCM1804 junction | 13.9 | 14.4 | 15.2 |
| ADM7150-3.3 / -5.0 junction | 4.8 / 2.4 | 9.2 / 6.5 | 16.6 / 13.3 |
| CS8406 junction | 4.8 | 5.4 | 6.4 |
| **LMP7721: board / junction** | **0.18 / 0.56** | 0.22 / 0.61 | 0.30 / 0.69 |
| **Guard island ΔT across it** | **0.14** | 0.17 | 0.22 |
| Board → shield conductance | 2.8 W/K | | |

- **The walls carry the heat.** The bolted strips take most of it. With
  h_contact of 100 / 1000 W/m²K the board maximum is 4.4 / 3.3 K and the
  LMP7721 board rise 0.31 / 0.12 K. If the strips were insulated (no contact),
  the maximum would be 8.2 K and the LMP7721 would sit 2.5 K above the shield.
- **The input compartment is the coolest part of the board.** It is fenced off
  by the strips at x = 3.5 and x = 45: the LMP7721 sees almost only its own
  6.5 mW.

| PSU (rise in K above the PSU box) | Value |
|---|---:|
| Board maximum (under the IRM-05) | **34.8** (27.3 with the box air convection doubled) |
| L78L12 junction / LM317 CC / LM317 CV junction | 35.9 / 32.5 / 31.5 |
| LT3045 junction | 20.6 |
| Board mean | 15.3 |
| EDLC cells (hottest / coolest) | 14.1 / 0.8 |

On the PSU board, the charger, its IRM-05 and the timer area share one
GND_C pour and form one warm zone. The unpoured bucket area at the bottom
stays cool, as do the receiver side and the metal standoffs.

### 2.3 Outdoor box, 24 h (temperatures in °C, min..max)

PSU-fed throughout, unless marked battery. Every case has the shade roof unless
marked "no roof" or "beam blocked" (the ideal reference: no direct sun on any face).
"PSU hottest" is the hottest point on the PSU board.

| Design day | Ambient | Box air | Hottest box face | **LMP7721** | PSU hottest | EDLC max (life-equivalent) | **Front-end rate**, heating / cooling (K/h) |
|---|---|---|---:|---|---:|---:|---:|
| Summer, light grey, door S | 21..37 | 22..49 | 58 | **24..49** | 66 | 59.0 (48) | 3.7 / 5.9 |
| Summer, light grey, door W | 21..37 | 22..50 | 57 | **24..50** | 67 | 59.9 (49) | 5.1 / 6.9 |
| Summer, **white**, door S | 21..37 | 22..44 | 48 | **24..44** | 61 | 54.4 (45) | 2.6 / 3.9 |
| Summer, **white**, door W | 21..37 | 22..44 | 47 | **24..45** | 62 | 54.8 (45) | 2.6 / 4.4 |
| Summer, **black**, door S | 21..37 | 22..55 | 72 | 24..55 | 72 | 64.8 (53) | 6.2 / 8.5 |
| Summer, **black**, door W | 21..37 | 22..57 | 70 | 24..56 | 73 | 66.5 (55) | 8.4 / 10.2 |
| Summer, black, door W, **no roof** | 21..37 | 20..64 | 77 | 22..62 | 79 | 72.3 (59) | 9.2 / 11.1 |
| Summer, light grey, **beam blocked** (ideal reference) | 21..37 | 22..46 | 46 | 24..46 | 63 | 56.4 (46) | 3.3 / 3.7 |
| Summer, light grey, door S, 3 m/s wind | 21..37 | 22..46 | 53 | 24..46 | 63 | 55.9 (46) | 2.5 / 4.8 |
| **Record 40 °C**, light grey, door S | 24..40 | 25..52 | 61 | 27..52 | 69 | **62.0** (51) | 3.6 / 5.9 |
| **Record 40 °C**, light grey, door N | 24..40 | 25..52 | 61 | 27..52 | 69 | **62.2** (51) | 3.3 / 6.0 |
| **Record 40 °C**, light grey, door W | 24..40 | 25..53 | 60 | 27..53 | 70 | **62.8** (52) | 5.0 / 6.8 |
| **Record 40 °C**, light grey, door E | 24..40 | 25..51 | 62 | 27..54 | 71 | **63.7** (52) | 4.4 / 7.3 |
| Record 40 °C, light grey, door W, **no roof** | 24..40 | 24..56 | 63 | 25..55 | 72 | 65.4 (54) | 5.6 / 7.3 |
| **Winter** cold spell, light grey, PSU + heater | −18..−6 | 0.2..6.2 | 16 | **−4.4..5.7** | 12..23 | 16 | 2.4 / 2.4 |
| Winter cold spell, PSU + heater, on/off thermostat | −18..−6 | −2.0..6.1 | 16 | −2.6..5.5 | 14..23 | 16 | 2.3 / 4.3 |
| Winter cold spell, PSU, no heater (reference) | −18..−6 | −17.5..6.1 | 16 | −16..5.4 | 1.1..23 | 16 | 5.3 / 4.8 |
| **Record cold −25 °C**, 5 m/s, PSU + heater | −25..−13 | −3.1..2.3 | 0 | **−9.2..−1.0** | 7..16 | 9 | 1.7 / 1.3 |
| Record cold −25 °C, 5 m/s, PSU, no heater (reference) | −25..−13 | −24..−7 | −1 | −22..−7 | −5..10 | 4 | 3.1 / 2.4 |
| Winter cold spell, battery (no PSU, no heater) | −18..−6 | −19..5 | 16 | −17..5 | – | – | 5.3 / 4.9 |
| Autumn clear night, light grey, PSU + heater | 2..11 | 4.5..24.5 | 33 | 5.0..24 | 41 | 34 | 5.0 / 5.4 |
| Autumn clear night, PSU + heater, **no roof** | 2..11 | 4.0..25 | 35 | 3.6..24 | 41 | 34 | 5.3 / 6.1 |
| Autumn clear night, no heater (reference) | 2..11 | 2.3..25 | 33 | 3.7..24 | 41 | 35 | 5.3 / 5.4 |

**Box surface** (under the roof unless marked).
- **Summer.** A light-grey box runs **12–13 K above ambient** at midday (box air
  50 °C on a 37 °C day, door W; 16 K and 56 °C on the record day without the roof).
  White paint brings that to **7–8 K** (44 °C). A black box reaches **21 K** under
  the roof (57 °C) and **27 K** without it (64 °C). The ideal "beam blocked" shade
  gives 9 K (46 °C): the real roof lets low morning and evening sun reach the sides.
- **Night.** Without the roof the box cools **below ambient** at dawn, because it
  radiates to the clear sky (0.6–0.8 K on summer nights, 2–3 K on the autumn
  night); under the roof it stays about 1 K above. Without the heater the winter
  box air still dips 0.2 K (PSU) to 1.5 K (battery) below ambient: the ≈ 2.7 W of
  dissipation does not make up for it. With the 30 W heater the box air stays at
  least 10 K (−18 °C) to 15 K (−25 °C, 5 m/s) above ambient.
- **Winter days.** The low sun warms the box air **12–13 K above ambient**.

**Front-end swing.**
- **Fastest change: 6.9 K/h** for light grey (door W) on a summer evening under the
  roof (10.2 K/h black, 4.4 K/h white, 3.7 K/h with the beam blocked; 7.3 K/h for
  grey and 11.1 K/h for black without the roof). It peaks when the sun first reaches the box
  in the morning and as it leaves in the evening.
- **Cloud.** A cloud that drops the sun to 15 % for 15 min changes the rate by
  about 2 K/h.
- **Gust.** A 25 m/s gust lasting 3 min takes the box faces down by several
  kelvin, but the front end by only −7 K/h for a few minutes.
- **Time constants.** Those of the network are 7 s (box air), 3–6 min (walls,
  plate), 15 min, 33 min and **56 min** (the shields). The front end sits
  behind the slowest of them.

**Box heater (mains-powered cases).**

| Case | Heater duty | Energy | PCM1804 minimum (no heater) |
|---|---:|---:|---:|
| Winter cold spell −18 °C | 42 % | 299 Wh/day | **−2.92 °C** (−14.6 °C) |
| Winter cold spell, on/off thermostat | 53 % | 382 Wh/day | −1.2 °C |
| Record cold −25 °C, 5 m/s | 77 % | 553 Wh/day | **−7.72 °C** (−20.9 °C) |
| Autumn clear night | 2 % | 12 Wh/day | 6.4 °C |
| Autumn clear night, no roof | 5 % | 36 Wh/day | 5.0 °C (5.1 °C no heater, with roof) |
| Every summer case | 0 | 0 | – |

- **On/off thermostat.** A real bimetal thermostat (on below −2 °C, off above
  +5 °C box air) cycles about every **4 min** (182 cycles a day in the cold spell)
  with **4.9 K pp** in the box air, but the shields' 56 min time constant leaves
  **9 mK pp at the LMP7721**, at a few mHz, far below the ELF band. The
  cycle-averaged duty used in the other cases is the conservative one (its minima
  are lower).
- **Battery operation** has no heater: the amplifier board reaches −16.8 °C in the
  −18 °C cold spell under the roof (−19.3 °C without it), below the PCM1804's −10 °C
  rating.

### 2.4 Can the PCB have white solder mask to reduce heating?

**It can, but it makes no measurable difference.**

- **No sun reaches the board.** Both boards sit in closed aluminium enclosures
  inside the box, so solder-mask colour only matters through its **infrared**
  emissivity.
- **White and green mask emit alike in the infrared.** Both are ≈ 0.85–0.95.
  The radiative exchange is in any case limited by the ε 0.25 bead-blasted
  aluminium walls.

| Board mask | Amplifier max rise | LMP7721 board rise | PSU max rise |
|---|---:|---:|---:|
| green, ε 0.90 | 3.727 K | 0.1746 K | 34.82 K |
| white, ε 0.88 | 3.727 K | 0.1747 K | 34.86 K |
| pessimistic, ε 0.80 | 3.729 K | 0.1748 K | 35.04 K |

The differences are millikelvin on the amplifier, and 0.2 K on the PSU.

**The colour that matters is the outer box's.**

| Box surface (door W) | LMP7721 peak on a 37 °C day | Box air peak |
|---|---:|---:|
| Light grey RAL 7035, under the roof | 50 °C | 50 °C |
| White, under the roof | 45 °C | 44 °C |
| Light grey, beam blocked (ideal shade) | 46 °C | 46 °C |
| Black, under the roof | 56 °C | 57 °C |
| Black, no roof | 62 °C | 64 °C |

Under the roof, white paint is still worth **5 K** at the front end and **5 K** at
the EDLCs (59.9 → 54.8 °C); without the roof white paint and the roof were each worth
about 8 K.

If white mask is wanted for looks or inspection, JLCPCB offers it. It needs the
**0.13 mm mask dam** that `tools/kicadgen/fabrules.py` already applies to every
board (`MASK_DAM = 0.13`, "any colour"), so it costs no layout change. The
guard island and the wall strips stay unmasked either way.

### 2.5 LMP7721 bias current and the femtoamp front end

| Front-end temperature | I_b typ / max | Shot noise √(2qI_b) typ / max | At antenna, SR1 | Total SR1 at antenna (J202 100 G, budget 74.8) typ / max | DC shift at IN_P via 100 G, typ / max |
|---|---|---|---|---|---|
| −15 °C | 0.19 / 1.3 fA | 8 / 20 aA/√Hz | 1.1 / 2.9 nV/√Hz | 74.8 / 74.9 | 0.02 / 0.13 mV |
| 25 °C | 3 / 20 fA | 31 / 80 aA/√Hz | 4.5 / 11.6 | 74.9 / 75.7 | 0.3 / 2.0 mV |
| 40 °C | 8.5 / 57 fA | 52 / 135 | 7.6 / 19.6 | 75.2 / 77.3 | 0.85 / 5.7 mV |
| **50 °C** (grey box, summer peak) | **17 / 113 fA** | 74 / 190 | 10.7 / 27.6 | **75.6 / 79.8** | 1.7 / 11.3 mV |
| 60 °C (black box) | 34 / 226 fA | 104 / 269 | 15.1 / 39.1 | 76.3 / 84.4 | 3.4 / 22.6 mV |

- **Bias current over a summer day.** I_b rises about 6× from the night (24 °C)
  to the afternoon peak (50 °C) in a grey box under the roof (8× without it).
- **Noise.** For a typical part, the SR1 noise rises by **0.1 dB**. For a
  worst-case (20 fA) part in a grey box it rises by **0.6 dB**, in a black box
  by **1.2 dB**, and in a white box by about 0.4 dB. All of it comes on summer
  afternoons only.
- **DC operating point.** The extra current moves the IN_P DC level by at most
  23 mV (100 G). The PCM1804 does not see that DC level, because Cg blocks it.
  It is far below the atmospheric-current shifts of simulations/system
  (100 mV per pA).
- **The LMP7721's own heating** is 0.4 K, from its 6.5 mW. The whole board
  adds only another 0.2 K. So I_b is set by the box, not by the board.
- **Guard island.** It is isothermal to **0.14 K**. The gradient is constant
  while the power is constant, and the parts on the island are all copper/ENIG.
  Seebeck offsets are therefore DC and do not drift with the daily cycle in any
  way that matters at ELF.

### 2.6 Can clouds or gusts reach the input below 1 Hz? (`thermal_frontend.svg`)

Each entry is the response to a sinusoidal modulation at that frequency:
800 W/m² of sun or 10 m/s of wind. The operating point is the summer midday,
light grey box, 3 m/s wind. The two right-hand columns are the equivalent
peak voltage at IN_P.

| Frequency | ΔT_U201, cloud | ΔT_U201, gust | V_IN_P via I_b(T), max-I_b part | V_IN_P via TCV_os 4 µV/K |
|---|---:|---:|---:|---:|
| 1 mHz | 0.14 K | 0.24 K | 125 µV | 0.9 µV |
| 10 mHz | 1.2 mK | 2.0 mK | 0.59 µV | 8 nV |
| 0.1 Hz | 5 µK | 9 µK | 0.32 nV | 0.04 nV |
| **1 Hz** | **47 nK** | **80 nK** | **0.3 pV** | **0.3 pV** |

- **The temperature cannot follow.** The shields' 56 min time constant and the
  box's chain of thermal masses filter the weather like a fourth-order low-pass
  above 1 mHz.
- **1 Hz.** Any weather-driven artefact is **10⁵ times below** the receiver
  noise in a 1 Hz bin (26.7 nV at IN_P).
- **0.1 Hz.** It is 18 dB below the noise in a 0.01 Hz bin.
- **Below 0.03 Hz.** The I_b(T) drift through J202 is visible. That is the
  intended DC tracking behaviour, far below SR1 (7.83 Hz). It sits under the
  J202 high-pass (6.6 mHz at 100 G), the preamp's Cg high-pass (1.6 Hz) and the
  ADC's HPF.

### 2.7 Condensation

| Night | Inner wall vs dew point, vented box | Board vs dew point, vented box | Inner wall vs dew point, sealed + silica gel (−10 °C) |
|---|---:|---:|---:|
| Summer, clear, T_d 18 °C (door S) | +2.4 K | +5.6 K | +30 K |
| Autumn clear night, saturated at dawn, PSU + heater | **−0.9 K** | +3.0 K | +11.1 K |
| Autumn clear night, battery (no heater) | **−1.9 K** | +1.1 K | +10.1 K |
| Autumn clear night, PSU + heater, no roof | **−5.2 K** | +1.6 K | +6.8 K |
| Autumn clear night, no heater (reference) | **−1.5 K** | +1.7 K | +10.5 K |
| Winter cold spell, PSU + heater (no heater) | +5.9 K (+1.6 K) | +16.6 K (+5.0 K) | (outdoor T_d −21 °C) |

- **Why a vented box condenses.** Under a clear sky the box radiates to a sky
  at about −20 °C, so its walls and air sink **3–4 K below the outdoor air**.
  The PSU heat stays mostly inside the PSU box, so the amplifier shield gets
  only its own 0.6 W.
- **Autumn.** In a box that exchanges air freely with the outside, the inner
  walls fall 6.5 K below the dew point on a damp, clear autumn night. The
  amplifier board falls ≈ 1 K below it. That is dew on the femtoamp board, the
  worst thing that can happen to the guard island.
- **Summer dawn.** The inner walls fall just below the dew point there too.
- **Sealed box.** A box that is sealed and dried with silica gel (inside dew
  point ≈ −10 °C) stays clear of condensation on every design night.
- **Shade roof.** The roof over the box cuts the night-sky loss: with it (and the
  heater at 2 % duty) the walls of a vented box fall only 0.9 K below the dew point
  instead of 5.2 K, and the board stays 3.0 K above it. On a battery (no heater) the
  board stays 1.1 K above it.
- **Heater.** Without the roof its 5 % duty on the autumn night lifts the amplifier
  board in a vented box to +1.6 K above the dew point. With or without the roof the
  inner walls of a vented box still fall below it, so the box stays sealed with
  silica gel.

## 3. Verdict

| Check | Requirement | Result |
|---|---|---|
| T1 junctions | ≤ 125 °C, record 40 °C day | **PASS**: hottest the L78L12 at 80 °C (black box, no roof), 74 °C (black, roof), 71.5 °C (grey record day, door E) |
| T2 LMP7721 | ≤ 85 °C | **PASS**: 54 °C grey record day (door E), 62 °C black without the roof |
| T3 PCM1804, hot | ≤ 70 °C (data sheet operating range −10..+70 °C) | **PASS, marginal in black**: 67.7 °C (black, no roof), 62 °C (black, roof), 59 °C (grey record day) |
| T3b PCM1804, cold | ≥ −10 °C down to −25 °C outside (30 W mains heater) | **PASS**: −2.92 °C at −18 °C, −7.72 °C at −25 °C with 5 m/s wind (without the heater −14.6 / −20.9 °C; battery operation −16.8 °C, no heater) |
| T3c thermostat ripple | LMP7721 < 0.05 K pp (on/off thermostat) | **PASS**: 9 mK pp, ~3 min cycles |
| T3d heater off all summer | thermostat open (box air > +5 °C) in every summer case | **PASS**: duty 0 |
| T4 CS8406-CZZ, hot | ≤ 70 °C (commercial grade) | **PASS**: 64 °C black without the roof, 56 °C grey record day (margin small in black) |
| T5 EDLC | ≤ 65 °C (2.7 V rating), light grey box on a 40 °C day under the shade roof, any door direction | **PASS**: 62.0 °C (door S), 62.2 °C (N), 62.8 °C (W), 63.7 °C (E); 65.4 °C without the roof, 54.8 °C white; a black box fails even under the roof (66.5 °C on a 37 °C day, 72 °C without) |
| T6 IRM-05 | ambient ≤ 70 °C at 41 % load | **PASS**: PSU box air ≈ 56 °C (grey), 58-60 °C (record, roof), 62 °C (record, no roof) |
| T7 CS8406-DZZ, cold | ≥ −40 °C down to −25 °C outside | **PASS**: −8.1 °C (the CZZ, ≥ −10 °C, failed at −17.6 °C without the heater) |
| T8 LM317BTG cold | T_J ≥ −40 °C down to −25 °C outside | **PASS**: +6.0 °C (the TI LM317KCSE3, T_J ≥ 0 °C, failed at −2.8 °C without the heater) |
| T8b reed relays, cold | ≥ −20 °C down to −25 °C outside | **PASS**: +3.8 °C |
| T9 sun/wind at ≥ 1 Hz | < 1/1000 of the 1 Hz-bin noise | **PASS**: 0.3 pV against 26.7 nV |
| T10 sun/wind at 0.1 Hz | below the 0.01 Hz-bin noise | **PASS**: 0.32 nV against 2.7 nV |
| T11 condensation, vented box (rejected option) | board and walls above the dew point | boards **PASS** (+3.0 K, roof and heater), walls **FAIL** (−0.9 K; −5.2 K without the roof), autumn clear night |
| T12 condensation, sealed + silica gel | everything above the inside dew point | **PASS** (≥ +5.5 K, autumn night without roof or heater; ≥ +10.1 K under the roof) |
| White solder mask | – | no effect (≤ 1 mK on the amplifier, 0.04 K on the PSU) |

### Findings and recommendations (not applied)

1. **Fit the sun/rain shade roof; never paint the box black.** (Done 2026-10-31:
   the roof is built in CAD and the BOM and modelled geometrically; the EDLC verdict
   passes for any door direction.)
   - **The roof as built.** White 2 mm aluminium, 500 × 500 mm, centred over the box
     (on a free-standing post the sun reaches the back too), 30 mm above it on its
     own arms on the post (MOUNTING.md section 5, step 7). Record 40 °C day, light
     grey box: EDLC 62.0-63.7 °C (door E the worst), against 65.4 °C without it.
   - **Door north or south.** The east door is the worst (63.7 °C), then west
     (62.8 °C); north and south keep the EDLCs at about 62 °C.
   - **Size.** A wall-flush 500 × 400 roof would have left only 0.4 K of margin with
     an east door, hence the centred 500 × 500.
   - **A roof also helps at night.** It cuts the sky-radiation cooling: the heater
     duty on the autumn night falls from 5 % to 2 % and a vented box's walls come
     within 0.9 K of the dew point (5.2 K below without the roof).
   - **White paint on top.** Under the roof white still takes the EDLCs from 59.9 to
     54.8 °C on a 37 °C day and the front-end swing from 6.9 to 4.4 K/h. Use a
     UV-stable white for polycarbonate; the paint must stay non-conductive, because
     the E-field antenna sees through the box.
   - **Grey ARCA as supplied** passes everything under the roof.
2. **Keep the box sealed and dry.** MOUNTING.md already asks for a silica-gel
   bag and an ePTFE membrane vent. This model supports that, and sharpens it:
   - **The vent must be a membrane.** It equalises pressure but passes almost
     no moist air. An open drain or breather hole is not a substitute.
   - **Change the desiccant on schedule.** Make the 3-monthly change a firm
     rule from October to March, and add a humidity indicator card to the
     desiccant bag.
   - **The risk night** is calm, clear and damp in the Mura/Drava plains in
     autumn: dew forms on any surface that sees the sky. These are also the
     nights when the antenna's air-earth current, and the leakage across a
     damp guard island, matter most.
3. **CS8406-CZZ is specified only down to −10 °C.** The board reaches
   −17.6 °C in a −18 °C cold spell. Its industrial/automotive-grade sibling
   CS8406-DZZ (−40 to +85 °C) would close this; check that grade's
   availability and its pin compatibility. (Done: CS8406-DZZ is fitted.) The
   **PCM1804 is rated −10..+70 °C** (SLES022C; the study first assumed −25..+85 °C)
   and the board reaches −17.2 °C in the cold spell: 7 K below its rating. No
   pin-compatible industrial part is known. (Done: a 30 W mains-side box heater,
   STEGO HG 140 with a KTO 111 thermostat at +5 °C, keeps it at or above −7.7 °C
   down to −25 °C outside under the shade roof, −8.8 °C without it. A 1-2 W heater was too small against the box's night-sky
   loss. On a battery there is no heater, so winter battery operation is out of
   the PCM1804's rating.)
4. **LM317 (TI LM317KCSE3) and L78L12AC are specified for T_J ≥ 0 °C.** In a
   −18 °C cold spell they start at about −3 °C, until their own heat brings
   them up. Fine in practice, but −40 °C-rated equivalents cost nothing extra:
   onsemi LM317BTG (−40 to +125 °C) and L78L12ABUTR (B grade).
5. **PSU board hot zone.** The IRM-05 sits on unpoured primary copper and
   reaches ≈ 35 K above the PSU box. The charger cluster sits at 30–36 K
   (L78L12 T_J 80 °C in a black box). There is no failure, but the PSU board
   is the hottest place in the unit. Options:
   - give the LM317 tabs more copper, or bolt them to the PSU box base through
     a pad;
   - move U3 away from the LM317s.
   (Done: more tab copper, 0.3–0.5 K. Bolting was rejected on 2026-10-31: the tabs
   are live, the base is PE, and 0.17–0.22 W per LM317 does not need it.)
6. **Battery operation, 13 V battery (upper bound; modelled at 15 V)** costs at most 1.4 W on the amplifier board, all of it
   in the two ADM7150s (16.6 K junction rise). This is harmless, but the PSU's
   6.98 V is the cooler and quieter input.

## 4. Limitations

- **Board model.**
  - It is 2-D: the layers are taken as isothermal through the thickness (fine
    for 1.6 mm FR4 at these power densities).
  - Tall parts' own surfaces are ignored, except the IRM-05 and the EDLCs, so
    the junction rises are slightly pessimistic.
  - The PSU board's enclosed-air convection is uncertain: the maximum rise
    falls from 35 to 27 K if the box air is stirred twice as well.
- **Strip contact conductance** is the largest uncertainty on the amplifier
  board, but even 100 W/m²K keeps the LMP7721 within 0.3 K of the shield.
- **The enclosure network is lumped.**
  - Each face is one node, and the internal radiation uses a mean-radiant star
    node instead of view factors.
  - The box is free-standing on a post; a wall mount shades the back.
  - The shade roof is a flat plate at ambient temperature for the faces' sky view
    (top face: no sky; sides: half their sky); its drip flange is ignored, and the
    roof's own shadow on the ground is not modelled.
  - Three reference cases were defined without the roof: the on/off thermostat run
    and the autumn night without the heater (as labelled in the tables).
  - There is no rain, snow cover or dew latent heat.
- **Clear-sky sun only.** Real skies are cloudier, which lowers the peaks and
  makes the night cooling smaller.
- **Climate values.** The ambient profiles are design days: approximate ARSO
  extremes, with the ASHRAE daily-range shape.
- **Part data.** Several limits and supply currents are datasheet-typical or
  assumed, marked **assumed** / "check" above: PCM1804 lower limit, SIL05
  relay range, IRM-05 derating, θ_JB values.

**2026-10-31 update.** The amplifier input is now limited to 13 V (SMAJ13A TVS), so
the "13 V battery (upper bound)" rows above, modelled at 15 V (14.7 V at the board),
are a conservative upper bound; the board sees at most
about 12.7 V after the SS34.
