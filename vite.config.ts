/// <reference types="vitest/config" />
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Dev-server mock of the QueryService `ask` endpoint (`ASK_PATH` in src/ai/askClient.ts) until
 * the real service exists (issue #14). MOCK_ASK=ok (default) | unavailable | slow | off.
 * `vite preview` and the production image have no mock, so there the App falls back (REQ-39).
 */
function mockAskPlugin(): Plugin {
  return {
    name: 'mock-ask',
    apply: 'serve',
    configureServer(server) {
      const mode = process.env.MOCK_ASK ?? 'ok'
      if (mode === 'off') return
      server.middlewares.use('/api/ask', (req, res, next) => {
        server
          .ssrLoadModule('/src/ai/mockAskService.ts')
          .then((m) =>
            (m as typeof import('./src/ai/mockAskService')).handleMockAsk(req, res, mode),
          )
          .catch(next)
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), mockAskPlugin()],
  // Bundle every browser dependency in one pass when the dev server starts. When some were found
  // late, a second pass sometimes put a second copy of React inside react-dom/client
  // ("Invalid hook call", blank page).
  optimizeDeps: {
    include: [
      'react',
      'react/jsx-runtime',
      'react/jsx-dev-runtime',
      'react-dom',
      'react-dom/client',
      'maplibre-gl',
    ],
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}', 'src/**/*.test.{ts,tsx}'],
  },
})
