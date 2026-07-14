import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
      },
      '/openapi.json': {
        target: 'http://localhost:8000',
      },
    },
  },
  test: {
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
