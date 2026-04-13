-- Initialize database for QueryPulse-AI

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pgstattuple;

-- Create tables
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS query_history (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT,
    query TEXT,
    execution_time_ms FLOAT,
    plan TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX (tenant_id, created_at)
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT,
    title TEXT,
    message TEXT,
    severity TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    INDEX (tenant_id, created_at)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_query_history_tenant_time ON query_history(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_tenant_time ON alerts(tenant_id, created_at);

-- Insert default tenant
INSERT INTO tenants (id, name) 
VALUES ('default', 'Default Organization')
ON CONFLICT (id) DO NOTHING;

-- Insert default admin user (password: admin123)
INSERT INTO users (email, password_hash, tenant_id) 
VALUES ('admin@example.com', 'admin_placeholder_hash', 'default')
ON CONFLICT (email) DO NOTHING;