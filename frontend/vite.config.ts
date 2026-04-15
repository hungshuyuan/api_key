import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(),basicSsl()],
server: {
    host: '0.0.0.0',         // 強制對外開放！
    allowedHosts: [
      '163.18.26.144.nip.io' // 允許你的偽裝網域
    ],
    // 👇 這是為了解決 Mixed Content 必須加上的 Proxy 轉發設定
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // 將前端 /api 的請求，轉發給本機跑在 8000 port 的 FastAPI
        changeOrigin: true,
      }
    }
  }
})
