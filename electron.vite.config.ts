import { resolve } from 'path'
import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  main: {},
  // sandbox: true only accepts CommonJS preload scripts (out/preload/index.js).
  preload: {},
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src')
      }
    },
    plugins: [react(), tailwindcss()],
    // Pre-bundle up front: a dependency discovered mid-load triggers a reload that can leave
    // two copies of React in the dev renderer ("Invalid hook call").
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-dom/client',
        'react/jsx-runtime',
        'react/jsx-dev-runtime',
        'zustand',
        '@microsoft/fetch-event-source',
        'lucide-react',
        'react-markdown',
        'remark-gfm'
      ]
    }
  }
})
