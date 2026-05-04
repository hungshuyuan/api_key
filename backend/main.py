import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List
import xml.etree.ElementTree as ET

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import jwt
import httpx

# --- 新增：資料庫與加密套件 ---
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from cryptography.fernet import Fernet

# 載入環境變數
load_dotenv()

# --- 環境變數與驗證設定 ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-for-dev")
JWT_ALGORITHM = "HS256"

# 學長的 LiteLLM API 設定 (請в .env 中設定，或修改預設值)
LITELLM_API_BASE = os.getenv("LITELLM_API_BASE", "https://b225.54ucl.com/capystar/auth")
LITELLM_MANAGE_KEY = os.getenv("LITELLM_MANAGE_KEY", "sk-your-manage-key")

# 新用戶預設參數
# NEW_USER_MAX_BUDGET = float(os.getenv("NEW_USER_MAX_BUDGET", "100"))
NEW_USER_ROLE = os.getenv("NEW_USER_ROLE", "internal_user")
# NEW_USER_BUDGET_DURATION = os.getenv("NEW_USER_BUDGET_DURATION", "7d")

# 加密 Key (用來加密存進資料庫的 raw_key，防止資料外線。可用 Fernet.generate_key() 產生)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# --- 資料庫設定 (預設使用 SQLite：keys.db) ---
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./keys.db")
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)
# 正式上線後要刪除有關邏輯
TEST = os.getenv("TEST", "false").lower() == "true"
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 定義資料表 Schema
class ApiKeyRecord(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True)
    key_alias = Column(String, index=True)  # 例如: C113118289_1744800000
    encrypted_raw_key = Column(String)      # 加密後的完整 key（備用）

# 自動建立資料表
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(title="NKUST API Key Service")

# 設定 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# --- 依賴注入：驗證自己的 JWT ---
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

class KeyResponse(BaseModel):
    id: int
    key_name: str            # LiteLLM 回傳的遮罩 key，例如 sk-...FJUQ
    key_alias: str           # 例如 C113118289_1744800000
    spend: float             # 此 key 的用量
    user_total_spend: float  # 帳號總用量（user 層）
    max_budget: float        # 帳號預算上限（user 層）
    budget_duration: str     # 重置週期，例如 '7d'
    budget_reset_at: Optional[str]  # 下次重置時間，ISO 格式

# --- 共用函式：取得學長 API 用的 Header ---
def get_litellm_headers():
    return {
        "Authorization": f"Bearer {LITELLM_MANAGE_KEY}",
        "Content-Type": "application/json"
    }


def _xml_element_to_value(element: ET.Element):
    children = list(element)
    if not children:
        text = (element.text or "").strip()
        return text

    result = {}
    for child in children:
        child_value = _xml_element_to_value(child)
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_value)
        else:
            result[child.tag] = child_value
    return result


async def parse_post_payload(request: Request):
    content_type = (request.headers.get("content-type") or "").lower()
    raw_body = await request.body()
    text_body = raw_body.decode("utf-8", errors="replace").strip()

    if not text_body:
        return "empty", None

    if "json" in content_type:
        return "json", json.loads(text_body)

    if "xml" in content_type:
        root = ET.fromstring(text_body)
        return "xml", {root.tag: _xml_element_to_value(root)}

    try:
        return "json", json.loads(text_body)
    except json.JSONDecodeError:
        try:
            root = ET.fromstring(text_body)
            return "xml", {root.tag: _xml_element_to_value(root)}
        except ET.ParseError:
            return "text", text_body

# ==========================================
# 1. 登入邏輯 (含學長端 /user/info 與 /user/new)
# ==========================================
def role_payload(student_id: str):
    first = student_id[0].upper()
    if first == "C":
        max_budget = float(os.getenv("C_MAX_BUDGET", -1))
        budget_duration = os.getenv("C_BUDGET_DURATION", -1)
    elif first == "F":
        max_budget = float(os.getenv("F_MAX_BUDGET", -1))
        budget_duration = os.getenv("F_BUDGET_DURATION", -1)
    elif first.isdigit():
        # 若學號第一個字為數字，使用數字類型預設設定（可在 .env 中設定 NUM_MAX_BUDGET / NUM_BUDGET_DURATION）
        max_budget = float(os.getenv("NUM_MAX_BUDGET", -1))
        budget_duration = os.getenv("NUM_BUDGET_DURATION", -1)

    # 正式上線後要刪除有關邏輯
    if TEST:
        return {
            "user_id": student_id,
            "user_role": NEW_USER_ROLE,
            "budget_duration": budget_duration,
        }
    return {
        "user_id": student_id,
        "max_budget": max_budget,
        "user_role": NEW_USER_ROLE,
        "budget_duration": budget_duration,
    }
