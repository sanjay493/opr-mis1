# Data Source Mapping Report

## Complete Data Extraction Trace

Generated: 2026-06-26

---

## SOURCE 1: OISCO File (May 2025)

### File Details
- **Path:** `D:\opr-mis1\Report_format\monthly\BSPOISCO_MAY'25.xlsx`
- **Report Month:** 2025-05 (May 2025)
- **Extractor:** `backend/excel_extractors/excel_extractor_bsp_oisco.py`
- **Function:** `extract_preview(file_path, '2025-05')`

### Extraction Statistics
- **Total Parameters:** 37
- **Parameters with Values:** 34
- **Parameters with NULL:** 3
- **Unique Sections:** 9
- **Data Groups:** IRON_MAKING, SMS, MAJOR, GENERAL

### Sections Found
1. CDI
2. Fuel Rate
3. Pellet in Burden
4. LD Slag Usage
5. Not Dry Cast
6. Coal to Hot Metal
7. BSP SMS-2
8. BSP SMS-3
9. Utilities

### Furnaces Extracted
```
BF-4: CDI = 113.65 Kg/THM (from parameter: "BSP BF-4")
BF-6: CDI = 112.58 Kg/THM (from parameter: "BSP BF-6")
BF-7: CDI = 103.17 Kg/THM (from parameter: "BSP BF-7")
BF-8: CDI = 134.54 Kg/THM (from parameter: "BSP BF-8")
```

### Sample Parameters Extracted
```
group_code: "IRON_MAKING"
section: "CDI"
parameter: "BSP BF-4"
unit: "Kg/THM"
actual: 113.65230928905034

group_code: "IRON_MAKING"
section: "Fuel Rate"
parameter: "BSP"
unit: "Kg/THM"
actual: 563.7946032276635

group_code: "SMS"
section: "BSP SMS-2"
parameter: "Converter Availability"
unit: "% ICH"
actual: 88.1

group_code: "SMS"
section: "BSP SMS-2"
parameter: "Converter Utilisation"
unit: "% Avail hr"
actual: 73.0
```

### NULL Values (Not Extracted)
```
parameter: "BSP BF-5" → NULL (Furnace BF-5 has no data)
parameter: "Coal to Hot Metal" → NULL (No value in Excel)
parameter: "Avg. Lining Life" → NULL
```

### Conversion to JSON
**Database Table:** `techno_furnace_data`

Inserted Records:
```
BF-4 (2025-05): 1 parameter (CDI)
BF-6 (2025-05): 1 parameter (CDI)
BF-7 (2025-05): 1 parameter (CDI)
BF-8 (2025-05): 1 parameter (CDI)
```

**Database Table:** `techno_plant_data`

Calculated from furnaces:
```
Plant: BSP (2025-05)
Parameters: 4
  - BSP BF-4: 113.65 (simple_average)
  - BSP BF-6: 112.58 (simple_average)
  - BSP BF-7: 103.17 (simple_average)
  - BSP BF-8: 134.54 (simple_average)
```

---

## SOURCE 2: TechnoMay File (May 2026)

### File Details
- **Path:** `D:\opr-mis1\Report_format\monthly\BSP-3-page-TechMay'26.xlsx`
- **Report Month:** 2026-05 (May 2026)
- **Extractor:** `backend/excel_extractors/excel_extractor_bsp_techno.py`
- **Function:** `extract_preview(file_path, '2026-05')`

### Extraction Statistics
- **Total Parameters:** 62
- **Parameters with Values:** 61
- **Parameters with NULL:** 1
- **Unique Sections:** 19
- **Data Groups:** COKE_SINTER, IRON_MAKING, MILL_BSP, SMS

### Sections Found
1. Coke Yield
2. Sinter Plant SP-2
3. Sinter Plant SP-3
4. Sinter in Burden
5. BF Coke Rate
6. Coke Screen Loss
7. CDI
8. Slag Rate
9. Nut Coke Rate
10. BF Productivity
11. Pellet in Burden
12. Energy
13. SMS-II Consumption
14. SMS-III Consumption
15. Bar & Rod Mill
16. Merchant Mill
17. Plate Mill
18. Rail & Structural Mill
19. (1 more)

