# Task 2: `board_note_docx_utils.py` — Completion Report

## Status
DONE

## Changes Made

### 1. `backend/board_note_docx_utils.py` (new)
Standalone python-docx mutation helper module, depends only on `docx`:

- `set_para(paragraph, text)` — ported verbatim from `page_do_letter.py:_set_paragraph_text` (lines 348-358). Overwrites `runs[0].text` and clears the rest, preserving first-run formatting; falls back to `add_run` if the paragraph has no runs.
- `remove_paragraph(paragraph)` — ported verbatim from `_remove_paragraph` (lines 361-363). Detaches the `<w:p>` element from its parent.
- `clone_paragraph_after(ref_paragraph, text)` — ported verbatim from `_clone_paragraph_after` (lines 366-377). Deep-copies the reference paragraph's XML, inserts it immediately after via `addnext`, wraps it in a new `Paragraph`, and sets its text via `set_para`. Returns the new `Paragraph`.
- `set_cell(cell, text)` — ported verbatim from `_set_cell_text` (lines 388-398). Sets `paragraphs[0]` via `set_para`, removes every subsequent paragraph via `remove_paragraph`.
- `replace_in_para(paragraph, replacements)` — new (not in `page_do_letter.py`). Reads `paragraph.text`, applies each `(old, new)` substring swap in order, then rewrites via `set_para` (so first-run formatting is kept). This handles the brief's test case; note it works on the paragraph's full joined text rather than per-run, so it's correct even if a substring happens to span multiple runs — but formatting beyond the first run is not preserved per-run (same limitation `set_para` has elsewhere in the codebase).
- `fill_variable_bullets(slots, lines)` — new. Zips `slots` with `lines` via `set_para` for the overlapping prefix; if `lines` is longer, clones extra paragraphs off the last slot (or last clone) in order; if `slots` is longer, removes every unmatched trailing slot via `remove_paragraph`.

### 2. `backend/tests/test_board_note_docx_utils.py` (new)
The 7 tests from the brief, copied verbatim (no changes needed).

## Verification (strict TDD)
1. Wrote the tests first, confirmed failure: temporarily moved the module out of `backend/` and ran
   `C:\opr-mis1\backend\venv\Scripts\python.exe -m pytest tests/test_board_note_docx_utils.py -v`
   from the worktree's `backend/` directory → `ModuleNotFoundError: No module named 'board_note_docx_utils'` (1 error during collection), as expected.
2. Restored the module, implemented as above, re-ran the same command → **7 passed**.

Note on interpreter path: this worktree (`C:\opr-mis1\.worktrees\board-note-generator`) has no `backend/venv` of its own (venv isn't checked into git and worktrees don't get untracked files). Used the main checkout's interpreter directly (`C:\opr-mis1\backend\venv\Scripts\python.exe`) invoked with cwd set to the worktree's `backend/` directory — this is the same interpreter the brief/CLAUDE.md specifies, just referenced by its absolute path since the worktree doesn't have its own copy.

## Commit
- **Hash:** `067db9c`
- **Message:** "Add shared docx mutation helpers for Board Note adapters"
- **Files:** `backend/board_note_docx_utils.py`, `backend/tests/test_board_note_docx_utils.py`

## Concerns
- `backend/_update_bn_board_report.py` is an untracked scratch file that was already present in the worktree before this task started (visible in `git status` throughout) — not part of my scope (CLAUDE.md: files named `_*` are ad-hoc scratch scripts), so I left it untouched and did not stage it.
- `replace_in_para`'s implementation is not specified step-by-step in the brief (only its signature and one test case are given); I implemented it as a whole-paragraph-text substring swap followed by `set_para`, which satisfies the given test and is robust to a match spanning multiple runs, at the cost of not preserving per-run formatting beyond the first run (consistent with the rest of this module's helpers).
