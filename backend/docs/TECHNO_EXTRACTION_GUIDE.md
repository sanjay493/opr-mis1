# Techno-Economic Parameter Extraction — Developer Guide

This is a reference for maintaining and extending the techno-economic parameter
pipeline: how each plant's source files get turned into rows in `techno_data`,
how those rows reach the frontend report pages, and — most importantly — what
to change (and what *not* to change) when a source file's format shifts or a
new parameter needs to be tracked.

Written from the extraction rewrites and bug fixes done across RSP, BSP, DSP,
ISP and BSL in 2026; every example below is a real case, not a hypothetical.

---

## 1. The data model

Everything lands in one SQLite table: `techno_data`.

```
techno_data
  id, plant, report_month ('YYYY-MM'), unit, techno_json

techno_json = {
  "month":      { param_key: value, ... },   # this month's figure
  "till_month": { param_key: value, ... },   # April → report_month cumulative
}
```

- **`unit`** is a shop/furnace/mill name, not a plant-wide bucket: `"BF-1"`,
  `"COB-old"`, `"SMS-I"`, `"General"` (plant-wide KPIs with no natural unit).
  Unit names are **not** standardized across plants — RSP splits its coke
  ovens into `COB-old`/`COB-new`, BSP has one combined `COB`, DSP/BSL call
  theirs `Coke Ovens`. This is the single biggest source of "why is this
  plant's data invisible on the report page" bugs — see §5.
- **`param_key`** is a snake_case name, meant to be the *same string* across
  every plant that reports that parameter (`coke_rate`, `cdi`,
  `specific_hm_consumption`, ...). In practice, plants drift apart over time
  because each extractor was written independently against its own source
  file's wording. Reconciling this drift is most of the maintenance work on
  this pipeline — see §6.
- Two DB-writing functions in `db.py`:
  - `merge_upsert_techno_data(plant, report_month, unit, new_techno_json, source_file)`
    — merges new **non-null** values into whatever's already there.
    **A new non-null value always overwrites the existing one**, even if the
    existing value came from a more authoritative source — there is no
    "don't clobber a good value" protection built in. This is exactly why the
    "final vs. tentative" extractor pairing (§2) depends on both writing the
    *same* key name — see the incident in §6.
  - `upsert_techno_data(...)` — full replace of a unit's whole `techno_json`.

---

## 2. Per-plant extraction architecture

