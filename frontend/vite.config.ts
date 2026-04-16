import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: react(),
server: {
    allowedHosts:['nkustapikey.54ucl.com'],
    host: '0.0.0.0',         // 強制對外開放！
    // 👇 這是為了解決 Mixed Content 必須加上的 Proxy 轉發設定
    proxy: {
      '/api': {
        target: 'https://nkustapikey.54ucl.com', // 將前端 /api 的請求，轉發給本機跑在 8000 port 的 FastAPI
        changeOrigin: true,
      }
    }
  }
})
