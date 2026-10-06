# SDD ledger — plan: docs/superpowers/plans/2026-10-05-board-note-generator.md

Spec: docs/superpowers/specs/2026-10-05-board-note-generator-design.md

## Pre-flight scan

| Check | Finding |
|---|---|
| Task 1 (db.py, mysql_schema.sql) vs any other task's files | No overlap — only Task 1 touches these files. Clean. |
| Task 2 (board_note_docx_utils.py) vs Task 3/4 | No file overlap. Task 3's Produces list claims `fill_variable_bullets` as a dependency but Task 3's own functions (`get_manual_text`/`save_manual_text`/`additional_highlight_lines`/`why_narrative_lines`) never call it — the merge happens in Tasks 5-8, not Task 3. **Ruling below.** |
| Task 3 (board_note_manual_text.py) internal consistency | Interfaces block overstates: lists `board_note_docx_utils.fill_variable_bullets` under "Consumes" but no step in Task 3 calls it. **Ruling below.** |
| Task 4 (board_note_common.py) internal consistency | Interfaces block lists `page_techno._get_plant_techno_plan_targets`/`compute_sail_targets` under "Consumes", but Task 4's own Produces list only has `fuel_rate_fallback(tgt: dict) -> dict` — a pure dict transform that takes an already-fetched dict. The actual `page_techno.*` calls happen in Task 5-8's adapters (confirmed by Task 5 Step 3: "the techno target lookup now calls `board_note_common.fuel_rate_fallback(tgt)` per plant"). Task 4 does not need to import `page_techno` at all. **Ruling below.** |
| Task 4 produces vs Task 5-8 consumes | `quarter_months`/`long_period_months`/`fy_months`/`quarter_label`/`long_period_label`/`pick_best`/`fmt_*`/`imp_phrase`/`fuel_rate_fallback`/`improvement_pct`/`ITEMS_FOR_PLANT`/`period_sum`/`conv_sum`/`row_values`/`best_ever`/`best_ever_bullets` — every name Task 5's Step 3 narrative uses matches a name Task 4 Produces. Clean. |
| Task 5 Step 4 ("git rm backend/_update_bn_board_report.py") vs worktree state | The file was copied into this worktree manually (as an untracked reference-only file — it was never committed anywhere in this branch's history, since it was a `??` untracked scratch file in the main checkout when this worktree was created). `git rm` will fail with "did not match any files". **Ruling below.** |
| Tasks 5/6/7/8 template files | Each creates a distinct path under `backend/board_note_templates/` (`board_note_q1..q4_template.docx`) and a distinct `board_note_qN.py` — no collision between them. |
| Task 9 (main.py) vs any other task | Only Task 9 touches `main.py`. Clean. |
| Task 10 (frontend) vs Task 9 | Consumes exactly the 3 routes Task 9 produces (`/api/board-note/docx`, `GET`/`POST /api/board-note/manual-text`). Clean. |
| Global Constraint "Finished Steel at SAIL level always adds Conversion; individual-plant never does" vs Task 4/5 | Task 4 Step 6 restates this exactly (`add_conv=True` only when `plant=="SAIL" and label=="Finished Steel"`); Task 5's `SAIL_ITEMS`/`BIG5_ITEMS`/etc. row-config tuples (ported from the validated one-off script) encode the same rule per-row. Clean. |
| Global Constraint "new manual-text periods start blank, never auto-copied" vs Task 3 | Task 3's own test list includes `test_new_period_never_sees_another_periods_text`, and no step in Task 3 implements any copy-forward. Clean. |

## Rulings

- Ruling: Task 3's implementer should disregard the "Consumes: board_note_docx_utils.fill_variable_bullets" line in its brief — `board_note_manual_text.py` has no actual dependency on `board_note_docx_utils`. That merge (calling `fill_variable_bullets` with the lines these functions return) happens in Tasks 5-8's adapters, which depend on both modules together. Cost if wrong: none — it's a documentation-accuracy correction with no code impact either way, since Task 3's own test list fully specifies its real behavior independent of this line.
- Ruling: Task 4's implementer should not import `page_techno` — `fuel_rate_fallback(tgt: dict) -> dict` operates on a plain dict the caller (the Task 5-8 adapters) already fetched via `page_techno`. Cost if wrong: none for Task 4 itself (its tests don't touch `page_techno`); if a future implementer mistakenly adds the import anyway it's dead weight, not a defect — will flag in task review if seen.
- Ruling: Task 5 Step 4 ("git rm backend/_update_bn_board_report.py") becomes a plain `rm backend/_update_bn_board_report.py` (not a git operation) — the file is untracked scratch, copied into this worktree only as a reference for porting its logic, never part of this branch's git history. Cost if wrong: none — either command removes the same file from the working tree; `git rm` would just error out first, costing one retry.

