# core-backend/Dockerfile
FROM python:3.11-slim-bookworm

# Cài curl để Docker healthcheck hoạt động
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements trước để layer cache hoạt động hiệu quả
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt trình duyệt tàng hình cho đặc vụ Scout
RUN playwright install --with-deps chromium

# Copy toàn bộ source
COPY . .

# Tạo thư mục shared cho QA Sniper screenshots
RUN mkdir -p /tmp/qa_screenshots /app/shared_data

EXPOSE 8000

# --reload để dev mode tự hot-reload khi code thay đổi
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