@app.post("/api/auth/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest):
    try:
        id_info = id_token.verify_oauth2_token(
            request.token, google_requests.Request(), GOOGLE_CLIENT_ID, clock_skew_in_seconds=10
        )
        email = id_info.get("email", "")
        
        allowed_domains = ["nkust.edu.tw"]
        domain = email.split("@")[-1]
        if domain not in allowed_domains:
            raise HTTPException(status_code=403, detail="權限不足：限高科大 (NKUST) 學生帳號登入")
            
        student_id = email.split("@")[0].upper()

        # [新增] 檢查並註冊 LiteLLM 使用者
        async with httpx.AsyncClient() as client:
            headers = get_litellm_headers()
            
            # 檢查使用者是否登入過 (有此用戶)
            check_res = await client.get(f"{LITELLM_API_BASE}/user/info?user_id={student_id}", headers=headers)
            
            if check_res.status_code == 404:
                # 若無該用戶，向學長 API 新增用戶
                role_payload_data = role_payload(student_id)
                create_res = await client.post(f"{LITELLM_API_BASE}/user/new", json=role_payload_data, headers=headers)
                if create_res.status_code != 200:
                    raise HTTPException(status_code=500, detail="無法在 LiteLLM 系統建立新用戶")
            elif check_res.status_code != 200:
                raise HTTPException(status_code=500, detail="LiteLLM 系統連線發生錯誤")

        # 簽發 JWT 給前端
        expire = datetime.utcnow() + timedelta(hours=2)
        jwt_payload = {"student_id": student_id, "exp": expire}
        access_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return {"access_token": access_token, "student_id": student_id}
        
    except ValueError as e:
        print(f"🚨 Token 驗證失敗的真正原因: {e}")
        raise HTTPException(status_code=401, detail="無效的 Google Token")


# ==========================================
# 2. 申請 Key (存入本地 DB)
# ==========================================
@app.post("/api/keys/generate")
async def generate_key(student_id: str = Depends(verify_jwt), db: Session = Depends(get_db)):
    timestamp = int(datetime.utcnow().timestamp())
    payload = {
        "user_id": student_id,
        "key_alias": f"{student_id}_{timestamp}",
        "key_type": "llm_api" # 依學長規格
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LITELLM_API_BASE}/key/generate",
                json=payload,
                headers=get_litellm_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            raw_key = data.get("key")
            if not raw_key:
                raise HTTPException(status_code=500, detail="學長 API 未回傳有效的 Key")

            # 使用 Fernet 將完整 Key 加密後再存入 DB，保護明文安全
            encrypted_key = cipher_suite.encrypt(raw_key.encode()).decode()
            key_alias = f"{student_id}_{timestamp}"

            # 存入資料庫
            new_key_record = ApiKeyRecord(
                student_id=student_id,
                key_alias=key_alias,
                encrypted_raw_key=encrypted_key
            )
            db.add(new_key_record)
            db.commit()
            db.refresh(new_key_record)
            
            # 僅在申請當下回傳一次完整 raw_key，之後不再顯示
            return {"message": "申請成功", "key": raw_key}
            
        except httpx.HTTPStatusError as e:
            print(f"🚨 學長 API 錯誤: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail="申請金鑰失敗")


# ==========================================
# 3. 取得使用者的 Key 列表與目前用量
# ==========================================
@app.get("/api/keys", response_model=List[KeyResponse])
async def get_my_keys(student_id: str = Depends(verify_jwt), db: Session = Depends(get_db)):
    # 向學長 API 查詢該 user 的所有 key 與用量（一次搞定）
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{LITELLM_API_BASE}/user/info?user_id={student_id}",
            headers=get_litellm_headers()
        )
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail="無法取得用量資訊")
        data = res.json()

    user_info = data.get("user_info", {})
    litellm_keys = data.get("keys", [])
    max_budget = user_info.get("max_budget", 0.0) or 0.0
    user_total_spend = user_info.get("spend", 0.0) or 0.0
    budget_duration = user_info.get("budget_duration") or "N/A"
    budget_reset_at = user_info.get("budget_reset_at")

    # 建立 key_alias → db_id 的對應表（用於讓前端拿到刪除所需的 id）
    db_records = db.query(ApiKeyRecord).filter(ApiKeyRecord.student_id == student_id).all()
    alias_to_id = {r.key_alias: r.id for r in db_records}

    result = []
    for k in litellm_keys:
        alias = k.get("key_alias", "")
        db_id = alias_to_id.get(alias)
        if db_id is None:
            continue  # 不在自己 DB 的 key（非本系統申請），略過
        result.append({
            "id": db_id,
            "key_name": k.get("key_name", ""),
            "key_alias": alias,
            "spend": k.get("spend", 0.0) or 0.0,
            "user_total_spend": user_total_spend,
            "max_budget": max_budget,
            "budget_duration": budget_duration,
            "budget_reset_at": budget_reset_at,
        })

    return result


# ==========================================
# 4. 註銷/刪除 Key
# ==========================================
@app.delete("/api/keys/{key_id}")
async def delete_key(key_id: int, student_id: str = Depends(verify_jwt), db: Session = Depends(get_db)):
    # 1. 驗證身分 (確保該 Key 屬於發出請求的學號)
    record = db.query(ApiKeyRecord).filter(ApiKeyRecord.id == key_id, ApiKeyRecord.student_id == student_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="找不到此 API Key 或無權限")

    async with httpx.AsyncClient() as client:
        try:
            # 2. 向學長 API 發出刪除請求（用 key_alias，不需解密）
            await client.post(
                f"{LITELLM_API_BASE}/key/delete",
                json={"key_aliases": [record.key_alias]},
                headers=get_litellm_headers()
            )

            # 3. 從本地資料庫刪除紀錄
            db.delete(record)
            db.commit()

            return {"message": "註銷成功"}

        except httpx.HTTPError as e:
            print(f"註銷 Key 失敗: {e}")
            raise HTTPException(status_code=500, detail="註銷失敗，請稍後再試")


# ==========================================
# 5. 查看完整 Raw Key
# ==========================================
@app.get("/api/keys/{key_id}/reveal")
async def reveal_key(key_id: int, student_id: str = Depends(verify_jwt), db: Session = Depends(get_db)):
    record = db.query(ApiKeyRecord).filter(ApiKeyRecord.id == key_id, ApiKeyRecord.student_id == student_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="找不到此 API Key 或無權限")
    raw_key = cipher_suite.decrypt(record.encrypted_raw_key.encode()).decode()
    return {"raw_key": raw_key}

@app.post("/api/course/new")
async def create_course(request: Request, student_id: str = Depends(verify_jwt)):
    payload_format, payload = await parse_post_payload(request)
    return {
        "student_id": student_id,
        "format": payload_format,
        "data": payload,
    }
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)