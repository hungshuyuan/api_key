import { useState, useEffect } from 'react';
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import axios from 'axios';
import { Dropdown, type DropdownOption } from './Dropdown';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// 定義 Key 的資料結構 (對應後端回傳的格式)
interface KeyInfo {
  id: number;
  key_name: string;
  key_alias: string;
  spend: number;
  user_total_spend: number;
  max_budget: number;
  budget_duration: string;
  budget_reset_at: string | null;
}

interface CourseInfo {
  courseName: string;
  courseID: string;
  created_at: string;
}
// nkust LOGO
console.log(`%c
                                                 %%                                                 
                                                 ##                                                 
                                                 **                                                 
                                                 ++                                                 
                                          %*#   %==%   #*%                                          
                 #                          +=+#*==*#+=*                          #                 
                 ++*%                        *========*                        %*++                 
                 *++++*%             %##**++++========++++**##%             %*++++*                 
                 *++++++*#%                 %*========*%                 %#+++++++*                 
         #%      %#*+++++++*#%              *==**==**==*              %#*+++++++*#%      %#         
         #++*#%     %#*+++++++*#          %**%  %==%  %**%          #*+++++++*#%     %#*++#         
          *+++++*#%     %**++++++*%              ==              %*++++++**%     %#*+++++*          
          #++++++++**#%    %#*+++++*#            ++            #*+++++*#%    %#**++++++++%          
           %%#**+++++++*#%     #*+++++*%         ##         %*+++++*#     %#*+++++++**#%%           
   %**##%        %#**++++++*#%    #*++++*%       %%       #*++++*%    %#*++++++**#%        %##**%   
    %+++++***#%%      %##*+++++*#    %*+++*%            #*+++*%   %#*+++++*#%%      %%#***+++++%    
     %+++++++++++**#%%     %%#*+++*#%   #*++*%        %*++*#   %#*+++*#%      %%#**+++++++++++%     
      %***+++++++++++++**##%    %#*+++*%  %*++%      #++*%  %*++**#%    %##**+++++++++++++***%      
            %%###****++++++++**#%%  %#*++#% %*+#    #+*% %*++*%   %%#**++++++++****##%%%            
                       %%###**+++++*#%% %#**% #+%  #+# %**#% %%#*++++***###%%                       
 %#############%%%%%%%%%        %%##**+**#%%#*%%*  *%%*#%%#**+**##%%        %%%%%%%%%#############% 
  %###########################%%%%%%  %%##**#%#%#%#%##%#**##%%  %%%%%%###########################%  
   %###################################%%%%%####%%%%####%%%%%###################################%   
     %%%%%%%%%%%#############################%###%%###%#############################%%%%%%%%%%%     
                               %%%%%%%%######################%%%%%%%%                               
                                            %%%######%%%                                            
    ###################################%%%%      %%      %%%%#########################%    %####%   
   %###########################################%%  %%##################################%   ######   
    %%%%%%%%%%%%%%%%%%%%#########%%%%%%%%%%##########################%%%%%%%%%%%%%%%%%      %%%%    
                          #####%            %######################                                 
                          #####%             ######################                                 
     %%%      %%%%%%%%%%%########%%%%%%%%%%%########################%%%%%%%%%%%%%%%%%%%%%%%%%       
   ######    ##################################################################################     
   %#####    #################################################################################%     
                   %%##########%                             %%###############%%                    
                      #######%                                  #############                       
                     %########                                  #############%                      
             %%#####################%          %%###################################%%              
            %#########################        %#######################################%             
             %#######################%         %#####################################%    
`, "color: #777DA7")
console.log(`%c
██╗   ██╗  ██████╗ ██╗     
██║   ██║ ██╔════╝ ██║     
██║   ██║ ██║      ██║     
██║   ██║ ██║      ██║     
╚██████╔╝ ╚██████╗ ███████╗
 ╚═════╝   ╚═════╝ ╚══════╝
`, "color: #777DA7");
console.log(`%c
服務出bug了？
　　　∩∩
　　（´･ω･）
　 ＿|　⊃／(＿＿_
　／ └-(＿＿＿／
　￣￣￣￣￣￣￣
算了反正不是我寫的
　　 ⊂⌒／ヽ-、＿
　／⊂_/＿＿＿＿ ／
　￣￣￣￣￣￣￣
萬一是我寫的呢
　　　∩∩
　　（´･ω･）
　 ＿|　⊃／(＿＿_
　／ └-(＿＿＿／
　￣￣￣￣￣￣￣
算了反正改了一個又出三個
　　 ⊂⌒／ヽ-、＿
　／⊂_/＿＿＿＿ ／
　￣￣
`, "color: #777DA7"
)

