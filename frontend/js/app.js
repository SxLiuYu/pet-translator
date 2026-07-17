const API_BASE = 'http://localhost:8000';
let ws = null;
let pets = [];
let currentPage = 'dashboard';
let mediaRecorder = null;
let audioChunks = [];
let camViewWs = null;

// ===== API Client =====
const api = {
  async get(path) { const r = await fetch(API_BASE + path); return r.json(); },
  async post(path, body) {
    const r = await fetch(API_BASE + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return r.json();
  },
  async put(path, body) {
    const r = await fetch(API_BASE + path, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return r.json();
  },
  async del(path) { const r = await fetch(API_BASE + path, { method: 'DELETE' }); return r.json(); },
  async uploadAudio(file) {
    const form = new FormData();
    form.append('file', file);
    const r = await fetch(API_BASE + '/api/upload_audio', { method: 'POST', body: form });
    return r.json();
  },
};

// ===== WebSocket =====
function connectWS() {
  const wsUrl = API_BASE.replace(/^http/, 'ws') + '/ws';
  ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    document.getElementById('ws-status').className = 'status-dot online';
    document.getElementById('ws-status-text').textContent = '已连接';
  };
  ws.onclose = () => {
    document.getElementById('ws-status').className = 'status-dot offline';
    document.getElementById('ws-status-text').textContent = '已断开';
    setTimeout(connectWS, 3000);
  };
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'behavior_alert' || msg.type === 'behavior_update') {
        addRealtimeEvent(msg.data);
      }
    } catch (err) {}
  };
  ws.onerror = () => {};
}

// ===== Navigation =====
document.querySelectorAll('.nav-item').forEach((item) => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
    document.querySelectorAll('.page').forEach((p) => p.classList.remove('active'));
    item.classList.add('active');
    const page = item.dataset.page;
    currentPage = page;
    const pg = document.getElementById('page-' + page);
    if (pg) pg.classList.add('active');
    document.getElementById('page-title').textContent = item.textContent.trim();
    loadPage(page);
  });
});

function loadPage(page) {
  const actions = {
    dashboard: loadDashboard,
    pets: loadPets,
    events: loadEvents,
    report: loadReport,
    cameras: loadCameras,
    upload: () => {},
    settings: loadSettings,
    trends: loadTrends,
  };
  if (actions[page]) actions[page]();
}

// ===== Dashboard =====
async function loadDashboard() {
  try {
    const status = await api.get('/api/status');
    document.getElementById('stat-events').textContent = status.events_today || 0;
    const camStatus = status.cameras || {};
    document.getElementById('stat-cameras').textContent = Object.keys(camStatus).length;
  } catch (err) {}
  try {
    const report = await api.get('/api/report');
    if (report.health_score !== undefined) {
      document.getElementById('stat-health').textContent = report.health_score;
      document.getElementById('stat-alerts').textContent = report.alert_count || 0;
      document.getElementById('dashboard-suggestions').innerHTML = (report.suggestions || []).map((s) => '<div class="event-item">' + s + '</div>').join('') || '<div class="empty-state">暂无建议</div>';
    }
  } catch (err) {}
}

function addRealtimeEvent(data) {
  const el = document.getElementById('realtime-events');
  const item = document.createElement('div');
  item.className = 'event-item' + (data.is_alert ? ' alert' : '');
  item.innerHTML = '<div class="event-time">' + (data.timestamp || '') + '</div>' +
    '<div class="event-title">' + (data.animal || '') + ' ' + (data.behavior || '') +
    ' <span style="font-size:12px;color:#636e72">' + Math.round((data.confidence || 0) * 100) + '%</span></div>' +
    '<div class="event-desc">' + (data.interpretation || '') + '</div>' +
    '<div class="event-desc">💡 ' + (data.suggestion || '') + '</div>';
  el.prepend(item);
  if (el.children.length > 50) el.removeChild(el.lastChild);
  const alertsEl = document.getElementById('stat-alerts');
  if (data.is_alert) alertsEl.textContent = parseInt(alertsEl.textContent || '0') + 1;
  document.getElementById('stat-events').textContent = parseInt(document.getElementById('stat-events').textContent || '0') + 1;
}

