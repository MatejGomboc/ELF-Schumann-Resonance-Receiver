<!-- SPDX-License-Identifier: CERN-OHL-W-2.0 -->

# ELARA -- local suppliers in eastern Slovenia (mechanical parts)

> **Disclaimer.** This list was compiled from web searches on
> **2026-09-30**. Most company websites could not be opened from the
> research environment, so many details come from search-result snippets
> and business directories. Nobody has been contacted, nothing here is an
> endorsement, and prices, minimum charges and lead times were not checked.
> **Confirm every entry by phone or e-mail before relying on it.**
> Businesses close, move and change what they offer.

"Eastern Slovenia" here means the Podravska, Pomurska, Savinjska, Koroška
and Posavska regions. Where nothing suitable turned up in the east, a
national supplier is listed and marked as such.

## What has to be made or bought

The parts are described in [README.md](README.md) (sections 1–4) and in
[`../bom/mechanical_bom.csv`](../bom/mechanical_bom.csv).

| Job | Parts | Where to go |
| --- | --- | --- |
| Saw, face, drill, tap, mill | A1–A3 amplifier wall bars (6 off, EN AW-6082-T6 flat bar 60 x 8, faced to 52 x 7). A5 bottom tray (EN AW-6082-T651 plate, 15 mm, three pockets 12 deep). P1–P2 PSU bars (4 off, 6060/6082 flat bar 50 x 6, stock height) | CNC job shop (§1) |
| Lathe | A6 PTFE feed-through bush (from Ø20 rod). 8 PTFE standoffs Ø10 x 15 with Ø3.2 bore. 2 PTFE terminal posts Ø10 x 24 | Job shop that turns plastics (§1) or plastics stockist with machining (§4) |
| Mill and engrave | POM-C capacitor base 184 x 92 x 8: 11 x M3 tapped, 4 x Ø4.5, labels engraved 0.6 mm deep | Plastics stockist with CNC (§4) or job shop (§1) |
| Laser or waterjet from DXF | A4 amplifier lid (2 mm), P3 PSU base (3 mm), P4 PSU lid (2 mm). EN AW-5754-H22 or 6082 sheet | Sheet-metal cutter (§2) |
| CNC routing or waterjet from DXF | B2 mounting plate, PE-HD 8 mm, 240 x 350 | Plastics stockist with CNC (§4) or waterjet (§2) |
| Buy | Aluminium stock (if you supply the material), PTFE rod and 0.5 mm skived sheet, A2 fasteners, M3 standoffs, Fibox ARCA 403015 or Gewiss GW44220, nylon glands, cable | §3–§6 |

**Files to send with an enquiry**

* **DXF flat patterns** (units are millimetres, scale 1:1):
  `mechanical/dxf/amp_lid.dxf`, `psu_base.dxf`, `psu_lid.dxf`,
  `mounting_plate.dxf`.
* **STEP models** in `mechanical/step/`: `amp_frame_long_top.step`,
  `amp_frame_long_bottom.step`, `amp_frame_end_left.step`,
  `amp_frame_end_right.step`, `amp_frame_internal_1.step`,
  `amp_frame_internal_2.step`, `amp_tray.step`,
  `amp_feedthrough_ptfe.step`, `amp_lid.step`, `psu_bar_long_front.step`,
  `psu_bar_long_back.step`, `psu_bar_short_mains.step`,
  `psu_bar_short_output.step`, `psu_base.step`, `psu_lid.step`,
  `platecap_base_POM.step`, `mounting_plate.step`. The PTFE standoffs and
  terminal posts exist only inside `platecap_assembly.step`, so give their
  sizes in the enquiry text.
* **The part tables** A1–A9 and P1–P6 from `mechanical/README.md`, plus
  `mechanical/renders/mounting_plate_layout.png` (hole table) and
  `amp_shield_exploded.png` so the shop sees what the parts are for.
* **A thread list.** STEP files carry no thread data. Every tapped hole is
  modelled as a plain Ø2.5 tap-drill hole (see "How to order").

## 1. CNC milling and turning job shops (one-off friendly)

