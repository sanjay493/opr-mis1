# HM Production (Weighting Data) Strategy

## 📊 Current Database Analysis

### Production Table Structure:
```sql
CREATE TABLE production_table (
  report_month TEXT,      -- "2026-06"
  plant_name TEXT,        -- "BSP", "DSP", "RSP", etc.
  item_name TEXT,         -- "Hot Metal", "BF-1", "BF#1-7", "SMS-2", etc.
  month_actual REAL       -- Production value
)
```

### Available Data Per Plant:

**RSP Plant:**
- ✅ Individual furnaces: BF-1, BF-5 (furnace-wise production)
- ✅ Hot Metal (total)
- Example: `2026-04 | RSP | BF-1 | 89.017`

**BSP Plant:**
- ❌ No individual furnaces: Only BF#1-7, BF#8 (grouped)
- ✅ Hot Metal (total plant-level)
- Example: `2026-04 | BSP | Hot Metal | 515.206`

**Other Plants:** Likely similar - some have furnace-wise, some don't

---

## 🤔 Key Challenge

**PDF extraction gives furnace-wise techno data:**
```
BF-1: Coke Rate = 300, BF Prod = 2.10
BF-2: Coke Rate = 350, BF Prod = 2.15
BF-3: Coke Rate = 345, BF Prod = 1.95
BF-4: Coke Rate = 357, BF Prod = 2.20
```

**But production_table doesn't always have furnace-wise HM Production:**
- Some plants: Have BF-1, BF-2, BF-3, BF-4 individual data ✅
- Some plants: Only have BF#1-7 grouped data ⚠️
- All plants: Have plant-level "Hot Metal" total data ✅

---

## 💡 Recommended Hybrid Strategy

### **Priority Cascade for HM Production:**

```
Priority 1: PDF/Excel Extraction (Best)
  ↓
  IF PDF contains furnace-wise HM Production:
    Use PDF values directly
  
Priority 2: production_table (Good)
  ↓
  IF production_table has individual furnace data:
    SELECT month_actual FROM production_table
    WHERE plant = ? AND item_name = 'BF-1' AND month = ?
  
Priority 3: Proportional Allocation (Acceptable)
  ↓
  IF no furnace-wise data available:
    Total HM = plant-level "Hot Metal" from production_table
    Per furnace allocation = Total HM / number of furnaces
    (Simple split, not perfect but reasonable)
```

---

## 📋 Implementation Plan

### Step 1: Extract from PDF with HM Production

**When extracting furnace-wise techno data from PDF:**

```python
def extract_furnace_data_from_pdf(pdf_rows, plant, report_month):
    """
    Extract furnace data INCLUDING HM Production if available
    """
    furnace_records = []
    
    # Identify furnaces from PDF (BF-1, BF-2, BF-3, etc.)
    furnaces = _identify_furnaces(pdf_rows)
    
    for furnace in furnaces:
        data = {
            "Coke Rate": {"value": 300, "unit": "Kg/THM"},
            "BF Productivity": {"value": 2.10, "unit": "T/m³/day"},
            "CDI Rate": {"value": 433, "unit": "Kg/THM"},
            # ... other params ...
            "HM Production": {
                "value": 10000,  # ← Extract from PDF if available
                "unit": "T",
                "source": "PDF"    # ← Note where it came from
            }
        }
        furnace_records.append({
            'plant': plant,
            'furnace': furnace,
            'report_month': report_month,
            'data': data
        })
    
    return furnace_records
```

### Step 2: Fill Missing HM Production from production_table

```python
def fill_missing_hm_production(furnace_records, plant, report_month):
    """
    For any furnace missing HM Production in JSON,
    try to fetch from production_table
    """
    
    for record in furnace_records:
        if 'HM Production' not in record['data']:
            # Try to fetch from production_table
            hm_value = get_hm_from_production_table(
                plant=plant,
                furnace=record['furnace'],
                report_month=report_month
            )
            
            if hm_value:
                record['data']['HM Production'] = {
                    'value': hm_value,
                    'unit': 'T',
                    'source': 'production_table'  # ← Note source
                }
            else:
                # No furnace-wise data, will use plant-level allocation
                record['data']['HM Production'] = {
                    'value': None,
                    'unit': 'T',
                    'source': 'pending_plant_allocation'
                }
    
    return furnace_records


def get_hm_from_production_table(plant, furnace, report_month):
    """
    Query production_table for furnace-wise HM production
    """
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    
    # Try to match furnace name to item_name in production_table
    # e.g., "BF-1" in JSON might be "BF-1" or "BF#1" in production_table
    
    possible_names = [
        furnace,                    # "BF-1"
        furnace.replace('-', '#'),  # "BF#1"
        furnace.upper(),            # "BF-1" (already upper)
    ]
    
    for item_name in possible_names:
        cursor.execute("""
            SELECT month_actual FROM production_table
            WHERE plant_name = ? AND item_name = ? AND report_month = ?
        """, [plant, item_name, report_month])
        
        result = cursor.fetchone()
        if result:
            conn.close()
            return result[0]
    
    conn.close()
    return None
```

