# Techno Data API Reference

Complete guide to querying techno (technical/production parameters) data via API.

---

## Overview

Techno data is **completely separate** from production data:

| Type | Table | Records | Purpose |
|------|-------|---------|---------|
| Furnace-level | `techno_furnace_data` | 17 | Individual furnace parameters |
| Plant-level | `techno_plant_data` | 7 | Consolidated plant parameters |
| SAIL-level | `techno_sail_consolidated` | ~3 | SAIL-wide consolidated |

---

## Available Plants

- **BSP** - Bhilai Steel Plant
- **DSP** - Durgapur Steel Plant
- **RSP** - Rourkela Steel Plant
- **BSL** - Bokaro Steel Plant
- **ISP** - Iyer Steel Plant

---

## API Endpoints

### 1. Get Available Data Months

**Endpoint:** `GET /api/techno-available-data`

**Description:** Returns all available plants and their months with data

**Query Parameters:** None

**Example URL:**
```
http://127.0.0.1:8082/api/techno-available-data
```

**Response:**
```json
{
  "status": "success",
  "plants": ["BSL", "BSP", "DSP", "ISP", "RSP"],
  "months": {
    "BSL": ["2026-06", "2026-05", "2025-05"],
    "BSP": ["2026-06", "2026-05", "2025-05"],
    "DSP": ["2026-06", "2026-05", "2025-05"],
    "ISP": ["2026-06", "2026-05", "2025-05"],
    "RSP": ["2026-06", "2026-05", "2025-05"]
  }
}
```

---

### 2. Get Furnace-Level Data

**Endpoint:** `GET /api/techno-furnace-data`

**Description:** Get technical parameters for a specific furnace

**Query Parameters:**
| Parameter | Required | Format | Example |
|-----------|----------|--------|---------|
| plant | Yes | String (uppercase) | BSP, DSP, RSP, BSL, ISP |
| report_month | Yes | YYYY-MM | 2025-05, 2026-06 |
| furnace | No | String | BF-1, BF-2, SMS-1, SMS-2 |

**Example URLs:**
```
# Get all furnaces for BSP in May 2025
http://127.0.0.1:8082/api/techno-furnace-data?plant=BSP&report_month=2025-05

# Get specific furnace BF-1
http://127.0.0.1:8082/api/techno-furnace-data?plant=BSP&report_month=2025-05&furnace=BF-1
```

**Response (All Furnaces):**
```json
{
  "status": "success",
  "plant": "BSP",
  "report_month": "2025-05",
  "furnaces": {
    "BF-1": {
      "Coke Rate": {
        "value": 428.5,
        "unit": "Kg/THM",
        "source": "Excel"
      },
      "BF Productivity": {
        "value": 2.15,
        "unit": "T/m³/day",
        "source": "Excel"
      },
      "HM Production": {
        "value": 10500.0,
        "unit": "T",
        "source": "Excel"
      }
    },
    "BF-2": {
      "Coke Rate": {
        "value": 430.2,
        "unit": "Kg/THM",
        "source": "Excel"
      },
      ...
    }
  }
}
```

**Response (Single Furnace):**
```json
{
  "status": "success",
  "plant": "BSP",
  "report_month": "2025-05",
  "furnace": "BF-1",
  "data": {
    "Coke Rate": {
      "value": 428.5,
      "unit": "Kg/THM",
      "source": "Excel"
    },
    "BF Productivity": {
      "value": 2.15,
      "unit": "T/m³/day",
      "source": "Excel"
    },
    "HM Production": {
      "value": 10500.0,
      "unit": "T",
      "source": "Excel"
    }
  }
}
```

---

### 3. Get Plant-Level Data

**Endpoint:** `GET /api/techno-plant-data`

**Description:** Get consolidated plant-level parameters (calculated from furnaces if needed)

**Query Parameters:**
| Parameter | Required | Format | Example |
|-----------|----------|--------|---------|
| plant | Yes | String (uppercase) | BSP, DSP, RSP, BSL, ISP |
| report_month | Yes | YYYY-MM | 2025-05, 2026-06 |

**Example URL:**
```
http://127.0.0.1:8082/api/techno-plant-data?plant=BSP&report_month=2025-05
```

**Response:**
```json
{
  "status": "success",
  "plant": "BSP",
  "report_month": "2025-05",
  "data": {
    "Coke Rate": {
      "value": 428.7,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 7,
      "furnaces": ["BF-1", "BF-2", "BF-3", "BF-4", "BF-5", "BF-6", "BF-7"]
    },
    "BF Productivity": {
      "value": 2.14,
      "unit": "T/m³/day",
      "calculation_method": "weighted_average_by_hm_production",
      "furnaces_used": 7,
      "furnaces": ["BF-1", "BF-2", "BF-3", "BF-4", "BF-5", "BF-6", "BF-7"]
    },
    "HM Production": {
      "value": 74500.0,
      "unit": "T",
      "calculation_method": "sum_of_furnaces",
      "furnaces_used": 7
    }
  },
  "calculation_details": {
    "Coke Rate": {
      "formula": "Weighted average by HM production",
      "furnaces_used": 7,
      "total_weight": 74500.0
    },
    "BF Productivity": {
      "formula": "Weighted average by HM production",
      "furnaces_used": 7,
      "total_weight": 74500.0
    }
  }
}
```

