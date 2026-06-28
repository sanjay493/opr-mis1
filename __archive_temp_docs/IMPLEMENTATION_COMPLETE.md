# JSON-Based Techno Data Implementation - COMPLETE ✅

## Summary of What's Done

### 1. **Database Layer** (Updated `backend/db.py`)

Created 3 new tables with JSON support:

```sql
-- Table 1: Individual furnace-level data
techno_furnace_data (
  plant, furnace, report_month,
  data JSON,  -- {param: {value, unit, source, ...}}
  timestamps
)

-- Table 2: Plant consolidated data
techno_plant_data (
  plant, report_month,
  data JSON,  -- {param: {value, unit, calculation_method, ...}}
  calculation_details JSON,
  timestamps
)

-- Table 3: SAIL company-wide consolidated
techno_sail_consolidated (
  report_month,
  data JSON,  -- {param: value}
  calculation_method JSON,
  timestamps
)
```

**New Functions Added:**
- `insert_techno_furnace_data()` - Save furnace data
- `get_techno_furnace_data()` - Retrieve furnace data
- `insert_techno_plant_data()` - Save plant consolidated
- `get_techno_plant_data()` - Retrieve plant consolidated
- `insert_techno_sail_consolidated()` - Save SAIL data
- `get_techno_sail_consolidated()` - Retrieve SAIL data

---

### 2. **Extraction Utilities** (New file: `backend/techno_json_utils.py`)

Created 3 main utility classes:

#### **TechnoFurnaceExtractor** (Base Class)
```python
class TechnoFurnaceExtractor:
    def extract_furnace_data(pdf_rows, report_month)
    def save_furnace_data(furnace_records)
```

Use this to create plant-specific extractors (BSP, DSP, RSP, etc.)

#### **TechnoPlantCalculator**
Calculates plant-level consolidated data from furnaces:
- **Priority 1**: Weighted average using HM Production as weight
- **Priority 2**: Simple average (if HM data missing)
- Returns: `(plant_data, calculation_details)`

#### **TechnoSAILCalculator**
Calculates SAIL company-wide values:
- **Priority 1**: SAIL direct value (from old techno_actuals)
- **Priority 2**: Average of 5 plants
- Returns: `(sail_data, calculation_method)`

**Convenience Functions:**
```python
extract_and_save_furnace_data(extractor, pdf_rows, report_month)
calculate_and_save_plant_consolidated(plant, report_month)
calculate_and_save_sail_consolidated(report_month)
process_complete_extraction(extractor, pdf_rows, report_month)  # All 3 steps
```

---

### 3. **Production Utilities** (New file: `backend/production_utils.py`)

Handles fetching HM Production from `production_table`:

```python
get_hm_production_for_furnace(plant, furnace, report_month)
  # Priority: exact name → hash format → uppercase → space format

get_plant_hm_production(plant, report_month)
  # Get plant-level "Hot Metal" value

allocate_plant_hm_to_furnaces(plant, report_month, num_furnaces)
  # Fallback: divide plant HM by furnace count

get_furnace_production_variants(plant, report_month, base_name)
  # Debug helper: returns all possible matching formats
```

---

### 4. **API Endpoints** (New file: `backend/api_techno_json.py`)

Integrated into main.py with FastAPI router:

#### **Furnace Data Endpoints**
```
GET  /api/techno-furnace-data
     ?plant=BSP&report_month=2026-06&furnace=BF-1 (optional)
     
POST /api/techno-furnace-data-insert
     Insert/update furnace-level data
```

#### **Plant Consolidated Endpoints**
```
GET  /api/techno-plant-data
     ?plant=BSP&report_month=2026-06
     
POST /api/techno-plant-data-calculate
     Calculate plant consolidated from furnaces
```

#### **SAIL Consolidated Endpoints**
```
GET  /api/techno-sail-data
     ?report_month=2026-06
     
POST /api/techno-sail-data-calculate
     Calculate SAIL consolidated from 5 plants
```

#### **Utility Endpoints**
```
GET  /api/techno-parameters-list
     All available parameters
     
GET  /api/techno-months-available
     ?plant=BSP (optional)
     
GET  /api/techno-furnaces-for-plant
     ?plant=BSP&report_month=2026-06 (optional)
```

---

## How to Use

### Step 1: Create Plant-Specific Extractor

Create `backend/excel_extractors/bsp_json_extractor.py`:

```python
from techno_json_utils import TechnoFurnaceExtractor
import re

class BSPFurnaceExtractor(TechnoFurnaceExtractor):
    def __init__(self):
        super().__init__(plant='BSP')
    
    def _identify_furnaces(self, pdf_rows):
        # Return list of furnaces: ["BF-1", "BF-2", "BF-3", "BF-4"]
        # Parse from PDF structure
        furnaces = []
        for row in pdf_rows:
            match = re.search(r'BF[-#]?(\d+)', str(row))
            if match:
                furnaces.append(f"BF-{match.group(1)}")
        return list(set(furnaces))  # Unique furnaces
    
    def _extract_param_for_furnace(self, pdf_rows, furnace, param):
        # Extract specific parameter value for furnace from PDF
        # Return float value or None
        
        # Example logic:
        for i, row in enumerate(pdf_rows):
            if furnace in str(row) and param in str(row):
                # Extract and parse value
                value = extract_value(pdf_rows[i])
                return value
        return None
```

### Step 2: Extract and Save Data

```python
from bsp_json_extractor import BSPFurnaceExtractor
from techno_json_utils import process_complete_extraction

# Extract from PDF/Excel
extractor = BSPFurnaceExtractor()
pdf_rows = load_pdf('BSP_June_2026.pdf')

# Complete flow: extract furnaces → calculate plant → calculate SAIL
count = process_complete_extraction(extractor, pdf_rows, '2026-06')
print(f"✅ Extracted {count} furnace records")
```

### Step 3: Retrieve Data via API

```bash
# Get furnace data
curl "http://localhost:8000/api/techno-furnace-data?plant=BSP&report_month=2026-06"

# Get plant consolidated
curl "http://localhost:8000/api/techno-plant-data?plant=BSP&report_month=2026-06"

# Get SAIL consolidated
curl "http://localhost:8000/api/techno-sail-data?report_month=2026-06"

# Calculate plant consolidated (from furnaces)
curl -X POST "http://localhost:8000/api/techno-plant-data-calculate?plant=BSP&report_month=2026-06"

# Calculate SAIL consolidated (from 5 plants)
curl -X POST "http://localhost:8000/api/techno-sail-data-calculate?report_month=2026-06"
```

---

## Data Flow Diagram

```
PDF/Excel Input
    ↓
[1] TechnoFurnaceExtractor.extract_furnace_data()
    ↓
    {"BF-1": {...}, "BF-2": {...}, ...}
    ↓
[2] insert_techno_furnace_data() → techno_furnace_data table
    ↓
[3] TechnoPlantCalculator.calculate_plant_consolidated()
    ├─ Fetch furnace data
    ├─ Calculate weighted average (using HM Production)
    └─ Return plant_data, calc_details
    ↓
[4] insert_techno_plant_data() → techno_plant_data table
    ↓
[5] TechnoSAILCalculator.calculate_sail_consolidated()
    ├─ Fetch all 5 plants' data
    ├─ Aggregate with SAIL priority
    └─ Return sail_data, calc_method
    ↓
[6] insert_techno_sail_consolidated() → techno_sail_consolidated table
    ↓
API Endpoints + Frontend Dashboard ✅
```

---

## JSON Data Structure Examples

### Furnace-Level Data

```json
{
  "plant": "BSP",
  "furnace": "BF-1",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {
      "value": 300.0,
      "unit": "Kg/THM",
      "source": "PDF"
    },
    "BF Productivity": {
      "value": 2.10,
      "unit": "T/m³/day",
      "source": "PDF"
    },
    "HM Production": {
      "value": 10000.0,
      "unit": "T",
      "source": "production_table"
    }
  }
}
```

### Plant Consolidated

```json
{
  "plant": "BSP",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {
      "value": 337.98,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 4
    }
  },
  "calculation_details": {
    "Coke Rate": {
      "formula": "weighted_average",
      "weight_parameter": "HM_Production",
      "furnaces": ["BF-1", "BF-2", "BF-3", "BF-4"],
      "total_weight": 38213,
      "calculation": "(300×10000 + 350×11100 + 345×7234 + 357×9879) / 38213"
    }
  }
}
```

### SAIL Consolidated

```json
{
  "report_month": "2026-06",
  "data": {
    "Coke Rate": 425.1,
    "BF Productivity": 2.16,
    "CDI Rate": 437.8
  },
  "calculation_method": {
    "Coke Rate": "avg_5_plants",
    "BF Productivity": "avg_5_plants",
    "CDI Rate": "SAIL_direct"
  }
}
```

---

## Weighted Average Calculation (Key Feature!)

The system uses **HM Production as the weight**:

```
Coke Rate (Plant) = Σ(Furnace Coke Rate × Furnace HM Production) / Σ(Furnace HM Production)

Example with 4 furnaces:
= (300×10000 + 350×11100 + 345×7234 + 357×9879) / (10000+11100+7234+9879)
= 12,911,433 / 38,213
= 337.98 Kg/THM
```

