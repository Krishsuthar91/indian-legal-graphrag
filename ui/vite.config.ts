/// <reference types="vitest" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // The backend port must match the port uvicorn actually binds. Historically
  // this was hardcoded to 8000 while the dev command was started with
  // `--port 8080`, which produced `http proxy error: /api/v1/query` +
  // AggregateError [ECONNREFUSED] because nothing listened on 8000.
  // Override with VITE_BACKEND_TARGET (e.g. http://127.0.0.1:8080) in ui/.env.
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            react: ['react', 'react-dom', 'react-router-dom'],
            query: ['@tanstack/react-query'],
            flow: ['@xyflow/react'],
            cytoscape: ['cytoscape'],
            charts: ['recharts'],
            motion: ['framer-motion'],
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  }
})