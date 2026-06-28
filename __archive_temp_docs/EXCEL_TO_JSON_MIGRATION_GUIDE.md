# Excel to JSON Migration Guide

## Overview

This guide shows how to migrate your existing Excel-based techno data extraction to the new JSON-based system.

**Current State:**
- Excel extractors (excel_extractor_bsp_techno.py, excel_extractor_bsp_oisco.py) extract parameter data
- Data stored in old techno_actuals table (normalized schema)

**Target State:**
- Same extractors run → output converted to JSON
- Data stored in new techno_furnace_data, techno_plant_data, techno_sail_consolidated tables
- Automatic calculation of plant consolidated and SAIL consolidated

---

## Step-by-Step Migration Process

### STEP 1: Extract Data from Your Excel Files

Your existing extractors return parameter rows. The converter recognizes furnaces from the "section" field.

**Your Excel files:**
```
- Report_format/monthly/BSP-3-page-TechMya'26.xlsx
- Report_format/monthly/BSPOISCO_MAY'25.xlsx
```

**The extractors return:**
```python
{
  'techno_param_rows': [
    {
      'group_code': 'IRON_MAKING',
      'section': 'Blast Furnaces (BSP)',  # ← Contains furnace reference
      'parameter': 'Coke Rate',
      'unit': 'Kg/THM',
      'actual': 425.5,
      ...
    },
    ...
  ]
}
```

### STEP 2: Create the JSON Conversion Tool

**File: `backend/excel_to_json_converter.py`** ✅ (Already created)

This tool:
1. Takes parameter rows from your extractor
2. Identifies furnace names from the "section" field
3. Groups parameters by furnace
4. Converts to JSON format
5. Inserts into new tables
6. Auto-calculates plant and SAIL consolidated

### STEP 3: Manual Conversion (For Testing)

If you want to test without running Python, here's what happens:

#### Example Input (From Excel Extractor):
```python
[
  {
    'group_code': 'IRON_MAKING',
    'section': 'Blast Furnaces, BF-4',     # <-- Furnace identified here
    'parameter': 'Coke Rate',
    'unit': 'Kg/THM',
    'actual': 425.5
  },
  {
    'group_code': 'IRON_MAKING',
    'section': 'Blast Furnaces, BF-4',
    'parameter': 'BF Productivity',
    'unit': 'T/m³/day',
    'actual': 2.15
  },
  {
    'group_code': 'IRON_MAKING',
    'section': 'Blast Furnaces, BF-6',     # <-- Different furnace
    'parameter': 'Coke Rate',
    'unit': 'Kg/THM',
    'actual': 430.2
  }
]
```

#### Converter Processing:
```
1. Group by furnace:
   BF-4:
     - Coke Rate: 425.5 Kg/THM
     - BF Productivity: 2.15 T/m³/day
   
   BF-6:
     - Coke Rate: 430.2 Kg/THM

2. Convert to JSON:
   {
     'BF-4': {
       'Coke Rate': {
         'value': 425.5,
         'unit': 'Kg/THM',
         'source': 'Excel'
       },
       'BF Productivity': {
         'value': 2.15,
         'unit': 'T/m³/day',
         'source': 'Excel'
       }
     },
     'BF-6': {
       'Coke Rate': {
         'value': 430.2,
         'unit': 'Kg/THM',
         'source': 'Excel'
       }
     }
   }

3. Insert to database (techno_furnace_data table)
```

### STEP 4: Complete Workflow

```mermaid
Excel File (BSP-3-page-TechMya'26.xlsx)
        ↓
[extract_preview(file, '2026-05')]
        ↓
Parameter Rows (list of dicts)
        ↓
[process_excel_extraction(plant='BSP', rows, '2026-05')]
        ↓
┌─ Identify furnaces from 'section' field
├─ Group parameters by furnace
├─ Convert to JSON format
├─ Insert to techno_furnace_data (10 records if 10 furnaces)
├─ Calculate plant consolidated (weighted average)
└─ Insert to techno_plant_data (1 record)
        ↓
Database Contains:
  - techno_furnace_data: {10 furnace records}
  - techno_plant_data: {1 plant record}
```

