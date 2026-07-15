import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.DOCKER_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            proxyReq.setHeader('Host', req.headers.host || 'demo.localhost');
          });
        },
      },
      '/openapi.json': {
        target: process.env.DOCKER_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            proxyReq.setHeader('Host', req.headers.host || 'demo.localhost');
          });
        },
      },
    },
  },
  test: {
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
