-- seed_cal_month.sql -- fills cal_month (schema_v2.sql) with every month
-- from 1960-04 to 2040-03 (80 Indian financial years, 960 rows).
--
--   report_month  'YYYY-MM'
--   month_start   first day of the month
--   fy            'YYYY-YY', the Indian FY (April to March) the month falls in,
--                 e.g. 2026-08 and 2027-03 are both in '2026-27'
--   fy_month      1 = April ... 12 = March
--   quarter       FY quarter, 1 = Apr-Jun ... 4 = Jan-Mar
--   half          FY half, 1 = Apr-Sep, 2 = Oct-Mar
--
-- Run after schema_v2.sql. Re-runnable (INSERT IGNORE). The recursion is
-- 959 steps deep, under the MySQL default cte_max_recursion_depth (1000).
-- Checked by tests/test_schema_v2.py::test_cal_month_seed.

INSERT IGNORE INTO cal_month (report_month, month_start, fy, fy_month, quarter, half)
WITH RECURSIVE m (month_start) AS (
    SELECT DATE '1960-04-01'
    UNION ALL
    SELECT month_start + INTERVAL 1 MONTH FROM m WHERE month_start < DATE '2040-03-01'
),
f AS (
    SELECT month_start,
           YEAR(month_start) - (MONTH(month_start) < 4) AS fy_start,
           (MONTH(month_start) + 8) MOD 12 + 1          AS fy_month
    FROM m
)
SELECT DATE_FORMAT(month_start, '%Y-%m'),
       month_start,
       CONCAT(fy_start, '-', LPAD((fy_start + 1) MOD 100, 2, '0')),
       fy_month,
       (fy_month - 1) DIV 3 + 1,
       (fy_month - 1) DIV 6 + 1
FROM f;
