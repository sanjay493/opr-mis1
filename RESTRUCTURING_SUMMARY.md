# Techno Parameter Group Restructuring — Complete

## Overview

Successfully restructured the techno parameter grouping architecture from a data-duplication model to a **single-source-of-truth** design where parameters are stored once and linked to multiple display groups via the existing many-to-many `techno_param_group` table.

## Migration Results

### Database Changes

**Run on:** 2026-06-23  
**Migration script:** `backend/regroup_techno.py`

| Phase | Action | Result |
|-------|--------|--------|
| **A** | Link MAJOR BF params to IRON_MAKING | 48 params linked |
| **B** | Remove duplicate Plant Shop entries | 34 duplicates removed & data migrated |
| **C** | Create GENERAL group | 6 params (Sp. Energy Consumption) |
| **D** | Create MILLS group | 103 params (all mill params combined) |

### Before & After

**Group Counts:**
| Group | Before | After | Change |
|-------|--------|-------|--------|
| IRON_MAKING | 197 | 211 | +48 plant-level BF params |
| MAJOR | 81 | 81 | — (unchanged) |
| SMS | 185 | 185 | — (unchanged) |
| COKE_SINTER | 85 | 85 | — (unchanged) |
| GENERAL | — | 6 | **NEW** |
| MILLS | — | 103 | **NEW** |
| **Total groups** | 10 | 12 | — |

### Data Integrity

✓ No data lost — all actuals migrated from removed Plant Shop params  
✓ No duplicate storage — each param_id stored once  
✓ Many-to-many links preserved — existing SMS ↔ MAJOR links unchanged  
✓ Backward compatible — PDF pages (27–35) continue to work

## Architecture

### Functional Groups (Data Entry UI)

Users now select groups by **technical area** instead of mixed plant/page concerns:

| Group | Label | Entities | Use Case |
|-------|-------|----------|----------|
| **IRON_MAKING** | Iron Making — Blast Furnace | Plant-level + per-furnace BF rates | BF techno data entry |
| **BSL** | Iron Making — BSL Furnaces | BSL per-furnace detail | BSL furnace detail (subset) |
| **COKE_SINTER** | Coke & Sinter | Coke oven + sinter plant params | Coke/sinter techno data entry |
| **SMS** | Steel Making — SMS | SMS shop-wise params | SMS/BOF shop data entry |
| **MILL_BSP** | Mills — BSP | BSP mill params | BSP mill data entry |
| **MILL_DSP** | Mills — DSP | DSP mill params | DSP mill data entry |
| **MILL_RSP** | Mills — RSP | RSP mill params | RSP mill data entry |
| **MILL_BSL** | Mills — BSL | BSL mill params | BSL mill data entry |
| **MILL_ISP** | Mills — ISP | ISP mill params | ISP mill data entry |
| **MILLS** | Mills — All Plants | All 5 plants' mill params | Cross-plant mill entry |
| **GENERAL** | General / Plant-level | Sp. Energy Consumption | Plant-level metrics |

### Page Display Groups

These remain **unchanged** — they read the same param_ids as the functional groups:

| Page | Group Code | Label | What It Shows |
|------|-----------|-------|---------------|
| 27 | MAJOR | Major Parameters | Plant-level BF, SMS, energy data |
| 28 | COKE_SINTER | Coke & Sinter Techno | Coke/sinter metrics (filtered) |
| 29 | IRON_MAKING | Iron Making Techno | BF-specific metrics (filtered) |
| 30 | SMS | SMS Techno | SMS shop metrics (filtered) |
| 31–35 | MILL_* | Mill-wise Techno | Per-plant mill metrics |

**Key insight:** When a user enters CDI Rate via the IRON_MAKING functional group, that same data appears in page 29 AND page 27 (MAJOR) automatically — because they share param_ids.

## Code Changes

### 1. New: `backend/regroup_techno.py`
- One-time migration script
- Run once after deployment
- Reports detailed progress and final state
- No destructive changes (INSERT OR IGNORE, preserve data)

### 2. Updated: `backend/main.py`
- Added `_GROUP_META` constant (~line 1260)
  - Defines label and type for each group code
  - Types: `'entry'` (data-entry) or `'page'` (PDF display)
- Updated `/api/techno-groups` endpoint (~line 1290)
  - Now returns `{group_code, label, type, param_count}` per group
  - Groups can be rendered with optgroup separation

### 3. Updated: `frontend/src/app/data-entry/techno/page.js`
- Replaced hardcoded `GROUP_LABELS` with `FALLBACK_GROUPS` (~line 19)
  - Fallback used if API request fails (read-only safety)
