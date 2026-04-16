# NKUST API Key 申請系統

高科大學生透過 Google 帳號登入，向 LiteLLM 服務申請 API Key，用於呼叫 AI 模型。

---

## 系統架構

```
使用者瀏覽器
    │
    ▼
Frontend (React + Vite)  https://nkustapikey.54ucl.com
    │  JWT
    ▼
Backend (FastAPI)         https://nkustapikey.54ucl.com/api/...
    │  LITELLM_MANAGE_KEY
    ▼
LiteLLM API               https://b225.54ucl.com/aiservice
    │
    ▼
AI 模型推論服務
```

---

## 環境需求

- Python 3.10+
- Node.js 18+
- SQLite（內建，無需額外安裝）

---

## 安裝與啟動

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

設定 `.env`（複製下方範本）：

```env
GOOGLE_CLIENT_ID=你的 Google OAuth Client ID
JWT_SECRET=自訂一串亂碼密鑰

LITELLM_API_BASE=https://b225.54ucl.com/aiservice
LITELLM_MANAGE_KEY=sk-管理員key

# 產生方式：python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=產生的Fernet金鑰

# 新用戶預設設定
NEW_USER_MAX_BUDGET=100
NEW_USER_ROLE=internal_user
NEW_USER_BUDGET_DURATION=7d
```

啟動：

```bash
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### Frontend

```bash
cd frontend
npm install
```

設定 `.env`：

```env
VITE_GOOGLE_CLIENT_ID=你的 Google OAuth Client ID
VITE_API_BASE_URL=http://localhost:8000
```

啟動：

```bash
npm run dev
```

---

## API 端點總覽

| 方法 | 路徑 | 說明 | 需要 JWT |
|------|------|------|---------|
| POST | `/api/auth/google` | Google 登入，回傳 JWT | ✗ |
| GET | `/api/keys` | 取得 Key 列表與用量 | ✓ |
| POST | `/api/keys/generate` | 申請新 API Key | ✓ |
| GET | `/api/keys/{id}/reveal` | 查看完整 Raw Key | ✓ |
| DELETE | `/api/keys/{id}` | 註銷 Key | ✓ |

---

## 完整操作流程

### 1. 使用者登入

前端透過 Google OAuth 取得 credential，發送給 backend 驗證：

```bash
# 自動由前端處理，手動測試範例：
curl -X POST https://nkustapikey.54ucl.com/api/auth/google \
  -H "Content-Type: application/json" \
  -d '{"token": "Google_credential_token"}'
```

Response：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "student_id": "C112118111"
}
```

---

### 2. 申請 API Key

```bash
curl -X POST https://nkustapikey.54ucl.com/api/keys/generate \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response：
```json
{
  "message": "申請成功",
  "key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
}
```

> ⚠️ **此為唯一一次顯示完整 Key 的機會，請立即複製保存。**

---

### 3. 查看 Key 列表與用量

```bash
curl https://nkustapikey.54ucl.com/api/keys \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

Response：
```json
[
  {
    "id": 1,
    "key_name": "sk-...D_7g",
    "key_alias": "C112118111_1744800000",
    "spend": 0.00123,
    "user_total_spend": 0.00123,
    "max_budget": 100.0,
    "budget_duration": "7d",
    "budget_reset_at": "2026-04-20T00:00:00Z"
  }
]
```

---

### 4. 查看完整 Raw Key

```bash
curl https://nkustapikey.54ucl.com/api/keys/1/reveal \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

Response：
```json
{
  "raw_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
}
```

---

### 5. 使用 API Key 呼叫 AI 模型

**查看可用模型：**

```bash
curl https://b225.54ucl.com/aiservice/v1/models \
  -H "Authorization: Bearer sk-你的raw_key"
```

**呼叫模型（curl）：**

```bash
curl -X POST https://b225.54ucl.com/aiservice/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-你的raw_key" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

**呼叫模型（Python OpenAI SDK）：**

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-你的raw_key",
    base_url="https://b225.54ucl.com/aiservice/v1"
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "你好"}]
)

print(response.choices[0].message.content)
```

---

### 6. 註銷 Key

```bash
curl -X DELETE https://nkustapikey.54ucl.com/api/keys/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

Response：
```json
{
  "message": "註銷成功"
}
```

---

## 管理員操作（curl）

**查詢指定用戶資料：**

```bash
curl "https://b225.54ucl.com/aiservice/user/info?user_id=C112118111" \
  -H "Authorization: Bearer sk-管理員key"
```

**刪除用戶（測試用）：**

```bash
curl -X POST https://b225.54ucl.com/aiservice/user/delete \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-管理員key" \
  -d '{"user_ids": ["C112118111"]}'
```

**清除本地 DB 紀錄（測試用）：**

```bash
cd backend
sqlite3 keys.db "DELETE FROM api_keys WHERE student_id = 'C112118111';"
```

---

## 注意事項

- 僅限 `@nkust.edu.tw` 信箱登入
- 每位用戶預算上限 `NEW_USER_MAX_BUDGET`，每 `NEW_USER_BUDGET_DURATION` 重置一次
- `ENCRYPTION_KEY` 設定後不可更換，換掉將導致所有已存 Key 無法解密
- JWT 有效期 2 小時，過期需重新登入
