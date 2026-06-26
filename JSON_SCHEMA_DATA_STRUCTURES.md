# JSON Schema - Data Structures Reference

Complete reference for the structure of data stored in each JSON table.

---

## 1. production_data_json

**Purpose:** Production actuals (monthly actual production values)

**Table Schema:**
```sql
production_data_json (
  id INTEGER PRIMARY KEY,
  report_month TEXT NOT NULL,  -- "2025-05", "2026-06", etc.
  data TEXT NOT NULL,          -- JSON string
  source TEXT,                 -- "excel", "manual", "migrated"
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE(report_month)
)
```

**JSON Structure:**
```json
{
  "plant_name": {
    "item_name": numeric_value,
    "item_name": numeric_value,
    ...
  },
  "plant_name": { ... }
}
```

**Complete Example (month: 2000-04):**
```json
{
  "ASP": {
    "Saleable Steel": 4.864,
    "Total Crude Steel": 8.741
  },
  "BSL": {
    "Saleable Steel": 10.5,
    "Total Crude Steel": 18.2
  },
  "BSP": {
    "Total Crude Steel": 313.29,
    "Finished Steel": 290.15,
    "Saleable Semis": 45.3,
    "Coke Rate": 428.5,
    "Hot Metal": 285.0,
    "Pig Iron": 2.1
  },
  "DSP": {
    "Total Crude Steel": 145.67,
    "Finished Steel": 130.2
  },
  "ISP": {
    "Total Crude Steel": 78.5,
    "Finished Steel": 72.3
  },
  "RSP": {
    "Total Crude Steel": 95.2,
    "Finished Steel": 88.9
  },
  "SSP": {
    "Total Crude Steel": 12.3,
    "Finished Steel": 11.5
  },
  "VISL": {
    "Total Crude Steel": 5.6,
    "Finished Steel": 5.1
  }
}
```

**Record Count:** 11,231 total records  
**Distinct Months:** 316  
**Data Points per Month:** 30-50 items across 8 plants  
**Typical Units:** '000 T (thousands of tonnes)

**Python Access:**
```python
import json
from backend import db

# Get production data for a month
data = db.get_production_data_json("2000-04")

# Access specific value
bsp_crude_steel = data["BSP"]["Total Crude Steel"]  # 313.29

# Iterate all plants
for plant_name, items in data.items():
    print(f"{plant_name}:")
    for item_name, value in items.items():
        print(f"  {item_name}: {value}")
```

---

## 2. production_plan_json

**Purpose:** Production plans (planned/budgeted production values)

**Table Schema:**
```sql
production_plan_json (
  id INTEGER PRIMARY KEY,
  report_month TEXT NOT NULL,  -- "2025-05", "2026-06", etc.
  data TEXT NOT NULL,          -- JSON string
  source TEXT,                 -- "excel", "manual", "migrated"
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE(report_month)
)
```

**JSON Structure:**
```json
{
  "plant_name": {
    "item_name": numeric_value,
    "item_name": numeric_value,
    ...
  },
  "plant_name": { ... }
}
```

**Example (month: 2025-06):**
```json
{
  "BSP": {
    "Total Crude Steel": 330.0,
    "Finished Steel": 305.0,
    "Saleable Steel": 295.0,
    "Hot Metal": 295.0,
    "Pig Iron": 2.5
  },
  "DSP": {
    "Total Crude Steel": 150.0,
    "Finished Steel": 135.0
  },
  "ISP": {
    "Total Crude Steel": 80.0,
    "Finished Steel": 73.0
  },
  "RSP": {
    "Total Crude Steel": 100.0,
    "Finished Steel": 92.0
  }
}
```

**Record Count:** 1,664 total records  
**Distinct Months:** 12  
**Structure:** Identical to production_data_json (plant → items → values)

**Python Access:**
```python
import json
from backend import db

# Get production plan for a month
plan_data = db.get_production_plan_json("2025-06")

# Compare actual vs plan
actual = db.get_production_data_json("2025-06")
bsp_actual = actual["BSP"]["Total Crude Steel"]
bsp_plan = plan_data["BSP"]["Total Crude Steel"]
variance = ((bsp_actual - bsp_plan) / bsp_plan) * 100
print(f"BSP Variance: {variance}%")
```

