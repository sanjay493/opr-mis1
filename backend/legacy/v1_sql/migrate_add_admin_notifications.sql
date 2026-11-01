-- One-time migration: table behind the admin notification bell
-- (frontend/src/components/AdminNotifications.js, db.add_admin_notification).
-- Additive only; safe to re-run.
--
-- Run against the live DB after a fresh backup:
--   backend\scripts\backup_mysql.bat
--   mysql -u mis_app -p mis_reports < backend/scripts/migrate_add_admin_notifications.sql

CREATE TABLE IF NOT EXISTS admin_notifications (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(40) NOT NULL,
    kind       VARCHAR(20) NOT NULL,
    user_email VARCHAR(190),
    user_name  VARCHAR(190),
    ip_address VARCHAR(64),
    path       VARCHAR(255),
    KEY idx_admin_notif_kind_ip (kind, ip_address, created_at)
) ENGINE=InnoDB;
