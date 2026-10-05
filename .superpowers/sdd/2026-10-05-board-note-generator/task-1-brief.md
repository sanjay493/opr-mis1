### Task 1: `board_note_manual_text` table

**Files:**
- Modify: `backend/db.py` (inside `init_db`, alongside the existing `do_letter_remark_table` CREATE TABLE at `db.py:282-289`)
- Modify: `backend/scripts/mysql_schema.sql` (alongside `do_letter_remark_table` at line 172-178)

**Interfaces:**
- Produces: a `board_note_manual_text` table with columns `report_fy CHAR(7)/TEXT`, `quarter TINYINT/INTEGER`, `plant VARCHAR(16)/TEXT`, `field VARCHAR(24)/TEXT`, `text TEXT`, `PRIMARY KEY (report_fy, quarter, plant, field)` — exact shape from spec §3.3.

- [ ] **Step 1: Add the SQLite `CREATE TABLE IF NOT EXISTS board_note_manual_text` statement to `init_db` in `backend/db.py`**, right after the `do_letter_remark_table` block, with a short comment (one line) saying it backs the Board Note generator's per-plant "Additional highlights"/"Why narrative" fields and that new periods start blank by convention (not migrated/copied by any code path).
- [ ] **Step 2: Add the matching `CREATE TABLE IF NOT EXISTS board_note_manual_text ... ENGINE=InnoDB;` to `backend/scripts/mysql_schema.sql`**, right after `do_letter_remark_table`, with `report_fy CHAR(7) NOT NULL`, `quarter TINYINT NOT NULL`, `plant VARCHAR(16) NOT NULL`, `field VARCHAR(24) NOT NULL`, `text TEXT`.
- [ ] **Step 3: Verify**

Run: `cd backend && venv/Scripts/python.exe -c "import db; db.init_db(); print('ok')"`
Expected: prints `ok` with no exception (confirms the new `CREATE TABLE` is valid SQLite syntax against the live dev DB path).

- [ ] **Step 4: Commit**

```bash
git add backend/db.py backend/scripts/mysql_schema.sql
git commit -m "Add board_note_manual_text table for Board Note editable narrative"
```

---