// ===== Pets =====
async function loadPets() {
  try {
    const data = await api.get('/api/pets');
    pets = data.pets || [];
    const tbody = document.getElementById('pet-table-body');
    if (pets.length === 0) { tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无宠物</td></tr>'; return; }
    tbody.innerHTML = pets.map((p) => '<tr><td>' + (p.id || '') + '</td><td>' + (p.name || '') + '</td><td>' + (p.species || '') + '</td><td>' + (p.breed || '') + '</td><td>' + (p.age || 0) + '</td><td><button class="btn btn-sm" onclick="editPet(\'' + p.id + '\')">✏️</button> <button class="btn btn-sm btn-danger" onclick="deletePet(\'' + p.id + '\')">🗑️</button></td></tr>').join('');
    document.getElementById('event-pet-filter').innerHTML = '<option value="">全部宠物</option>' + pets.map((p) => '<option value="' + p.id + '">' + p.name + '</option>').join('');
  } catch (err) {}
}

document.getElementById('btn-add-pet').addEventListener('click', () => openPetModal());
document.getElementById('pet-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('pet-id').value;
  const data = { name: document.getElementById('pet-name').value, species: document.getElementById('pet-species').value, breed: document.getElementById('pet-breed').value, age: parseInt(document.getElementById('pet-age').value) || 0, personality_tags: document.getElementById('pet-tags').value.split(',').map((s) => s.trim()).filter(Boolean), health_notes: document.getElementById('pet-notes').value };
  if (id) { await api.put('/api/pets/' + id, data); }
  else { data.pet_id = 'pet_' + Date.now(); await api.post('/api/pets', data); }
  closePetModal(); loadPets();
});
document.querySelector('.modal-close').addEventListener('click', closePetModal);
document.getElementById('pet-modal').addEventListener('click', (e) => { if (e.target === e.currentTarget) closePetModal(); });

function openPetModal(pet) {
  document.getElementById('pet-modal').classList.add('active');
  document.getElementById('pet-modal-title').textContent = pet ? '编辑宠物' : '添加宠物';
  document.getElementById('pet-id').value = pet ? pet.id : '';
  document.getElementById('pet-name').value = pet ? (pet.name || '') : '';
  document.getElementById('pet-species').value = pet ? (pet.species || '狗') : '狗';
  document.getElementById('pet-breed').value = pet ? (pet.breed || '') : '';
  document.getElementById('pet-age').value = pet ? (pet.age || 0) : 0;
  document.getElementById('pet-tags').value = pet ? (pet.personality_tags || []).join(',') : '';
  document.getElementById('pet-notes').value = pet ? (pet.health_notes || '') : '';
}
function closePetModal() { document.getElementById('pet-modal').classList.remove('active'); }
function editPet(id) { const p = pets.find((x) => x.id === id); if (p) openPetModal(p); }
async function deletePet(id) { if (!confirm('确定删除该宠物？')) return; await api.del('/api/pets/' + id); loadPets(); }

// ===== Events =====
async function loadEvents() {
  try {
    const petId = document.getElementById('event-pet-filter').value;
    const url = petId ? '/api/events?pet_id=' + petId : '/api/events';
    const data = await api.get(url);
    const events = data.events || [];
    const el = document.getElementById('events-list');
    if (events.length === 0) { el.innerHTML = '<div class="empty-state">暂无事件记录</div>'; return; }
    el.innerHTML = events.map((e) => '<div class="event-item' + (e.is_alert ? ' alert' : '') + '"><div class="event-time">' + (e.timestamp || '') + ' | ' + (e.period || '') + '</div><div class="event-title">' + (e.animal || '') + ' ' + (e.behavior || '') + ' <span style="font-size:12px;color:#636e72">' + Math.round((e.confidence || 0) * 100) + '%</span> <span style="font-size:11px;color:' + (e.severity === 'alert' ? '#e17055' : e.severity === 'warning' ? '#fdcb6e' : '#00b894') + '">' + (e.severity || '') + '</span></div><div class="event-desc">' + (e.interpretation || '') + '</div><div class="event-desc">💡 ' + (e.suggestion || '') + '</div><div style="margin-top:6px"><button class="btn btn-sm" onclick="addFeedback(\'' + e.id + '\',\'correct\')">✅ 正确</button> <button class="btn btn-sm" onclick="addFeedback(\'' + e.id + '\',\'false_positive\')">❌ 误报</button></div></div>').join('');
  } catch (err) {}
}
document.getElementById('event-pet-filter').addEventListener('change', loadEvents);
async function addFeedback(eventId, fb) { await api.post('/api/event/' + eventId + '/feedback', { feedback: fb }); loadEvents(); }

