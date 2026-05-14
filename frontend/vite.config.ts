import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * 浏览器地址栏直接访问 / 刷新时，请求头 Accept 包含 text/html，
 * 这类"文档导航"请求应交给 Vite 返回 index.html 以激活 SPA 路由，
 * 而不是被代理到后端（后端对 /admin、/profile 这类路径本身并没有 HTML 响应）。
 */
const bypassHtmlNav = (req: any) => {
  if (req.method === 'GET' && (req.headers.accept ?? '').includes('text/html')) {
    return req.url
  }
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3002,
    proxy: {
      '/api':     { target: 'http://localhost:8080', changeOrigin: true },
      '/auth':    { target: 'http://localhost:8080', changeOrigin: true },
      '/admin':   { target: 'http://localhost:8080', changeOrigin: true, bypass: bypassHtmlNav },
      '/profile': { target: 'http://localhost:8080', changeOrigin: true, bypass: bypassHtmlNav },
    },
  },
  build: {
    outDir: 'dist',
  },
})
