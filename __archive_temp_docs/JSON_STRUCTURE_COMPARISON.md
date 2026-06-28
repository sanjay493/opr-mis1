# JSON Structure Comparison - Furnace vs Shop vs Plant Data

## 🏭 Data Hierarchy Overview

```
BSP Plant
├── Furnace Level (Individual)
│   ├── BF-1: Coke Rate = 420.5, BF Productivity = 2.10
│   ├── BF-2: Coke Rate = 425.3, BF Productivity = 2.15
│   └── BF-3: Coke Rate = 428.8, BF Productivity = 2.18
│
├── Shop Level (Consolidated)
│   └── BF Shop: Coke Rate = 424.9 (avg of 3 BFs)
│
└── Plant Level (Overall)
    └── BSP Plant Shop: Coke Rate = 424.9
```

---

## 📊 APPROACH A: Plant-Level Only (Current)

**Single JSON per plant-month with consolidated values**

### Storage Structure
```json
{
  "id": 101,
  "plant": "BSP",
  "report_month": "2026-06",
  "level": "PLANT",
  "data": {
    "Coke Rate": {
      "value": 424.9,
      "unit": "Kg/THM",
      "source": "avg_3_furnaces"
    },
    "BF Productivity": {
      "value": 2.15,
      "unit": "T/m³/day",
      "source": "avg_3_furnaces"
    },
    "CDI Rate": {
      "value": 435.2,
      "unit": "Kg/THM",
      "source": "avg_3_furnaces"
    }
  },
  "metadata": {
    "source": "PDF",
    "source_file": "BSP_June_2026.pdf",
    "extraction_date": "2026-06-20T14:30:00",
    "quality": "extracted",
    "furnaces": ["BF-1", "BF-2", "BF-3"],
    "furnace_count": 3
  },
  "created_at": "2026-06-20T14:30:00",
  "updated_at": "2026-06-20T14:30:00"
}
```

### Query Example - Get BSP June Data
```sql
SELECT data FROM techno_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

### Result
```json
{
  "Coke Rate": {"value": 424.9, "unit": "Kg/THM"},
  "BF Productivity": {"value": 2.15, "unit": "T/m³/day"}
}
```

### Pros & Cons

**✅ Pros:**
- Single row per plant-month
- Simple queries
- Small JSON size
- Good for PDF reports (needs plant-level)
- Good for dashboard "All 5 Plants" (use SAIL consolidated)

**❌ Cons:**
- Cannot drill down to furnace-level data
- Lose granular furnace performance
- Cannot compare BF-1 vs BF-2 vs BF-3
- Source of average lost if not stored in "source" field

---

## 📊 APPROACH B: Hierarchical (Furnace + Shop + Plant)

**Single JSON per plant-month with ALL three levels nested**

### Storage Structure
```json
{
  "id": 101,
  "plant": "BSP",
  "report_month": "2026-06",
  "data": {
    "FURNACE": {
      "BF-1": {
        "Coke Rate": {
          "value": 420.5,
          "unit": "Kg/THM"
        },
        "BF Productivity": {
          "value": 2.10,
          "unit": "T/m³/day"
        },
        "CDI Rate": {
          "value": 433.2,
          "unit": "Kg/THM"
        }
      },
      "BF-2": {
        "Coke Rate": {
          "value": 425.3,
          "unit": "Kg/THM"
        },
        "BF Productivity": {
          "value": 2.15,
          "unit": "T/m³/day"
        },
        "CDI Rate": {
          "value": 435.2,
          "unit": "Kg/THM"
        }
      },
      "BF-3": {
        "Coke Rate": {
          "value": 428.8,
          "unit": "Kg/THM"
        },
        "BF Productivity": {
          "value": 2.18,
          "unit": "T/m³/day"
        },
        "CDI Rate": {
          "value": 437.2,
          "unit": "Kg/THM"
        }
      }
    },
    "SHOP": {
      "BF Shop": {
        "Coke Rate": {
          "value": 424.9,
          "unit": "Kg/THM",
          "calculation": "avg"
        },
        "BF Productivity": {
          "value": 2.14,
          "unit": "T/m³/day",
          "calculation": "avg"
        },
        "CDI Rate": {
          "value": 435.2,
          "unit": "Kg/THM",
          "calculation": "avg"
        }
      },
      "SMS Shop": {
        "SMS Productivity": {
          "value": 2.45,
          "unit": "T/hr"
        }
      }
    },
    "PLANT": {
      "BSP Plant Shop": {
        "Coke Rate": {
          "value": 424.9,
          "unit": "Kg/THM",
          "calculation": "all_furnaces"
        },
        "BF Productivity": {
          "value": 2.14,
          "unit": "T/m³/day"
        },
        "CDI Rate": {
          "value": 435.2,
          "unit": "Kg/THM"
        }
      }
    }
  },
  "metadata": {
    "source": "PDF",
    "source_file": "BSP_June_2026.pdf",
    "extraction_date": "2026-06-20T14:30:00",
    "quality": "extracted",
    "furnaces": ["BF-1", "BF-2", "BF-3"],
    "shops": ["BF Shop", "SMS Shop"]
  },
  "created_at": "2026-06-20T14:30:00",
  "updated_at": "2026-06-20T14:30:00"
}
```

### Query Examples

**Get Plant-Level Data**
```sql
SELECT JSON_EXTRACT(data, '$.PLANT."BSP Plant Shop"') AS plant_data
FROM techno_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

