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
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  // The built assets are served by Django under STATIC_URL ("static/"), inside
  // the "frontend" prefix. This must match where the output lands so that the
  // browser requests resolve to /static/frontend/...
  base: '/static/frontend/',

  build: {
    // Build directly into Django's static directory — no manual copy needed.
    outDir: path.resolve(__dirname, '../ZaminexB/static/frontend'),

    // Every build wipes the previous output so hashed files never accumulate.
    emptyOutDir: true,

    // Produce .vite/manifest.json: a map of logical entry → hashed file, which
    // Django reads (via the vite_asset template tag) to reference the built
    // JS/CSS automatically.
    manifest: true,

    rollupOptions: {
      // In the Django setup, base.html is the HTML entry (not index.html), so
      // the React entry point is src/main.tsx.
      input: path.resolve(__dirname, 'src/main.tsx'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
