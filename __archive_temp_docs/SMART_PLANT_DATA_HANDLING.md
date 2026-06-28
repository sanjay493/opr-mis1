# Smart Plant Data Handling

## 🎯 The Logic

```
IF plant data in source file:
    ✓ Use it directly
ELSE:
    ✓ Auto-calculate from furnace data
```

**Simple!** No unnecessary calculations.

---

## 📊 Two Scenarios

### **Scenario 1: Plant Data IN Source File**

```
Excel File (OISCO)
├── BF-4: CDI = 118.08
├── BF-6: CDI = 118.08
├── BF-7: (empty)
├── BF-8: (empty)
└── Plant Level: CDI = 118.08  ← Plant data in source!

Extraction:
  Furnace data → BF-4, BF-6
  Plant data → Found in source ✓
  
Insertion:
  ✓ Insert furnace data (BF-4, BF-6)
  ✓ Use plant data from source directly
  (No calculation needed!)
```

**Output:**
```
✓ techno_furnace_data: BF-4, BF-6 data
✓ techno_plant_data: Data from source file
```

---

### **Scenario 2: Plant Data NOT in Source File**

```
Excel File (TechnoMya)
├── BF-4: Coke Rate = 430.2
├── BF-6: Coke Rate = 430.2
├── BF-7: Coke Rate = (empty)
├── BF-8: Coke Rate = (empty)
└── Plant Level: (Not in file)  ← No plant data!

Extraction:
  Furnace data → BF-4, BF-6
  Plant data → Not found
  
Insertion:
  ✓ Insert furnace data (BF-4, BF-6)
  ✓ Auto-calculate plant consolidated from furnace data
  (Uses weighted averages or direct values)
```

**Output:**
```
✓ techno_furnace_data: BF-4, BF-6 data
✓ techno_plant_data: Auto-calculated from furnaces
```

---

## 🔄 How It Works

```
Extract All Data
    ↓
Separate:
  ├─ Furnace data (has furnace ID)
  └─ Plant data (no furnace ID)
    ↓
IF plant_data found in source:
  ├─ Insert furnace data
  └─ Insert plant data (from source)
ELSE:
  ├─ Insert furnace data
  └─ Auto-calculate & insert plant data
```

---

## ✅ Key Points

✅ **Respects source file** - If plant data exists, uses it  
✅ **No wasted calculation** - Only calculates if needed  
✅ **Accurate data** - Source data always preferred  
✅ **Flexible** - Works whether plant data is in file or not  
✅ **Intelligent** - System handles logic automatically  

---

## 📋 Example Outputs

### **Example 1: OISCO (Plant data in source)**
```
Extraction Output:
  ✓ Furnace data: 4 parameters
  ✓ Plant data in source: 1 parameters

Insertion:
  ✓ BF-4: 1 parameters
  ✓ BF-6: 1 parameters
  Plant consolidated:
    ✓ Using data from source: 1 parameters
```

### **Example 2: TechnoMya (Plant data NOT in source)**
```
Extraction Output:
  ✓ Furnace data: 3 parameters
  ✓ Plant data in source: 0 parameters

Insertion:
  ✓ BF-4: 1 parameters
  ✓ BF-6: 1 parameters
  ✓ BF-7: 1 parameters
  Plant consolidated:
    ⓘ Not in source, calculating from furnace data...
    ✓ Calculated: 1 parameters
```

---

## 🎯 When Does Each Happen?

| Condition | Action |
|-----------|--------|
| Plant data in Excel file | Use directly, don't calculate |
| Plant data NOT in Excel file | Calculate from furnace data |
| Only furnace data extracted | Calculate plant from furnaces |
| No data at all | Skip (error) |

---

## 💡 Why This Matters

**Scenario A: You have plant-level Coke Rate in Excel**
```
Plant Coke Rate = 430.2 (from Excel)
  ↓
✓ Use this directly
✗ Don't calculate from furnaces
```

**Scenario B: You only have furnace-level data**
```
BF-4 Coke Rate = 430.2
BF-6 Coke Rate = 430.2
BF-7 = empty
BF-8 = empty
  ↓
✓ Calculate plant rate from available furnaces
✓ Not from all 8 (some empty)
```

---

## 🚀 In Practice

When you run extraction:

```bash
python run_bsp_oisco_extraction.py
```

The system will show:

```
Separating data:
  ✓ Furnace data: 2 parameters
  ✓ Plant data in source: 1 parameters
    
Plant consolidated:
  ✓ Using data from source: 1 parameters
```

OR

```
Separating data:
  ✓ Furnace data: 3 parameters
  ✓ Plant data in source: 0 parameters
    
Plant consolidated:
  ⓘ Not in source, calculating from furnace data...
  ✓ Calculated: 1 parameters
```

**You'll see which approach was taken!** ✅

---

## 🔍 Verification

### **Check what was inserted (SQL)**

```sql
-- See if plant data is from source or calculated
SELECT plant, report_month, data 
FROM techno_plant_data 
WHERE plant='BSP';

-- Look at calculation_details to see method:
-- {'method': 'from_source'} = From Excel
-- {'method': 'calculated'} = Auto-calculated from furnaces
```

---

## ✨ Summary

**The system is smart:**
- ✅ Knows to use plant data if it's in the source
- ✅ Knows to calculate if it's not
- ✅ Never does unnecessary work
- ✅ Always prefers source data
- ✅ Shows you what it did

**You don't need to think about it.** The system handles it automatically! 🎉