---

## Files Created

| File | Purpose | Status |
|------|---------|--------|
| `excel_to_json_converter.py` | Main converter tool | ✅ Created |
| `migrate_excel_to_json.py` | Migration script | ✅ Created |
| `simple_extraction_test.py` | Test script | ✅ Created |
| `pdf_extractor_bsp_furnace.py` | PDF extractor (future) | ✅ Created |

---

## How to Run Migration

### Option 1: Using the Migration Script
```bash
cd backend
python migrate_excel_to_json.py
```

This will:
1. Extract from both Excel files
2. Convert to JSON
3. Insert into database
4. Calculate plant and SAIL consolidated
5. Display results

### Option 2: Using the Converter Directly
```python
from excel_to_json_converter import process_excel_extraction

# After your extractor returns param_rows:
param_rows = [...] # from extract_preview()

furnaces_inserted, preview = process_excel_extraction(
    plant='BSP',
    parameter_rows=param_rows,
    report_month='2026-05',
    auto_calculate_plant=True,
    auto_calculate_sail=False
)

print(preview)  # Shows what was converted
```

### Option 3: Manual Step-by-Step
```python
from excel_extractor_bsp_techno import extract_preview
from excel_to_json_converter import ExcelToJsonConverter, JsonDataManager
from db import init_db

# 1. Initialize
init_db()

# 2. Extract
result = extract_preview('Report_format/monthly/BSP-3-page-TechMya\'26.xlsx', '2026-05')
param_rows = result['techno_param_rows']

# 3. Convert
converter = ExcelToJsonConverter('BSP')
param_row_objs = [
    ParameterRow(
        group_code=r.get('group_code'),
        section=r.get('section'),
        parameter=r.get('parameter'),
        unit=r.get('unit'),
        value=r.get('actual'),
        plant='BSP',
        month='2026-05'
    )
    for r in param_rows
]

furnace_data, preview = converter.convert_parameter_rows(param_row_objs, '2026-05')
print(preview)

# 4. Insert
manager = JsonDataManager()
count = manager.insert_furnace_data('BSP', furnace_data, '2026-05')
manager.calculate_and_insert_plant_consolidated('BSP', '2026-05')

print(f"Inserted {count} furnaces")
```

---

## Understanding the Converter

### Key Components

#### 1. Furnace Identification
The converter looks for furnace patterns in the `section` field:
```python
FURNACE_PATTERNS = {
    'BF-1': ['BF 1', 'BF-1', 'BF#1'],
    'BF-2': ['BF 2', 'BF-2', 'BF#2'],
    # ... etc for BF-4 through BF-8
}
```

**Your Excel sections might be:**
- "Blast Furnaces, BF-4" → Matches 'BF-4'
- "BF 4 Operations" → Matches 'BF-4'
- "Furnace 4" → Won't match (add to patterns)

**If your furnace section format is different:**
Edit `excel_to_json_converter.py` line 44-53:
```python
FURNACE_PATTERNS = {
    'BF-4': ['BF 4', 'BF-4', 'BF#4', 'BF 04', 'Furnace 4'],  # ← Add your pattern
    # ...
}
```

#### 2. Data Grouping
Groups all parameters for a furnace:
```python
furnace_data['BF-4']['Coke Rate'] = {
    'value': 425.5,
    'unit': 'Kg/THM',
    'source': 'Excel'
}
```

#### 3. Weighted Average Calculation
Plant consolidation uses HM Production as weight:
```
Plant Coke Rate = Σ(Furnace Coke × HM Production) / Σ(HM Production)

Example:
= (425.5×10000 + 430.2×11100 + ...) / (10000+11100+...)
= 427.3 Kg/THM
```

Fallback to simple average if HM Production missing.

---

## Data Flow Diagram

