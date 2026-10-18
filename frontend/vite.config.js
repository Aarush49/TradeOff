import { defineConfig } from 'vite';

export default defineConfig({
  base: '/ui/',
  build: {
    outDir: '../static/ui',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8501',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('origin', 'http://127.0.0.1:8501');
          });
        },
      },
    },
  },
});