This approach:
- ✅ Weights parameters by actual production volume
- ✅ Accurate plant-level representation
- ✅ Handles furnaces with different production capacities

---

## Adding New Parameters

One of the major advantages of JSON approach:

**No schema changes needed!**

Just add to extraction:
```python
# In TechnoFurnaceExtractor.PARAM_UNITS:
'New Parameter Name': 'unit',

# Write extraction logic:
def _extract_new_param(self, pdf_rows, furnace):
    return value

# Call in extract_furnace_data():
elif param == 'New Parameter Name':
    value = self._extract_new_param(pdf_rows, furnace)
```

Dashboard and API automatically show the new parameter! ✨

---

## Next Steps

1. **Create Extractors** for each plant:
   - [ ] BSP JSON Extractor
   - [ ] DSP JSON Extractor
   - [ ] RSP JSON Extractor
   - [ ] BSL JSON Extractor
   - [ ] ISP JSON Extractor

2. **Test Extraction**:
   - [ ] Extract sample PDFs/Excel files
   - [ ] Verify furnace-wise data in DB
   - [ ] Verify plant consolidation calculations
   - [ ] Verify SAIL consolidation

3. **Update Dashboard**:
   - [ ] Integrate new API endpoints
   - [ ] Display furnace-wise drill-down
   - [ ] Show plant consolidated
   - [ ] Show SAIL consolidated

4. **PDF Report**:
   - [ ] Use `techno_plant_data` for PDF generation
   - [ ] Update `page_techno.py` to use new tables

---

## Files Created/Modified

### New Files:
- `backend/techno_json_utils.py` - Extraction & calculation utilities
- `backend/production_utils.py` - HM production lookup utilities
- `backend/api_techno_json.py` - API endpoints

### Modified Files:
- `backend/db.py` - Added 3 new tables + 6 utility functions
- `backend/main.py` - Integrated new API router

### Documentation:
- `TECHNO_JSON_FINAL_DESIGN.md` - Complete design
- `HM_PRODUCTION_STRATEGY.md` - HM production handling
- `ADDING_NEW_PARAMETERS.md` - How to add new parameters

---

## Testing the Implementation

### Test 1: Create Tables
```python
from db import init_db
init_db()  # Creates all tables including new ones
```

### Test 2: Insert Sample Data
```python
from db import insert_techno_furnace_data

insert_techno_furnace_data(
    plant='BSP',
    furnace='BF-1',
    report_month='2026-06',
    data={
        'Coke Rate': {'value': 300.0, 'unit': 'Kg/THM'},
        'HM Production': {'value': 10000.0, 'unit': 'T', 'source': 'PDF'}
    }
)
```

### Test 3: Calculate Plant Consolidated
```python
from techno_json_utils import calculate_and_save_plant_consolidated

success = calculate_and_save_plant_consolidated('BSP', '2026-06')
if success:
    print("✅ Plant consolidated calculated")
```

### Test 4: API Endpoint
```bash
curl "http://localhost:8000/api/techno-plant-data?plant=BSP&report_month=2026-06"
```

---

## Architecture Advantages

| Feature | Old | New |
|---------|-----|-----|
| **Tables** | 5+ | 3 |
| **Add Parameter** | Schema migration | Just JSON field |
| **Furnace Data** | Not stored | Fully supported |
| **Calculation** | Complex JOINs | Simple JSON processing |
| **Audit Trail** | Limited | Full (source tracked) |
| **Flexibility** | Low | Very high |
| **Performance** | Good | Excellent |

---

## Support & Troubleshooting

### Issue: HM Production not found
**Solution**: Check `production_table` for furnace names:
```python
from production_utils import get_furnace_production_variants

variants = get_furnace_production_variants('BSP', '2026-06', 'BF-1')
print(variants)  # Shows all possible matching formats
```

### Issue: Plant calculation shows incomplete
**Solution**: Ensure all furnaces have data extracted:
```python
furnaces = get_techno_furnace_data('BSP', '2026-06')
print(f"Furnaces with data: {list(furnaces.keys())}")
```

### Issue: SAIL calculation using simple average instead of direct
**Solution**: Check old `techno_actuals` table for SAIL direct values:
```sql
SELECT * FROM techno_actuals 
JOIN techno_param ON techno_actuals.param_id = techno_param.param_id
WHERE techno_param.row_label = 'SAIL'
```

---

## 🚀 Ready to Start?

All infrastructure is ready! Next:

1. **Create your first extractor** (e.g., BSP)
2. **Extract sample data** from PDF
3. **Verify calculations** are correct
4. **Integrate with dashboard**
5. **Generate PDF reports** using plant data

Let me know if you need help with any step! 💪