Every plant except SAIL has (at least) two extraction paths feeding the same
table: a **final** extractor that reads the authoritative monthly report, and
a **monthend/tentative** extractor that reads a same-day/next-day preliminary
report so the dashboard has *something* before the final report arrives. Both
write into the exact same `(plant, report_month, unit)` row via
`merge_upsert_techno_data`, so if they don't use the same `param_key` for the
same real-world figure, the "final" value never actually overwrites the
"tentative" one — both spellings just sit there side by side. This is the
single most common bug class in this codebase (see §6, "Two extractors, two
spellings").

| Plant | Final extractor | Reads | Monthend/tentative extractor |
|---|---|---|---|
| **RSP** | `techno_project/rsp_technopara_extractor.py` (+ `rsp_technopara_sections.py` registry) | `TECHNOPARA <MONTH><YYYY>.xlsx`, sheet matching `PAGE-?1-8/9` | `techno_project/rsp_monthend_techno_extractor.py` (Daily Morning Report) |
| **BSP** | `techno_project/bsp_extractor.py` + `bsp_oisco_extractor.py`, row numbers from `bsp_techno_map.json` / `bsp_oisco_map.json` | `3 page Tech for CO_<Mon>'<YY>.xls(x)`, OISCO Excel | `excel_extractors/pdf_extractor_bsp_flash.py` (Flash.pdf) |
| **DSP** | `techno_project/dsp_technopara_extractor.py` (imports label/regex tables from `excel_extractors/pdf_extractor_dsp.py`) | DSP monthly PDF report | `techno_project/dsp_mcr_techno_extractor.py` (MCR daily Excel, `mcr1_*.xlsx`) |
| **ISP** | `techno_project/isp_technopara_extractor.py`, row numbers from `isp_technopara_map.json` | `Summarized Monthly Report <Month>'<YY>.xlsx` | `techno_project/isp_monthend_techno_extractor.py` (Morning Report) |
| **BSL** | `techno_project/bsl_technopara_extractor.py` (`_RAW_TO_PARAM_KEY`-style dict) | BF PDF report + BSL technopara Excel | `techno_project/bsl_mer_parser.py` (MER report) |
| **SAIL** | `api_techno_manual.py`'s `_compute_sail_bf` | *no raw file* — computed as a weighted average of RSP/BSP/ISP/DSP/BSL's own `BF_Shop` unit, weighted by each plant's Hot Metal production | manual entry via `/data-entry/techno-manual`, plus historical bulk-CSV rows |

### Two different mapping styles

Extractors resolve "which row is which parameter" one of two ways:

1. **JSON row-number map** (BSP, ISP) — a `{unit: {param_key: row_number}}`
   JSON file, read by a thin Python wrapper that just does
   `ws.cell(row_number, month_col).value`. Fast to edit (no Python knowledge
   needed — just the row number), but **brittle**: if the source file's row
   layout shifts by even one row, every mapping below the shift silently
   reads the wrong cell. This is why RSP was rewritten away from this style
   (see the retired `rsp_technopara_map.json` — replaced by the
   section-aware registry below) and why DSP/BSL use label-matching instead.

2. **Label-matching registry** (RSP, DSP, BSL) — the extractor walks the
   sheet top-to-bottom, and resolves each row by matching its *own label
   text* against a registered dictionary, never by row number. This survives
   row insertions/deletions in the source file for free, at the cost of
   needing exact (or alias-covered) label text. RSP's version
   (`rsp_technopara_sections.py`) is the canonical example — see §4/§5 for
   how to extend and debug it.

---

## 3. The full mapping chain

```
Source file (Excel/PDF)
   │  extractor reads labels/rows, resolves (unit, param_key, value)
   ▼
techno_data table   { plant, report_month, unit, techno_json: {month, till_month} }
   │  page_techno.py's _TECHNO_DB_SCHEMA[page_no]["sections"] looks up
   │  (unit, param_key) tuples per plant
   ▼
generate_techno_from_db(report_month, page_no)   → { sections: [{label, rows: [...]}] }
   │  served via /api/... to the frontend
   ▼
frontend/src/components/TechnoParamsTemplate.js   renders the table
```

The critical file is **`backend/page_techno.py`**'s `_TECHNO_DB_SCHEMA` dict
(pages 28-35) — it is the *only* place that says "here's which unit+key
combination, for which plant, shows up as a row in this parameter's
section." An extractor can be writing perfectly good data into `techno_data`
and it will still never appear anywhere if this schema doesn't have an entry
for that plant's unit name.

```python
# page_techno.py, page 28's schema — one row per (label, unit_str, unit_specs)
28: {
    "type": "param",
    "sections": [
        ("BF Coke Yield", "%",
         [("COB-old", "bf_coke_yield"), ("COB-new", "bf_coke_yield"),
          ("Coke Ovens", "bf_coke_yield"), ("COB", "bf_coke_yield")]),
        ...
    ],
},
```

Each `(unit, key)` pair is checked **per plant** — the generic renderer loop
(`generate_techno_from_db`, around line 2046) iterates every plant in
`available_plants` and, for each, tries every `(unit, key)` pair in the
row's `unit_specs` list; whichever pair actually has non-null data for that
plant produces a row. A plant whose unit name isn't in the list is *silently
skipped*, not flagged — which is exactly how several real bugs escaped
notice (§5).

---

## 4. Worked example: adding a new parameter end-to-end

Say RSP's source file gains a new row, "Slag Basicity", under the
`SINTER PLANT-I` section, and you want it on page 29.

**Step 1 — find the exact label text.** Open the source file, find the row,
copy its column-A text *verbatim*, including odd spacing/capitalization
(`norm_label` only collapses whitespace and lowercases — it does **not**
strip punctuation, so `"Slag Basicity"` and `"Slag  Basicity "` normalize
to different strings if the punctuation/wording itself differs, but not if
only extra spaces differ).

**Step 2 — pick a canonical key name.** Check whether any *other* plant
already reports this parameter under some name — search `page_techno.py`'s
three alias tables (`_KEY_ALIASES`, `_COKE_OVEN_PARAM_ALIASES`,
`_SAIL_MANUAL_PARAM_KEYS`) and `main.py`'s `_PARAM_KEY_ALIASES` for anything
like `slag_basicity`, `basicity_of_sinter`, etc. If BSL already reports
`basicity_of_sinter` for the conceptually same figure, use that same key —
don't invent a second name for the same concept (this is the #1 cause of
the "duplicate parameter" cleanups done throughout 2026 — o2_enrichment vs
oxygen_enrichment, cdi vs cdi_rate, coal_to_hm vs coal_to_hot_metal, etc.).
If it's genuinely new, pick a clear snake_case name now — renaming later
means a DB migration.