## Task log

Ruling: Task 5's manual `additional_highlights` text is keyed `(report_fy, quarter, plant, field)` per the spec's own schema — one value per plant for the whole Q-2+H-1 note, with no way to distinguish "for the Q-2 section" from "for the H-1 section." The implementer appended it to BOTH sections (duplicating it); reviewer flagged this. Ruling: append manual `additional_highlights` to the Q-2 highlights block ONLY (not H-1) — Q-2 is the note's primary period and this avoids duplication. This is a plan/spec gap surfacing at implementation, not a code defect to blindly fix either way; ledgered per SDD process. Cost if wrong: a plant's manually-entered extra highlight reads oddly placed under Q-2 when the record was really an H-1 one — low cost, user can word the text to be period-neutral.
Ruling: ASP/SSP/VISL have no "Highlights:" paragraph slot in the template at all (confirmed structural fact, not a parsing bug) — their manual `additional_highlights` field has no visible effect in the generated docx for this pass. Accepted limitation, not sent back for a fix: adding a new structural block to a fixed template conflicts with this codebase's established "mutate fixed templates, never restructure them" convention (same principle as the PDF layout guardrails). Cost if wrong: a user who fills in ASP/SSP/VISL's additional-highlights box sees no effect and may be confused — worth a frontend hint in Task 10, not a blocker here.

Task 5: fix round 1/5 (1 Critical + 8 Important open — P3/P18/19 static title/header; MoU table header/%Ful unfilled; annexure index stale; additional_highlights duplicated Q2+H1; bullet slots included non-bullet lead-ins (BSL Q2/H1, ISP Q2); lead-ins misstated "Quarter"/"half yearly" scope; dangling Highlights heading on zero records; SAIL MoU row fabricated 0; techno target kept stale text on missing value; commits 2da3381..415ab9a)
Task 5: fix round 1/5 (9 addressed, 0 open — plus an unprompted 4th instance of the lead-in-as-slot bug found and fixed at ISP H-1/P277; commits 415ab9a..0ba8408)
Task 5: minor (deferred): fix round introduced stray blank paragraphs inside ISP's Q-2/H-1 highlight bullet lists (P243, P276, P238) — whitespace only, no wrong text/figures.
Task 5: complete (commits 2da3381..0ba8408, review clean after 1 fix round)

Task 1: complete (commits 5ff9a7c..434868d, review clean)
Task 1: minor (deferred): comment spans 3 lines vs brief's "one line" in db.py:291-293 and mysql_schema.sql:176-178 — content fine, not a compliance issue.

Task 2: complete (commits 434868d..067db9c, review clean)
Task 2: minor (deferred): fill_variable_bullets(slots=[], lines=non-empty) would crash on clone_paragraph_after(None, ...) — unreachable in practice (board_note_docx_utils.py:98-100), noted for awareness.
Task 2: minor (deferred): ported helpers' docstrings copied verbatim from page_do_letter.py rather than referencing it — future doc changes there won't propagate here.

Task 3: complete (commits 067db9c..11c2e0e, review clean)
Task 3: minor (deferred): save_manual_text doesn't validate `field` against the exported FIELDS tuple — a typo'd field string would silently persist unrecognized.

