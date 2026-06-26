# File Upload Data Flow

Where uploaded files insert data - OLD tables vs NEW JSON tables.

---

## Current Status

### Techno Data (NEW JSON Tables) ✅

When you upload **Techno parameter files**:
- **BSP**: OISCO file, 3-page Techno file
- **DSP, RSP, BSL, ISP**: Techno parameter files

**Data goes to:** NEW JSON tables
```
✓ techno_furnace_data (furnace-level parameters)
✓ techno_plant_data (plant-level consolidated)
```

**Example:** Upload `BSPOISCO_MAY'25.xlsx`
```
→ Extracts Coke Rate, BF Productivity, etc.
→ Separates furnace-level (BF-1, BF-2, etc.) and plant-level data
→ Inserts into techno_furnace_data JSON table
→ Inserts into techno_plant_data JSON table
```

---

### Production Data (OLD Normalized Tables) ⚠️

When you upload **Production volume files**:
- BSP PPC MIS daily reports (`.xls`)
- Production plans
- Special steel orders
- Stock reports
- IPT reports

**Data goes to:** OLD normalized tables
```
✗ production_table (old schema)
✗ production_plan_table (old schema)
✗ special_steel_orders (old schema)
✗ stock_table (old schema)
✗ ipt_table (old schema)
```

**NOT in new JSON tables yet.**

---

## Full Breakdown

### What's Using NEW JSON Tables

| Data Type | File Type | Tables | Status |
|-----------|-----------|--------|--------|
| **Techno Parameters** | Excel (.xlsx) | `techno_furnace_data`, `techno_plant_data` | ✅ NEW tables |
| **Techno SAIL Consolidated** | Calculated | `techno_sail_consolidated` | ✅ NEW table |

### What's Still Using OLD Tables

| Data Type | File Type | Tables | Status |
|-----------|-----------|--------|--------|
| **Production Actuals** | Excel (.xls, .xlsx) | `production_table` | ⚠️ OLD table |
| **Production Plans** | Excel | `production_plan_table` | ⚠️ OLD table |
| **Special Steel** | Excel | `special_steel_orders` | ⚠️ OLD table |
| **Stock Data** | Excel | `stock_table` | ⚠️ OLD table |
| **IPT Data** | Excel | `ipt_table` | ⚠️ OLD table |

---

## Upload Endpoints

### 1. Techno File Upload (→ NEW JSON Tables)

**Endpoint:** `POST /api/upload`

**Supported:**
```
Plant: BSP, DSP, RSP, BSL, ISP
Extractor: oisco (BSP only), techno, rsp
```

**Example:**
```
File: BSPOISCO_MAY'25.xlsx
Plant: BSP
Extractor: oisco
Month: 2025-05

↓
Goes to: techno_furnace_data + techno_plant_data (NEW JSON TABLES)
```

**Form Data:**
```
file: <binary file>
plant: BSP
extractor_type: oisco
report_month: 2025-05
```

**Response:**
```json
{
  "status": "success",
  "message": "Data extracted and inserted",
  "data": {
    "plant": "BSP",
    "month": "2025-05",
    "furnaces_inserted": 7,
    "plant_data": "from_source",
    "parameters_extracted": 35
  }
}
```

### 2. Production File Upload (→ OLD Tables)

**Current Extractors:**
```
BSP PPC MIS daily reports
  → extract_and_save_excel() in excel_extractor_bsp.py
  → INSERT INTO production_table (old schema)
```

**These are NOT yet wired to NEW JSON tables.**

---

## Detailed Flow Diagram

```
┌─────────────────────────────────────────┐
│ USER UPLOADS FILE                       │
└────────────┬────────────────────────────┘
             │
             ├─── Techno Parameter File ───────────┐
             │     (OISCO, BSP-3page, RSP, etc.)   │
             │                                      │
             └──────────────────────────────────────┤
                                                    │
                                           SmartExtractorAdapter
                                                    │
                                           ┌────────┴────────┐
                                           │                 │
                                    NEW JSON Tables    OLD Tables
                                           │                 │
                                    techno_furnace_data      ✗
                                    techno_plant_data        ✗
             │
             ├─── Production File ─────────────────┐
             │     (PPC MIS, Plans, etc.)          │
             │                                      │
             └──────────────────────────────────────┤
                                                    │
                                         Existing Extractors
                                                    │
                                           ┌────────┴────────┐
                                           │                 │
                                        OLD Tables      NEW JSON Tables
                                           │                 │
                                    production_table         ✗
                                    production_plan_table    ✗
                                           │
                                        ✗ NOT YET MIGRATED
```

---

## Production Data Migration Path

To use NEW JSON tables for production data:

### Option 1: Migrate Existing Extractors (Recommended)
```
1. Modify excel_extractor_*.py to call insert_production_data_json()
2. Keep old tables for backward compatibility
3. Gradually transition report generation
```