// ===== Report =====
async function loadReport() {
  try {
    const data = await api.get('/api/report');
    const el = document.getElementById('report-content');
    if (data.health_score === undefined) {
      el.innerHTML = '<div class="empty-state">暂无报告数据</div><button class="btn btn-primary" id="btn-generate-report">📊 生成今日报告</button>';
      document.getElementById('btn-generate-report').addEventListener('click', generateReport); return;
    }
    const maxCount = Math.max(...Object.values(data.hourly_chart || {}).map((v) => v.total || 0), 1);
    el.innerHTML = '<div class="report-card"><div class="score">' + data.health_score + '/100</div><div class="status">' + (data.health_status || '') + '</div></div>' +
      '<div class="report-section"><h3>📊 今日概况</h3><p>事件总数: ' + (data.total_events || 0) + ' | 警报: ' + (data.alert_count || 0) + '</p></div>' +
      '<div class="report-section"><h3>💡 陪玩建议</h3>' + (data.suggestions || []).map((s) => '<div class="event-item">' + s + '</div>').join('') + '</div>' +
      '<div class="report-section"><h3>📈 时段分布</h3>' + Object.entries(data.hourly_chart || {}).sort((a, b) => a[0] - b[0]).map(([h, v]) => '<div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span style="width:40px;font-size:12px">' + h + ':00</span><div style="flex:1;height:20px;background:#eee;border-radius:4px;overflow:hidden"><div style="height:100%;width:' + ((v.total / maxCount) * 100) + '%;background:linear-gradient(90deg,#6c5ce7,#a29bfe);border-radius:4px"></div></div><span style="font-size:12px;color:#636e72">' + v.total + '</span></div>').join('') + '</div>' +
      '<button class="btn btn-primary" id="btn-generate-report" style="margin-top:12px">🔄 重新生成</button>';
    document.getElementById('btn-generate-report').addEventListener('click', generateReport);
  } catch (err) {
    document.getElementById('report-content').innerHTML = '<div class="empty-state">暂无报告数据</div><button class="btn btn-primary" id="btn-generate-report">📊 生成今日报告</button>';
    document.getElementById('btn-generate-report').addEventListener('click', generateReport);
  }
}
async function generateReport() {
  document.getElementById('report-content').innerHTML = '<div class="empty-state">⏳ 生成中...</div>';
  try {
    const data = await api.post('/api/report/generate', {});
    if (data.report) loadReport();
    else { document.getElementById('report-content').innerHTML = '<div class="empty-state">' + (data.message || '生成失败') + '</div><button class="btn btn-primary" id="btn-generate-report">🔄 重试</button>'; document.getElementById('btn-generate-report').addEventListener('click', generateReport); }
  } catch (err) {
    document.getElementById('report-content').innerHTML = '<div class="empty-state">生成失败: ' + err.message + '</div><button class="btn btn-primary" id="btn-generate-report">🔄 重试</button>';
    document.getElementById('btn-generate-report').addEventListener('click', generateReport);
  }
}

// ===== Cameras + Live View =====
async function loadCameras() {
  try {
    const status = await api.get('/api/status');
    const cams = status.cameras || {};
    const el = document.getElementById('camera-status');
    if (Object.keys(cams).length === 0) { el.innerHTML = '<div class="empty-state">暂无摄像头</div>'; return; }
    el.innerHTML = Object.entries(cams).map(([name, info]) => '<div class="event-item"><div class="event-title">📷 ' + name + ' <button class="btn btn-sm btn-primary" onclick="startCamView(\'' + name + '\')">▶️ 查看</button></div><div class="event-desc">状态: ' + (info.running ? '🟢 运行中' : '🔴 已停止') + ' | FPS: ' + (info.fps || 0) + ' | 信号: ' + (info.has_frame ? '✅' : '❌') + '</div></div>').join('');
  } catch (err) {}
}

