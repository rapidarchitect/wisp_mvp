-- Control-plane database schema.
-- Holds only what must exist before a tenant database does.

CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    address TEXT,
    logo_path TEXT,
    status TEXT NOT NULL DEFAULT 'provisioning',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL UNIQUE,
    tier TEXT NOT NULL DEFAULT 'standard',
    funding TEXT NOT NULL CHECK (funding IN ('card', 'voucher')),
    stripe_customer_id TEXT,
    stripe_checkout_id TEXT,
    voucher_code TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'canceled')),
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (voucher_code) REFERENCES vouchers(code)
);

CREATE TABLE IF NOT EXISTS vouchers (
    code TEXT PRIMARY KEY,
    issued_to TEXT NOT NULL,
    redeemed_by_tenant_id INTEGER,
    redeemed_at TEXT,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (redeemed_by_tenant_id) REFERENCES tenants(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
