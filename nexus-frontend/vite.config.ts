import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    host: '0.0.0.0',
    port: 3333,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://core_api:8000',
        changeOrigin: true,
      },
    },
    watch: {
      usePolling: true
    }
  },
});
