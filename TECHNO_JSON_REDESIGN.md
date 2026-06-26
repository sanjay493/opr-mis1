# Techno Database Redesign - Option 3: JSON-Based Single Table Architecture

## 📋 Executive Summary

**Current Pain Points:**
- 5+ tables with complex JOINs
- Adding new parameters requires schema changes
- Units not stored with values
- Difficult to track data quality/source

**New Solution:**
- 2 tables instead of 5+
- JSON columns store parameters and units
- Metadata for audit trail
- Flexible for future expansion

---

## 🏗️ Part 1: Database Schema Design

### Table 1: `techno_data` (Individual Plant Data)

```sql
CREATE TABLE techno_data (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant TEXT NOT NULL,                    -- "BSP", "DSP", "RSP", "BSL", "ISP"
  report_month TEXT NOT NULL,             -- "2026-06" (YYYY-MM format)
  
  data JSON NOT NULL,                     -- Main data: {param: {value, unit}}
  metadata JSON,                          -- Source, quality, extraction details
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE(plant, report_month)
);
```

### Table 2: `techno_sail_consolidated` (Company-wide Consolidated Data)

```sql
CREATE TABLE techno_sail_consolidated (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_month TEXT NOT NULL PRIMARY KEY, -- "2026-06" (YYYY-MM format)
  
  data JSON NOT NULL,                     -- {param: value} (no units, already SAIL value)
  calculation_method JSON,                -- {param: "SAIL_direct" | "avg_5_plants"}
  last_updated DATETIME,
  
  UNIQUE(report_month)
);
```

---

## 📊 Part 2: Schema Examples with Real Data

### Example 1: BSP Data from PDF (June 2026)

**Table: `techno_data`**
```json
{
  id: 101,
  plant: "BSP",
  report_month: "2026-06",
  data: {
    "Coke Rate": {
      value: 425.5,
      unit: "Kg/THM"
    },
    "BF Productivity": {
      value: 2.15,
      unit: "T/m³/day"
    },
    "CDI Rate": {
      value: 435.2,
      unit: "Kg/THM"
    },
    "Fuel Rate": {
      value: 610.8,
      unit: "Kg/THM"
    },
    "O2 Enrichment": {
      value: 2.5,
      unit: "%"
    },
    "Sinter in Burden": {
      value: 42.3,
      unit: "%"
    },
    "Pellet in Burden": {
      value: 18.5,
      unit: "%"
    },
    "BF Coke Rate": {
      value: 438.2,
      unit: "Kg/THM"
    },
    "Slag Rate": {
      value: 145.8,
      unit: "Kg/THM"
    },
    "Hot Blast Temp": {
      value: 1235,
      unit: "°C"
    }
  },
  metadata: {
    source: "PDF",
    source_file: "BSP_June_2026.pdf",
    extraction_date: "2026-06-20T14:30:00",
    extraction_method: "pdf_extractor_bsp",
    quality: "extracted",
    furnaces: ["BF-1", "BF-2", "BF-3"],
    extracted_by: "system",
    confidence_score: 0.95
  },
  created_at: "2026-06-20T14:30:00",
  updated_at: "2026-06-20T14:30:00"
}
```

### Example 2: DSP Data from Excel (June 2026)

**Table: `techno_data`**
```json
{
  id: 102,
  plant: "DSP",
  report_month: "2026-06",
  data: {
    "Coke Rate": {
      value: 422.1,
      unit: "Kg/THM"
    },
    "BF Productivity": {
      value: 2.18,
      unit: "T/m³/day"
    },
    "CDI Rate": {
      value: 440.5,
      unit: "Kg/THM"
    },
    "Fuel Rate": {
      value: 615.2,
      unit: "Kg/THM"
    },
    "O2 Enrichment": {
      value: 2.8,
      unit: "%"
    },
    "Sinter in Burden": {
      value: 41.5,
      unit: "%"
    },
    "Pellet in Burden": {
      value: 19.2,
      unit: "%"
    },
    "BF Coke Rate": {
      value: 436.8,
      unit: "Kg/THM"
    },
    "Slag Rate": {
      value: 148.2,
      unit: "Kg/THM"
    }
  },
  metadata: {
    source: "EXCEL",
    source_file: "DSP_TechnoData_June2026.xlsx",
    extraction_date: "2026-06-21T10:15:00",
    extraction_method: "excel_extractor_dsp",
    quality: "extracted",
    furnaces: ["BF-2", "BF-3", "BF-4"],
    extracted_by: "system",
    data_entry_by: "dsp_operator",
    confidence_score: 0.92
  },
  created_at: "2026-06-21T10:15:00",
  updated_at: "2026-06-21T10:15:00"
}
```

