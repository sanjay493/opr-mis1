# BSL Techno Parameter Extraction Mapping

## Overview
The BSL techno parameter extractor (`excel_extractor_bsl.py`) extracts data from techno-economic Excel files and maps them to a standardized database format.

## Extraction File Format

**Input:** TECHNO <MONTH><YYYY>.XLS or .XLSX
- Contains multiple sheets: Sheet1, Sheet2, Sheet3, Sheet4, SMS-I, SMS-II
- Each parameter stored in specific cell (Row, Column)
- Two values per parameter: Monthly (actual) and Cumulative (till_month)

## Parameter Map

### Sheet1 - Main Blast Furnace & Energy Parameters

| Parameter | Row | Col | Multiplier | Group Code | Section | Unit |
|-----------|-----|-----|-----------|-----------|---------|------|
| Sp. Heat Cons. | 10 | F | 1000 | COKE_SINTER | Energy | Kcal/TCO |
| Specific Energy Consumption | 26 | F | 1 | COKE_SINTER | Energy | KWH/TCHS |
| Machine Productivity | 31 | F | 1 | COKE_SINTER | Sinter Plant | T/m²/hr |
| **BF Productivity** | 33 | F | 1 | **IRON_MAKING** | BF Productivity | **T/m³/day** |
| **BF Coke Rate** | 35 | F | 1 | **IRON_MAKING** | BF Coke Rate | **Kg/THM** |
| **CDI Rate** | 37 | F | 1 | **MAJOR** | CDI Rate | **kg/Thm** |
| **Fuel Rate** | 39 | F | 1 | **IRON_MAKING** | Fuel Rate | **Kg/THM** |
| **Coal to Hot Metal** | 41 | F | 1 | **MAJOR** | Coal to Hot Metal | **Ratio** |
| Coke Ovens - Gross Yield | 14 | F | 1 | COKE_SINTER | Coke Ovens | % |
| ... | ... | ... | ... | ... | ... | ... |

**(Bold items are MAJOR parameters displayed on Page 27)**

### Sheet2 - Coke Oven Parameters

| Parameter | Row | Col | 
|-----------|-----|-----|
| Dry Coal Charge per Oven | 11 | F |
| Average Coking Time | 12 | F |
| Gross Coke Yield | 14 | F |
| BF Coke Yield | 15 | F |
| Ammonium Sulphate | 16 | F |
| Crude Tar | 17 | F |
| ... | ... | ... |

### Sheet3 - Sinter Plant Parameters

| Parameter | Row | Col |
|-----------|-----|-----|
| Coke Crushing Index for Sinter | 25 | F |
| Flux Crushing Index for Sinter | 27 | F |
| Sinter Return | 29 | F |
| FeO in Sinter | 31 | F |
| ... | ... | ... |

### Sheet4 - Additional Blast Furnace Parameters

| Parameter | Row | Col |
|-----------|-----|-----|
| **Sinter in Burden** | 31 | F |
| **O2 Enrichment** | 33 | F |
| Coke Screen Loss | 35 | F |
| Slag Rate | 37 | F |
| ... | ... | ... |

### SMS-I & SMS-II - Steel Melting Shop Parameters

| Parameter | Row | Col | Section |
|-----------|-----|-----|---------|
| Tap to Tap Time (Avail. Hrs) | 12 | F | SMS-I |
| Tap to Tap Time (Working Hrs) | 14 | F | SMS-I |
| **Sp. Hot Metal Cons.** | 23 | F | **SMS-I** |
| **Sp. Scrap Cons.** | 25 | F | **SMS-I** |
| Iron Ore Consumption | 27 | F | SMS-I |
| Pellet Consumption | 26 | F | SMS-I |
| ... | ... | ... | ... |

## Database Storage

### Old Schema (DEPRECATED)
- Used `techno_actuals` table with individual parameter rows
- Structure: `(report_month, param_id, actual, till_month_actual, source)`

### New Schema (CURRENT)
- Uses `techno_data` table with JSON storage
- Structure:
  ```json
  {
    "plant": "BSL",
    "report_month": "2026-05",
    "unit": "BF_Shop",
    "techno_json": {
      "month": {
        "bf_productivity": 2.24,
        "bf_coke_rate": 407,
        "cdi_rate": 125,
        "fuel_rate": 550,
        "coal_to_hot_metal": 0.92,
        "specific_energy_consumption": 5.86,
        "nut_coke_rate": 18,
        "sinter_in_burden": 69.3,
        "pellet_in_burden": 18.2,
        ...
      },
      "till_month": {
        "bf_productivity": 2.24,
        ...
      }
    }
  }
```