**Get Shop-Level Data**
```sql
SELECT JSON_EXTRACT(data, '$.SHOP."BF Shop"') AS bf_shop_data
FROM techno_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

**Get Specific Furnace Data**
```sql
SELECT JSON_EXTRACT(data, '$.FURNACE."BF-1"') AS bf1_data
FROM techno_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

**Get Coke Rate for All Furnaces**
```sql
SELECT 
  JSON_EXTRACT(data, '$.FURNACE."BF-1"."Coke Rate".value') AS BF1_Coke,
  JSON_EXTRACT(data, '$.FURNACE."BF-2"."Coke Rate".value') AS BF2_Coke,
  JSON_EXTRACT(data, '$.FURNACE."BF-3"."Coke Rate".value') AS BF3_Coke
FROM techno_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

### Pros & Cons

**✅ Pros:**
- All data in one place (single row)
- Can drill down to furnace level
- Can compare furnaces (BF-1 vs BF-2 vs BF-3)
- Can show shop-wise consolidated
- Can show plant-level
- Complete data lineage (furnace → shop → plant)

**❌ Cons:**
- Larger JSON size (redundant data across levels)
- Complex nested queries (JSON_EXTRACT syntax)
- Harder to extract for PDF reports
- Hard to update single furnace value
- Storage overhead (stores same parameter 3+ times)

---

## 📊 APPROACH C: Separate Tables per Level

**Three separate tables: furnace, shop, plant**

### Table 1: `techno_furnace_data`
```json
{
  "id": 1001,
  "plant": "BSP",
  "furnace": "BF-1",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {"value": 420.5, "unit": "Kg/THM"},
    "BF Productivity": {"value": 2.10, "unit": "T/m³/day"},
    "CDI Rate": {"value": 433.2, "unit": "Kg/THM"}
  },
  "metadata": {"source": "PDF", "quality": "extracted"}
}
```

### Table 2: `techno_shop_data`
```json
{
  "id": 2001,
  "plant": "BSP",
  "shop": "BF Shop",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {"value": 424.9, "unit": "Kg/THM", "calculation": "avg_3_furnaces"},
    "BF Productivity": {"value": 2.14, "unit": "T/m³/day", "calculation": "avg"}
  },
  "metadata": {"source": "calculated", "quality": "derived"}
}
```

### Table 3: `techno_plant_data`
```json
{
  "id": 3001,
  "plant": "BSP",
  "report_month": "2026-06",
  "data": {
    "Coke Rate": {"value": 424.9, "unit": "Kg/THM"},
    "BF Productivity": {"value": 2.14, "unit": "T/m³/day"}
  },
  "metadata": {"source": "PDF", "quality": "extracted"}
}
```

### Query Examples

**Get Plant-Level Data**
```sql
SELECT data FROM techno_plant_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

**Get Shop-Level Data**
```sql
SELECT data FROM techno_shop_data 
WHERE plant = 'BSP' AND shop = 'BF Shop' AND report_month = '2026-06'
```

**Get Furnace Data**
```sql
SELECT furnace, data FROM techno_furnace_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
```

