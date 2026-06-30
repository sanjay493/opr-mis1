# Sinter % in Burden and Pellet % in Burden Calculation

## Overview

When extracting techno parameters, we automatically calculate **Sinter % in Burden** and **Pellet % in Burden** from raw material consumption data. These are common parameters across all blast furnaces at all plants.

## Calculation Formula

### Total Burden
```
Total Burden = Iron Ore Consumption + Sinter Consumption + Pellet Consumption + Scrap Consumption
(All in tonnes)
```

### Sinter % in Burden
```
Sinter % in Burden = (Sinter Consumption / Total Burden) × 100
```

### Pellet % in Burden
```
Pellet % in Burden = (Pellet Consumption / Total Burden) × 100
```

## Data Flow

### Input Parameters (Extracted)
- **Iron Ore Consumption** (T)
- **Sinter Consumption** (T)
- **Pellet Consumption** (T)
- **Scrap Consumption** (T)

### Output Parameters (Calculated)
- **Sinter % in Burden** (%)
- **Pellet % in Burden** (%)

## Implementation

### Shared Utility Module
**File:** `backend/excel_extractors/techno_calc_utils.py`

Function: `calculate_burden_percentages(rows_out, report_month, plant_name)`

**Features:**
- Works with all plant extractors (BSL, BSP, DSP, ISP, RSP)
- Handles furnace-wise calculations (BF-1, BF-2, BF-4, BF-5)
- Handles shop-level aggregations (BF_Shop, SMS-I, etc.)
- Automatically groups data by furnace/plant label
- Validates input data before calculation
- Adds calculated rows with proper metadata

### Plant Extractors Integration

All plant extractors call this utility:

```python
from techno_calc_utils import calculate_burden_percentages

# At the end of extraction, before returning preview
calculate_burden_percentages(rows_out, db_month, plant_name="BSL")
```

## Example: BSL Extraction

### Input from Excel File

| Parameter | Iron Ore (T) | Sinter (T) | Pellet (T) | Scrap (T) |
|-----------|--------------|-----------|-----------|-----------|
| BF-1 | 100 | 60 | 30 | 10 |
| BF-2 | 110 | 65 | 35 | 12 |
| BF Shop | 220 | 130 | 70 | 25 |

### Calculations

**BF-1:**
- Total Burden = 100 + 60 + 30 + 10 = 200 T
- Sinter % = (60 / 200) × 100 = **30.0%**
- Pellet % = (30 / 200) × 100 = **15.0%**

**BF-2:**
- Total Burden = 110 + 65 + 35 + 12 = 222 T
- Sinter % = (65 / 222) × 100 = **29.28%**
- Pellet % = (35 / 222) × 100 = **15.77%**

**BF Shop (Aggregate):**
- Total Burden = 220 + 130 + 70 + 25 = 445 T
- Sinter % = (130 / 445) × 100 = **29.21%**
- Pellet % = (70 / 445) × 100 = **15.73%**

### Output (Added to rows_out)

```json
{
  "group_code": "IRON_MAKING",
  "section": "Sinter in Burden",
  "parameter": "BSL BF-1",
  "unit": "%",
  "actual": 30.0,
  "cum_actual": 30.0,
  "sort_order": 200,
  "source_priority": 4,
  "cell": "Calculated: Sinter / (Iron Ore + Sinter + Pellet + Scrap) × 100",
  "file_label": "Sinter % in Burden (BSL BF-1)",
  "plant": "BSL",
  "month": "2026-05",
  "found_via": "BSL BF-1 Burden calculation",
  "status": "ok"
}
```

## Display on Page 27

These calculated parameters appear in the **Iron Making** group section on Page 27:

- **Sinter in Burden (%)** — Furnace-wise and shop-wise
- **Pellet in Burden (%)** — Furnace-wise and shop-wise

### Formatting

- Unit: `%`
- Decimal places: **0 decimals** (per formatting rules)
- Example display: **30%**, **15%**

## Data Storage

Calculated burden percentages are stored in the `techno_data` table like any other extracted parameter:

```json
{
  "month": {
    "sinter_in_burden": 30.0,
    "pellet_in_burden": 15.0,
    "iron_ore_consumption": 100,
    "sinter_consumption": 60,
    "pellet_consumption": 30,
    "scrap_consumption": 10
  }
}
```

## Extraction Priority

- **source_priority = 4**: Calculated values (lower priority)
- **source_priority = 5**: Directly extracted values (higher priority)

This means if burden percentages are found directly in the Excel file (extracted as priority 5), they will **not be overwritten** by calculated values (priority 4).

## Supported Plants

The calculation is automatically applied for all plants:

| Plant | Extractors | Furnaces |
|-------|-----------|----------|
| **BSL** | excel_extractor_bsl.py | BF-1, BF-2, BF-4, BF-5, BF Shop |
| **BSP** | excel_extractor_bsp.py | BF-1, BF-2, BF-3, BF Shop |
| **DSP** | excel_extractor_dsp.py | BF-3, BF-4, BF Shop |
| **RSP** | excel_extractor_rsp.py | BF-1, BF-2, BF-3, BF Shop |
| **ISP** | excel_extractor_isp.py | BF-1, BF-2, BF Shop |

## Error Handling

The calculation:
- ✅ Handles missing consumption data gracefully (skips calculation if data incomplete)
- ✅ Validates total burden > 0 (won't calculate if total is zero or negative)
- ✅ Rounds to 2 decimal places for storage, displayed as 0 decimals
- ✅ Works with both individual furnaces and aggregated shop-level data
- ✅ Adds metadata for debugging ("Calculated from...")

## Debugging

If burden percentages don't appear:
1. Verify extraction includes consumption data (Iron Ore, Sinter, Pellet, Scrap)
2. Check all four consumption values are present (cannot calculate with partial data)
3. Check `source_file` in extraction log to confirm the extractor was called
4. Verify `status` is "ok" in extracted data (not "skip")

### Check Database
```sql
SELECT * FROM techno_data 
WHERE plant = 'BSL' 
AND report_month = '2026-05'
AND unit = 'BF_Shop'
AND techno_json LIKE '%sinter_in_burden%'
```

## Common Issues

### Issue: Percentages sum to more than 100%
**Cause:** This can happen if not all burden materials are included in the total
**Solution:** Verify Excel file includes all materials (iron ore, sinter, pellet, scrap)

### Issue: Calculated percentages differ from Excel file
**Cause:** Excel file may use different materials or calculation method
**Solution:** Check if Excel file has pre-calculated percentages; those will be used instead (priority 5 > 4)

### Issue: Percentages not showing on Page 27
**Cause:** Parameter names or database keys don't match
**Solution:** Verify `sinter_in_burden` and `pellet_in_burden` keys exist in JSON