function startCamView(camName) {
  const el = document.getElementById('camera-viewer');
  el.innerHTML = '<div style="text-align:center"><p>⏳ 连接摄像头 ' + camName + '...</p></div>';
  if (camViewWs) { camViewWs.close(); camViewWs = null; }
  const wsUrl = API_BASE.replace(/^http/, 'ws') + '/camera/stream/' + encodeURIComponent(camName);
  camViewWs = new WebSocket(wsUrl);
  camViewWs.onopen = () => { el.innerHTML = ''; };
  camViewWs.onmessage = (e) => {
    if (e.data instanceof Blob) {
      e.data.arrayBuffer().then((ab) => {
        const bytes = new Uint8Array(ab);
        const sepIdx = bytes.indexOf(0);
        if (sepIdx > 0) {
          const jpeg = new Blob([bytes.slice(sepIdx + 1)], { type: 'image/jpeg' });
          const url = URL.createObjectURL(jpeg);
          el.innerHTML = '<img src="' + url + '" style="max-width:100%;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1)" onload="URL.revokeObjectURL(this.src)">';
        }
      });
    }
  };
  camViewWs.onerror = camViewWs.onclose = () => {
    if (el.innerHTML === '') el.innerHTML = '<div class="empty-state">摄像头连接已断开</div>';
  };
}

document.getElementById('camera-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('cam-name').value;
  const type = document.getElementById('cam-type').value;
  const url = document.getElementById('cam-url').value;
  try {
    const data = { name, source_type: type };
    if (type === 'rtsp' || type === 'esp32cam') data.url = url;
    else data.device_index = parseInt(url) || 0;
    await api.post('/api/cameras/register', data);
    loadCameras();
    document.getElementById('camera-form').reset();
  } catch (err) { alert('添加失败: ' + err.message); }
});

// ===== Upload Audio + Browser Recording =====
document.getElementById('upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('audio-file');
  const file = fileInput.files[0];
  if (!file) { alert('请选择音频文件'); return; }
  await uploadAndShow(file);
});

async function uploadAndShow(file) {
  const el = document.getElementById('upload-result');
  el.innerHTML = '<div class="empty-state">⏳ 分析中...</div>';
  try {
    const data = await api.uploadAudio(file);
    el.innerHTML = '<div class="upload-result-card' + (data.is_alert ? ' alert' : '') + '"><div style="font-size:18px;font-weight:600">' + (data.animal || '') + ' ' + (data.behavior || '') + ' <span style="font-size:14px;color:#636e72">' + Math.round((data.confidence || 0) * 100) + '%</span></div><div style="margin-top:8px;color:#636e72">' + (data.interpretation || '') + '</div><div style="margin-top:4px;color:#636e72">💡 ' + (data.suggestion || '') + '</div>' + (data.is_alert ? '<div style="margin-top:8px;color:#e17055;font-weight:600">🚨 需要关注!</div>' : '') + '</div>';
  } catch (err) { el.innerHTML = '<div class="empty-state">分析失败: ' + err.message + '</div>'; }
}

// Browser Recording
let mediaRecorder = null;
let audioChunks = [];

async function startRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm' });
    audioChunks = [];
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      document.getElementById('record-status').textContent = '⏳ 上传分析中...';
      await uploadAndShow(new File([blob], 'recording.webm', { type: 'audio/webm' }));
      document.getElementById('record-status').textContent = '';
      document.getElementById('btn-start-record').style.display = 'inline-flex';
      document.getElementById('btn-stop-record').style.display = 'none';
    };
    mediaRecorder.start();
    document.getElementById('btn-start-record').style.display = 'none';
    document.getElementById('btn-stop-record').style.display = 'inline-flex';
    document.getElementById('record-status').textContent = '🔴 录音中...';
  } catch (err) { alert('麦克风访问被拒绝: ' + err.message); }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    document.getElementById('record-status').textContent = '⏳ 处理中...';
  }
}