**Compare All Furnaces**
```sql
SELECT furnace, JSON_EXTRACT(data, '$.Coke Rate.value') AS coke_rate
FROM techno_furnace_data 
WHERE plant = 'BSP' AND report_month = '2026-06'
ORDER BY furnace
```

### Pros & Cons

**✅ Pros:**
- Clean separation of concerns (furnace, shop, plant)
- Simple, flat queries
- Easy to update single furnace
- Efficient storage (no duplication)
- Clear data lineage
- Easy to archive old data per level
- Perfect for both drill-down AND consolidated reports

**❌ Cons:**
- 3 tables instead of 1
- Need to query multiple tables for full picture
- More complex ETL (need to calculate shops from furnaces)
- More rows in database

---

## 🎯 Comparison Matrix

| Aspect | Approach A (Plant) | Approach B (Hierarchical) | Approach C (Separate) |
|--------|------------------|---------------------------|----------------------|
| **Number of Tables** | 1 | 1 | 3 |
| **Rows per Month** | 5 (1 per plant) | 5 (1 per plant) | 65+ (5 plants × furnaces/shops/plant) |
| **JSON Size** | Small | Large (redundant) | N/A |
| **Furnace Drill-Down** | ❌ No | ✅ Yes | ✅ Yes |
| **Shop Consolidated** | ❌ No | ✅ Yes (nested) | ✅ Yes (separate table) |
| **Plant Consolidated** | ✅ Yes | ✅ Yes (nested) | ✅ Yes (separate table) |
| **Query Complexity** | Simple | Complex (JSON_EXTRACT) | Simple (separate tables) |
| **PDF Report** | ✅ Easy | ⚠️ Medium | ✅ Easy |
| **Dashboard "All 5"** | ✅ Easy | ✅ Easy | ✅ Easy (via SAIL table) |
| **Update Single Furnace** | ❌ Not possible | ⚠️ Hard (rewrite JSON) | ✅ Easy |
| **Calculation Logic** | Manual | Inside JSON | Separate ETL |
| **Data Consistency** | ✅ High | ⚠️ Medium (nested duplication) | ✅ High |

---

## 💡 My Recommendation

**Use Approach C (Separate Tables)** because:

1. **For PDF Reports**: Query `techno_plant_data` (single table, plant-consolidated only)
2. **For Dashboard All Plants**: Use `techno_sail_consolidated` (company-wide SAIL values)
3. **For Drill-Down Analysis**: Query `techno_furnace_data` to compare BF-1 vs BF-2
4. **For Plant Benchmarking**: Query `techno_shop_data` to compare BF Shop vs SMS Shop
5. **Clean separation**: Each table has clear responsibility
6. **Easy extraction**: No complex JSON_EXTRACT queries
7. **Easy updates**: Correct a furnace value without touching others
8. **Future-proof**: Easy to add new levels (e.g., section-wise)

---

## 📋 Approach C Implementation Pattern

### Extraction Flow
```
PDF/Excel Input
    ↓
Extract raw furnace-wise values
    ↓
INSERT INTO techno_furnace_data (all individual furnaces)
    ↓
CALCULATE shop averages
    ↓
INSERT INTO techno_shop_data (aggregated shops)
    ↓
CALCULATE plant overall
    ↓
INSERT INTO techno_plant_data (final plant consolidated)
    ↓
CALCULATE SAIL if all 5 plants have data
    ↓
UPDATE techno_sail_consolidated
```

### Retrieval Flow
```
For PDF Report:
  SELECT FROM techno_plant_data WHERE plant=? AND month=?
  
For Dashboard (All 5 Plants):
  SELECT FROM techno_sail_consolidated WHERE month=?
  
For Dashboard (Individual Plant):
  SELECT FROM techno_plant_data WHERE plant=?
  
For Furnace Comparison:
  SELECT FROM techno_furnace_data WHERE plant=? AND month=?
```

---

## 🤔 Which Approach Do You Prefer?

- **A (Plant-Only)**: If you ONLY need plant-level data, no furnace details needed
- **B (Hierarchical)**: If you need all levels but prefer single table (accept JSON complexity)
- **C (Separate Tables)**: If you want clean queries, easy updates, and drill-down capability (recommended)

What's your preference?
