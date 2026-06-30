# BSL Techno Data Extraction & Display Workflow

## End-to-End Flow

### 1. File Upload (Frontend)
**Page:** Data Entry → Techno Data
**URL:** `localhost:3000/data-entry/techno`

- User selects plant: **BSL**
- User selects month: **May** / **2026**
- User uploads file: **TECHNO APRIL2026.XLS** or **BlastFurnace Apr26.pdf**
- Click: **Extract & Save**

### 2. Preview Extraction (Backend)
**Endpoint:** `POST /api/extract-techno`

**Request:**
```
POST /api/extract-techno
Content-Type: multipart/form-data

file: <TECHNO APRIL2026.XLS>
plant_name: BSL
month: 2026-05
```

**Backend Processing:**
1. Receives file upload
2. Saves temporarily to `/backend/temp/`
3. Detects file type:
   - `.pdf` → BSL BF Performance & Analysis Report
   - `.xls`/`.xlsx` → BSL Techno Excel / DPR / Corp SS Report
4. Loads appropriate extractor:
   - `excel_extractor_bsl.extract_preview(file_path, month)`
5. Extracts parameters according to `_TECHNO_PARAM_MAP`
6. Returns preview with rows like:
   ```json
   {
     "plant": "BSL",
     "month": "2026-05",
     "source_type": "BSL Techno-Economic Parameters",
     "techno_param_rows": [
       {
         "group_code": "IRON_MAKING",
         "section": "BF Productivity",
         "parameter": "BF Productivity",
         "unit": "T/m³/day",
         "actual": 2.24,
         "cum_actual": 2.24,
         "cell": "F33/G33",
         "status": "ok"
       },
       {
         "group_code": "IRON_MAKING",
         "section": "BF Coke Rate",
         "parameter": "BF Coke Rate",
         "unit": "Kg/THM",
         "actual": 407,
         "cum_actual": 407,
         "cell": "F35/G35",
         "status": "ok"
       },
       ...
     ]
   }
   ```

**Response:**
```json
{
  "status": 200,
  "file_name": "TECHNO APRIL2026.XLS",
  "plant": "BSL",
  "month": "2026-05",
  "techno_param_rows": [...]
}
```

### 3. User Reviews Preview (Frontend)
**Component:** Extract Preview Table

Shows:
- Parameter Name
- Unit
- Monthly Actual Value
- Cumulative Value
- Cell Location (e.g., F33)
- Status (ok/skip)

User can:
- Review extracted values
- Correct/edit values if needed
- See any extraction errors

### 4. User Confirms Extraction (Frontend)
**Action:** Click **Confirm & Save** button

Frontend sends:
```
POST /api/techno-entries
Content-Type: application/json

{
  "plant": "BSL",
  "month": "2026-05",
  "file_name": "TECHNO APRIL2026.XLS",
  "rows": [
    {
      "parameter": "BF Productivity",
      "actual": 2.24,
      "cum_actual": 2.24,
      "group_code": "IRON_MAKING",
      "section": "BF Productivity",
      "unit": "T/m³/day"
    },
    {
      "parameter": "BF Coke Rate",
      "actual": 407,
      "cum_actual": 407,
      "group_code": "IRON_MAKING",
      "section": "BF Coke Rate",
      "unit": "Kg/THM"
    },
    ...
  ]
}
```

### 5. Save to Database (Backend)
**Endpoint:** `POST /api/techno-entries`

**Backend Processing:**

1. **New Function:** `db.save_techno_data_from_extraction()`
   - Takes extracted rows
   - Converts parameter names to database keys:
     - "BF Productivity" → `bf_productivity`
     - "BF Coke Rate" → `bf_coke_rate`
     - "CDI Rate" → `cdi_rate`
     - "Coal to Hot Metal" → `coal_to_hot_metal`
     - etc.

2. **Builds JSON Structure:**
   ```json
   {
     "month": {
       "bf_productivity": 2.24,
       "bf_coke_rate": 407,
       "cdi_rate": 125,
       "fuel_rate": 550,
       "coal_to_hot_metal": 0.92,
       "specific_energy_consumption": 5.86,
       "nut_coke_rate": 18,
       "sinter_in_burden": 69.3,
       "pellet_in_burden": 18.2
     },
     "till_month": {
       "bf_productivity": 2.24,
       ... (same as month in this case)
     }
   }
   ```

3. **Saves to Database:**
   - Table: `techno_data`
   - Columns:
     - `plant`: "BSL"
     - `report_month`: "2026-05"
     - `unit`: "BF_Shop"
     - `techno_json`: (JSON string from step 2)
     - `source_file`: "TECHNO APRIL2026.XLS"
     - `created_at`: Current timestamp

