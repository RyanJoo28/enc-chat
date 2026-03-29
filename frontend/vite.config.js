import {fileURLToPath, URL} from 'node:url'
import {createLogger, defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'fs'
import path from 'path'

// 本地开发时优先复用项目根目录下的 TLS 证书。
const certPath = path.resolve(__dirname, '../certs/cert.pem')
const keyPath = path.resolve(__dirname, '../certs/key.pem')

const resolveDevProxyTarget = (hostHeader = '', scheme = 'http') => {
    const configuredTarget = process.env.VITE_DEV_PROXY_TARGET
    if (configuredTarget) {
        return configuredTarget
    }

    const rawHost = String(hostHeader || '').trim()
    if (!rawHost) {
        return `${scheme}://127.0.0.1:8000`
    }

    if (rawHost.startsWith('[')) {
        const closingBracketIndex = rawHost.indexOf(']')
        const hostname = closingBracketIndex >= 0 ? rawHost.slice(0, closingBracketIndex + 1) : '[::1]'
        return `${scheme}://${hostname}:8000`
    }

    const hostname = rawHost.split(':')[0] || '127.0.0.1'
    return `${scheme}://${hostname}:8000`
}

const baseLogger = createLogger()

const shouldIgnoreDevWsProxyError = (message = '') => {
    const normalizedMessage = String(message)
    const isWsProxyLog = normalizedMessage.includes('ws proxy error') || normalizedMessage.includes('ws proxy socket error')
    if (!isWsProxyLog) {
        return false
    }

    return normalizedMessage.includes('ECONNRESET')
        || normalizedMessage.includes('This socket has been ended by the other party')
        || normalizedMessage.includes('writeAfterFIN')
}

const customLogger = {
    ...baseLogger,
    error(message, options) {
        if (shouldIgnoreDevWsProxyError(message)) {
            return
        }
        baseLogger.error(message, options)
    }
}

export default defineConfig(({ command }) => {
    const isDevServer = command === 'serve'
    const hasLocalCerts = fs.existsSync(keyPath) && fs.existsSync(certPath)
    const devProxyScheme = process.env.VITE_DEV_PROXY_SCHEME || (hasLocalCerts ? 'https' : 'http')

    return {
        plugins: [
            vue(),
        ],
        customLogger,
        resolve: {
            alias: {
                '@': fileURLToPath(new URL('./src', import.meta.url))
            }
        },
        server: {
            ...(isDevServer && hasLocalCerts ? {
                https: {
                    key: fs.readFileSync(keyPath),
                    cert: fs.readFileSync(certPath),
                }
            } : {}),
            host: '0.0.0.0',
            port: 3000,
            strictPort: false,
            ...(isDevServer ? {
                proxy: {
                    '/api': {
                        target: `${devProxyScheme}://127.0.0.1:8000`,
                        changeOrigin: true,
                        secure: false,
                        ws: true,
                        router: (req) => resolveDevProxyTarget(req.headers.host, devProxyScheme),
                    }
                }
            } : {})
        }
    }
})