### Furnaces Extracted
```
BF-6: Coke Rate = 430.2 Kg/THM (from parameter: "Coke Rate" in section "BF Coke Rate")
BF-6: BF Productivity = 2.12 T/m³/day
BF-6: HM Production = 11100.0 T
BF-7: BF Productivity = 1.91 T/m³/day (from parameter: "BSP BF-7")
BF-8: BF Productivity = 2.45 T/m³/day (from parameter: "BSP BF-8")
```

### Sample Parameters Extracted
```
group_code: "COKE_SINTER"
section: "Coke Yield"
parameter: "BF Coke"
unit: "%"
actual: 69.0

group_code: "IRON_MAKING"
section: "BF Coke Rate"
parameter: "BSP"
unit: "Kg/THM"
actual: 428.52

group_code: "IRON_MAKING"
section: "BF Productivity"
parameter: "BSP BF-7"
unit: "T/m³/day"
actual: 1.9126873578178025

group_code: "IRON_MAKING"
section: "CDI"
parameter: "BSP"
unit: "Kg/THM"
actual: 118.08
```

### NULL Values (Not Extracted)
```
parameter: "Crude Benzol" → NULL (No value in Excel)
```

### Conversion to JSON
**Database Table:** `techno_furnace_data`

Inserted Records:
```
BF-6 (2026-05): 3 parameters (Coke Rate, BF Productivity, HM Production)
BF-7 (2026-05): 1 parameter (BSP BF-7)
BF-8 (2026-05): 1 parameter (BSP BF-8)
```

**Database Table:** `techno_plant_data`

Calculated/Retrieved:
```
Plant: BSP (2026-05)
Parameters: 4
  - BF Productivity: 2.0 (SOURCE: legacy_data from old table)
  - Coke Rate: 428.13 (SOURCE: legacy_data from old table)
  - BSP BF-7: 1.91 (SOURCE: calculated from furnace)
  - BSP BF-8: 2.45 (SOURCE: calculated from furnace)
```

---

## 🔍 POTENTIAL ISSUES & CORRECTIONS NEEDED

### Issue 1: Parameter Name Inconsistency

**Problem Location:** How parameter names are extracted and stored

**OISCO:**
- Extracts: "BSP BF-4", "BSP BF-6", etc. (from parameter column)
- Stored as: Full parameter name including "BSP BF-X"
- **Fix needed?** Do you want to normalize to just "CDI" or keep full name?

**TechnoMay:**
- Section: "BF Productivity"
- Parameter: "BSP BF-7"
- Extracts: "BSP BF-7" (from parameter)
- **Fix needed?** Same inconsistency as OISCO

**Recommendation:**
```python
# In converter, normalize parameter names:
if 'BF-' in param_name:
    # Extract just the value part, not the furnace identifier
    param_display_name = param_name.replace('BSP ', '')
```

---

### Issue 2: Furnace Not Identified (BF-5)

**Problem:**
- OISCO has parameter "BSP BF-5" with NULL value
- Not extracted because value is NULL
- Should still create furnace BF-5 record with NULL data? Or skip?

**Current Code:**
```python
if row.value is None:
    continue  # Skips NULL values
```

**Fix Options:**
1. **Keep current:** Skip NULL values (cleaner data)
2. **Include NULL:** Store NULL records for completeness
3. **Custom logic:** Different handling per parameter type

**Recommendation:** Ask - do you want to keep NULL values?

---

### Issue 3: Legacy Data Priority Masking Real Data

**Problem Location:** `techno_json_utils.py`, line ~245

