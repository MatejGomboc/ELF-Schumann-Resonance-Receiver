# ELARA outdoor unit -- thermal simulations

> **Update 2026-10-31 (applied from this study):** CS8406-DZZ, LM317BTG and
> L78L12ABUTR (all −40 °C), a sealed box with an ePTFE vent and silica gel, and a white
> shade roof. Every design check now passes; the two "vented box" failures describe the
> rejected option. The PSU's LM317 tab copper was grown to the board edge with 26
> thermal vias per tab: re-simulated, it lowers the LM317s by only 0.3–0.5 K (the PSU
> board's rise is set by the whole board heating its box air, not by local spreading),
> so the remaining lever is bolting the tabs to the aluminium base (about 0.4 W straight
> to the box), left optional because every part is within its limits.

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
| `thermal_enclosure_24h.svg` | Summer design day for grey, white and black boxes and a sun shade; PSU contents; front-end dT/dt; daily ranges on every design day |
| `thermal_frontend.svg` | LMP7721 Ib and SR1 noise against temperature; transfer from sun and wind to the LMP7721 temperature; equivalent voltage at IN_P |
| `thermal_cold_condensation.svg` | Autumn condensation night, and a winter cold spell against the parts' minimum temperatures |

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
| Amplifier input | 6.0 V from the PSU (6.98 V − 7.2 Ω × 95 mA − 0.3 V SS34); 9.3 V fresh PP3; 14.7 V for a 15 V battery | simulations/psu, design.py |
| PSU charger | periodic bucket model: CC 0.2016 A → CV 10.4 V, 2.2 Ω + ESR 0.2 Ω, SS34 V_F = 0.27 + 0.33·I, 15.2 s half period, 97.8 mA drain; LM317 dropout 1.55 V + 0.6 Ω·I | design.py, psu_model.NOMINAL (reproduces its 9.46–10.05 V sawtooth) |
| IRM-05-15 efficiency | 75 % at 2.0 W out (41 % load) | datasheet 80 % at full load; light-load value **assumed** |
| Relay coils | 2 strings of 2 × 200 Ω + 82 Ω from 12 V = 24.9 mA, both strings energised in the same half period (50 % duty) | design.py |
| θ_JB / θ_JC | ADM7150 15, PCM1804/CS8406 45, SOIC-8 60–90, LM317 θ_JC + tab 6, LT3045 10, L78L12 SOT-89 40 K/W | package-typical (**assumed**, datasheets give θ_JA) |
| Box | Fibox ARCA 403015, 300 × 400 × 150 mm, PC 4 mm (ρc_p 1.5 MJ/m³K), IR ε 0.9, wall-free on a post, door facing S or W | mechanical/params.py, bom |
| Box solar absorptance | light grey RAL 7035 **0.55**, white paint 0.25, black 0.95 | ASHRAE / paint tables (light grey 0.45–0.6, white 0.2–0.3) |
| Units inside | shield 1.09 kg Al, PSU box 0.70 kg Al, plate 1.2 kJ/K, boards 130 / 160 J/K; areas from params.py | mechanical/params.py |
| Inside convection | h = 1.42·(ΔT/L)^0.25, ≥ 1 W/m²K | laminar natural convection, air |
| Outside convection | (h_nat³ + (2.8 + 3.0·v)³)^(1/3) | Watmuff/Duffie-Beckman flat-plate wind correlation |
| Site | 46.5 N, 16.0 E (Maribor / Ptuj / Murska Sobota) | user |
| Sun | Meinel/ASHRAE clear sky, DNI = 1361 × 0.7^(AM^0.678), diffuse 0.12 × DNI, albedo 0.2; 15 Jul gives GHI 1000 W/m² at solar noon | consistent with PVGIS clear-sky July values for this location (≈ 950–1000 W/m²; not fetched) |
| Summer design day | 37 °C max (16:00 CEST), 21 °C min, T_d 18 °C, wind 1 m/s (calm, worst); record case 40/24 °C | ARSO normals: Pannonian summer peaks 35–38 °C, record ~40 °C (approximate); ASHRAE daily-range shape |
| Winter cold spell | 15 Jan, −18 °C at dawn, −6 °C max, T_d −21 °C, clear, 1 m/s | ARSO cold extremes −15 to −20 °C (approximate) |
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
| Amplifier | 15 V battery, 14.7 V | 1.40 W | LDOs 462 + 587 mW |
| PSU | mains | **2.08 W** (2.69 W from mains) | IRM-05 loss 672 mW, LT3045 224 mW, LM317 CV 221 mW, LM317 CC 171 mW, L78L12 134 mW, 4 coils 248 mW + 2 × 82 Ω 50 mW, 6.2 Ω 86 mW, 1.74 k 48 mW, CMC 61 mW |

As a check, the bucket model reproduces the ngspice sawtooth of
simulations/psu: 9.46–10.05 V, LOAD_P mean 9.11 V, and 0.104 A mean charger
current.

### 2.2 Board temperature rise (above the enclosure walls, steady state)

| Amplifier (rise in K) | PSU-fed | PP3 9.3 V | 15 V battery |
|---|---:|---:|---:|
| Board maximum (under PCM1804, or ADM7150-3.3 on 15 V) | 3.7 | 4.5 | 7.8 |
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

PSU-fed throughout, unless marked battery. "PSU hottest" is the hottest point
on the PSU board.

| Design day | Ambient | Box air | Hottest box face | **LMP7721** | PSU hottest | EDLC max (life-equivalent) | **Front-end rate**, heating / cooling (K/h) |
|---|---|---|---:|---|---:|---:|---:|
| Summer, light grey, door S | 21..37 | 20..52 | 60 | **22..51** | 68 | 60 (48) | 4.0 / 6.3 |
| Summer, light grey, door W | 21..37 | 20..53 | 60 | **22..52** | 69 | 61 (50) | 5.6 / 7.4 |
| Summer, **white**, door S | 21..37 | 20..44 | 47 | **22..44** | 61 | 53 (43) | 3.0 / 4.0 |
| Summer, **white**, door W | 21..37 | 20..44 | 47 | **22..44** | 61 | 54 (44) | 2.9 / 4.5 |
| Summer, **black**, door S | 21..37 | 20..62 | 77 | 22..61 | 78 | 70 (55) | 6.8 / 9.2 |
| Summer, **black**, door W | 21..37 | 20..64 | 77 | 22..62 | 79 | 71 (58) | 9.2 / 11.1 |
| Summer, light grey + **sun shade** (beam blocked) | 21..37 | 22..46 | 46 | 24..46 | 63 | 55 (45) | 3.3 / 3.7 |
| Summer, light grey, door S, 3 m/s wind | 21..37 | 21..48 | 54 | 23..47 | 64 | 56 (46) | 3.3 / 5.0 |
| **Record 40 °C**, light grey, door W | 24..40 | 24..56 | 63 | 25..55 | 72 | 64 (53) | 5.6 / 7.3 |
| **Winter** cold spell, light grey, PSU | −18..−6 | −20..5 | 16 | **−19..4** | −1.5..22 | 14 | 5.8 / 5.3 |
| Winter cold spell, battery (no PSU) | −18..−6 | −22..4 | 15 | −19..4 | – | – | 5.8 / 5.4 |
| Autumn clear night, light grey | 2..11 | −0.5..25 | 35 | 1..24 | 41 | 33 | 5.9 / 6.1 |
| Autumn clear night, + shade roof | 2..11 | 2..16 | 16 | 4..17 | 34 | 26 | 2.5 / 2.1 |

**Box surface.**
- **Summer.** A light-grey box in full sun runs **15–16 K above ambient** at
  midday (box air 53 °C on a 37 °C day). White paint halves that, to **7 K**
  (44 °C). A black box reaches **27 K** (64 °C). A shade that keeps the direct
  sun off the box does as well as white paint.
- **Night.** All colours cool **≈ 1 K below ambient** at dawn, because the box
  radiates to the clear sky. On the winter and autumn nights this reaches
  **3–4 K below ambient**: the ≈ 2.7 W of dissipation does not make up for it.
- **Winter days.** The low sun on a south-facing door warms the box air
  **11–12 K above ambient**.

**Front-end swing.**
- **Fastest change: 7.4 K/h** for light grey on a summer evening (11 K/h black,
  4.5 K/h white, 3.7 K/h shaded). It peaks when the sun first reaches the box
  in the morning and as it leaves in the evening.
- **Cloud.** A cloud that drops the sun to 15 % for 15 min changes the rate by
  about 2 K/h.
- **Gust.** A 25 m/s gust lasting 3 min takes the box faces down by several
  kelvin, but the front end by only −7 K/h for a few minutes.
- **Time constants.** Those of the network are 7 s (box air), 3–6 min (walls,
  plate), 15 min, 33 min and **56 min** (the shields). The front end sits
  behind the slowest of them.

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

| Box surface | LMP7721 peak on a 37 °C day | Box air peak |
|---|---:|---:|
| Light grey RAL 7035 | 52 °C | 53 °C |
| White | 44 °C | 44 °C |
| Light grey under a sun shade | 46 °C | 46 °C |
| Black | 62 °C | 64 °C |

On the outer box, white paint (or a shade roof) is worth **8 K** at the front
end and **8 K** at the EDLCs.

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

- **Bias current over a summer day.** I_b rises 8× from the night (22 °C) to
  the afternoon peak (52 °C) in a grey box.
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
| Summer, clear, T_d 18 °C | −0.9 K | +3.9 K | +27 K |
| Autumn clear night, saturated at dawn | **−6.5 K** | **−1.0 K** (PSU on), −1.6 K (battery) | +5.5 K |
| Autumn, with a shade roof | −1.5 K | +1.7 K | +10.5 K |
| Winter cold spell | −3.3 K | +2.4 K | (outdoor T_d −21 °C) |

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
- **Shade roof.** A roof over the box cuts the night-sky loss. That alone lifts
  the board above the dew point (+1.7 K) and cuts the walls' deficit from
  6.5 K to 1.5 K.

## 3. Verdict

| Check | Requirement | Result |
|---|---|---|
| T1 junctions | ≤ 125 °C, record 40 °C day | **PASS**: hottest the L78L12 at 80 °C (black box), 73 °C (grey) |
| T2 LMP7721 | ≤ 85 °C | **PASS**: 55 °C grey record day, 62 °C black |
| T3 PCM1804, hot | ≤ 70 °C (data sheet operating range −10..+70 °C) | **PASS, marginal**: 67.7 °C (black), 61 °C (grey record day) |
| T3b PCM1804, cold | ≥ −10 °C, −18 °C cold spell | **FAIL**: −17.2 °C (see finding 3) |
| T4 CS8406-CZZ, hot | ≤ 70 °C (commercial grade) | **PASS**: 64 °C black, 57 °C grey record day (margin small in black) |
| T5 EDLC | ≤ 65 °C (2.7 V rating), grey box on a 40 °C day | **FAIL by 0.45 K**: 65.4 °C (grey record, no roof; the review's leg diodes and doubled divider current add ≈1 K), 72 °C (black) fails, 54 °C (white); the shade roof required by MOUNTING.md keeps it ≈9 K lower |
| T6 IRM-05 | ambient ≤ 70 °C at 41 % load | **PASS**: PSU box air ≈ 59 °C (grey), 62 °C (record) |
| T7 CS8406-CZZ, cold | ≥ −10 °C, −18 °C cold spell | **FAIL**: −17.6 °C |
| T8 LM317 cold | T_J ≥ 0 °C (TI recommended), −18 °C cold spell | **FAIL**: −2.8 °C at dawn (works in practice; outside the spec) |
| T9 sun/wind at ≥ 1 Hz | < 1/1000 of the 1 Hz-bin noise | **PASS**: 0.3 pV against 26.7 nV |
| T10 sun/wind at 0.1 Hz | below the 0.01 Hz-bin noise | **PASS**: 0.32 nV against 2.7 nV |
| T11 condensation, vented box | board and walls above the dew point | **FAIL** (autumn clear night: board −1.0 K, walls −6.5 K) |
| T12 condensation, sealed + silica gel | everything above the inside dew point | **PASS** (≥ +5.5 K) |
| White solder mask | – | no effect (≤ 1 mK on the amplifier, 0.04 K on the PSU) |

### Findings and recommendations (not applied)

1. **Paint the outer box white, or fit a sun/rain shade roof; never black.**
   - **The gain.** White takes the summer peak inside the box from 53 to 44 °C,
     the EDLCs from 61 to 54 °C, and halves the front-end swing (7.4 → 4.5 K/h).
   - **EDLC life.** The life-equivalent EDLC temperature drops from 50 to
     44 °C; with the usual doubling per 10 K, that is about 1.5× the life.
   - **A roof also helps at night.** It cuts the sky-radiation cooling, which
     fixes most of the condensation case. A roof 50–100 mm above the box with
     open sides is the best single measure.
   - **The paint.** Use a UV-stable white for polycarbonate (or a white
     polyester/GRP box). The paint must stay non-conductive, because the
     E-field antenna sees through the box.
   - **Grey ARCA as supplied.** It passes everything except the EDLC margin on
     a record day (64.3 °C against 65 °C).
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
   pin-compatible industrial part is known. Options: run it out of spec in winter
   (most commercial parts work, unguaranteed: check in a freezer on the bench),
   insulate the inside of the outdoor box (closed-cell foam) so the 0.6 W of the
   board keeps it warmer, or a thermostat heater (1-2 W, PSU-powered only).
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
   Bolting the LM317 tabs to the base would also take about 0.4 W straight to
   the aluminium.
6. **Battery operation at 15 V** costs 1.4 W on the amplifier board, all of it
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
  - There is no rain, snow cover or dew latent heat.
- **Clear-sky sun only.** Real skies are cloudier, which lowers the peaks and
  makes the night cooling smaller.
- **Climate values.** The ambient profiles are design days: approximate ARSO
  extremes, with the ASHRAE daily-range shape.
- **Part data.** Several limits and supply currents are datasheet-typical or
  assumed, marked **assumed** / "check" above: PCM1804 lower limit, SIL05
  relay range, IRM-05 derating, θ_JB values.

**2026-10-31 update.** The amplifier input is now limited to 13 V (SMAJ13A TVS), so
the "15 V battery" rows above are a conservative upper bound; the board sees at most
about 12.7 V after the SS34.
