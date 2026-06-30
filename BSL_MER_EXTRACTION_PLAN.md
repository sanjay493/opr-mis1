# BSL Blast Furnace Month-End Report (MER) Extraction Plan

## Overview

Extract furnace-wise techno parameters from BSL Month-End Report PDF files.
- **File pattern:** `BSL_BlastFurnace_DDMMYYYY.pdf` (e.g., `BSL_BlastFurnace_30042026.pdf`)
- **Report date format:** DDMMYYYY → converted to YYYY-MM for database
- **Data scope:** Monthly values only (no till-month available)
- **Furnaces:** BF-1, BF-2, BF-4, BF-5 (+ BF_Shop aggregate)

---

## Parameters to Extract

### Production & Performance (from PRODUCTION PERFORMANCE table)

| Parameter | Handle Name | Unit | Example Value |
|-----------|------------|------|----------------|
| Daily Production | `production` | tonnes | 3678 |
| Daily Rate | `daily_rate` | tonnes/day | 3335 |
| Monthly Rate | `monthly_rate` | tonnes | 100056 |
| BF Productivity | `bf_productivity` | t/m³/day | 2.09 |

### Quality Parameters (from QUALITY PARAMETERS table)

| Parameter | Handle Name | Unit | Example Value |
|-----------|------------|------|----------------|
| Si ≤ 0.90 (%) | `si_in_hm` | % | 100 / 89.2 |
| S ≤ 0.045 (%) | `s_in_hm` | % | 33.3 / 60.0 |
| Slag Rate | `slag_rate` | kg/THM | 468 / 455 |
| Coke Rate | `coke_rate` | kg/thm | 440 / 439 |
| CDI Rate | `cdi` | kg/thm | 108 / 94 |
| Fuel Rate | `fuel_rate` | kg/thm | 568 / 548 |
| Nut Coke Rate | `nut_coke_rate` | kg/thm | 19 / 16 |
| Hot Blast Temp | `hot_blast_temp` | °C | 1100 / 1088 |
| Hot Metal Temp | `hot_metal_temp` | °C | 1495 / 1479 |
| O2 Enrichment | `o2_enrichment` | % | 3.02 / 2.95 |

### Raw Material Consumption (from CONSUMPTION OF RAW MATERIAL table)

| Parameter | Handle Name | Unit | Example Value |
|-----------|------------|------|----------------|
| Coke Consumption | `coke_consumption` | tonnes | 1619 / 43899 |
| Iron Ore Consumption | `iron_ore_consumption` | tonnes | 2415 / 59037 |
| Sinter Consumption | `sinter_consumption` | tonnes | 4810 / 110488 |
| Scrap Consumption | `scrap_consumption` | tonnes | 0 / 3483 |
| Pellet Consumption | `pellet_consumption` | tonnes | 0 / 8229 |
| Nut Coke Consumption | `nut_coke_consumption` | tonnes | 72 / 1556 |

### Calculated Parameters

| Parameter | Handle Name | Formula |
|-----------|------------|---------|
| Sinter % in Burden | `sinter_in_burden` | (Sinter / Total Burden) × 100 |
| Pellet % in Burden | `pellet_in_burden` | (Pellet / Total Burden) × 100 |

**Where:** Total Burden = Iron Ore + Sinter + Pellet + Scrap

---

## Data Extraction Source

### PDF Structure

The PDF contains multiple tables:

1. **PRODUCTION PERFORMANCE** (Rows 2-10)
   - Furnace data: BF-1, BF-2, BF-4, BF-5, Shop aggregate
   - Contains: Production, Daily Rate, Charges, Off-Blast, Hot Blast, Productivity

2. **QUALITY PARAMETERS** (Rows 13-20)
   - Furnace-wise quality metrics
   - Contains: Si, S, Slag, Temperature, Rates

3. **CONSUMPTION OF RAW MATERIAL** (Rows 23-32)
   - Furnace-wise raw material consumption
   - Contains: Coke, Iron Ore, Sinter, Scrap, Pellet, Nut Coke
   - **Format:** Each cell has "monthly / till_month" (e.g., "1619 / 43899")
   - **We extract:** First value only (monthly)

---

## Extraction Strategy

### Step 1: Read PDF as Text
```python
import pdfplumber

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[0]
    text = page.extract_text()
```

### Step 2: Parse Tables by Section
Split text into sections (PRODUCTION PERFORMANCE, QUALITY PARAMETERS, CONSUMPTION)

### Step 3: Extract Values for Each Furnace

For each furnace row:
1. Extract monthly value (before "/" character)
2. Clean: remove commas, handle "***" (under repair)
3. Convert to float

### Step 4: Calculate Burden Percentages
```python
total_burden = iron_ore + sinter + pellet + scrap
if total_burden > 0:
    sinter_pct = (sinter / total_burden) * 100
    pellet_pct = (pellet / total_burden) * 100
```