### Option 2: Create Adapter Layer
```
1. Create production_extractor_adapter.py (like SmartExtractorAdapter)
2. Reuse existing extraction logic
3. Serialize to JSON before inserting
```

### Option 3: Batch Migration Script
```
1. Read all data from old tables
2. Convert to JSON format (already written: json_extractor_adapter.py)
3. Insert into new tables on-demand
```

---

## Current Recommendation

### ✅ For Techno Data:
**Use upload endpoint NOW** - data goes to NEW JSON tables automatically

```bash
# Upload OISCO file for BSP
POST /api/upload
  file: BSPOISCO_MAY'25.xlsx
  plant: BSP
  extractor_type: oisco
  report_month: 2025-05

# Data inserted into:
# - techno_furnace_data (NEW)
# - techno_plant_data (NEW)
```

### ⚠️ For Production Data:
**Still using OLD normalized tables** - existing extractors haven't been updated

**Options:**
1. **Continue with old tables** - extractors work as-is, data in production_table
2. **Migrate with json_extractor_adapter.py** - script to convert old table data to new JSON tables (already created)
3. **Wait for updated extractors** - update extractors to use new JSON tables

---

## Data in Database NOW

### What's in NEW JSON Tables:
```
✅ techno_furnace_data: 17 records (5 plants, 3 months)
✅ techno_plant_data: 7 records (5 plants)
✅ techno_sail_consolidated: ~3 records

✅ production_data_json: 11,231 records (migrated from old table)
✅ production_plan_json: 1,664 records (migrated from old table)
✅ special_steel_json: 678 records (migrated from old table)
✅ stock_data_json: 286 records (migrated from old table)
✅ ipt_data_json: 26 records (migrated from old table)
```

### What's in OLD Normalized Tables:
```
⚠️ production_table: 11,231 records (original data)
⚠️ production_plan_table: 1,664 records (original data)
⚠️ special_steel_orders: 678 records (original data)
⚠️ stock_table: 286 records (original data)
⚠️ ipt_table: 26 records (original data)
```

---

## Uploading NEW Files

### If you upload a Techno file:
```
✅ NEW data goes to: techno_furnace_data, techno_plant_data (JSON tables)
✅ Query via: GET /api/techno-plant-data?plant=BSP&report_month=2025-05
✅ View via: Dashboard with dynamic plant/month selector
```

### If you upload a Production file:
```
✅ NEW data goes to: production_table (old normalized table)
⚠️ NOT automatically in production_data_json (JSON table)
⚠️ Need to run migration script if you want JSON version
```

---

## Migration Scripts Available

If you want to move production data to NEW JSON tables:

### Script 1: json_extractor_adapter.py
```python
from json_extractor_adapter import extract_all_months_to_json

# Converts all old table data to new JSON tables
results = extract_all_months_to_json()
print(f"Production months extracted: {results['production_months']}")
print(f"Plans months extracted: {results['production_plan_months']}")
```

### Script 2: populate_json_schema.py
```bash
python backend/populate_json_schema.py

# Initializes DB + extracts + verifies + generates report
```

---

## Next Steps

### For Techno Data:
✅ **Start uploading now** - everything is wired to use NEW JSON tables

### For Production Data:

**Choose one:**

1. **Option A: Keep using old tables** (no changes needed)
   - Extractors work as-is
   - Old normalized tables work with current dashboard
   - Data is in production_table

2. **Option B: Migrate to new JSON tables** (manual step)
   - Run: `python backend/populate_json_schema.py`
   - Data converts to JSON format
   - New tables populated

3. **Option C: Wait for extractor updates** (future)
   - Will update extractors to use new JSON tables
   - New uploads will go directly to JSON tables

---

## Summary Table

| File Type | Uploaded | Goes To | Table | Format | API |
|-----------|----------|---------|-------|--------|-----|
| Techno params | ✅ YES | NEW | techno_furnace_data | JSON | `/api/techno-*` |
| Production actual | ✅ YES | OLD | production_table | Normalized | (no dedicated API) |
| Production plan | ✅ YES | OLD | production_plan_table | Normalized | (no dedicated API) |
| Special steel | ✅ YES | OLD | special_steel_orders | Normalized | (no dedicated API) |
| Stock | ✅ YES | OLD | stock_table | Normalized | (no dedicated API) |
| IPT | ✅ YES | OLD | ipt_table | Normalized | (no dedicated API) |

---

## Clarification

**Q: Do production data uploads go to NEW JSON tables?**
A: No, not yet. They still go to OLD normalized tables. The NEW JSON tables are populated via migration script only.

**Q: Can I query production data via API?**
A: Via old normalized table queries only. The NEW JSON tables exist but extractors haven't been updated to populate them on upload.

**Q: Should I migrate production data now?**
A: Recommended:
- Run `populate_json_schema.py` once to create initial JSON versions
- Use both old + new tables during transition
- Update extractors gradually, one file type at a time
- Test report generation with new tables before deprecating old ones