### Example 3: SAIL Consolidated Data (June 2026)

**Table: `techno_sail_consolidated`**
```json
{
  id: 201,
  report_month: "2026-06",
  data: {
    "Coke Rate": 425.1,
    "BF Productivity": 2.16,
    "CDI Rate": 437.8,
    "Fuel Rate": 612.1,
    "O2 Enrichment": 2.6,
    "Sinter in Burden": 42.0,
    "Pellet in Burden": 18.8,
    "BF Coke Rate": 437.5,
    "Slag Rate": 147.0,
    "Hot Blast Temp": 1240
  },
  calculation_method: {
    "Coke Rate": "avg_5_plants",
    "BF Productivity": "avg_5_plants",
    "CDI Rate": "SAIL_direct",
    "Fuel Rate": "avg_5_plants"
  },
  last_updated: "2026-06-21T16:45:00"
}
```

---

## 🔄 Part 3: Complete Workflow - Extraction to Display

### Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
├─────────────────────────────────────────────────────────────────┤
│  PDF Files           │  Excel Files          │  Manual Entry    │
│  BSP_June_2026.pdf   │  DSP_TechnoData.xlsx  │  Portal Form     │
│  RSP_June_2026.pdf   │  RSP_June_2026.xlsx   │  (Direct Insert) │
└────────┬─────────────┴──────────────┬────────┴─────────┬────────┘
         │                            │                   │
         ▼                            ▼                   ▼
┌──────────────────┐    ┌──────────────────┐  ┌──────────────────┐
│ PDF Extractors   │    │ Excel Extractors │  │ API Insert       │
│ • pdf_extractor_ │    │ • excel_extractor│  │ Endpoint         │
│   bsp.py         │    │   _bsp.py        │  │ POST /api/techno │
│ • pdf_extractor_ │    │ • excel_extractor│  │ -data-insert     │
│   dsp.py         │    │   _dsp.py        │  │                  │
│ • pdf_extractor_ │    │ • excel_extractor│  │                  │
│   rsp.py         │    │   _rsp.py        │  │                  │
└────────┬─────────┘    └────────┬─────────┘  └────────┬─────────┘
         │                       │                      │
         └───────────┬───────────┴──────────┬──────────┘
                     ▼
        ┌────────────────────────────────┐
        │ Extract → JSON Conversion      │
        │ (Transform to JSON format)     │
        └────────────┬───────────────────┘
                     ▼
        ┌────────────────────────────────┐
        │ INSERT/UPDATE techno_data      │
        │ (One row per plant-month)      │
        │                                │
        │ UPSERT plant + report_month    │
        │ (Update if exists, insert new) │
        └────────────┬───────────────────┘
                     ▼
        ┌────────────────────────────────┐
        │ Calculate SAIL Consolidated    │
        │ (Aggregate 5 plants)           │
        │                                │
        │ Priority 1: Check SAIL value   │
        │ Priority 2: Average 5 plants   │
        └────────────┬───────────────────┘
                     ▼
        ┌────────────────────────────────┐
        │ UPDATE techno_sail_consolidated│
        │ (One row per report_month)     │
        └────────────┬───────────────────┘
                     ▼
        ┌────────────────────────────────┐
        │ RETRIEVE for Different Uses:   │
        ├────────────────────────────────┤
        │ 1. PDF MIS Report Generation   │
        │    → SELECT * FROM techno_sail │
        │    → Extract SAIL values       │
        │                                │
        │ 2. Dashboard Display           │
        │    → SELECT * FROM techno_data │
        │    → WHERE plant IN (...)      │
        │    → Format for table/charts   │
        │                                │
        │ 3. Comparison Reports          │
        │    → SELECT all 5 plants       │
        │    → JOIN with SAIL data       │
        │    → Calculate variance        │
        └────────────┬───────────────────┘
                     ▼
        ┌────────────────────────────────┐
        │ OUTPUT FORMATS                 │
        ├────────────────────────────────┤
        │ • PDF MIS Report               │
        │ • Dashboard Tables             │
        │ • Dashboard Charts             │
        │ • Export to Excel              │
        │ • API Response (JSON)          │
        └────────────────────────────────┘
