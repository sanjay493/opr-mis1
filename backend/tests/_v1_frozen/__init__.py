"""Frozen copy of the v1 repository modules (backend/repo/<m>.py as of
892b515, before the Task 7g switch-over), kept ONLY as a test oracle.

The app runs the v2 implementations (backend/repo/<m>.py). The dual-DB
equivalence tests (tests/test_repo_v2_*.py, via tests/v2dual.py) run the
same write / read through this v1 copy on a v1-schema test database
(the `mysql_v1_db` fixture, tests/fixtures/schema_v1.sql) and through
repo.<m> on a v2-schema test database, and compare. tools/repo_oracle.py
can replay its v1 recording against these modules (`--impl v1`).

Do not import this package from app code, and do not edit it: it is the
v1 behaviour the v2 code was proven against. The only change from the
originals is techno._log_techno_save binding this package's ops module.
"""
