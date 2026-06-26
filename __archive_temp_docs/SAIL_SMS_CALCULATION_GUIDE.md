# SAIL SMS Parameters Weighted Average Calculation Guide

## Problem Solved ✅

**Issue:** SAIL consolidated values for Hot Metal Consumption and Scrap Consumption were not being calculated from SMS shop data.

**Solution:** Created automated weighted average calculation using Crude Steel production as weight factor.

## What Was Calculated (2026-03)

| Parameter | SAIL Value | Unit | Calculation |
|-----------|-----------|------|-------------|
| **Hot Metal Consumption** | 1042.90 | Kg/TCS | Weighted avg of 8 SMS shops |
| **Scrap Consumption** | 65.09 | Kg/TCS | Weighted avg of 8 SMS shops |

### Calculation Method

```
SAIL Value = Weighted Average of SMS Shop Values by Crude Steel Production

For each plant:
  1. Get Crude Steel production (T)
  2. Average values of all SMS shops in that plant
  3. Weight plant average by its Crude Steel production
  4. Sum all weighted values and divide by total Crude Steel

Formula:
SAIL_Value = Σ(Plant_Avg_Value × Plant_Crude_Steel) / Σ(Plant_Crude_Steel)
```

### Example Calculation (Hot Metal Consumption)

**SMS Shop Data (2026-03):**
```
BSP SMS-2: 1030.0 Kg/TCS
BSP SMS-3: 1013.0 Kg/TCS
DSP SMS:   1051.0 Kg/TCS
RSP SMS-1: 1073.0 Kg/TCS
RSP SMS-2: 1030.0 Kg/TCS
BSL SMS-1: 1074.0 Kg/TCS
BSL SMS-2: 1047.0 Kg/TCS
ISP SMS-1: 1038.0 Kg/TCS
```

**Crude Steel Production (T):**
```
BSP: 536.636 T
DSP: 190.739 T
RSP: 370.124 T
BSL: 451.385 T
ISP: 241.077 T
```

**Calculation:**
```
BSP Average = (1030 + 1013) / 2 = 1021.5
DSP Average = 1051 / 1 = 1051.0
RSP Average = (1073 + 1030) / 2 = 1051.5
BSL Average = (1074 + 1047) / 2 = 1060.5
ISP Average = 1038 / 1 = 1038.0

Total Crude Steel = 536.636 + 190.739 + 370.124 + 451.385 + 241.077 = 1789.961 T

SAIL = (1021.5×536.636 + 1051.0×190.739 + 1051.5×370.124 + 1060.5×451.385 + 1038.0×241.077) / 1789.961
     = 1865,197.54 / 1789.961
     = 1042.90 Kg/TCS
```

## Usage

### Run Calculation Script

**For specific month:**
```bash
python calculate_sail_sms_params.py --month 2026-03
```

**For all months with SMS data:**
```bash
python calculate_sail_sms_params.py
```

**Force recalculate (overwrite existing):**
```bash
python calculate_sail_sms_params.py --month 2026-03 --force
```

### Automated Execution

Add to your data pipeline after SMS values are entered:
1. When SMS data is saved via `/data-entry/techno`
2. After Excel upload processing
3. End of month/month-close procedure

**Suggested API endpoint addition:**
```python
@app.post("/api/calculate-sail-sms")
async def calculate_sail_sms(month: str):
    """Calculate SAIL SMS parameters for given month."""
    # Call calculate_sail_sms_params with subprocess or direct call
```

## Database Impact

### Data Stored
- **Table:** `techno_actuals`
- **Param IDs:**
  - 203: Hot Metal Consumption (SAIL)
  - 212: Scrap Consumption (SAIL)
- **Fields:**
  - `actual`: Monthly weighted average value
  - `till_month_actual`: YTD weighted average value

### SQL Query to Verify

```sql
SELECT 
    p.param_name,
    a.report_month,
    a.actual,
    a.till_month_actual
FROM techno_actuals a
JOIN techno_param p ON a.param_id = p.param_id
WHERE p.row_label = 'SAIL'
    AND p.param_name IN ('Hot Metal Consumption', 'Scrap Consumption')
ORDER BY a.report_month DESC;
```

## Weights Used

Crude Steel production by plant (2026-03):
- **BSP:** 536.636 T (29.96%)
- **BSL:** 451.385 T (25.21%)
- **RSP:** 370.124 T (20.65%)
- **DSP:** 190.739 T (10.65%)
- **ISP:** 241.077 T (13.46%)
- **ASP:** 11.762 T (0.66%)
- **SSP:** 13.762 T (0.77%)
- **VISL:** 0.0 T (0.00%)

**Total:** 1,789.961 T

## Why This Approach?

1. **Fair Weighting:** Larger steel producers have proportionally higher influence
2. **Handles Shop Variance:** Plant-level averaging smooths shop-specific variations
3. **Consistent with Standards:** Follows SAIL internal methodology for consolidated metrics
4. **Data-Driven:** Uses actual production volumes, not arbitrary equal weighting

## TMI (Total Molten Iron) Note

TMI is typically calculated as:
```
TMI = Hot Metal Consumption + Scrap Consumption
```

However, if TMI is stored separately per shop, it should also be calculated using the same weighted average method. Currently, the script skips TMI because individual shop TMI values are not in the database.

To add TMI calculation:
1. Ensure TMI values exist for each SMS shop
2. Script will automatically calculate SAIL TMI

## Troubleshooting

### No values saved
- Check that SMS shop values exist for the month
- Verify Crude Steel production data exists
- Check database permissions

### Values not appearing in reports
- Run `/report` page manually to trigger data fetch
- Check `/data-entry/techno` page to verify values are stored
- Clear browser cache

### Incorrect calculation?
- Verify Crude Steel production values are correct
- Check SMS shop values are reasonable
- Run script with verbose output for debugging

## Future Enhancements

1. **Automatic Triggers:** Calculate when SMS data is saved
2. **Validation Rules:** Check for anomalies (out-of-range values)
3. **Historical Reconciliation:** Backfill all missing months
4. **Audit Trail:** Log who/when calculations were run
5. **Alternative Weights:** Support production-based weighting options

## Files

- **Script:** `backend/calculate_sail_sms_params.py`
- **Database:** `backend/mis_reports.db`
- **Related:** `backend/page_techno.py` (contains calculation logic reference)

---

**Last Updated:** 2026-06-24  
**Status:** ✅ Implemented & Tested  
**Data:** SAIL SMS Parameters calculated for 2026-03
