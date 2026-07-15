import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: process.env.DOCKER_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        headers: process.env.DOCKER_API_URL ? { Host: 'demo.localhost' } : undefined,
      },
      '/openapi.json': {
        target: process.env.DOCKER_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        headers: process.env.DOCKER_API_URL ? { Host: 'demo.localhost' } : undefined,
      },
    },
  },
  test: {
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
