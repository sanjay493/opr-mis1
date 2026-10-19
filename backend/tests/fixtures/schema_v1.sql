
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `activity_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_email` varchar(190) DEFAULT NULL,
  `user_name` varchar(190) DEFAULT NULL,
  `action` varchar(64) NOT NULL,
  `entity` varchar(160) DEFAULT NULL,
  `details` text,
  `timestamp` varchar(40) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_activity_ts` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `admin_notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `admin_notifications` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` varchar(40) NOT NULL,
  `kind` varchar(20) NOT NULL,
  `user_email` varchar(190) DEFAULT NULL,
  `user_name` varchar(190) DEFAULT NULL,
  `ip_address` varchar(64) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_admin_notif_kind_ip` (`kind`,`ip_address`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `allowed_emails`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `allowed_emails` (
  `email` varchar(190) NOT NULL,
  `added_by` varchar(190) DEFAULT NULL,
  `added_at` varchar(40) NOT NULL,
  `barred` int NOT NULL DEFAULT '0',
  `barred_by` varchar(190) DEFAULT NULL,
  `barred_at` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bf_benchmark_external_bf`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bf_benchmark_external_bf` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(190) NOT NULL,
  `company` varchar(190) DEFAULT '',
  `location` varchar(190) DEFAULT '',
  `working_volume_m3` double DEFAULT NULL,
  `active` tinyint NOT NULL DEFAULT '1',
  `created_at` varchar(40) NOT NULL,
  `created_by` varchar(190) DEFAULT '',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bf_benchmark_external_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bf_benchmark_external_data` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `external_bf_id` bigint NOT NULL,
  `report_month` char(7) NOT NULL,
  `param_json` json NOT NULL,
  `created_at` varchar(40) DEFAULT NULL,
  `updated_at` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_bf_benchmark_ext` (`external_bf_id`,`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bf_benchmark_sail_meta`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bf_benchmark_sail_meta` (
  `plant` varchar(32) NOT NULL,
  `unit` varchar(32) NOT NULL,
  `working_volume_m3` double DEFAULT NULL,
  `updated_at` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`plant`,`unit`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `board_note_manual_text`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `board_note_manual_text` (
  `report_fy` char(7) NOT NULL,
  `quarter` tinyint NOT NULL,
  `plant` varchar(16) NOT NULL,
  `field` varchar(24) NOT NULL,
  `text` text,
  PRIMARY KEY (`report_fy`,`quarter`,`plant`,`field`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `breakdown_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `breakdown_table` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `plant` varchar(8) NOT NULL,
  `unit_type` varchar(16) NOT NULL,
  `unit_name` varchar(32) NOT NULL,
  `sms_subtag` varchar(16) DEFAULT NULL,
  `start_ts` varchar(16) NOT NULL,
  `end_ts` varchar(16) DEFAULT NULL,
  `is_ongoing` tinyint(1) NOT NULL DEFAULT '0',
  `cause` text NOT NULL,
  `hours_lost_override` double DEFAULT NULL,
  `capital_repair_id` bigint DEFAULT NULL,
  `created_by` varchar(190) DEFAULT NULL,
  `created_at` varchar(40) DEFAULT NULL,
  `updated_by` varchar(190) DEFAULT NULL,
  `updated_at` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_breakdown_plant_unit` (`plant`,`unit_type`,`unit_name`),
  KEY `idx_breakdown_start` (`start_ts`),
  KEY `idx_breakdown_cr` (`capital_repair_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `capital_repair_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `capital_repair_table` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `plant` varchar(8) NOT NULL,
  `fy` varchar(8) NOT NULL,
  `shop` varchar(64) DEFAULT NULL,
  `equipment` varchar(64) DEFAULT NULL,
  `unit_type` varchar(16) DEFAULT NULL,
  `unit_name` varchar(32) DEFAULT NULL,
  `sms_subtag` varchar(16) DEFAULT NULL,
  `activity` varchar(255) DEFAULT NULL,
  `schedule_days` varchar(64) DEFAULT NULL,
  `actual_start` char(10) DEFAULT NULL,
  `actual_end` char(10) DEFAULT NULL,
  `actual_ongoing` tinyint(1) NOT NULL DEFAULT '0',
  `planned_days` double DEFAULT NULL,
  `period` varchar(64) DEFAULT NULL,
  `actual` varchar(128) DEFAULT NULL,
  `sort_order` int DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_cr_plant_fy` (`plant`,`fy`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cost_trend_annual`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cost_trend_annual` (
  `fy` char(7) NOT NULL,
  `product` varchar(8) NOT NULL,
  `cost_type` varchar(16) NOT NULL,
  `plant` varchar(16) NOT NULL,
  `value` double DEFAULT NULL,
  PRIMARY KEY (`fy`,`product`,`cost_type`,`plant`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cost_trend_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cost_trend_monthly` (
  `report_month` char(7) NOT NULL,
  `product` varchar(8) NOT NULL,
  `cost_type` varchar(16) NOT NULL,
  `plant` varchar(16) NOT NULL,
  `month_value` double DEFAULT NULL,
  `till_month_value` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`product`,`cost_type`,`plant`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cover_photos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cover_photos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `filename` varchar(64) NOT NULL,
  `thumb_filename` varchar(64) NOT NULL,
  `original_name` varchar(255) NOT NULL,
  `width` int DEFAULT NULL,
  `height` int DEFAULT NULL,
  `uploaded_by` varchar(255) DEFAULT NULL,
  `uploaded_at` char(19) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `daily_work_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `daily_work_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `work_date` varchar(10) NOT NULL,
  `description` text NOT NULL,
  `remarks` text,
  `created_at` varchar(40) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `do_letter_remark_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `do_letter_remark_table` (
  `report_month` char(7) NOT NULL,
  `item_name` varchar(32) NOT NULL,
  `plant_name` varchar(8) NOT NULL,
  `remark` text,
  PRIMARY KEY (`report_month`,`item_name`,`plant_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `extraction_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `extraction_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `logged_at` varchar(40) NOT NULL,
  `plant_name` varchar(32) NOT NULL,
  `report_month` char(7) NOT NULL,
  `file_name` varchar(255) DEFAULT NULL,
  `sheet_name` varchar(160) DEFAULT NULL,
  `source_type` varchar(160) DEFAULT NULL,
  `items_extracted` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_extraction_logged` (`logged_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ipt_data_json`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ipt_data_json` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `report_month` char(7) NOT NULL,
  `data` json NOT NULL,
  `source` varchar(32) DEFAULT 'excel',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `report_month` (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ipt_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ipt_table` (
  `report_month` char(7) NOT NULL,
  `item` varchar(64) NOT NULL,
  `from_plant` varchar(32) NOT NULL,
  `to_plant` varchar(32) NOT NULL,
  `unit` varchar(32) DEFAULT NULL,
  `sort_order` int DEFAULT '0',
  `plan` double DEFAULT NULL,
  `actual` double DEFAULT NULL,
  `plan_tonnage` double DEFAULT NULL,
  `actual_tonnage` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`item`,`from_plant`,`to_plant`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `item_capacity_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `item_capacity_table` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `plant_name` varchar(8) NOT NULL,
  `item_name` varchar(64) NOT NULL,
  `effective_month` char(7) NOT NULL,
  `annual_capacity` double NOT NULL,
  `reason` varchar(255) DEFAULT '',
  `created_by` varchar(190) DEFAULT NULL,
  `created_at` varchar(40) DEFAULT NULL,
  `updated_by` varchar(190) DEFAULT NULL,
  `updated_at` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_capacity_plant_item_month` (`plant_name`,`item_name`,`effective_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `key_highlights_narrative`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `key_highlights_narrative` (
  `report_month` char(7) NOT NULL,
  `achievements` text,
  `shortfalls` text,
  `focus_areas` text,
  `updated_by` varchar(190) DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `macro_indicators_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `macro_indicators_monthly` (
  `report_month` char(7) NOT NULL,
  `metric_code` varchar(32) NOT NULL,
  `value` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`metric_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `major_unit_daily_record`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `major_unit_daily_record` (
  `plant_code` varchar(8) NOT NULL,
  `unit_label` varchar(64) NOT NULL,
  `unit_of_measure` varchar(16) DEFAULT NULL,
  `value` double DEFAULT NULL,
  `record_date` varchar(10) DEFAULT NULL,
  `remarks` text,
  `sort_order` int NOT NULL DEFAULT '0',
  `updated_by` varchar(128) DEFAULT NULL,
  `updated_at` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`plant_code`,`unit_label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `market_price_trend_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `market_price_trend_monthly` (
  `report_month` char(7) NOT NULL,
  `series_code` varchar(48) NOT NULL,
  `value` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`series_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mine_end_uses_master`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mine_end_uses_master` (
  `end_use_code` varchar(16) NOT NULL,
  `end_use_name` varchar(48) NOT NULL,
  `sort_order` int NOT NULL,
  `tracks_actual` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`end_use_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mine_groups_master`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mine_groups_master` (
  `group_code` varchar(8) NOT NULL,
  `group_name` varchar(64) NOT NULL,
  `sort_order` int NOT NULL,
  PRIMARY KEY (`group_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mine_materials_master`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mine_materials_master` (
  `material_code` varchar(16) NOT NULL,
  `material_name` varchar(32) NOT NULL,
  `material_category` varchar(16) NOT NULL,
  `has_production` tinyint(1) NOT NULL DEFAULT '0',
  `counts_in_total_production` tinyint(1) NOT NULL DEFAULT '0',
  `sort_order` int NOT NULL,
  PRIMARY KEY (`material_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mines_booked_qty_actual_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mines_booked_qty_actual_monthly` (
  `report_month` char(7) NOT NULL,
  `mine_code` varchar(24) NOT NULL,
  `material_code` varchar(16) NOT NULL,
  `transport_mode` varchar(8) NOT NULL,
  `qty_actual` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`mine_code`,`material_code`,`transport_mode`),
  KEY `mine_code` (`mine_code`),
  KEY `material_code` (`material_code`),
  KEY `idx_mines_booked_qty_actual_material` (`report_month`,`material_code`),
  CONSTRAINT `mines_booked_qty_actual_monthly_ibfk_1` FOREIGN KEY (`mine_code`) REFERENCES `mines_master` (`mine_code`),
  CONSTRAINT `mines_booked_qty_actual_monthly_ibfk_2` FOREIGN KEY (`material_code`) REFERENCES `mine_materials_master` (`material_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mines_booked_qty_plan_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mines_booked_qty_plan_monthly` (
  `report_month` char(7) NOT NULL,
  `mine_code` varchar(24) NOT NULL,
  `material_code` varchar(16) NOT NULL,
  `qty_plan` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`mine_code`,`material_code`),
  KEY `mine_code` (`mine_code`),
  KEY `material_code` (`material_code`),
  KEY `idx_mines_booked_qty_plan_material` (`report_month`,`material_code`),
  CONSTRAINT `mines_booked_qty_plan_monthly_ibfk_1` FOREIGN KEY (`mine_code`) REFERENCES `mines_master` (`mine_code`),
  CONSTRAINT `mines_booked_qty_plan_monthly_ibfk_2` FOREIGN KEY (`material_code`) REFERENCES `mine_materials_master` (`material_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mines_despatch_actual_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mines_despatch_actual_monthly` (
  `report_month` char(7) NOT NULL,
  `mine_code` varchar(24) NOT NULL,
  `material_code` varchar(16) NOT NULL,
  `transport_mode` varchar(8) NOT NULL,
  `end_use_code` varchar(16) NOT NULL,
  `qty_actual` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`mine_code`,`material_code`,`transport_mode`,`end_use_code`),
  KEY `mine_code` (`mine_code`),
  KEY `material_code` (`material_code`),
  KEY `end_use_code` (`end_use_code`),
  KEY `idx_mines_despatch_actual_material` (`report_month`,`material_code`),
  KEY `idx_mines_despatch_actual_enduse` (`report_month`,`end_use_code`),
  CONSTRAINT `mines_despatch_actual_monthly_ibfk_1` FOREIGN KEY (`mine_code`) REFERENCES `mines_master` (`mine_code`),
  CONSTRAINT `mines_despatch_actual_monthly_ibfk_2` FOREIGN KEY (`material_code`) REFERENCES `mine_materials_master` (`material_code`),
  CONSTRAINT `mines_despatch_actual_monthly_ibfk_3` FOREIGN KEY (`end_use_code`) REFERENCES `mine_end_uses_master` (`end_use_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mines_despatch_plan_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mines_despatch_plan_monthly` (
  `report_month` char(7) NOT NULL,
  `mine_code` varchar(24) NOT NULL,
  `material_code` varchar(16) NOT NULL,
  `end_use_code` varchar(16) NOT NULL,
  `qty_plan` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`mine_code`,`material_code`,`end_use_code`),
  KEY `mine_code` (`mine_code`),
  KEY `material_code` (`material_code`),
  KEY `end_use_code` (`end_use_code`),
  KEY `idx_mines_despatch_plan_material` (`report_month`,`material_code`),
  CONSTRAINT `mines_despatch_plan_monthly_ibfk_1` FOREIGN KEY (`mine_code`) REFERENCES `mines_master` (`mine_code`),
  CONSTRAINT `mines_despatch_plan_monthly_ibfk_2` FOREIGN KEY (`material_code`) REFERENCES `mine_materials_master` (`material_code`),
  CONSTRAINT `mines_despatch_plan_monthly_ibfk_3` FOREIGN KEY (`end_use_code`) REFERENCES `mine_end_uses_master` (`end_use_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mines_master`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mines_master` (
  `mine_code` varchar(24) NOT NULL,
  `mine_name` varchar(64) NOT NULL,
  `group_code` varchar(8) NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `sort_order` int NOT NULL,
  PRIMARY KEY (`mine_code`),
  KEY `group_code` (`group_code`),
  CONSTRAINT `mines_master_ibfk_1` FOREIGN KEY (`group_code`) REFERENCES `mine_groups_master` (`group_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mines_production_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mines_production_monthly` (
  `report_month` char(7) NOT NULL,
  `mine_code` varchar(24) NOT NULL,
  `material_code` varchar(16) NOT NULL,
  `qty_actual` double DEFAULT NULL,
  `qty_plan` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`mine_code`,`material_code`),
  KEY `mine_code` (`mine_code`),
  KEY `material_code` (`material_code`),
  CONSTRAINT `mines_production_monthly_ibfk_1` FOREIGN KEY (`mine_code`) REFERENCES `mines_master` (`mine_code`),
  CONSTRAINT `mines_production_monthly_ibfk_2` FOREIGN KEY (`material_code`) REFERENCES `mine_materials_master` (`material_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `mou_plan_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mou_plan_table` (
  `report_month` char(7) NOT NULL,
  `plant_name` varchar(32) NOT NULL,
  `item_name` varchar(64) NOT NULL,
  `month_actual` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`plant_name`,`item_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `otp_codes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `otp_codes` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `email` varchar(190) NOT NULL,
  `purpose` varchar(32) NOT NULL,
  `code_hash` varchar(255) NOT NULL,
  `expires_at` varchar(40) NOT NULL,
  `used` int NOT NULL DEFAULT '0',
  `created_at` varchar(40) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `page3_narrative`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `page3_narrative` (
  `report_month` char(7) NOT NULL,
  `production_narrative` text,
  `highlights` text,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `page_configs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `page_configs` (
  `report_month` char(7) NOT NULL,
  `page_number` int NOT NULL,
  `page_data` mediumtext,
  PRIMARY KEY (`report_month`,`page_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `page_visits`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `page_visits` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `timestamp` varchar(40) NOT NULL,
  `ip_address` varchar(64) DEFAULT NULL,
  `user_email` varchar(190) DEFAULT NULL,
  `user_name` varchar(190) DEFAULT NULL,
  `path` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_visits_ts` (`timestamp`),
  KEY `idx_visits_email` (`user_email`),
  KEY `idx_visits_ip` (`ip_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `pdf_item_alias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pdf_item_alias` (
  `plant_name` varchar(32) NOT NULL,
  `pdf_label` varchar(160) NOT NULL,
  `item_name` varchar(64) NOT NULL,
  `convert_t` int DEFAULT '1',
  PRIMARY KEY (`plant_name`,`pdf_label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `power_data_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `power_data_table` (
  `report_month` char(7) NOT NULL,
  `plant_name` varchar(32) NOT NULL,
  `item_name` varchar(64) NOT NULL,
  `value` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`plant_name`,`item_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `production_data_json`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `production_data_json` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `report_month` char(7) NOT NULL,
  `data` json NOT NULL,
  `source` varchar(32) DEFAULT 'excel',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `report_month` (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `production_plan_json`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `production_plan_json` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `report_month` char(7) NOT NULL,
  `data` json NOT NULL,
  `source` varchar(32) DEFAULT 'excel',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `report_month` (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `production_plan_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `production_plan_table` (
  `report_month` char(7) NOT NULL,
  `plant_name` varchar(32) NOT NULL,
  `item_name` varchar(64) NOT NULL,
  `month_actual` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`plant_name`,`item_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `production_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `production_table` (
  `report_month` char(7) NOT NULL,
  `plant_name` varchar(32) NOT NULL,
  `item_name` varchar(64) NOT NULL,
  `month_actual` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`plant_name`,`item_name`),
  KEY `idx_prod_plant_item` (`plant_name`,`item_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `rail_prod_despatch`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rail_prod_despatch` (
  `financial_year` char(7) NOT NULL,
  `metric` varchar(32) NOT NULL,
  `value` double DEFAULT NULL,
  `note` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`financial_year`,`metric`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `rail_prod_despatch_note`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rail_prod_despatch_note` (
  `sort_order` int NOT NULL,
  `note_text` varchar(500) NOT NULL,
  PRIMARY KEY (`sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `rake_detention_annual`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rake_detention_annual` (
  `plant` varchar(8) NOT NULL,
  `financial_year` char(7) NOT NULL,
  `avg_hours` double DEFAULT NULL,
  PRIMARY KEY (`plant`,`financial_year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `rake_detention_master`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rake_detention_master` (
  `id` int NOT NULL AUTO_INCREMENT,
  `plant` varchar(8) NOT NULL,
  `section` varchar(8) NOT NULL,
  `commodity` varchar(48) DEFAULT NULL,
  `wagon_type` varchar(24) DEFAULT NULL,
  `row_label` varchar(48) NOT NULL,
  `is_total` tinyint(1) NOT NULL DEFAULT '0',
  `direction` varchar(4) DEFAULT NULL,
  `freetime_hours` double DEFAULT NULL,
  `freetime_effective_from` char(10) DEFAULT NULL,
  `sort_order` int NOT NULL DEFAULT '0',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `rake_detention_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rake_detention_monthly` (
  `report_month` char(7) NOT NULL,
  `master_id` int NOT NULL,
  `value_hours` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`master_id`),
  KEY `master_id` (`master_id`),
  CONSTRAINT `rake_detention_monthly_ibfk_1` FOREIGN KEY (`master_id`) REFERENCES `rake_detention_master` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `rake_detention_summary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rake_detention_summary` (
  `report_month` char(7) NOT NULL,
  `period_row` varchar(24) NOT NULL,
  `plant` varchar(8) NOT NULL,
  `value` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`period_row`,`plant`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ready_reckoner_pages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ready_reckoner_pages` (
  `plant_code` varchar(8) NOT NULL,
  `plant_name` varchar(64) DEFAULT NULL,
  `plant_group` varchar(4) NOT NULL,
  `process_flow_image_path` varchar(255) DEFAULT NULL,
  `sort_order` int NOT NULL DEFAULT '0',
  `updated_by` varchar(128) DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `capacity_rows` longtext,
  `product_mix_headers` longtext,
  `product_mix_rows` longtext,
  `product_mix_caption` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`plant_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_cover_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_cover_settings` (
  `report_month` char(7) NOT NULL,
  `design` varchar(24) NOT NULL,
  `photo_mode` varchar(8) NOT NULL DEFAULT 'random',
  `photo_id` int DEFAULT NULL,
  `updated_by` varchar(255) DEFAULT NULL,
  `updated_at` char(19) DEFAULT NULL,
  PRIMARY KEY (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sail_mines_monthly`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sail_mines_monthly` (
  `report_month` char(7) NOT NULL,
  `section` varchar(24) NOT NULL,
  `item` varchar(32) NOT NULL,
  `month_actual` double DEFAULT NULL,
  `month_plan` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`section`,`item`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sail_sales_note_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sail_sales_note_table` (
  `report_month` char(7) NOT NULL,
  `note` text,
  PRIMARY KEY (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sail_sales_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sail_sales_table` (
  `report_month` char(7) NOT NULL,
  `item_name` varchar(64) NOT NULL,
  `data_json` json DEFAULT NULL,
  PRIMARY KEY (`report_month`,`item_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `sail_stock_snapshot_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sail_stock_snapshot_table` (
  `snapshot_date` char(10) NOT NULL,
  `item_name` varchar(32) NOT NULL,
  `value` double DEFAULT NULL,
  PRIMARY KEY (`snapshot_date`,`item_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `secretary_review_text`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `secretary_review_text` (
  `report_month` char(7) NOT NULL,
  `block_key` varchar(32) NOT NULL,
  `text` text,
  `updated_at` varchar(19) DEFAULT NULL,
  PRIMARY KEY (`report_month`,`block_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `special_steel_abp_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_steel_abp_table` (
  `report_month` char(7) NOT NULL,
  `plant_name` varchar(32) NOT NULL,
  `abp_qty` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`plant_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `special_steel_grade_clubs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_steel_grade_clubs` (
  `plant_name` varchar(32) NOT NULL,
  `product` varchar(160) NOT NULL,
  `quality_grade` varchar(160) NOT NULL,
  `club_label` varchar(200) NOT NULL,
  `created_at` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`plant_name`,`product`,`quality_grade`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `special_steel_ipt_requirement`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_steel_ipt_requirement` (
  `financial_year` char(7) NOT NULL,
  `item` varchar(64) NOT NULL,
  `from_plant` varchar(8) NOT NULL,
  `to_plant` varchar(8) NOT NULL,
  `plan_kt` double DEFAULT NULL,
  `sort_order` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`financial_year`,`item`,`from_plant`,`to_plant`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `special_steel_json`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_steel_json` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `report_month` char(7) NOT NULL,
  `data` json NOT NULL,
  `source` varchar(32) DEFAULT 'excel',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `report_month` (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `special_steel_orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_steel_orders` (
  `report_month` char(7) NOT NULL,
  `plant_name` varchar(32) NOT NULL,
  `product` varchar(160) NOT NULL,
  `quality_grade` varchar(160) NOT NULL,
  `section` varchar(160) NOT NULL DEFAULT '',
  `sort_order` int DEFAULT '0',
  `order_qty` double DEFAULT NULL,
  `actual_despatch` double DEFAULT NULL,
  PRIMARY KEY (`report_month`,`plant_name`,`product`,`quality_grade`,`section`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `special_steel_phys_meta`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_steel_phys_meta` (
  `plant` varchar(8) NOT NULL,
  `series` varchar(16) NOT NULL,
  `capacity_kt` double DEFAULT NULL,
  `best_actual_kt` double DEFAULT NULL,
  `best_year` char(7) DEFAULT NULL,
  `remark` varchar(200) DEFAULT NULL,
  `sort_order` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`plant`,`series`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `special_steel_phys_note`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_steel_phys_note` (
  `financial_year` char(7) NOT NULL,
  `sort_order` int NOT NULL,
  `note_text` varchar(500) NOT NULL,
  PRIMARY KEY (`financial_year`,`sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `special_steel_phys_perf`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_steel_phys_perf` (
  `financial_year` char(7) NOT NULL,
  `plant` varchar(8) NOT NULL,
  `series` varchar(16) NOT NULL,
  `metric` varchar(8) NOT NULL,
  `value_kt` double DEFAULT NULL,
  PRIMARY KEY (`financial_year`,`plant`,`series`,`metric`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `steel_sales_highlights`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `steel_sales_highlights` (
  `report_month` char(7) NOT NULL,
  `month_items` text,
  `ytd_items` text,
  `updated_by` varchar(190) DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `steel_sector_performance_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `steel_sector_performance_table` (
  `report_month` char(7) NOT NULL,
  `data_json` json DEFAULT NULL,
  `source_file` varchar(255) DEFAULT NULL,
  `created_at` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `stock_data_json`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stock_data_json` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `stock_month` char(7) NOT NULL,
  `data` json NOT NULL,
  `source` varchar(32) DEFAULT 'excel',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `stock_month` (`stock_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `stock_table`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stock_table` (
  `stock_month` char(7) NOT NULL,
  `plant_name` varchar(32) NOT NULL,
  `item_type` varchar(64) NOT NULL,
  `stock_type` varchar(64) NOT NULL DEFAULT '',
  `stock` double DEFAULT NULL,
  PRIMARY KEY (`stock_month`,`plant_name`,`item_type`,`stock_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `techno_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `techno_data` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `plant` varchar(32) NOT NULL,
  `report_month` char(7) NOT NULL,
  `unit` varchar(32) NOT NULL,
  `techno_json` json NOT NULL,
  `source_file` varchar(255) DEFAULT '',
  `created_at` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_techno` (`plant`,`report_month`,`unit`),
  KEY `idx_techno_month` (`report_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `techno_plan_fy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `techno_plan_fy` (
  `plant_name` varchar(32) NOT NULL,
  `unit` varchar(32) NOT NULL,
  `fy` char(7) NOT NULL,
  `techno_json` json NOT NULL,
  `is_user_supplied` int DEFAULT '0',
  `calculated_json` json DEFAULT NULL,
  `calculation_method` json DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `created_by` varchar(190) DEFAULT NULL,
  PRIMARY KEY (`plant_name`,`unit`,`fy`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `todo_jobs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `todo_jobs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `subject` varchar(255) NOT NULL,
  `details` text,
  `recipient` varchar(255) DEFAULT NULL,
  `due_date` varchar(10) NOT NULL,
  `priority` varchar(16) NOT NULL DEFAULT 'medium',
  `status` varchar(16) NOT NULL DEFAULT 'pending',
  `created_at` varchar(40) NOT NULL,
  `completed_at` varchar(40) DEFAULT NULL,
  `remark` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `email` varchar(190) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `name` varchar(190) DEFAULT '',
  `role` varchar(32) DEFAULT NULL,
  `profile_pic` varchar(255) DEFAULT '',
  `created_at` varchar(40) NOT NULL,
  `updated_at` varchar(40) DEFAULT NULL,
  `allowed_pages` text,
  `can_delete` tinyint NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