function App() {
  // --- 基礎狀態 ---
  const [token, setToken] = useState<string | null>(null);
  const [studentId, setStudentId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // --- API Key 管理相關狀態 ---
  const [keys, setKeys] = useState<KeyInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [course, setCourse] = useState<CourseInfo[]>([]);

  // --- Dropdown 示例狀態 ---
  const [selectedFilter, setSelectedFilter] = useState<DropdownOption | null>(null);

  // ==========================================
  // 0. 頁面載入時從 localStorage 還原登入狀態
  // ==========================================
  useEffect(() => {
    const savedToken = localStorage.getItem('token');
    const savedStudentId = localStorage.getItem('studentId');
    if (savedToken && savedStudentId) {
      // 檢查 JWT 是否過期
      try {
        const payload = JSON.parse(atob(savedToken.split('.')[1]));
        if (payload.exp * 1000 > Date.now()) {
          setToken(savedToken);
          setStudentId(savedStudentId);
        } else {
          // 已過期，清掉
          localStorage.removeItem('token');
          localStorage.removeItem('studentId');
        }
      } catch {
        localStorage.removeItem('token');
        localStorage.removeItem('studentId');
      }
    }
  }, []);


  useEffect(() => {
    if (!token || !selectedFilter) return;

    fetchKeys(token, selectedFilter.id !== 'private');
  }, [selectedFilter, token])



  // ==========================================
  // 1. 取得使用者的 API Keys 列表與用量
  // ==========================================
  const fetchKeys = async (currentToken: string, isCourse: boolean) => {
    try {
      // 呼叫自己的後端。後端負責去 DB 撈出這個學號所有的 Key，
      // 並逐一向學長端 GET /key/info 取得 current_spend 與 max_budget 後合併回傳。
      if (isCourse) {
        const res = await axios.get(`${API_BASE_URL}/api/courses/keys/?courseID=${selectedFilter?.id}`, {
          headers: { Authorization: `Bearer ${currentToken}` }
        });
        setKeys(res.data)
      } else {
        const res = await axios.get(`${API_BASE_URL}/api/keys`, {
          headers: { Authorization: `Bearer ${currentToken}` }
        });
        setKeys(res.data)
      }
    } catch (error) {
      console.error("載入 Key 列表失敗", error);
      setErrorMsg("無法載入您的 API Key 列表與用量");
    }
  };

  const fetchCourse = async (currentToken: string) => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/courses/list`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      console.log("課程列表", res.data.courses);
      setCourse(res.data.courses);
    } catch (error) {
      console.error("載入課程列表失敗", error);
      setErrorMsg("無法載入課程列表");
    }
  };

  // 當成功取得 token (登入成功) 時，自動獲取 Key 列表
  useEffect(() => {
    if (token) {
      fetchKeys(token, false);
      fetchCourse(token);
    }
  }, [token]);

  useEffect(() => {
    console.log(keys[0])
  }, [keys]);

  // ==========================================
  // 2. Google 登入邏輯
  // ==========================================
  const handleLoginSuccess = async (credentialResponse: CredentialResponse) => {
    setErrorMsg(null);
    try {
      // 後端登入 API 需實作：
      // 1. 解析 Google Token 取得學號。
      // 2. 向學長端 GET /user/info?user_id={學號}。
      // 3. 若 404，則 POST /user/new 建立用戶。
      // 4. 最後回傳 JWT (access_token) 給前端。
      const res = await axios.post(`https://nkustapikey.54ucl.com/api/auth/google`, {
        token: credentialResponse.credential,
      });
      // const res = await axios.post(`${API_BASE_URL}/api/auth/google`, {
      //   token: credentialResponse.credential,
      // });
      setToken(res.data.access_token);
      setStudentId(res.data.student_id);
      localStorage.setItem('token', res.data.access_token);
      localStorage.setItem('studentId', res.data.student_id);
    } catch (error: any) {
      if (error.response?.status === 403) {
        setErrorMsg("登入失敗：請使用高科大 (@nkust.edu.tw) 學生信箱！");
      } else {
        setErrorMsg("登入過程中發生錯誤，請稍後再試。" + (error.response?.data?.detail || ''));
      }
    }
  };

  // ==========================================
  // 3. API Key 申請邏輯
  // ==========================================
  const handleApplyKey = async () => {
    if (!token) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      // 呼叫後端 API，由後端向學長端 /key/generate 申請，並寫入自身 DB
      const res = await axios.post(
        `${API_BASE_URL}/api/keys/generate`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const rawKey = res.data.key;
      setNewlyCreatedKey(rawKey);
      fetchKeys(token, false); // 申請成功後，重新載入列表與最新用量
    } catch (error) {
      setErrorMsg("申請 API Key 失敗，請確認登入狀態或稍後再試。");
    } finally {
      setLoading(false);
    }
  };

  // --- 刪除確認 Modal 狀態 ---
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; keyName: string } | null>(null);
  const [deleteInput, setDeleteInput] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);

  // ==========================================
  // 5. 查看 Raw Key
  // ==========================================
  const handleRevealKey = async (keyId: number) => {
    if (!token) return;
    try {
      const res = await axios.get(`${API_BASE_URL}/api/keys/${keyId}/reveal`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRevealedKey(res.data.raw_key);
    } catch {
      setErrorMsg('無法取得 API Key，請稍後再試。');
    }
  };

  const handleDeleteKey = (keyId: number, keyName: string) => {
    setDeleteInput('');
    setDeleteTarget({ id: keyId, keyName });
  };

  const confirmDeleteKey = async () => {
    if (!token || !deleteTarget) return;
    if (deleteInput !== studentId) return;
    setDeleteLoading(true);
    try {
      await axios.delete(`${API_BASE_URL}/api/keys/${deleteTarget.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDeleteTarget(null);
      fetchKeys(token, false);
    } catch (error) {
      setErrorMsg('註銷 API Key 失敗，請稍後再試。');
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleCopyKey = async (textToCopy: string) => {
    try {
      await navigator.clipboard.writeText(textToCopy);
      alert("已複製 API Key！");
    } catch (err) {
      setErrorMsg("複製失敗，請手動選取複製。");
    }
  };

  // ==========================================
  // 畫面渲染 (UI)
  // ==========================================
  return (
    <div style={{ maxWidth: '700px', margin: '50px auto', fontFamily: 'sans-serif', textAlign: 'center' }}>
      <h1>NKUST API Key 申請系統</h1>

      {/* ===== 申請成功 Modal ===== */}
      {newlyCreatedKey && (
        <div
          onClick={() => setNewlyCreatedKey(null)}
          style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ backgroundColor: '#fff', borderRadius: '16px', padding: '36px 32px 28px', maxWidth: '480px', width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', textAlign: 'left' }}
          >
            {/* 標題列 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span style={{ fontSize: '22px' }}>🎉</span>
              <span style={{ fontSize: '18px', fontWeight: 700, color: '#111' }}>申請成功</span>
            </div>
            <p style={{ margin: '0 0 20px 0', fontSize: '13px', color: '#e53935', fontWeight: 500 }}>
              請立即複製並妥善保存，此 Key 之後不會再次顯示。
            </p>

            {/* Key 顯示區 */}
            <div style={{ position: 'relative', backgroundColor: '#f7f7f8', border: '1px solid #e5e5e5', borderRadius: '10px', padding: '14px 48px 14px 16px', marginBottom: '24px' }}>
              <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: '13px', color: '#111', wordBreak: 'break-all', lineHeight: '1.6' }}>
                {newlyCreatedKey}
              </span>
              <button
                onClick={() => handleCopyKey(newlyCreatedKey)}
                title="複製"
                style={{ position: 'absolute', top: '50%', right: '12px', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px', color: '#666', padding: '4px' }}
              >
                📋
              </button>
            </div>

            {/* 關閉按鈕 */}
            <button
              onClick={() => setNewlyCreatedKey(null)}
              style={{ width: '100%', padding: '11px', backgroundColor: '#111', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 600, letterSpacing: '0.3px' }}
            >
              已複製，關閉
            </button>
          </div>
        </div>
      )}

      {/* ===== 查看 Raw Key Modal ===== */}
      {revealedKey && (
        <div
          onClick={() => setRevealedKey(null)}
          style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ backgroundColor: '#fff', borderRadius: '16px', padding: '36px 32px 28px', maxWidth: '480px', width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', textAlign: 'left' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span style={{ fontSize: '22px' }}>🔑</span>
              <span style={{ fontSize: '18px', fontWeight: 700, color: '#111' }}>API Key</span>
            </div>
            <p style={{ margin: '0 0 16px 0', fontSize: '13px', color: '#888' }}>請妥善保管，勿分享給他人。</p>
            <div style={{ position: 'relative', backgroundColor: '#f7f7f8', border: '1px solid #e5e5e5', borderRadius: '10px', padding: '14px 16px', marginBottom: '24px', wordBreak: 'break-all', fontFamily: 'ui-monospace, monospace', fontSize: '13px', color: '#111', lineHeight: '1.6' }}>
              {revealedKey}
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => handleCopyKey(revealedKey)}
                style={{ flex: 1, padding: '11px', backgroundColor: '#f0f0f0', color: '#333', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 600 }}
              >
                📋 複製
              </button>
              <button
                onClick={() => setRevealedKey(null)}
                style={{ flex: 1, padding: '11px', backgroundColor: '#111', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 600 }}
              >
                關閉
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 註銷確認 Modal ===== */}
      {deleteTarget && (
        <div
          onClick={() => setDeleteTarget(null)}
          style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ backgroundColor: '#fff', borderRadius: '16px', padding: '36px 32px 28px', maxWidth: '420px', width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', textAlign: 'left' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span style={{ fontSize: '22px' }}>⚠️</span>
              <span style={{ fontSize: '18px', fontWeight: 700, color: '#111' }}>確認註銷</span>
            </div>
            <p style={{ margin: '0 0 6px 0', fontSize: '13px', color: '#555' }}>
              即將註銷以下 API Key，此操作無法復原：
            </p>
            <div style={{ backgroundColor: '#f7f7f8', border: '1px solid #e5e5e5', borderRadius: '8px', padding: '10px 14px', marginBottom: '20px', fontFamily: 'ui-monospace, monospace', fontSize: '13px', color: '#111' }}>
              {deleteTarget.keyName}
            </div>
            <p style={{ margin: '0 0 8px 0', fontSize: '13px', color: '#555' }}>
              請輸入您的學號 <strong>{studentId}</strong> 以確認：
            </p>
            <input
              type="text"
              value={deleteInput}
              onChange={(e) => setDeleteInput(e.target.value)}
              placeholder={studentId ?? ''}
              style={{ width: '100%', padding: '10px 12px', fontSize: '14px', border: '1px solid #ddd', borderRadius: '8px', outline: 'none', boxSizing: 'border-box', marginBottom: '16px' }}
            />
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => setDeleteTarget(null)}
                style={{ flex: 1, padding: '11px', backgroundColor: '#f0f0f0', color: '#333', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 600 }}
              >
                取消
              </button>
              <button
                onClick={confirmDeleteKey}
                disabled={deleteInput !== studentId || deleteLoading}
                style={{ flex: 1, padding: '11px', backgroundColor: deleteLoading ? '#9e9e9e' : (deleteInput === studentId ? '#e53935' : '#f5c6c6'), color: '#fff', border: 'none', borderRadius: '8px', cursor: deleteInput === studentId && !deleteLoading ? 'pointer' : 'not-allowed', fontSize: '14px', fontWeight: 600, transition: 'background-color 0.2s' }}
              >
                {deleteLoading ? '註銷中...' : '確認註銷'}
              </button>
            </div>
          </div>
        </div>
      )}

      {errorMsg && (
        <div style={{ color: 'red', marginBottom: '20px', padding: '10px', border: '1px solid red', borderRadius: '4px' }}>
          {errorMsg}
        </div>
      )}

      {!token ? (
        // --- 尚未登入畫面 ---
        <div>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <GoogleLogin onSuccess={handleLoginSuccess} onError={() => setErrorMsg("Google 登入視窗意外關閉或發生錯誤")} />
          </div>
        </div>
      ) : (
        // --- 登入成功畫面 ---
        <div style={{ marginTop: '32px', textAlign: 'left' }}>

          {/* 頂部：歡迎 + 操作按鈕 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <div>
              <div style={{ fontSize: '13px', color: '#888', marginBottom: '2px' }}>已登入</div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#111' }}>{studentId}</div>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => {
                  localStorage.removeItem('token');
                  localStorage.removeItem('studentId');
                  setToken(null);
                  setStudentId(null);
                  setKeys([]);
                }}
                style={{
                  padding: '10px 16px', fontSize: '14px', fontWeight: 600, cursor: 'pointer',
                  backgroundColor: '#f0f0f0', color: '#555', border: 'none',
                  borderRadius: '8px', letterSpacing: '0.3px'
                }}
              >
                登出
              </button>
              <button
                onClick={handleApplyKey}
                disabled={loading}
                style={{
                  padding: '10px 20px', fontSize: '14px', fontWeight: 600, cursor: 'pointer',
                  backgroundColor: '#111', color: '#fff', border: 'none',
                  borderRadius: '8px', letterSpacing: '0.3px', opacity: loading ? 0.6 : 1
                }}
              >
                {loading ? '申請中...' : '+ 申請新 Key'}
              </button>
            </div>
          </div>

          {/* 帳號用量概覽卡片（只在有 key 時顯示） */}
          {keys.length > 0 && (
            <div style={{
              backgroundColor: '#f7f7f8', border: '1px solid #e5e5e5',
              borderRadius: '12px', padding: '16px 20px', marginBottom: '20px'
            }}>
              <div style={{ fontSize: '12px', color: '#888', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>帳號用量概覽</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '24px', fontWeight: 700, color: keys[0].user_total_spend / keys[0].max_budget > 0.8 ? '#e53935' : '#111' }}>
                  ${keys[0].user_total_spend.toFixed(4)}
                </span>
                <span style={{ fontSize: '14px', color: '#888' }}>/ ${keys[0].max_budget}</span>
              </div>
              <div style={{ marginTop: '4px', fontSize: '12px', color: '#aaa' }}>
                每 {keys[0].budget_duration} 重置
                {keys[0].budget_reset_at && (
                  <span> · 下次重置：{new Date(keys[0].budget_reset_at).toLocaleDateString('zh-TW', { year: 'numeric', month: 'numeric', day: 'numeric' })}</span>
                )}
              </div>
              {/* 進度條 */}
              <div style={{ marginTop: '10px', height: '6px', backgroundColor: '#e0e0e0', borderRadius: '99px', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: '99px',
                  backgroundColor: keys[0].user_total_spend / keys[0].max_budget > 0.8 ? '#e53935' : '#111',
                  width: `${Math.min(keys[0].user_total_spend / keys[0].max_budget * 100, 100)}%`,
                  transition: 'width 0.4s ease'
                }} />
              </div>
            </div>
          )}

          {/* Key 列表 */}
          <div style={{ fontSize: '13px', color: '#888', marginBottom: '10px', fontWeight: 500, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
            <div>API Keys（{keys.length}）</div>
            {/* 刷新按鈕 + Dropdown */}
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <button
                onClick={() => fetchKeys(token || '', selectedFilter ? selectedFilter.id !== 'private' : false)}
                title="刷新 API Keys 列表"
                style={{
                  padding: '6px 8px',
                  fontSize: '14px',
                  cursor: 'pointer',
                  backgroundColor: 'transparent',
                  color: '#555',
                  border: 'none',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '4px',
                  flexShrink: 0,
                  lineHeight: 1,
                  transition: 'color 0.2s ease'
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#111')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#555')}
              >
                <i className="fa-solid fa-arrows-rotate"></i>
                刷新
              </button>
              <div style={{ minWidth: '200px' }}>
                <Dropdown
                  options={[
                    { id: 'private', label: '私人 API Keys' },
                    ...course.map(c => ({ id: c.courseID, label: c.courseName }))
                  ]}
                  onSelect={(option) => setSelectedFilter(option)}
                  placeholder="篩選..."
                  defaultLabel="None"
                />
              </div>
            </div>
          </div>

          {keys.length === 0 ? (
            <div style={{ padding: '32px', textAlign: 'center', border: '1px dashed #ddd', borderRadius: '12px', color: '#aaa', fontSize: '14px' }}>
              尚未申請任何 API Key
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {keys.map((k) => (
                <div key={k.id} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '14px 16px', border: '1px solid #e5e5e5', borderRadius: '10px',
                  backgroundColor: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
                }}>
                  {/* 左：key 名稱 + 用量 */}
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: '14px', color: '#111', marginBottom: '4px' }}>
                      {k.key_name}
                    </div>
                    <div style={{ fontSize: '12px', color: '#888' }}>
                      此 Key 總用量(自創建起)：<span style={{ color: '#555', fontWeight: 600 }}>${k.spend.toFixed(5)}</span>
                    </div>
                  </div>

                  {/* 右：操作按鈕 */}
                  <div style={{ display: 'flex', gap: '8px', flexShrink: 0, marginLeft: '16px' }}>
                    <button
                      onClick={() => handleRevealKey(k.id)}
                      style={{ padding: '7px 14px', fontSize: '13px', cursor: 'pointer', backgroundColor: '#f0f0f0', color: '#333', border: 'none', borderRadius: '6px', fontWeight: 500 }}
                    >
                      查看
                    </button>
                    <button
                      onClick={() => handleDeleteKey(k.id, k.key_name)}
                      style={{ padding: '7px 14px', fontSize: '13px', cursor: 'pointer', backgroundColor: '#fff0f0', color: '#e53935', border: '1px solid #ffd0d0', borderRadius: '6px', fontWeight: 500 }}
                    >
                      註銷
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;