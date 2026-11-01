-- Cleanup script for SMS production data duplicates
-- Remove entries with quotes at the end

-- First, let's identify and remove duplicate entries with quoted item names
-- These are duplicates with trailing quotes and spaces like 'SMS-2 BLOOM '

DELETE FROM production_plan_table
WHERE item_name LIKE '''%''
  AND report_month >= '2026-04'
  AND report_month <= '2027-03';

-- Verify cleanup - show remaining SMS entries
SELECT plant_name, item_name, SUM(month_actual) as annual_total
FROM production_plan_table
WHERE item_name LIKE '%SMS%'
  AND report_month >= '2026-04'
  AND report_month <= '2027-03'
GROUP BY plant_name, item_name
ORDER BY plant_name, item_name;
