# Cell Mapping - Quick Start

## 🚀 The Process (4 Steps)

### **Step 1: Find Cell Locations in Excel** 📍
```
Open: Report_format/Monthly/BSP-3-page-TechMay'26.xlsx

Look for your parameters and note the cell:
  Coke Rate value is in cell: B3
  BF Productivity value is in cell: B4
  CDI value is in cell: B5
```

### **Step 2: Create Mapping File** 📝
```
Create: backend/bsp_techno_mapping.json

{
  "file": "Report_format/Monthly/BSP-3-page-TechMay'26.xlsx",
  "sheet_name": "Sheet1",
  "plant": "BSP",
  "report_month": "2026-05",
  "mappings": [
    {"parameter": "Coke Rate", "cell": "B3", "unit": "Kg/THM", "furnace": null},
    {"parameter": "BF Productivity", "cell": "B4", "unit": "T/m³/day", "furnace": null},
    {"parameter": "CDI", "cell": "B5", "unit": "Kg/THM", "furnace": null}
  ]
}
```

### **Step 3: Extract & Preview** ✅
```bash
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe extract_and_insert.py bsp_techno_mapping.json --preview-only
```

**Output shows:**
```
Plant: BSP
Month: 2026-05

  Coke Rate                  =       430.20 Kg/THM
  BF Productivity            =         2.12 T/m³/day
  CDI                        =       118.08 Kg/THM
```

### **Step 4: Insert into Database** 🗄️
```bash
C:\Users\sanja\anaconda3\python.exe extract_and_insert.py bsp_techno_mapping.json
```

When prompted: Type **`yes`** to confirm insertion

---

## 📊 What Gets Extracted

| From Excel | Maps To | Stored In Database |
|-----------|---------|-------------------|
| Cell B3 (430.2) | Coke Rate | techno_furnace_data |
| Cell B4 (2.12) | BF Productivity | techno_furnace_data |
| Cell B5 (118.08) | CDI | techno_furnace_data |

Then **plant_consolidated** is auto-calculated!

---

## 🔄 For Multiple Months

Same mapping file works for multiple months:

```json
{
  "from_month": "2026-05",
  "till_month": "2026-12",
  "mappings": [...]
}
```

Extracts all 12 months automatically!

---

## ⚡ Common Cell Patterns

### **Excel has header row:**
```
     A                  B
1    Parameter          Value
2    Coke Rate          430.2      ← cell is B2
3    BF Productivity    2.12       ← cell is B3
```

### **Excel has multiple columns (one per month):**
```
     A                  B          C              D
1    Parameter          May-26     Jun-26         Jul-26
2    Coke Rate          430.2      431.5          432.1
```

May-26 mapping:
```json
{"parameter": "Coke Rate", "cell": "B2", ...}
```

Jun-26 needs different cell:
```json
{"parameter": "Coke Rate", "cell": "C2", ...}
```

---

## 💾 Mapping Template

To create template:
```bash
C:\Users\sanja\anaconda3\python.exe excel_cell_mapper.py create-template bsp_mapping.json
```

Opens template to edit!

---

## ✔️ Verify It Works

After insertion, check dashboard:
```
URL: http://localhost:8000/dashboard

Select:
- Plant: BSP
- Month: 2026-05
- View: Plant Consolidated

Should see your extracted values!
```

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| Cell not found | Click cell in Excel → check Name Box (top-left) → copy exact reference |
| Invalid value | Check cell contains number, not text |
| Wrong month extracted | Verify cell references match the correct month column |
| Data not in dashboard | Reload page (Ctrl+F5) → check month selection |

---

## 📁 Files You Need

```
backend/
├── excel_cell_mapper.py         ✓ (Already created)
├── extract_and_insert.py         ✓ (Already created)
└── bsp_techno_mapping.json       ← You create this!
```

---

## 🎯 Next Actions

1. **Open Excel file:** BSP-3-page-TechMay'26.xlsx
2. **Find cell locations** for your parameters
3. **Create mapping file** with those cell references
4. **Run extraction** with `--preview-only` first
5. **Verify output** looks correct
6. **Run insertion** without `--preview-only`

**That's it!** 🚀

---

## 📞 Example Commands

```bash
# Create template to get started
python excel_cell_mapper.py create-template bsp_mapping.json

# Preview extraction (no database changes)
python extract_and_insert.py bsp_mapping.json --preview-only

# Actually insert into database
python extract_and_insert.py bsp_mapping.json
```

---

**Ready? Start by finding those cell locations in Excel!** 📍