| Business | Town (region) | What they do / why relevant | Website | Notes |
| --- | --- | --- | --- | --- |
| HT-CNC (High Technology CNC), Marjan Plejnšek s.p. | Sveti Tomaž, near Ormož (Podravska) | Small-series production and **individual pieces**. CNC milling up to 508 x 408 x 508 mm, with an emphasis on aluminium and brass. Also laser engraving and 3D printing | <https://ht-cnc.si/> | Exists per search results. Explicitly advertises one-offs. Ask whether the laser engraver can mark the POM base labels |
| Matt-Pro, Matej Dolinar s.p. | Cerkvenjak, Slovenske gorice (Podravska) | CNC milling and turning of **unique** and serial parts. The turning page lists plastics including **POM, PA, PTFE, PE, PVC**. Enquiries can attach CAD/PDF files | <https://matt-pro.si/> | Exists per search results. Good candidate for the tray plus the PTFE/POM parts in one order |
| D-CNC d.o.o. | Murska Sobota (Pomurska) | Focus on **small series of 1–50 pieces** and prototypes. 3- and 4-axis milling, CNC turning | <https://www.d-cnc.eu/> | Exists per search results. Batch size matches the one-off build |
| ECU d.o.o. | Pesnica pri Mariboru (Podravska) | Serial **and individual** production to customer documentation. CNC turning, 3- and 5-axis milling, slot broaching. Mainly supplies Austrian and German customers | <https://www.ecu.si/> | Exists per search results. Willingness to take a private one-off order unverified |
| Strojegradnja Cmok d.o.o. | Šentjur (Savinjska) | CNC and **conventional** machining, small series on customer request, spare parts for machines | <https://strojegradnja-cmok.si/> | Exists per search results. Suits the README's "manual-shop alternative" (no CNC pocketing) |

**Also found (check before use):**

* JSN CNC (CNC rezkanje in struženje, Stevan Novak s.p.), Murska Sobota.
  Metal and plastic parts to customer specification for the electronics
  industry, Haas machines. <https://www.jsn-cnc.com/>
* ALING d.o.o., Maribor (Tezno). CNC turning, milling, drilling.
  <https://www.aling.si/>
* Koban d.o.o., Ptuj. 3- and 5-axis CNC milling, turning as a support
  service. <https://www.koban.si/storitve/>
* Rajh Plus d.o.o., Črešnjevec near Slovenska Bistrica. Aluminium CNC
  milling and turning, grinding and "surface protection" (make sure they do
  not anodise). <https://www.rajh.eu/obdelava-aluminija/>
* Obdelava kovin Denis Cafuta s.p., Slovenj Gradec, workshop in Muta
  (Koroška). CNC turning Ø8–180 mm (INDEX lathes) and milling.
  <https://denis-cafuta.si/>
* Euroinoks d.o.o., Prebold (Savinjska). Laser cutting plus CNC turning and
  milling. Listed in §2.

Directory used to find some of these, with rough price ranges:
<https://www.mojmojster.net/imenik/cnc_obdelava_kovin/maribor> (it quoted
€135–225 for some aluminium CNC jobs in Maribor; treat that as indicative
only).

## 2. Laser and waterjet cutting of aluminium sheet from DXF

| Business | Town (region) | What they do / why relevant | Website | Notes |
| --- | --- | --- | --- | --- |
| Lasertehnik (Lasertehnik Marfin d.o.o.) | Maribor (Podravska) | Laser cutting and bending on TRUMPF lasers. Steel, stainless steel and **aluminium**, sheets up to 8000 x 2500 mm | <https://www.lasertehnik.si/> | Exists per search results. One-off pricing unverified |
| Tišma d.o.o. | Maribor (Podravska) | Laser cutting (TRUMPF TruLaser, aluminium up to 25 mm), laser welding, bending | <https://www.tisma.si/?lang=en> | Exists per search results. Also runs <https://www.laserskirazreztisma.com/en/> |
| Fortis Maribor d.o.o. | Maribor (Podravska) | Laser cutting to order, aluminium up to 10 mm, minimum hole Ø1 mm, ISO 9013 quality. Also bending, **thread drilling**, welding | <https://fortismb.si/laserski-razrez-po-narocilu/> | Exists per search results. Could cut and tap in one go |
| Euroinoks d.o.o. | Prebold (Savinjska) | Fibre laser cutting 0.8–20 mm including aluminium, CNC bending, CNC turning, milling, drilling, tapping. Asks for **DXF at 1:1** | <https://lasercncbend.com/> | Exists per search results. Also uses <https://www.euroinox.biz/>. One stop for sheet parts and some machining |
| HyperCUT | Ptuj area (Podravska) | Builds CNC lasers. Also offers laser cutting of metals and cutting/engraving of **non-metals** | <https://www.hypercut.si/> | Exists per search results. Addresses differ between listings (Gorišnica, Cirkulane, Ptuj). Ask whether it takes service jobs |

