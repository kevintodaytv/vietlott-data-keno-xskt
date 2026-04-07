# nexus-frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
# Ép cài đặt bỏ qua xung đột phiên bản của Three.js và Threlte
RUN npm install --legacy-peer-deps

COPY . .

EXPOSE 3000

# Đảm bảo Vite mở cửa ra toàn thế giới (0.0.0.0) thay vì trói ở localhost nội bộ
CMD ["npx", "vite", "dev", "--host", "0.0.0.0", "--port", "3000"]
