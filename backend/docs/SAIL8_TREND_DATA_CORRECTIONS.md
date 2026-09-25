# Annexure-4 (SAIL 8 Plants Production Trend) — data corrections

**Source of truth right now:** `page_sail8_trend_annexure.py`'s `_REFERENCE_VALUES`
dict — verified figures for every closed FY (2007-08 through 2025-26), transcribed
from SAIL's own published PRODUCTION summary sheets (two screenshots supplied
2026-09-25: FY2016-17→2025-26 and FY2007-08→2016-17). These are applied
**in preference to** a live sum from `production_table` for every year they
cover. Only the still-open current FY (not in the source table) is computed
live.

This doc exists so that whoever backfills/fixes `production_table`'s
underlying data later has a checklist. **Once a closed year's DB figures are
corrected to match `_REFERENCE_VALUES`, delete that year's entry from the
override dict** (same convention as `page_major_unit_records.py`'s
`_ANNUAL_RECORD_FLOOR`) — don't leave a hardcoded value shadowing a
now-correct DB figure.

## Why the live computation disagreed: root causes

Comparing `production_table`'s live-computed figures against the published
table turned up 61 discrepant cells out of 114 (19 years × 6 items). They
fall into four distinct causes:

1. **Pig Iron missing entirely before FY2012-13.** `production_table` has no
   `'Pig Iron'` rows at all before `2012-04` (any plant). FY2007-08 through
   FY2011-12 show blank in the live computation for this reason alone.

2. **Semi Finished Steel — missing before FY2012-13, and understated almost
   every year after that.** `'Saleable Semis'` (the item summed for this row)
   also has no data before `2012-06`. Worse: **RSP has no `'Saleable Semis'`
   item in `production_table` at all** (only `'Semis Despatch'`, a different
   quantity) — the SAIL-level sum (BSP+DSP+RSP+BSL+ISP's Saleable Semis, plus
   ASP's Saleable Steel − Finished Steel) permanently omits RSP's real
   contribution, which is why almost every post-2012-13 year is still short
   by a few hundred to ~2,000 '000 T (worst: FY2020-21, short by 1,832;
   FY2018-19, short by 1,573). **Fix requires backfilling RSP's semi-finished
   production into `production_table` under a `'Saleable Semis'` item** (or
   an equivalent RSP-specific mapping added to the SAIL aggregate formula in
   `page5_6.py` / `page_sail8_trend_annexure.py`).

3. **Finished Steel missing before FY2015-16.** RSP and BSL never reported a
   `'Finished Steel'` item in `production_table` until FY2021-22
   (`report_month` ≥ `2021-04`) — before that, the SAIL-level figure can only
   come from the live sum when *all 8 plants* have a value, which never
   happens pre-2021, so the code falls back to the directly-stored `'SAIL'`
   plant row for `'Finished Steel'` — but that row itself only starts at
   `2015-04`. Net effect: FY2007-08 through FY2014-15 are blank. **Fix
   requires either backfilling RSP/BSL's historical Finished Steel figures,
   or backfilling the stored SAIL `'Finished Steel'` row further back.**

4. **Crude Steel, FY2010-11 / FY2011-12 — a likely period-boundary
   misassignment.** These two years are off by **+97** and **−96**
   respectively (almost exactly offsetting), unlike every other year's ±1-3
   rounding noise. This pattern suggests one plant's March or April figure
   landed under the wrong `report_month` (spilling from one FY into the
   adjacent one) rather than genuinely missing/wrong data. **Fix requires
   checking each of the 8 plants' `'Total Crude Steel'` entries for
   `2011-03` and `2011-04` against their source documents.**

5. **Scattered ±1 to ±8 '000 T differences** on Hot Metal / Crude Steel /
   Saleable Steel / Finished Steel across most other years — most plausibly
   later corrections made to individual plants' monthly figures in
   `production_table` *after* the published summary was compiled (this app's
   own data keeps getting corrected/backfilled; the published sheet is a
   point-in-time snapshot). Not investigated per-cell; low priority.

6. **FY2025-26 is internally inconsistent in the source table itself** — its
   own Semi Finished Steel (2,638) + Finished Steel (16,952) = 19,590, which
   does **not** equal its own Saleable Steel (19,177), a gap of 413. Every
   other year's two components sum exactly to that year's Saleable Steel.
   This looks like an error in the source screenshot / underlying report
   itself (FY2025-26 being the most recent, least-reconciled year), not a
   transcription mistake here — kept as published rather than silently
   "corrected" against a formula. Worth confirming against SAIL's own
   original document before trusting either figure fully.

## Full cell-by-cell discrepancy list

`production_table` (live sum, this app's pre-override computation, as of
2026-09-25 data / report_month 2026-08) vs. the published reference now
hardcoded in `_REFERENCE_VALUES`:

| FY | Item | production_table (live sum) | Reference (SAIL published) | Diff |
|---|---|---:|---:|---:|
| 07-08 | Crude Steel | 13,962 | 13,964 | -2 |
| 07-08 | Pig Iron | — | 441 | n/a (missing) |
| 07-08 | Semi Finished Steel | — | 2,243 | n/a (missing) |
| 07-08 | Finished Steel | — | 10,801 | n/a (missing) |
| 08-09 | Hot Metal | 14,443 | 14,442 | 1 |
| 08-09 | Pig Iron | — | 267 | n/a (missing) |
| 08-09 | Semi Finished Steel | — | 2,206 | n/a (missing) |
| 08-09 | Finished Steel | — | 10,288 | n/a (missing) |
| 09-10 | Crude Steel | 13,509 | 13,506 | 3 |
| 09-10 | Pig Iron | — | 323 | n/a (missing) |
| 09-10 | Saleable Steel | 12,631 | 12,632 | -1 |
| 09-10 | Semi Finished Steel | — | 2,392 | n/a (missing) |
| 09-10 | Finished Steel | — | 10,240 | n/a (missing) |
| 10-11 | Crude Steel | 13,858 | 13,761 | 97 |
| 10-11 | Pig Iron | — | 261 | n/a (missing) |
| 10-11 | Semi Finished Steel | — | 2,394 | n/a (missing) |
| 10-11 | Finished Steel | — | 10,493 | n/a (missing) |
| 11-12 | Crude Steel | 13,254 | 13,350 | -96 |
| 11-12 | Pig Iron | — | 106 | n/a (missing) |
| 11-12 | Semi Finished Steel | — | 2,527 | n/a (missing) |
| 11-12 | Finished Steel | — | 9,872 | n/a (missing) |
| 12-13 | Semi Finished Steel | 63 | 2,422 | -2,359 |
| 12-13 | Finished Steel | — | 9,962 | n/a (missing) |
| 13-14 | Semi Finished Steel | — | 2,760 | n/a (missing) |
| 13-14 | Finished Steel | — | 10,120 | n/a (missing) |
| 14-15 | Crude Steel | 13,907 | 13,908 | -1 |
| 14-15 | Pig Iron | 630 | 634 | -4 |
| 14-15 | Semi Finished Steel | — | 3,007 | n/a (missing) |
| 14-15 | Finished Steel | — | 9,835 | n/a (missing) |
| 15-16 | Crude Steel | 14,277 | 14,279 | -2 |
| 15-16 | Pig Iron | 677 | 642 | 35 |
| 15-16 | Semi Finished Steel | 1,011 | 3,054 | -2,043 |
| 15-16 | Finished Steel | 9,325 | 9,327 | -2 |
| 16-17 | Crude Steel | 14,497 | 14,496 | 1 |
| 16-17 | Semi Finished Steel | 2,753 | 3,170 | -417 |
| 16-17 | Finished Steel | 10,696 | 10,697 | -1 |
| 17-18 | Crude Steel | 15,021 | 15,020 | 1 |
| 17-18 | Saleable Steel | 14,073 | 14,074 | -1 |
| 17-18 | Semi Finished Steel | 2,342 | 2,610 | -268 |
| 17-18 | Finished Steel | 11,466 | 11,464 | 2 |
| 18-19 | Semi Finished Steel | 1,596 | 3,169 | -1,573 |
| 18-19 | Finished Steel | 11,892 | 11,900 | -8 |
| 19-20 | Saleable Steel | 15,082 | 15,147 | -65 |
| 19-20 | Semi Finished Steel | 1,813 | 2,995 | -1,182 |
| 19-20 | Finished Steel | 12,088 | 12,152 | -64 |
| 20-21 | Semi Finished Steel | 1,965 | 3,797 | -1,832 |
| 21-22 | Crude Steel | 17,365 | 17,366 | -1 |
| 21-22 | Semi Finished Steel | 2,952 | 3,171 | -219 |
| 21-22 | Finished Steel | 13,944 | 13,724 | 220 |
| 22-23 | Crude Steel | 18,290 | 18,291 | -1 |
| 22-23 | Semi Finished Steel | 2,363 | 2,277 | 86 |
| 22-23 | Finished Steel | 14,882 | 14,969 | -87 |
| 23-24 | Crude Steel | 19,239 | 19,240 | -1 |
| 23-24 | Saleable Steel | 18,436 | 18,437 | -1 |
| 23-24 | Semi Finished Steel | 2,689 | 2,686 | 3 |
| 23-24 | Finished Steel | 15,747 | 15,751 | -4 |
| 24-25 | Crude Steel | 19,175 | 19,174 | 1 |
| 24-25 | Saleable Steel | 17,942 | 17,940 | 2 |
| 24-25 | Finished Steel | 15,408 | 15,406 | 2 |
| 25-26 | Semi Finished Steel | 2,639 | 2,638 | 1 |
| 25-26 | Finished Steel | 16,538 | 16,952 | -414 |

Rows not listed (Hot Metal for most years, Saleable Steel for most years,
etc.) already matched exactly, or matched to within rounding noise, and are
not shown.

## Suggested fix order (highest impact first)

1. Backfill RSP's semi-finished production under a `'Saleable Semis'` item in
   `production_table` (root cause #2 — affects nearly every year from
   FY2012-13 onward, the single largest source of discrepancy).
2. Backfill RSP/BSL's `'Finished Steel'` figures pre-FY2021-22, or extend the
   stored SAIL `'Finished Steel'` snapshot back before FY2015-16 (root cause
   #3).
3. Backfill `'Pig Iron'` and `'Saleable Semis'` for FY2007-08 through
   FY2011-12 (root cause #1 — five ISPs only, should be a bounded, well-
   defined backfill).
4. Check the FY2010-11 / FY2011-12 Crude Steel period-boundary issue (root
   cause #4).
5. Confirm FY2025-26 against SAIL's original document (root cause #6) before
   trusting either the hardcoded Semi Finished/Finished split or the
   Saleable Steel total for that year.
