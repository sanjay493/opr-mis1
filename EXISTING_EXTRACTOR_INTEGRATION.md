# Existing Extractor Integration Guide

## 🎯 Overview

Your existing extractors now work with the **new JSON DB architecture**!

**What changed:**
- ✅ Your extractors still work (no changes needed!)
- ✅ Output automatically converts to new JSON structure
- ✅ Data inserts into `techno_furnace_data` table
- ✅ Plant consolidated auto-calculated
- ✅ Parameter names normalized automatically

---

## 🚀 How It Works

```
Your Existing Extractor          Unified Adapter              New DB
─────────────────────            ───────────────              ──────
extract_oisco_real.py
  ↓
excel_extractor_bsp_oisco.py     unified_extractor_adapter.py
  ↓ extract_preview()             ↓ _convert_to_json()
Parameter rows dict         →     Furnace data dict    →    techno_furnace_data
  ↓                               ↓                          ↓
  • parameter: "BF-4 CDI"    →   "CDI" (normalized)   →    value: 118.08
  • value: 118.08           →   furnace: "BF-4"       →    source: "Excel-Extracted"
  • unit: "Kg/THM"          →   unit: "Kg/THM"        →

Then: Plant consolidated auto-calculated!
```

---

## 📝 Integration Layers

### **Layer 1: Your Existing Extractors** (UNCHANGED)
```python
# Your original code - works as-is!
from excel_extractor_bsp_oisco import extract_preview

result = extract_preview('file.xlsx', '2025-05')
param_rows = result['techno_param_rows']  # List of parameter dicts
```

### **Layer 2: Unified Adapter** (NEW)
```python
# New adapter wraps your extractor
from unified_extractor_adapter import ExtractorAdapter

adapter = ExtractorAdapter('BSP', 'oisco')
furnace_data, preview = adapter.extract_and_convert(
    'file.xlsx', '2025-05'
)
```

### **Layer 3: New DB** (NEW)
```python
# New JSON structure
techno_furnace_data:
  plant: "BSP"
  furnace: "BF-4"
  report_month: "2025-05"
  data: {
    "CDI": {"value": 118.08, "unit": "Kg/THM", ...},
    "Coke Rate": {...}
  }
```

---

## ✅ Using With Your Extractors

### **BSP OISCO Data**

```bash
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe run_bsp_oisco_extraction.py
```

**What happens:**
1. ✓ Finds BSPOISCO_MAY'25.xlsx
2. ✓ Calls excel_extractor_bsp_oisco.extract_preview()
3. ✓ Converts output to new JSON structure
4. ✓ Inserts into techno_furnace_data
5. ✓ Calculates plant_consolidated

**Output:**
```
================================================================================
BSP OISCO DATA EXTRACTION
================================================================================

Extraction: OISCO

[STEP 1] Calling existing extractor...
  File: BSPOISCO_MAY'25.xlsx
  Month: 2025-05
  ✓ Extracted 37 parameters

[STEP 2] Converting to JSON format...
  ✓ Converted 37 parameters
  ✓ 4 furnaces with data

...

INSERTING DATA INTO DATABASE
✓ BF-4: 1 parameters
✓ BF-6: 1 parameters
✓ BF-7: 0 parameters
✓ BF-8: 0 parameters

✓ Successfully inserted 4 furnaces
```

### **BSP TechnoMya Data**

```bash
C:\Users\sanja\anaconda3\python.exe run_bsp_techno_extraction.py
```

Same workflow, different source file!

---

## 🔄 Unified Command (Any Extractor)

```bash
python unified_extractor_adapter.py <PLANT> <TYPE> <FILE> [--month YYYY-MM]
```

### **Examples:**

```bash
# BSP OISCO
python unified_extractor_adapter.py BSP oisco Report_format/Monthly/BSPOISCO_MAY\'25.xlsx --month 2025-05

# BSP Techno
python unified_extractor_adapter.py BSP techno Report_format/Monthly/BSP-3-page-TechMay\'26.xlsx --month 2026-05

# DSP (if extractor exists)
python unified_extractor_adapter.py DSP rsp Report_format/Monthly/DSP-rsp-file.xlsx --month 2026-05

# RSP (if extractor exists)
python unified_extractor_adapter.py RSP rsp Report_format/Monthly/RSP-rsp-file.xlsx --month 2026-05
```

---

## 🛠️ What The Adapter Does

### **1. Loads Your Extractor**
```python
from excel_extractor_bsp_oisco import extract_preview
result = extract_preview(excel_file, report_month)
param_rows = result['techno_param_rows']
```

### **2. Converts Parameter Format**
```python
# Your extractor output:
{
  'parameter': 'BF-4 CDI',
  'value': 118.08,
  'unit': 'Kg/THM',
  'section': 'Blast Furnaces',
  ...
}

# ↓ Converted to:

# For furnace BF-4:
{
  'CDI': {
    'value': 118.08,
    'unit': 'Kg/THM',
    'source': 'Excel-Extracted',
    'section': 'Blast Furnaces'
  }
}
```

### **3. Identifies Furnaces**
- Looks for furnace patterns: "BF-4", "BF 4", "BF#4"
- Maps parameters to correct furnace
- Groups by furnace automatically

