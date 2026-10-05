### Task 5: `board_note_q2.py` adapter (Q-2 + H-1)

**Files:**
- Create: `backend/board_note_templates/board_note_q2_template.docx` (copy of `Report_format/BN_ Production Q-2 and H-1'25-26 R-2.docx`)
- Create: `backend/board_note_q2.py`
- Test: `backend/tests/test_board_note_q2.py` (requires the live MySQL dev DB — see Step 5)

**Interfaces:**
- Consumes: `board_note_common.*` (Task 4), `board_note_docx_utils.*` (Task 2), `board_note_manual_text.additional_highlight_lines`/`why_narrative_lines` (Task 3), `page_techno._get_plant_techno_plan_targets`, `page_techno.compute_sail_targets`, `techno_period.build_period_report`, `page_do_letter._fetch_conversion`.
- Produces: `generate(fy: str) -> bytes` — the only symbol Task 9's dispatcher imports.

This is the already-validated quarter shape: rebuild `_update_bn_board_report.py`'s logic as `generate(fy)`, replacing every hardcoded `2026-27`/`Q2_CUR`/`H1_CUR` with `board_note_common` calls parameterized by `fy_start = int(fy[:4])`, and replacing the per-plant "Highlights"/"why" paragraph blocks (which the one-off script left as the *old* document's literal 25-26 example text — fine for editing one real document in place, wrong for a from-scratch generator) with: auto-generated core-4 bullets (now via `board_note_common.best_ever_bullets(cur, plant, ...)` for **every** plant, not just SAIL) + `additional_highlight_lines` appended, via `fill_variable_bullets`; and the "why" block replaced entirely by `why_narrative_lines(manual, plant, "[Add production narrative for <plant> here]")` via `fill_variable_bullets`.

- [ ] **Step 1: Copy the template.** `cp "Report_format/BN_ Production Q-2 and H-1'25-26 R-2.docx" backend/board_note_templates/board_note_q2_template.docx` (create the `board_note_templates/` directory first).
- [ ] **Step 2: Re-derive and record the per-plant "Highlights"/"why" paragraph index ranges** for every one of the 9 units (SAIL + 8 plants), for both the Q-2 and H-1 sub-sections, using the same `document.element.body.iterchildren()` dump technique already used (and shown working) when this template was analyzed for the one-off script. Record each range as a constant block at the top of `board_note_q2.py`, e.g. `HIGHLIGHTS_BULLETS_START = {("SAIL", "q2"): 29, ...}` paired with a matching `..._END` or explicit slot-count — whatever shape `fill_variable_bullets` needs (a list of existing slot paragraphs to pass in). Comment each constant with the literal heading text it sits under, so a future reader can re-verify by eye.
- [ ] **Step 3: Implement `generate(fy: str) -> bytes` in `backend/board_note_q2.py`**, porting `_update_bn_board_report.py`'s `main()` body almost line-for-line: same table-filling order (table0 MoU, table1/2 SAIL, tables3-18 plants, table19 techno), same paragraph order (P9/P11 MoU narrative, P35/37/38 SAIL H-1, per-plant heading+summary pairs, techno section) — but every month list now comes from `board_note_common.quarter_months(fy_start, 2)` / `long_period_months(fy_start, 2)`; the techno target lookup now calls `board_note_common.fuel_rate_fallback(tgt)` per plant instead of the one-off script's inline fallback block, and the 4 SAIL improvement sentences now call `board_note_common.improvement_pct(cur_v, cply_v, higher_is_better)` instead of the one-off script's local `improvement_pct` closure; every best-ever call goes through `board_note_common.best_ever_bullets` for **all 9 units** (not just SAIL), and immediately after each unit's auto bullets are placed, call `fill_variable_bullets` again on that unit's recorded "why"-block slots with `why_narrative_lines(manual, plant, placeholder)`, and on its highlights slots with the auto bullets plus `additional_highlight_lines(manual, plant)` appended. Load `manual = board_note_manual_text.get_manual_text(fy, 2)` once at the top.
- [ ] **Step 4: Delete `backend/_update_bn_board_report.py`** now that its logic lives in the permanent modules (keep it out of the final diff — `git rm`).
- [ ] **Step 5: Verify against the live dev DB** (same validation already done manually for Q-2'26-27):

Run:
```bash
cd backend && venv/Scripts/python.exe -c "
import board_note_q2
open('_out.docx', 'wb').write(board_note_q2.generate('2026-27'))
"
venv/Scripts/python.exe -c "
import docx
d = docx.Document('_out.docx')
print(d.tables[1].rows[2].cells[3].text)   # SAIL Hot Metal Q-2 actual
print(d.paragraphs[9].text)                 # Finished-Steel-vs-MoU narrative
"
```
Expected: `d.tables[1].rows[2].cells[3].text == "5152"` and the paragraph 9 text contains `"4.360 MT"` and `"98%"` — the exact figures already hand-validated for Q-2'26-27 earlier in this project. Delete `_out.docx` afterward (it's a scratch artifact, not a test fixture).

- [ ] **Step 6: Commit**

```bash
git add backend/board_note_templates/board_note_q2_template.docx backend/board_note_q2.py
git rm backend/_update_bn_board_report.py
git commit -m "Add Q-2+H-1 Board Note adapter, retiring the one-off script it generalizes"
```

---