**Step 3 — register the extraction.** In `rsp_technopara_sections.py`:

```python
PARAM_ALIASES = {
    ...
    "Slag Basicity": ("SP-1", "basicity_of_sinter"),   # raw label → (unit, key)
}
```

If the same label text appears under multiple sinter plants (SP-1/SP-2/SP-3)
with the section header already setting `current_unit` correctly, you don't
need the `(unit, key)` tuple form — a bare `"Slag Basicity": "basicity_of_sinter"`
resolves against whatever `current_unit` the walk has already established
from the enclosing section header (see `SECTION_UNITS` a few lines above).

**Step 4 — add it to the report schema.** In `page_techno.py`'s page 29:

```python
("Slag Basicity", "ratio",
 [("SP-1", "basicity_of_sinter"), ("SP-2", "basicity_of_sinter"),
  ("SP-3", "basicity_of_sinter"), ("SP", "basicity_of_sinter")]),
```

List every unit name across every plant that might report this parameter —
not just RSP's. A row that's missing a plant's unit name silently drops that
plant, exactly as in §5's examples.

**Step 5 — verify.** Re-run the extractor against a real sample file and
check the value shows up:

```python
from techno_project.rsp_technopara_extractor import TechnoExtractor
recs = TechnoExtractor("path/to/file.xlsx", report_month="2026-06").extract()
print(next(r for r in recs if r["unit"] == "SP-1")["techno_json"]["month"])
```

Then functionally check the report page itself:

```python
import db; db.DB_PATH = "path/to/mis_reports.db"
import page_techno
result = page_techno.generate_techno_from_db("2026-06", 29)
# confirm "Slag Basicity" appears in result["sections"]
```

**Step 6 — backfill if needed.** New parameters obviously won't exist in
already-saved historical DB rows. If you have the original source files for
past months, re-extract just that one unit/key and merge it in — this is
additive and safe (`merge_upsert_techno_data` never touches other keys):

```python
db.merge_upsert_techno_data(
    plant="RSP", report_month="2025-04", unit="SP-1",
    new_techno_json={"month": {"basicity_of_sinter": 2.1},
                      "till_month": {"basicity_of_sinter": 2.05}},
    source_file="backfill:...",
)
```

**Step 7 — run the tests.** `pytest tests -q` from `backend/` — the
row-stability tests (`tests/test_rsp_technopara_row_stability.py`, and its
ISP/DSP/BSL/BSP siblings) run the extractor against every real sample file
in the repo and check crash-free extraction plus some plausible-value-range
regression guards. If your new parameter has a plausible numeric range,
consider adding a guard for it there too (see §5's worked example — this is
exactly how the "COKE OVENS (...)" header bug got a permanent regression
test).

---

## 5. Worked example: a source format change breaking extraction

**The bug (RSP, June 2026):** every prior month correctly extracted RSP's
`COB-old` (3 params: `bf_coke_yield`, `coke_oven_gas_yield`,
`dry_coal_charge_oven`) and `COB-new` (4 params, plus
`ammonium_sulphate_yield` and `crude_tar_yield`). June 2026's upload was
missing `COB-old` entirely and had only 2 of `COB-new`'s 4 parameters.

**Diagnosis approach — always start here for a "some data missing" report:**

