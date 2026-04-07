-- infrastructure/db/init.sql
-- KÉT SẮT LƯU TRỮ LỊCH SỬ XỔ SỐ (DRAW HISTORY)

CREATE TABLE IF NOT EXISTS draw_history (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,            -- Nguồn: 'Vietlott Mega 6/45', 'Minh Ngọc'
    draw_code VARCHAR(50),                    -- Mã kỳ quay (nếu cào được)
    winning_numbers INTEGER[] NOT NULL,       -- Mảng chứa các con số chiến thắng
    confidence_score DECIMAL(5,2),            -- Độ tin cậy lúc cào dữ liệu
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tạo Index để AI sau này truy xuất lịch sử siêu tốc
CREATE INDEX idx_provider_time ON draw_history(provider, created_at DESC);