## Parameter Name Conversion

When extracting parameters, the names are converted to database keys:

| Excel Parameter Name | Database Key |
|----------------------|--------------|
| BF Productivity | `bf_productivity` |
| BF Coke Rate | `bf_coke_rate` |
| CDI Rate | `cdi_rate` |
| Fuel Rate | `fuel_rate` |
| Coal to Hot Metal | `coal_to_hot_metal` |
| Specific Energy Consumption | `specific_energy_consumption` |
| Nut Coke Rate | `nut_coke_rate` |
| Sinter in Burden | `sinter_in_burden` |
| Pellet in Burden | `pellet_in_burden` |
| O2 Enrichment | `o2_enrichment` |
| Sp. Hot Metal Cons. | `sp_hot_metal_cons` |
| Sp. Scrap Cons. | `sp_scrap_cons` |

## Extraction Workflow

1. **Upload File**
   - User uploads TECHNO APRIL2026.XLS
   - System auto-detects month from filename or Sheet1 header

2. **Preview Extraction** (GET /api/extract-techno-preview)
   - Reads Excel file
   - Parses cells according to `_TECHNO_PARAM_MAP`
   - Returns list of extracted rows with status (ok/skip)
   - Shows: parameter name, value, unit, cell location

3. **Confirm & Save** (POST /api/techno-entries)
   - User reviews and confirms extraction
   - System calls `save_techno_data_from_extraction()`
   - Converts parameters to lowercase keys
   - Builds JSON structure
   - Saves to `techno_data` table

4. **Display** (GET /report/page/27)
   - Page 27 loads data from `techno_data` table
   - Extracts values for major parameters
   - Formats according to decimal place rules:
     - BF Productivity: 2 decimals
     - Coal to Hot Metal: 3 decimals
     - Others: 0 decimals

## MAJOR Parameters on Page 27

These parameters are displayed on Page 27 (Major Techno-Economic Parameters):

1. **Coal to Hot Metal** (kg/kg) - 3 decimals
   - Excel: Sheet1, Row 41, Col F
   - DB Key: `coal_to_hot_metal`

2. **Coke Rate** (kg/thm) - 0 decimals
   - Excel: Sheet1, Row 35, Col F
   - DB Key: `bf_coke_rate`

3. **Nut Coke Rate** (kg/thm) - 0 decimals
   - Excel: Sheet1, Row 35, Col F
   - DB Key: `nut_coke_rate`

4. **CDI Rate** (kg/thm) - 0 decimals
   - Excel: Sheet1, Row 37, Col F
   - DB Key: `cdi_rate`

5. **Fuel Rate** (kg/thm) - 0 decimals
   - Excel: Sheet1, Row 39, Col F
   - DB Key: `fuel_rate`

6. **Sinter in Burden** (%) - 0 decimals
   - Excel: Sheet4, Row 31, Col F
   - DB Key: `sinter_in_burden`

7. **Pellet in Burden** (%) - 0 decimals
   - Excel: Sheet4, Row 31, Col F
   - DB Key: `pellet_in_burden`

8. **BF Productivity** (T/m³/day) - 2 decimals
   - Excel: Sheet1, Row 33, Col F
   - DB Key: `bf_productivity`

9. **Specific Energy Consumption** (Gcal/tcs) - 2 decimals
   - Excel: Sheet1, Row 26, Col F
   - DB Key: `specific_energy_consumption`

## Debugging

If extraction fails:
1. Check Excel file has sheets: Sheet1, Sheet2, Sheet3, Sheet4, SMS-I, SMS-II
2. Verify cells contain numeric values at expected locations
3. Check month is correctly detected from filename or header
4. Verify file is not corrupted (try opening in Excel first)

If values don't appear on Page 27:
1. Verify `techno_data` table has rows for your plant/month
2. Check database keys match parameter names (lowercase, underscore-separated)
3. Confirm JSON structure has "month" and "till_month" keys
4. Check report month selection matches extracted month

