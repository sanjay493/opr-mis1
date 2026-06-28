# Adding New Techno Parameters to JSON Database

## 🎯 The Beauty of JSON Approach

**Old Normalized Approach:**
```
❌ Need to ADD column to techno_param table
❌ Need to UPDATE schema
❌ Need to UPDATE dashboard queries
❌ Time-consuming and risky
```

**New JSON Approach:**
```
✅ Just add to JSON data object
✅ No schema changes
✅ Dashboard automatically picks it up
✅ Simple and flexible!
```

---

## 📊 Example: Adding a New Parameter

### Scenario: You find "Furnace Efficiency (%)" in the PDF that isn't currently extracted

### Step 1: Identify the Parameter in PDF

```
From PDF (BSP_June_2026.pdf):

Furnace Performance Summary
├── BF-1: Furnace Efficiency = 85.5%
├── BF-2: Furnace Efficiency = 87.2%
├── BF-3: Furnace Efficiency = 84.8%
└── BF-4: Furnace Efficiency = 86.1%
```

### Step 2: Add to Python Extractor (One Time Setup)

**File: `backend/excel_extractors/pdf_extractor_bsp.py`**

```python
def extract_furnace_data_from_pdf(pdf_rows, report_month):
    """
    Extract furnace-wise data from BSP PDF
    Now includes: Furnace Efficiency
    """
    
    # Existing parameters
    PARAM_UNITS = {
        'Coke Rate': 'Kg/THM',
        'BF Productivity': 'T/m³/day',
        'CDI Rate': 'Kg/THM',
        'Fuel Rate': 'Kg/THM',
        'O2 Enrichment': '%',
        'Sinter in Burden': '%',
        'Pellet in Burden': '%',
        'Slag Rate': 'Kg/THM',
        'Hot Blast Temp': '°C',
        'HM Production': 'T',
        
        # NEW PARAMETER - Just add it!
        'Furnace Efficiency': '%'  ← NEW!
    }
    
    furnaces = _identify_furnaces(pdf_rows)  # BF-1, BF-2, BF-3, BF-4
    
    furnace_records = []
    
    for furnace in furnaces:
        data = {}
        
        for param, unit in PARAM_UNITS.items():
            # For most parameters, use existing extraction logic
            if param in ['Coke Rate', 'BF Productivity', ...]:
                value = _extract_param_for_furnace(pdf_rows, furnace, param)
            
            # For NEW parameter, add new extraction logic
            elif param == 'Furnace Efficiency':
                value = _extract_furnace_efficiency(pdf_rows, furnace)
            
            if value is not None:
                data[param] = {
                    'value': float(value),
                    'unit': unit
                }
        
        furnace_record = {
            'plant': 'BSP',
            'furnace': furnace,
            'report_month': report_month,
            'data': data  # ← Automatically includes new parameter!
        }
        
        furnace_records.append(furnace_record)
    
    return furnace_records


# NEW EXTRACTION FUNCTION (just add this)
def _extract_furnace_efficiency(pdf_rows, furnace):
    """
    Extract Furnace Efficiency from specific section of PDF
    
    PDF section:
    Furnace Performance Summary
    BF-1: 85.5
    BF-2: 87.2
    etc.
    """
    
    for i, row in enumerate(pdf_rows):
        # Look for "Furnace Performance" section
        if 'Furnace Performance' in str(row) or 'Furnace Efficiency' in str(row):
            # Find matching furnace row
            for j in range(i, min(i + 10, len(pdf_rows))):
                if furnace in str(pdf_rows[j]):
                    # Extract efficiency value
                    # (implementation depends on PDF structure)
                    value = _parse_efficiency_value(pdf_rows[j])
                    return value
    
    return None


def _parse_efficiency_value(row_text):
    """Parse efficiency value from row"""
    import re
    
    # Extract number followed by %
    match = re.search(r'(\d+\.?\d*)\s*%', str(row_text))
    if match:
        return float(match.group(1))
    
    return None
```

### Step 3: Data is Automatically Stored in JSON

```json
{
  "id": 1001,
  "plant": "BSP",
  "furnace": "BF-1",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {"value": 300.0, "unit": "Kg/THM"},
    "BF Productivity": {"value": 2.10, "unit": "T/m³/day"},
    "Furnace Efficiency": {
      "value": 85.5,
      "unit": "%"
    }
  }
}
```

**No schema changes needed!** JSON automatically includes the new parameter.

---

## 🌐 Step 4: Dashboard Automatically Picks It Up

**Frontend: `techno-dashboard/page.js`**

```javascript
// When you load parameters from API:
const res = await fetch(`${API_BASE}/api/techno-parameters`);
const { parameters } = await res.json();

// Response now includes: "Furnace Efficiency"
// Parameters list automatically shows:
// ✓ Coke Rate
// ✓ BF Productivity
// ✓ Furnace Efficiency  ← NEW! Automatically appears!
// ✓ etc.
```

