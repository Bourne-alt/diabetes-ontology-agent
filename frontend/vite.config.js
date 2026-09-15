import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 开发期：Vite 起在 5173，把 Agent 的 SSE 端点代理到 Python 服务（默认 8200）。
// 构建期：产物进 dist/，由 FastAPI 在 / 直接托管，不需要再有 Node 进程。
const AGENT_ORIGIN = process.env.AGENT_ORIGIN ?? 'http://127.0.0.1:8200';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/demo': { target: AGENT_ORIGIN, changeOrigin: true },
      '/patients': { target: AGENT_ORIGIN, changeOrigin: true },
      '/chat': {
        target: AGENT_ORIGIN,
        changeOrigin: true,
        // SSE 必须关掉代理层缓冲，否则事件会攒到流结束才一次性吐出来。
        configure(proxy) {
          proxy.on('proxyRes', (proxyRes) => {
            delete proxyRes.headers['content-encoding'];
          });
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
