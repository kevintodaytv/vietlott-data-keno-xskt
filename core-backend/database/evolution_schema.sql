-- ══════════════════════════════════════════════════════════════════
--   KENO_EVOLUTION_LOG — Autonomous Evolution Protocol Schema
--   Chạy trong Supabase SQL Editor
--   Bổ sung vào schema hiện tại (không xung đột)
-- ══════════════════════════════════════════════════════════════════

-- ── BẢNG 5: Lịch sử tiến hóa tư duy Orbis ────────────────────────
CREATE TABLE IF NOT EXISTS keno_evolution_log (
    id               SERIAL PRIMARY KEY,
    timestamp        TIMESTAMPTZ DEFAULT NOW(),
    phase            VARCHAR(20)  NOT NULL,      -- CRITIQUE / EVOLVE / DEPLOY / REJECT / DEEP_LEARNING / MORNING_BRIEF
    strategy_name    VARCHAR(100),
    confidence_score FLOAT,
    win_rate         FLOAT,
    lesson_learned   TEXT,                        -- Bài học rút ra (Gemini AI hoặc template)
    weights          JSONB        DEFAULT '{}',   -- Trọng số tại thời điểm critique
    draws_analyzed   INT          DEFAULT 0
);

-- Index để query nhanh
CREATE INDEX IF NOT EXISTS idx_evolution_log_timestamp   ON keno_evolution_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_evolution_log_phase       ON keno_evolution_log(phase);
CREATE INDEX IF NOT EXISTS idx_evolution_log_win_rate    ON keno_evolution_log(win_rate DESC);

-- ── BẢNG 6: Proactive Ping Log ────────────────────────────────────
CREATE TABLE IF NOT EXISTS orbis_proactive_log (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    ping_id     INT,
    ping_type   VARCHAR(50),                     -- ANOMALY / PNL_STREAK / NEW_STRATEGY / CONFIDENCE_RECORD / MORNING_BRIEF
    priority    VARCHAR(20),                     -- URGENT / HIGH / NORMAL
    message     TEXT,
    trigger     VARCHAR(100),
    payload     JSONB        DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_proactive_log_created_at ON orbis_proactive_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proactive_log_type       ON orbis_proactive_log(ping_type);
CREATE INDEX IF NOT EXISTS idx_proactive_log_priority   ON orbis_proactive_log(priority);

-- ── RLS Policies ────────────────────────────────────────────────────
ALTER TABLE keno_evolution_log   ENABLE ROW LEVEL SECURITY;
ALTER TABLE orbis_proactive_log  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read on keno_evolution_log"
    ON keno_evolution_log FOR SELECT USING (true);

CREATE POLICY "Allow service write on keno_evolution_log"
    ON keno_evolution_log FOR INSERT
    WITH CHECK (auth.role() = 'service_role' OR auth.role() = 'anon');

CREATE POLICY "Allow public read on orbis_proactive_log"
    ON orbis_proactive_log FOR SELECT USING (true);

CREATE POLICY "Allow service write on orbis_proactive_log"
    ON orbis_proactive_log FOR INSERT
    WITH CHECK (auth.role() = 'service_role' OR auth.role() = 'anon');

-- ── Realtime ─────────────────────────────────────────────────────────────────
ALTER PUBLICATION supabase_realtime ADD TABLE keno_evolution_log;
ALTER PUBLICATION supabase_realtime ADD TABLE orbis_proactive_log;

-- ── DONE ─────────────────────────────────────────────────────────────────────
-- Chạy trong Supabase SQL Editor:
-- Dashboard → SQL Editor → Paste file này → Run

-- ── BẢNG: Predictive Engine — User Behavior Logs ─────────────────────────────
CREATE TABLE IF NOT EXISTS user_behavior_logs (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL DEFAULT 'boss_001',
    action_type TEXT NOT NULL,   -- USER_LOGIN, OPEN_TAB, LEAVE_TAB, OPEN_SETTINGS, CLICK_PREDICT
    target_name TEXT NOT NULL,   -- Tab_KENO, Tab_MARKET_FLOW, APP, SETTINGS_PANEL
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_behavior_session ON user_behavior_logs (session_id, created_at DESC);

-- Extend user_personas với behavioral fields
ALTER TABLE user_personas
    ADD COLUMN IF NOT EXISTS favorite_tabs    TEXT[]  DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS active_hours     INT[]   DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS last_action      TEXT    DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS trading_style    TEXT    DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS daily_target_vnd BIGINT  DEFAULT 0;

-- Enable Realtime cho behavior logs
ALTER PUBLICATION supabase_realtime ADD TABLE user_behavior_logs;