**No code changes needed!** The dashboard's parameter selection automatically shows all parameters from the JSON.

---

## 📋 Complete Workflow for Adding New Parameters

### Scenario: Add 5 New Parameters

#### New Parameters to Add:
1. **Gas Utilization Rate (%)** - Blast furnace efficiency metric
2. **Slag Basicity (CaO/SiO2)** - Steel slag quality
3. **Refractory Wear Rate (mm/month)** - Equipment monitoring
4. **Oxygen Consumption (m³/THM)** - Process efficiency
5. **Water Usage (m³/THM)** - Environmental metric

#### Implementation (3 Simple Steps):

### Step 1: Update PARAM_UNITS Dictionary

**File: `backend/excel_extractors/pdf_extractor_bsp.py`**

```python
PARAM_UNITS = {
    # Existing parameters
    'Coke Rate': 'Kg/THM',
    'BF Productivity': 'T/m³/day',
    'CDI Rate': 'Kg/THM',
    'Fuel Rate': 'Kg/THM',
    'O2 Enrichment': '%',
    'Sinter in Burden': '%',
    'Pellet in Burden': '%',
    'Slag Rate': 'Kg/THM',
    'Hot Blast Temp': '°C',
    'HM Production': 'T',
    
    # NEW PARAMETERS - Just add them!
    'Gas Utilization Rate': '%',
    'Slag Basicity': 'CaO/SiO2',
    'Refractory Wear Rate': 'mm/month',
    'Oxygen Consumption': 'm³/THM',
    'Water Usage': 'm³/THM'
}
```

### Step 2: Add Extraction Logic for Each Parameter

```python
def _extract_gas_utilization_rate(pdf_rows, furnace):
    """Extract Gas Utilization Rate from PDF"""
    # Your PDF parsing logic here
    pass

def _extract_slag_basicity(pdf_rows, furnace):
    """Extract Slag Basicity from PDF"""
    # Your PDF parsing logic here
    pass

def _extract_refractory_wear_rate(pdf_rows, furnace):
    """Extract Refractory Wear Rate from PDF"""
    # Your PDF parsing logic here
    pass

def _extract_oxygen_consumption(pdf_rows, furnace):
    """Extract Oxygen Consumption from PDF"""
    # Your PDF parsing logic here
    pass

def _extract_water_usage(pdf_rows, furnace):
    """Extract Water Usage from PDF"""
    # Your PDF parsing logic here
    pass
```

### Step 3: Update Main Extraction Function

```python
def extract_furnace_data_from_pdf(pdf_rows, report_month):
    PARAM_UNITS = {...}  # From Step 1
    
    furnace_records = []
    
    for furnace in furnaces:
        data = {}
        
        for param, unit in PARAM_UNITS.items():
            # Generic extraction for most parameters
            if param in ['Coke Rate', 'BF Productivity', ...]:
                value = _extract_param_for_furnace(pdf_rows, furnace, param)
            
            # Specific extraction for new parameters
            elif param == 'Gas Utilization Rate':
                value = _extract_gas_utilization_rate(pdf_rows, furnace)
            elif param == 'Slag Basicity':
                value = _extract_slag_basicity(pdf_rows, furnace)
            elif param == 'Refractory Wear Rate':
                value = _extract_refractory_wear_rate(pdf_rows, furnace)
            elif param == 'Oxygen Consumption':
                value = _extract_oxygen_consumption(pdf_rows, furnace)
            elif param == 'Water Usage':
                value = _extract_water_usage(pdf_rows, furnace)
            
            if value is not None:
                data[param] = {'value': float(value), 'unit': unit}
        
        furnace_records.append({
            'plant': 'BSP',
            'furnace': furnace,
            'report_month': report_month,
            'data': data
        })
    
    return furnace_records
```

---

## 🎯 How Parameters Flow Through the System

```
PDF File
    ↓
    ├─ Existing extraction logic
    │  (Coke Rate, BF Prod, etc.)
    │
    └─ NEW extraction logic
       (Gas Util Rate, Slag Basicity, etc.)
    ↓
Furnace-wise JSON Data:
{
  "Coke Rate": {...},
  "Gas Utilization Rate": {...},  ← NEW
  "Slag Basicity": {...},         ← NEW
  "Water Usage": {...}            ← NEW
}
    ↓
INSERT INTO techno_furnace_data
    ↓
Calculate Plant Consolidated:
  Weighted average of all parameters
  (including new ones!)
    ↓
INSERT INTO techno_plant_data
    ↓
API /api/techno-parameters returns:
[
  "Coke Rate",
  "Gas Utilization Rate",  ← NEW (auto-detected)
  "Slag Basicity",         ← NEW (auto-detected)
  ...
]
    ↓
Dashboard automatically shows:
✓ Parameter selection checkboxes (includes new params)
✓ Table view with new parameters
✓ Chart view with new parameters
```

---

## 🚀 API Automatically Detects New Parameters

**File: `backend/main.py`**

