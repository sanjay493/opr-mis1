# Integration Guide: Burden Percentage Calculation

## What Was Done

### 1. Created Shared Utility Module
**File:** `backend/excel_extractors/techno_calc_utils.py`

This module provides:
- `calculate_burden_percentages()` function
- Works with all plant extractors
- Handles furnace-wise and shop-level calculations
- Validates input before calculation

### 2. Updated Extractors

#### ✅ BSL (COMPLETED)
**File:** `backend/excel_extractors/excel_extractor_bsl.py`

**Change:** Added call to utility at line ~1153:
```python
# Calculate Sinter % in Burden and Pellet % in Burden
_calculate_burden_percentages(rows_out, db_month)
```

Internal wrapper function delegates to shared utility.

#### ✅ BSP (COMPLETED)
**File:** `backend/excel_extractors/excel_extractor_bsp.py`

**Change:** Added call at line 675 in `_extract_techno_3page_preview()`:
```python
# Calculate Sinter % in Burden and Pellet % in Burden
from techno_calc_utils import calculate_burden_percentages
calculate_burden_percentages(rows_out, db_month, plant_name="BSP")
```

### 3. PDF Extractors

PDF extractors (BSL BF PDF, etc.) already have columns 12 and 13 for burden percentages, so they extract them directly rather than calculating.

## Integration for Remaining Plants

### Pattern

For each plant extractor, find the main extraction function and add these 2 lines before the return statement:

```python
from techno_calc_utils import calculate_burden_percentages
calculate_burden_percentages(rows_out, report_month, plant_name="PLANT_NAME")
```

### Plant-by-Plant Integration

#### DSP (`excel_extractor_dsp.py`)

**Step 1:** Find the main techno extraction function
```bash
grep -n "techno_param_rows" excel_extractor_dsp.py
```

**Step 2:** Add before return statement:
```python
from techno_calc_utils import calculate_burden_percentages
calculate_burden_percentages(rows_out, db_month, plant_name="DSP")
```

#### ISP (`excel_extractor_isp.py`)

Same pattern as DSP:
```python
from techno_calc_utils import calculate_burden_percentages
calculate_burden_percentages(rows_out, db_month, plant_name="ISP")
```

#### RSP (`excel_extractor_rsp.py`)

Same pattern:
```python
from techno_calc_utils import calculate_burden_percentages
calculate_burden_percentages(rows_out, report_month, plant_name="RSP")
```

Note: RSP may use `report_month` instead of `db_month` - check the variable name used in that file.

#### BSP OISCO (`excel_extractor_bsp.py` - `_extract_oisco_preview()`)

If OISCO format also extracts consumption data:
```python
from techno_calc_utils import calculate_burden_percentages
calculate_burden_percentages(rows_out, db_month, plant_name="BSP")
```

## How It Works

### Before Integration
```
Excel File
  ↓
Extract parameters (Iron Ore, Sinter, Pellet, Scrap)
  ↓
Return preview rows
  ↓
Database storage
```

### After Integration
```
Excel File
  ↓
Extract parameters (Iron Ore, Sinter, Pellet, Scrap)
  ↓
CALCULATE Sinter % and Pellet % ← NEW!
  ↓
Return preview rows (including calculated %)
  ↓
Database storage (includes calculated %)
```

## Testing the Integration

### Manual Test

1. Upload a techno Excel file
2. Check the preview for:
   - Sinter in Burden (%)
   - Pellet in Burden (%)
3. Confirm values:
   - Sinter % + Pellet % ≤ 100%
   - Should have 2 decimal places (before formatting)

### Database Test

```sql
-- Check if burden percentages are stored
SELECT techno_json FROM techno_data 
WHERE plant = 'BSP' 
AND unit = 'BF_Shop'
LIMIT 1;

-- Should see JSON like:
-- {"month": {"sinter_in_burden": 30.0, "pellet_in_burden": 15.0, ...}}
```

### Frontend Test

1. Navigate to Reports → Page 27
2. Look for Sinter in Burden and Pellet in Burden rows
3. Verify values display correctly with 0 decimal places

## Key Features

✅ **Automatic Calculation**
- No manual entry needed
- Calculated from raw material consumption

✅ **Furnace-Wise**
- Calculates for each furnace (BF-1, BF-2, etc.)
- Also at shop level (BF_Shop aggregate)

✅ **Priority Handling**
- Extracted values (priority 5) override calculated (priority 4)
- If Excel has pre-calculated %, those are used instead

✅ **Error Handling**
- Validates data before calculation
- Skips if consumption data incomplete
- Won't calculate if total burden = 0

✅ **Logging**
- Marked as "Calculated from..." in metadata
- Includes formula in cell reference
- source_priority = 4 (lower than extracted = 5)

## Common Issues & Fixes

### Percentages not appearing in preview
1. Check extraction includes consumption data (Iron Ore, Sinter, Pellet, Scrap)
2. Verify all four values are present
3. Check `from techno_calc_utils import` line was added
4. Look for import errors in backend logs

### Percentages sum to >100%
This is normal if not all burden materials are included in the Excel total. The calculation includes whatever materials are present.

### Different values than Excel file
Excel file may have pre-calculated percentages (which are used with priority 5) or use a different calculation method. Check which values are being extracted vs calculated.

## Status

| Plant | Main Excel | PDF | Status | Notes |
|-------|-----------|-----|--------|-------|
| BSL | ✅ DONE | ✅ Has columns | Complete | Using utility function |
| BSP | ✅ DONE | (if exists) | Complete | Using utility function |
| DSP | ⏳ PENDING | (if exists) | Ready | Follow pattern above |
| ISP | ⏳ PENDING | (if exists) | Ready | Follow pattern above |
| RSP | ⏳ PENDING | (if exists) | Ready | Follow pattern above |

## Next Steps

1. **Apply to DSP, ISP, RSP**
   - Add the 2 lines to each extractor
   - Test with sample files

2. **Verify on Page 27**
   - Upload test files for each plant
   - Check Page 27 displays burden percentages
   - Verify formatting (0 decimals)

3. **Database Validation**
   - Query `techno_data` table
   - Confirm JSON includes `sinter_in_burden` and `pellet_in_burden` keys

## Questions?

The shared utility function handles all the complexity:
- Grouping consumption data by furnace
- Validating inputs
- Calculating percentages
- Adding metadata
- Handling edge cases

Just import and call it - the calculation is automatic!