**Also found (check before use):**

* Varline, Maribor. Locksmith work, TRUMPF TLF 4030 laser (aluminium up to
  8 mm), bending, drilling and thread cutting.
  <http://varline.eu/nase-storitve/laserski-razrez/>
* STK d.o.o. (Laserski razrez STK Kovinarstvo), Maribor.
  <https://stk.si/?lang=en>
* MDM d.o.o. offers laser, plasma and **waterjet** cutting as services
  (waterjet 1–150 mm, ±0.2 mm, table 6000 x 3000). It has a branch in
  Maribor (see §3), but where its waterjet machine stands was not
  confirmed. <https://www.mdm.si/trgovina/storitve/razrezi/razrez-z-vodnim-curkom-waterjet/>
* Inpos (Celje, Krško, Žalec) arranges laser, plasma and waterjet cutting of
  sheet to your drawings **through partners**.
  <https://www.inpos.eu/storitve>
* Delta T d.o.o., Dol pri Hrastniku. In-house CNC waterjet since 2017. This
  is just outside the eastern regions (Zasavska), west of Celje.
  <https://www.delta-t.si/vodni-razrez/>
* Razrez.net (Texinn d.o.o.), Beltinci (Pomurska). Waterjet **without
  abrasive**, for foam, rubber, insulation and composites, with an online
  configurator and no minimum order. It will **not** cut aluminium. Ask
  whether it can cut the 0.5 mm PTFE washers. <https://razrez.net/>
* Multimetal, Hren Tomaž s.p., Slovenska Bistrica. Plasma cutting
  (Kjellberg), with waterjet through partners. Plasma is too coarse for
  2 mm lids with Ø3.4 holes. <https://multimetal.si/razrez-aluminija-stajerska/>

No in-house **abrasive** waterjet for metal was confirmed inside the five
eastern regions. For the aluminium sheet parts, a fibre laser is the
practical choice. For the 8 mm PE-HD mounting plate, use CNC routing (§4)
or waterjet. Laser-cutting PE-HD tends to leave melted edges.

## 3. Aluminium stockists and metal service centres

| Business | Town (region) | What they do / why relevant | Website | Notes |
| --- | --- | --- | --- | --- |
| Impol Servis d.o.o. -- Trgovina Alumix | Slovenska Bistrica (Podravska) | Impol's retail arm. Flat bars, rods, tubes, sheet, **plate over 6 mm cut to size**. Sells **small quantities (even under 1 kg)**. Hydraulic shears, vertical saw, bar and circular saws, with cutting done on the spot. Online shop with delivery by post | <https://alumix.si/> and <https://impol-servis.si/> | Exists per search results. Best first call for A1–A5 and P1–P4 stock. The listing names **EN AW-6060/6063** flat bar in stock and mentions 6082. Ask for **6082-T6 60 x 8** and **6082-T651 15 mm plate** |
| MDM d.o.o., PE Maribor | Maribor (Podravska) | Aluminium and stainless steel stockist. About 150 flat-bar sizes, sheet and plate, long products cut to length, laser and waterjet services | <https://www.mdm.si/> | Exists per search results. MDM's site gives Belokranjska 12b; LinkedIn gives Meljska cesta 84, so ask. From 5 Dec 2025 the **online shop is B2B-only**, but private buyers can still use the retail shop |
| Kovintrade d.d. | Celje and Štore (Savinjska) | Large metals trader. Aluminium sheet and bar, cutting and rough machining centres. Retail moved to the central warehouse at Štore | <https://kovintrade.com/> | Exists per search results. An older notice said sales to private consumers were temporarily suspended. Check that they sell to individuals now |
| Merkur (Maribor, Celje, Murska Sobota) | Maribor, Celje (Hudinja), Murska Sobota | DIY and trade chain with a metallurgy range (sheet, bar, coloured metals) and cutting of metallurgical products | <https://www.merkur.si/merkur-murska-sobota> | Operating in 2026 (2026 catalogue found). Alloy and temper are rarely specified, so this is fine for P1–P2 (6060), not ideal for 6082-T6 |
| Inpos d.o.o. | Celje, Krško, Žalec (Savinjska, Posavska) | Technical wholesaler with ferrous and non-ferrous metallurgy, including sheet. Cutting through partners | <https://www.inpos.eu/> | Exists per search results. Aluminium bar range unverified |