```

---

## 💻 Part 4: Python Extraction Code

### Example 1: PDF Extraction to JSON

```python
# backend/excel_extractors/pdf_extractor_bsp.py

def extract_to_json(pdf_rows, report_month):
    """
    Extract BSP PDF data and convert to JSON format for techno_data table
    
    Args:
        pdf_rows: List of extracted rows from PDF
        report_month: "2026-06"
    
    Returns:
        {
            'plant': 'BSP',
            'report_month': '2026-06',
            'data': {...},
            'metadata': {...}
        }
    """
    
    # Parameter mapping with units
    PARAM_UNITS = {
        'Coke Rate': 'Kg/THM',
        'BF Productivity': 'T/m³/day',
        'CDI Rate': 'Kg/THM',
        'Fuel Rate': 'Kg/THM',
        'O2 Enrichment': '%',
        'Sinter in Burden': '%',
        'Pellet in Burden': '%',
        'BF Coke Rate': 'Kg/THM',
        'Slag Rate': 'Kg/THM',
        'Hot Blast Temp': '°C'
    }
    
    # Extract values from PDF
    data = {}
    for param, unit in PARAM_UNITS.items():
        value = _extract_param_from_pdf(pdf_rows, param)
        if value is not None:
            data[param] = {
                'value': float(value),
                'unit': unit
            }
    
    # Build JSON object
    json_data = {
        'plant': 'BSP',
        'report_month': report_month,
        'data': data,
        'metadata': {
            'source': 'PDF',
            'source_file': 'BSP_June_2026.pdf',
            'extraction_date': datetime.now().isoformat(),
            'extraction_method': 'pdf_extractor_bsp',
            'quality': 'extracted',
            'furnaces': ['BF-1', 'BF-2', 'BF-3'],
            'extracted_by': 'system',
            'confidence_score': 0.95
        }
    }
    
    return json_data


