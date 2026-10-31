-- migrate_rmt_plan_drop_coal_req.sql -- 2026-10-31
-- The RMT report's coal requirement is now calculated from the FY dry coal
-- charge target and the pushing plan (rmt_plan.coal_basis), so the entered
-- columns go. schema_v2.sql no longer has them. No report reads them after
-- this change, so no data_version bump. Run once on each machine's
-- mis_reports_v2, after migrate_add_rmt_plan.sql; a database built from
-- schema_v2.sql after this change never had the columns: skip it there.
ALTER TABLE rmt_plan_note DROP COLUMN coal_req_app, DROP COLUMN coal_req_op;
