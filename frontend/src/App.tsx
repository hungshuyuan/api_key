import { useState, useEffect } from 'react';
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function App() {
  // --- 基礎狀態 ---
  const [token, setToken] = useState<string | null>(null);
  const [studentId, setStudentId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  // --- 切換登入方式狀態 ---
  const [loginMethod, setLoginMethod] = useState<'google' | 'qr'>('google');
  
  // --- QR 登入相關狀態 ---
  const [qrImage, setQrImage] = useState<string | null>(null);
  const [qrSessionId, setQrSessionId] = useState<string | null>(null);

  // --- API Key 申請相關狀態 ---
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [isCopied, setIsCopied] = useState<boolean>(false);

  // ==========================================
  // 1. Google 登入邏輯
  // ==========================================
  const handleLoginSuccess = async (credentialResponse: CredentialResponse) => {
    setErrorMsg(null);
    try {
      const res = await axios.post(`${API_BASE_URL}/api/auth/google`, {
        token: credentialResponse.credential, 
      });
      setToken(res.data.access_token);
      setStudentId(res.data.student_id);
    } catch (error: any) {
      if (error.response?.status === 403) {
        setErrorMsg("登入失敗：請使用高科大 (@nkust.edu.tw) 學生信箱！");
      } else {
        setErrorMsg("登入過程中發生錯誤，請稍後再試。");
      }
    }
  };

  // ==========================================
  // 2. QR Code 登入邏輯
  // ==========================================
  const fetchQrCode = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/auth/qr/generate`);
      setQrImage(res.data.qr_image);
      setQrSessionId(res.data.session_id);
    } catch (error) {
      setErrorMsg("無法產生 QR Code，請稍後再試。");
    }
  };

  // 當切換到 QR 登入時，自動取得 QR Code
  useEffect(() => {
    if (loginMethod === 'qr' && !token) {
      fetchQrCode();
    } else {
      setQrImage(null);
      setQrSessionId(null);
    }
  }, [loginMethod, token]);

  // 輪詢 (Polling) 檢查 QR 狀態
  useEffect(() => {
    let intervalId: number;

    if (loginMethod === 'qr' && qrSessionId && !token) {
      intervalId = window.setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE_URL}/api/auth/qr/status/${qrSessionId}`);
          if (res.data.status === 'SUCCESS') {
            setToken(res.data.access_token);
            setStudentId(res.data.student_id);
            setLoginMethod('google'); // 重置登入方式狀態
          }
        } catch (error: any) {
          console.error("檢查狀態失敗", error);
          if (error.response?.data?.detail === "QR Code 已過期，請重新整理") {
            fetchQrCode(); // 過期自動重新整理
          }
        }
      }, 2000);
    }

    return () => clearInterval(intervalId);
  }, [loginMethod, qrSessionId, token]);

  // ==========================================
  // 3. API Key 申請與複製邏輯
  // ==========================================
  const handleApplyKey = async () => {
    if (!token) return;
    setLoading(true);
    setErrorMsg(null);
    setIsCopied(false);
    try {
      const res = await axios.post(
        `${API_BASE_URL}/api/apply-key`, 
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setApiKey(res.data.api_key);
    } catch (error) {
      setErrorMsg("申請 API Key 失敗，請確認登入狀態或稍後再試。");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyKey = async () => {
    if (apiKey) {
      try {
        await navigator.clipboard.writeText(apiKey);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
      } catch (err) {
        console.error("複製失敗", err);
        setErrorMsg("複製失敗，請手動選取複製。");
      }
    }
  };

  // ==========================================
  // 畫面渲染 (UI)
  // ==========================================
  return (
    <div style={{ maxWidth: '600px', margin: '50px auto', fontFamily: 'sans-serif', textAlign: 'center' }}>
      <h1>NKUST API Key 申請系統</h1>
      
      {errorMsg && <div style={{ color: 'red', marginBottom: '20px' }}>{errorMsg}</div>}

      {!token ? (
        // --- 尚未登入畫面 ---
        <div>
          <div style={{ marginBottom: '20px' }}>
            <button 
              onClick={() => setLoginMethod('google')}
              style={{ fontWeight: loginMethod === 'google' ? 'bold' : 'normal', padding: '10px', marginRight: '10px' }}
            >
              Google 登入
            </button>
            <button 
              onClick={() => setLoginMethod('qr')}
              style={{ fontWeight: loginMethod === 'qr' ? 'bold' : 'normal', padding: '10px' }}
            >
              APP 掃碼登入
            </button>
          </div>

          {loginMethod === 'google' ? (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <GoogleLogin onSuccess={handleLoginSuccess} onError={() => setErrorMsg("Google 登入視窗意外關閉或發生錯誤")} />
            </div>
          ) : (
            <div style={{ padding: '20px', border: '1px solid #ccc', borderRadius: '8px' }}>
              <h3>請使用校園 APP 掃描登入</h3>
              {qrImage ? (
                <img src={qrImage} alt="Login QR Code" style={{ width: '200px', height: '200px' }} />
              ) : (
                <p>載入中...</p>
              )}
              <p style={{ fontSize: '12px', color: 'gray' }}>請開啟手機 APP 掃描此條碼</p>
              <button onClick={fetchQrCode} style={{ fontSize: '12px', marginTop: '10px' }}>重新整理條碼</button>
            </div>
          )}
        </div>
      ) : (
        // --- 登入成功畫面 ---
        <div style={{ marginTop: '30px' }}>
          <h2>歡迎，學號：{studentId}</h2>
          
          <button 
            onClick={handleApplyKey} 
            disabled={loading}
            style={{ padding: '10px 20px', fontSize: '16px', cursor: 'pointer' }}
          >
            {loading ? '申請中...' : '申請 API Key'}
          </button>

          {apiKey && (
            <div style={{ marginTop: '30px', padding: '20px', backgroundColor: '#f0f0f0', borderRadius: '8px' }}>
              <h3>✅ 申請成功！</h3>
              <p style={{
                wordBreak: 'break-all',     // 強制長字串在邊界換行
                whiteSpace: 'normal',      // 允許正常換行
                backgroundColor: '#eee',   // 灰底背景
                padding: '10px',
                borderRadius: '4px',
                fontFamily: 'monospace',   // 使用等寬字型，看起來更專業
                fontSize: '14px'
              }}>您的 Key: <strong>{apiKey}</strong></p>
              
              <button
                onClick={handleCopyKey}
                style={{
                  marginTop: '10px',
                  padding: '8px 16px',
                  fontSize: '14px',
                  cursor: 'pointer',
                  backgroundColor: isCopied ? '#4CAF50' : '#008CBA',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  transition: 'background-color 0.3s'
                }}
              >
                {isCopied ? '✓ 已複製！' : '📋 複製 API Key'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;