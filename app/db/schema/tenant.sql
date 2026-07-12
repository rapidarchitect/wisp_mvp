-- Per-tenant SQLite database schema.
-- One file per tenant; created at provisioning time.

CREATE TABLE IF NOT EXISTS corporate_vitals (
    tenant_id INTEGER PRIMARY KEY,
    employee_range TEXT NOT NULL,
    clients_per_year_range TEXT NOT NULL,
    primary_software TEXT NOT NULL,
    deployment_type TEXT NOT NULL,
    has_efin INTEGER NOT NULL DEFAULT 0,
    it_support_provider TEXT,
    remote_access INTEGER NOT NULL DEFAULT 0,
    paper_files INTEGER NOT NULL DEFAULT 0,
    sensitive_data_types TEXT NOT NULL DEFAULT '[]',
    coordinator_name TEXT NOT NULL,
    coordinator_title TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    totp_secret TEXT,
    totp_enrolled INTEGER NOT NULL DEFAULT 0,
    roles TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'invited' CHECK (status IN ('invited', 'active', 'deactivated')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    roles TEXT NOT NULL DEFAULT '[]',
    token TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    accepted_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    issued_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wisp_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'complete')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    parent_version_id INTEGER,
    UNIQUE (tenant_id, number),
    FOREIGN KEY (parent_version_id) REFERENCES wisp_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL CHECK (code IN (
        'AC', 'PE', 'RA', 'CA', 'SC', 'SI', 'AT', 'AU',
        'CM', 'IA', 'IR', 'MA', 'MP', 'PS'
    )),
    name TEXT NOT NULL,
    wisp_version_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_questions' CHECK (
        status IN ('pending_questions', 'ready', 'assigned', 'in_progress', 'in_review', 'approved')
    ),
    UNIQUE (wisp_version_id, code),
    FOREIGN KEY (wisp_version_id) REFERENCES wisp_versions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    answer_type TEXT NOT NULL DEFAULT 'yes_no' CHECK (answer_type IN ('yes_no')),
    origin TEXT NOT NULL DEFAULT 'seeded' CHECK (origin IN ('seeded', 'admin')),
    enabled INTEGER NOT NULL DEFAULT 1,
    position INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL UNIQUE,
    contributor_id INTEGER NOT NULL,
    value TEXT CHECK (value IN ('yes', 'no')),
    skipped INTEGER NOT NULL DEFAULT 0,
    followups_state TEXT NOT NULL DEFAULT 'pending' CHECK (followups_state IN ('pending', 'complete', 'waived')),
    answered_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    FOREIGN KEY (contributor_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    response_text TEXT,
    position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 3),
    FOREIGN KEY (answer_id) REFERENCES answers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS compiled_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL UNIQUE,
    narrative_text TEXT NOT NULL,
    compiled_at TEXT NOT NULL DEFAULT (datetime('now')),
    revised_by_reviewer_id INTEGER,
    approved_at TEXT,
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
    FOREIGN KEY (revised_by_reviewer_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS domain_assignments (
    domain_id INTEGER PRIMARY KEY,
    contributor_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
    FOREIGN KEY (contributor_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    channel TEXT NOT NULL DEFAULT 'both' CHECK (channel IN ('in_app', 'email', 'both')),
    read_at TEXT,
    sent_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    event_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}',
    at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_domains_version_id ON domains(wisp_version_id);
CREATE INDEX IF NOT EXISTS idx_questions_domain_id ON questions(domain_id);
CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);
CREATE INDEX IF NOT EXISTS idx_followups_answer_id ON followups(answer_id);
CREATE INDEX IF NOT EXISTS idx_compiled_answers_domain_id ON compiled_answers(domain_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor ON audit_events(actor_user_id);
