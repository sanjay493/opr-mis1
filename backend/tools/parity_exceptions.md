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

## 1b. /api/iron-ore-mines/series: row order of the FY 2026-27 despatch_plan list (Task 7e1, needs a ruling)

- **What differs.** `GET /api/iron-ore-mines/series?fy_start=2026`: the `despatch_plan` list holds the same rows in another order. v1 returns them as (group, mine, month, material, end use); v2 returns (month, mine, material, end use), which is also v1's order for every other FY and for the other two lists.
- **Why.** v1's statement has no ORDER BY. For this FY (about 710 plan rows) MySQL drove the join from `mines_master`'s group_code index; for the sparser FYs it used a range scan on the fact table. That is a cost-model choice per call, which v2 cannot predict without fitting today's row counts. `repo.mines.get_iron_ore_mines_series` is compared as `deep_unordered(depth=2)` in tools/repo_oracle.py COMPARE_MODE.
- **User-visible effect: none.** The frontend (`reports/iron-ore-mines/View.js`) filters the rows by scope and sums them per month, and `mines_group_wise` keys them by (mine, material, end use). Every `qty_plan` in the v1 data is an integer, so every sum is exact in any order. Only the raw JSON list order differs, so 7g parity shows this one endpoint diff.

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

### 2c. Narrative text keys v2 cannot hold (Task 7d)

repo.v2.text checks every write against the v1 column limits and raises v1's own error (DataError 1406 / 1264, IntegrityError 1048 / 1062 with v1's column and key names), so over-long input fails alike on both sides. Two inputs fit a v1 column but not report_text; `OutOfModelError` (a ValueError) is raised before anything is written:

| input | v1 | v2 | reachable? |
|---|---|---|---|
| a board_note plant of 9..16 characters | stored (plant VARCHAR(16)) | OutOfModelError (plant_code VARCHAR(8), FK to the plant master) | **Only through a hand-crafted request:** the `plant` of POST `/api/board-note/manual-text` entries is a free string. The UI sends the fixed board-note plant list; the longest plant in the v1 data has 4 characters. |
| a board_note period longer than 10 characters (`'<fy>:Q<n>'` with a 2+ digit or negative quarter) | stored (quarter TINYINT) | OutOfModelError (period VARCHAR(10)) | No: `_parse_board_note_period` allows quarters 1-4 only. |

**Trailing spaces: now reproduced (Task 7e1).** MySQL stores a CHAR / VARCHAR value whose excess over the column length is only trailing spaces by cutting them (no error even in strict mode), e.g. v1 stored `'2025-04'` for a month `'2025-04 '`, and its `ON DUPLICATE KEY` matched the stored `'2025-04'` row, while its plain `WHERE report_month = '2025-04 '` matched nothing (the collations are NO PAD). 7d's v2 raised DataError 1406 instead. Since 7e1 every v2 writer that takes a month or an FY applies the same cut (`repo/v2/_keys.fit_char` / `fit_month` / `fit_fy`): it writes the cut value, and looks up with it only where the lookup stands in for v1's duplicate-key check; lookups v1 ran as their own SELECT or DELETE keep the raw value. The dual tests cover `'2025-04 '` and `'2025-26 '` in every v2 domain. This is reachable only through requests that do not validate the shape of the value:
- POST `/api/page3-narrative` (`month` is a free string);
- POST `/api/sail-1page/confirm` (`report_month` is only checked for presence);
- POST `/api/special-steel-physical/grid` (`financial_year` is only checked for presence);
- api_key_highlights' `_validate_month`, which splits on `-` and accepts `'2025-04 '` because `int('04 ')` is 4.

Other routes pass months from the month picker and fixed block keys and plant lists, or validate the shape.

### 2d. Keys of stock / ipt / special_steel / mines / rake / cost_trend v2 cannot hold (Task 7e1)

The 7e1 modules check every write against v1's column limits and raise v1's own errors (1048 / 1406 with v1's column names, 1452 with v1's constraint text), so over-long input fails alike. These inputs fit a v1 column but not the v2 model; `OutOfModelError` (a ValueError) is raised before anything is written:

