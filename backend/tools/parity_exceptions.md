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
