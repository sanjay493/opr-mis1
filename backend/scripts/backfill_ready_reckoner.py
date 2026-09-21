"""
One-time backfill for "Ready Reckoner" (Annexure-1: 5 Integrated Steel
Plants — BSP/DSP/RSP/BSL/ISP; Annexure-2: 3 Special Steel Plants —
ASP/SSP/VISL). Content transcribed directly from the two source documents
the user supplied:
  - "Ready Reckoner (Plant wise Details).pdf" (BSP/RSP/ISP/BSL/DSP —
    capacity + product-mix tables extracted with pdfplumber's grid-table
    reader; RSP's product-mix page has no gridlines so its rows are
    transcribed by hand from the same page's text).
  - "Ready Reckoner Special Steel Plant.docx" (ASP/SSP/VISL — table cells
    read directly via python-docx, already clean).

Process-flow diagrams: BSP/ISP/ASP each had one single clean embedded
image in the source file, extracted as-is. RSP/BSL/DSP's diagrams are
composited from dozens of tiny positioned image fragments with no
straightforward way to re-stitch losslessly, so those three pages were
rasterized whole (pypdfium2, 3x scale) instead — a faithful screenshot of
the original page. SSP/VISL's diagrams are similarly fragmented but their
source is a .docx (no page-rasterize tool available in this environment),
so no image was extracted for them; an editor can supply one later via the
in-preview "Replace diagram" upload (see ReadyReckonerTemplate.js).

Idempotent: every db call here is an upsert, safe to re-run.

OBSOLETE for capacity/product-mix content as of 2026-09-21: that content
moved to plain structured data (capacity_rows/product_mix_headers/
product_mix_rows — see db.py's own comment above _READY_RECKONER_COLS),
and real edits have since been made to it via the live app, so this
script's static _CONTENT strings below are stale and run() no longer
writes them (db.save_ready_reckoner_content's signature changed shape
entirely — calling it with these old HTML strings would silently write
garbage into the new columns, not raise). Kept only as the historical
record of what was originally transcribed from the source PDF/docx, and
for its still-valid plant-identity/image upserts. See scripts/migrate_
ready_reckoner_structured.py for the one-time migration that carried the
real (by-then-edited) content over to the new shape.

Run: python backfill_ready_reckoner.py   (from backend/scripts/, same venv
as the rest of the backend)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "ready_reckoner")

# plant_code -> (plant_name, plant_group, sort_order, image_filename|None)
PLANTS = {
    "BSP":  ("Bhilai Steel Plant", "ISP", 1, "BSP.jpg"),
    "DSP":  ("Durgapur Steel Plant", "ISP", 2, "DSP.png"),
    "RSP":  ("Rourkela Steel Plant", "ISP", 3, "RSP.png"),
    "BSL":  ("Bokaro Steel Plant", "ISP", 4, "BSL.png"),
    "ISP":  ("IISCO Steel Plant", "ISP", 5, "ISP.jpg"),
    "ASP":  ("Alloy Steels Plant", "SSP", 1, "ASP.png"),
    "SSP":  ("Salem Steel Plant", "SSP", 2, None),
    "VISL": ("Visvesvaraya Iron and Steel Plant", "SSP", 3, None),
}


def _table(headers, rows, caption=None):
    """headers: list[str] (colgroup labels); rows: list[list[str]]."""
    parts = ["<table>"]
    if caption:
        parts.append(f"<caption style=\"font-weight:700;text-align:left;padding:2px 0;\">{caption}</caption>")
    parts.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead>")
    parts.append("<tbody>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


# ─────────────────────────── BSP ───────────────────────────────────────────
BSP_CAPACITY = _table(
    ["Facility", "Details", "Capacity"],
    [
        ["Coke Ovens (11 Nos.)", "8 batteries (#1-8) of 4.3-m height (65 ovens each); 3 batteries (#9-11) of 7-m height (67 ovens each); all wet quenching except COB-11 (dry quenching / CDCP)", "COB#1-10: 3.303 MTPA<br>COB#11: 0.880 MTPA<br><b>Total Coke: 4.183 MTPA</b>"],
        ["Sinter Plants (2 Nos.)", "SP-II: 4 M/cs (M/c1-3: 75 m² & M/c-4: 80 m² hearth area); SP-III: M/c-1: 320 m², M/c-2: 360 m²", "3.137 + 3.197 + 3.707 MTPA<br><b>Total Sinter: 10.04 MTPA</b>"],
        ["Blast Furnaces (6 Nos.)", "BF-1 (1033/886 m³) — to be phased out; BF-4,5,6 (1719/1491 m³ each); BF-7 (2363/2105 m³); BF-8 (4060/3445 m³)", "0.600 + 3×0.945 + 1.575 + 2.810 MTPA<br><b>Total HM: 7.5 MTPA</b>"],
        ["Steel Melting Shop-II", "BOF: 3 converters 100/130 T each; 3 ARUs, 1 VAD, 2 LFs, 2 RHs; 6 casters (4 slab + 2 bloom); De-S Unit (2.87 MTPA)", "3.0 MTPA"],
        ["Steel Melting Shop-III", "BOF: 3 converters 160/180 T each; 3 ARUs, 3 LFs, 1 RH; 4 casters (2×6-strand billet, 1×6-strand bloom-cum-billet, 1×3-strand bloom-cum-beam blank); De-S Unit (2.8 MTPA)", "4 MTPA"],
        ["&mdash;", "<b>Total Crude Steel Capacity</b>", "<b>7 MTPA</b>"],
        ["Rail &amp; Structural Mill (RSM)", "3 pusher-type RHFs of 75 TPH each; roughing/intermediate/finishing stands; 7 hot saws; separate SR/LR finishing area; LR complex", "0.65 MTPA"],
        ["Universal Rail Mill (URM)", "1 walking-beam RHF of 230 TPH; 3 stands (BD-1, BD-2, Tandem); hot saws, cooling bed, finishing/welding area", "1.2 MTPA"],
        ["Bar &amp; Rod Mill (BRM)", "1 walking-beam RHF of 200 TPH; 18 stands (6 roughing, 6 intermediate, 6 finishing); 2 shears; 2 lateral + 1 central + 1 WR line", "0.9 MTPA"],
        ["Merchant Mill (M Mill)", "3 pusher-type RHFs of 60 TPH each; 12 stands (St-9,10,12 housing-less)", "0.75 MTPA"],
        ["Wire Rod Mill (WRM)", "1 pusher-type RHF of 120 TPH; 4 strands A/B/C/D (St-A stopped, quality issues)", "0.70 MTPA"],
        ["Plate Mill (P Mill)", "3 pusher-type RHFs of 120 TPH each; 1 roughing + 1 finishing 4-high stand; 2 levellers, 2 side-trimming shears; normalising furnace", "1.650 MTPA"],
        ["&mdash;", "<b>Total Finished Steel Capacity</b>", "<b>5.850 MTPA</b>"],
        ["&mdash;", "<b>Total Semis Capacity</b>", "<b>0.710 MTPA</b>"],
        ["&mdash;", "<b>Total Saleable Steel Capacity</b>", "<b>6.560 MTPA</b>"],
    ],
)
BSP_PRODUCT_MIX = _table(
    ["Mill", "Product Type", "Profile / Size Range", "Steel Grade Range"],
    [
        ["RSM", "Rails", "UIC-60, 60E1, EF-TWA (60E1A1); 13/26/65-m as rolled, 260-m as welded panel", "Gr 880, R260, NCC"],
        ["RSM", "Crossing Sleepers", "&mdash;", "IRS T9-70"],
        ["RSM", "Crane Rails", "CR120, CR100, CR80", "Crane rail grade"],
        ["URM", "Rails", "60E1, 130-m rolled length &amp; 260-m welded panel", "Gr 880, R260, 1175HT"],
        ["BRM", "Plain Bars", "16-60 mm", "Fe500D, Fe550D, HCR, EQR, SEQR (Fe500D/550D)"],
        ["BRM", "TMT Bars", "6-40 mm", ""],
        ["BRM", "Plain Wire Rod", "5.5-22 mm", ""],
        ["M Mill", "TMT Bars", "28/32/36/40-45 mm", "HCRM, Fe500D, Fe550D, Fe600D"],
        ["M Mill", "Angles", "50×50, 65×65, 75×75, 80×80, 90×90", "SAILMA Gr-A, IS-2062"],
        ["M Mill", "Channels", "100×50, 75×40", ""],
        ["WRM", "Plain Wire Rods", "5.5-7 mm", "EWNR, SAE (1008/1015), CAQ, EQR-D"],
        ["WRM", "TMT Rods", "8-10 mm", ""],
        ["P Mill", "Plates", "Thickness: 7-120 mm; Width: 1500-3200 mm; Length: 4500-12500 mm", "BQ, HT, MS, DMR"],
    ],
)

# ─────────────────────────── RSP ───────────────────────────────────────────
RSP_CAPACITY = _table(
    ["Plant / Unit", "Capacity", "Description"],
    [
        ["Ore Bedding and Blending Plant (OBBP)", "12 MTPA", "Receiving, unloading, reclaiming and transporting Iron ore lump &amp; fines, limestone, dolomite, quartzite; base-mix prep for Sinter Plants; crushed fuel/flux transport for trimming"],
        ["Sinter Plant I", "2 × 0.75 MTPA", "2 sinter machines of 1.5 MT/yr (125 sq.m sintering area each)"],
        ["Sinter Plant II", "1 × 1.57 MTPA", "1 sinter machine of 1.57 MT/yr (192 sq.m sintering area)"],
        ["Sinter Plant III", "1 × 3.7 MTPA", "1 sinter machine of 3.70 MT/yr (360 sq.m sintering area)"],
        ["Coke Ovens — COB 1-6", "0.35 + 0.353 + 0.36 + 0.41 + 0.41 + 0.66 MTPA (hard coke)", "3 batteries of 70 ovens (4.5 m tall), 2 batteries of 80 ovens (4.5 m tall) — wet quenching; 1 battery of 67 ovens (7 m tall) with CDCP"],
        ["Blast Furnaces — BF-1, BF-4, BF-5", "1.01 + 0.765 + 2.8 MTPA", "BF#1: 1491/1710 m³ (working/useful); BF#4: 1448/1658 m³; BF#5: 3470/4060 m³"],
        ["Steel Melting Shop I", "0.5 MTPA slabs", "2 mixers (1100 T each), 2 LDs (60/66 T/blow), 1 single-strand slab caster, 1 LF, 1 VOR, 1 VAR"],
        ["Steel Melting Shop II", "3.2 MTPA slabs", "2 mixers (1300 T each), 3 LD converters (150 T each), 2 single-strand slab casters + 1 new single-strand caster-3, 1 ARS, 3 LFs, 1 RH-OB unit"],
        ["Hot Strip Mill", "1.67 MTPA HR coils", "2 walking-beam furnaces (225 T/hr each); 3-stand roughing + 4-hi 6-stand finishing mill"],
        ["Hot Strip Mill 2", "2.94 MTPA HR coils", "2 walking-beam furnaces (300 T/hr each), 4-high reversing mill with edger, 7-stand 4-hi tandem mill, 0.4 MT sheet shearing line"],
        ["Plate Mill", "0.5 MTPA plates", "1 walking-beam furnace (100 T/hr), 3.1 m wide 4-hi reversing mill"],
        ["New Plate Mill", "0.92 MTPA plates", "1 walking-beam furnace (225 T/hr, 2-row charging), 4.3 m wide 4-hi reversing mill"],
        ["Pipe Plants", "ERW: 0.075 MTPA; SW: 0.055 MTPA", "ERW plant with 400 KHz HF welding; SW plant with double sub-merged arc welding"],
        ["Cold Rolling Mill", "Galva: 0.16 MTPA GP/GC sheets", "2 pickling lines, 1 cold reversing mill, 1 five-stand tandem mill, hood + continuous annealing, 2 skin-pass mills, sheet shearing line, 1,60,000 T/yr continuous galvanising line"],
        ["Silicon Steel Mill", "CRNO: 0.0735 MTPA", "4-Hi reversing CRNO mill"],
        ["Captive Power Plant-I", "&mdash;", "5 units, 125 MW"],
    ],
)
RSP_PRODUCT_MIX = _table(
    ["Mill", "Dimensions (O/P Material)", "Grades / Applications"],
    [
        ["Hot Strip Mill", "HR Coils/Plates — Width: 950-1450 mm, Thickness: 2-11 mm", "IS 2062 E250 Br (Gr1/GrB), IS 10748 etc. — tube making, cold reducing, LPG, chequered coils for flooring"],
        ["Hot Strip Mill 2", "HR Coils/Plates — Width: 950-1450 mm, Thickness: 1.2-25.4 mm", "IS 10748 (Gr 1,2,3), IS 2062 E250/E350/E350C HSFQ etc. — tube making, cold reducing, LPG etc."],
        ["Plate Mill", "Plates — Width: 1500-2500 mm, Thickness: 8-63 mm, Length: 6300-12500 mm", "IS 2062 E250 Br, API (HRCF Fe I 5LF Gr70) etc. — pressure vessels, railway wagons, engineering structures, pipes"],
        ["New Plate Mill", "Plates — Width: 1600-4200 mm, Thickness: 8-100 mm, Length: 6300-15000 mm", "IS 2062 Gr250Br/350Br/350C/410C/410Br/450BrCu, ASTM Gr70 etc. — pressure vessels, heavy vehicles, earth-moving equipment, railway wagons, ship building, high-strength structures"],
        ["ERW Pipe Plant", "Diameter: 8″-18″ OD, Thickness: 4.3-12 mm", "API 5L PSL1, IS 3589, IS 4270 CRLA, ASTM A-53 etc."],
        ["SW Pipe Plant", "Diameter: 20″-64″ OD, Thickness: 5.6-14.2 mm", "IS 3589, IS 5504, CRLA etc."],
        ["Cold Rolling Mill", "Cold-rolled plates (GP/GC) — thickness 0.35-1.23 mm", "GP and GC coils and sheets"],
        ["CRNO", "Coils — 0.5 × 900-1000 mm", "IS 648 50C, Gr 400/450/530/600/700/800/900 etc. — motors, transformers, other electrical appliances"],
    ],
)

# ─────────────────────────── ISP ───────────────────────────────────────────
ISP_CAPACITY = _table(
    ["Department", "Major Unit", "Name-Plate Capacity (MT)", "Facilities"],
    [
        ["Coke Oven", "COB#10", "0.467 (gross coke)", "78 ovens, 4.4 m height, wet quenching"],
        ["Coke Oven", "COB#11", "0.881 (gross coke)", "2×37 ovens, 7 m height, dry quenching"],
        ["Sinter Plant", "M/C-1 &amp; 2", "3.88", "2×204 m² area each"],
        ["Blast Furnace", "BF-5", "2.7", "Useful vol: 4161 m³, working vol: 3551 m³"],
        ["SMS", "&mdash;", "2.5", "3 converters, 3 casters (2×6-strand, 1×4-strand), 2 LF, 1 RHF"],
        ["Mills — WRM", "&mdash;", "0.55", "Single walking-beam RHF (side charge/discharge), 150 T/hr, 30 stands"],
        ["Mills — Bar Mill", "&mdash;", "0.9", "Single walking-beam RHF (side charge/discharge), 160 T/hr, 22 stands"],
        ["Mills — USM", "&mdash;", "0.85", "Single walking-beam RHF (front charge/end discharge), 180 T/hr, 4 stands"],
    ],
)
ISP_PRODUCT_MIX = _table(
    ["Mill", "Product Mix"],
    [
        ["WRM", "Plain round coils (mm): 5.5, 6, 6.5, 7, 7.5, 8, 9, 10, 12, 14, 16, 20, 22; Rebar coils (mm): 6, 8, 10"],
        ["Bar Mill", "TMT bars (mm): 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36, 40"],
        ["USM", "Parallel flange beams (NPB 240-750 and variants), H-beams (WPB 200-450 and variants), channels 200-400, equal angles 150-200, special sections"],
    ],
)

# ─────────────────────────── BSL ───────────────────────────────────────────
BSL_CAPACITY = _table(
    ["Department", "Unit / Facilities", "Products", "Capacity (kT)"],
    [
        ["Coke Ovens", "8 batteries of 69 ovens each (incl. 1 standby), 27.3 m³ useful chamber volume, 4.7 m height", "BF Coke", "3480"],
        ["Sinter Plant", "3 M/cs of 252 m² area each", "Gross Sinter", "6900"],
        ["Blast Furnace", "BF-1,3,4 &amp; 5 each 2000 m³, BF-2 2500 m³ useful volume", "Hot Metal", "5250"],
        ["SMS-I", "2×130 T LD converters &amp; 1 single-strand casting machine", "Cast Slab", "1260"],
        ["SMS-II", "2×300 T LD converters &amp; 2 double-strand casting machines", "Cast Slab / Crude Steel", "3350 / 4610"],
        ["Hot Strip Mill", "4 reheating furnaces (walking beam), modernised finishing stands with hydraulic AGC, 4 hydraulic coilers; 2 shearing lines + 1 slitting line", "HR Coil / HR Plate-Sheet / HR Slit Coil", "4500 / 1200 / 920"],
        ["Cold Rolling Mill I &amp; II", "2 pickling lines (2000 mm &amp; 1420 mm), 4-stand 2000 mm + 5-stand 1420 mm tandem mills, bell &amp; continuous annealing, skin-pass mills, shearing/slitting lines, hot-dip galvanising + corrugation lines", "Pickled/Reduced/Annealed/CR Coil, TMBP, CR Sheet, GP/GC Coil-Sheet", "1729 / 1728 / 1560 / 1456 / 100 / 980 / 170 / CR Saleable 1660"],
        ["Cold Rolling Mill III", "Continuous HCl pickling + 5-stand 6-Hi tandem cold mill, electrolytic cleaning, 100% hydrogen bell annealing (47 bases, 26 furnaces), skin-pass mill, tension leveller, hot-dip galvanising", "Reduced/Annealed/CR/GI/GA Coil", "1228 / 366 / 860 / 847 / 693 / 324 / 36; CR Saleable 1200"],
        ["&mdash;", "&mdash;", "<b>Total Saleable Steel</b>", "<b>3780</b>"],
    ],
)
BSL_PRODUCT_MIX = _table(
    ["H.R. Coil", "H.R. Plate", "H.R. Sheet", "CR Coil", "CR Sheet", "GP Coil", "GP Sheet", "GC Sheet"],
    [
        ["E-46 SS 4012A", "IS 5986 ISH 330 S", "SAILCOR", "SAILCOR", "IS-513 CR 0", "IS-513 CR 1", "IS 277 GR 80", "IS 277 GR 120"],
        ["API 5L X42M PSL2", "IS 5986 ISH 410 S", "IS 6240 (LPG)", "IS 15914 HS 345", "IS-513 CR 1", "IS-513 CR 2", "IS 277 GR 120", "Defective"],
        ["API 5L X46 PSL1", "HSFQ 450", "DMR 249 GR A", "IS 6240 (LPG)", "IS-513 CR 2", "SAILCOR", "IS 277 GP 350 GR 450", ""],
        ["API 5L X52 PSL1", "IS 5986 ISH500 LAHFQ 450", "DMR 249 A (ABA)", "IS 1079 HR1+Cu", "IS-513 CR 3", "IS-513 CR 1+Cu", "IS 277 GP 350 GR 600", ""],
        ["API 5L X70M PSL2 / EN 10025-2 / IS 6240 (LPG) etc.", "IS 5986 / IS 1079 / IS 2062 series", "IS 2062 E-series, ASTM A36, A572 Gr50 TY2", "IS 1079 HR1/HR2, IS 513 ISC series", "IS-513 series, HRPD, CRUA, Mixed/Defective/PUP", "&mdash;", "&mdash;", "&mdash;"],
        ["SAIL BR (IBRTC), SAIL CORTEN, SAIL MC-40/45/55/60", "IS 2062 E410/E450, SAE 1006, IS 11513 CR4/SAILSOFT", "&mdash;", "&mdash;", "&mdash;", "&mdash;", "&mdash;", "&mdash;"],
    ],
    caption="BSL: Grades in Finished Product (representative grade families per product — see full spec sheet for exhaustive list)",
)

# ─────────────────────────── DSP ───────────────────────────────────────────
DSP_CAPACITY = _table(
    ["Deptt", "Major Unit", "Name-Plate Capacity (MT)", "Facilities"],
    [
        ["Coke Oven", "COB#1-6", "1.49 (gross coke)", "78 ovens, 4.45 m height, wet quenching; 4 batteries (2,3,5,6) operating, 2 (1,4) under cold repair/rebuild"],
        ["Sinter Plant", "SP-1 / SP-2", "1.3 / 1.71 (total 3.01)", "Hearth area 142.7 m² / 180 m²"],
        ["Blast Furnace", "BF-2 / BF-3 / BF-4", "2.4 (combined)", "Working volume 1204/1204/1539 m³ (Bell/BLT/Bell type)"],
        ["SMS", "Conv #1-3, M/c#1-4", "2.2", "3 converters (120/130 T), 4 casters — 2 billet casters 6-strand 0.384 each, 1 bloom caster 4-strand 0.75, 1 BRC 4-strand 0.75; 2 mixers 1300 T, 3 LF 130 T, 1 VAD 130 T"],
        ["Mills — Section Mill", "&mdash;", "0.207", "Single walking-beam RHF (side charge/discharge), 150 T/hr, 30 stands"],
        ["Mills — Merchant Mill", "&mdash;", "0.33", "Single walking-beam RHF (side charge/discharge), 160 T/hr, 22 stands"],
        ["Mills — MSM", "&mdash;", "1.0", "Single walking-beam RHF (front charge/end discharge), 180 T/hr; roughing (3H+3V), finishing (3H-3U)"],
        ["WAP (Wheel &amp; Axle Plant)", "&mdash;", "Wheels 0.0322; Axles 0.01178", "75,000 wheels &amp; 4,500 axles/yr; rotary reheat furnace ø17m, 63/12 MN forging press, wheel rolling mill, dishing press 20 MN, hot stamping 3 MN, heat-treatment furnaces, CNC machines"],
    ],
)
DSP_PRODUCT_MIX = _table(
    ["Mill", "Product Mix", "Steel Grade"],
    [
        ["Section Mill", "Joist 200×100, Channel 150×75, Channel 200×75", "&mdash;"],
        ["Merchant Mill", "20 mm &amp; 25 mm TMT bars", "HCR, SEQR"],
        ["MSM", "NPB: 200, 250; WPB: 150, 160; Beam: 150,250,300; Channel MC: 100,125,150,200,300; Angle: 90,100,200", "Carbon/low-alloy/high-tensile structural steel — IS-2062, IS-8500, SAILMA, Hyten, corrosion-resistant steel"],
        ["WAP", "BG Coach, EMU, Metro LHB wheel, BG Loco S-profile, G Loco WAG-9, LHB Axle", "R-19/R-34/R-16"],
    ],
)

# ─────────────────────────── SSP (Salem Steel Plant) ───────────────────────
SSP_CAPACITY = _table(
    ["Shop", "Details", "Capacity (T/annum)"],
    [
        ["Steel Melting Shop", "55 T Electric Arc Furnace (EAF); 60 T Refining Converter (AOD); 60 T Ladle Furnace (LF); single-strand Slab Caster (Level-2 automation); slab grinder; slab dimensions: thickness 145-175 mm, length 5500-10500 mm, width 600-1300 mm", "1,80,000"],
        ["Hot Rolling Mill", "Walking-beam RHF; 4-hi reversing roughing mill; 4-hi reversing Steckel mill (Level-2 automation); down-coiler; roll shop. Product profile — carbon steel: 1.6-14 mm, stainless steel: 2.5-10 mm", "3,64,000"],
        ["Cold Rolling Mill", "Coil Build-Up Lines (CBL); Bell Annealing Furnaces (BAF); Annealing &amp; Pickling Lines (APL); 20-Hi Sendzimir Mills (Z-Mill); Strip Grinding Line; Skin Pass Mills; Shearing/Slitting Lines; Roll Shop; Tension Levelling Line; Rotary Polisher; Plate Annealing Furnace. Product profile — Coil (No.1 finish: 2.5-8 mm, CR material: 0.2-5.0 mm), Sheet (width 600-1250 mm, length 500-6200 mm), Slit Coil (width ≥40 mm)", "3,40,000"],
        ["Blanking Unit", "Blanking press (with degreasing &amp; deburring unit), rimming machines, annealing furnace, pickling &amp; polishing line, counting machines", "6,600"],
    ],
)
SSP_PRODUCT_MIX = _table(
    ["Product Type", "Grades"],
    [
        ["Stainless Steel — HR Coils &amp; Sheets, CR Coils/Sheets/Coin Blanks", "Austenitics: 301, 304, 304L, 309S, 310S, 316, 316L, 321; Low-Nickel Austenitics: N1,N2,N3,N5,N6,N7, SSLNM; Ferritics: 409, 410S, 409M, 430, 439, 441; Martensitic: 410, 420S1 &amp; S2, SSBS; Duplex: 32202, 2205"],
        ["Hot Rolled Carbon Steel Coils &amp; Sheets", "Low &amp; medium carbon: IS 1079 HR2, IS 10748 Gr I &amp; II, IS 2062 E250BR / E350BRCu / E450BRCu, IS 5986 Fe 205 etc."],
        ["Finishes in Stainless Steel", "No.1 Finish, 2D &amp; 2B Finish, No.4/No.3/2J Finish, No.8 (Mirror) Finish; special finishes: Moon Rock, Honeycomb, Chequered, Macromatt, Hammertone, Linen Fabric, Stripe, Slipfree, Dull"],
    ],
)

# ─────────────────────────── VISL (Visvesvaraya Iron & Steel Plant) ────────
VISL_CAPACITY = _table(
    ["Shop", "Details", "Capacity (T/annum)"],
    [
        ["Primary Mill", "2×15 TPH pusher furnaces (fuel: FO, 11 burners); 1×8-cell soaking pit (38.2 T); 3×3-high roughing mills (720 mm dia × 1780 mm roll size); 1 hot shear (500 T); 1×3-stand 3-high finishing mill (600 mm dia × 1500 mm roll size); 2 mechanical hot saws; 6 sand + 6 pit cooling beds", "78,000"],
        ["Bar Mill", "2×15 TPH walking-hearth furnaces (fuel: FO, hydraulic); 1 descaling unit (250 kg/cm²); 1×3-high roughing mill (manual, 520 mm dia); 1×4-stand finishing mill (manual, 3/2-high, 440/420 mm dia)", "36,000"],
        ["Forge Plant", "1×1600 T hydraulic press with 12 T rail-bound manipulator; 1 long forging machine; 4 disposition + 5 bogie hearth furnaces (LDO); 1 rotary hearth furnace (LDO)", "12,940"],
        ["Heat Treatment Shop", "11 dual-fired bogie hearth furnaces (30 T each); 1 electrical annealing furnace (10 T); 2 dual-fired bogie hearth furnaces for hardening &amp; normalising (7.5 T each); 3 electrical tempering furnaces (6 T each)", "&mdash;"],
        ["Utilities", "30 TPD oxygen plants", "&mdash;"],
    ],
)
VISL_PRODUCT_MIX = _table(
    ["Shop", "Products"],
    [
        ["Primary Mill", "Rounds: 70-140 mm (steps of 5 mm); Billets: 60,63,65-140 mm (steps of 5 mm); special sections: 64,96,100,105,120,140 mm billets for Defence; Flats: 50-100 mm thick, 155-300 mm wide; Blooms: 145-250 mm"],
        ["Bar Mill", "Rounds: 20-65 mm (multiple sizes); Billets: 36,40,44,45,50,53,55,56 mm; Flats: 10-20 mm thick, 70-120 mm wide"],
        ["Forge Plant", "Press rounds (tool/carbon/alloy steels ø201-600 mm); die blocks; broken-corner squares; flats; long forgings (rounds ø70-200 mm, squares 100-150 mm); BG Coach &amp; LHB axles; heat-treated rolled/forged products (annealed, normalised, spheroidise-annealed, hardened &amp; tempered)"],
    ],
)

# ─────────────────────────── ASP (Alloy Steels Plant) ──────────────────────
ASP_CAPACITY = _table(
    ["Shop", "Details", "Capacity (T/annum)"],
    [
        ["Steel Melting Shop", "3 Electric Arc Furnaces (EAF), 50 T each; 2×18.75 MVA transformers (1965); 1×25 MVA transformer (1985)", "2,46,450"],
        ["Secondary Steel Refining Units", "2 Ladle Furnaces (60 T each); 1 Vacuum Arc Degassing Unit (VAD, 60 T, non-SS); 1 Vacuum Oxygen Decarburising Unit (VOD, 60 T, non-SS); 1 Argon Oxygen Decarburising (AOD) converter (60 T, SS &amp; non-SS)", "2,46,450"],
        ["Caster — Slab-cum-Twin Bloom", "1 slab-cum-twin bloom caster", "1,38,000"],
        ["Caster — Ingot", "Ingot casting", "93,663"],
        ["Blooming &amp; Billet Mill", "Fuel-fired soaking pits (12 nos.); blooming (roughing) mill 2-high 900 mm; billet mill 2-high 700 mm; 2 finishing stands 2-high 650 mm", "1,60,000"],
        ["Forge Shop", "2,000 T oil-hydraulic forging press; pneumatic hammers (5 T &amp; 2 T); chargers, manipulators, heating/dispositioning furnaces", "9,600"],
        ["Conditioning Shops I &amp; II", "2 heat-treatment furnaces; slow-cooling facility; surface grinding machines; magnetic particle testing; ultrasonic testing; cutting facilities", "&mdash;"],
        ["Plate Mill", "1×3-high reversing mill; annealing, levelling &amp; shearing facilities; sand-blasting facility", "6,500"],
        ["Heat Treatment &amp; Finishing Shop", "Heat-treatment furnaces &amp; quenching systems; straightening machines; ultrasonic testing; online hardness testing; cutting &amp; inspection facilities", "29,160"],
    ],
)
ASP_PRODUCT_MIX = _table(
    ["Shop", "Products"],
    [
        ["Blooming &amp; Billet Mill", "Rolled RCS billets: 85-140 mm; rolled RCS blooms: 160-340 mm; rolled rounds: 80-210 mm"],
        ["Forge Shop", "Forged squares: 100-550 mm; forged rounds: 100-625 mm"],
        ["Plate Mill", "Plates (non-stainless steel): 5-40 mm thick"],
        ["Continuous Casting Shop", "Slabs (stainless/non-stn): 170×(900-1300) mm; bloom (twin) (stainless/non-stn): 250×(350-950) mm"],
    ],
)

_CONTENT = {
    "BSP": (BSP_CAPACITY, BSP_PRODUCT_MIX),
    "RSP": (RSP_CAPACITY, RSP_PRODUCT_MIX),
    "ISP": (ISP_CAPACITY, ISP_PRODUCT_MIX),
    "BSL": (BSL_CAPACITY, BSL_PRODUCT_MIX),
    "DSP": (DSP_CAPACITY, DSP_PRODUCT_MIX),
    "SSP": (SSP_CAPACITY, SSP_PRODUCT_MIX),
    "VISL": (VISL_CAPACITY, VISL_PRODUCT_MIX),
    "ASP": (ASP_CAPACITY, ASP_PRODUCT_MIX),
}


def run():
    print("NOTE: capacity/product-mix content is no longer seeded by this script "
          "(obsolete — see this module's own docstring); only plant-identity fields "
          "and process-flow images are upserted below.")
    for plant_code, (plant_name, plant_group, sort_order, image_filename) in PLANTS.items():
        db.upsert_ready_reckoner_master({
            "plant_code": plant_code, "plant_name": plant_name,
            "plant_group": plant_group, "sort_order": sort_order,
        })
        if image_filename:
            image_path = os.path.join(_STATIC_DIR, image_filename)
            if os.path.exists(image_path):
                db.save_ready_reckoner_image(plant_code, image_path, "backfill_script")
            else:
                print(f"WARNING: image not found for {plant_code}: {image_path}")
        print(f"seeded {plant_code} ({plant_name})")
    print("done")


if __name__ == "__main__":
    run()
