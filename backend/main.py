import os
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import jwt
import httpx  #發送 HTTP 請求API

import qrcode
import base64
from io import BytesIO

# 載入環境變數
load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-for-dev")
JWT_ALGORITHM = "HS256"

app = FastAPI(title="NKUST API Key Service")

# 設定 CORS (允許 Vite 預設 port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# --- 依賴注入 (Dependency)：驗證我們自己核發的 JWT ---
def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["student_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已過期，請重新登入")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無效的 Token")

# --- Request / Response Models ---
class GoogleAuthRequest(BaseModel):
    token: str

class AuthResponse(BaseModel):
    access_token: str
    student_id: str

# --- API Endpoints ---

@app.post("/api/auth/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest):
    try:
        # 1. 驗證 Google Token
        # Google 官方提供的驗證函式
        id_info = id_token.verify_oauth2_token(
            # request.token：ID Token；google_requests.Request()：Google Auth 套件用來發送 HTTP 請求的工具
            # GOOGLE_CLIENT_ID：.env內的字串；clock_skew_in_seconds=10：容錯 10秒誤差
            request.token, google_requests.Request(), GOOGLE_CLIENT_ID,clock_skew_in_seconds=10
        )
        
        email = id_info.get("email", "")
        
        # 2. 驗證是否為高科大信箱 (可依需求擴充其他網域)
        allowed_domains = ["nkust.edu.tw"]
        domain = email.split("@")[-1]
        
        if domain not in allowed_domains:
            raise HTTPException(status_code=403, detail="權限不足：限高科大 (NKUST) 學生帳號登入")
            
        # 3. 擷取學號 (切割 @ 前面的字串)
        # upper() 小寫轉大寫
        student_id = email.split("@")[0].upper()
        
        # 4. 簽發我們自己的 JWT 給前端使用
        # 自己做一張名牌（JWT）交給前端，讓前端以後拿著這張名牌來要資料，而不需要每次都重新登入 Google
        # 有效期限
        expire = datetime.utcnow() + timedelta(hours=2)
        # student_id：記錄這個 Token 是屬於哪個學號的。
        # exp (Expiration Time)：這是 JWT 的標準保留字，Token有效期限
        jwt_payload = {"student_id": student_id, "exp": expire}
        access_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return {"access_token": access_token, "student_id": student_id}
        
    except ValueError as e:
        print(f"🚨 Token 驗證失敗的真正原因: {e}")
        raise HTTPException(status_code=401, detail="無效的 Google Token")



@app.post("/api/apply-key")
async def apply_key(student_id: str = Depends(verify_jwt)):
    # 學長的 API 網址
    external_api_url = "https://b225.54ucl.com/capystar/auth/generate-key"
    
    # 準備要傳給學長 API 的資料 (JSON 格式)
    payload = {
        "student_id": student_id
    }
    
    # 使用 httpx 發送非同步請求
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                external_api_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # 檢查學長的 API 是否回傳成功 (狀態碼 200 系列)
            response.raise_for_status()
            
            # 取得學長 API 回傳的 JSON 資料
            data = response.json()
            
            # 直接將學長給的資料回傳給前端
            return data
            
        except httpx.HTTPStatusError as e:
            # 處理學長 API 回傳錯誤的情況 (例如 400 或 500 錯誤)
            print(f"🚨 學長 API 錯誤: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail="無法向系統申請金鑰，請稍後再試")
            
        except httpx.RequestError as e:
            # 處理連線失敗 (例如網路斷線、伺服器死機) 的情況
            print(f"🚨 連線錯誤: {e}")
            raise HTTPException(status_code=500, detail="與金鑰伺服器連線失敗")



# -----掃碼登入-----


# 模擬外部 DB 的操作 (你需要替換成實際呼叫外部 DB API 的 httpx 程式碼)
async def save_session_to_external_db(session_id: str):
    # TODO: 用 httpx.post 打外部 DB，告訴它建立一筆 session_id，狀態為 PENDING
    pass

async def check_session_in_external_db(session_id: str):
    # TODO: 用 httpx.get 打外部 DB，查詢這個 session_id 的最新狀態
    # 假設外部 DB 回傳: {"status": "SUCCESS", "student_id": "C110...123"}
    # 這邊先 mock 一下：
    return {"status": "PENDING"} # 測試時可以手動改成 SUCCESS 來測

@app.get("/api/auth/qr/generate")
async def generate_qr_code():
    """產生一組新的 QR Code 登入 Session"""
    # 1. 產生唯一的 Session ID (Key)
    session_id = uuid.uuid4().hex
    
    # 2. 將 Session ID 註冊到外部 DB (等待被掃描)
    await save_session_to_external_db(session_id)
    
    # 3. 製作 QR Code (將字串包裝成 JSON 或是特定格式供 APP 辨識)
    qr_data = f"nkust-login:{session_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # 將 QR Code 轉成 Base64 圖片，讓前端直接當作圖片 src 顯示
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return {
        "session_id": session_id,
        "qr_image": f"data:image/png;base64,{img_base64}"
    }

@app.get("/api/auth/qr/status/{session_id}")
async def check_qr_status(session_id: str):
    """前端用來輪詢 (Polling) 檢查是否登入成功的 API"""
    # 1. 向外部 DB 查詢狀態
    db_record = await check_session_in_external_db(session_id)
    
    if db_record["status"] == "SUCCESS":
        student_id = db_record.get("student_id")
        
        # 2. 狀態為成功，核發我們自己的 JWT 給前端 (重用你之前的邏輯)
        expire = datetime.utcnow() + timedelta(hours=2)
        jwt_payload = {"student_id": student_id, "exp": expire}
        access_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return {
            "status": "SUCCESS",
            "access_token": access_token,
            "student_id": student_id
        }
    elif db_record["status"] == "EXPIRED":
        # 如果你想做超時機制
        raise HTTPException(status_code=400, detail="QR Code 已過期，請重新整理")
    
    # 還沒掃描或還在處理中
    return {"status": "PENDING"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)