```python
@app.get("/api/techno-parameters")
async def get_techno_parameters():
    """
    Returns list of ALL available parameters
    (automatically includes new ones!)
    """
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    
    # Query all unique parameters from all furnace records
    cursor.execute("""
        SELECT DISTINCT json_extract(data, '$')
        FROM techno_furnace_data
    """)
    
    all_params = set()
    
    for row in cursor.fetchall():
        data = json.loads(row[0]) if row[0] else {}
        all_params.update(data.keys())
    
    conn.close()
    
    # Remove non-display parameters
    exclude = ['HM Production']
    parameters = sorted([p for p in all_params if p not in exclude])
    
    return {
        'parameters': parameters,
        'count': len(parameters)
    }
```

**When you add new parameters, this endpoint automatically returns them!**

---

## 📊 JSON Data Structure with New Parameters

```json
{
  "plant": "BSP",
  "furnace": "BF-1",
  "report_month": "2026-06",
  "data": {
    // Existing parameters
    "Coke Rate": {
      "value": 300.0,
      "unit": "Kg/THM"
    },
    "BF Productivity": {
      "value": 2.10,
      "unit": "T/m³/day"
    },
    
    // NEW Parameters
    "Gas Utilization Rate": {
      "value": 87.5,
      "unit": "%"
    },
    "Slag Basicity": {
      "value": 1.25,
      "unit": "CaO/SiO2"
    },
    "Refractory Wear Rate": {
      "value": 2.3,
      "unit": "mm/month"
    },
    "Oxygen Consumption": {
      "value": 450.2,
      "unit": "m³/THM"
    },
    "Water Usage": {
      "value": 35.8,
      "unit": "m³/THM"
    },
    
    // Weight for calculation
    "HM Production": {
      "value": 10000.0,
      "unit": "T",
      "source": "PDF"
    }
  }
}
```

---

## ✅ Advantages of JSON for New Parameters

| Aspect | Old Normalized | New JSON |
|--------|----------------|----------|
| **Add new parameter** | Modify schema + add column | Just add to JSON |
| **Time to implement** | Days (schema migration) | Hours (extraction code) |
| **Risk** | High (schema changes) | Low (no schema changes) |
| **Dashboard update** | Must code new queries | Automatic (JSON flexible) |
| **Storage overhead** | Only for this plant | Only what exists |
| **Backward compatible** | ❌ Not easily | ✅ Full backward compatible |
| **Easy to remove** | ❌ Schema cleanup | ✅ Just delete from extraction |

---

## 🛠️ Quick Start: Adding a Parameter

### 3-Step Process:

**Step 1:** Add unit mapping
```python
'New Parameter Name': 'unit'
```

**Step 2:** Write extraction function
```python
def _extract_new_parameter(pdf_rows, furnace):
    # Extract logic
    return value
```

**Step 3:** Call it in main extraction
```python
elif param == 'New Parameter Name':
    value = _extract_new_parameter(pdf_rows, furnace)
```

**Done!** ✅

---

## 📝 Example: Real Parameter Addition

### Adding "Temperature at Hot Blast Stove" Parameter

**Before:**
```python
'Hot Blast Temp': '°C',  # Only one HB temp
```

**After:**
```python
'Hot Blast Temp': '°C',           # Main HB temp
'HB Stove A Temp': '°C',          # NEW - Stove A
'HB Stove B Temp': '°C',          # NEW - Stove B
'HB Stove C Temp': '°C',          # NEW - Stove C
```

**Implementation:**
```python
def _extract_hb_stove_temps(pdf_rows, furnace):
    """Extract individual stove temperatures"""
    temps = {
        'HB Stove A': None,
        'HB Stove B': None,
        'HB Stove C': None
    }
    
    for row in pdf_rows:
        if 'Hot Blast Stove' in str(row):
            for stove in ['A', 'B', 'C']:
                if f'Stove {stove}' in str(row):
                    temps[f'HB Stove {stove}'] = _parse_temp(row)
    
    return temps
```

**That's it!** All 3 new temperatures automatically appear in:
- ✅ Parameter selection (dashboard)
- ✅ Table view
- ✅ Chart view
- ✅ Data export

---

## 🎁 Summary

**With JSON-based design:**
- ✅ Add unlimited new parameters
- ✅ No database schema changes
- ✅ No code changes to dashboard
- ✅ Backward compatible
- ✅ Just write extraction code once per parameter

**vs Old Normalized:**
- ❌ Add parameter → Modify schema
- ❌ Each parameter → New column
- ❌ Risk of migration issues
- ❌ Must update dashboard queries
- ❌ Time-consuming process

---

## 🚀 Ready to Add Parameters?

Tell me:
1. **What new parameters do you want to add?**
2. **From which source?** (PDF, Excel, etc.)
3. **Which plants?** (BSP, DSP, RSP, etc.)

I can help you:
- [ ] Write extraction functions
- [ ] Test with sample data
- [ ] Integrate into existing code
- [ ] Verify in dashboard

What parameters would you like to add? 📊
