import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: react(),
  
  // 核心修正：指定生產環境與開發環境的基準子路徑 (Base Path)
  // 這會強制將打包後的 HTML 資源引用路徑修正為 /apply/assets/index-xxx.css
  base: '/apply/',

  server: {
    host: '0.0.0.0',         // 允許外網監聽
    
    // 安全策略：將新的正式網域加入白名單，避免開發模式下噴出 Invalid Host header
    allowedHosts: [
      'nkustapikey.54ucl.com',
      'www.iai.nkust.edu.tw',
      'iai.nkust.edu.tw'
    ],
    
    // 💡 架構提醒：此處的 proxy 僅在「執行 npm run dev (開發模式)」時生效！
    // 當前台打包成靜態檔案並放入 Nginx (8081) 部署後，此處的 proxy 設定將完全失效，
    // 屆時生產環境的 API 轉發必須完全依賴 Nginx 的 `location /iaibackend/` 配置。
    proxy: {
      // 為了與你生產環境的 Nginx 路由路徑保持一致，建議前端代碼統一呼叫 '/iaibackend/api/...'
      '/iaibackend': {
        // 開發環境下，直接轉發給跑在本機 8000 埠口的 FastAPI 後端
        target: 'http://127.0.0.1:8000', 
        changeOrigin: true,
        // 如果後端 FastAPI 的路由定義中沒有 /iaibackend 前綴（例如直接是 /api/courses/keys），則需要重寫路徑：
        rewrite: (path) => path.replace(/^\/iaibackend/, '')
      }
    }
  }
})