### Step 3: Allocate Plant-Level HM if No Furnace Data

```python
def allocate_plant_hm_to_furnaces(furnace_records, plant, report_month):
    """
    If furnace-wise HM Production not available,
    use plant-level Hot Metal / number of furnaces
    """
    
    # Get plant-level Hot Metal
    plant_hm = get_plant_hm(plant, report_month)
    
    if plant_hm:
        # Count furnaces that need allocation
        furnaces_needing_hm = [r for r in furnace_records 
                               if r['data'].get('HM Production', {}).get('value') is None]
        
        if furnaces_needing_hm:
            # Simple allocation: divide by number of furnaces
            per_furnace = plant_hm / len(furnace_records)
            
            for record in furnaces_needing_hm:
                record['data']['HM Production'] = {
                    'value': per_furnace,
                    'unit': 'T',
                    'source': 'plant_level_allocation',
                    'note': f'Plant total {plant_hm}T / {len(furnace_records)} furnaces'
                }
    
    return furnace_records


def get_plant_hm(plant, report_month):
    """Get plant-level Hot Metal production"""
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT month_actual FROM production_table
        WHERE plant_name = ? AND item_name = 'Hot Metal' AND report_month = ?
    """, [plant, report_month])
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None
```

### Step 4: Final JSON Structure with HM Production

```json
{
  "id": 1001,
  "plant": "BSP",
  "furnace": "BF-1",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {
      "value": 300.0,
      "unit": "Kg/THM"
    },
    "BF Productivity": {
      "value": 2.10,
      "unit": "T/m³/day"
    },
    "HM Production": {
      "value": 10000.0,
      "unit": "T",
      "source": "PDF"  ← Comes from PDF extraction
    }
  }
}
```

---

## 📊 Query to Get Furnace Data with HM Production

```python
@app.get("/api/furnace-data-with-weights")
async def get_furnace_data_with_weights(plant: str, report_month: str):
    """
    Get furnace data with HM Production weights for calculating plant-level
    """
    
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT furnace, data
        FROM techno_furnace_data
        WHERE plant = ? AND report_month = ?
        ORDER BY furnace
    """, [plant, report_month])
    
    rows = cursor.fetchall()
    
    result = {
        'furnaces': {},
        'plant': plant,
        'report_month': report_month,
        'total_hm_production': 0
    }
    
    for row in rows:
        furnace_data = json.loads(row['data'])
        result['furnaces'][row['furnace']] = furnace_data
        
        # Accumulate total HM
        if 'HM Production' in furnace_data:
            result['total_hm_production'] += furnace_data['HM Production']['value']
    
    conn.close()
    
    return result

# Response example:
{
  "furnaces": {
    "BF-1": {
      "Coke Rate": {"value": 300, "unit": "Kg/THM"},
      "HM Production": {"value": 10000, "unit": "T", "source": "PDF"}
    },
    "BF-2": {
      "Coke Rate": {"value": 350, "unit": "Kg/THM"},
      "HM Production": {"value": 11100, "unit": "T", "source": "production_table"}
    }
  },
  "total_hm_production": 38213
}
```

---

## 🎯 Summary of Approach

### Don't Store Production Separately:
❌ Keep production_table as single source of truth
✅ Include HM Production in JSON for reference/audit
✅ Store source of HM Production (PDF, production_table, or allocation)

### Benefits:
1. **Complete in JSON**: All data needed for calculation in one place
2. **Audit Trail**: Know where each HM value came from
3. **Flexible**: Can use PDF, production_table, or plant-level allocation
4. **No JOIN needed**: For display/calculation, everything is in JSON
5. **Historical**: Can see what HM values were used when calculation happened

### JSON includes:
- **Techno parameters** (Coke Rate, BF Prod, etc.) from PDF/Excel
- **HM Production** (for weighting) from:
  - Priority 1: PDF extraction
  - Priority 2: production_table query
  - Priority 3: Plant-level allocation
- **Source tracking** (where each value came from)

---

## 🚀 Implementation Flow

```
PDF Input (BSP June 2026)
    ↓
Extract furnace-wise techno + HM Prod from PDF
    ↓
If HM missing → Query production_table for furnace
    ↓
If still missing → Allocate from plant-level Hot Metal
    ↓
INSERT INTO techno_furnace_data (JSON includes HM Prod + source)
    ↓
Calculate plant consolidated using HM from JSON
    ↓
INSERT INTO techno_plant_data (with calculation details showing weights used)
```

---

## ✅ Final Decision:

**Store HM Production IN the JSON with source tracking:**

```json
"HM Production": {
  "value": 10000,
  "unit": "T",
  "source": "PDF" | "production_table" | "plant_allocation"
}
```

This gives you:
- ✅ Self-contained furnace data
- ✅ Clear audit trail
- ✅ Flexible sourcing
- ✅ No extra JOIN queries needed
- ✅ Historical record of what was used

Ready to implement?