// ===== Settings =====
function loadSettings() {
  document.getElementById('settings-wechat-webhook').value = localStorage.getItem('WECHAT_WEBHOOK') || '';
  document.getElementById('settings-serverchan').value = localStorage.getItem('SERVERCHAN_KEY') || '';
  document.getElementById('settings-yolo-model').value = localStorage.getItem('YOLO_MODEL') || 'yolov8n.pt';
}

document.getElementById('settings-form').addEventListener('submit', (e) => {
  e.preventDefault();
  localStorage.setItem('WECHAT_WEBHOOK', document.getElementById('settings-wechat-webhook').value);
  localStorage.setItem('SERVERCHAN_KEY', document.getElementById('settings-serverchan').value);
  localStorage.setItem('YOLO_MODEL', document.getElementById('settings-yolo-model').value);
  document.getElementById('settings-status').textContent = '✅ 设置已保存（刷新后端生效）';
  setTimeout(() => document.getElementById('settings-status').textContent = '', 3000);
});

// ===== Trends =====
async function loadTrends() {
  try {
    const data = await api.get('/api/trends');
    const el = document.getElementById('trends-content');
    if (!data.days || data.days.length === 0) { el.innerHTML = '<div class="empty-state">暂无历史数据，过几天再来看吧</div>'; return; }
    const days = data.days;
    const maxScore = Math.max(...days.map((d) => d.health_score || 0), 100);
    el.innerHTML = '<div class="report-section"><h3>📈 近7天健康趋势</h3><div style="display:flex;align-items:flex-end;gap:8px;height:180px;padding:16px 0">' +
      days.map((d) => '<div style="flex:1;display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end"><div style="width:100%;max-width:40px;height:' + ((d.health_score / maxScore) * 160) + 'px;background:linear-gradient(180deg,#6c5ce7,#a29bfe);border-radius:6px 6px 0 0;transition:height 0.3s;position:relative"><span style="position:absolute;top:-20px;left:50%;transform:translateX(-50%);font-size:11px;font-weight:600;color:#6c5ce7">' + d.health_score + '</span></div><span style="font-size:11px;color:#636e72;margin-top:6px">' + (d.date || '').slice(5) + '</span></div>').join('') +
      '</div></div>' +
      '<div class="report-section"><h3>📊 每日统计</h3>' + days.map((d) => '<div class="event-item"><div class="event-title">' + (d.date || '') + ' <span style="font-size:12px;color:#636e72">评分: ' + (d.health_score || 0) + ' | 事件: ' + (d.total_events || 0) + ' | 警报: ' + (d.alert_count || 0) + '</span></div></div>').join('') + '</div>';
  } catch (err) { document.getElementById('trends-content').innerHTML = '<div class="empty-state">加载失败: ' + err.message + '</div>'; }
}

// ===== Refresh =====
document.getElementById('btn-refresh').addEventListener('click', () => loadPage(currentPage));

// ===== Init =====
connectWS();
loadDashboard();

// ===== Data Export =====
async function exportEvents() {
  const petId = document.getElementById('event-pet-filter').value;
  const url = petId ? '/api/events/export?format=json&pet_id=' + petId : '/api/events/export?format=json';
  try {
    const data = await api.get(url);
    if (!data.events || data.events.length === 0) { alert('暂无数据可导出'); return; }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'pet_events_' + new Date().toISOString().slice(0, 10) + '.json';
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) { alert('导出失败: ' + err.message); }
}

// ===== Auth =====
function getToken() { return localStorage.getItem("pet_token"); }
function setToken(t) { localStorage.setItem("pet_token", t); }
function clearToken() { localStorage.removeItem("pet_token"); }
function getCurrentUser() {
  try { return JSON.parse(localStorage.getItem("pet_user")); }
  catch { return null; }
}

