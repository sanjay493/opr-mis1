# Manual Data Entry Guide

## 📋 Overview

Instead of automated extraction, you'll manually enter data one parameter at a time, ensuring **100% accuracy**.

**Process:**
1. Edit JSON template file with actual values
2. Validate the JSON
3. Review preview
4. Insert into database

---

## 📁 Files Available

### **Template File**
```
backend/manual_data_entry_template.json
```

Contains structure for all furnaces and parameters. Pre-filled with known values:
- BF-4: Coke Rate = 430.2, CDI = 118.08
- BF-6: Coke Rate = 430.2, BF Productivity = 2.12, CDI = 118.08
- BF-7: BF Productivity = 1.91
- BF-8: BF Productivity = 2.45
- Others: Set to null (waiting for your input)

### **Validation Script**
```
backend/validate_manual_entry.py
```

Checks your JSON before insertion:
- All values are valid numbers
- Units match expected values
- Data quality issues flagged

### **Insertion Script**
```
backend/insert_manual_data.py
```

Safely inserts validated data into database with confirmation step.

---

## 🚀 Step-by-Step Process

### **Step 1: Open and Edit Template**

```
File: backend/manual_data_entry_template.json
```

Structure:
```json
{
  "report_month": "2026-05",
  "plant": "BSP",
  "furnaces": {
    "BF-1": {
      "Coke Rate": {
        "value": null,        ← Replace null with actual value
        "unit": "Kg/THM",
        "source": "Manual"
      },
      ...
    }
  }
}
```

**For each parameter:**
1. Open source file (Excel/PDF)
2. Find the value in the file
3. Replace `null` with the value
4. Keep unit and source as-is

---

### **Step 2: Validate JSON**

Run validation:
```bash
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe validate_manual_entry.py manual_data_entry_template.json
```

**Output will show:**
- ✓ JSON structure correct
- ✓ All values are valid numbers
- ✓ Units match
- ⚠️ Any warnings or missing data

**Example output:**
```
[OK] JSON file loaded successfully

[VALIDATING STRUCTURE]
  [OK] report_month present
  [OK] plant present
  [OK] furnaces present
  [OK] 8 furnaces defined

[VALIDATING VALUES]
  [INFO] Total parameters: 24
  [INFO] Filled values: 8
  [WARN] Empty values: 16
    - BF-1.Coke Rate
    - BF-1.BF Productivity
    - BF-1.CDI
    ... etc

[VALIDATING UNITS]
  [OK] All units match expected values

[VALIDATING DATA QUALITY]
  [WARN] 2 potential issues:
    - BF-1: No parameters filled
    - BF-2: Only 0/3 parameters filled

✅ DATA VALIDATION PASSED - Safe to insert into database
```

---

### **Step 3: Review Data Preview**

```bash
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe insert_manual_data.py manual_data_entry_template.json
```

This will:
1. Validate the JSON
2. Show a preview:
```
Report Month: 2026-05
Plant: BSP

Furnace Data (8 furnaces):

  BF-1: 0/3 parameters
  BF-2: 0/3 parameters
  BF-3: 0/3 parameters
  BF-4: 2/3 parameters
    • Coke Rate: 430.2 Kg/THM
    • CDI: 118.08 Kg/THM
  BF-6: 3/3 parameters
    • Coke Rate: 430.2 Kg/THM
    • BF Productivity: 2.12 T/m³/day
    • CDI: 118.08 Kg/THM
  BF-7: 1/3 parameters
    • BF Productivity: 1.91 T/m³/day
  BF-8: 1/3 parameters
    • BF Productivity: 2.45 T/m³/day
```

3. Ask for confirmation: `Insert this data into database? (yes/no):`

---

### **Step 4: Insert into Database**

Type `yes` to confirm insertion.

**Script will:**
1. Insert furnace data for each furnace with values
2. Calculate plant consolidated
3. Verify insertion by retrieving from database
4. Show results

**Example success:**
```
INSERTING DATA INTO DATABASE

Inserting furnace data for BSP (2026-05)...

  ⊘  BF-1: No data to insert (all values null)
  ⊘  BF-2: No data to insert (all values null)
  ⊘  BF-3: No data to insert (all values null)
  ✓ BF-4: 2 parameters inserted
  ✓ BF-6: 3 parameters inserted
  ✓ BF-7: 1 parameters inserted
  ✓ BF-8: 1 parameters inserted

Calculating plant consolidated for BSP...

  ✓ Plant consolidated calculated: 3 parameters

INSERTION RESULTS

Furnace records inserted: 4

Verifying inserted data:

✓ Furnace data retrieved: 4 furnaces
  BF-4: 2 parameters
  BF-6: 3 parameters
  BF-7: 1 parameters
  BF-8: 1 parameters

✓ Plant consolidated retrieved: 3 parameters

✅ DATA INSERTION COMPLETE
```