def insert_to_techno_data(json_data):
    """
    Insert or update techno_data table with JSON data
    """
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    
    # UPSERT: Update if exists, insert if new
    cursor.execute("""
        INSERT INTO techno_data (plant, report_month, data, metadata, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(plant, report_month) 
        DO UPDATE SET 
            data = excluded.data,
            metadata = excluded.metadata,
            updated_at = datetime('now')
    """, (
        json_data['plant'],
        json_data['report_month'],
        json.dumps(json_data['data']),
        json.dumps(json_data['metadata'])
    ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Inserted/Updated {json_data['plant']} data for {json_data['report_month']}")
```

### Example 2: Excel Extraction to JSON

```python
# backend/excel_extractors/excel_extractor_dsp.py

def extract_to_json(excel_data, report_month):
    """
    Extract DSP Excel data and convert to JSON format
    """
    
    PARAM_UNITS = {
        'Coke Rate': 'Kg/THM',
        'BF Productivity': 'T/m³/day',
        'CDI Rate': 'Kg/THM',
        'Fuel Rate': 'Kg/THM',
        'O2 Enrichment': '%',
        'Sinter in Burden': '%',
        'Pellet in Burden': '%',
        'BF Coke Rate': 'Kg/THM',
        'Slag Rate': 'Kg/THM'
    }
    
    # Extract from Excel cells
    data = {}
    for param, unit in PARAM_UNITS.items():
        value = excel_data.get(param)
        if value is not None:
            data[param] = {
                'value': float(value),
                'unit': unit
            }
    
    json_data = {
        'plant': 'DSP',
        'report_month': report_month,
        'data': data,
        'metadata': {
            'source': 'EXCEL',
            'source_file': 'DSP_TechnoData_June2026.xlsx',
            'extraction_date': datetime.now().isoformat(),
            'extraction_method': 'excel_extractor_dsp',
            'quality': 'extracted',
            'furnaces': ['BF-2', 'BF-3', 'BF-4'],
            'extracted_by': 'system',
            'data_entry_by': 'dsp_operator',
            'confidence_score': 0.92
        }
    }
    
    return json_data
```

### Example 3: Calculate SAIL Consolidated

```python
# backend/sail_utils.py

def calculate_sail_consolidated(report_month):
    """
    Calculate SAIL consolidated values for a report month
    Priority 1: Direct SAIL values (if they exist in PDF)
    Priority 2: Average of 5 plants
    """
    
    conn = sqlite3.connect(db.DB_PATH)
    cursor = conn.cursor()
    
    PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']
    
    # Fetch all 5 plants' data for this month
    cursor.execute("""
        SELECT plant, data 
        FROM techno_data 
        WHERE report_month = ? AND plant IN (?, ?, ?, ?, ?)
    """, [report_month] + PLANTS)
    
    rows = cursor.fetchall()
    plants_data = {row[0]: json.loads(row[1]) for row in rows}
    
    # Build SAIL consolidated data
    sail_data = {}
    calculation_method = {}
    
    # Get list of all parameters across all plants
    all_params = set()
    for plant_data in plants_data.values():
        all_params.update(plant_data.keys())
    
    for param in all_params:
        # Try to get SAIL direct value (if parameter exists with SAIL row label)
        cursor.execute("""
            SELECT ta.actual
            FROM techno_actuals ta
            JOIN techno_param tp ON ta.param_id = tp.param_id
            WHERE ta.report_month = ? 
              AND tp.row_label = 'SAIL'
              AND tp.param_name = ?
        """, [report_month, param])
        
        sail_value_row = cursor.fetchone()
        
        if sail_value_row and sail_value_row[0] is not None:
            # Use SAIL direct value
            sail_data[param] = float(sail_value_row[0])
            calculation_method[param] = 'SAIL_direct'
        else:
            # Calculate average of 5 plants
            values = []
            for plant in PLANTS:
                if plant in plants_data and param in plants_data[plant]:
                    values.append(plants_data[plant][param]['value'])
            
            if values:
                sail_data[param] = round(sum(values) / len(values), 2)
                calculation_method[param] = 'avg_5_plants'
    
    # Insert/Update SAIL consolidated data
    cursor.execute("""
        INSERT INTO techno_sail_consolidated (report_month, data, calculation_method, last_updated)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(report_month)
        DO UPDATE SET
            data = excluded.data,
            calculation_method = excluded.calculation_method,
            last_updated = datetime('now')
    """, (report_month, json.dumps(sail_data), json.dumps(calculation_method)))
    
    conn.commit()
    conn.close()
    
    print(f"✅ SAIL consolidated data calculated for {report_month}")
    
    return sail_data
```

---

## 🌐 Part 5: API Endpoints

### Endpoint 1: Insert/Update Techno Data

```python
@app.post("/api/techno-data-insert")
async def insert_techno_data(payload: dict):
    """
    Insert or update techno data from extraction
    
    Request body:
    {
        "plant": "BSP",
        "report_month": "2026-06",
        "data": {
            "Coke Rate": {"value": 425.5, "unit": "Kg/THM"},
            "BF Productivity": {"value": 2.15, "unit": "T/m³/day"}
        },
        "metadata": {
            "source": "PDF",
            "source_file": "BSP_June_2026.pdf",
            ...
        }
    }
    """
    try:
        plant = payload['plant']
        report_month = payload['report_month']
        data = payload['data']
        metadata = payload['metadata']
        
        conn = sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO techno_data (plant, report_month, data, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(plant, report_month)
            DO UPDATE SET
                data = excluded.data,
                metadata = excluded.metadata,
                updated_at = datetime('now')
        """, (plant, report_month, json.dumps(data), json.dumps(metadata)))
        
        conn.commit()
        
        # Recalculate SAIL consolidated data
        calculate_sail_consolidated(report_month)
        
        conn.close()
        
        return {"status": "ok", "message": f"Data inserted for {plant} - {report_month}"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/techno-data-retrieve")
async def retrieve_techno_data(plant: str = "", report_month: str = ""):
    """
    Retrieve techno data for dashboard or report generation
    
    Query params:
      - plant: "BSP" or "SAIL" (for consolidated)
      - report_month: "2026-06"
    
    Response:
    {
        "plant": "BSP",
        "report_month": "2026-06",
        "data": {
            "Coke Rate": {"value": 425.5, "unit": "Kg/THM"},
            ...
        },
        "metadata": {...}
    }
    """
    try:
        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if plant.upper() == "SAIL":
            # Get SAIL consolidated data
            cursor.execute("""
                SELECT report_month, data, calculation_method, last_updated
                FROM techno_sail_consolidated
                WHERE report_month = ?
            """, [report_month])
        else:
            # Get individual plant data
            cursor.execute("""
                SELECT plant, report_month, data, metadata, created_at, updated_at
                FROM techno_data
                WHERE plant = ? AND report_month = ?
            """, [plant, report_month])
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Data not found")
        
        # Convert JSON strings back to dicts
        if plant.upper() == "SAIL":
            return {
                "report_month": row['report_month'],
                "data": json.loads(row['data']),
                "calculation_method": json.loads(row['calculation_method']),
                "last_updated": row['last_updated']
            }
        else:
            return {
                "plant": row['plant'],
                "report_month": row['report_month'],
                "data": json.loads(row['data']),
                "metadata": json.loads(row['metadata']),
                "created_at": row['created_at'],
                "updated_at": row['updated_at']
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 📄 Part 6: PDF Report Generation

### Generate MIS Report using SAIL Data

```python
# backend/page_techno_json.py

def generate_techno_page(report_month):
    """
    Generate PDF MIS report using JSON-based SAIL consolidated data
    """
    
    # Retrieve SAIL consolidated data
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT data, calculation_method, last_updated
        FROM techno_sail_consolidated
        WHERE report_month = ?
    """, [report_month])
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"status": "error", "message": "No SAIL data found"}
    
    sail_data = json.loads(row['data'])
    calculation_method = json.loads(row['calculation_method'])
    
    # Build page content
    page_data = {
        'report_month': report_month,
        'parameters': []
    }
    
    # Map to page sections (as per MIS report structure)
    sections = {
        'Iron Making': [
            'Coke Rate',
            'BF Productivity',
            'CDI Rate',
            'Fuel Rate',
            'O2 Enrichment',
            'Sinter in Burden',
            'Pellet in Burden'
        ],
        'Blast Furnace': [
            'BF Coke Rate',
            'Slag Rate',
            'Hot Blast Temp'
        ],
        'Steel Making': [
            'SMS Productivity',
            'Oxygen Consumption',
            'Refractory Consumption'
        ]
    }
    
    for section, params in sections.items():
        section_data = {
            'section': section,
            'parameters': []
        }
        
        for param in params:
            if param in sail_data:
                value = sail_data[param]
                method = calculation_method.get(param, 'unknown')
                
                section_data['parameters'].append({
                    'name': param,
                    'value': value,
                    'method': method,
                    'source': 'SAIL_direct' if method == 'SAIL_direct' else '5_plant_avg'
                })
        
        if section_data['parameters']:
            page_data['parameters'].append(section_data)
    
    return page_data
```

---

## 📊 Part 7: Dashboard Retrieval

### Retrieve Data for Dashboard Display

```python
# backend/api_dashboard.py

@app.get("/api/dashboard/techno")
async def get_dashboard_techno(
    plants: str = "BSP,DSP,RSP,BSL,ISP",
    report_month: str = "2026-06"
):
    """
    Retrieve all techno data for dashboard display
    Returns data for all selected plants + SAIL consolidated
    """
    
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    plant_list = plants.split(',')
    
    result = {
        'report_month': report_month,
        'individual_plants': {},
        'sail_consolidated': {}
    }
    
    # Get individual plant data
    for plant in plant_list:
        cursor.execute("""
            SELECT data, metadata
            FROM techno_data
            WHERE plant = ? AND report_month = ?
        """, [plant.strip(), report_month])
        
        row = cursor.fetchone()
        if row:
            result['individual_plants'][plant.strip()] = {
                'data': json.loads(row['data']),
                'metadata': json.loads(row['metadata'])
            }
    
    # Get SAIL consolidated data
    cursor.execute("""
        SELECT data, calculation_method
        FROM techno_sail_consolidated
        WHERE report_month = ?
    """, [report_month])
    
    row = cursor.fetchone()
    if row:
        result['sail_consolidated'] = {
            'data': json.loads(row['data']),
            'calculation_method': json.loads(row['calculation_method'])
        }
    
    conn.close()
    
    return result


# Frontend usage example (React)
async function loadDashboardData(month) {
    const res = await fetch(
        `/api/dashboard/techno?plants=BSP,DSP,RSP,BSL,ISP&report_month=${month}`
    );
    const data = await res.json();
    
    // For "All 5 Plants" view, use SAIL consolidated
    displaySAILData(data.sail_consolidated.data);
    
    // For individual plant views
    displayIndividualPlants(data.individual_plants);
}
```

---

## 🔄 Part 8: Data Update Scenarios

### Scenario 1: New Month Data Arrives

```
1. BSP PDF arrives on June 20
   → extract_to_json() → {plant: "BSP", data: {...}}
   → insert_to_techno_data() → INSERT INTO techno_data
   → calculate_sail_consolidated("2026-06")
   
2. DSP Excel arrives on June 21
   → extract_to_json() → {plant: "DSP", data: {...}}
   → insert_to_techno_data() → UPDATE techno_data (UPSERT)
   → calculate_sail_consolidated("2026-06") [Recalculates with 2 plants]
   
3. RSP PDF arrives on June 22
   → extract_to_json() → {plant: "RSP", data: {...}}
   → insert_to_techno_data() → INSERT INTO techno_data
   → calculate_sail_consolidated("2026-06") [Recalculates with 3 plants]
   
4. ... Continues for all 5 plants
   
5. SAIL consolidated has all 5 plants = Final consolidated values ready
```

### Scenario 2: Data Correction (Update)

```
Original: BSP Coke Rate = 425.5
Correction: BSP Coke Rate = 426.2 (manual correction)

1. API receives corrected data
2. UPSERT updates the existing row:
   UPDATE techno_data 
   SET data = {...}, metadata = {...}, updated_at = now()
   WHERE plant = "BSP" AND report_month = "2026-06"

3. Recalculate SAIL (SAIL average now includes corrected value)
4. Previous "SAIL" row updated with new averages
```

### Scenario 3: Missing SAIL Value, Calculate from Plants

```
If SAIL direct value not found in PDF:
1. check_sail_direct_value("CDI Rate", "2026-06") → NULL
2. Calculate average: (BSP + DSP + RSP + BSL + ISP) / 5
3. Store in calculation_method: "avg_5_plants"
4. Next month when SAIL appears: Update to "SAIL_direct"
```

---

## 📈 Part 9: Benefits Summary

| Aspect | Old (Multi-Table) | New (JSON) |
|--------|-------------------|-----------|
| **Tables** | 5+ (techno_param, techno_actuals, etc.) | 2 (techno_data, techno_sail) |
| **Queries** | 3-4 JOINs | Direct JSON access |
| **Add Parameter** | Modify schema ❌ | Add to JSON ✅ |
| **Extraction** | Complex mapping → Normal form | Simple → JSON format |
| **SAIL Calculation** | Complex aggregations | Simple averaging |
| **PDF Report** | Join 5 tables | Query 1 row (SAIL) |
| **Dashboard** | Query multiple sources | Single API endpoint |
| **Update Speed** | Multiple updates needed | Single row UPSERT |
| **Data Quality** | Not tracked | Tracked in metadata |
| **Flexibility** | Low | High |

---

## ✅ Implementation Checklist

- [ ] Create two new tables (techno_data, techno_sail_consolidated)
- [ ] Migrate existing data to new format
- [ ] Update PDF extractors to use new format
- [ ] Update Excel extractors to use new format
- [ ] Create SAIL calculation function
- [ ] Update API endpoints for new schema
- [ ] Update PDF report generation
- [ ] Update dashboard to use new API
- [ ] Update database connection in db.py
- [ ] Test end-to-end: Extract → Store → Retrieve → Display

---

## 🎯 Next Steps

1. **Confirm this design** - Does this fit your workflow?
2. **Migration Plan** - How to move existing data?
3. **Implementation** - Start with table creation?
4. **Timeline** - Phase it in or big-bang?

Would you like me to help with any of these steps?
