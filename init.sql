CREATE DATABASE IF NOT EXISTS task_scheduler;
USE task_scheduler;

-- users table
CREATE TABLE `users` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app_user_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT 'user ID',
  `ip_address` varchar(64) NOT NULL COMMENT 'user ip address',
  `create_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `update_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `archive_user_id` varchar(64) DEFAULT NULL,
  `latest_anchor_token` varchar(64) DEFAULT NULL,
  `latest_sec_user_id` varchar(64) DEFAULT NULL,
  `platform_username` varchar(64) DEFAULT NULL,
  `is_watch_history_available` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT 'unknow',
  `time_zone` varchar(64) DEFAULT NULL,
  `waitlist_opt_in` tinyint(1) DEFAULT NULL,
  `waitlist_opt_in_at` tinyint(1) DEFAULT NULL,
  `email` varchar(128) DEFAULT NULL,
  `verfied_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`app_user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

-- tasks 
CREATE TABLE `tasks` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `task_id` varchar(64) DEFAULT NULL COMMENT 'task ID',
  `app_user_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT 'user ID',
  `status` enum('pending','verifying','collecting','analyzing','completed','failed','paused','cancelled','rejected','finalized','email_send') DEFAULT 'pending',
  `region_verify_status` enum('success','failed','timeout','retrying','verifying') DEFAULT NULL COMMENT 'validate region status',
  `region_verify_result` json DEFAULT NULL COMMENT 'validate region result',
  `region_retry_count` tinyint DEFAULT '0' COMMENT 'validate region retry count',
  `collect_total` int DEFAULT '0' COMMENT 'total records to collect',
  `collect_completed` int DEFAULT '0' COMMENT 'completed records',
  `collect_page` int DEFAULT '0' COMMENT 'current page (20 per page)',
  `collect_status` enum('not_started','collecting','completed','failed') DEFAULT 'not_started',
  `analysis_status` enum('success','failed','timeout','not_executed') DEFAULT 'not_executed',
  `analysis_result` json DEFAULT NULL COMMENT 'analysis result',
  `error_msg` text COMMENT 'error message',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `device_id` varchar(64) DEFAULT NULL,
  `email_status` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_task_status` (`status`),
  KEY `idx_user_id` (`app_user_id`),
  KEY `idx_task_id` (`task_id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

-- API request logs
CREATE TABLE `api_call_logs` (
  `log_id` bigint NOT NULL AUTO_INCREMENT,
  `task_id` varchar(64) NOT NULL COMMENT 'task ID',
  `api_type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'api type',
  `request_url` varchar(256) NOT NULL COMMENT 'api endpoint',
  `request_params` json DEFAULT NULL COMMENT 'request parameters',
  `request_headers` json DEFAULT NULL COMMENT 'request headers',
  `response_code` int DEFAULT NULL COMMENT 'response code',
  `response_data` json DEFAULT NULL COMMENT 'response data',
  `cost_time` float DEFAULT NULL COMMENT 'call duration (seconds)',
  `status` enum('success','timeout','failed') NOT NULL COMMENT 'call status',
  `error_detail` text COMMENT 'error detail',
  `retry_count` tinyint DEFAULT '0' COMMENT 'number of retries',
  `call_time` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`log_id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_api_type` (`api_type`)
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

-- browse records table
CREATE TABLE IF NOT EXISTS browse_records (
    record_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL COMMENT 'task ID',
    user_id VARCHAR(64) NOT NULL,
    url VARCHAR(256) NOT NULL,
    browse_time DATETIME NOT NULL,
    stay_duration INT COMMENT 'stay duration (seconds)',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id)
);

-- Retry strategies table
CREATE TABLE IF NOT EXISTS retry_strategies (
    strategy_id VARCHAR(64) PRIMARY KEY COMMENT 'strategy ID',
    api_type VARCHAR(64) NOT NULL COMMENT 'api type',
    max_retry_count TINYINT DEFAULT 3 COMMENT 'max retry count',
    initial_delay FLOAT DEFAULT 1.0 COMMENT 'initial retry delay (seconds)',
    max_delay FLOAT DEFAULT 10.0 COMMENT 'max retry delay (seconds)',
    multiplier FLOAT DEFAULT 2.0 COMMENT 'delay multiplier',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_api_type (api_type)
);

CREATE TABLE `app_sessions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_user_id` varchar(64) DEFAULT NULL,
  `device_id` varchar(64) DEFAULT NULL,
  `platform` varchar(64) DEFAULT NULL,
  `app_version` varchar(64) DEFAULT NULL,
  `os_version` varchar(64) DEFAULT NULL,
  `token_hash` varchar(64) DEFAULT NULL,
  `token_encrypted` varchar(128) DEFAULT NULL,
  `issued_at` datetime DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `revoked_at` datetime DEFAULT NULL,
  `session_id` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

-- Insert default retry strategies
INSERT IGNORE INTO retry_strategies (strategy_id, api_type, max_retry_count, initial_delay, max_delay, multiplier)
VALUES 
('strategy_region', 'region_verify', 5, 1.0, 10.0, 2.0),
('strategy_collect', 'browse_collect', 3, 1.0, 5.0, 2.0),
('strategy_analysis', 'browse_analysis', 3, 1.0, 5.0, 2.0);