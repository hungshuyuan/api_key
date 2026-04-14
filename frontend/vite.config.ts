import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
server: {
    host: '0.0.0.0',       // 強制對外開放！
    allowedHosts: [
      '163.18.26.144.nip.io' // 允許你的偽裝網域
    ]
  }
})