1. **Compare DB coverage across months** for the affected plant/unit, to
   confirm it's a *regression* (works in older months, breaks in the new
   one) rather than the source genuinely never having this data:

   ```python
   cur.execute("SELECT report_month, techno_json FROM techno_data "
               "WHERE plant='RSP' AND unit IN ('COB-old','COB-new') "
               "ORDER BY report_month")
   # print each month's set of non-null keys — look for the month where
   # the key set suddenly shrinks
   ```

2. **Re-run the extractor directly against the raw source file** for the
   broken month (bypassing the API/DB entirely) to confirm it's the
   extractor, not something in the upload/save path:

   ```python
   from techno_project.rsp_technopara_extractor import TechnoExtractor
   recs = TechnoExtractor(path, report_month="2026-06").extract()
   for r in recs:
       if r["unit"] in ("COB-old", "COB-new"):
           print(r["unit"], sorted(r["techno_json"]["month"].keys()))
   ```

3. **Dump the raw section headers/labels** around the affected area and
   diff them, mentally, against what the registry expects:

   ```python
   from rsp_row_scan import find_p18_sheet
   ws = wb[find_p18_sheet(wb.sheetnames)]
   for r in range(1, 70):
       label = ws.cell(r, 1).value or ws.cell(r, 2).value
       if label: print(r, repr(label))
   ```

**What the diff showed:** the section header at row 4 was
`"COKE OVENS (BATTERY -1-5)"`. The registry (`SECTION_UNITS` in
`rsp_technopara_sections.py`) had only `"BATTERY - (1-5)"` registered.
Section matching is **exact**, never substring
(`if label_norm in _SECTION_UNITS_NORM`) — so the new wrapped header simply
never matched anything, `current_unit` never got set walking through that
whole section, and *every* row under it — including rows whose own
`PARAM_ALIASES` entries were completely correct and unchanged — got silently
dropped. (`COB-new` still got 2 of 4 keys because its `COAL CHEMICALS`
sub-header, further down, happened to match unchanged and set `current_unit`
correctly for the rows under *that* header.)

**The fix — add an alias, don't change the matching strategy:**

```python
SECTION_UNITS = {
    "BATTERY - (1-5)":        "COB-old",
    "BATTERY - 6":            "COB-new",
    # New file editions wrap the same headers — register as-is rather than
    # switching to substring matching, which would risk false-positive
    # matches elsewhere in the sheet.
    "COKE OVENS (BATTERY -1-5)": "COB-old",
    "COKE OVENS (BATTERY - 6)":  "COB-new",
    "COAL CHEMICALS":         "COB-new",
    ...
}
```

This is the general pattern for *every* format-drift fix in this codebase:
**add the new exact text as an additional dictionary entry pointing to the
same target, rather than loosening the match to substring/fuzzy.** Fuzzy
matching on a sheet with dozens of similar-looking headers
(`"SINTER PLANT-I"` vs `"SINTER PLANT - II"` vs `"SINTER PLANT - III"`) is
how you get a *new*, harder-to-spot bug (matching the wrong section) instead
of fixing this one.

**Don't forget:**
- **Backfill** the already-saved DB row for the broken month, since the fix
  only affects *future* extractions (see §4 step 6).
- **Add a regression test** so the exact bug can't silently reappear — a
  targeted "if this unit is present, its key set must be complete" assertion
  is stronger than the existing coarse "at least N units, at least M
  non-null values" checks, which are usually too generous to catch a
  2-key-missing regression:

  ```python
  _COB_OLD_KEYS = {"bf_coke_yield", "coke_oven_gas_yield", "dry_coal_charge_oven"}
  if "COB-old" in by_unit:
      present = _COB_OLD_KEYS & by_unit["COB-old"].keys()
      assert present == _COB_OLD_KEYS, f"COB-old missing {_COB_OLD_KEYS - present}"
  ```

---

## 6. Conventions and recurring pitfalls

**Two extractors, two spellings.** The single most common bug this year:
final and monthend/tentative extractors for the same plant using different
`param_key` spellings for the same real figure (`blast_temperature` vs
`hot_blast_temp`, `hot_metal_consumption` vs `specific_hm_consumption`,
`coal_to_hot_metal` vs `coal_to_hm`, ...). Since `merge_upsert_techno_data`
merges by key, two different keys just coexist forever instead of one
overwriting the other. **When adding/editing an extractor, always grep the
plant's *other* extractor (final ↔ monthend) for how it spells the same
parameter** before picking a key name.