| input | v1 | v2 | reachable? |
|---|---|---|---|
| a plant of 9..32 characters (stock_table, ipt_table from/to, special_steel_orders, special_steel_abp_table, special_steel_grade_clubs: VARCHAR(32)) or 9..16 (cost_trend_*: VARCHAR(16)) | stored | OutOfModelError (plant_code VARCHAR(8), FK to the plant master) | **Only through hand-crafted requests:** the plant of POST `/api/stock-entry` entries, `/api/special-steel-manual/save`, `/api/special-steel-abp` and the cost-trend saves is a free string. The UI and extractors send fixed plant lists (the longest plant in the v1 data has 4 characters). IPT routes go through `_check_ipt_plants`. |
| a short non-month (`'2025-4'`) for stock, sail sales, ipt, cost_trend monthly, sail_mines, mines, rake monthly / summary, special_steel orders / abp | stored as text | OutOfModelError (cal_month FK) | As §2a: only routes that do not validate the month shape. An empty batch never checks the month, as in v1. |
| a sail_stock_snapshot date that is not a canonical `'YYYY-MM-DD'` (`'2021-1-4'`) | stored (CHAR(10)) | OutOfModelError (DATE) | **Only through a hand-crafted request** to `/api/sail-1page/confirm`: the stock rows' `snapshot_date` comes from the extractor, which writes ISO dates. A read with such a string returns None, as v1's did (no stored v1 value is spelled that way). |
| a grade-club `created_at` that is not a `datetime.now().isoformat()` string | stored (VARCHAR(40)) | OutOfModelError (DATETIME(6)) | No: the only caller (api_special_steel_clubs) passes `datetime.now().isoformat()`. |

### 2e. Keys of breakdown / capital_repair / misc / pages / ops v2 cannot hold (Task 7e2 / 7f)

These modules also raise v1's own column errors (1048 / 1406 with v1's column names, v1's 1062 key names for users.email and uq_bf_benchmark_ext). These inputs fit a v1 column but not the v2 model; `OutOfModelError` (a ValueError) or an FK error is raised before anything is written:

| input | v1 | v2 | reachable? |
|---|---|---|---|
| capital_repair `actual_start` / `actual_end` that is not a canonical `'YYYY-MM-DD'` (`'2026-6-1'`, `''`, free text) | stored (CHAR(10)) | OutOfModelError (DATE) | **Needs a ruling.** POST `/api/capital-repair-entry` maps empty to NULL but does not validate the shape; the form uses date inputs. |
| capital_repair `fy` of 8 characters (`'2026-27 '`) | stored (VARCHAR(8)) | OutOfModelError (CHAR(7)) | No: `/api/capital-repair-row` requires `\d{4}-\d{2}`. |
| major_unit_daily_record `record_date` that is not a canonical date (`'1 Oct'`, `'2026-4-1'`, `''`) | stored (VARCHAR(10)) | OutOfModelError (DATE) | **Needs a ruling.** The data-entry form (`entry/major-unit-daily/Form.js`) is a free-text input with the placeholder YYYY-MM-DD (blank becomes NULL). |
| todo `due_date` / worklog `work_date` matching `\d{4}-\d{2}-\d{2}` but not a real date (`'2026-02-30'`) | stored | OutOfModelError (DATE) | Hand-crafted only. |
| a plant of 9..32 characters (pdf_item_alias, power, bf_benchmark_sail_meta) | stored | OutOfModelError (plant_code VARCHAR(8)) | Hand-crafted only (as §2d). |
| a short non-month for power / market / macro / page_config / cover setting | stored as text | OutOfModelError (cal_month FK) | As §2a. |
| page_config `page_data` holding NaN / Infinity | stored (json.dumps text) | OutOfModelError (JSON_VALID check) | Hand-crafted only: JSON bodies from the UI never hold them. |
| a timestamp string passed to bf_benchmark / cover_photo / steel_sector / users / otp / todo / worklog writers that is not in its column's v1 form | stored (VARCHAR) | OutOfModelError | No: every caller passes `datetime.now(...).isoformat()` / `strftime` in the column's form. |
| report_cover_setting.photo_id of a photo that does not exist; bf_benchmark_external_data for a BF that does not exist | stored (no FK in v1) | FK error 1452 | No: cover_store / api_bf_benchmark check existence first. |
| pdf_item_alias `convert_t` outside TINYINT (-128..127) | stored (INT) | DataError 1264 | No: callers pass 0 / 1. |
| `work_date` / `from` / `to` filters of `/api/worklog/list` that are not real dates | string compare | MySQL date error | Hand-crafted only. |

### 1c. Row order the optimizer picked per call (Task 7e2)

`breakdown.open_breakdown_rows` is a COMPARE_MODE multiset: v1's order depends on a per-call cost choice (2 of 32 recorded calls used the `start_ts` index, the rest the `capital_repair_id IS NULL` scan); v2 returns id order. The only caller groups the events by (plant, unit_type, unit_name) and sorts the result, so it can only change which of two equal-hour events of one unit supplies the cause text.

`ops` text ordering: v1 sorted its UTC ISO strings under ai_ci, where a value with a fraction sorts before the whole-second value of the same second; v2 reproduces that key, so the order is unchanged.