---

### 4. Get SAIL-Consolidated Data

**Endpoint:** `GET /api/techno-sail-consolidated`

**Description:** Get SAIL-wide consolidated parameters (across all 5 plants)

**Query Parameters:**
| Parameter | Required | Format | Example |
|-----------|----------|--------|---------|
| report_month | Yes | YYYY-MM | 2025-05, 2026-06 |

**Example URL:**
```
http://127.0.0.1:8082/api/techno-sail-consolidated?report_month=2025-05
```

**Response:**
```json
{
  "status": "success",
  "report_month": "2025-05",
  "data": {
    "Coke Rate": {
      "value": 429.2,
      "unit": "Kg/THM",
      "calculation_method": "weighted_average_5_plants"
    },
    "BF Productivity": {
      "value": 2.13,
      "unit": "T/m³/day",
      "calculation_method": "weighted_average_5_plants"
    },
    "HM Production": {
      "value": 250000.0,
      "unit": "T",
      "calculation_method": "sum_of_plants"
    }
  },
  "calculation_method": {
    "Coke Rate": "SAIL_direct",
    "BF Productivity": "avg_5_plants"
  }
}
```

---

### 5. Get Furnace List

**Endpoint:** `GET /api/techno-furnace-list`

**Description:** Get list of furnaces with data for a plant/month

**Query Parameters:**
| Parameter | Required | Format | Example |
|-----------|----------|--------|---------|
| plant | Yes | String (uppercase) | BSP, DSP, RSP, BSL, ISP |
| report_month | Yes | YYYY-MM | 2025-05, 2026-06 |

**Example URL:**
```
http://127.0.0.1:8082/api/techno-furnace-list?plant=BSP&report_month=2025-05
```

**Response:**
```json
{
  "status": "success",
  "plant": "BSP",
  "report_month": "2025-05",
  "furnaces": [
    {
      "furnace": "BF-1",
      "parameters": 5,
      "source": "Excel"
    },
    {
      "furnace": "BF-2",
      "parameters": 5,
      "source": "Excel"
    },
    {
      "furnace": "BF-3",
      "parameters": 5,
      "source": "Excel"
    },
    {
      "furnace": "SMS-1",
      "parameters": 3,
      "source": "Excel"
    }
  ]
}
```

---

## Data Structure

### Furnace-Level Parameters

Each furnace has a set of parameters with metadata:

```json
{
  "parameter_name": {
    "value": numeric,        // The actual measured/calculated value
    "unit": "string",        // Unit of measurement (Kg/THM, T/m³/day, etc.)
    "source": "string",      // Where data comes from (Excel, manual, calculated)
    "timestamp": "ISO8601"   // Optional: when measurement was taken
  }
}
```

**Common Parameters:**
- `Coke Rate` - Kg/THM (Kilograms per Tonne Hot Metal)
- `BF Productivity` - T/m³/day (Tonnes per cubic meter per day)
- `HM Production` - T (Tonnes of hot metal)
- `CDI` - Chemical Durability Index (Kg/THM)
- `Slag Rate` - Kg/THM

### Plant-Level Parameters

Plant-level data includes calculation metadata:

```json
{
  "parameter_name": {
    "value": numeric,
    "unit": "string",
    "calculation_method": "weighted_average_by_hm_production" | "sum_of_furnaces" | "from_source",
    "furnaces_used": integer,     // How many furnaces contributed to calculation
    "furnaces": ["BF-1", "BF-2"]  // Which furnaces were used
  }
}
```

---

## Query Examples

### Example 1: Get BSP Coke Rate for May 2025

**URL:**
```
GET /api/techno-plant-data?plant=BSP&report_month=2025-05
```

**Python:**
```python
import requests

response = requests.get(
    "http://127.0.0.1:8082/api/techno-plant-data",
    params={"plant": "BSP", "report_month": "2025-05"}
)
data = response.json()
coke_rate = data["data"]["Coke Rate"]["value"]
print(f"BSP Coke Rate (May 2025): {coke_rate} Kg/THM")
```

**cURL:**
```bash
curl "http://127.0.0.1:8082/api/techno-plant-data?plant=BSP&report_month=2025-05"
```

---

### Example 2: Compare Furnaces in Same Plant

**URL:**
```
GET /api/techno-furnace-data?plant=BSP&report_month=2025-05
```

