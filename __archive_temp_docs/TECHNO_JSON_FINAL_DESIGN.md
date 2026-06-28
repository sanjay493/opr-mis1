# Techno Database JSON Design - FINAL (Furnace + Plant Consolidated)

## 🏭 Data Hierarchy (Correct Understanding)

```
Plant X (e.g., BSP)
│
├── Level 1: FURNACE DATA (Individual furnaces)
│   ├── BF-1: Coke Rate = 300 Kg/THM, HM Prod = 10000 T
│   ├── BF-2: Coke Rate = 350 Kg/THM, HM Prod = 11100 T
│   ├── BF-3: Coke Rate = 345 Kg/THM, HM Prod = 7234 T
│   ├── BF-4: Coke Rate = 357 Kg/THM, HM Prod = 9879 T
│   ├── SMS-1: SMS Productivity = 2.50 T/hr
│   ├── SMS-2: SMS Productivity = 2.45 T/hr
│   ├── SMS-3: SMS Productivity = 2.48 T/hr
│   └── SMS-4: SMS Productivity = 2.55 T/hr
│
└── Level 2: PLANT DATA (Consolidated from furnaces)
    └── BSP Plant: Coke Rate = 337.98 Kg/THM (weighted avg by HM prod)
        (No separate "Shop" table - Plant IS the Shop consolidated)
```

---

## 📊 Table 1: `techno_furnace_data` - Individual Furnace Data

### Schema:
```sql
CREATE TABLE techno_furnace_data (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant TEXT NOT NULL,              -- "BSP", "DSP", "RSP", "BSL", "ISP"
  furnace TEXT NOT NULL,            -- "BF-1", "BF-2", "BF-3", "BF-4", "SMS-1", "SMS-2", etc.
  report_month TEXT NOT NULL,       -- "2026-06" (YYYY-MM)
  
  data JSON NOT NULL,               -- {param: {value, unit, ...}}
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE(plant, furnace, report_month)
);
```

### Example Row: BSP Blast Furnaces (June 2026)

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
    "CDI Rate": {
      "value": 433.2,
      "unit": "Kg/THM"
    },
    "Fuel Rate": {
      "value": 600.5,
      "unit": "Kg/THM"
    },
    "O2 Enrichment": {
      "value": 2.4,
      "unit": "%"
    },
    "Sinter in Burden": {
      "value": 40.2,
      "unit": "%"
    },
    "Pellet in Burden": {
      "value": 20.1,
      "unit": "%"
    },
    "Slag Rate": {
      "value": 142.5,
      "unit": "Kg/THM"
    },
    "Hot Blast Temp": {
      "value": 1230,
      "unit": "°C"
    },
    "HM Production": {
      "value": 10000.0,
      "unit": "T",
      "note": "Used as weight for calculating plant-level weighted average"
    }
  },
  "created_at": "2026-06-20T14:30:00",
  "updated_at": "2026-06-20T14:30:00"
}
```

```json
{
  "id": 1002,
  "plant": "BSP",
  "furnace": "BF-2",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {"value": 350.0, "unit": "Kg/THM"},
    "BF Productivity": {"value": 2.15, "unit": "T/m³/day"},
    "CDI Rate": {"value": 435.2, "unit": "Kg/THM"},
    "Fuel Rate": {"value": 615.2, "unit": "Kg/THM"},
    "O2 Enrichment": {"value": 2.8, "unit": "%"},
    "Sinter in Burden": {"value": 42.5, "unit": "%"},
    "Pellet in Burden": {"value": 18.5, "unit": "%"},
    "Slag Rate": {"value": 145.8, "unit": "Kg/THM"},
    "Hot Blast Temp": {"value": 1240, "unit": "°C"},
    "HM Production": {"value": 11100.0, "unit": "T"}
  },
  "created_at": "2026-06-20T14:30:00",
  "updated_at": "2026-06-20T14:30:00"
}
```

```json
{
  "id": 1003,
  "plant": "BSP",
  "furnace": "BF-3",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {"value": 345.0, "unit": "Kg/THM"},
    "HM Production": {"value": 7234.0, "unit": "T"}
  }
}
```

```json
{
  "id": 1004,
  "plant": "BSP",
  "furnace": "BF-4",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {"value": 357.0, "unit": "Kg/THM"},
    "HM Production": {"value": 9879.0, "unit": "T"}
  }
}
```

---

## 📊 Table 2: `techno_plant_data` - Plant Consolidated Data

### Schema:
```sql
CREATE TABLE techno_plant_data (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant TEXT NOT NULL PRIMARY KEY,  -- "BSP", "DSP", "RSP", "BSL", "ISP"
  report_month TEXT NOT NULL,       -- "2026-06" (YYYY-MM)
  
  data JSON NOT NULL,               -- {param: {value, unit, calculation, ...}}
  calculation_details JSON,         -- How each parameter was calculated
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE(plant, report_month)
);
```

### Example Row: BSP Plant Consolidated (June 2026)

```json
{
  "id": 3001,
  "plant": "BSP",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {
      "value": 337.98,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 4,
      "note": "Weighted average of BF-1, BF-2, BF-3, BF-4 using HM Production"
    },
    "BF Productivity": {
      "value": 2.125,
      "unit": "T/m³/day",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 4
    },
    "CDI Rate": {
      "value": 435.65,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 3
    },
    "Fuel Rate": {
      "value": 610.85,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 2
    },
    "O2 Enrichment": {
      "value": 2.6,
      "unit": "%",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 2
    },
    "Sinter in Burden": {
      "value": 41.35,
      "unit": "%",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 2
    },
    "Pellet in Burden": {
      "value": 19.3,
      "unit": "%",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 2
    },
    "Slag Rate": {
      "value": 145.5,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 2
    },
    "Hot Blast Temp": {
      "value": 1235,
      "unit": "°C",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 2
    }
  },
  "calculation_details": {
    "Coke Rate": {
      "formula": "weighted_average",
      "weight_parameter": "HM_Production",
      "calculation": "(300×10000 + 350×11100 + 345×7234 + 357×9879) / (10000+11100+7234+9879)",
      "result": 337.98
    },
    "total_hm_production": 38213,
    "furnaces_in_calculation": ["BF-1", "BF-2", "BF-3", "BF-4"]
  },
  "created_at": "2026-06-20T14:30:00",
  "updated_at": "2026-06-20T14:30:00"
}
```

---

## 🔄 Complete Data Flow

### Step 1: Extract Furnace-Level Data from PDF/Excel
```
PDF/Excel Input (BSP June 2026)
    ↓