// Override API client to add auth header
const origGet = api.get;
const origPost = api.post;
const origPut = api.put;
const origDel = api.del;

api.get = async function(path) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  const r = await fetch(API_BASE + path, { headers });
  if (r.status === 401) { clearToken(); showLoginPage(); return {}; }
  return r.json();
};

api.post = async function(path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  const r = await fetch(API_BASE + path, { method: "POST", headers, body: JSON.stringify(body) });
  if (r.status === 401) { clearToken(); showLoginPage(); return {}; }
  return r.json();
};

api.put = async function(path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  const r = await fetch(API_BASE + path, { method: "PUT", headers, body: JSON.stringify(body) });
  if (r.status === 401) { clearToken(); showLoginPage(); return {}; }
  return r.json();
};

api.del = async function(path) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  const r = await fetch(API_BASE + path, { method: "DELETE", headers });
  if (r.status === 401) { clearToken(); showLoginPage(); return {}; }
  return r.json();
};

async function login() {
  const username = document.getElementById("login-username").value;
  const password = document.getElementById("login-password").value;
  if (!username || !password) { document.getElementById("login-error").textContent = "请输入用户名和密码"; return; }
  document.getElementById("login-error").textContent = "登录中...";
  try {
    const r = await fetch(API_BASE + "/api/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await r.json();
    if (!r.ok) { document.getElementById("login-error").textContent = data.detail || "登录失败"; return; }
    setToken(data.access_token);
    localStorage.setItem("pet_user", JSON.stringify(data.user));
    hideLoginPage();
    loadDashboard();
  } catch (err) { document.getElementById("login-error").textContent = "网络错误: " + err.message; }
}

async function register() {
  const username = document.getElementById("reg-username").value;
  const email = document.getElementById("reg-email").value;
  const password = document.getElementById("reg-password").value;
  const display_name = document.getElementById("reg-displayname").value;
  if (!username || !email || !password) { document.getElementById("register-error").textContent = "请填写必填字段"; return; }
  document.getElementById("register-error").textContent = "注册中...";
  try {
    const r = await fetch(API_BASE + "/api/auth/register", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password, display_name }),
    });
    const data = await r.json();
    if (!r.ok) { document.getElementById("register-error").textContent = data.detail || "注册失败"; return; }
    setToken(data.access_token);
    localStorage.setItem("pet_user", JSON.stringify(data.user));
    hideLoginPage();
    loadDashboard();
  } catch (err) { document.getElementById("register-error").textContent = "网络错误: " + err.message; }
}

function showRegister() {
  document.getElementById("login-form").style.display = "none";
  document.getElementById("register-form").style.display = "block";
  document.getElementById("login-error").textContent = "";
  document.getElementById("register-error").textContent = "";
}

function showLogin() {
  document.getElementById("login-form").style.display = "block";
  document.getElementById("register-form").style.display = "none";
  document.getElementById("login-error").textContent = "";
  document.getElementById("register-error").textContent = "";
}

function showLoginPage() {
  document.querySelectorAll(".nav-item").forEach((n) => n.style.display = "none");
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.getElementById("page-login").classList.add("active");
  document.getElementById("page-title").textContent = "登录";
  document.getElementById("sidebar-footer").innerHTML = "";
  document.getElementById("btn-refresh").style.display = "none";
}

function hideLoginPage() {
  document.querySelectorAll(".nav-item").forEach((n) => n.style.display = "");
  document.getElementById("page-login").classList.remove("active");
  document.getElementById("sidebar-footer").innerHTML = '<span id="ws-status" class="status-dot offline"></span><span id="ws-status-text">未连接</span>';
  document.getElementById("btn-refresh").style.display = "";
  const user = getCurrentUser();
  if (user) {
    document.getElementById("sidebar-footer").innerHTML += "<span style=\"margin-left:auto;font-size:11px;opacity:0.7\">" + (user.display_name || user.username) + "</span>";
  }
}

// Override init to check auth
const origInit = window.onload || function(){};
window.onload = function() {
  const token = getToken();
  if (token) {
    hideLoginPage();
    connectWS();
    loadDashboard();
  } else {
    showLoginPage();
  }
};
