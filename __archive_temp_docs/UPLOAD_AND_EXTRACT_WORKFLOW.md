# Upload & Extract Workflow

## 🎯 Simple Workflow

```
Step 1: Upload via Port 3000 (old system)
Step 2: Run Python extraction script
Step 3: Data auto-inserts into NEW JSON tables ✓
```

---

## 📋 Complete Steps

### **Step 1: Upload File**
```
Open: http://localhost:3000/upload
Upload your Excel file
(Same as before!)
```

### **Step 2: Run Extraction Script**
```bash
cd d:\opr-mis1\backend
python extract_from_upload.py <file_path> <plant> <extractor_type> <month>
```

### **Step 3: Done!** ✓
Data automatically in JSON tables

---

## 💻 Command Examples

### **OISCO Data**
```bash
python extract_from_upload.py "Report_format/Monthly/BSPOISCO_MAY'25.xlsx" BSP oisco 2025-05
```

### **Techno Data**
```bash
python extract_from_upload.py "Report_format/Monthly/BSP-3-page-TechMay'26.xlsx" BSP techno 2026-05
```

### **DSP RSP Data**
```bash
python extract_from_upload.py "uploads/DSP-rsp-file.xlsx" DSP rsp 2026-05
```

---

## 🔧 Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| file_path | Path to uploaded file | "uploads/file.xlsx" or "Report_format/Monthly/file.xlsx" |
| plant | Plant code | BSP, DSP, RSP, BSL, ISP |
| extractor_type | Type of data | oisco, techno, rsp |
| month | Report month | 2025-05, 2026-05 (YYYY-MM format) |

---

## ✅ What Happens

```
Run Script
  ↓
Validates file exists
  ↓
Loads extractor
  ↓
Extracts parameters
  ↓
Separates furnace vs plant data
  ↓
Smart handling:
  ├─ Plant data in source? → Use directly
  └─ Plant data not in source? → Auto-calculate
  ↓
Inserts into JSON tables:
  ├─ techno_furnace_data
  └─ techno_plant_data
  ↓
Shows success/failure
```

---

## 🚀 Typical Workflow

```bash
# 1. Upload file via browser
# http://localhost:3000/upload
# Upload: BSPOISCO_MAY'25.xlsx

# 2. Extract via command line
cd d:\opr-mis1\backend
python extract_from_upload.py "Report_format/Monthly/BSPOISCO_MAY'25.xlsx" BSP oisco 2025-05

# 3. Check results
# Open: http://localhost:8000/dashboard
# Select: Plant=BSP, Month=2025-05
# → See your data! ✓
```

---

## 📊 Output Example

```
================================================================================
EXTRACT FROM UPLOADED FILE
================================================================================

File: BSPOISCO_MAY'25.xlsx
Plant: BSP
Extractor: oisco
Month: 2025-05
✓ Loaded extractor: excel_extractor_bsp_oisco

================================================================================
SMART EXTRACTION - BSP
================================================================================

✓ Extracted 37 parameters

Separating data:
  ✓ Furnace data: 2 parameters
  ✓ Plant data in source: 1 parameters

Preview:
  BF-4: 1 parameters
  BF-6: 1 parameters
  [Plant-level data from source]: 1 parameters

================================================================================
INSERTING DATA
================================================================================

  ✓ BF-4: 1 parameters
  ✓ BF-6: 1 parameters

Plant consolidated:
  ✓ Using data from source: 1 parameters
  ✓ Inserted

================================================================================
INSERTION RESULTS
================================================================================

✓ SUCCESS
  Furnaces inserted: 2
  Plant consolidated: from source

✓ Extraction complete!

Data inserted into JSON tables:
  ✓ techno_furnace_data
  ✓ techno_plant_data

Verify in dashboard: http://localhost:8000/dashboard
```

---

## 🎯 Supported Combinations

| Plant | OISCO | TechnoMya | RSP |
|-------|-------|-----------|-----|
| BSP   | ✓     | ✓         | -   |
| DSP   | -     | -         | ✓   |
| RSP   | -     | -         | ✓   |
| BSL   | -     | -         | ✓   |
| ISP   | -     | -         | ✓   |

---

## ✨ Key Features

✅ Simple command-line interface  
✅ Works with your existing upload system (port 3000)  
✅ Auto-extracts and inserts  
✅ Smart plant data handling  
✅ Clear success/failure messages  
✅ Shows extracted data summary  

---

## 🛠️ Troubleshooting

### Error: "File not found"
**Fix:** Check file path is correct
```bash
# Correct:
python extract_from_upload.py "Report_format/Monthly/file.xlsx" BSP oisco 2025-05

# Wrong:
python extract_from_upload.py "Report_format/monthly/file.xlsx" BSP oisco 2025-05  # lowercase 'monthly'
```

### Error: "Could not load extractor"
**Fix:** Check plant and extractor_type are correct
```bash
# Check supported combinations in table above
python extract_from_upload.py "file.xlsx" BSP techno 2025-05  # ✓ Correct
python extract_from_upload.py "file.xlsx" DSP techno 2025-05  # ✗ DSP doesn't support techno
```

### Error: "No parameters extracted"
**Fix:** Check Excel file has correct data structure

### Data not in dashboard
**Fix:**
1. Verify script showed "SUCCESS"
2. Open dashboard: http://localhost:8000/dashboard
3. Select correct Plant and Month
4. Reload page (Ctrl+F5)

---

## 📝 Script Location

```
d:\opr-mis1\backend\extract_from_upload.py
```

Keep this script handy for extraction!

---

## 🎉 Done!

Your workflow is complete:
1. ✓ Upload via port 3000 (same as before)
2. ✓ Extract via Python script (simple command)
3. ✓ Data in JSON tables (automatic)
4. ✓ Verify in dashboard (easy check)

**Simple, familiar, and powerful!** 🚀

