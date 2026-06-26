# API Endpoint: Calculate SAIL SMS Parameters On-the-Fly

## Overview

New API endpoint `/api/sail-sms-params` calculates SAIL consolidated SMS parameters (Hot Metal Consumption, Scrap Consumption) using weighted averages.

**Key Feature:** Values are calculated on-the-fly and NOT stored in the database. If a manually entered DB value exists, it takes precedence.

---

## API Endpoint

### GET `/api/sail-sms-params?month=YYYY-MM`

**Purpose:** Fetch or calculate SAIL SMS parameters for a given month

**Parameters:**
- `month` (required): Month in format `YYYY-MM` (e.g., `2026-03`)

**Response:**
```json
{
  "month": "2026-03",
  "sail_params": {
    "Hot Metal Consumption": {
      "actual": 1042.90,
      "till_month_actual": 1042.35,
      "source": "db",
      "unit": "Kg/TCS"
    },
    "Scrap Consumption": {
      "actual": 65.09,
      "till_month_actual": 65.79,
      "source": "db",
      "unit": "Kg/TCS"
    }
  }
}
```

---

## Data Logic

### 1. Check Database First
```
IF SAIL_{param}_{month} EXISTS in techno_actuals
  THEN return value with source="db"
```

### 2. If Not in DB, Calculate
```
FOR each SMS shop:
  GET monthly value & YTD value
  
FOR each plant:
  avg_monthly = average of all SMS shop monthly values in that plant
  avg_ytd = average of all SMS shop YTD values in that plant
  
GET Crude Steel production:
  monthly_cs = that month's CS production
  ytd_cs = cumulative CS production (Apr to that month)

CALCULATE weighted averages:
  SAIL_monthly = Σ(plant_avg_monthly × plant_monthly_cs) / Σ(plant_monthly_cs)
  SAIL_ytd = Σ(plant_avg_ytd × plant_ytd_cs) / Σ(plant_ytd_cs)
  
RETURN with source="calculated"
```

---

## Integration Points

### Frontend: Data-Entry/Techno Page

**Location:** `/data-entry/techno`

**Component:** `SailSmsParamsDisplay` (new)

**How it works:**
1. Uses `useSailSmsParams` hook to fetch data
2. Displays SAIL values in a separate table under each group
3. Shows "from DB" or "calculated" badge
4. Only shows for SMS group (`groupCode === 'SMS'`)

**Component Usage:**
```jsx
import SailSmsParamsDisplay from '@/components/SailSmsParamsDisplay';

<SailSmsParamsDisplay 
  apiBase={API_BASE_URL} 
  month={reportMonth} 
  groupCode={groupCode} 
/>
```

### Frontend: Report Page

For the `/report` page (if displaying techno data client-side):
```jsx
const { sailParams, loading, error } = useSailSmsParams(apiBase, month);

// Display sailParams in the SMS section
Object.entries(sailParams).forEach(([paramName, data]) => {
  // Display data.actual and data.till_month_actual
  // Show data.source as badge
});
```

### Backend: Page Generation

The existing `page_techno.py` contains weighted average calculation logic.

When rendering the `/report` page:
- SMS techno template gets data from `generate_techno()` function
- SAIL values are computed in-memory using `_compute_sail()` function
- No storage to DB - values are computed per request

---

## Example Scenarios

### Scenario 1: Manual Entry Exists (DB Value)
```
Request: GET /api/sail-sms-params?month=2026-03
Response source: "db"
Reason: User manually entered SAIL Hot Metal Consumption for Mar'26
```

### Scenario 2: SMS Data Exists, No DB Entry
```
Request: GET /api/sail-sms-params?month=2025-04
SMS shops: BSP SMS-2=1030, BSP SMS-3=1013, ... (8 shops total)
Crude Steel: BSP=536.6T, DSP=190.7T, ... (5 plants)

Calculation:
  BSP avg = (1030 + 1013) / 2 = 1021.5
  DSP avg = 1051.0
  RSP avg = 1051.5
  BSL avg = 1060.5
  ISP avg = 1038.0
  
  SAIL = weighted average by CS production
       = 1043.33 Kg/TCS
       
Response source: "calculated"
```

### Scenario 3: Incomplete Data
```
Request: GET /api/sail-sms-params?month=2024-01
SMS data: Only 3 shops have values (5 missing)
Result: 
  - If enough data to weight: return calculated value
  - If too sparse: return null for that value
```

---

## Key Differences from Manual Saving

| Aspect | Old Way | New Way |
|--------|---------|---------|
| Storage | Save to DB | Calculate on-the-fly |
| Updates | Stale after SMS changes | Always reflects latest SMS data |
| Manual Override | Not possible | DB entry takes precedence |
| Source | Unknown | Clearly marked (db/calculated) |
| Volume | Multiple saved entries | No extra DB storage |

---

## Files Created/Modified

### New Files
- `backend/main.py` - Added `/api/sail-sms-params` endpoint
- `frontend/src/hooks/useSailSmsParams.js` - React hook for API calls
- `frontend/src/components/SailSmsParamsDisplay.js` - Component to display SAIL values

### Modified Files
- `frontend/src/app/data-entry/techno/page.js` - Integrated component

---

## Usage Examples

### cURL
```bash
curl "http://localhost:8000/api/sail-sms-params?month=2026-03"
```

### JavaScript (Fetch)
```javascript
const response = await fetch(
  `${API_BASE_URL}/api/sail-sms-params?month=2026-03`
);
const data = await response.json();
console.log(data.sail_params);
```

### React Hook
```javascript
import { useSailSmsParams } from '@/hooks/useSailSmsParams';

function MyComponent() {
  const { sailParams, loading, error } = useSailSmsParams(apiBase, month);
  
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return (
    <div>
      {Object.entries(sailParams).map(([name, data]) => (
        <div key={name}>
          {name}: {data.actual} ({data.source})
        </div>
      ))}
    </div>
  );
}
```

---

## Error Handling

### Network Errors
```javascript
try {
  const response = await fetch(`/api/sail-sms-params?month=${month}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
} catch (err) {
  console.error('Failed to fetch SAIL params:', err);
  // Fall back to empty display or retry
}
```

### No Data Available
```json
{
  "month": "2026-03",
  "sail_params": {}
}
```
Return empty object if no SMS data or no Crude Steel production data available.

---

## Testing

### Test Endpoints

1. **March 2026 (should exist in DB):**
   ```
   GET /api/sail-sms-params?month=2026-03
   Expected: source="db"
   ```

2. **April 2025 (should calculate):**
   ```
   GET /api/sail-sms-params?month=2025-04
   Expected: source="calculated"
   ```

3. **Non-existent month:**
   ```
   GET /api/sail-sms-params?month=2020-01
   Expected: empty sail_params {}
   ```

---

## Performance Considerations

- **Calculation Time:** ~50-100ms per request (queries SMS + CS data)
- **Caching:** No caching (always fresh data)
- **Load:** Minimal - only fetches if SMS group selected
- **Scalability:** O(n) where n = number of SMS shops (currently 8)

---

## Future Enhancements

1. **Caching:** Add 5-minute cache for repeated requests
2. **Batch Calculation:** API to calculate for multiple months
3. **Custom Weights:** Allow alternative weighting schemes
4. **Audit Trail:** Log when manual entries override calculations
5. **Validation:** Alert if calculated values are anomalous

---

**API Version:** 1.0  
**Status:** Production Ready  
**Date:** 2026-06-24