---

## 3. special_steel_json

**Purpose:** Special steel orders (non-standard products with specific grades and specifications)

**Table Schema:**
```sql
special_steel_json (
  id INTEGER PRIMARY KEY,
  report_month TEXT NOT NULL,
  data TEXT NOT NULL,          -- JSON string
  source TEXT,
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE(report_month)
)
```

**JSON Structure:**
```json
{
  "plant_name": [
    {
      "product": "string",
      "quality_grade": "string",
      "section": "string",
      "sort_order": integer,
      "order_qty": numeric_value,
      "actual_despatch": numeric_value
    },
    { ... }
  ],
  "plant_name": [ ... ]
}
```

**Complete Example (month: 2025-04):**
```json
{
  "DSP": [
    {
      "product": "ASP\nStructurals",
      "quality_grade": "E 250 B0",
      "section": "CHANNEL",
      "sort_order": 38,
      "order_qty": 132.0,
      "actual_despatch": 0.0
    },
    {
      "product": "Structurals",
      "quality_grade": "E 250 A0",
      "section": "CHANNEL",
      "sort_order": 39,
      "order_qty": 95.0,
      "actual_despatch": 45.5
    },
    {
      "product": "Rail",
      "quality_grade": "56 E1",
      "section": "FLAT",
      "sort_order": 1,
      "order_qty": 500.0,
      "actual_despatch": 450.0
    }
  ],
  "ISP": [
    {
      "product": "Wire Rod",
      "quality_grade": "LD",
      "section": "COIL",
      "sort_order": 10,
      "order_qty": 200.0,
      "actual_despatch": 180.0
    }
  ],
  "RSP": [
    {
      "product": "Heavy Structurals",
      "quality_grade": "ASTM A 36",
      "section": "BEAM",
      "sort_order": 5,
      "order_qty": 75.0,
      "actual_despatch": 75.0
    }
  ]
}
```

**Record Count:** 678 total records  
**Distinct Months:** 8  
**Records per Plant:** 10-50 per month  
**Typical Units:** Tonnes

**Python Access:**
```python
import json
import sqlite3
from backend import db

# Query special steel data
conn = sqlite3.connect(db.DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT data FROM special_steel_json WHERE report_month = ?", ("2025-04",))
row = cursor.fetchone()
conn.close()

if row:
    data = json.loads(row[0])
    
    # Iterate through plants and their orders
    for plant, orders in data.items():
        print(f"\n{plant}:")
        for order in orders:
            print(f"  {order['product']} - {order['quality_grade']}")
            print(f"    Section: {order['section']}")
            print(f"    Order Qty: {order['order_qty']} T")
            print(f"    Despatch: {order['actual_despatch']} T")
            
            # Calculate despatch rate
            if order['order_qty'] > 0:
                despatch_rate = (order['actual_despatch'] / order['order_qty']) * 100
                print(f"    Despatch Rate: {despatch_rate:.1f}%")
```

---

## 4. stock_data_json

**Purpose:** Inventory stock levels by plant, item type, and stock category

**Table Schema:**
```sql
stock_data_json (
  id INTEGER PRIMARY KEY,
  stock_month TEXT NOT NULL,
  data TEXT NOT NULL,          -- JSON string
  source TEXT,
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE(stock_month)
)
```

**JSON Structure (3-level hierarchy):**
```json
{
  "plant_name": {
    "item_type": {
      "stock_type": numeric_value,
      "stock_type": numeric_value,
      ...
    },
    "item_type": { ... }
  },
  "plant_name": { ... }
}
```

