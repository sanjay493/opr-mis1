# Legacy Data Priority System

## 🎯 Overview

The JSON-based techno data system now implements a **3-tier priority system** to ensure legacy data is preserved while supporting new calculated values:

```
Priority 1: Legacy Data (techno_actuals)
    ↓ (if no legacy data found)
Priority 2: Calculated Data (from furnaces/plants)
    ↓ (if calculation incomplete)
Priority 3: Fallback (simple average/partial data)
```

---

## 🔑 Key Principle

**Legacy data always takes priority over calculated values.**

This ensures:
- ✅ Historical data integrity preserved
- ✅ No disruption to existing reports
- ✅ Smooth transition from old to new system
- ✅ Data consistency maintained

---

## 📊 How It Works

### For Plant-Level Data

```python
Plant Coke Rate Calculation:

1. Check legacy techno_actuals table
   └─ Query: WHERE row_label = 'BSP' AND param_name = 'Coke Rate'
   └─ If found → USE THIS VALUE (Priority 1)
   └─ Source: 'legacy_data'

2. If not found in legacy, calculate from furnaces
   └─ Get all furnace data for BSP
   └─ Calculate weighted average: Σ(value × HM_prod) / Σ(HM_prod)
   └─ Source: 'calculated'

3. Return value with source indicator
```

### For SAIL Consolidated

```python
SAIL Coke Rate Calculation:

1. Check legacy techno_actuals table
   └─ Query: WHERE row_label = 'SAIL' AND param_name = 'Coke Rate'
   └─ If found → USE THIS VALUE (Priority 1)
   └─ Source: 'SAIL_direct'

2. If not found in legacy, calculate from 5 plants
   └─ Get plant consolidated for BSP, DSP, RSP, BSL, ISP
   └─ Calculate average: Σ(plant_values) / 5
   └─ Source: 'avg_5_plants'

3. Return value with calculation method indicator
```

---

## 💾 Data Source Tracking

Every calculated value includes a **source indicator**:

```json
{
  "data": {
    "Coke Rate": {
      "value": 337.78,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_by_hm_production",
      "source": "calculated"    // <-- NEW: Indicates source
    }
  }
}
```

### Source Values:
- `"legacy_data"` - From old techno_actuals (Priority 1)
- `"SAIL_direct"` - SAIL value from legacy (Priority 1)
- `"calculated"` - Calculated from furnace/plant data (Priority 2)
- `"avg_5_plants"` - Average of 5 plants (Priority 2)

---

## 🔍 Example Scenario

### Scenario: June 2026 Coke Rate for BSP

```
Step 1: Check Legacy Data
───────────────────────────
SELECT ta.actual FROM techno_actuals ta
JOIN techno_param tp ON ta.param_id = tp.param_id
WHERE ta.report_month = '2026-06'
  AND tp.row_label = 'BSP'
  AND tp.param_name = 'Coke Rate'

Result: Found! Value = 340.5 (manually entered)

✓ USE THIS VALUE → 340.5
  Source: 'legacy_data'
  (Furnace calculation NOT performed)
```

### Scenario: New Month with No Legacy Data

```
Step 1: Check Legacy Data
───────────────────────────
SELECT ta.actual FROM techno_actuals ta
WHERE report_month = '2026-07' AND row_label = 'BSP' ...

Result: Not found!

Step 2: Calculate from Furnaces
──────────────────────────────
Get furnace data:
  BF-1: 300.0 × 10000T = 3,000,000
  BF-2: 350.0 × 11100T = 3,885,000
  BF-3: 345.0 × 7234T  = 2,495,730
  BF-4: 357.0 × 9879T  = 3,530,703
  
Total: 12,911,433 / 38,213 = 337.78

✓ USE CALCULATED VALUE → 337.78
  Source: 'calculated'
  Calculation: 'weighted_average_by_hm_production'
```

---

## 📈 Priority Comparison

| Scenario | Priority 1 | Priority 2 | Used |
|----------|-----------|-----------|------|
| Legacy data exists | ✓ Found | - | **Legacy (340.5)** |
| Only furnace data | ✗ Not found | ✓ Calculate | **Calculated (337.78)** |
| Both exist | ✓ Found | - | **Legacy (takes precedence)** |
| Neither exists | ✗ Not found | ✗ No data | **NULL** |

---

## 🔧 Implementation Details

### Code in `techno_json_utils.py`

```python
def _calculate_parameter(self, plant, param, furnace_data, report_month):
    """
    Priority 1: Check legacy data in techno_actuals
    Priority 2: Calculate from furnace data
    """
    
    # PRIORITY 1: Check legacy data
    legacy_value = self._get_legacy_plant_value(plant, param, report_month)
    if legacy_value is not None:
        details = {
            'formula': 'legacy_data',
            'source': 'techno_actuals',
            'note': 'Using existing legacy data (takes priority)'
        }
        return legacy_value, 'legacy_data', details
    
    # PRIORITY 2: Calculate from furnaces
    # ... weighted average calculation ...
    
    return result_value, 'weighted_average_by_hm_production', details
```

