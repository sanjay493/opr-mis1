"""v2 repository implementations (Task 7, ruling R12).

Each module here has the same public names, signatures, return shapes and
exceptions as the v1 module of the same name in backend/repo/, and reads /
writes the v2 schema (scripts/v2/schema_v2.sql). The app does not import
this package yet: tools/repo_oracle.py replays the v1 reads against it and
tests/test_repo_v2_*.py prove the writes; Task 7g swaps the modules in.
"""
