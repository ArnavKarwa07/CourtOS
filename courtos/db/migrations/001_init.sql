-- Create telemetry_events table
CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id       TEXT        PRIMARY KEY,
    event_type     TEXT        NOT NULL,
    timestamp      TIMESTAMP   NOT NULL,
    source         TEXT        NOT NULL,
    payload        JSON        NOT NULL,
    received_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_event_type CHECK (
        event_type IN ('kinematic', 'game_state', 'network', 'review')
    )
);

CREATE INDEX IF NOT EXISTS idx_events_received ON telemetry_events (received_at ASC);
CREATE INDEX IF NOT EXISTS idx_events_type ON telemetry_events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_type_received ON telemetry_events (event_type, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_source ON telemetry_events (source);

-- Create incidents table
CREATE TABLE IF NOT EXISTS incidents (
    incident_id      TEXT        PRIMARY KEY,
    severity         TEXT        NOT NULL,
    category         TEXT        NOT NULL,
    message          TEXT        NOT NULL,
    created_at       TIMESTAMP   NOT NULL,
    source_event_id  TEXT        NOT NULL,
    status           TEXT        NOT NULL DEFAULT 'active',
    resolved_at      TIMESTAMP,
    FOREIGN KEY (source_event_id) REFERENCES telemetry_events (event_id),
    CONSTRAINT chk_severity CHECK (
        severity IN ('info', 'warning', 'critical')
    ),
    CONSTRAINT chk_status CHECK (
        status IN ('active', 'resolved')
    ),
    CONSTRAINT chk_resolved_consistency CHECK (
        (status = 'active'   AND resolved_at IS NULL) OR
        (status = 'resolved' AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
CREATE INDEX IF NOT EXISTS idx_incidents_source_event ON incidents (source_event_id);

-- Create state_snapshots table
CREATE TABLE IF NOT EXISTS state_snapshots (
    snapshot_id       TEXT        PRIMARY KEY,
    state             JSON        NOT NULL,
    trigger_event_id  TEXT,
    created_at        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_event_id) REFERENCES telemetry_events (event_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_latest ON state_snapshots (created_at DESC);

-- Create audit_log table
CREATE TABLE IF NOT EXISTS audit_log (
    log_id           TEXT        PRIMARY KEY,
    action           TEXT        NOT NULL,
    actor            TEXT        NOT NULL DEFAULT 'system',
    details          JSON        NOT NULL,
    source_event_id  TEXT,
    request_id       TEXT,
    created_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_action CHECK (
        action IN (
            'event_ingested',
            'incident_created',
            'incident_resolved',
            'overlay_state_change',
            'network_recalculated',
            'state_snapshot_created',
            'simulation_started',
            'simulation_stopped'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action, created_at DESC);
