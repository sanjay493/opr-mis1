# Accepted v1 → v2 parity exceptions

This file lists every accepted difference between the v1 and v2 data models' output. Each entry is a controller ruling.

Rules for Task 7g:
- The parity diff of the full parity run on mis_reports_v2_rehearsal must be exactly the effects listed here, and nothing else.
- The repo-level counterpart of each entry is `KNOWN_PARITY_EXCEPTIONS` in `tools/repo_oracle.py`. Replay reports those calls as `KNOWN EXCEPTION` and still fails on any other diff.

## 1. /records single-plant tabs: second-place month labels among equal totals

**Ruling.** Task 7b, ruling (a), 2026-10-22.

**The repo calls.** `repo.production.records_calendar_month_totals(cur, ("plant_name IN (%s)", [P]))` for P in BSP, DSP, RSP, BSL and ISP. These are the single-plant scopes that `page_records.generate_records` builds. The 5 calls differ in both the sql and the bulk replay passes.

**Cause.**
- v1 ran `GROUP BY item_name, report_month ORDER BY item_name, mon_num, total DESC` through filesort.
- For one plant these are 2,700–8,800 groups. That is more than the default `sort_buffer_size` (256 KB), so MySQL sorted chunks and merged them.
- The order of groups with equal (item, month number, total) is an artefact of that buffer size.
- v2 orders ties as a sort that fits one buffer would (`repo/v2/_mysqlsort.py`). That is exactly v1's order for every other scope, and v1's own order for these 5 when MySQL runs with `sort_buffer_size = 64M`.
- Rows, totals and the key sequence are identical; only tied rows swap.

**Where it shows.**
- `/api/production-records`: `generate_records()`, key `<plant>.cal_months[<item>][<month number>]`, the best and 2nd-best per calendar month.
- That feeds the plant tabs BSP, DSP, RSP and BSL of the /records page. ISP is unaffected.
- `page_records` keeps the first two non-NULL rows per (item, month number), so when two or more months tie on the total, a different month can be named.
- 33 entries change in total. In every case the totals shown are the same, and only the month label (and its `month`) changes.
- Nothing else in the response changes: `top5_months` re-sorts by (total, month), and the quarter / half / FY / CY records come from `records_rows`, which matches v1 exactly.

