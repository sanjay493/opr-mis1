# JSON Techno Data - Quick Reference Card

## ⚡ Quick Start (5 minutes)

### 1. Extract Furnace Data from Excel
```python
from excel_extractors.bsp_json_extractor import extract_from_excel

# Extract and save to DB
records = extract_from_excel('bsp_data.xlsx', '2026-06')
print(f"Extracted {len(records)} furnace records")
```

### 2. Calculate Plant Consolidated
```python
from techno_json_utils import calculate_and_save_plant_consolidated

success = calculate_and_save_plant_consolidated('BSP', '2026-06')
if success:
    print("Plant data calculated and saved!")
```

### 3. Calculate SAIL Consolidated
```python
from techno_json_utils import calculate_and_save_sail_consolidated

success = calculate_and_save_sail_consolidated('2026-06')
if success:
    print("SAIL consolidated calculated!")
```

### 4. Query Data via API
```bash
# Get furnace data
curl "http://localhost:8000/api/techno-furnace-data?plant=BSP&report_month=2026-06"

# Get plant data
curl "http://localhost:8000/api/techno-plant-data?plant=BSP&report_month=2026-06"

# Get SAIL data
curl "http://localhost:8000/api/techno-sail-data?report_month=2026-06"
```

---

## 📊 Data Structures

### Furnace Record (JSON)
```json
{
  "plant": "BSP",
  "furnace": "BF-1",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {
      "value": 300.0,
      "unit": "Kg/THM",
      "source": "Excel"
    },
    "HM Production": {
      "value": 10000.0,
      "unit": "T",
      "source": "Excel"
    }
  }
}
```

### Plant Consolidated (JSON)
```json
{
  "plant": "BSP",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {
      "value": 337.78,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 4
    }
  },
  "calculation_details": {
    "Coke Rate": {
      "formula": "weighted_average",
      "furnaces": ["BF-1", "BF-2", "BF-3", "BF-4"],
      "total_weight": 38213
    }
  }
}
```

### SAIL Consolidated (JSON)
```json
{
  "report_month": "2026-06",
  "data": {
    "Coke Rate": 321.78,
    "BF Productivity": 2.11
  },
  "calculation_method": {
    "Coke Rate": "avg_5_plants",
    "BF Productivity": "avg_5_plants"
  }
}
```

---

## 🔌 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/techno-furnace-data` | GET | Get furnace-wise data |
| `/api/techno-plant-data` | GET | Get plant consolidated |
| `/api/techno-sail-data` | GET | Get SAIL consolidated |
| `/api/techno-plant-data-calculate` | POST | Trigger plant calculation |
| `/api/techno-sail-data-calculate` | POST | Trigger SAIL calculation |
| `/api/techno-parameters-list` | GET | List all parameters |
| `/api/techno-months-available` | GET | List available months |

### Query Parameters
```
plant=BSP          Plant code (BSP, DSP, RSP, BSL, ISP)
report_month=2026-06    YYYY-MM format
furnace=BF-1       (Optional) Specific furnace
```

---

## 🛠️ Common Tasks

### Add New Parameter
1. **Update extractor:**
   ```python
   # In TechnoFurnaceExtractor.PARAM_UNITS:
   'New Parameter': 'unit',
   ```

2. **Add extraction method:**
   ```python
   def _extract_new_parameter(self, pdf_rows, furnace):
       # Your extraction logic
       return value
   ```

3. **Call in extraction:**
   ```python
   elif param == 'New Parameter':
       value = self._extract_new_parameter(pdf_rows, furnace)
   ```

### Check Extraction Status
```python
from db import get_techno_furnace_data

# See what was extracted
furnaces = get_techno_furnace_data('BSP', '2026-06')
for furnace, data in furnaces.items():
    print(f"{furnace}: {len(data)} parameters")
```

### Verify Calculations
```python
from db import get_techno_plant_data

plant_data = get_techno_plant_data('BSP', '2026-06')
for param, info in plant_data['data'].items():
    print(f"{param}: {info['value']} ({info['calculation_method']})")
```

### Debug HM Production
```python
from production_utils import get_furnace_production_variants

variants = get_furnace_production_variants('BSP', '2026-06', 'BF-1')
print(variants)  # Shows all matching formats
```

---

## 📈 Database Tables

### techno_furnace_data
```sql
id              INTEGER PRIMARY KEY
plant           TEXT (BSP, DSP, etc)
furnace         TEXT (BF-1, BF-2, etc)
report_month    TEXT (YYYY-MM)
data            JSON {param: {value, unit, source}}
created_at      DATETIME
updated_at      DATETIME

UNIQUE(plant, furnace, report_month)
```

