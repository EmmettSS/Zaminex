import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'


function ZaminexAssetResolver() {
  return {
    name: 'Zaminex-asset-resolver',
    resolveId(id) {
      if (id.startsWith('Zaminex:asset/')) {
        const filename = id.replace('Zaminex:asset/', '')
        return path.resolve(__dirname, 'src/assets', filename)
      }
    },
  }
}

export default defineConfig({
  plugins: [
    ZaminexAssetResolver(),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  base: '/static/frontend/',

  build: {
    outDir: path.resolve(__dirname, '../ZaminexB/static/frontend'),

    emptyOutDir: true,

    manifest: true,

    rollupOptions: {
      input: path.resolve(__dirname, 'src/main.tsx'),
    },
  },

  assetsInclude: ['**/*.svg', '**/*.csv'],
})
