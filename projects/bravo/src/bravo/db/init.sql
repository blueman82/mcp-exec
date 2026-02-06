-- Bravo database schema
-- PostgreSQL 16

-- Watched tickets table
CREATE TABLE IF NOT EXISTS watched_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_key VARCHAR(50) NOT NULL UNIQUE,
    jira_id VARCHAR(50) NOT NULL,
    project VARCHAR(20) NOT NULL,
    summary TEXT,
    assignee_jira_id VARCHAR(100),
    assignee_name VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'ACQUIRED',
    jira_status VARCHAR(100),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_polled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_assignee_comment_at TIMESTAMPTZ,
    snoozed_until TIMESTAMPTZ,
    g1_passed BOOLEAN,
    g2_passed BOOLEAN,
    g3_passed BOOLEAN,
    g4_passed BOOLEAN,
    llm_clarity NUMERIC(3,2),
    llm_completeness NUMERIC(3,2),
    llm_root_cause NUMERIC(3,2),
    llm_actionability NUMERIC(3,2),
    llm_average NUMERIC(3,2),
    llm_scored_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('ACQUIRED', 'ACTIVE', 'SNOOZED', 'RESOLVED'))
);

CREATE INDEX IF NOT EXISTS idx_watched_tickets_status ON watched_tickets(status);
CREATE INDEX IF NOT EXISTS idx_watched_tickets_assignee ON watched_tickets(assignee_jira_id);
CREATE INDEX IF NOT EXISTS idx_watched_tickets_project ON watched_tickets(project);
CREATE INDEX IF NOT EXISTS idx_watched_tickets_last_polled ON watched_tickets(last_polled_at);

-- Nudge events table
CREATE TABLE IF NOT EXISTS nudge_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_key VARCHAR(50) NOT NULL REFERENCES watched_tickets(ticket_key) ON DELETE CASCADE,
    assignee_jira_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'SENT',
    trigger_reason TEXT,
    slack_channel VARCHAR(100),
    slack_ts VARCHAR(50),
    message_content TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    jira_comment_posted TEXT,
    posted_at TIMESTAMPTZ,
    snoozed_until TIMESTAMPTZ,

    CONSTRAINT valid_nudge_status CHECK (status IN ('SENT', 'ACKNOWLEDGED', 'SNOOZED', 'RESPONDED', 'POSTED', 'CANCELLED'))
);

CREATE INDEX IF NOT EXISTS idx_nudge_events_ticket ON nudge_events(ticket_key);
CREATE INDEX IF NOT EXISTS idx_nudge_events_assignee ON nudge_events(assignee_jira_id);
CREATE INDEX IF NOT EXISTS idx_nudge_events_status ON nudge_events(status);
CREATE INDEX IF NOT EXISTS idx_nudge_events_created ON nudge_events(created_at);

-- Watched assignees table
CREATE TABLE IF NOT EXISTS watched_assignees (
    jira_id VARCHAR(100) PRIMARY KEY,
    jira_display_name VARCHAR(255),
    slack_user_id VARCHAR(50),
    email VARCHAR(255),
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    default_snooze_minutes INTEGER DEFAULT 240,
    timezone VARCHAR(50) DEFAULT 'Europe/London',
    nudge_count INTEGER DEFAULT 0,
    last_nudge_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watched_assignees_slack ON watched_assignees(slack_user_id);

-- Project configs table
CREATE TABLE IF NOT EXISTS project_configs (
    project_key VARCHAR(20) PRIMARY KEY,
    display_name VARCHAR(100),
    enabled BOOLEAN DEFAULT TRUE,
    custom_gates JSONB,
    custom_llm_threshold NUMERIC(3,2),
    jql_filter TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Polling state table
CREATE TABLE IF NOT EXISTS polling_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_cursor TIMESTAMPTZ,
    last_poll_at TIMESTAMPTZ,
    tickets_fetched INTEGER DEFAULT 0,
    next_poll_at TIMESTAMPTZ,

    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO polling_state (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Poll history table
CREATE TABLE IF NOT EXISTS poll_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    tickets_fetched INTEGER DEFAULT 0,
    tickets_new INTEGER DEFAULT 0,
    tickets_updated INTEGER DEFAULT 0,
    nudges_triggered INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running',
    error_message TEXT,

    CONSTRAINT valid_poll_status CHECK (status IN ('running', 'completed', 'failed', 'partial'))
);

CREATE INDEX IF NOT EXISTS idx_poll_history_started ON poll_history(started_at DESC);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
DROP TRIGGER IF EXISTS update_watched_tickets_updated_at ON watched_tickets;
CREATE TRIGGER update_watched_tickets_updated_at
    BEFORE UPDATE ON watched_tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_watched_assignees_updated_at ON watched_assignees;
CREATE TRIGGER update_watched_assignees_updated_at
    BEFORE UPDATE ON watched_assignees
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_project_configs_updated_at ON project_configs;
CREATE TRIGGER update_project_configs_updated_at
    BEFORE UPDATE ON project_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
