#!/bin/bash

# 設定 API 網址 (請根據你實際執行的 port 修改，預設通常是 8000)
API_URL="http://localhost:8000/api/course/new"

# 檢查 XML 檔案是否存在
if [ ! -f "stud_export.xml" ]; then
    echo "錯誤：找不到 stud_export.xml 檔案，請確保檔案在目前目錄下。"
    exit 1
fi

echo "正在上傳課程資料..."

# 執行 curl 請求
# -F 用於傳送 multipart/form-data
# 檔案路徑前必須加上 @ 符號
# curl -X 'POST' \
#   "$API_URL" \
#   -H 'accept: application/json' \
#   -H 'Content-Type: multipart/form-data' \
#   -F "courseID=C113-PY-101" \
#   -F "courseName=Python程式設計基礎" \
#   -F "students=@stud_export.xml"
curl -X 'POST' \
  "http://localhost:8000/api/course/keys" \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F "courseID=C113-PY-101" \
  -F "budget=10" \

echo -e "\n\n測試完成。"