| plant tab | item | month | v1 shows (label, total) | v2 shows (label, total) |
|---|---|---|---|---|
| BSP | SP-1 | Jun | Jun'08 (58.966), Jun'12 (0.0) | Jun'08 (58.966), Jun'10 (0.0) |
| DSP | Finished Export | Apr | Apr'21 (0.0), Apr'19 (0.0) | Apr'26 (0.0), Apr'24 (0.0) |
| DSP | Finished Export | Jun | Jun'25 (0.0), Jun'26 (0.0) | Jun'22 (0.0), Jun'24 (0.0) |
| DSP | Finished Export | Jul | Jul'22 (0.08), Jul'26 (0.0) | Jul'22 (0.08), Jul'16 (0.0) |
| DSP | Oven Pushing (nos/day) | Sep | Sep'23 (345.0), Sep'17 (340.0) | Sep'23 (345.0), Sep'16 (340.0) |
| RSP | SMS-1 Ingot | Mar | Mar'22 (0.0), Mar'25 (0.0) | Mar'24 (0.0), Mar'21 (0.0) |
| RSP | SMS-1 Ingot | Jun | Jun'24 (0.07), Jun'23 (0.069) | Jun'24 (0.07), Jun'21 (0.069) |
| RSP | SMS-1 Ingot | Sep | Sep'25 (0.072), Sep'24 (0.072) | Sep'24 (0.072), Sep'25 (0.072) |
| RSP | SMS-1 Ingot | Oct | Oct'24 (0.072), Oct'22 (0.072) | Oct'24 (0.072), Oct'25 (0.072) |
| RSP | SMS-1 Ingot | Nov | Nov'24 (0.072), Nov'21 (0.072) | Nov'25 (0.072), Nov'24 (0.072) |
| BSL | New CR Sheet | Jan | Jan'26 (0.0), Jan'25 (0.0) | Jan'25 (0.0), Jan'21 (0.0) |
| BSL | New CR Sheet | Feb | Feb'24 (0.0), Feb'22 (0.0) | Feb'20 (0.0), Feb'25 (0.0) |
| BSL | New CR Sheet | Mar | Mar'25 (0.0), Mar'21 (0.0) | Mar'26 (0.0), Mar'21 (0.0) |
| BSL | New CR Sheet | May | May'19 (0.0), May'23 (0.0) | May'20 (0.0), May'21 (0.0) |
| BSL | New CR Sheet | Jun | Jun'19 (0.0), Jun'22 (0.0) | Jun'21 (0.0), Jun'24 (0.0) |
| BSL | New CR Sheet | Jul | Jul'23 (0.0), Jul'24 (0.0) | Jul'22 (0.0), Jul'24 (0.0) |
| BSL | New CR Sheet | Aug | Aug'19 (0.0), Aug'22 (0.0) | Aug'22 (0.0), Aug'23 (0.0) |
| BSL | New CR Sheet | Sep | Sep'24 (0.0), Sep'22 (0.0) | Sep'22 (0.0), Sep'23 (0.0) |
| BSL | New CR Sheet | Oct | Oct'20 (0.0), Oct'21 (0.0) | Oct'21 (0.0), Oct'23 (0.0) |
| BSL | New CR Sheet | Nov | Nov'22 (0.0), Nov'21 (0.0) | Nov'21 (0.0), Nov'25 (0.0) |
| BSL | New CR Sheet | Dec | Dec'21 (0.0), Dec'20 (0.0) | Dec'21 (0.0), Dec'24 (0.0) |
| BSL | SMS-1 Ingot | Sep | Sep'20 (45.012), Sep'26 (0.23) | Sep'20 (45.012), Sep'23 (0.23) |
| BSL | Semis Export | Jan | Jan'26 (0.0), Jan'25 (0.0) | Jan'23 (0.0), Jan'26 (0.0) |
| BSL | Semis Export | Feb | Feb'24 (0.0), Feb'23 (0.0) | Feb'26 (0.0), Feb'23 (0.0) |
| BSL | Semis Export | Mar | Mar'23 (0.0), Mar'24 (0.0) | Mar'25 (0.0), Mar'26 (0.0) |
| BSL | Semis Export | Apr | Apr'25 (14.29), Apr'23 (0.0) | Apr'25 (14.29), Apr'24 (0.0) |
| BSL | Semis Export | Jun | Jun'25 (14.446), Jun'24 (0.0) | Jun'25 (14.446), Jun'22 (0.0) |
| BSL | Semis Export | Jul | Jul'23 (0.0), Jul'25 (0.0) | Jul'22 (0.0), Jul'23 (0.0) |
| BSL | Semis Export | Aug | Aug'23 (0.0), Aug'26 (0.0) | Aug'22 (0.0), Aug'25 (0.0) |
| BSL | Semis Export | Sep | Sep'25 (16.254), Sep'23 (0.0) | Sep'25 (16.254), Sep'22 (0.0) |
| BSL | Semis Export | Oct | Oct'23 (0.0), Oct'22 (0.0) | Oct'22 (0.0), Oct'24 (0.0) |
| BSL | Semis Export | Nov | Nov'25 (0.0), Nov'24 (0.0) | Nov'22 (0.0), Nov'23 (0.0) |
| BSL | Semis Export | Dec | Dec'25 (0.0), Dec'24 (0.0) | Dec'22 (0.0), Dec'24 (0.0) |

**How the table was made.** Measured 2026-10-22 on mis_reports_rehearsal (the v1 oracle) against mis_reports_v2_rehearsal. The items are page_records' items for each plant tab: `distinct_items(actual, plant)` minus `LEGACY_ITEM_NAMES`. The data is the data as of the parity `--today 2026-10-19`.