Not found in the east: **Schachermayer** is in Trzin, near Ljubljana,
with a webshop <https://webshop.schachermayer.com/cat/sl-SI> and no
eastern branch found. Searches found no Slovenian retail branches for
**Hydro** or **Tehnomat**.

## 4. Technical plastics (PTFE, POM-C, PE-HD)

| Business | Town (region) | What they do / why relevant | Website | Notes |
| --- | --- | --- | --- | --- |
| Galeja d.o.o. | Slovenske Konjice (Savinjska) | Technical plastics since 1990, including **PTFE**, **POM-C** and **PE (KOTERM)** as sheet, strip and round rod. **Cutting of all stock and finished parts on CNC machines** | <https://www.galeja.si/tehnicna-plastika/> | Exists per search results. Best eastern option for the PTFE rod, POM base and PE-HD mounting plate, possibly machined too |
| Tridex d.o.o. | Slovenj Gradec (Koroška) | Technical plastics wholesaler. Rods, sheet and profiles in PE, PP, PA, **POM**, PET, PC, PVDF and more. **Cutting and machining to order** | <https://www.tridex.si/TEHNICNA_PLASTIKA> | Exists per search results. PTFE was not in the listing seen, so ask |
| M&M Intercom d.o.o. *(national, Ljubljana)* | Ljubljana | PE, PP, **POM**, PA, PET, **PTFE**, PEEK. Cut to size (±0.1 mm) in 1–2 working days. CNC drilling, milling, turning | <https://www.mmintercom.com/storitve/razrez-tehnicne-plastike-8/> | Exists per search results. Good for the 0.5 mm skived PTFE sheet |
| Ex-Mega d.o.o. *(national, Ljubljana)* | Ljubljana | Technical plastics including **PTFE** and **POM**. Online shop | <https://www.exmega.si/slo/ptfe-politetrafluoretilen.html> and <https://trgovina.exmega.si/prodajni-program/tehnicna-plastika> | Exists per search results |
| POS Plastika d.o.o. *(national)* | Sodražica | **POM-C** and **PE** sheet and rod, sheet cutting service, send a sketch by e-mail | <https://www.pos-plastika.si/tehnicna-plastika> | Exists per search results. No PTFE seen |

**Also found:** Dimer d.o.o., Grosuplje. Cutting, turning and milling of
technical plastics (bushes, gears and similar).
<https://dimer.si/storitve/razrez-struzenje-in-rezkanje-tehnicne-plastike-gume-in-ostalo/>
MS Viscom, Cerklje na Gorenjskem. PE-HD 300 and POM-C sheet and rod.
<https://www.ms-viscom.com/>

## 5. Fasteners, standoffs, enclosures, glands and cable

### Fasteners (A2 stainless) and standoffs

| Business | Town (region) | What they do / why relevant | Website | Notes |
| --- | --- | --- | --- | --- |
| Haberkorn d.o.o. | Maribor (HQ), also Ptuj and Murska Sobota | Industrial supplier with more than 30,000 fasteners online, including **ISO 7380 A2** button heads | <https://www.haberkorn.com/si/sl/podjetje/haberkorn-slovenija> and <https://shop.haberkorn.si/vijaki-vijacne-zveze> | Exists per search results. The shop lists ISO 7380-**2** (flanged). The model uses plain ISO 7380(-1), so check which you get |
| Würth d.o.o. -- trgovine | Maribor, Ptuj, Celje | Trade counters for screws, nuts, washers and tools | <https://www.wuerth.si/sl-SI/Page/trgovine> | Exists per search results (shop list). Ask whether private buyers can buy over the counter |
| Merkur | Maribor, Celje, Murska Sobota | A2 DIN 912 and DIN 933 screws over the counter | <https://www.merkur.si/delavnica/vijacni-program/> | Operating in 2026. Small sizes such as M3 x 25 ISO 7380 may not be stocked |
| Vijaki d.o.o. | Velika Dolina, Brežice municipality (Posavska) | Fastener wholesaler: screws, nuts, washers in many standards, special parts to order | <https://vijaki.si/> | Exists per search results. Minimum order unverified |
| Nano Elektronika d.o.o. and ČIP d.o.o. | Maribor | Electronic component shops. Nano Elektronika lists metal and plastic **standoffs** (for the M3 x 10 F-F). ČIP sells components, cable and tools | <https://nanoelektronika.si/> and <https://www.cip.si/> | Both exist per search results. Stock of the exact standoff unverified. Standoffs at ČIP not confirmed |

