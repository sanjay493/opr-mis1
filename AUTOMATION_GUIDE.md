# Automation Guide - Extract from Excel Automatically

## 🚀 Three Ways to Automate

### **Option 1: One-Command Auto-Detect** (Easiest)
```bash
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe auto_cell_detector.py --batch Report_format/Monthly
```

**What it does:**
- Scans all Excel files in `Report_format/Monthly`
- Auto-detects parameters and cell locations
- Creates mapping files for each plant
- **No manual mapping needed!**

**Output:**
```
BSP: ✓ 3 parameters detected
DSP: ✓ 5 parameters detected
RSP: ✓ 4 parameters detected
```

Creates:
- `backend/bsp_auto_mapping.json`
- `backend/dsp_auto_mapping.json`
- `backend/rsp_auto_mapping.json`

---

### **Option 2: Batch Extract All Plants**
```bash
python batch_automation.py extract
```

**What it does:**
- Reads all mapping files
- Extracts from all enabled plants
- Validates and inserts into database
- Logs all operations

**Output:**
```
================================================================================
BATCH EXTRACTION
================================================================================

BSP:  ✓ SUCCESS
DSP:  ✓ SUCCESS
RSP:  ✓ SUCCESS
BSL:  ✓ SUCCESS
ISP:  ✓ SUCCESS

================================================================================
BATCH EXTRACTION SUMMARY
================================================================================

Success: 5
Failed:  0
Skipped: 0
Total:   5
```

---

### **Option 3: Scheduled Daily Extraction**
```bash
python batch_automation.py setup-daily
```

**What it does:**
- Sets up Windows Task Scheduler to run extraction daily at 9:00 AM
- Automatically extracts from all plants every morning
- Logs all runs with timestamps

**Steps:**
1. Run the command above
2. Follow on-screen instructions
3. Enter your Windows password when prompted
4. **Done!** Extraction runs automatically every day

**Or manually via PowerShell (as Admin):**
```powershell
Register-ScheduledTask -TaskName 'SAIL_MIS_Techno_Extraction' `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 09:00) `
  -Action (New-ScheduledTaskAction -Execute 'C:\Users\sanja\AppData\Local\Temp\run_extraction.bat')
```

---

## 📊 Complete Workflow

### **First Time Setup (5 minutes)**

**Step 1: Auto-Detect All Mappings**
```bash
python auto_cell_detector.py --batch Report_format/Monthly
```

**Step 2: Review Generated Mappings**
```
backend/bsp_auto_mapping.json
backend/dsp_auto_mapping.json
backend/rsp_auto_mapping.json
backend/bsp_auto_mapping.json
backend/bsl_auto_mapping.json
```

**Step 3: Test Extraction**
```bash
python batch_automation.py extract --preview
```

**Step 4: Setup Daily Schedule (Optional)**
```bash
python batch_automation.py setup-daily
```

---

### **Daily Usage - After Setup**

**Manual extraction:**
```bash
python batch_automation.py extract
```

**Scheduled extraction:**
- Runs automatically at 9:00 AM every day
- Check logs: `backend/logs/extraction_*.log`

---

## 🔍 How Auto-Detection Works

### **Scan Pattern**
1. Opens each Excel file
2. Looks for known parameter names in Column A
3. Finds values in Column B onwards
4. Maps cell locations automatically
5. Generates mapping file

### **Known Parameters**
- Coke Rate
- BF Productivity
- CDI
- Slag Rate
- Nut Coke Rate
- Fuel Rate
- Energy
- Pellet in Burden
- Sinter in Burden

### **Example Detection**
```
Excel Layout:
  A                      B
  Coke Rate (Kg/THM)     430.2
  BF Productivity        2.12
  CDI (Kg/THM)           118.08

Generated Mapping:
  {
    "parameter": "Coke Rate",
    "cell": "B1",
    "unit": "Kg/THM"
  }
```

---

## ⚙️ Configuration

### **View Config**
```bash
python batch_automation.py config
```

### **Edit Config**
```bash
python batch_automation.py config-edit
```

**Config options:**
- Enable/disable specific plants
- Setup schedule
- Auto-insert without confirmation
- Notification settings

### **Config File Location**
```
backend/batch_automation_config.json
```

**Example:**
```json
{
  "enabled": true,
  "excel_folder": "Report_format/Monthly",
  "schedule": {
    "enabled": true,
    "frequency": "daily",
    "time": "09:00"
  },
  "extraction": {
    "auto_insert": false,
    "verify": true
  },
  "plants": [
    {"code": "BSP", "enabled": true},
    {"code": "DSP", "enabled": true},
    {"code": "RSP", "enabled": true},
    {"code": "BSL", "enabled": true},
    {"code": "ISP", "enabled": true}
  ]
}
```