**Complete Example (month: 2024-01):**
```json
{
  "BSP": {
    "BLOOM/BILLETS": {
      "FOR SALE": 18.61,
      "INPROCESS": 90.311
    },
    "FINISHED STEEL": {
      "": 119.547
    },
    "PIG IRON": {
      "": 4.44
    },
    "SLABS": {
      "FOR SALE": 20.613,
      "INPROCESS": 31.594
    }
  },
  "DSP": {
    "BLOOM/BILLETS": {
      "FOR SALE": 80.567,
      "INPROCESS": 18.93
    },
    "FINISHED STEEL": {
      "": 16.41
    },
    "PIG IRON": {
      "": 9.922
    },
    "SEMI-FINISHED": {
      "FOR SALE": 45.2,
      "INPROCESS": 32.1
    }
  },
  "ISP": {
    "FINISHED STEEL": {
      "": 28.5
    },
    "SEMI-FINISHED": {
      "FOR SALE": 12.3,
      "INPROCESS": 5.6
    }
  },
  "RSP": {
    "FINISHED STEEL": {
      "": 42.1
    },
    "SEMI-FINISHED": {
      "FOR SALE": 18.9,
      "INPROCESS": 8.2
    }
  }
}
```

**Record Count:** 286 total records  
**Distinct Months:** 17  
**Typical Units:** '000 T (thousands of tonnes)  
**Stock Types:** "FOR SALE", "INPROCESS", or empty string ("")

**Python Access:**
```python
import json
import sqlite3
from backend import db

# Query stock data
conn = sqlite3.connect(db.DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT data FROM stock_data_json WHERE stock_month = ?", ("2024-01",))
row = cursor.fetchone()
conn.close()

if row:
    data = json.loads(row[0])
    
    # Access specific stock value (3-level navigation)
    bsp_blooms_for_sale = data["BSP"]["BLOOM/BILLETS"]["FOR SALE"]
    print(f"BSP Blooms for Sale: {bsp_blooms_for_sale} '000T")
    
    # Sum all stock of an item type
    bsp_blooms_total = sum(data["BSP"]["BLOOM/BILLETS"].values())
    print(f"BSP Total Blooms: {bsp_blooms_total} '000T")
    
    # Iterate plant → item_type → stock_type
    for plant, item_types in data.items():
        for item_type, stock_types in item_types.items():
            for stock_type, quantity in stock_types.items():
                stock_cat = stock_type if stock_type else "TOTAL"
                print(f"{plant} {item_type} ({stock_cat}): {quantity} '000T")
```

**SQL JSON_EXTRACT Example:**
```sql
-- Get BSP finished steel stock for 2024-01
SELECT JSON_EXTRACT(data, '$.BSP."FINISHED STEEL"."FOR SALE"')
FROM stock_data_json
WHERE stock_month = '2024-01';
-- Returns: 119.547
```

---

## 5. ipt_data_json

**Purpose:** Inter-Plant Transfer (IPT) data - movement of materials between plants

**Table Schema:**
```sql
ipt_data_json (
  id INTEGER PRIMARY KEY,
  report_month TEXT NOT NULL,
  data TEXT NOT NULL,          -- JSON string
  source TEXT,
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE(report_month)
)
```

**JSON Structure:**
```json
{
  "item_name": [
    {
      "from_plant": "string",
      "to_plant": "string",
      "unit": "string",
      "sort_order": integer,
      "plan": numeric_value,
      "actual": numeric_value,
      "plan_tonnage": numeric_value,
      "actual_tonnage": numeric_value
    },
    { ... }
  ],
  "item_name": [ ... ]
}
```

