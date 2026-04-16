Problem:

- litellm未設定manage key

- ENCRYPTION_KEY未設定，且程式碼:
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
導致每次啟動都是一把隨機key

-回傳key仍經加密，移除masked_key函式

-前端未增加key欄位的變數，導致只能回傳"申請成功"



測試流程:

刪除本地DB資料:
sqlite3 keys.db "DELETE FROM api_keys WHERE student_id = 'C112118111';"

刪除user
curl -X POST http://163.18.26.230:7536/user/delete   -H "Content-Type: application/json"   -H "Authorization: Bearer sk-IdvMmlIxF73YTgY4XovMlQ"   -d '{"user_ids": ["C112118111"]}'

查詢user資料
curl -X GET "http://163.18.26.230:7536/user/info?user_id=C112118111"   -H "Content-Type: application/json"   -H "Authorization: Bearer sk-IdvMmlIxF73YTgY4XovMlQ"