import { createLogger, defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8002'
  const wsTarget = env.VITE_DEV_WS_TARGET || proxyTarget.replace(/^http/, 'ws')
  const baseLogger = createLogger()

  const withTimestamp = (msg: string): string => {
    return `[${new Date().toISOString()}] ${msg}`
  }

  const logger = {
    ...baseLogger,
    info(msg: string, options?: { clear?: boolean; timestamp?: boolean }) {
      baseLogger.info(withTimestamp(msg), options)
    },
    warn(msg: string, options?: { clear?: boolean; timestamp?: boolean }) {
      baseLogger.warn(withTimestamp(msg), options)
    },
    warnOnce(msg: string, options?: { clear?: boolean; timestamp?: boolean }) {
      baseLogger.warnOnce(withTimestamp(msg), options)
    },
    error(msg: string, options?: { error?: Error | null }) {
      baseLogger.error(withTimestamp(msg), options)
    },
  }

  return {
    plugins: [react()],
    customLogger: logger,
    server: {
      port: 3003,
      host: true,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              logger.error(`[proxy] error: ${err.message}`, { error: err })
            })
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              logger.info(`[proxy] ${req.method} ${req.url} -> ${proxyReq.path}`)
            })
          },
        },
        '/ws': {
          target: wsTarget,
          ws: true,
          changeOrigin: true,
        },
      },
    },
    preview: {
      host: true,
      allowedHosts: true,
    },
  }
})