### **4. Normalizes Parameter Names**
- Removes furnace prefixes
- Maps to universal naming (e.g., "BF Coke" → "Coke Rate")
- Consistent across all plants

### **5. Inserts into New DB**
```python
insert_techno_furnace_data(
  plant='BSP',
  furnace='BF-4',
  report_month='2025-05',
  data={'CDI': {'value': 118.08, ...}}
)
```

### **6. Auto-Calculates Plant Consolidated**
```python
calc = TechnoPlantCalculator()
plant_data = calc.calculate_plant_consolidated('BSP', '2025-05')
# Weighted averages from furnace data
```

---

## 📊 Full Data Flow

```
Source Excel File
  ↓
Your Existing Extractor (extract_preview)
  ↓ param_rows list
Unified Adapter
  ├─ Identify furnaces
  ├─ Normalize parameters
  └─ Group by furnace
    ↓ furnace_data dict
Insert Pipeline
  ├─ Insert furnace data
  ├─ Calculate plant consolidated
  └─ Log results
    ↓
techno_furnace_data table (new JSON structure!)
techno_plant_data table (auto-calculated!)
```

---

## ✨ Key Benefits

✅ **No changes to existing extractors** - Your code stays the same!  
✅ **Automatic parameter normalization** - Consistent names  
✅ **Automatic furnace identification** - Smart detection  
✅ **Automatic plant calculations** - Weighted averages  
✅ **Clear error messages** - Easy debugging  
✅ **Logging** - Track all operations  

---

## 🎯 Quick Start

### **1. Run OISCO Extraction**
```bash
cd d:\opr-mis1\backend
python run_bsp_oisco_extraction.py
```

### **2. Run Techno Extraction**
```bash
python run_bsp_techno_extraction.py
```

### **3. Verify in Dashboard**
```
http://localhost:8000/dashboard
Select: Plant, Month, View
See: Your extracted data!
```

---

## 🔧 Creating Extractors for Other Plants

If you have extractors for DSP, RSP, BSL, ISP:

**Step 1: Create extractor file**
```python
# backend/excel_extractors/excel_extractor_dsp_rsp.py

def extract_preview(excel_file, report_month):
    # Your extraction logic
    return {
        'techno_param_rows': [
            {'parameter': 'CDI', 'value': 120.5, 'unit': 'Kg/THM', ...},
            ...
        ]
    }
```

**Step 2: Create run script**
```bash
# backend/run_dsp_rsp_extraction.py

from unified_extractor_adapter import extract_and_insert

extract_and_insert('DSP', 'rsp', 'Report_format/Monthly/DSP-file.xlsx', '2026-05')
```

**Step 3: Run**
```bash
python run_dsp_rsp_extraction.py
```

That's it! The adapter handles everything else!

---

## 📋 Adapter Features

| Feature | Description |
|---------|-------------|
| Auto-furnace detection | Identifies BF-1 through BF-8 |
| Parameter normalization | Maps to universal names |
| Null filtering | Skips empty values |
| Unit preservation | Keeps original units |
| Source tracking | Records "Excel-Extracted" source |
| Preview generation | Shows what will be inserted |
| Error handling | Clear error messages |
| Logging | Full operation logs |

---

## 🚀 Advanced Usage

### **Extract Multiple Files**
```python
from unified_extractor_adapter import extract_and_insert

for excel_file in ['file1.xlsx', 'file2.xlsx', 'file3.xlsx']:
    extract_and_insert('BSP', 'oisco', excel_file, '2025-05')
```

### **Auto-Insert Without Confirmation**
```bash
python unified_extractor_adapter.py BSP oisco file.xlsx --auto-insert
```

### **Custom Month**
```bash
python run_bsp_oisco_extraction.py  # Uses hardcoded 2025-05
# Or edit the script to change REPORT_MONTH variable
```

---

## 📞 Troubleshooting

### Error: "Could not load extractor"
**Problem:** Extractor module not found

**Solution:**
1. Check file exists: `backend/excel_extractors/excel_extractor_bsp_oisco.py`
2. Verify function name: `extract_preview()`
3. Update EXTRACTORS mapping in adapter if needed

### Error: "No furnaces detected"
**Problem:** Furnace names not recognized

**Solution:**
1. Check parameter names in Excel
2. Add new furnace pattern to `_identify_furnace()`
3. Check section names contain furnace references

### Error: "No parameters with values"
**Problem:** All extracted values are None/null

**Solution:**
1. Check Excel file has actual data
2. Verify extractor is reading correct cells
3. Check cell format (should be numbers, not text)

---

## 📝 Complete Example

```python
#!/usr/bin/env python3

import sys
sys.path.insert(0, 'excel_extractors')

from unified_extractor_adapter import extract_and_insert

# Extract BSP OISCO data
print("Extracting BSP OISCO...")
success = extract_and_insert(
    plant='BSP',
    extractor_type='oisco',
    excel_file='Report_format/Monthly/BSPOISCO_MAY\'25.xlsx',
    report_month='2025-05',
    auto_insert=False  # Ask for confirmation
)

if success:
    print("✓ Extraction complete!")
    print("Check dashboard: http://localhost:8000/dashboard")
else:
    print("✗ Extraction failed")
```

---

**Your existing extractors now power the new JSON architecture!** 🚀