### Step 5: Build Output Records
```json
{
  "plant": "BSL",
  "report_month": "2026-04",
  "unit": "BF-1",
  "techno_json": {
    "month": {
      "production": 3678,
      "daily_rate": 3335,
      "bf_productivity": 2.09,
      "coke_rate": 440,
      "cdi": 108,
      "hot_blast_temp": 1100,
      "hot_metal_temp": 1495,
      "si_in_hm": 100,
      "s_in_hm": 33.3,
      "slag_rate": 468,
      "fuel_rate": 568,
      "nut_coke_rate": 19,
      "o2_enrichment": 3.02,
      "iron_ore_consumption": 2415,
      "sinter_consumption": 4810,
      "scrap_consumption": 0,
      "pellet_consumption": 0,
      "nut_coke_consumption": 72,
      "sinter_in_burden": 54.27,
      "pellet_in_burden": 0.0
    },
    "till_month": {}
  }
}
```

---

## Implementation Notes

### Value Format in PDF

Each cell contains two values separated by "/":
```
monthly_value / till_month_value

Examples:
- "1619 / 43899" → Extract 1619 (monthly)
- "100/89.2"     → Extract 100 (monthly)
- "3.02/2.95"    → Extract 3.02 (monthly)
```

### Furnace Rows

| Furnace | Production Row | Quality Row | Consumption Row |
|---------|----------------|-------------|-----------------|
| BF-1 | Row 5 | Row 14 | Row 27 |
| BF-2 | Row 6 | Row 15 | Row 28 |
| BF-4 | Row 8 | Row 17 | Row 30 |
| BF-5 | Row 9 | Row 18 | Row 31 |
| Shop | Row 10 | Row 19 | Row 32 |

### Special Cases

1. **Under Repair:** BF-3 marked with "***U N D E R C A P I T A L R E P A I R***" → Skip
2. **Zero Values:** Keep as is (0 tonnes is valid)
3. **Missing Data:** Store as null/None (will be skipped in JSON)

---

## Database Storage

### Target Table: `techno_data`

```sql
CREATE TABLE techno_data (
    id INTEGER PRIMARY KEY,
    plant TEXT NOT NULL,              -- "BSL"
    report_month TEXT NOT NULL,       -- "2026-04"
    unit TEXT NOT NULL,               -- "BF-1", "BF-2", "BF_Shop"
    techno_json TEXT NOT NULL,        -- JSON: {"month": {...}, "till_month": {}}
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### JSON Structure

```json
{
  "month": {
    "production": 3678,
    "daily_rate": 3335,
    ...
  },
  "till_month": {}
}
```

---

## Testing

### Test Case: April 2026

**File:** `BSL_BlastFurnace_30042026.pdf`

**Expected Output for BF-1:**
```json
{
  "unit": "BF-1",
  "production": 3678,
  "daily_rate": 3335,
  "bf_productivity": 2.09,
  "coke_rate": 440,
  "iron_ore_consumption": 2415,
  "sinter_consumption": 4810,
  "pellet_consumption": 0,
  "scrap_consumption": 0,
  "sinter_in_burden": 54.27,
  "pellet_in_burden": 0.0
}
```

### Validation

1. ✓ All furnaces present: BF-1, BF-2, BF-4, BF-5, BF_Shop
2. ✓ All parameters extracted
3. ✓ Burden percentages calculated
4. ✓ Monthly values used (not till-month)
5. ✓ Report month correctly detected from filename

---

## Integration

### API Endpoint

```python
POST /api/extract-bsl-mer
{
  "file_path": "Report_format/MONTHEND/BSL_BlastFurnace_30042026.pdf",
  "report_month": "2026-04"  (optional, auto-detected)
}
```

### Response
```json
{
  "status": "success",
  "extracted": 5,
  "plant": "BSL",
  "report_month": "2026-04",
  "units": ["BF-1", "BF-2", "BF-4", "BF-5", "BF_Shop"],
  "records": [...]
}
```

### Database Insert
```python
for record in records:
    db.execute(
        "INSERT INTO techno_data (plant, report_month, unit, techno_json) VALUES (?, ?, ?, ?)",
        (record['plant'], record['report_month'], record['unit'], json.dumps(record['techno_json']))
    )
```

---

## Parameters Summary

**Total Parameters:** 18 extractable + 2 calculated = **20 parameters per furnace**

**Furnaces:** 5 (BF-1, BF-2, BF-4, BF-5, BF_Shop)

**Total Records per Report:** 5 units × 1 (month only, no till-month) = **5 records per report**

---

## Next Steps

1. ✅ Create parameter map (bsl_mer_map.json)
2. ✅ Create extractor skeleton (bsl_mer_extractor.py)
3. ⏳ Implement PDF parsing logic for actual table extraction
4. ⏳ Add burden percentage calculation
5. ⏳ Create API endpoint in main.py
6. ⏳ Test with sample BSL month-end reports
7. ⏳ Verify data display on Page 27