### techno_plant_data
```sql
id                      INTEGER PRIMARY KEY
plant                   TEXT (BSP, DSP, etc)
report_month            TEXT (YYYY-MM)
data                    JSON {param: {value, unit, method}}
calculation_details     JSON {param: {formula, furnaces}}
created_at              DATETIME
updated_at              DATETIME

UNIQUE(plant, report_month)
```

### techno_sail_consolidated
```sql
id                  INTEGER PRIMARY KEY
report_month        TEXT (YYYY-MM) UNIQUE
data                JSON {param: value}
calculation_method  JSON {param: "avg_5_plants" | "SAIL_direct"}
last_updated        DATETIME
```

---

## 🎯 Weighted Average Formula

```
Result = Σ(Parameter × HM_Production) / Σ(HM_Production)

Example (BSP Coke Rate):
= (300×10000 + 350×11100 + 345×7234 + 357×9879) / 38213
= 337.78 Kg/THM
```

---

## ⚙️ System Flow

```
[PDF/Excel Upload]
        ↓
[Plant Extractor] ← Identifies furnaces, extracts params
        ↓
techno_furnace_data ← Insert furnace records
        ↓
[Plant Calculator] ← Weighted average calculation
        ↓
techno_plant_data ← Insert plant consolidated
        ↓
[SAIL Calculator] ← Multi-plant average
        ↓
techno_sail_consolidated ← Insert SAIL data
        ↓
[API Endpoints] ← Serve data to frontend
        ↓
[Dashboard/PDF] ← Display results
```

---

## 🚀 Performance Tips

1. **Batch Extract Multiple Plants**
   ```python
   for plant in ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']:
       extract_and_save_for_plant(plant, '2026-06')
   
   # Then calculate all at once
   for plant in PLANTS:
       calculate_and_save_plant_consolidated(plant, '2026-06')
   
   calculate_and_save_sail_consolidated('2026-06')
   ```

2. **Cache API Responses**
   ```javascript
   // Frontend: Cache SAIL data for "All Plants" view
   const sailData = await fetchWithCache(
     '/api/techno-sail-data?report_month=2026-06',
     3600  // 1 hour cache
   );
   ```

3. **Lazy Load Furnace Details**
   ```javascript
   // Load furnace data only when needed
   const furnaceData = await fetch(
     '/api/techno-furnace-data?plant=BSP&report_month=2026-06'
   );
   ```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| No data returned | Check `report_month` format (YYYY-MM) |
| Weighted avg wrong | Verify HM Production in all furnaces |
| Parameter missing | Check extractor recognizes parameter |
| SAIL = simple avg | SAIL direct value not found in old tables |
| Slow queries | Use `/api/techno-plant-data` (not furnace) |

---

## 📝 Python Usage Examples

### Insert Custom Data
```python
from db import insert_techno_furnace_data

insert_techno_furnace_data(
    plant='BSP',
    furnace='BF-1',
    report_month='2026-06',
    data={
        'Coke Rate': {'value': 300.0, 'unit': 'Kg/THM'},
        'HM Production': {'value': 10000.0, 'unit': 'T'}
    }
)
```

### Retrieve and Process
```python
from db import get_techno_plant_data
import json

plant = get_techno_plant_data('BSP', '2026-06')
data = plant['data']
calc = plant['calculation_details']

for param, info in data.items():
    print(f"{param}: {info['value']}")
```

### Test Calculation
```python
from techno_json_utils import TechnoPlantCalculator

calc = TechnoPlantCalculator()
plant_data, calc_details = calc.calculate_plant_consolidated('BSP', '2026-06')

print(f"Calculated {len(plant_data)} parameters")
```

---

## 📚 Documentation Links

- **Full Design:** `TECHNO_JSON_FINAL_DESIGN.md`
- **HM Production:** `HM_PRODUCTION_STRATEGY.md`
- **New Parameters:** `ADDING_NEW_PARAMETERS.md`
- **Complete Setup:** `IMPLEMENTATION_COMPLETE.md`
- **Full Summary:** `IMPLEMENTATION_SUMMARY.md`

---

## ✅ Status Checklist

- [x] Database schema created
- [x] Extraction utilities written
- [x] API endpoints implemented
- [x] Example extractor provided
- [x] All tests passing
- [x] Documentation complete
- [ ] Frontend integration (next)
- [ ] PDF report update (next)
- [ ] Plant extractors (next)

---

## 🎓 Quick Links

**Test it:**
```bash
cd backend
python test_json_implementation.py
python test_complete_integration.py
```

**Run server:**
```bash
python -m uvicorn main:app --reload
```

**Check API:**
```bash
curl http://localhost:8000/api/techno-parameters-list
```

---

**Last Updated:** 2026-06-26  
**Status:** ✅ Production Ready  
**Version:** 1.0