---

## 📊 Data Entry Checklist

For **May 2026 (2026-05)**, open: **BSP-3-page-TechMay'26.xlsx**

### **BF-1** ☐
- [ ] Coke Rate
- [ ] BF Productivity
- [ ] CDI

### **BF-2** ☐
- [ ] Coke Rate
- [ ] BF Productivity
- [ ] CDI

### **BF-3** ☐
- [ ] Coke Rate
- [ ] BF Productivity
- [ ] CDI

### **BF-4** ☑️ (Pre-filled)
- [x] Coke Rate: 430.2
- [ ] BF Productivity
- [x] CDI: 118.08

### **BF-5** ⊘
- (Empty - no data available)

### **BF-6** ☑️ (Pre-filled)
- [x] Coke Rate: 430.2
- [x] BF Productivity: 2.12
- [x] CDI: 118.08

### **BF-7** ⚠️ (Partial)
- [ ] Coke Rate
- [x] BF Productivity: 1.91
- [ ] CDI

### **BF-8** ⚠️ (Partial)
- [ ] Coke Rate
- [x] BF Productivity: 2.45
- [ ] CDI

---

## ✅ Verification

After insertion, verify data via dashboard:

```
URL: http://localhost:8000/dashboard

Select:
- Plant: BSP
- Month: 2026-05
- View: Furnace Data

Should see all furnaces you entered data for!
```

---

## 🛠️ Troubleshooting

### Validation Fails
**Problem:** `Invalid number`, `Missing unit`, etc.

**Solution:**
1. Open manual_data_entry_template.json in text editor
2. Find the error line (validator tells you which)
3. Check the value is a valid number (not text like "NULL" or empty string)
4. Fix and save, then validate again

### Insertion Fails
**Problem:** `ERROR - XYZ parameter`

**Solution:**
1. Run validator first (shows more details)
2. Check the specific parameter that failed
3. Verify it's a valid number in the JSON
4. Run validation again before retry

### Data Not Appearing in Dashboard
**Problem:** Inserted data not showing up

**Solution:**
1. Reload dashboard page (Ctrl+F5 or Cmd+Shift+R)
2. Check month and plant selection
3. Verify insertion succeeded (check terminal output)
4. Try different view (Furnace Data vs Plant Consolidated)

---

## 📝 Data Entry Tips

1. **Be Precise:** Copy exact values from source files
   - Don't round unless instructed
   - Include decimals (e.g., 2.12 not 2)

2. **Check Units:** Match the unit in source file
   - Kg/THM, T/m³/day, %, etc.
   - Validator will warn if wrong

3. **Leave Null for Missing Data:**
   - If parameter not in source file, leave as `null`
   - Don't guess or estimate values

4. **One Month at a Time:**
   - Create separate JSON file for each month
   - Prevents mixing data by accident

5. **Validate Before Insert:**
   - Always run validator first
   - Review preview carefully
   - It's harder to fix after insertion

---

## 🎯 Complete Workflow Example

```bash
# 1. Edit template file with values from Excel
# File: backend/manual_data_entry_template.json
# (Use your text editor - Notepad, VS Code, etc.)

# 2. Validate
cd d:\opr-mis1\backend
C:\Users\sanja\anaconda3\python.exe validate_manual_entry.py manual_data_entry_template.json

# 3. Insert (requires confirmation)
C:\Users\sanja\anaconda3\python.exe insert_manual_data.py manual_data_entry_template.json

# 4. Verify in dashboard
# http://localhost:8000/dashboard

# 5. For next month, copy template and repeat
# Edit → Validate → Insert → Verify
```

---

## 📚 Parameter Reference

**Available Parameters:**
- Coke Rate (Kg/THM)
- BF Productivity (T/m³/day)
- CDI (Kg/THM)
- Slag Rate (Kg/THM)
- Nut Coke Rate (Kg/THM)
- Fuel Rate (Kg/THM)
- Pellet in Burden (%)
- Sinter in Burden (%)
- And many more...

**If you need to add parameters not in template:**
1. Add to `EXPECTED_UNITS` in `validate_manual_entry.py`
2. Add to template.json
3. Validate will recognize it

---

## 📞 Support

If you encounter issues:
1. **Validation errors:** Error message tells you which line/parameter
2. **Insertion errors:** Check validation output first
3. **Data not in dashboard:** Check month/plant selection and reload page

All scripts provide clear error messages to guide you!

---

**Ready to start? Open `backend/manual_data_entry_template.json` and begin entering data!** 📝