**Python:**
```python
import requests

response = requests.get(
    "http://127.0.0.1:8082/api/techno-furnace-data",
    params={"plant": "BSP", "report_month": "2025-05"}
)
data = response.json()

# Compare coke rates across furnaces
for furnace, params in data["furnaces"].items():
    coke_rate = params["Coke Rate"]["value"]
    hm_prod = params["HM Production"]["value"]
    print(f"{furnace}: Coke Rate = {coke_rate}, HM = {hm_prod}")
```

---

### Example 3: Get All Available Months

**URL:**
```
GET /api/techno-available-data
```

**Python:**
```python
import requests

response = requests.get("http://127.0.0.1:8082/api/techno-available-data")
data = response.json()

# Print available months for each plant
for plant, months in data["months"].items():
    print(f"{plant}: {months}")
```

---

### Example 4: SAIL-Wide Consolidated Data

**URL:**
```
GET /api/techno-sail-consolidated?report_month=2025-05
```

**Python:**
```python
import requests

response = requests.get(
    "http://127.0.0.1:8082/api/techno-sail-consolidated",
    params={"report_month": "2025-05"}
)
data = response.json()

# Get SAIL-wide HM production
hm_total = data["data"]["HM Production"]["value"]
print(f"SAIL Total HM Production (May 2025): {hm_total} T")
```

---

## Data Separation

### Production Data vs Techno Data

| Aspect | Production | Techno |
|--------|------------|--------|
| **Tables** | production_data_json, production_plan_json | techno_furnace_data, techno_plant_data |
| **Level** | Plant-level only | Furnace + Plant levels |
| **Scope** | Production volumes (Crude Steel, Finished Steel) | Technical parameters (Coke Rate, Productivity) |
| **Unit** | '000 T | Kg/THM, T/m³/day, etc. |
| **Purpose** | Business reporting | Technical/operational analysis |
| **API Prefix** | `/api/` (generic) | `/api/techno-` (specialized) |

---

## Error Responses

### Invalid Plant Code
**Request:**
```
GET /api/techno-plant-data?plant=INVALID&report_month=2025-05
```

**Response (404):**
```json
{
  "status": "error",
  "message": "No data found for plant INVALID in month 2025-05"
}
```

### Invalid Date Format
**Request:**
```
GET /api/techno-plant-data?plant=BSP&report_month=2025-13
```

**Response (400):**
```json
{
  "status": "error",
  "message": "Invalid report_month format. Use YYYY-MM"
}
```

---

## Current Data Status

```
Furnace-Level Data:
  - Plants: 5 (BSP, DSP, RSP, BSL, ISP)
  - Months: 3 (2025-05, 2026-05, 2026-06)
  - Total Records: 17

Plant-Level Data:
  - Plants: 5 (BSP, DSP, RSP, BSL, ISP)
  - Total Records: 7 (calculated/consolidated)

Available Parameters:
  - Coke Rate (Kg/THM)
  - BF Productivity (T/m³/day)
  - HM Production (T)
  - CDI (Kg/THM)
  - Slag Rate (Kg/THM)
```

---

## Testing the API

### Quick Test from Browser

Visit these URLs in your browser (assuming server running on port 8082):

1. Check available data:
   ```
   http://127.0.0.1:8082/api/techno-available-data
   ```

2. Get BSP furnace data:
   ```
   http://127.0.0.1:8082/api/techno-furnace-data?plant=BSP&report_month=2025-05
   ```

3. Get BSP plant data:
   ```
   http://127.0.0.1:8082/api/techno-plant-data?plant=BSP&report_month=2025-05
   ```

### Automated Testing

```python
# test_techno_api.py
import requests

base_url = "http://127.0.0.1:8082"

# Test 1: Available data
response = requests.get(f"{base_url}/api/techno-available-data")
assert response.status_code == 200
print("✓ Available data endpoint works")

# Test 2: Furnace data
response = requests.get(
    f"{base_url}/api/techno-furnace-data",
    params={"plant": "BSP", "report_month": "2025-05"}
)
assert response.status_code == 200
print("✓ Furnace data endpoint works")

# Test 3: Plant data
response = requests.get(
    f"{base_url}/api/techno-plant-data",
    params={"plant": "BSP", "report_month": "2025-05"}
)
assert response.status_code == 200
print("✓ Plant data endpoint works")

# Test 4: SAIL consolidated
response = requests.get(
    f"{base_url}/api/techno-sail-consolidated",
    params={"report_month": "2025-05"}
)
assert response.status_code == 200
print("✓ SAIL consolidated endpoint works")

print("\nAll API endpoints functional!")
```

---

## Integration with Dashboard

The dashboard (`dashboard.html`) uses these endpoints to:
1. Load available plants and months via `/api/techno-available-data`
2. Display plant selector (dropdown)
3. Display month selector based on selected plant
4. Fetch and display techno parameters when plant/month selected

The new JSON-based techno tables **completely separate** from production tables ensure clean data organization.
