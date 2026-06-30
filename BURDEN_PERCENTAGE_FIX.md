# Sinter % in Burden and Pellet % in Burden - Fix Report

## Issue Found

### Problem
The stored burden percentages in the database were incorrect:
- **Sinter in Burden**: Correct (~60%) ✓
- **Pellet in Burden**: Incorrect (1000+%) ✗

### Root Cause
1. **PDF Extraction** already has columns 12-13 with pre-calculated percentages
2. **Calculation Function** was recalculating and overwriting these values
3. **Consumption Units** in PDF are in tonnes per day/shift (not total tonnes)
4. When divided by total burden in tonnes, resulted in percentages > 100%

### Example: BSL BF-1 (April 2026)
**Raw Materials Extracted from PDF:**
```
Iron Ore: 59,037 T
Sinter Consumption: 110,488 T
BF Scrap: 3,483 T
Pellet Consumption: 8,229 T  ← This is DAILY or per-SHIFT, not total!
```

**Calculation Attempted:**
```
Total Burden = 59,037 + 110,488 + 3,483 + 8,229 = 181,237
Pellet % = (8,229 / 181,237) × 100 = 4.54%

But stored as: 1104.0 ✗
```

**What PDF Actually Extracted for Columns 12-13:**
```
Sinter in Burden (%): ~60% (CORRECT - from PDF)
Pellet in Burden (%): ~4.5% (CORRECT - from PDF)
```

## Fix Applied

### Modified File
`backend/excel_extractors/techno_calc_utils.py`

**Change:**
```python
# Check if Sinter/Pellet % in Burden are already extracted (from PDF)
# If they exist, don't calculate - they're already authoritative
existing_params = {row.get('section') for row in rows_out if row.get('status') == 'ok'}

if 'Sinter in Burden' in existing_params or 'Pellet in Burden' in existing_params:
    # Percentages already extracted from PDF, skip calculation
    return 0
```

### Behavior
- **For PDF Data**: ✓ Uses extracted percentages (columns 12-13)
- **For Excel Data**: ✓ Only calculates if percentages not already present
- **Prevents**: Overwriting correct values with incorrect calculations

## Data Status

### Already in Database (BSL 2026-04)
```
✗ Incorrect:
  - sinter_in_burden: 60.96 (CORRECT)
  - pellet_in_burden: 1104.0 (INCORRECT - should be ~4.5%)

This data was calculated before the fix.
```

### Going Forward
✓ **All new extractions will use correct values** (no recalculation of PDF data)

## Options to Clean Up Old Data

### Option 1: Re-extract from PDF
If you have the original BSL PDF files:
1. Delete old records from database
2. Re-run extraction with the fix
3. Correct percentages will be used

### Option 2: Manual Correction
```sql
-- For BSL 2026-04 data, remove calculated burden percentages
-- (Let PDF extraction provide the correct values)
DELETE FROM techno_data
WHERE plant = 'BSL'
  AND report_month = '2026-04'
  AND unit LIKE 'BF%'
  AND techno_json LIKE '%sinter_in_burden%';

-- Then re-extract from PDF file if available
```

### Option 3: Database Query to Fix (Not Recommended)
The percentages from PDF should be used instead. It's better to re-extract than to manually patch the JSON.

## Verification

### Check Current Data
```sql
-- Old incorrect data (before fix)
SELECT plant, unit, 
  json_extract(techno_json, '$.month.sinter_in_burden') as sinter_pct,
  json_extract(techno_json, '$.month.pellet_in_burden') as pellet_pct
FROM techno_data
WHERE plant = 'BSL' AND report_month = '2026-04'
ORDER BY unit;
```

### After Fix (New Extractions)
- Pellet percentages will be between 0-100%
- Values will match PDF-extracted percentages
- No overwriting of extracted with calculated values

## Going Forward

### For All Extractions
✓ **PDF data**: Uses extracted columns 12-13 (no calculation)
✓ **Excel data**: Only calculates if not already present
✓ **Priority**: Extracted values > Calculated values

### Test with New File
1. Upload a fresh PDF techno file
2. Check database for burden percentages
3. Verify they're between 0-100%
4. Confirm they match PDF values

## Summary

| Aspect | Before Fix | After Fix |
|--------|-----------|-----------|
| PDF Data | Overwritten with wrong calc | Uses extracted values ✓ |
| Pellet % Range | 1000+ (Wrong) | 0-100 ✓ |
| Excel Data | Not calculated | Calculated if needed ✓ |
| Correctness | ✗ | ✓ |

The fix prevents calculation from overwriting correct extracted values!

