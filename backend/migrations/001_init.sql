-- AI assets: the "registered" AI applications/agents being governed
CREATE TABLE ai_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    declared_data_sources TEXT[] NOT NULL DEFAULT '{}',
    monitoring_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    retention_days INT NOT NULL DEFAULT 90,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sanitized prompts (raw prompt text is NEVER stored — only the redacted version)
CREATE TABLE prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES ai_assets(id),
    sanitized_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- PII detection metadata, one row per detected entity per prompt
CREATE TABLE pii_detections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id UUID NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,   -- e.g. NAME, PHONE, EMAIL
    count INT NOT NULL DEFAULT 1
);

-- Agent execution runs
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES ai_assets(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',  -- running | success | failed
    model TEXT,
    input_tokens INT,
    output_tokens INT
);

-- Every data source / tool actually touched during a run
CREATE TABLE run_data_access_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,   -- e.g. "FAQ Database", "Orders Database"
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_prompts_asset_id ON prompts(asset_id);
CREATE INDEX idx_pii_detections_prompt_id ON pii_detections(prompt_id);
CREATE INDEX idx_runs_asset_id ON agent_runs(asset_id);
CREATE INDEX idx_access_events_run_id ON run_data_access_events(run_id);
