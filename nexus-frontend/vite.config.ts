import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    host: '0.0.0.0',
    port: 3333,
    strictPort: true,

    // ─── FIX: Cho phép truy cập từ LAN (192.168.x.x)
    allowedHosts: ['all'],

    // ─── FIX: Proxy API + WebSocket qua backend port 8888
    proxy: {
      // REST API + WebSocket
      '/api': {
        target: 'http://127.0.0.1:8888',
        changeOrigin: true,
        secure: false,
        ws: true, // QUAN TRỌNG: Cho phép proxy WebSocket (ví dụ /api/ws/keno)
      },
      // WebSocket Keno — QUAN TRỌNG: ws:true bắt buộc!
      '/ws': {
        target: 'ws://127.0.0.1:8888',
        ws: true,
        changeOrigin: true,
        secure: false,
      },
      // WebSocket Vietlott
      '/stream': {
        target: 'ws://127.0.0.1:8888',
        ws: true,
        changeOrigin: true,
        secure: false,
      },
    },

    // ─── FIX: HMR ổn định trên Windows (không dùng native fs watcher)
    hmr: {
      host: '127.0.0.1',
      port: 3334,           // HMR port riêng, tránh xung đột WS proxy
      clientPort: 3334,
    },
    watch: {
      usePolling: true,     // Bắt buộc trên Windows để tránh HMR zombie
      interval: 800,
    },
  },

  // ─── FIX: Tăng timeout khi build (tránh crash khi máy yếu)
  build: {
    chunkSizeWarningLimit: 2000,
  },
});

