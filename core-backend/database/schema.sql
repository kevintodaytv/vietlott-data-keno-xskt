-- ══════════════════════════════════════════════════════════════════
--   SUPABASE SCHEMA — Sniper-X Hub / XSKT
--   Chạy file này trong Supabase SQL Editor hoặc migration tool
--   URL: https://supabase.com/dashboard → SQL Editor
-- ══════════════════════════════════════════════════════════════════

-- Enable UUID extension (thường đã có sẵn trên Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── BẢNG 1: Kết quả xổ số thực tế ──────────────────────────────
CREATE TABLE IF NOT EXISTS lottery_results (
    id              UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Kết quả thực tế scraped từ web
    numbers         INTEGER[]   NOT NULL,               -- VD: [2, 9, 23, 30, 32, 42]
    provider        TEXT        NOT NULL,               -- 'Minh Ngoc', 'VIETLOTT', v.v
    draw_type       TEXT        NOT NULL DEFAULT 'mega6x45',  -- 'mega6x45', 'power655', 'keno'
    draw_date       DATE        DEFAULT CURRENT_DATE,
    
    -- AI Output
    ai_prediction   INTEGER[]   DEFAULT '{}',          -- Dự đoán AI trước kết quả
    confidence      FLOAT8      DEFAULT 0.0,           -- Độ tin cậy 0-100
    
    -- Meta
    scrape_url      TEXT,
    scrape_duration_ms INTEGER
);

-- Index cho query performance
CREATE INDEX IF NOT EXISTS idx_lottery_results_draw_type ON lottery_results(draw_type);
CREATE INDEX IF NOT EXISTS idx_lottery_results_created_at ON lottery_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lottery_results_draw_date ON lottery_results(draw_date DESC);

-- ── BẢNG 2: AI Training Metrics ──────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_training_metrics (
    id          UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    model_name  TEXT        NOT NULL,   -- 'alien_brain_v1', 'sentinel_v2', v.v
    epoch       INTEGER     NOT NULL,
    accuracy    FLOAT8,
    loss        FLOAT8,
    val_accuracy FLOAT8,
    val_loss    FLOAT8,
    metadata    JSONB       DEFAULT '{}'  -- Extra hyperparams, training config
);

CREATE INDEX IF NOT EXISTS idx_ai_metrics_model ON ai_training_metrics(model_name);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_created ON ai_training_metrics(created_at DESC);

-- ── BẢNG 3: Số thống kê tần suất ──────────────────────────────────
CREATE TABLE IF NOT EXISTS number_frequency (
    id          UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    updated_at  TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    draw_type   TEXT        NOT NULL,
    number      INTEGER     NOT NULL,       -- Số 1-45 (hoặc 1-55 tùy game)
    frequency   INTEGER     DEFAULT 0,      -- Số lần xuất hiện
    last_seen   DATE,                       -- Lần cuối xuất hiện
    hot_score   FLOAT8      DEFAULT 0.0,    -- Score tổng hợp (AI tính)
    
    UNIQUE (draw_type, number)
);

CREATE INDEX IF NOT EXISTS idx_freq_draw_type ON number_frequency(draw_type);

-- ── BẢNG 4: Prediction Sessions ────────────────────────────────
CREATE TABLE IF NOT EXISTS prediction_sessions (
    id              UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    session_token   TEXT        UNIQUE,     -- Identifier cho mỗi phiên dự đoán
    draw_type       TEXT        NOT NULL,
    predicted_numbers INTEGER[] NOT NULL,
    confidence      FLOAT8,
    model_version   TEXT,
    
    -- Kết quả so sánh (sau khi có kết quả thật)
    actual_numbers  INTEGER[],              -- null cho đến khi có kết quả
    matches_count   INTEGER,               -- Số con đúng
    is_jackpot      BOOLEAN     DEFAULT FALSE,
    evaluation_at   TIMESTAMPTZ
);

-- ── ROW LEVEL SECURITY (RLS) ────────────────────────────────────
-- Bật RLS để bảo vệ data
ALTER TABLE lottery_results        ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_training_metrics    ENABLE ROW LEVEL SECURITY;
ALTER TABLE number_frequency       ENABLE ROW LEVEL SECURITY;
ALTER TABLE prediction_sessions    ENABLE ROW LEVEL SECURITY;

-- Policy: Cho phép đọc public (anon key)
CREATE POLICY "Allow public read on lottery_results"
    ON lottery_results FOR SELECT USING (true);

CREATE POLICY "Allow public read on number_frequency"
    ON number_frequency FOR SELECT USING (true);

CREATE POLICY "Allow public read on prediction_sessions"
    ON prediction_sessions FOR SELECT USING (true);

-- Policy: Chỉ service_role được write
CREATE POLICY "Allow service write on lottery_results"
    ON lottery_results FOR INSERT
    WITH CHECK (auth.role() = 'service_role' OR auth.role() = 'anon');

CREATE POLICY "Allow service write on ai_training_metrics"
    ON ai_training_metrics FOR ALL
    WITH CHECK (auth.role() = 'service_role' OR auth.role() = 'anon');

CREATE POLICY "Allow service write on number_frequency"
    ON number_frequency FOR ALL
    WITH CHECK (auth.role() = 'service_role' OR auth.role() = 'anon');

CREATE POLICY "Allow service write on prediction_sessions"
    ON prediction_sessions FOR ALL
    WITH CHECK (auth.role() = 'service_role' OR auth.role() = 'anon');

-- ── REALTIME: Enable cho bảng lottery_results ──────────────────
-- Cho phép subscribe realtime events
ALTER PUBLICATION supabase_realtime ADD TABLE lottery_results;
ALTER PUBLICATION supabase_realtime ADD TABLE prediction_sessions;

-- ── VIEW: Thống kê nhanh ────────────────────────────────────────
CREATE OR REPLACE VIEW latest_predictions AS
SELECT
    ps.id,
    ps.created_at,
    ps.draw_type,
    ps.predicted_numbers,
    ps.confidence,
    ps.model_version,
    lr.numbers AS actual_numbers,
    ps.matches_count,
    ps.is_jackpot
FROM prediction_sessions ps
LEFT JOIN lottery_results lr ON lr.draw_date = ps.created_at::date AND lr.draw_type = ps.draw_type
ORDER BY ps.created_at DESC
LIMIT 50;

-- ── DONE ────────────────────────────────────────────────────────
-- Schema đã sẵn sàng. Tiếp theo:
-- 1. Lấy SUPABASE_URL và SUPABASE_ANON_KEY từ Dashboard → Settings → API
-- 2. Điền vào file .env
-- 3. pip install supabase