**Complete Example (month: 2026-04):**
```json
{
  "BF coke": [
    {
      "from_plant": "BSL",
      "to_plant": "ISP",
      "unit": "MT",
      "sort_order": 1,
      "plan": 2.0,
      "actual": 2.0,
      "plan_tonnage": 2000.0,
      "actual_tonnage": 2000.0
    },
    {
      "from_plant": "BSL",
      "to_plant": "RSP",
      "unit": "MT",
      "sort_order": 2,
      "plan": 1.5,
      "actual": 1.5,
      "plan_tonnage": 1500.0,
      "actual_tonnage": 1500.0
    }
  ],
  "CC Blooms": [
    {
      "from_plant": "BSP",
      "to_plant": "ASP",
      "unit": "MT",
      "sort_order": 1,
      "plan": 1000.0,
      "actual": 1120.0,
      "plan_tonnage": 1000000.0,
      "actual_tonnage": 1120000.0
    }
  ],
  "CC Slabs": [
    {
      "from_plant": "BSL",
      "to_plant": "RSP",
      "unit": "MT",
      "sort_order": 1,
      "plan": 35000.0,
      "actual": 11507.0,
      "plan_tonnage": 35000000.0,
      "actual_tonnage": 11507000.0
    },
    {
      "from_plant": "BSP",
      "to_plant": "ISP",
      "unit": "MT",
      "sort_order": 2,
      "plan": 5000.0,
      "actual": 4800.0,
      "plan_tonnage": 5000000.0,
      "actual_tonnage": 4800000.0
    }
  ],
  "Coke Breeze": [
    {
      "from_plant": "BSL",
      "to_plant": "ISP",
      "unit": "MT",
      "sort_order": 1,
      "plan": 1.0,
      "actual": 1.0,
      "plan_tonnage": 1000.0,
      "actual_tonnage": 1000.0
    }
  ],
  "Mixed Coke": [
    {
      "from_plant": "BSL",
      "to_plant": "RSP",
      "unit": "MT",
      "sort_order": 1,
      "plan": 1.0,
      "actual": 1.0,
      "plan_tonnage": 1000.0,
      "actual_tonnage": 1000.0
    }
  ],
  "Screened Coke": [
    {
      "from_plant": "BSL",
      "to_plant": "CFP",
      "unit": "MT",
      "sort_order": 1,
      "plan": 1.0,
      "actual": 0.0,
      "plan_tonnage": 1000.0,
      "actual_tonnage": 0.0
    }
  ],
  "Sinter": [
    {
      "from_plant": "DSP",
      "to_plant": "BSL",
      "unit": "MT",
      "sort_order": 1,
      "plan": 2.0,
      "actual": 0.0,
      "plan_tonnage": 2000.0,
      "actual_tonnage": 0.0
    }
  ],
  "Spade/ 2Pi / Jackal Slabs": [
    {
      "from_plant": "ASP",
      "to_plant": "RSP",
      "unit": "MT",
      "sort_order": 1,
      "plan": 250.0,
      "actual": 525.0,
      "plan_tonnage": 250000.0,
      "actual_tonnage": 525000.0
    }
  ]
}
```

**Record Count:** 26 total records  
**Distinct Months:** 2  
**Records per Month:** 8-15 items with multiple routes each  
**Typical Units:** MT (Metric Tonnes), with dual measurements (plan/tonnage variants)

**Python Access:**
```python
import json
import sqlite3
from backend import db

# Query IPT data
conn = sqlite3.connect(db.DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT data FROM ipt_data_json WHERE report_month = ?", ("2026-04",))
row = cursor.fetchone()
conn.close()

if row:
    data = json.loads(row[0])
    
    # Iterate through items and their routes
    for item_name, routes in data.items():
        print(f"\n{item_name}:")
        for route in routes:
            from_plant = route["from_plant"]
            to_plant = route["to_plant"]
            actual = route["actual"]
            plan = route["plan"]
            
            # Calculate variance
            if plan > 0:
                variance = ((actual - plan) / plan) * 100
                print(f"  {from_plant} → {to_plant}: Plan {plan} MT, Actual {actual} MT ({variance:+.1f}%)")
            else:
                print(f"  {from_plant} → {to_plant}: Actual {actual} MT")
            
            # Tonnage details
            print(f"    Tonnage: {route['actual_tonnage']:,} / {route['plan_tonnage']:,}")
```

---

## Summary Table

| Table | Record Count | Months | Structure | Primary Keys |
|-------|--------------|--------|-----------|--------------|
| production_data_json | 11,231 | 316 | plant → items → value | report_month |
| production_plan_json | 1,664 | 12 | plant → items → value | report_month |
| special_steel_json | 678 | 8 | plant → [orders] | report_month |
| stock_data_json | 286 | 17 | plant → type → category → value | stock_month |
| ipt_data_json | 26 | 2 | item → [routes] | report_month |
| **TOTAL** | **13,885** | **~355** | **Mixed** | **Date** |