---

## 📝 Advanced: Single Plant Auto-Detection

Auto-detect for one plant only:
```bash
python auto_cell_detector.py Report_format/Monthly/BSP-3-page-TechMay'26.xlsx --plant BSP
```

With custom output:
```bash
python auto_cell_detector.py Report_format/Monthly/BSP-3-page-TechMay'26.xlsx \
  --plant BSP \
  --month 2026-05 \
  --output bsp_custom_mapping.json
```

---

## 🔄 Multi-Month Extraction

Auto-detection creates mappings for single month. For multiple months:

**Edit mapping file:**
```json
{
  "from_month": "2026-01",
  "till_month": "2026-12",
  "mappings": [...]
}
```

System automatically adjusts cell references for each month column!

---

## 📊 Logs and Monitoring

### **Log Location**
```
backend/logs/extraction_20260627_090000.log
```

### **Log Format**
```
2026-06-27 09:00:15 - __main__ - INFO - Batch extraction started
2026-06-27 09:00:15 - __main__ - INFO - BSP: Extraction successful
2026-06-27 09:00:20 - __main__ - INFO - DSP: Extraction successful
2026-06-27 09:00:25 - __main__ - INFO - RSP: Extraction successful
```

### **View Latest Log**
```bash
Get-Content backend/logs/*.log | Tail -100
```

---

## ✅ Verification

### **Check Extraction Status**
```bash
python batch_automation.py extract
```

Shows:
- ✓ Success count
- ✗ Failed count
- ⊘ Skipped count
- Detailed per-plant status

### **Verify in Dashboard**
```
URL: http://localhost:8000/dashboard

Select:
- Plant: BSP, DSP, RSP, etc.
- Month: Select latest month
- View: Plant Consolidated

Should see freshly extracted data!
```

---

## 🛠️ Troubleshooting

### Problem: "No parameters detected"
**Solution:**
1. Check Excel file has expected layout (parameters in Column A)
2. Verify parameter names match known list
3. Ensure values are in Column B onwards
4. Manually check: `python auto_cell_detector.py <file> --plant BSP`

### Problem: "Mapping file not found"
**Solution:**
1. Run auto-detect: `python auto_cell_detector.py --batch Report_format/Monthly`
2. Verify files created: `ls backend/*_auto_mapping.json`

### Problem: Scheduled extraction not running
**Solution:**
1. Open Task Scheduler (Win+R → taskschd.msc)
2. Find task: "SAIL_MIS_Techno_Extraction"
3. Right-click → Run
4. Check logs: `backend/logs/`

### Problem: Extraction errors
**Solution:**
1. Check Excel files are readable and not locked
2. Verify column structure hasn't changed
3. Check database connection
4. Review log file for specific error

---

## 🎯 Recommended Setup

**For Daily Automatic Extraction:**

```bash
# Step 1: Auto-detect mappings (once)
python auto_cell_detector.py --batch Report_format/Monthly

# Step 2: Test extraction (once)
python batch_automation.py extract

# Step 3: Setup daily schedule (once)
python batch_automation.py setup-daily

# Now: Every day at 9:00 AM, extraction runs automatically!
```

**Check results:**
```bash
# View latest log
Get-Content backend/logs/*.log | Sort-Object -Descending | Select-Object -First 50

# Verify in dashboard
# Open: http://localhost:8000/dashboard
```

---

## 📈 Benefits

✅ **Zero manual work** - Fully automated  
✅ **Accurate detection** - Smart parameter identification  
✅ **Reliable** - Logging and verification built-in  
✅ **Flexible** - Enable/disable plants, customize schedule  
✅ **Safe** - Validation before insertion  
✅ **Scheduled** - Runs automatically at set times  

---

## 🚀 Quick Start

```bash
# 1. Auto-detect all mappings
cd d:\opr-mis1
python backend/auto_cell_detector.py --batch Report_format/Monthly

# 2. Test extraction
python backend/batch_automation.py extract

# 3. Setup daily automatic extraction
python backend/batch_automation.py setup-daily

# Done! Extraction runs every day at 9:00 AM 🎉
```

---

## 📞 Support

If issues occur:
1. **Check logs:** `backend/logs/extraction_*.log`
2. **Verify mappings:** `ls backend/*_auto_mapping.json`
3. **Test single plant:** `python auto_cell_detector.py <file> --plant <CODE>`
4. **Review config:** `python batch_automation.py config`

**All scripts provide clear error messages!**

---

**Fully automated, zero manual work!** 🚀

