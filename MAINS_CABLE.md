# ELARA -- the insulated, shielded mains feed to the outdoor unit

> **Safety first.** This is a 230 V mains circuit running outdoors, possibly
> underground, to a metal enclosure. **The connection to the building
> installation, the choice of protective devices and the final tests must be
> done by a qualified electrician.** In Slovenia this means an authorised
> installer who issues a test report; the rules are in
> [TSG-N-002:2021](https://www.gov.si/assets/ministrstva/MNVP/Dokumenti/Graditev/TSG-N-002_2021_nizkonapetostne_instalacije.pdf)
> and SIST HD 60364. This guide explains what the ELARA design needs from the
> cable and how to prepare the PSU end. It does not replace the electrician.
> Never work on a live cable.

## 1. What the design needs (PLAN section 5.2)

- **Twisted L and N** so their magnetic fields cancel. A multi-core cable
  already has twisted (cabled) cores.
- **An overall screen** acting as containment shielding. It keeps the cable's
  own 50 Hz electric field away from the antenna, the reverse of normal
  shielding. **The screen is earthed at the mains entry end only**, and left
  floating and insulated at the PSU end, so it carries no loop current.
- **A protective earth (PE) conductor.** The PSU enclosure is aluminium and is
  bonded to PE (the M4 PE stud through the mains-end bar, and the board's H1/H3
  plated holes on metal standoffs). PE is a safety
  conductor, so it is connected at **both** ends, unlike the screen.
- **About 100 m run.** The PSU draws only about 5 W (about 25 mA), so voltage
  drop is not an issue. The conductor size is set by the protective device and
  the loop impedance, which the electrician checks.

## 2. Cable

**Recommended:** Lapp **ÖLFLEX CLASSIC 110 CY BLACK 0.6/1 kV, 3G1.5**. It has
three cores (L, N, green/yellow PE), a tinned-copper braid screen, a black
UV-resistant PVC sheath, and is rated for outdoor use
([Lapp catalogue](https://products.lappgroup.com/online-catalogue/power-and-control-cables/various-applications/pvc-outer-sheath-and-numbered-cores/oelflex-classic-110-cy-black-061-kv.html)).

- The standard (grey) 110 CY is **not** UV-resistant
  ([data sheet](https://media.automation24.com/datasheet/en/DB1135752EN.pdf)).
  Use it only fully inside conduit.
- Conductor resistance is about 13.3 Ohm/km, so about 1.3 Ohm per conductor
  over 100 m.
- **Underground:** lay it in a protective conduit (corrugated PE cable duct),
  at least **0.6 m** deep, or **0.8 m** under traffic areas
  ([TSG-N-002](https://www.gov.si/assets/ministrstva/MNVP/Dokumenti/Graditev/TSG-N-002_2021_nizkonapetostne_instalacije.pdf)).
  Put a warning tape about 0.3 m above it. Keep at least 0.5 m from any
  signal (AES3) cable in the same trench, or use a separate duct.
- **Overhead or on a fence:** use a catenary wire with UV-stabilised ties and
  a drip loop at each end. Keep it away from the antenna wire; cross it at a
  right angle, never run it parallel.

Buy a few metres extra for the drip loops and for re-terminating later.

**Not suitable:** Ethernet (Cat5e/6/7) cable, even shielded, and even though the
PSU draws only about 25 mA. It is not mains rated: thin insulation, 0.2 mm²
cores, no 300/500 V rating, and the wiring rules do not allow it on 230 V.

### DIY alternative: rubber cable with a braid sleeve

Audiophile mains cords use the same recipe this design needs: twisted
conductors, a 100 % foil wrap under a tinned-copper braid (about 85 % coverage),
and the screen earthed at the wall end only through a drain wire
([TNT-Audio](https://www.tnt-audio.com/clinica/merlino.html),
[Alpha Audio](https://www.alpha-audio.net/background/cable-shielding-and-a-diy-power-cord/2/),
[DIY Audio Projects](https://diyaudioprojects.com/Power/diyMains/)). Build it
from certified parts, never from loose building wire in a garden hose (single
cores have only basic insulation, a hose is no rated conduit, and there would be
no PE core):

1. **Core cable:** H07RN-F 3G1.5. This is the standard outdoor rubber cable:
   brown (L) and blue (N) twisted with the green/yellow PE, oil, water and UV
   resistant, 450/750 V.
2. **Foil:** wrap self-adhesive copper foil tape spirally over the sheath with
   50 % overlap, end to end. It gives the 100 % coverage a braid alone does not.
3. **Braid:** pull a tinned-copper expandable braid sleeve (for a 10-12 mm
   cable) over the foil. At the building end, fold the braid back over a short
   bare length of drain wire, solder the two together and crimp a ring terminal
   on the drain wire for the PE bar. At the outdoor end, cut the foil and the
   braid back and seal them under adhesive-lined heat-shrink (section 4, step 4).
4. **Outer jacket:** the braid corrodes outdoors. Cover it with UV-resistant
   heat-shrink or a PET braided sleeve, or lay the whole cable in conduit.
5. **Terminal block:** J1 stays the 3-pole block: L, N and PE. The screen never
   lands on the PSU board.

The electrician still connects and tests the circuit (section 5). Treat the
foil and braid as the screen only: PE is the green/yellow core.

## 3. At the building end (electrician)

- **A dedicated circuit** from the distribution board, with:
  - a **30 mA RCD** (required for outdoor circuits),
  - an MCB sized for the 1.5 mm² cable and the measured loop impedance (for
    example B6 or B10),
  - preferably a surge protective device at the board.
- Terminate in an IP65 junction box, or a lockable outdoor socket and plug.
  The plug lets you isolate the outdoor unit yourself.
- **Screen: connect it to PE here** with a proper screen clamp or pigtail
  terminal. This is the only earth connection of the screen.

## 4. At the outdoor unit -- preparing the cable end

The cable enters the outdoor box through the **M20** gland at the bottom, then
the PSU box through its **M16** gland, low in the mains-end bar. Inside, J1's
wire entries face the gland across a 17 mm bay kept free of parts, and the M4
PE stud sits in the same bar, 40 mm up, above the IRM-05 module.

1. **Make sure the cable is dead** (unplugged or isolated and locked off) and
   test it.
2. **Leave a drip loop** below the outdoor box before the M20 gland. Take the
   cable through the M20 gland, across the mounting plate and through the M16
   gland of the PSU box. Leave about 100 mm inside the PSU box.
3. **Strip the outer sheath** back to about 20 mm inside the M16 gland seal,
   so the gland seals on the outer sheath, not on the braid.
4. **Screen, at this end: NOT connected.**
   - Comb out and cut the braid flush with the sheath edge.
   - Slide a 25 mm piece of adhesive-lined heat-shrink over the cut, covering
     the braid ends and 10 mm of sheath, and shrink it.
   - No strand may reach the PSU box, the board or PE.
5. **Cut the inner sheath and fillers** back, without nicking the core
   insulation.
6. **Cut the cores to length:**
   - L and N straight across the bay into J1 (pins 1 and 2, the upper two),
     with a little slack.
   - PE about **20 mm longer** than L and N, so that if the cable is ever
     pulled, PE is the last conductor to break.
7. **Fit crimped ferrules** (1.5 mm², insulated) on L and N.
8. **PE:**
   - Crimp a ring terminal (M4, 1.5 mm²) onto PE.
   - Fit it on the M4 PE stud in the mains-end bar (the stud's own nut and
     serrated washer are already on): ring terminal, washer, nut, then lock nut.
   - Then run a short green/yellow 1.5 mm² link from the stud to J1 pin 3
     (PE), ferruled at J1.
9. **Connect L to J1 pin 1 and N to J1 pin 2.** J1 is the Phoenix MKDS
   5.08 mm terminal. Tighten to the terminal's rated torque (about
   0.5-0.6 N·m), then tug-test each core.
10. **Tighten both glands** so the cable cannot be pulled or twisted at the
    terminals. Pull-test the cable at the M20 gland.
11. **Label the cable** at both ends: "ELARA 230 V -- outdoor unit" and the
    circuit number.

## 5. Tests (electrician, before first power-up)

With the PSU **disconnected** from J1: the IRM-05-15 and the varistor would
spoil the insulation test.

| Test | Expected |
| --- | --- |
| PE continuity, building PE to the PSU PE stud and to each PSU box bar | Low and consistent (about 2.7 Ohm for 100 m of 1.5 mm², out and back) |
| Screen continuity, building end to PSU end | Low. Then confirm the screen is **not** connected to PE at the PSU end: it should read open once the building-end bond is lifted |
| Insulation resistance at 500 V DC: L+N to PE, L+N to screen, PE to screen at the PSU end | Well above the minimum in HD 60364-6 (1 MOhm); expect hundreds of MOhm or more for a new cable |
| Loop impedance and RCD trip test | Within the limits for the chosen MCB; the RCD trips at or below 30 mA within the required time |

Then reconnect J1, power up with the PSU lid still off, and follow
ASSEMBLY.md section 6. Only the green LED on the charger side lights.

## 6. Why the earths are arranged like this

```text
 building              ~100 m shielded cable                  outdoor unit
 PE ----------------------- PE conductor --------------------- PSU box (aluminium), GND_C
 PE --- screen bond         screen (floating here) ----x  insulated
                                                               | two-bucket isolation (relays)
                                                              receiver GND -- local earth rod
```

- The mains side (charger, GND_C, PSU box) is tied to the building PE, as
  safety requires.
- The receiver side (amplifier, plate capacitors) is galvanically separate:
  the buckets swap through relays, and no copper path joins it to the charger
  while it runs. It takes its reference from its own earth rod at the mast
  (MOUNTING.md section 6).
- The mains screen is earthed at one end only, so it contains the cable's
  field without forming a current loop through the two earths.
- **Do not connect the local earth rod to the mains PE at the outdoor unit**,
  and never connect the DC cable's shield to the PSU box. Either would short
  out the isolation this design is built around.
