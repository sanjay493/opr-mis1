# Techno Parameter Groups — Quick Reference

## When to Use Which Group

### 🔥 Iron Making — Blast Furnace
**Group Code:** `IRON_MAKING`  
**Entities:** Plant-level (BSP, DSP, RSP, BSL, ISP, SAIL) + Per-furnace (BSP BF-4,6,7,8; DSP BF-2,3,4; etc.)  
**Params:** CDI Rate, Coke Rate, Nut Coke, Coal/HM, Fuel, BF Productivity, Sinter%, Pellet%  
**Use When:** Entering or reviewing blast furnace metrics

### 🔥 Iron Making — BSL Furnaces  
**Group Code:** `BSL`  
**Entities:** BSL per-furnace detail (BF-1, BF-2, BF-4, BF-5, Plant Shop)  
**Params:** CDI Rate, Coke Rate, BF Scrap, etc.  
**Use When:** Focusing on BSL furnace-specific data (subset of IRON_MAKING)

### ♨️ Coke & Sinter
**Group Code:** `COKE_SINTER`  
**Entities:** Plant-level coke + sinter plant data  
**Params:** Coal Charge, Tar Yield, Gas Yield, Benzol Yield, Sinter Productivity, etc.  
**Use When:** Entering coke oven or sinter plant data

### 🌡️ Steel Making — SMS
**Group Code:** `SMS`  
**Entities:** SMS shop-wise (BSP SMS-2, BSP SMS-3, DSP SMS, RSP SMS-1, RSP SMS-2, etc.)  
**Params:** Hot Metal Consumption, Scrap Consumption, TMI, Oxygen, etc.  
**Use When:** Entering steel melting shop metrics

### 🏭 Mills — [Plant Name]  
**Group Code:** `MILL_BSP`, `MILL_DSP`, `MILL_RSP`, `MILL_BSL`, `MILL_ISP`  
**Entities:** Per-plant rolling mill sections  
**Params:** Productivity, Availability, Utilisation, Yield, etc.  
**Use When:** Entering data for a specific mill

### 🏭 Mills — All Plants
**Group Code:** `MILLS`  
**Entities:** All 5 plants' mill data combined (200+ rows)  
**Params:** Same as individual MILL_* groups  
**Use When:** Cross-plant mill analysis or batch entry

### 📊 General / Plant-level
**Group Code:** `GENERAL`  
**Entities:** All plants + SAIL (6 rows)  
**Params:** Specific Energy Consumption, (others to be added)  
**Use When:** Entering plant-level cross-cutting metrics

### 📄 Major — Page 27 Display (Read-Only Reference)
**Group Code:** `MAJOR`  
**Entities:** Plant summaries + SAIL  
**Params:** Vital BF, SMS, energy params across areas  
**Use When:** Reviewing official page 27 display data (same data as IRON_MAKING, SMS, GENERAL, etc.)

---

## Key Principles

### ✓ Single Source of Truth
Each parameter is **stored once**. When you enter CDI Rate for BSP in IRON_MAKING, it automatically appears in MAJOR's display because they share the same param_id.

### ✓ No Duplication
The old system stored Plant Shop entries separately. Now "BSP" is stored once and linked to both MAJOR and IRON_MAKING groups.

### ✓ Area-Based Organization
Groups are organized by **technical area** (Iron Making, Coke, SMS, Mills, General) rather than mixing concerns.

### ✓ Backward Compatible
PDF pages (27–35) continue to work without changes. They query the same param_ids you're entering data into.

---

## Data Flow Example

**You enter:** CDI Rate = 92 for BSP via IRON_MAKING group  
↓  
Stored in `techno_actuals` for param_id = (CDI Rate, BSP)  
↓  
**Appears in:**
- IRON_MAKING group → CDI Rate section → BSP row ✓
- MAJOR group → CDI Rate section → BSP row ✓
- Page 29 PDF (IRON_MAKING page) ✓
- Page 27 PDF (MAJOR page) ✓

---

## Group Size Reference

| Group | # Params | # Plants/Entities | Estimated Rows |
|-------|----------|-------------------|-----------------|
| IRON_MAKING | ~30 | 6 plants + 14 furnaces | ~200 |
| BSL | ~30 | 5 furnaces + 1 shop | ~50 |
| COKE_SINTER | ~30 | Plant-level | ~30 |
| SMS | ~15 | 8 shops | ~120 |
| MILL_BSP | ~6 | 2–3 mill sections | ~15 |
| MILL_DSP | ~8 | 3–4 mill sections | ~30 |
| MILL_RSP | ~10 | 4–5 mill sections | ~40 |
| MILL_BSL | ~2 | 2 mill sections | ~4 |
| MILL_ISP | ~3 | 2–3 mill sections | ~8 |
| MILLS | ~40 | All 5 plants | ~100 |
| GENERAL | ~1 | 6 (5 plants + SAIL) | ~6 |
| MAJOR | ~40 | 6 (5 plants + SAIL) | ~80 |

---

## Common Tasks

### "I want to enter BF data"
→ Select **IRON_MAKING** group → Enter CDI, Coke, Fuel, etc.

### "I want to look at just BSL furnaces"
→ Select **BSL** group (faster than scrolling through IRON_MAKING)

### "I want to compare all mills"
→ Select **MILLS** group → All 5 plants in one view

### "I want to review plant-level metrics"
→ Select **GENERAL** group → Sp. Energy Consumption, etc.

### "I need to fill out page 27 of the report"
→ Select **MAJOR** group → This group drives page 27

### "I want the data to appear everywhere"
→ Enter via **functional group** (IRON_MAKING, COKE_SINTER, etc.) → Automatically appears in all linked displays

---

## API Response Format

When you load a group, you get back:

```json
{
  "group_code": "IRON_MAKING",
  "month": "2026-06",
  "sections": [
    {
      "section": "CDI Rate",
      "unit": "Kg/THM",
      "rows": [
        {
          "param_id": 12,
          "row_label": "BSP",
          "actual": 92.0,
          "till_month_actual": 90.5,
          "source": "manual"
        },
        {
          "param_id": 13,
          "row_label": "BSP BF-4",
          "actual": null,
          "till_month_actual": null,
          "source": null
        },
        ...
      ]
    }
  ]
}
```

Each **section** = one parameter name (e.g., "CDI Rate")  
Each **row** = one entity (e.g., "BSP" plant or "BSP BF-4" furnace)

---

## Troubleshooting

**Q: I entered data in IRON_MAKING but don't see it in MAJOR**  
A: Refresh the page and reload. They share the same param_id so it should appear.

**Q: The MILLS group is huge. Can I filter it?**  
A: Use the filter box on the left. Type "BSP" to see only BSP mill data.

**Q: Why is the GENERAL group so small?**  
A: It only has Sp. Energy Consumption for now. More params will be added later.

**Q: Can I enter data via MAJOR group?**  
A: Yes — MAJOR is also a functional group. But IRON_MAKING, SMS, etc. are preferred (more organized by area).