Task 4: fix round 1/5 (0 addressed, 3 open — add_conv unguarded on row_values/best_ever; missing Conversion silently treated as 0.0 (violates never-guess); improvement_pct/imp_phrase crash on None; commits 11c2e0e..d5b0bc4)
Task 4: fix round 1/5 (3 addressed, 0 open; commits d5b0bc4..2da3381)
Task 4: complete (commits 11c2e0e..2da3381, review clean after 1 fix round)
Task 4: minor (deferred): period_sum duplicates page4._p4_ytd_sum's shape instead of calling it; conv_sum repeats the same found-flag loop.
Task 4: minor (deferred): best_ever_bullets' unknown style/plant falls through silently (wrong text or empty list) instead of raising.
Task 4: minor (deferred): bullet MT figures use round(v/1000,3) not fmt_mt, so trailing zeros aren't padded ("1.53" not "1.530").
Task 4: minor (deferred): best_ever scans FY 1960..cur for every item — correct but many small queries against MySQL; inherited from the validated reference script, not a regression.
Task 4: minor (deferred): trivial _fy_start_years wrapper; stray module-level loop variable _p.

Task 6: Ruling: Q-1 techno table carries Specific Energy Consumption in place of Fuel Rate — the template's four parameter rows are Coke, CDI, BF Productivity, Specific Energy; the adapter follows the template, not Q-2's param set — cost if wrong: a Fuel Rate row would need a template change, not a code change.
Task 6: Ruling: plan Step 3 expected four improvement sentences under the techno table — the Q-1 template has none (title paragraph goes straight to the table), so none are generated — cost if wrong: no commentary line under the Q-1 techno table, which matches the source document.
Task 6: Ruling: DSP and ISP have no "Highlights:" section in the Q-1 template (nor ASP/SSP/VISL, as in Q-2), so their best-ever bullets are computed but have no slot and are not written — cost: a DSP or ISP Q-1 record will not appear in the note; this is visible to the user and should be flagged.
Task 6: Ruling: BSL's static "SMS-1 new grade HSQ550" paragraph is a highlight slot and is overwritten, along with the rest of BSL's static bullets (same policy Q-2 applies) — cost: that sentence must be re-entered in additional highlights if it should appear.
Task 6: Ruling: per-unit why narrative is replaced by manual text or the placeholder, as in Q-2 — cost: the source document's Q-1 narrative disappears from the output until entered in the manual-text box.
Task 6: Ruling: best_ever_bullets gained a 'q1' style via a shared branch that also serves 'q2' (same wording, Q-n) — cost: none for Q-2; covered by the full suite (232 passed).
Task 6: Ruling: board_note_q1 imports the table/summary helpers from board_note_q2 rather than copying ~150 lines — cost: a later change to those q2 helpers changes Q-1 output too; moving them to a shared module is deferred.
Task 6: Ruling: blank paragraph P139 inside BSL's highlights block is removed before filling, so generated bullets are contiguous — cost: none.
Task 6: Ruling: no MoU table or Finished-Steel-vs-MoU opening (plan Step 3 said skip; confirmed — table 0 is the SAIL ABP/Actual table, not a MoU table) — cost: none.
Task 6: minor (deferred): P0 meeting date "JULY, 2026" and the signatory block are left static, as in Q-2 — the date is not regenerated for other periods.
Task 6: live-DB check (FY 2026-27): SAIL HM Q-1 ABP 5504 / Actual 5051 / %Ful 92 / CPLY 5128 and BSP Coke Rate target 407 / Q-1 429 match the Q-1'26-27 source document; BSP HM best-ever bullet 1.579 MT (prev 1.53, Q-1'25-26) is a real record; SAIL HM has no record for Q-1 so no SAIL bullet; FY 2025-26 and empty FY 2040-41 generate without error.
Task 6: complete (commits f6348b2..039d1a9, tests: bash -c 'cd backend && /c/opr-mis1/backend/venv/Scripts/python.exe -m pytest tests -q' → 232 passed, 126 skipped in 61.70s (0:01:01))
