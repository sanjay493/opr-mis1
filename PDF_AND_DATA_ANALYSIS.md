# PDF Report Issues & Data Analysis

## Issue 1: Font Size & Legibility

**Current Font Configuration** (`backend/models.py`):
- Table data cells: 9.5pt
- Table headers: 9.0pt  
- Page titles: 13.0pt

### To Increase Font Size

You can pass custom FontConfig when generating the PDF:

**Option A: Via API (modify backend/main.py)**
```python
# In the /api/generate-pdf endpoint
font_config = FontConfig(
    td_size=11.0,      # Increased from 9.5
    th_size=10.5,      # Increased from 9.0
    title_size=15.0    # Increased from 13.0
)
```

**Option B: Modify Layout Configuration**
Edit the layout JSON files in `backend/` to adjust:
- `td_size`: Table cell font size
- `row_height`: Row height (to fit larger fonts)
- `page_margins`: Page margins to fit content

**Recommended increase**: 
- td_size: 9.5 → **11.0** or **11.5**
- th_size: 9.0 → **10.5** or **11.0**
- title_size: 13.0 → **15.0** or **16.0**

---

## Issue 2: SMS Parameters Vacant for FY 2025-26

### Root Cause Analysis

✅ **Data EXISTS in database:**
```
Hot Metal Consumption | SAIL | 2026-05 | 1038.165
Scrap Consumption     | SAIL | 2026-05 | 68.34
TMI                   | SAIL | 2026-05 | 1106.505
```

❌ **But showing as vacant in PDF**

### Why This Happens

These are **SMS (Steel Melting Shop) parameters** that are:

1. **Shop-level aggregated data**: Requires data from multiple SMS shops:
   - BSP SMS-2, BSP SMS-3
   - DSP SMS
   - RSP SMS-1, RSP SMS-2
   - BSL SMS-1, BSL SMS-2
   - ISP SMS-1

2. **Annual FY values computed differently**: 
   - For most BF params: weighted average by Hot Metal production
   - For SMS params: weighted average by **Crude Steel production per shop**
   - Requires aggregation logic in `_inject_sail_techno()`

3. **Potential Issue**: The **annual FY 2025-26 value** (not monthly) might not be computed if:
   - Fewer than required months of data available
   - Aggregation computation skipped for incomplete fiscal year
   - SAIL calculation logic not triggered for current fiscal year

### The Data Flow

```
Individual SMS Shop Data (2026-04, 2026-05)
        ↓
Weighted by Crude Steel Production per shop
        ↓
SAIL Aggregation (stored in techno_actuals)
        ↓
Annual FY Computation (fy_map) ← May be missing for current FY
        ↓
PDF Rendering
```

### Verification

Run this to check data availability for current FY:
```sql
-- Check which SMS shops have data for FY 2025-26
SELECT DISTINCT p.row_label, a.report_month, a.actual
FROM techno_actuals a
JOIN techno_param p ON a.param_id = p.param_id
WHERE p.param_name = 'Hot Metal Consumption'
  AND p.row_label IN ('BSP SMS-2', 'BSP SMS-3', 'DSP SMS', 'RSP SMS-1', 'RSP SMS-2', 'BSL SMS-1', 'BSL SMS-2', 'ISP SMS-1')
  AND a.report_month >= '2025-04'
ORDER BY p.row_label, a.report_month;
```

### Solution

1. **Check data entry**: Ensure SMS shop data has been entered for all months in current FY
2. **Verify aggregation**: Check if `_inject_sail_techno()` is running for FY 2025-26
3. **Wait for more months**: SMS FY value might only compute after sufficient months (typically after 6-12 months of data)

---

## Summary

**Font size issue**: Adjustable via FontConfig in API or layout configuration

**SMS data issue**: Data exists but annual FY aggregation may not be complete for current fiscal year (FY 2025-26 just started April 2025, may need more months of data for stable annual value)