**Upkeep.** If the data or `--today` changes, regenerate this table before 7g compares parity.

## 2. Invalid-input deviations (writes)

These are writes that v1 stored and v2 refuses, because the v2 model cannot hold the value. None of them is produced by the app's UI, extractors or scripts, and none occurs in the v1 data. They are listed so that a refusal is recognised as known, not taken for a regression. The parity snapshot has no write calls, so none of them shows up in 7g's parity diff.

### 2a. Report months that are not 'YYYY-MM' (Task 7b)

- **The input.** A month string of at most 7 characters that is not a real month, such as `'2025-4'`, `'2025-13'`, `'abc'` or `''`.
- **v1** stored it as text in its CHAR(7) column.
- **v2** cannot: cal_month needs a real month_start and FY. `repo/v2/_keys.check_month` raises `OutOfModelError` (a ValueError) before the bump, so nothing is written.
- **Reachable** through the unvalidated production endpoints (`/api/production-entry`, `/api/production-item-range`, `/api/conversion-entry`, `/api/confirm-plan`), and through api_capacity, whose `_validate_month` accepts `'2026-4'`. Each gives a 500 where v1 returned 200.
- Longer strings fail on both sides with the same DataError 1406.

### 2b. Techno blob shapes v2's codec refuses (Task 7c, fix round 2)

`repo.v2codec.encode_techno` refuses, with `CodecError` (a ValueError), three blob shapes that v1 stored verbatim as JSON. In the write chain the error is raised before the write; a merge rolls its transaction back. Audit, 2026-10-23, of every builder of a blob passed to upsert_techno_data, merge_upsert(_techno_data), save_techno_json, save_techno_data_from_extraction, save_sail_techno_actuals and _raw_upsert_techno_data:

- **Callers covered:**
  - the api_*_techno routers, through their extractors in techno_project/ and excel_extractors/pdf_extractor_bsp_flash;
  - main.py's BSL BF PDF save and /api/techno-entries;
  - api_techno_manual's /save and SAIL BF;
  - page_techno.calculate_sail_actuals;
  - api_coal_*, api_mcr_techno and api_unified_techno;
  - the scripts/ backfills and techno_project/bulk_load_sail_csv.
- **What they build.** Every one builds `{"month": {...}, "till_month": {...}}` or a subset of it, with dict periods and str keys. bulk_load_sail_csv validates its period column, and a merge onto a stored row always rebuilds both periods as dicts.

| shape | v1 | v2 | reachable? |
|---|---|---|---|
| top-level keys other than `month` / `till_month` | stored | CodecError | No: no builder adds one |
| a period that is not an object (`"till_month": None`, a list, ...) | stored (as a merge base, a later merge raised AttributeError in v1 too) | CodecError | No: every builder makes dict periods; SaveRequest's month_data / till_month_data are typed `Dict[str, ...]` |
| a parameter key longer than 190 characters | stored | CodecError | **Only through a hand-crafted request:** the keys of SaveRequest.month_data / till_month_data (`/api/techno/manual/save`), and `key` / `parameter` of `/api/techno-entries` rows, are free strings. The UI sends its fixed PARAM_TEMPLATES keys, and the extractors map labels to fixed keys. The longest key in the v1 data has 37 characters. |
| a non-str key (`{1: 5}`), or a tuple leaf | stored (json.dumps makes them `"1"` / a list) | CodecError | No: pydantic and every builder give str keys and list / scalar values |

**Why the long key is not supported.** `techno_value.param_key` is VARCHAR(190) inside the primary key. Widening it is a schema change, and the InnoDB key limit (3072 bytes) would still cap a key at about 700 characters, while v1's JSON keys could reach 64 KB. Full support would need a different key design, for example a hashed key plus a text column. That is not cheap, so the case is reported here instead (7c report, fix round 2).