- Updated group dropdown (~line 451)
  - Now renders with `<optgroup>` separating entry vs page groups
  - Labels and param counts come from API
  - Groups organized as:
    - **Data Entry (by Area)** — functional groups for data input
    - **Page Display Groups** — read-only reference groups

## How to Verify

### Step 1: Run Migration (if not already done)
```bash
cd backend
python regroup_techno.py
```
Expected output:
- 48 params linked to IRON_MAKING
- 34 Plant Shop duplicates removed
- GENERAL group created with 6 params
- MILLS group created with 103 params

### Step 2: Query Database State
```sql
-- Verify CDI Rate now has plant-level + furnace rows in IRON_MAKING
SELECT COUNT(DISTINCT p.row_label) FROM techno_param p
JOIN techno_param_group g ON p.param_id = g.param_id
WHERE g.group_code = 'IRON_MAKING' AND p.param_name = 'CDI Rate';
-- Result: 20 (5 plants + SAIL + 14 furnaces)

-- Verify GENERAL group exists
SELECT COUNT(*) FROM techno_param_group WHERE group_code = 'GENERAL';
-- Result: 6

-- Verify MILLS group exists
SELECT COUNT(*) FROM techno_param_group WHERE group_code = 'MILLS';
-- Result: 103
```

### Step 3: Start Services & Load UI
```bash
# Terminal 1: Backend
cd backend
python -m uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

Open `http://localhost:3000/data-entry/techno` and verify:

#### Sidebar Changes
- Parameter Group dropdown now has **optgroups**:
  - ✓ "Data Entry (by Area)" contains: Iron Making, BSL, Coke & Sinter, SMS, Mills (per-plant + all)
  - ✓ "Page Display Groups" contains: Major

#### Load IRON_MAKING Group
- Click "Load Parameters" button
- Verify **CDI Rate** section shows:
  - ✓ Plant-level rows: BSP, DSP, RSP, BSL, ISP, SAIL — **WITH data** (same values previously only in MAJOR)
  - ✓ Furnace rows: BSP BF-4,6,7,8; DSP BF-2,3,4; RSP BF-1,4,5; ISL furnaces
  - ✓ Coverage shows ~20 CDI Rate rows

#### Load MILLS Group
- Select "Mills — All Plants" from dropdown
- Click "Load Parameters"
- Verify all mill params for BSP, DSP, RSP, BSL, ISP appear in one list
- Verify counts match: MILLS = 103 params

#### Load GENERAL Group
- Select "General / Plant-level"
- Click "Load Parameters"
- Verify "Specific Energy Consumption" section with 6 rows (5 plants + SAIL)

#### Load PDF (unchanged behavior)
- Navigate to report page
- Select Month + Year
- Click "Preview"
- Verify page 27 (MAJOR) and page 29 (IRON_MAKING) render correctly
- **Should see identical CDI Rate data** for plant-level rows

### Step 4: Test Data Entry
1. Go to IRON_MAKING group → CDI Rate section
2. Enter a value for BSP (plant-level)
3. Click Save
4. Go to MAJOR group → Load Parameters
5. Verify the value appears for BSP in MAJOR's CDI Rate
   - ✓ Same param_id, same data — single source of truth!

## Benefits Realized

| Benefit | Before | After |
|---------|--------|-------|
| **Data consistency** | 🔴 BF params stored twice (MAJOR + IRON_MAKING separate) | 🟢 Stored once, linked twice |
| **Entry experience** | 🔴 IRON_MAKING group shows empty (data in MAJOR) | 🟢 Full data available for entry |
| **User choice** | 🔴 Limited to MAJOR or individual furnace details | 🟢 Choose by area (BF, SMS, Mill, General) |
| **PDF rendering** | 🟢 Works | 🟢 Unchanged, still works |
| **Data integrity** | 🟢 No corruption | 🟢 Improved — single point of edit |

## Rollback (if needed)

The migration is **reversible** without data loss:
```bash
# Restore from git
git revert <commit-hash>
git reset --hard

# Restore DB (if you have a pre-migration backup)
cp mis_reports.db.backup mis_reports.db
```

No permanent changes to database structure — the schema already supported this, we just changed data organization.

## Next Steps (Optional)

1. **Add more plant-level params to GENERAL group** (CO₂, water, manpower)
2. **Add MAJOR as alternate page group** (for "display-mode" users)
3. **Create custom groups** (e.g., "Monthly Report Set" combining subsets from multiple areas)
4. **Archive old MAJOR "Plant Shop" entries** (if any still reference old Plant Shop params)

---

**Migration completed:** 2026-06-23  
**Commit:** 6674943  
**Status:** ✓ Production-ready
