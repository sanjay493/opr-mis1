# Excel Cell Mapping Guide

## 🎯 Overview

Instead of manually entering parameters, you **map Excel cells** to parameters:
- **Step 1:** Open Excel file and find cell locations (e.g., "B5" = Coke Rate)
- **Step 2:** Create JSON mapping file with cell locations
- **Step 3:** Run extraction script - automatically pulls from those cells
- **Step 4:** Extract data for multiple months automatically

**Result:** Automatic, accurate extraction for any date range!

---

## 📝 Step 1: Find Cell Locations in Excel

Open: **BSP-3-page-TechMay'26.xlsx**

### Example Layout:
```
     A                    B          C              D
1    Parameter Name       May-26     Jun-26         Jul-26
2    ─────────────────    ──────     ──────         ──────
3    Coke Rate (Kg/THM)   430.2      431.5          432.1
4    BF Productivity      2.12       2.15           2.18
5    CDI (Kg/THM)         118.08     118.5          119.2
```

**You identify:**
- Coke Rate = Cell **B3** (value 430.2 in May-26 column)
- BF Productivity = Cell **B4** (value 2.12)
- CDI = Cell **B5** (value 118.08)

**For other months:**
- Jun-26 values in Column C
- Jul-26 values in Column D

---

## 📋 Step 2: Create Mapping File

Create file: `backend/bsp_techno_mapping.json`

```json
{
  "file": "Report_format/Monthly/BSP-3-page-TechMay'26.xlsx",
  "sheet_name": "Sheet1",
  "plant": "BSP",
  "report_month": "2026-05",
  "from_month": "2026-05",
  "till_month": "2026-05",
  "notes": "Cell mappings for BSP Techno data extraction",
  "mappings": [
    {
      "parameter": "Coke Rate",
      "cell": "B3",
      "unit": "Kg/THM",
      "furnace": null,
      "notes": "Plant-level coke rate"
    },
    {
      "parameter": "BF Productivity",
      "cell": "B4",
      "unit": "T/m³/day",
      "furnace": null,
      "notes": "Plant-level BF productivity"
    },
    {
      "parameter": "CDI",
      "cell": "B5",
      "unit": "Kg/THM",
      "furnace": null,
      "notes": "Plant-level CDI"
    }
  ]
}
```

### Mapping Fields:

| Field | Description |
|-------|-------------|
| `file` | Path to Excel file |
| `sheet_name` | Which sheet to read (default: "Sheet1") |
| `plant` | Plant code (BSP, DSP, etc.) |
| `report_month` | Initial month (YYYY-MM format) |
| `from_month` | Start month for extraction |
| `till_month` | End month for extraction |
| `mappings` | Array of cell-to-parameter mappings |

### Mapping Entry Fields:

| Field | Description |
|-------|-------------|
| `parameter` | Parameter name (Coke Rate, BF Productivity, etc.) |
| `cell` | Excel cell location (B3, C5, D10, etc.) |
| `unit` | Measurement unit (Kg/THM, T/m³/day, %, etc.) |
| `furnace` | Furnace ID if furnace-specific (BF-1, BF-2, null for plant-level) |
| `notes` | Optional description |

---

## 🚀 Step 3: Run Extraction

### Create Template (First Time Only):
```bash
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe excel_cell_mapper.py create-template bsp_techno_mapping.json
```

Creates template you can edit.

### Extract Data:
```bash
C:\Users\sanja\anaconda3\python.exe excel_cell_mapper.py extract bsp_techno_mapping.json
```

**Output:**
```
================================================================================
EXCEL CELL MAPPING EXTRACTOR
================================================================================

Configuration:
  Plant: BSP
  File: Report_format/Monthly/BSP-3-page-TechMay'26.xlsx
  Sheet: Sheet1
  Mappings: 3 parameters

Month: 2026-05
  ✓ Coke Rate (B3): 430.2
  ✓ BF Productivity (B4): 2.12
  ✓ CDI (B5): 118.08

================================================================================
EXTRACTED DATA
================================================================================
  BF Productivity: 2.12
  CDI: 118.08
  Coke Rate: 430.2
```

---

## 📊 Multiple Months Extraction

For extracting **May to Dec 2026**:

```json
{
  "from_month": "2026-05",
  "till_month": "2026-12",
  "mappings": [
    {
      "parameter": "Coke Rate",
      "cell_base": "B",  // Column B for May, C for Jun, etc.
      "row": 3
    }
  ]
}
```

---

## 🔍 Finding Cell Locations - Tips

### **Method 1: Excel Column Headers**
```
Open file in Excel → Look at column headers → Note the column letter
Example: If "May 2026" data is in Column B, then B3 = first parameter in that column
```

### **Method 2: Click Cell → See Reference**
```
Excel shows cell reference in Name Box (top left)
Click on value → See "B3", "C5", etc. in Name Box
```

### **Method 3: Multiple Sheets**
```
If data is on different sheets:
{
  "sheet_name": "May 2026",
  "mappings": [{"parameter": "Coke Rate", "cell": "B3", ...}]
}
```

### **Method 4: Furnace-Specific Data**
```
If each furnace is separate:
{
  "parameter": "Coke Rate",
  "cell": "B3",
  "furnace": "BF-1"
}
```

---

## ✅ Validation Checklist

Before running extraction:

- [ ] Excel file path is correct
- [ ] Sheet name matches actual sheet
- [ ] Cell references are valid (e.g., "B3", not "B03")
- [ ] All parameters have units specified
- [ ] from_month and till_month are in YYYY-MM format
- [ ] file exists and is readable

---

## 🛠️ Troubleshooting

### Error: "Cell not found"
**Problem:** Invalid cell reference

**Solution:**
1. Open Excel file
2. Click on the value you want
3. Check the cell reference in Name Box (top-left)
4. Copy exact reference to mapping file
5. Re-run extraction

### Error: "Invalid value"
**Problem:** Cell contains text, not a number

**Solution:**
1. Check Excel cell contains numeric value
2. Verify it's not a formula result that's text
3. Update cell reference to correct cell
4. Re-run

### Missing months
**Problem:** Extraction doesn't extract all months

**Solution:**
1. Verify `from_month` and `till_month` are correct
2. Check date range doesn't span multiple Excel files
3. For multi-file extraction, may need separate mappings per file

---

## 📂 File Structure

```
backend/
├── excel_cell_mapper.py          # Main extraction script
├── bsp_techno_mapping.json       # Your cell mappings
├── dsp_techno_mapping.json       # (For DSP plant)
├── rsp_techno_mapping.json       # (For RSP plant)
└── ...
```

---

## 🎯 Complete Workflow Example

```bash
# 1. Create template
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe excel_cell_mapper.py create-template bsp_mapping.json

# 2. Open bsp_mapping.json in text editor
# 3. Find Excel cell locations in BSP-3-page-TechMay'26.xlsx
# 4. Update cell references in JSON
# Example:
#   - B3: Coke Rate → "cell": "B3"
#   - B4: BF Productivity → "cell": "B4"
#   - B5: CDI → "cell": "B5"

# 5. Save mapping file

# 6. Extract data
C:\Users\sanja\anaconda3\python.exe excel_cell_mapper.py extract bsp_mapping.json

# 7. Verify output shows correct values
```

---

## 💡 Advanced Usage

### **Extract for Month Range**
```json
{
  "from_month": "2026-01",
  "till_month": "2026-12",
  "mappings": [...]
}
```

Automatically extracts all 12 months (same cell locations).

### **Furnace-Specific Data**
```json
{
  "parameter": "Coke Rate",
  "cell": "B3",
  "furnace": "BF-4"
}
```

### **Multiple Parameters**
```json
{
  "mappings": [
    {"parameter": "Coke Rate", "cell": "B3", "unit": "Kg/THM"},
    {"parameter": "BF Productivity", "cell": "B4", "unit": "T/m³/day"},
    {"parameter": "CDI", "cell": "B5", "unit": "Kg/THM"},
    {"parameter": "Slag Rate", "cell": "B6", "unit": "Kg/THM"},
    ...
  ]
}
```

---

## 📞 Support

If you encounter issues:
1. **Check cell references** - Make sure they exist in Excel
2. **Verify file path** - Must be exact path to .xlsx file
3. **Check sheet name** - Must match actual sheet name
4. **Validate JSON** - Use online JSON validator

All scripts provide clear error messages!

---

**Ready to start? Open your Excel file and find those cell locations!** 📍