Extract:
  - BF-1: Coke=300, HM Prod=10000
  - BF-2: Coke=350, HM Prod=11100
  - BF-3: Coke=345, HM Prod=7234
  - BF-4: Coke=357, HM Prod=9879
    ↓
INSERT INTO techno_furnace_data (4 rows, one per furnace)
```

### Step 2: Calculate Plant-Level Consolidated
```
Query techno_furnace_data for all furnaces of plant "BSP"
    ↓
For each parameter:
  IF parameter has HM Production data for each furnace:
    Calculate weighted_average = Σ(param_value × HM_prod) / Σ(HM_prod)
  ELSE IF parameter exists for all furnaces:
    Calculate simple_average = Σ(param_value) / count
  ELSE:
    Calculate harmonic_mean = n / Σ(1/value)
    ↓
INSERT INTO techno_plant_data (1 row for plant BSP)
```

### Step 3: Calculate SAIL Consolidated (Company-Wide)
```
Query techno_plant_data for all 5 plants
    ↓
For "All 5 Plants" representation:
  Priority 1: Use SAIL direct value if available
  Priority 2: Calculate weighted average of 5 plants
    ↓
UPDATE techno_sail_consolidated
```

---

## 💻 Python Code Examples

### Example 1: Extract Furnace Data from PDF

```python
def extract_furnace_data_from_pdf(pdf_rows, plant, report_month):
    """
    Extract individual furnace data from PDF
    Returns list of furnace records to insert
    """
    
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
        'HM Production': 'T'  # IMPORTANT: Need this for weighting
    }
    
    # Identify furnaces from PDF (BF-1, BF-2, BF-3, BF-4, etc.)
    furnaces = _identify_furnaces(pdf_rows)  # e.g., ["BF-1", "BF-2", "BF-3", "BF-4"]
    
    furnace_records = []
    
    for furnace in furnaces:
        data = {}
        for param, unit in PARAM_UNITS.items():
            value = _extract_param_for_furnace(pdf_rows, furnace, param)
            if value is not None:
                data[param] = {
                    'value': float(value),
                    'unit': unit
                }
        
        furnace_record = {
            'plant': plant,
            'furnace': furnace,
            'report_month': report_month,
            'data': data
        }
        
        furnace_records.append(furnace_record)
    
    return furnace_records