4. **Logs Extraction:**
   ```
   db.log_extraction(
     plant="BSL",
     report_month="2026-05",
     file_name="TECHNO APRIL2026.XLS",
     sheet_name="Sheet1/Sheet2/Sheet3/Sheet4",
     source_type="Techno-Economic Parameters",
     items_extracted=45  # number of parameters with data
   )
   ```

### 6. Display on Page 27 (Frontend)
**Page:** Reports → Page 27 (Major Techno-Economic Parameters)
**URL:** `localhost:3000/reports/1?month=2026-05`

**Backend API Call:**
```
GET /api/page/27?month=2026-05
```

**Retrieves:**
1. Plant-wise major parameters from `techno_data` table
2. SAIL consolidated parameters from `techno_plan_fy` table
3. Formatting applied:
   - BF Productivity: 2 decimal places → 2.24
   - Coal to Hot Metal: 3 decimal places → 0.920
   - Others: 0 decimal places → 407, 550, 125, etc.
   - Zero values hidden (not displayed)

**Display Format:**

| Parameters | Shop/Plant | Actual | Target 2026-27 |
|-----------|-----------|--------|----------------|
| BF Productivity (T/m³/day) | BSL | [monthly] | 2.24 |
| | SAIL | [monthly] | 2.24 |
| Coke Rate (kg/thm) | BSL | [monthly] | 407 |
| | SAIL | [monthly] | 400 |
| CDI Rate (kg/thm) | BSL | [monthly] | 125 |
| | SAIL | [monthly] | 120 |
| Coal to Hot Metal (kg/kg) | BSL | [monthly] | 0.92 |
| | SAIL | [monthly] | 0.885 |
| ... | ... | ... | ... |

## Data Persistence

**Database Table:** `techno_data`

```sql
CREATE TABLE techno_data (
  id INTEGER PRIMARY KEY,
  plant TEXT NOT NULL,                 -- "BSL", "BSP", etc.
  report_month TEXT NOT NULL,          -- "2026-05"
  unit TEXT NOT NULL,                  -- "BF_Shop" (shop-level aggregated)
  techno_json TEXT NOT NULL,           -- {"month": {...}, "till_month": {...}}
  source_file TEXT DEFAULT '',         -- "TECHNO APRIL2026.XLS"
  created_at TEXT,                     -- Timestamp
  UNIQUE(plant, report_month, unit)
)
```

## Parameter Key Mapping

### MAJOR Parameters (Page 27)

| Excel Name | Database Key | Page 27 Display | Decimals |
|-----------|-------------|-----------------|----------|
| Coal to Hot Metal | `coal_to_hot_metal` | Coal to Hot Metal (kg/kg) | 3 |
| BF Coke Rate | `bf_coke_rate` | Coke Rate (kg/thm) | 0 |
| Nut Coke Rate | `nut_coke_rate` | Nut Coke Rate (kg/thm) | 0 |
| CDI Rate | `cdi_rate` | CDI Rate (kg/thm) | 0 |
| Fuel Rate | `fuel_rate` | Fuel Rate (kg/thm) | 0 |
| Sinter in Burden | `sinter_in_burden` | Sinter in Burden (%) | 0 |
| Pellet in Burden | `pellet_in_burden` | Pellet in Burden (%) | 0 |
| BF Productivity | `bf_productivity` | BF Productivity (T/m³/day) | 2 |
| Specific Energy Consumption | `specific_energy_consumption` | Specific Energy Consumption (Gcal/tcs) | 2 |

## Troubleshooting

### Extraction Fails
1. Check file format (should be .xls or .xlsx for techno files, .pdf for BF reports)
2. Verify sheets exist: Sheet1, Sheet2, Sheet3, Sheet4, SMS-I, SMS-II (for techno Excel)
3. Check month detection works (auto from O1 or filename)
4. Verify cells have numeric values (not formulas returning #DIV/0! or errors)

### Data Doesn't Appear on Page 27
1. Navigate to Data Entry → Techno Data
2. Check month/year in selector matches extracted month
3. Verify extraction was confirmed (should show "Inserted X values")
4. Check database:
   ```sql
   SELECT * FROM techno_data 
   WHERE plant = 'BSL' 
   AND report_month = '2026-05' 
   AND unit = 'BF_Shop'
   ```
5. Verify JSON has correct keys (lowercase, underscore-separated)

### Values Not Formatted Correctly
1. Check decimal place formatting rules in `_fmt_param()` function
2. Verify parameter names match formatting rules
3. Zero values should be hidden (empty cells)

