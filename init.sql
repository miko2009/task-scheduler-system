CREATE DATABASE IF NOT EXISTS task_scheduler;
USE task_scheduler;

-- users table
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64) COMMENT 'user ID',
    ip_address VARCHAR(64) NOT NULL COMMENT 'user ip address',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id)
);

-- tasks 
CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(64) COMMENT 'task ID',
    user_id VARCHAR(64) NOT NULL COMMENT 'user ID',
    status ENUM('pending', 'verifying', 'collecting', 'analyzing', 'completed', 'failed', 'paused', 'cancelled', 'rejected') DEFAULT 'pending',
    region_verify_status ENUM('success', 'failed', 'timeout', 'retrying', 'verifying') COMMENT 'validate region status',
    region_verify_result JSON COMMENT 'validate region result',
    region_retry_count TINYINT DEFAULT 0 COMMENT 'validate region retry count',
    collect_total INT DEFAULT 0 COMMENT 'total records to collect',
    collect_completed INT DEFAULT 0 COMMENT 'completed records',
    collect_page INT DEFAULT 0 COMMENT 'current page (20 per page)',
    collect_status ENUM('not_started', 'collecting', 'completed', 'failed') DEFAULT 'not_started',
    analysis_status ENUM('success', 'failed', 'timeout', 'not_executed') DEFAULT 'not_executed',
    analysis_result JSON COMMENT 'analysis result',
    error_msg TEXT COMMENT 'error message',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_task_status (status),
    INDEX idx_user_id (user_id),
    INDEX idx_task_id (task_id)
);

-- API request logs
CREATE TABLE IF NOT EXISTS api_call_logs (
    log_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL COMMENT 'task ID',
    api_type ENUM('region_verify', 'browse_collect', 'browse_analysis') NOT NULL COMMENT 'api type',
    request_url VARCHAR(256) NOT NULL COMMENT 'api endpoint',
    request_params JSON COMMENT 'request parameters',
    request_headers JSON COMMENT 'request headers',
    response_code INT COMMENT 'response code',
    response_data JSON COMMENT 'response data',
    cost_time FLOAT COMMENT 'call duration (seconds)',
    status ENUM('success', 'timeout', 'failed') NOT NULL COMMENT 'call status',
    error_detail TEXT COMMENT 'error detail',
    retry_count TINYINT DEFAULT 0 COMMENT 'number of retries',
    call_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_api_type (api_type)
);

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
    api_type ENUM('region_verify', 'browse_collect', 'browse_analysis') NOT NULL COMMENT 'api type',
    max_retry_count TINYINT DEFAULT 3 COMMENT 'max retry count',
    initial_delay FLOAT DEFAULT 1.0 COMMENT 'initial retry delay (seconds)',
    max_delay FLOAT DEFAULT 10.0 COMMENT 'max retry delay (seconds)',
    multiplier FLOAT DEFAULT 2.0 COMMENT 'delay multiplier',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_api_type (api_type)
);

-- Insert default retry strategies
INSERT IGNORE INTO retry_strategies (strategy_id, api_type, max_retry_count, initial_delay, max_delay, multiplier)
VALUES 
('strategy_region', 'region_verify', 5, 1.0, 10.0, 2.0),
('strategy_collect', 'browse_collect', 3, 1.0, 5.0, 2.0),
('strategy_analysis', 'browse_analysis', 3, 1.0, 5.0, 2.0);