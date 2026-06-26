# File Upload Guide - Auto-Populate JSON Tables

## 🚀 How It Works

```
Upload Excel File
  ↓
Select Plant & Extractor Type
  ↓
Auto-Extract Data
  ↓
Auto-Populate JSON Tables
  ↓
Done! ✓
```

---

## 📱 Upload Page

Open in your browser:
```
http://localhost:8000/upload
```

---

## 📋 Upload Steps

### **Step 1: Select Plant**
```
BSP (Bhilai)
DSP (Durgapur)
RSP (Rourkela)
BSL (Bokaro)
ISP (Iisco)
```

### **Step 2: Select Extractor Type**
```
OISCO   (Integrated Steel Plant data)
TechnoMya (Technical/Production data)
RSP     (RSP-specific format)
```

### **Step 3: Choose Month**
```
Use the month picker
Or type: YYYY-MM format
Example: 2025-05 (May 2025)
```

### **Step 4: Upload File**
```
Click to upload
OR
Drag and drop Excel file
```

### **Step 5: Submit**
```
Click "Upload & Extract"
System auto-extracts and inserts data
Shows progress and results
```

---

## ✅ What Happens

```
1. Validates inputs
2. Saves file temporarily
3. Loads appropriate extractor
4. Extracts parameters from Excel
5. Separates furnace vs plant data
6. Checks if plant data in source
   - YES: uses it directly ✓
   - NO: auto-calculates from furnaces ✓
7. Inserts into JSON tables:
   - techno_furnace_data
   - techno_plant_data
8. Shows results
9. Cleans up temporary file
```

**All automatic!** 🎉

---

## 📊 Upload Response

### **Success**
```
✓ Upload Successful!

Plant: BSP
Month: 2025-05
Furnaces: 4
Furnace Parameters: 2
Plant Data Source: from_source
Plant Parameters: 1

✓ Data inserted into JSON tables!
```

### **Failure**
```
✗ Upload Failed

Error: [detailed error message]
```

---

## 🔄 API Endpoint (Programmatic Access)

If you want to upload via script or another app:

```bash
curl -X POST "http://localhost:8000/api/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@report.xlsx" \
  -F "plant=BSP" \
  -F "extractor_type=oisco" \
  -F "report_month=2025-05"
```

**Response:**
```json
{
  "status": "success",
  "message": "Data extracted and inserted successfully",
  "data": {
    "plant": "BSP",
    "month": "2025-05",
    "furnaces_inserted": 4,
    "plant_data_source": "from_source",
    "parameters": {
      "furnace": 2,
      "plant": 1
    }
  }
}
```

---

## 📝 Supported Extractors

| Plant | OISCO | TechnoMya | RSP |
|-------|-------|-----------|-----|
| BSP   | ✓     | ✓         | -   |
| DSP   | -     | -         | ✓   |
| RSP   | -     | -         | ✓   |
| BSL   | -     | -         | ✓   |
| ISP   | -     | -         | ✓   |

---

## 🛠️ Troubleshooting

### Error: "Unsupported plant"
**Fix:** Make sure plant code is correct (BSP, DSP, RSP, BSL, ISP)

### Error: "Unsupported extractor type"
**Fix:** Check which extractors are available for your plant

### Error: "Invalid month format"
**Fix:** Use YYYY-MM format (e.g., 2025-05)

### Error: "File not supported"
**Fix:** Upload Excel file (.xlsx or .xls)

### Error: "No parameters extracted"
**Fix:** Check Excel file has correct structure with parameters

### Data not appearing in tables
**Fix:** 
1. Check upload response for success
2. Open dashboard and verify month/plant
3. Reload dashboard page

---

## 📊 Verify Uploaded Data

### **In Dashboard**
```
URL: http://localhost:8000/dashboard
Select: Plant, Month
View: Furnace Data or Plant Consolidated
→ See your uploaded data!
```

### **In Database**
```sql
-- Check furnace data
SELECT * FROM techno_furnace_data 
WHERE plant='BSP' AND report_month='2025-05';

-- Check plant data
SELECT * FROM techno_plant_data 
WHERE plant='BSP' AND report_month='2025-05';
```

---

## 🎯 Typical Workflow

```bash
# 1. Start API server
cd d:\opr-mis1\backend
python -m uvicorn main:app --reload

# 2. Open upload page
# http://localhost:8000/upload

# 3. Upload file
# - Select: Plant=BSP, Type=oisco, Month=2025-05
# - Upload: BSPOISCO_MAY'25.xlsx
# - Click: Upload & Extract

# 4. View results
# - See upload confirmation
# - Check: http://localhost:8000/dashboard

# 5. Done!
# Data is in JSON tables ✓
```

---

## 📝 Upload Limitations

- **File size:** Up to typical FastAPI limit (~100MB)
- **File type:** Excel (.xlsx, .xls) only
- **Month format:** YYYY-MM
- **Plant codes:** BSP, DSP, RSP, BSL, ISP
- **Extractor types:** Depends on plant

---

## 🚀 Ready!

Open: **http://localhost:8000/upload**

Just upload your file and data auto-populates! 🎉