### For SAIL Data

```python
def _get_sail_direct_value(self, param, report_month):
    """
    Get legacy SAIL direct value from old techno_actuals table
    
    Priority 1: Legacy data takes precedence
    """
    
    cursor.execute("""
        SELECT ta.actual
        FROM techno_actuals ta
        JOIN techno_param tp ON ta.param_id = tp.param_id
        WHERE ta.report_month = ?
          AND tp.row_label = 'SAIL'
          AND tp.param_name = ?
    """, [report_month, param])
    
    row = cursor.fetchone()
    return float(row[0]) if row else None
```

---

## 📊 API Response with Legacy Data

When legacy data is used, the API response includes metadata:

```json
{
  "plant": "BSP",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {
      "value": 340.5,
      "unit": "Kg/THM",
      "calculation_method": "legacy_data",
      "source": "legacy",
      "furnaces_used": 0
    }
  },
  "calculation_details": {
    "Coke Rate": {
      "formula": "legacy_data",
      "source": "techno_actuals",
      "note": "Using existing legacy data (takes priority)"
    }
  }
}
```

---

## 🎯 SAIL Priority Example

### Legacy SAIL Data Exists
```
SAIL Coke Rate (Legacy):
- Legacy value: 425.1 Kg/THM
- Source: SAIL_direct (from old table)
- Used: YES (Priority 1)
- Furnace calculation: NOT performed
```

### No Legacy, Calculate from Plants
```
SAIL Coke Rate (Calculated):
- Plant values: BSP=337.78, DSP=325.13, RSP=325.99, BSL=305.00, ISP=315.00
- Average: 321.78 Kg/THM
- Method: avg_5_plants (Priority 2)
- Furnace calculation: Performed
```

---

## ✅ Benefits of This System

1. **Data Preservation**: Legacy data never gets overwritten
2. **Smooth Migration**: Old system continues alongside new system
3. **Transparency**: Source always indicated in response
4. **Audit Trail**: Can see which data is legacy vs calculated
5. **Backward Compatible**: Existing reports still get legacy values
6. **Progressive**: New data will use calculated values over time

---

## 🚀 Migration Strategy

### Phase 1 (Current)
- Legacy data takes priority (Priority 1)
- New furnace data extracted and stored
- Plant calculations run (but not used if legacy exists)
- SAIL calculations use legacy if available

### Phase 2 (After 6 months)
- Review which parameters have been replaced
- Archive old legacy data that's been superseded
- Transition to calculated values where verified

### Phase 3 (1 year)
- Full migration to new calculated system
- Legacy system can be phased out
- Keep historical data for audit purposes

---

## 📝 Configuration

If you want to **disable legacy priority** (use only calculated values):

```python
# In techno_json_utils.py, TechnoPlantCalculator:

def _calculate_parameter(self, plant, param, furnace_data, report_month):
    # DISABLE Priority 1 - comment out legacy check
    # legacy_value = self._get_legacy_plant_value(plant, param, report_month)
    # if legacy_value is not None: ...
    
    # SKIP directly to Priority 2 - calculated data
    # ... weighted average calculation ...
```

Or set environment variable:
```bash
# Use only calculated values, ignore legacy
export IGNORE_LEGACY_DATA=true
```

---

## 🔍 Monitoring & Verification

### Check Which Values Are Legacy vs Calculated

```sql
-- See how many parameters use legacy data
SELECT source, COUNT(*) 
FROM techno_plant_data, json_each(data)
WHERE json_extract(data, '$.*.source') = 'legacy'
GROUP BY source;
```

### API Endpoint to Check Sources

```bash
# Get plant data and see sources
curl "http://localhost:8000/api/techno-plant-data?plant=BSP&report_month=2026-06"

# Response will show:
{
  "data": {
    "Coke Rate": {
      "value": ...,
      "source": "legacy"  or  "calculated"
    }
  }
}
```

---

## 🎓 Summary

| System | Priority 1 | Priority 2 | Priority 3 |
|--------|-----------|-----------|-----------|
| **Plant Data** | Legacy techno_actuals | Weighted avg from furnaces | Simple avg |
| **SAIL Data** | Legacy SAIL row | 5-plant average | Partial data |
| **Benefit** | Data continuity | New accurate data | Coverage |

**Result**: Legacy data preserved while supporting new calculated values with complete transparency.

---

## 📞 Questions?

- **Why legacy first?** → Preserves historical accuracy and prevents disruption
- **Can I override?** → Set `IGNORE_LEGACY_DATA=true` to use only calculated
- **How long legacy?** → Recommended 6-12 months for full migration
- **What if both differ?** → Legacy is used; difference logged for review

---

**Status**: ✅ Legacy Data Priority System Implemented

All legacy data in `techno_actuals` table now takes precedence over calculated values, ensuring data consistency during migration.