National online alternatives for small quantities of A2 fasteners:
Vijaki.net (Ljubljana), which lists ISO 7380-2 A2 in M3,
<https://www.vijaki.net/vijak-s-polkrozno-imbus-glavo-m3-iso-7380-2-nerjavni-a2>.
Kamm (Šenčur), <https://www.kamm.si/>. IC Elektronika (Ljubljana) for M3
brass standoffs, <https://www.ic-elect.si/mehanske-komponente/distancniki.html>.

### Electrical wholesalers (enclosure, glands, cable)

| Business | Town (region) | What they do / why relevant | Website | Notes |
| --- | --- | --- | --- | --- |
| Rexel Slovenija (formerly Elektronabava) | Hoče near Maribor, Celje, Velenje, Murska Sobota (pick-up point) | Electrical wholesaler. Its e-shop lists **Lapp SKINTOP ST-M** glands (e.g. M20 x 1.5, 53111020), enclosures and cable. Click & Collect | <https://www.rexel.si/kontakti/> and <https://etrgovina.rexel.si/> | Exists per search results. The e-shop needs a **business registration**. Ask about Fibox ARCA |
| Marchiol d.o.o. | Maribor (Podravska) | Electrical installation wholesaler: boxes, trays, conduit, installation material | <https://marchiol.si/> | Exists per search results. Fibox or Gewiss range unverified |
| Epros d.o.o. | Braslovče and Žalec (Savinjska) | Electrical shop that carries the **Gewiss** brand (switches and sockets seen online) | <https://epros.si/> | Exists per search results. GW44220 availability unverified |
| LAPP Slovenija *(national, online)* | -- | Official LAPP e-shop: **SKINTOP** glands, locknuts, cable | <https://www.etrgovina-lappslovenija.si/skintop-kabelske-uvodnice> | Exists per search results. Lead-free SKINTOP MS-M is also offered |
| TME *(online, Poland)* | -- | Stocks **Fibox ARCA 403015** and 403021. Already the BOM source | <https://www.tme.com/us/en-us/details/arca403015/wall-mounting-enclosures/fibox/arca-403015/> | Fibox's sales for Slovenia are handled from its Czech office, and no Slovenian Fibox stockist was confirmed |

Checks on names in the brief:

* **Elektromaterial Lendava d.d.** exists, but it *manufactures* switches,
  sockets and luminaires (<https://www.elektromaterial.si/>). It is not a
  wholesaler for enclosures or glands.
* **Kovinotehna** was taken over by Merkur and closed its Celje shops
  (<https://www.24ur.com/novice/gospodarstvo/kovinotehna-zapira-trgovine.html>),
  so it is not listed.
* **Merkur** is trading in 2026.

**Enclosure note.** Sellers list the **Gewiss GW44220** as **IP56**,
380 x 300 x 180 mm. The README reference box, Fibox ARCA 403015, is
**IP66**. Before choosing the Gewiss box, check its inner size against the
240 x 350 mounting plate.

## 6. Online one-off services (not local)

| Service | Based in | What it offers | Website | Notes |
| --- | --- | --- | --- | --- |
| Prokon -- "Razrez na zahtevo" | Slovenia | Upload DXF files and get an instant **indicative** price plus sheet nesting. Prokon passes the job to a partner cutter, which quotes and invoices you directly | <https://prokon.si/en/cutting> | **Online broker.** Which partner cuts, and where, is unknown |
| Xometry Europe | EU | Instant quotes for CNC machining and sheet metal, delivery to all European countries | <https://xometry.eu/en/> | **Online.** Minimums, shipping cost and VAT handling not checked |
| Protolabs Network (formerly Hubs) | EU / global | Instant quotes for CNC, sheet metal and 3D printing. Clears customs and pays duties for EU deliveries | <https://www.hubs.com/> | **Online** |
| Donim promet | Croatia | Webshop for laser cutting and CNC. Upload DXF/STP, instant price, pay online, 3–5 working days | <https://donim-promet.hr/en/usluge/laser-cutting/> | **Online.** Delivery is stated "throughout Croatia", so shipping to Slovenia is unverified |
| LASIFY | Austria | Laser parts from 1 piece in steel, stainless steel and aluminium. Upload DXF/STEP for an instant price | <https://www.lasify.at/> | **Online.** Its information says delivery to **Austria and Germany only** |

## How to order -- checklist

1. **Send the package.** Include the DXF files (sheet parts), the STEP files
   (bars, tray, bush, POM base), the README part tables, the mounting-plate
   hole table and one exploded render. Say it is **one prototype for an
   open-hardware project**, and ask for a quote with lead time and minimum
   charge.
2. **Specify material and temper per part.**
   * A1–A3: EN AW-6082-**T6** flat bar 60 x 8.
   * A5: EN AW-6082-**T651** plate, 15 mm (faced to 14).
   * P1–P2: EN AW-6060 (T66) or 6082 flat bar 50 x 6.
   * A4, P4: EN AW-5754-H22 (or 6082), 2 mm. P3: the same, 3 mm.
   * PTFE: **virgin, unfilled** (not glass-filled or regenerated) for the
     feed-through, standoffs and posts.
   * POM-C, natural or black, for the base.
   * PE-HD (PE 300), 8 mm, for the mounting plate.

   If the stockist only has 6060 in 60 x 8, discuss it with the machinist
   first. 6060 is softer than 6082-T6, which affects facing finish and the
   strength of the M3 threads.
3. **Finish.** Write "**Do not anodise, do not paint. Deburr only.**" The
   wall bars and tray must make metal contact with the PCB GND strips.
   Optional, per the README: fine glass-bead blast after machining, then
   clear chromate conversion (Alodine 1200 / SurTec 650). Chromate
   conversion is not anodising, but say so explicitly to the shop.
4. **Tolerances.** Suggest ISO 2768-m for general dimensions. The
   **24-hole M3 pattern** must match the PCB (KiCad coordinates in
   `params.py`), so ask for positional accuracy of about ±0.1 mm. The
   **frame bottom face must be flat**: it is the RF seal against the GND
   strip. Laser or waterjet sheet parts: ±0.1–0.2 mm is fine. Clearance
   holes are Ø3.4 (M3) and Ø4.5 (M4).
5. **Thread list.** Every Ø2.5 hole in the STEP models is an **M3 tapped
   hole**.
   * Amplifier frame A1–A3: **64 x M3** in total (24 for the tray screws,
     24 for the lid screws, 16 at the corner and tee joints). Depth is
     12 mm from the bottom, 10 mm from the top, and 12 mm at the joints.
   * PSU bars P1–P2: M3, 8 mm deep in the top and bottom edges and 10 mm
     deep at the corner joints (short bars).
   * POM base: 11 x M3, through the 8 mm plate.

   Nothing else is threaded. The DC-in and RJ45 (AES3) notches and the
   Ø16.2 / Ø12.2 gland holes are plain.
6. **Quantity.** One of each machined part. **One spare of each sheet
   part** (lid, PSU base, PSU lid), because the extra cost after set-up is
   small. **Two spare PTFE standoffs.** One mounting plate.
7. **Who supplies the stock?** Ask whether the shop supplies the
   material. If it does not, buy it cut to length from Alumix, MDM or
   Galeja (§3–§4), with a few millimetres of saw and facing allowance per
   bar. The stock list is in `bom/mechanical_bom.csv`.
8. **Fasteners.** State **ISO 7380-1** (button, no flange) A2: M3 x 25 and
   M3 x 8. Also DIN 912 A2 M3 x 16 and M3 x 12. Several Slovenian
   shops list only ISO 7380-2, which is flanged and has a larger head
   than the Ø5.7 mm modelled in `params.py`.
9. **Confirm by phone or e-mail.** Ask whether the shop takes private
   (non-company) orders, whether VAT is included, and whether you can
   collect in person.
