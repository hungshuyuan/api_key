import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List
import xml.etree.ElementTree as ET

from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File, Form, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import jwt
import httpx

# --- 新增：資料庫與加密套件 ---
from cryptography.fernet import Fernet

from db import (
    commit_session,
    create_api_key_record,
    create_course_record,
    create_course_student_relation,
    create_student_record,
    delete_api_key_record,
    get_api_key_record,
    get_course_db,
    get_course_record,
    get_db,
    get_student_record,
    get_course_student_relation,
    init_db,
    list_api_key_records,
    list_courses_for_student,
)
from course_models import Course
import logging

# 載入環境變數
load_dotenv()
router = APIRouter()
logger = logging.getLogger("__uvicorn__")

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
if not ENCRYPTION_KEY:
    raise RuntimeError("ENCRYPTION_KEY is required")
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

TEST = os.getenv("TEST", "false").lower() == "true"


app = FastAPI(title="NKUST API Key Service")


@app.on_event("startup")
def on_startup() -> None:
    init_db()

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
        logger.info(f"JWT 驗證成功，payload: {payload}")
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

class CourseKeyRequest(BaseModel):
    courseID: str
    budget: Optional[float] = None

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
def role_payload(user_id: str, isCourse=False):
    if isCourse:
        max_budget = float(os.getenv("COURSE_MAX_BUDGET", -1))
        budget_duration = os.getenv("COURSE_BUDGET_DURATION", -1)
    else:
        first = user_id[0].upper()
        if first == "C":
            max_budget = float(os.getenv("C_MAX_BUDGET", -1))
            budget_duration = os.getenv("C_BUDGET_DURATION", -1)
        elif first == "F":
            max_budget = float(os.getenv("F_MAX_BUDGET", -1))
            budget_duration = os.getenv("F_BUDGET_DURATION", -1)
        elif first.isdigit():
            max_budget = float(os.getenv("T_MAX_BUDGET", -1))
            budget_duration = os.getenv("T_BUDGET_DURATION", -1)

    # 正式上線後要刪除有關邏輯
    if TEST:
        return {
            "user_id": user_id,
            "user_role": NEW_USER_ROLE,
            "budget_duration": budget_duration,
        }
    return {
        "user_id": user_id,
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
        logger.info(f"Google Auth - Email: {email}")
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
                role_payload_data = role_payload(student_id, False)
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
        logger.error(f"🚨 Token 驗證失敗的真正原因: {e}")
        raise HTTPException(status_code=401, detail="無效的 Google Token")


# ==========================================
# 2. 申請 Key (存入本地 DB)
# ==========================================
@app.post("/api/keys/generate")
async def generate_key(student_id: str = Depends(verify_jwt), db: Session = Depends(get_db)):
    timestamp = int(datetime.utcnow().timestamp())
    logger.info(f"申請 Key 的 student_id: {student_id}, timestamp: {timestamp}")
    payload = {
        "user_id": student_id,
        "key_alias": f"{student_id}_{timestamp}_private",
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
            key_alias = f"{student_id}_{timestamp}_private"

            # 存入資料庫
            create_api_key_record(db, student_id, key_alias, encrypted_key)
            
            # 僅在申請當下回傳一次完整 raw_key，之後不再顯示
            return {"message": "申請成功", "key": raw_key}
            
        except httpx.HTTPStatusError as e:
            logger.error(f"🚨 學長 API 錯誤: {e.response.text}")
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
    db_records = list_api_key_records(db, student_id)
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
    record = get_api_key_record(db, key_id, student_id)
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
            delete_api_key_record(db, record)

            return {"message": "註銷成功"}

        except httpx.HTTPError as e:
            logger.error(f"註銷 Key 失敗: {e}")
            raise HTTPException(status_code=500, detail="註銷失敗，請稍後再試")


# ==========================================
# 5. 查看完整 Raw Key
# ==========================================
@app.get("/api/keys/{key_id}/reveal")
async def reveal_key(key_id: int, student_id: str = Depends(verify_jwt), db: Session = Depends(get_db)):
    record = get_api_key_record(db, key_id, student_id)
    if not record:
        raise HTTPException(status_code=404, detail="找不到此 API Key 或無權限")
    raw_key = cipher_suite.decrypt(record.encrypted_raw_key.encode()).decode()
    return {"raw_key": raw_key}

@app.post("/api/courses/new")
async def create_course(
    courseID: str = Form(...),
    courseName: str = Form(...),
    students: UploadFile = File(...),
    db: Session = Depends(get_course_db),
):
    try:
        async with httpx.AsyncClient() as client:
            headers = get_litellm_headers()
            check_res = await client.get(f"{LITELLM_API_BASE}/user/info?user_id={courseID}", headers=headers)
            if check_res.status_code == 404:
                role_payload_data = role_payload(courseID, True)
                create_res = await client.post(f"{LITELLM_API_BASE}/user/new", json=role_payload_data, headers=headers)
                if create_res.status_code != 200:
                    raise HTTPException(status_code=500, detail="無法在系統建立新用戶")
            elif check_res.status_code != 200:
                raise HTTPException(status_code=500, detail="系統連線發生錯誤")
            else:
                raise HTTPException(status_code=400, detail="Course ID 已存在於系統")

        # ✅ 建立 course
        create_course_record(db, courseID, courseName, datetime.utcnow())

        # ✅ 讀 XML
        content = await students.read()

        try:
            root = ET.fromstring(content)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid XML format")

        student_data = []

        for item in root.findall(".//items/item"):
            if item.attrib.get("type") == "title":
                continue

            sid = item.findtext("account")
            name = item.findtext("realname")

            if sid:
                student_data.append({
                    "studentID": sid,
                    "studentName": name
                })

        # ✅ 寫入 DB
        for s in student_data:
            sid = s["studentID"]
            name = s["studentName"]

            # student
            student = get_student_record(db, sid)
            if not student:
                create_student_record(db, sid, name)

            # relation（避免重複）
            exists = get_course_student_relation(db, courseID, sid)

            if not exists:
                create_course_student_relation(db, courseID, sid)

        commit_session(db)

        return {
            "message": "Course created",
            "courseID": courseID,
            "students_count": len(student_data)
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/courses/keys")
async def generate_course_keys(
    body: CourseKeyRequest, 
    course_db: Session = Depends(get_course_db),
    key_db: Session = Depends(get_db)
):
    courseID = body.courseID
    budget = body.budget or 0.0
    course = get_course_record(course_db, courseID)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found in database, please create course first!")

    async with httpx.AsyncClient() as client:
        headers = get_litellm_headers()
        check_res = await client.get(f"{LITELLM_API_BASE}/user/info?user_id={courseID}", headers=headers)
        if check_res.status_code == 404:
            # 若無該用戶，向學長 API 新增用戶
            raise HTTPException(status_code=404, detail="Course not found in system, please create course first!")
        if check_res.status_code != 200:
            raise HTTPException(status_code=500, detail="System connection error")
        if check_res.status_code == 200:
            course_info = check_res.json().get("user_info", {})
            if course_info.get("max_budget") < len(course.students) * budget:
                raise HTTPException(status_code=400, detail="預算不足以覆蓋所有學生，請重新調整預算")
    result = []
    course_payload = role_payload(courseID, True)
    for cs in course.students:
        sid = cs.studentID
        key_alias = f"{sid}_{int(datetime.utcnow().timestamp())}_course"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{LITELLM_API_BASE}/key/generate",
                    json=course_payload,
                    headers=get_litellm_headers()
                )
                response.raise_for_status()
                data = response.json()
                
                raw_key = data.get("key")
                if not raw_key:
                    raise HTTPException(status_code=500, detail="學長 API 未回傳有效的 Key")

                # 使用 Fernet 將完整 Key 加密後再存入 DB，保護明文安全
                encrypted_key = cipher_suite.encrypt(raw_key.encode()).decode()
                key_alias = f"{sid}_{int(datetime.utcnow().timestamp())}_course"

                # 存入資料庫
                create_api_key_record(key_db, courseID, key_alias, encrypted_key)
            except httpx.HTTPStatusError as e:
                logger.error(f"🚨 學長 API 錯誤: {e.response.text}")
                raise HTTPException(status_code=e.response.status_code, detail="申請金鑰失敗")

    return {
        "courseID": courseID,
        "keys": result
    }

@app.get("/api/courses/list/{studentID}")
async def list_courses(studentID: str, course_db: Session = Depends(get_course_db)):
    courses = list_courses_for_student(course_db, studentID)
    return {
        "courses": [
            {
                "courseName": course.courseName,
                "courseID": course.courseID,
                "created_at": course.created_at,
            }
            for course in courses
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)