def insert_furnace_data(furnace_records):
    """
    Insert all furnace data into techno_furnace_data table
    """
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    
    for record in furnace_records:
        cursor.execute("""
            INSERT INTO techno_furnace_data (plant, furnace, report_month, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(plant, furnace, report_month) 
            DO UPDATE SET 
                data = excluded.data,
                updated_at = datetime('now')
        """, (
            record['plant'],
            record['furnace'],
            record['report_month'],
            json.dumps(record['data'])
        ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Inserted {len(furnace_records)} furnace records for {record['plant']}")
```

### Example 2: Calculate Plant Consolidated

```python
def calculate_plant_consolidated(plant, report_month):
    """
    Calculate plant-level consolidated data from furnace data
    Uses weighted average with HM Production as weight
    """
    
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Fetch all furnaces for this plant-month
    cursor.execute("""
        SELECT furnace, data
        FROM techno_furnace_data
        WHERE plant = ? AND report_month = ?
    """, [plant, report_month])
    
    furnace_rows = cursor.fetchall()
    
    if not furnace_rows:
        print(f"❌ No furnace data found for {plant} - {report_month}")
        return None
    
    # Parse furnace data
    furnace_data = {}
    for row in furnace_rows:
        furnace_data[row['furnace']] = json.loads(row['data'])
    
    # Get all unique parameters across all furnaces
    all_params = set()
    for f_data in furnace_data.values():
        all_params.update(f_data.keys())
    
    # Calculate plant-level values
    plant_data = {}
    calculation_details = {
        'furnaces_in_calculation': list(furnace_data.keys())
    }
    
    for param in all_params:
        if param == 'HM Production':
            # Don't include HM Production in plant data
            continue
        
        # Collect values and HM production for weighting
        values_with_weights = []
        values_simple = []
        
        for furnace, f_data in furnace_data.items():
            if param in f_data:
                value = f_data[param]['value']
                values_simple.append(value)
                
                # Check if HM Production exists for weighting
                if 'HM Production' in f_data:
                    hm_prod = f_data['HM Production']['value']
                    values_with_weights.append({
                        'value': value,
                        'weight': hm_prod,
                        'furnace': furnace
                    })
        
        if not values_simple:
            continue
        
        # Calculate weighted average
        if values_with_weights and len(values_with_weights) == len(values_simple):
            # All furnaces have HM Production - use weighted average
            total_value = sum(v['value'] * v['weight'] for v in values_with_weights)
            total_weight = sum(v['weight'] for v in values_with_weights)
            result_value = total_value / total_weight
            calc_method = 'weighted_average_by_hm_production'
            
            calculation_details[param] = {
                'formula': 'weighted_average',
                'weight_parameter': 'HM_Production',
                'furnaces_used': [v['furnace'] for v in values_with_weights],
                'total_weight': total_weight,
                'calculation': ' + '.join([f"({v['value']}×{v['weight']})" for v in values_with_weights]) + f" / {total_weight}",
                'result': result_value
            }
        else:
            # Some furnaces missing HM Production - use simple average
            result_value = sum(values_simple) / len(values_simple)
            calc_method = 'simple_average'
            
            calculation_details[param] = {
                'formula': 'simple_average',
                'furnaces_used': [f for f, d in furnace_data.items() if param in d],
                'count': len(values_simple),
                'result': result_value
            }
        
        plant_data[param] = {
            'value': round(result_value, 2),
            'unit': furnace_data[next(iter(furnace_data))][param]['unit'],
            'calculation_method': calc_method,
            'furnaces_used': len(values_simple)
        }
    
    # Insert into techno_plant_data
    cursor.execute("""
        INSERT INTO techno_plant_data (plant, report_month, data, calculation_details, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(plant, report_month) 
        DO UPDATE SET 
            data = excluded.data,
            calculation_details = excluded.calculation_details,
            updated_at = datetime('now')
    """, (plant, report_month, json.dumps(plant_data), json.dumps(calculation_details)))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Plant consolidated calculated for {plant} - {report_month}")
    print(f"   Parameters: {list(plant_data.keys())}")
    print(f"   Calculation: {calc_method}")
    
    return plant_data
```

---

## 🌐 API Endpoints

### Get Furnace Data
```python
@app.get("/api/furnace-data")
async def get_furnace_data(
    plant: str,
    report_month: str,
    furnace: str = ""
):
    """
    Get furnace-level data
    
    Query params:
      - plant: "BSP"
      - report_month: "2026-06"
      - furnace: "BF-1" (optional, if not provided returns all furnaces)
    """
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if furnace:
        cursor.execute("""
            SELECT furnace, data
            FROM techno_furnace_data
            WHERE plant = ? AND report_month = ? AND furnace = ?
        """, [plant, report_month, furnace])
    else:
        cursor.execute("""
            SELECT furnace, data
            FROM techno_furnace_data
            WHERE plant = ? AND report_month = ?
        """, [plant, report_month])
    
    rows = cursor.fetchall()
    conn.close()
    
    result = {}
    for row in rows:
        result[row['furnace']] = json.loads(row['data'])
    
    return result


@app.get("/api/plant-data")
async def get_plant_data(plant: str, report_month: str):
    """
    Get plant consolidated data
    
    Query params:
      - plant: "BSP"
      - report_month: "2026-06"
    """
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT data, calculation_details
        FROM techno_plant_data
        WHERE plant = ? AND report_month = ?
    """, [plant, report_month])
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Data not found")
    
    return {
        'data': json.loads(row['data']),
        'calculation_details': json.loads(row['calculation_details'])
    }
```

---

## 📊 Query Examples

### Get All Furnaces for a Plant-Month
```sql
SELECT furnace, data 
FROM techno_furnace_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
ORDER BY furnace
```

### Get Specific Furnace Data
```sql
SELECT data 
FROM techno_furnace_data 
WHERE plant = 'BSP' AND furnace = 'BF-1' AND report_month = '2026-06'
```

### Get Plant Consolidated Data
```sql
SELECT data, calculation_details 
FROM techno_plant_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

### Compare Furnaces (e.g., Coke Rate)
```sql
SELECT 
  furnace,
  JSON_EXTRACT(data, '$.Coke Rate.value') AS coke_rate,
  JSON_EXTRACT(data, '$.HM Production.value') AS hm_production
FROM techno_furnace_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
ORDER BY furnace
```

### Get Plant Coke Rate with Calculation Method
```sql
SELECT 
  plant,
  report_month,
  JSON_EXTRACT(data, '$.Coke Rate.value') AS coke_rate,
  JSON_EXTRACT(data, '$.Coke Rate.calculation_method') AS method,
  JSON_EXTRACT(calculation_details, '$.Coke Rate.calculation') AS how_calculated
FROM techno_plant_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

---

## 📄 PDF Report Usage

### For PDF MIS Report (Need Plant-Level Only):
```python
def generate_techno_page_pdf(report_month):
    """
    Generate PDF MIS report using plant-level consolidated data
    """
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    
    PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']
    
    page_data = {'month': report_month, 'plants': {}}
    
    for plant in PLANTS:
        cursor.execute("""
            SELECT data, calculation_details
            FROM techno_plant_data
            WHERE plant = ? AND report_month = ?
        """, [plant, report_month])
        
        row = cursor.fetchone()
        if row:
            plant_data = json.loads(row[0])
            page_data['plants'][plant] = plant_data
    
    conn.close()
    
    # Build PDF with plant_data
    # Each plant shows: Coke Rate, BF Productivity, CDI Rate, etc. (all consolidated)
    return page_data
```

---

## 📊 Dashboard Usage

### For Dashboard (Individual Plant):
```python
# Furnace-level drill-down
furnaces_data = fetch_api("/api/furnace-data?plant=BSP&report_month=2026-06")
# Returns: {"BF-1": {data}, "BF-2": {data}, ...}

# Plant-level consolidated
plant_data = fetch_api("/api/plant-data?plant=BSP&report_month=2026-06")
# Returns: {data: {Coke Rate: {value: 337.98, ...}}, calculation_details: {...}}
```

### For Dashboard (All 5 Plants):
```python
# Use SAIL consolidated
sail_data = fetch_api("/api/sail-data?report_month=2026-06")
# Returns: {Coke Rate: 425.1, BF Productivity: 2.16, ...}
```

---

## ✅ Summary

| Level | Table | Purpose | Rows/Month | Query |
|-------|-------|---------|------------|-------|
| **Furnace** | `techno_furnace_data` | Individual furnace metrics | 5 plants × 4-5 furnaces = 25 rows | `plant, furnace, month` |
| **Plant** | `techno_plant_data` | Consolidated from furnaces (weighted avg by HM prod) | 5 plants = 5 rows | `plant, month` |
| **Company** | `techno_sail_consolidated` | SAIL company-wide (existing) | 1 row/month | `month` |

**No separate "Shop" table needed** - Plant table IS the consolidated shop data!

---

## 🎯 Ready to Implement?

1. **Create the two tables** ✅
2. **Update extractors** to extract furnace-wise data ✅
3. **Auto-calculate** plant consolidated on insertion ✅
4. **Update API** endpoints ✅
5. **Update dashboard** to show both furnace and plant levels ✅

Should I start with implementation?