---

## Field Types Reference

| Field | Type | Examples | Notes |
|-------|------|----------|-------|
| report_month / stock_month | TEXT | "2025-05", "2026-06" | Format: YYYY-MM |
| plant_name | TEXT | "BSP", "DSP", "RSP", "ISP", "BSL", "ASP", "SSP", "VISL" | 8 plants in SAIL group |
| item_name | TEXT | "Total Crude Steel", "Finished Steel", "Coke Rate" | Production items |
| value (numeric) | FLOAT | 313.29, 95.5, 428.5 | May be NULL for missing data |
| product | TEXT | "Rail", "Structurals", "Wire Rod" | Special steel product |
| quality_grade | TEXT | "E 250 B0", "56 E1", "ASTM A 36" | Product specification |
| section | TEXT | "CHANNEL", "FLAT", "BEAM", "COIL" | Shape/form |
| sort_order | INTEGER | 1, 2, 38, 39 | Display/processing order |
| unit | TEXT | "MT", "'000T" | Measurement unit |
| from_plant / to_plant | TEXT | "BSP", "DSP", "CFP" | Plant codes |

---

## Accessing Data Programmatically

### Python Examples

```python
import json
import sqlite3
from backend import db

# Initialize DB
db.init_db()

# === PRODUCTION DATA ===
prod_data = db.get_production_data_json("2025-06")
if prod_data:
    bsp_crude = prod_data["BSP"]["Total Crude Steel"]
    print(f"BSP Crude Steel: {bsp_crude} '000T")

# === SPECIAL STEEL ===
conn = sqlite3.connect(db.DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT data FROM special_steel_json WHERE report_month = ?", ("2025-04",))
row = cursor.fetchone()
if row:
    ss_data = json.loads(row[0])
    for plant, orders in ss_data.items():
        print(f"{plant}: {len(orders)} orders")
conn.close()

# === STOCK DATA ===
cursor.execute("SELECT data FROM stock_data_json WHERE stock_month = ?", ("2024-01",))
row = cursor.fetchone()
if row:
    stock_data = json.loads(row[0])
    bsp_blooms = stock_data["BSP"]["BLOOM/BILLETS"]["FOR SALE"]
    print(f"BSP Blooms for Sale: {bsp_blooms}")

# === IPT DATA ===
cursor.execute("SELECT data FROM ipt_data_json WHERE report_month = ?", ("2026-04",))
row = cursor.fetchone()
if row:
    ipt_data = json.loads(row[0])
    cc_blooms = ipt_data["CC Blooms"]
    print(f"CC Blooms routes: {len(cc_blooms)}")
```

### SQL JSON Queries

```sql
-- Get all production months
SELECT DISTINCT report_month FROM production_data_json ORDER BY report_month;

-- Extract single value
SELECT JSON_EXTRACT(data, '$.BSP."Total Crude Steel"')
FROM production_data_json
WHERE report_month = '2025-06';

-- Count items for a plant
SELECT JSON_OBJECT_LENGTH(JSON_EXTRACT(data, '$.BSP'))
FROM production_data_json
WHERE report_month = '2025-06';

-- Get all plants in a month
SELECT JSON_KEYS(data)
FROM production_data_json
WHERE report_month = '2025-06';

-- Stock hierarchy query
SELECT JSON_EXTRACT(data, '$.BSP.*')
FROM stock_data_json
WHERE stock_month = '2024-01';
```

---

## Data Validation Notes

✅ All numeric values preserved with full precision  
✅ NULL values handled correctly  
✅ String values with special characters (newlines, spaces) preserved  
✅ Hierarchical nesting depth: max 3 levels (stock_data)  
✅ Array ordering preserved (sort_order used for special_steel, ipt)  
✅ Timestamp fields (created_at, updated_at) auto-populated  
✅ Source field tracks data origin (migrated, excel, manual)

