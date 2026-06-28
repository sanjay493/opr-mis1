# New Tables Only - Simple Guide

## 🎯 Your Setup

```
OLD Tables          → ❌ IGNORE (deprecated)
NEW JSON Tables     → ✅ USE (current)
```

**That's it!** Clean and simple.

---

## 🚀 How It Works

Your existing extractors automatically insert into **NEW JSON tables only**:

```
Excel File (OISCO or TechnoMya)
  ↓
Your Existing Extractor
  (excel_extractor_bsp_oisco.py or excel_extractor_bsp_techno.py)
  ↓
Unified Adapter
  (unified_extractor_adapter.py)
  • Converts to JSON format
  • Normalizes parameter names
  • Identifies furnaces
  ↓
techno_furnace_data table (NEW JSON)
  ↓
Auto-calculates
techno_plant_data table
```

---

## 📋 Two Simple Scripts

### **1. Extract OISCO Data**
```bash
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe run_bsp_oisco_extraction.py
```

**Inserts into:** `techno_furnace_data` (NEW JSON)

### **2. Extract Techno Data**
```bash
C:\Users\sanja\anaconda3\python.exe run_bsp_techno_extraction.py
```

**Inserts into:** `techno_furnace_data` (NEW JSON)

---

## ✨ What Happens Automatically

✅ Loads your extractor  
✅ Converts to new JSON format  
✅ Identifies furnaces (BF-1 through BF-8)  
✅ Normalizes parameter names (universal naming)  
✅ Inserts into `techno_furnace_data`  
✅ **Smart plant consolidated handling:**
   - **If plant data in Excel** → Uses it directly ✓
   - **If plant data NOT in Excel** → Auto-calculates from furnaces ✓
✅ Shows preview before inserting  
✅ Logs everything  

**No old tables involved!**

---

## 📊 Database Structure

### **NEW Tables (You Use These)**

```
techno_furnace_data
├── plant: "BSP"
├── furnace: "BF-4"
├── report_month: "2025-05"
└── data: {
    "CDI": {
      "value": 118.08,
      "unit": "Kg/THM",
      "source": "Excel-Extracted"
    },
    "Coke Rate": {...},
    ...
  }

techno_plant_data
├── plant: "BSP"
├── report_month: "2025-05"
└── data: {
    "CDI": {
      "value": 118.08,
      "unit": "Kg/THM",
      "source": "calculated"
    },
    ...
  }
```

### **OLD Tables (Ignore)**
- All the old normalized tables stay as-is
- They're not used or updated
- You can delete them later if needed

---

## 🔄 Workflow

### **Step 1: Extract**
```bash
python run_bsp_oisco_extraction.py
# or
python run_bsp_techno_extraction.py
```

### **Step 2: Confirm**
When prompted:
```
Insert this data into database? (yes/no): yes
```

### **Step 3: Done!**
Data is in `techno_furnace_data` table ✅

---

## ✅ Verify in Dashboard

Open: **http://localhost:8000/dashboard**

Select:
- **Plant:** BSP
- **Month:** 2025-05 (OISCO) or 2026-05 (Techno)
- **View:** Furnace Data or Plant Consolidated

You'll see your extracted data! 🎉

---

## 🎯 For All Plants

Once you have extractors for DSP, RSP, BSL, ISP:

```bash
# Any plant, any extractor type
python unified_extractor_adapter.py <PLANT> <TYPE> <FILE> --month <YYYY-MM>
```

Examples:
```bash
python unified_extractor_adapter.py BSP oisco Report_format/Monthly/BSPOISCO_MAY\'25.xlsx --month 2025-05
python unified_extractor_adapter.py BSP techno Report_format/Monthly/BSP-3-page-TechMay\'26.xlsx --month 2026-05
python unified_extractor_adapter.py DSP rsp Report_format/Monthly/DSP-file.xlsx --month 2026-05
```

---

## 📁 Files You Have

```
backend/
├── run_bsp_oisco_extraction.py          ← Use this
├── run_bsp_techno_extraction.py         ← Use this
├── unified_extractor_adapter.py         ← Powers both
├── excel_extractors/
│   ├── excel_extractor_bsp_oisco.py     ← Your existing
│   └── excel_extractor_bsp_techno.py    ← Your existing
├── db.py                                 ← New tables
├── techno_json_utils.py                  ← Plant calc
└── parameter_naming.py                   ← Normalization
```

**All set up. Just run and extract!** 🚀

---

## 🛠️ What If Something Goes Wrong?

### Error: "File not found"
- Check Excel file exists
- Verify path in script

### Error: "No parameters extracted"
- Check Excel file has data
- Verify extractor works

### Data not appearing in dashboard
- Reload dashboard (Ctrl+F5)
- Check month and plant selection
- Check database connection

---

## 📝 Summary

**You extract → data goes to NEW JSON tables → done!**

- ✅ Simple
- ✅ Clean
- ✅ No old tables involved
- ✅ Easy to understand
- ✅ Future-proof

**Just run the scripts and extract!** 🎉

---

## 🚀 Quick Start

```bash
# 1. Extract OISCO
cd d:\opr-mis1\backend
python run_bsp_oisco_extraction.py
# Type: yes
# Done! ✓

# 2. Extract Techno
python run_bsp_techno_extraction.py
# Type: yes
# Done! ✓

# 3. Verify
# Open: http://localhost:8000/dashboard
# Select plant and month
# See your data! 🎉
```

**That's all you need!** 🚀

