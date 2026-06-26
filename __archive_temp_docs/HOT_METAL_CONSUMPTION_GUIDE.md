# Hot Metal Consumption Data Integration Guide

## Overview

"Hot Metal Consumption" has been successfully added to your SAIL MIS Portal database as a techno-economic parameter. This guide explains how to manage this data.

## What Was Added

### 1. Database Parameters (8 entries created)
The following parameters are now tracked in your database:

- **SAIL** (Consolidated) - `Hot Metal Consumption` (T)
- **BSP** (Bhilai Steel Plant) - `Hot Metal Consumption` (T)
- **DSP** (Durgapur Steel Plant) - `Hot Metal Consumption` (T)
- **RSP** (Rourkela Steel Plant) - `Hot Metal Consumption` (T)
- **BSL** (Bokaro Steel Plant) - `Hot Metal Consumption` (T)
- **ISP** (Integrated Steel Plant) - `Hot Metal Consumption` (T)
- **BSP Blast Furnace** - `Hot Metal Consumption` (T)
- **DSP Blast Furnace** - `Hot Metal Consumption` (T)
- **RSP Blast Furnace** - `Hot Metal Consumption` (T)

### 2. Frontend Components
A new manual entry form has been added to the Data Entry page:

**Location:** `/data-entry` → Scroll to "Hot Metal Consumption — Manual Entry" section

**Features:**
- Select report month
- Load existing data
- Edit values for each plant
- Visual indication of changed values (yellow highlight)
- Save to database with validation
- Reset unsaved changes

### 3. Registry Updates
Added normalization mappings in `techno_registry.py`:
- `"hot metal consumption"` → canonical name
- `"hm consumption"` → canonical name

## How to Use

### Manual Data Entry

1. **Navigate to Data Entry:**
   - Go to `/data-entry` in your SAIL MIS Portal
   - Scroll down to "Hot Metal Consumption — Manual Entry" section

2. **Load Data:**
   - Select the report month (YYYY-MM format)
   - Click "Load" button
   - System will fetch existing values (if any)

3. **Enter Values:**
   - Input Hot Metal Consumption in tonnes (T) for each plant
   - Values are auto-highlighted in green when entered
   - Changed values show "edited" status in yellow

4. **Save Data:**
   - Click "Save to DB" button
   - Status message confirms save
   - Values are persisted to database

5. **Reset:**
   - Click "Reset" to discard unsaved changes
   - Revert to last saved values

### API Integration (Developers)

#### Load Existing Data
```bash
GET /api/techno-monthly-data?month=2025-04&param_names=Hot Metal Consumption
```

**Response:**
```json
{
  "data": [
    {
      "param_id": 2267,
      "param_name": "Hot Metal Consumption",
      "row_label": "BSP",
      "unit": "T",
      "report_month": "2025-04",
      "actual": 1250.5
    }
  ]
}
```

#### Save New Data
```bash
POST /api/techno-manual-save
Content-Type: application/json

{
  "month": "2025-04",
  "rows": [
    {
      "param_id": 2267,
      "actual": 1250.5,
      "till_month_actual": null
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "saved": 1,
  "cleared": 0,
  "message": "Saved 1 value(s), cleared 0 value(s) for 2025-04."
}
```

### Excel Upload

To upload Hot Metal Consumption data via Excel:

1. **Format your Excel file:**
   - Column: Plant name (BSP, DSP, RSP, BSL, ISP, SAIL)
   - Column: Hot Metal Consumption value (in tonnes)
   - Month information in header or standardized column

2. **Upload via:**
   - Navigate to `/upload` → Excel Ingestion
   - Select your file and process

3. **Data is automatically stored** in the database

## Database Schema

### Table: `techno_param`
Stores parameter definitions:
```sql
CREATE TABLE techno_param (
    param_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    param_name TEXT NOT NULL,          -- "Hot Metal Consumption"
    row_label  TEXT NOT NULL,          -- "BSP", "DSP", etc.
    unit       TEXT DEFAULT '',        -- "T" (Tonnes)
    sort_order INTEGER DEFAULT 0
);
```

### Table: `techno_actuals`
Stores actual values per month:
```sql
CREATE TABLE techno_actuals (
    param_id       INTEGER NOT NULL REFERENCES techno_param(param_id),
    report_month   TEXT NOT NULL,      -- "2025-04"
    actual         REAL,               -- Monthly value
    till_month_actual REAL,            -- YTD/Cumulative value
    source_priority INTEGER DEFAULT 0  -- 5 for manual entry
);
```

## Troubleshooting

### Issue: "No data found" when loading
**Solution:** 
- Ensure the month is in YYYY-MM format (e.g., 2025-04)
- First entry for a month will show empty fields
- Enter value and click "Save to DB"

### Issue: Changes not saved
**Solution:**
- Ensure at least one value is changed from original
- Click "Save to DB" button (not a different button)
- Wait for green success message
- Check browser console for errors (F12)

### Issue: Cannot load data
**Solution:**
- Check that backend server is running
- Verify API_BASE_URL environment variable is set
- Check network tab in browser DevTools (F12)

## Query Examples

### Get all Hot Metal Consumption for a month
```sql
SELECT p.row_label, a.actual 
FROM techno_actuals a
JOIN techno_param p ON a.param_id = p.param_id
WHERE p.param_name = 'Hot Metal Consumption'
  AND a.report_month = '2025-04'
ORDER BY p.row_label;
```

### Get SAIL-wide (consolidated) Hot Metal Consumption
```sql
SELECT a.report_month, a.actual 
FROM techno_actuals a
JOIN techno_param p ON a.param_id = p.param_id
WHERE p.param_name = 'Hot Metal Consumption'
  AND p.row_label = 'SAIL'
ORDER BY a.report_month DESC;
```

## Data Validation

- **Unit:** Tonnes (T) - enter decimal values
- **Range:** No automatic range validation - enter realistic values
- **Null handling:** Empty fields are treated as no data
- **Source Priority:** Manual entries (priority 5) override lower-priority sources

## Future Enhancements

Consider adding:
1. **Validation Rules:** Min/max checks per plant
2. **Trend Analysis:** Month-over-month comparison
3. **Forecasting:** Predict next month based on trend
4. **Bulk Upload:** CSV import with batch save
5. **Reports:** Custom report generation with charts

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review application logs: `backend/mis_reports.log`
3. Check database integrity: Verify `techno_param` and `techno_actuals` tables exist
4. Restart the backend server if experiencing issues

---

**Last Updated:** 2026-06-24  
**Version:** 1.0.0  
**System:** SAIL MIS Portal v1.0.0
