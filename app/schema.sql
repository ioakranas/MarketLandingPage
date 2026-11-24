-- Database schema. Executed on every application start, so every statement must be
-- idempotent (IF NOT EXISTS / INSERT OR IGNORE).
--
-- STRICT tables make SQLite enforce column types. By default SQLite would happily
-- store the text 'abc' in an INTEGER column.
--
-- The CHECK constraints are the last line of defence. The application validates
-- everything first (with user-friendly messages); these only guarantee that invalid
-- data can never reach the table, whatever code path writes to it.

CREATE TABLE IF NOT EXISTS countries (
    id         INTEGER PRIMARY KEY,
    iso_code   TEXT    NOT NULL UNIQUE CHECK (length(iso_code) = 2),
    name       TEXT    NOT NULL UNIQUE,
    -- Digits only, without the leading '+' (that is presentation).
    dial_code  TEXT    NOT NULL CHECK (dial_code <> '' AND dial_code NOT GLOB '*[^0-9]*')
) STRICT;

CREATE TABLE IF NOT EXISTS customers (
    id             INTEGER PRIMARY KEY,
    first_name     TEXT    NOT NULL CHECK (length(first_name) > 3 AND length(first_name) <= 50),
    last_name      TEXT    NOT NULL CHECK (length(last_name)  > 3 AND length(last_name)  <= 50),
    country_id     INTEGER NOT NULL REFERENCES countries (id),
    -- National number, digits only. The dial code is derived from the country.
    phone          TEXT    NOT NULL CHECK (length(phone) BETWEEN 6 AND 14 AND phone NOT GLOB '*[^0-9]*'),
    -- COLLATE NOCASE makes the UNIQUE constraint case-insensitive.
    email          TEXT    NOT NULL UNIQUE COLLATE NOCASE CHECK (length(email) <= 254 AND email LIKE '%_@_%'),
    password_hash  TEXT    NOT NULL,
    created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP  -- UTC
) STRICT;

-- One row per login attempt against an existing account: audit trail, login
-- statistics (count / last login) and the source for temporary account lockout.
CREATE TABLE IF NOT EXISTS login_attempts (
    id            INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers (id) ON DELETE CASCADE,
    success       INTEGER NOT NULL CHECK (success IN (0, 1)),
    ip_address    TEXT,
    attempted_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP  -- UTC
) STRICT;

-- Serves "failed attempts for this customer in the last N minutes".
CREATE INDEX IF NOT EXISTS idx_login_attempts_customer_time
    ON login_attempts (customer_id, attempted_at);

INSERT OR IGNORE INTO countries (iso_code, name, dial_code) VALUES
    ('GR', 'Greece',         '30'),
    ('CY', 'Cyprus',         '357'),
    ('GB', 'United Kingdom', '44');
