-- ============================== init-postgres.sql ==============================
-- CLAIM2CAR CONNECT™ FAOS - Initial Postgres schema and enums
-- This script is idempotent and safe to run multiple times on startup.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core Enums
CREATE TYPE user_role AS ENUM ('admin', 'carrier', 'dealer', 'tow_company', 'tow_driver', 'shop', 'inspector', 'system');
CREATE TYPE sync_status AS ENUM ('pending', 'syncing', 'synced', 'failed');

-- Tenants
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'tow_driver'
);

-- Idempotency locks
CREATE TABLE IF NOT EXISTS idempotency_locks (
    idempotency_key VARCHAR(255) PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
    response_payload JSONB,
    locked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for cache/perf
CREATE INDEX IF NOT EXISTS idx_idempotency_status ON idempotency_locks(status);

-- End of init-postgres.sql