**Three alias tables, kept in sync by hand — not by any shared source of
truth:**
- `page_techno.py`'s `_KEY_ALIASES` (used by `generate_major_techno_from_db`,
  page 27/MAJOR)
- `page_techno.py`'s `_COKE_OVEN_PARAM_ALIASES` (used by
  `generate_techno_from_db`, page 28's schema)
- `main.py`'s `_PARAM_KEY_ALIASES` (used by `/api/techno-data`'s
  parameter-picker lookup, `_extract_param_value`)

These are genuinely separate dicts for separate call sites, but they should
agree on **which spelling is canonical** for a given parameter. A mismatch
between them was itself a real bug (`_COKE_OVEN_PARAM_ALIASES` once had
`dry_coal_charge`/`cog_yield` as primary keys while `_KEY_ALIASES` had the
opposite convention) — when adding an alias, check all three, and note in a
comment which one is authoritative if they must differ for a structural
reason (e.g. one function is only ever called with the long-form key).

**`_rename_keys`'s conflict rule** (in
`techno_project/migrate_key_rename.py`): when a DB migration renames a
legacy key and the canonical spelling *already exists* in that same period,
the canonical value wins — the legacy value is dropped, never used to
overwrite. Always dry-run (`python migrate_key_rename.py`, no `--apply`)
before committing to a rename, and check the printed conflict list.

**"General" and shop-level units aren't always what they look like.** BSL's
`SMS` unit (distinct from `SMS-I`/`SMS-II`) holds a real, separately-reported
shop-level figure for some parameters (LD Slag/Lime/Aluminium Consumption —
no per-converter equivalent, so it's the *only* source) but is genuinely
redundant for others (`specific_hm_consumption` — SMS-I/SMS-II each already
report their own). Don't assume a "combined shop" unit is either always
extra data or always redundant; check case by case.

**Testing.** Every plant has a `tests/test_<plant>_technopara_row_stability.py`
that runs the extractor against every real sample file in the repo
(`Report_format/Monthly/<PLANT>/...`) with an explicit `(filename,
report_month)` list — add new sample files there as they're deposited.
Golden fixtures (`tests/goldens/*.json` + `tests/test_extraction_goldens.py`)
pin exact output for specific extractor/file combinations; regenerate with
whatever `--update-goldens`-style flag that test file supports if a change
is intentional, never by hand-editing the JSON.

---

## 7. Quick file reference

| What you're changing | File(s) |
|---|---|
| RSP label→param mapping | `techno_project/rsp_technopara_sections.py` |
| RSP extraction logic | `techno_project/rsp_technopara_extractor.py`, `rsp_technopara_parser.py`, `rsp_row_scan.py` |
| BSP row-number map | `techno_project/bsp_techno_map.json`, `bsp_oisco_map.json` |
| BSP extraction logic | `techno_project/bsp_extractor.py`, `bsp_oisco_extractor.py` |
| DSP label→param mapping | `excel_extractors/pdf_extractor_dsp.py` (the `_..._PAGE_DEFS`/`_BF_FURNACE_PARAMS` tables) |
| DSP extraction logic | `techno_project/dsp_technopara_extractor.py` |
| ISP row-number map | `techno_project/isp_technopara_map.json` |
| BSL label→param mapping | `techno_project/bsl_technopara_extractor.py` (`_RAW_TO_PARAM_KEY`-style dicts) |
| Which unit/key shows on which report page | `page_techno.py`'s `_TECHNO_DB_SCHEMA` (pages 28-35), `TECHNO_PAGES` |
| Cross-plant legacy-spelling fallbacks | `page_techno.py`'s `_KEY_ALIASES`, `_COKE_OVEN_PARAM_ALIASES`; `main.py`'s `_PARAM_KEY_ALIASES` |
| YTD cumulative method per parameter | `techno_cumulative.py`'s `CUMULATIVE_RULES` |
| One-time DB key renames | `techno_project/migrate_key_rename.py` |
| Frontend table rendering | `frontend/src/components/TechnoParamsTemplate.js` (pages 27-30 "param" layout), `PageRenderer.js` (dispatch) |