**Current Behavior (May 2026):**
```json
{
  "BF Productivity": {
    "value": 2.0,
    "source": "legacy"  ← Using OLD value, not new extracted 2.12!
  },
  "Coke Rate": {
    "value": 428.13,
    "source": "legacy"  ← Using OLD calculated value, not new 428.52!
  }
}
```

**Problem:**
- New TechnoMay extraction: BF Coke Rate = 428.52
- But plant data shows: Coke Rate = 428.13 (legacy)
- **Which is correct?** Old data (428.13) or new data (428.52)?

**Fix needed?**
```python
# Option 1: Use new data, ignore legacy
  Use extracted value: 428.52

# Option 2: Keep legacy, ignore new
  Use legacy value: 428.13

# Option 3: Compare and log difference
  Log: "Legacy: 428.13, New: 428.52 - using legacy"
```

**Recommendation:** Update the priority system to your preference

---

### Issue 4: Weighted Average Not Working

**Problem Location:** Plant calculation uses "simple_average" instead of "weighted_average"

**Reason:**
- HM Production values not properly extracted from TechnoMay
- Or not in the right format
- Falls back to simple average

**Current Result (May 2025):**
```
Furnaces: BF-4, BF-6, BF-7, BF-8
Method: simple_average (not weighted!)
Reason: "Some furnaces missing HM Production"
```

**Check:**
1. Does OISCO file have HM Production data?
2. If yes, which row/column?
3. What's the exact parameter name?

**Fix:**
```python
# In excel_extractor_bsp_oisco.py, add:
HM_PRODUCTION_ROWS = {
    'Hot Metal': 'HM Production',  # Adjust based on actual Excel
    'Production': 'HM Production',
    # Check Excel for exact name
}
```

---

## 📊 DATA QUALITY CHECKLIST

For each source file, verify:

### OISCO File (BSPOISCO_MAY'25.xlsx)
- [ ] Check exact column headers in Excel
- [ ] Verify BF-5 truly has no data (or should it?)
- [ ] Confirm HM Production location if exists
- [ ] Check for any hidden columns/data
- [ ] Verify all 37 parameters extracted match Excel

### TechnoMay File (BSP-3-page-TechMay'26.xlsx)
- [ ] Check Coke Rate value: is it 428.52 or something else?
- [ ] Verify BF Productivity values (1.91, 2.45 correct?)
- [ ] Confirm HM Production location
- [ ] Check which parameter has NULL value
- [ ] Verify all 62 parameters extracted match Excel

---

## 🔧 IMMEDIATE CORRECTIONS POSSIBLE

### 1. Fix Parameter Naming
```python
# File: excel_to_json_converter.py, line ~90
Old: param_name = row.parameter
New: param_name = clean_parameter_name(row.parameter)

def clean_parameter_name(param):
    # Remove "BSP " prefix if furnace-specific
    return param.replace('BSP ', '').strip()
```

### 2. Handle NULL Values
```python
# File: excel_to_json_converter.py, line ~84
Old: if row.value is None: continue
New: if row.value is None and not is_identifier_param(row.parameter):
        continue
```

### 3. Fix Legacy Data Priority
```python
# File: techno_json_utils.py
# Swap priority order or disable legacy check:
# legacy_value = None  # Disable legacy priority
# Or use new data if available
```

---

## 📝 NEXT STEPS

Please verify:

1. **Open BSPOISCO_MAY'25.xlsx**
   - Check parameter names in column C
   - Check BF-5 row - is it truly empty?
   - Check if HM Production exists (where?)

2. **Open BSP-3-page-TechMay'26.xlsx**
   - Check if Coke Rate is really 428.52 or different
   - Verify BF Productivity values
   - Check where HM Production is stored

3. **Confirm desired behavior:**
   - Keep or ignore NULL values?
   - Use new data or legacy data?
   - Should parameters be normalized?

Report back with these details and I'll fix the extractor code! 🔧

---

**Once confirmed, I can:**
- Update extractors for correct parameter names
- Fix the weighted average calculation
- Handle NULL values appropriately
- Resolve legacy vs. new data conflicts
