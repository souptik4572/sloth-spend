import { fileURLToPath } from 'url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const here = (p: string): string => fileURLToPath(new URL(p, import.meta.url))

// SlothSpend Web (WEB-IMPL W2): the browser app. In dev, /api goes to `npm run web:api` (python -m app.web);
// in production the same server serves web/dist, so the app and its API share one origin.
export default defineConfig({
  root: here('.'),
  resolve: {
    alias: {
      '@renderer': here('../src/renderer/src'),
      '@web': here('./src')
    }
  },
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true, // SLOTH_PUBLIC_URL (email links, the CSRF origin check) names this port
    proxy: { '/api': { target: process.env.SLOTH_WEB_API ?? 'http://127.0.0.1:8770' } }
  },
  build: { outDir: here('./dist'), emptyOutDir: true, sourcemap: true }
})