```
Existing System:
  Excel → Extract → Old Table (normalized)

New System:
  Excel → Extract → Converter → JSON Tables
                       ↓
                  [Furnace Data]
                       ↓
                  [Plant Consolidated]
                       ↓
                  [SAIL Consolidated]
                       ↓
                   API Endpoints
                       ↓
                  Dashboard/PDF
```

---

## Next Steps

### Phase 1 (Now) - Option A: Automated
```
1. ✅ Converter created (excel_to_json_converter.py)
2. ✅ Migration script created (migrate_excel_to_json.py)
3. TODO: Resolve Python environment dependencies
4. TODO: Run migration with your Excel files
5. TODO: Verify data in database
```

### Phase 2 (After Verification)
```
1. Update dashboard frontend
   - Change /api/techno-data → /api/techno-furnace-data
   - Change plant list → /api/techno-plant-data
   - Change SAIL view → /api/techno-sail-data

2. Update PDF report generation
   - Replace old query logic with:
     get_techno_plant_data('BSP', '2026-05')
     get_techno_sail_consolidated('2026-05')

3. Create extractors for remaining plants
   - DSP, RSP, BSL, ISP follow same pattern
```

### Phase 3 (Optional - PDF Extraction)
```
When libraries are available:
  1. Run pdf_extractor_bsp_furnace.py on flash-apr26.pdf
  2. Extract page 14 furnace data
  3. Insert via same converter
```

---

## Troubleshooting

### Issue: "Could not match parameter"
**Symptom:** Some parameters not converted

**Solution:** 
The converter couldn't match your parameter names to known ones. Edit `PARAM_UNITS` in converter or Excel extractor output.

### Issue: "No furnaces identified"
**Symptom:** All data grouped under None furnace

**Solution:**
Your section format doesn't match furnace patterns. Update `FURNACE_PATTERNS` in converter.

**Example:**
If your sections are "BF4 Coke" instead of "BF-4", add:
```python
'BF-4': ['BF 4', 'BF-4', 'BF#4', 'BF4'],  # Added 'BF4'
```

### Issue: "HM Production not found"
**Symptom:** Plant consolidated shows simple average instead of weighted average

**Solution:**
Add HM Production parameter to your extractor, or it will be looked up from production_table automatically.

---

## Key Files Reference

| File | Function | Location |
|------|----------|----------|
| extract_preview() | Extracts parameters | `excel_extractors/excel_extractor_bsp_techno.py` |
| process_excel_extraction() | Main conversion | `excel_to_json_converter.py` |
| ExcelToJsonConverter | Parser/converter | `excel_to_json_converter.py` |
| JsonDataManager | Database inserter | `excel_to_json_converter.py` |
| insert_techno_furnace_data() | DB insert | `db.py` |
| TechnoPlantCalculator | Plant calc | `techno_json_utils.py` |
| TechnoSAILCalculator | SAIL calc | `techno_json_utils.py` |

---

## API Endpoints After Migration

Once data is in the database, these endpoints become available:

```bash
# Get furnace-wise data
curl "http://localhost:8000/api/techno-furnace-data?plant=BSP&report_month=2026-05"

# Get plant consolidated
curl "http://localhost:8000/api/techno-plant-data?plant=BSP&report_month=2026-05"

# Get SAIL consolidated
curl "http://localhost:8000/api/techno-sail-data?report_month=2026-05"
```

---

## Summary

✅ **Infrastructure Created:**
- Excel to JSON converter
- Migration scripts
- Database functions
- API endpoints

**To Complete Migration:**
1. Resolve Python dependencies (openpyxl, xlrd, pdfplumber)
2. Run migration script OR manually call converter
3. Verify data in database
4. Update dashboard to use new endpoints

**Estimated Time:** 30-60 minutes of execution

**Current Blocker:** Python environment setup for Excel/PDF libraries

Would you like help with:
- A) Setting up Python environment properly?
- B) Manual SQL insertion if you prefer to skip extraction?
- C) Testing with simulated data first?

