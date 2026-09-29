// Tables are created automatically on first start (CREATE TABLE IF NOT EXISTS),
// so deploying only needs an empty MySQL/MariaDB database.
const opts = 'ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci';

export const SCHEMA: string[] = [
  `CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    discord_nickname VARCHAR(64) NOT NULL,
    public_nickname VARCHAR(32) NOT NULL,
    avatar_preset VARCHAR(16) NULL,
    avatar_file VARCHAR(64) NULL,
    role ENUM('participant','admin') NOT NULL DEFAULT 'participant',
    status ENUM('pending','active','rejected','suspended','deleted') NOT NULL DEFAULT 'pending',
    consent_terms_at DATETIME NULL,
    consent_public_profile_at DATETIME NULL,
    deletion_requested_at DATETIME NULL,
    verified_by INT UNSIGNED NULL,
    verified_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_users_email (email),
    UNIQUE KEY uq_users_nick (public_nickname),
    KEY idx_users_status (status)
  ) ${opts}`,

  `CREATE TABLE IF NOT EXISTS events (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(64) NOT NULL,
    motivation_text VARCHAR(255) NOT NULL DEFAULT '',
    access_code_hash VARCHAR(100) NULL,
    access_code_required TINYINT(1) NOT NULL DEFAULT 1,
    registration_open TINYINT(1) NOT NULL DEFAULT 1,
    is_public_leaderboard TINYINT(1) NOT NULL DEFAULT 1,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uq_events_slug (slug)
  ) ${opts}`,

  `CREATE TABLE IF NOT EXISTS reporting_periods (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id INT UNSIGNED NOT NULL,
    week_number INT UNSIGNED NOT NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    entry_deadline DATETIME NOT NULL,
    is_locked TINYINT(1) NOT NULL DEFAULT 0,
    UNIQUE KEY uq_period_week (event_id, week_number),
    CONSTRAINT fk_period_event FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
  ) ${opts}`,

  `CREATE TABLE IF NOT EXISTS revenue_entries (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    reporting_period_id INT UNSIGNED NOT NULL,
    cumulative_revenue BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_entry_user_period (user_id, reporting_period_id),
    KEY idx_entry_event (event_id),
    CONSTRAINT fk_entry_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_entry_period FOREIGN KEY (reporting_period_id) REFERENCES reporting_periods(id) ON DELETE CASCADE
  ) ${opts}`,

  `CREATE TABLE IF NOT EXISTS revenue_entry_audit_log (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    revenue_entry_id INT UNSIGNED NULL,
    user_id INT UNSIGNED NOT NULL,
    reporting_period_id INT UNSIGNED NOT NULL,
    changed_by_user_id INT UNSIGNED NOT NULL,
    old_value BIGINT UNSIGNED NULL,
    new_value BIGINT UNSIGNED NULL,
    change_reason VARCHAR(255) NULL,
    changed_at DATETIME NOT NULL,
    KEY idx_audit_user (user_id),
    KEY idx_audit_time (changed_at)
  ) ${opts}`,

  `CREATE TABLE IF NOT EXISTS correction_requests (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    reporting_period_id INT UNSIGNED NOT NULL,
    requested_value BIGINT UNSIGNED NOT NULL,
    message VARCHAR(500) NOT NULL DEFAULT '',
    status ENUM('open','resolved','dismissed') NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL,
    resolved_by INT UNSIGNED NULL,
    resolved_at DATETIME NULL,
    KEY idx_corr_status (status),
    CONSTRAINT fk_corr_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
  ) ${opts}`,

  `CREATE TABLE IF NOT EXISTS sessions (
    id CHAR(64) NOT NULL PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    KEY idx_sessions_user (user_id),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
  ) ${opts}`,

  `CREATE TABLE IF NOT EXISTS password_resets (
    token_hash CHAR(64) NOT NULL PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_reset_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
  ) ${opts}`,
];
