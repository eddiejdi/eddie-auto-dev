/**
 * RPA4ALL Chat Widget — Self-contained chat widget with Telegram integration.
 * 
 * Usage:
 *   <script src="chat-widget.js" data-api="https://estouaqui.rpa4all.com/api/webchat" data-source="rpa4all.com"></script>
 */
(function () {
  'use strict';

  // ─── Config ────────────────────────────────────────────────────────────────────
  const scriptTag = document.currentScript;
  const API_URL = (scriptTag && scriptTag.getAttribute('data-api')) || 'https://estouaqui.rpa4all.com/api/webchat';
  const SOURCE = (scriptTag && scriptTag.getAttribute('data-source')) || 'rpa4all.com';
  const POLL_INTERVAL = 4000; // 4 seconds
  const SESSION_KEY = 'rpa_chat_session';
  const NAME_KEY = 'rpa_chat_name';

  let sessionId = localStorage.getItem(SESSION_KEY) || null;
  let userName = localStorage.getItem(NAME_KEY) || '';
  let isOpen = false;
  let pollTimer = null;
  let lastMsgTimestamp = null;
  let unreadCount = 0;
  let messageCount = 0;

  // ─── Inject CSS ────────────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    #rpa-chat-toggle {
      position: fixed; bottom: 24px; right: 24px; z-index: 99999;
      width: 60px; height: 60px; border-radius: 50%;
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      border: none; cursor: pointer;
      box-shadow: 0 4px 24px rgba(59,130,246,0.4), 0 0 0 0 rgba(59,130,246,0.4);
      display: flex; align-items: center; justify-content: center;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
      animation: rpa-pulse 2.5s infinite;
    }
    #rpa-chat-toggle:hover {
      transform: scale(1.1);
      box-shadow: 0 6px 32px rgba(59,130,246,0.6);
    }
    #rpa-chat-toggle svg { width: 28px; height: 28px; fill: white; }
    #rpa-chat-toggle .badge {
      position: absolute; top: -4px; right: -4px;
      width: 22px; height: 22px; border-radius: 50%;
      background: #ef4444; color: white; font-size: 12px; font-weight: 700;
      display: none; align-items: center; justify-content: center;
      font-family: 'Inter', sans-serif;
    }
    #rpa-chat-toggle .badge.visible { display: flex; }
    @keyframes rpa-pulse {
      0% { box-shadow: 0 4px 24px rgba(59,130,246,0.4), 0 0 0 0 rgba(59,130,246,0.4); }
      50% { box-shadow: 0 4px 24px rgba(59,130,246,0.4), 0 0 0 12px rgba(59,130,246,0); }
      100% { box-shadow: 0 4px 24px rgba(59,130,246,0.4), 0 0 0 0 rgba(59,130,246,0); }
    }

    #rpa-chat-box {
      position: fixed; bottom: 96px; right: 24px; z-index: 99999;
      width: 380px; max-width: calc(100vw - 32px);
      height: 520px; max-height: calc(100vh - 120px);
      border-radius: 16px;
      background: rgba(15, 20, 38, 0.96);
      backdrop-filter: blur(24px);
      border: 1px solid rgba(255,255,255,0.08);
      box-shadow: 0 16px 64px rgba(0,0,0,0.5), 0 0 0 1px rgba(59,130,246,0.1);
      display: flex; flex-direction: column;
      opacity: 0; transform: translateY(20px) scale(0.95);
      pointer-events: none;
      transition: opacity 0.3s ease, transform 0.3s ease;
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      overflow: hidden;
    }
    #rpa-chat-box.open {
      opacity: 1; transform: translateY(0) scale(1);
      pointer-events: auto;
    }

    .rpa-chat-header {
      padding: 16px 20px;
      background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(37,99,235,0.08));
      border-bottom: 1px solid rgba(255,255,255,0.06);
      display: flex; align-items: center; justify-content: space-between;
    }
    .rpa-chat-header-info { display: flex; align-items: center; gap: 12px; }
    .rpa-chat-avatar {
      width: 36px; height: 36px; border-radius: 50%;
      background: linear-gradient(135deg, #3b82f6, #8b5cf6);
      display: flex; align-items: center; justify-content: center;
      font-size: 16px;
    }
    .rpa-chat-header-text h4 {
      margin: 0; font-size: 14px; font-weight: 600; color: #e8edf5;
    }
    .rpa-chat-header-text small {
      font-size: 11px; color: #22c55e;
    }
    .rpa-chat-close {
      background: none; border: none; cursor: pointer;
      color: #8896b0; font-size: 24px; line-height: 1;
      padding: 4px; border-radius: 8px;
      transition: color 0.2s, background 0.2s;
    }
    .rpa-chat-close:hover { color: #e8edf5; background: rgba(255,255,255,0.06); }

    .rpa-chat-messages {
      flex: 1; overflow-y: auto; padding: 16px;
      display: flex; flex-direction: column; gap: 12px;
    }
    .rpa-chat-messages::-webkit-scrollbar { width: 4px; }
    .rpa-chat-messages::-webkit-scrollbar-track { background: transparent; }
    .rpa-chat-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

    .rpa-chat-welcome {
      text-align: center; padding: 20px 16px;
      color: #8896b0; font-size: 13px; line-height: 1.5;
    }
    .rpa-chat-welcome .emoji { font-size: 32px; margin-bottom: 8px; }
    .rpa-chat-welcome strong { color: #e8edf5; }

    .rpa-msg {
      max-width: 85%; padding: 10px 14px;
      border-radius: 14px; font-size: 13px; line-height: 1.5;
      word-wrap: break-word; position: relative;
    }
    .rpa-msg.incoming {
      align-self: flex-end;
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      color: white;
      border-bottom-right-radius: 4px;
    }
    .rpa-msg.outgoing {
      align-self: flex-start;
      background: rgba(255,255,255,0.06);
      color: #e8edf5;
      border-bottom-left-radius: 4px;
      border: 1px solid rgba(255,255,255,0.06);
    }
    .rpa-msg .rpa-msg-time {
      font-size: 10px; margin-top: 4px; display: block;
      opacity: 0.6;
    }
    .rpa-msg.incoming .rpa-msg-time { text-align: right; }
    .rpa-msg.outgoing .rpa-msg-time { text-align: left; }
    .rpa-msg.outgoing .rpa-msg-sender {
      font-size: 11px; font-weight: 600; color: #3b82f6;
      margin-bottom: 2px;
    }

    .rpa-chat-name-prompt {
      padding: 20px 16px; text-align: center;
    }
    .rpa-chat-name-prompt p {
      color: #8896b0; font-size: 13px; margin-bottom: 12px;
    }
    .rpa-chat-name-prompt input {
      width: 100%; padding: 10px 14px; border-radius: 10px;
      background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
      color: #e8edf5; font-size: 14px; outline: none;
      font-family: inherit;
      transition: border-color 0.2s;
    }
    .rpa-chat-name-prompt input:focus { border-color: #3b82f6; }
    .rpa-chat-name-prompt button {
      margin-top: 10px; width: 100%; padding: 10px;
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      color: white; border: none; border-radius: 10px; cursor: pointer;
      font-weight: 600; font-size: 14px; font-family: inherit;
      transition: opacity 0.2s;
    }
    .rpa-chat-name-prompt button:hover { opacity: 0.9; }

    .rpa-chat-input-area {
      padding: 12px 16px;
      border-top: 1px solid rgba(255,255,255,0.06);
      display: flex; gap: 8px; align-items: flex-end;
      background: rgba(10,14,26,0.5);
    }
    .rpa-chat-input-area textarea {
      flex: 1; padding: 10px 14px; border-radius: 12px;
      background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
      color: #e8edf5; font-size: 14px; outline: none;
      font-family: inherit; resize: none;
      min-height: 40px; max-height: 100px;
      transition: border-color 0.2s;
      line-height: 1.4;
    }
    .rpa-chat-input-area textarea:focus { border-color: #3b82f6; }
    .rpa-chat-input-area textarea::placeholder { color: #5a6785; }
    .rpa-chat-send {
      width: 40px; height: 40px; border-radius: 50%;
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: opacity 0.2s, transform 0.2s;
      flex-shrink: 0;
    }
    .rpa-chat-send:hover { opacity: 0.9; transform: scale(1.05); }
    .rpa-chat-send:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
    .rpa-chat-send svg { width: 18px; height: 18px; fill: white; }

    .rpa-typing {
      align-self: flex-start;
      background: rgba(255,255,255,0.06);
      border-radius: 14px 14px 14px 4px;
      padding: 12px 18px;
      display: none;
    }
    .rpa-typing.visible { display: flex; gap: 4px; }
    .rpa-typing span {
      width: 6px; height: 6px; border-radius: 50%;
      background: #5a6785;
      animation: rpa-typing-dot 1.4s infinite;
    }
    .rpa-typing span:nth-child(2) { animation-delay: 0.2s; }
    .rpa-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes rpa-typing-dot {
      0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
      30% { transform: translateY(-6px); opacity: 1; }
    }

    .rpa-chat-powered {
      padding: 6px; text-align: center;
      font-size: 10px; color: #5a6785;
      border-top: 1px solid rgba(255,255,255,0.03);
    }
    .rpa-chat-powered a { color: #3b82f6; text-decoration: none; }

    @media (max-width: 480px) {
      #rpa-chat-box {
        bottom: 0; right: 0; left: 0;
        width: 100%; max-width: 100%;
        height: 100vh; max-height: 100vh;
        border-radius: 0;
      }
      #rpa-chat-toggle { bottom: 16px; right: 16px; width: 52px; height: 52px; }
      #rpa-chat-toggle svg { width: 24px; height: 24px; }
    }
  `;
  document.head.appendChild(style);

  // ─── Create DOM ────────────────────────────────────────────────────────────────
  const chatSVG = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>';
  const sendSVG = '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  const closeSVG = '✕';

  // Toggle button
  const toggleBtn = document.createElement('button');
  toggleBtn.id = 'rpa-chat-toggle';
  toggleBtn.setAttribute('aria-label', 'Abrir chat');
  toggleBtn.innerHTML = chatSVG + '<span class="badge">0</span>';
  document.body.appendChild(toggleBtn);

  // Chat box
  const chatBox = document.createElement('div');
  chatBox.id = 'rpa-chat-box';
  chatBox.innerHTML = `
    <div class="rpa-chat-header">
      <div class="rpa-chat-header-info">
        <div class="rpa-chat-avatar">💬</div>
        <div class="rpa-chat-header-text">
          <h4>Chat RPA4ALL</h4>
          <small>● Online — respondemos rápido</small>
        </div>
      </div>
      <button class="rpa-chat-close" aria-label="Fechar chat">${closeSVG}</button>
    </div>
    <div class="rpa-chat-messages" id="rpa-chat-messages">
      <div class="rpa-chat-welcome">
        <div class="emoji">👋</div>
        <strong>Olá! Como podemos ajudar?</strong><br>
        Envie sua mensagem e responderemos o mais rápido possível.
      </div>
    </div>
    <div class="rpa-typing" id="rpa-typing">
      <span></span><span></span><span></span>
    </div>
    <div class="rpa-chat-name-prompt" id="rpa-name-prompt" style="display:none;">
      <p>Antes de começar, como podemos te chamar?</p>
      <input type="text" id="rpa-name-input" placeholder="Seu nome..." maxlength="50">
      <button id="rpa-name-btn">Iniciar conversa</button>
    </div>
    <div class="rpa-chat-input-area" id="rpa-input-area" style="display:none;">
      <textarea id="rpa-msg-input" placeholder="Digite sua mensagem..." rows="1"></textarea>
      <button class="rpa-chat-send" id="rpa-send-btn" aria-label="Enviar">${sendSVG}</button>
    </div>
    <div class="rpa-chat-powered">
      Powered by <a href="https://www.rpa4all.com" target="_blank">RPA4ALL</a>
    </div>
  `;
  document.body.appendChild(chatBox);

  // ─── References ────────────────────────────────────────────────────────────────
  const messagesEl = document.getElementById('rpa-chat-messages');
  const namePrompt = document.getElementById('rpa-name-prompt');
  const nameInput = document.getElementById('rpa-name-input');
  const nameBtn = document.getElementById('rpa-name-btn');
  const inputArea = document.getElementById('rpa-input-area');
  const msgInput = document.getElementById('rpa-msg-input');
  const sendBtn = document.getElementById('rpa-send-btn');
  const badge = toggleBtn.querySelector('.badge');

  // ─── Event Handlers ───────────────────────────────────────────────────────────
  toggleBtn.addEventListener('click', toggleChat);
  chatBox.querySelector('.rpa-chat-close').addEventListener('click', toggleChat);

  nameBtn.addEventListener('click', submitName);
  nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') submitName(); });

  sendBtn.addEventListener('click', sendMessage);
  msgInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  msgInput.addEventListener('input', autoResize);

  function toggleChat() {
    isOpen = !isOpen;
    chatBox.classList.toggle('open', isOpen);
    toggleBtn.style.animation = isOpen ? 'none' : '';

    if (isOpen) {
      if (userName) {
        showInputArea();
        loadMessages();
        startPolling();
      } else {
        namePrompt.style.display = 'block';
        inputArea.style.display = 'none';
        setTimeout(() => nameInput.focus(), 300);
      }
      unreadCount = 0;
      updateBadge();
    } else {
      stopPolling();
    }
  }

  function submitName() {
    const name = nameInput.value.trim();
    if (!name) return;
    userName = name;
    localStorage.setItem(NAME_KEY, userName);
    namePrompt.style.display = 'none';
    showInputArea();
    loadMessages();
    startPolling();
  }

  function showInputArea() {
    inputArea.style.display = 'flex';
    setTimeout(() => msgInput.focus(), 100);
  }

  function autoResize() {
    msgInput.style.height = 'auto';
    msgInput.style.height = Math.min(msgInput.scrollHeight, 100) + 'px';
  }

  async function sendMessage() {
    const text = msgInput.value.trim();
    if (!text) return;

    sendBtn.disabled = true;
    msgInput.value = '';
    msgInput.style.height = 'auto';

    // Adicionar mensagem localmente (optimistic)
    appendMessage('incoming', text, userName, new Date().toISOString());

    try {
      const resp = await fetch(API_URL + '/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          sessionId: sessionId,
          senderName: userName,
          source: SOURCE,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || 'Erro ao enviar');
      }

      const data = await resp.json();
      if (!sessionId) {
        sessionId = data.sessionId;
        localStorage.setItem(SESSION_KEY, sessionId);
      }
      messageCount++;
    } catch (err) {
      appendSystemMessage('❌ ' + (err.message || 'Erro ao enviar. Tente novamente.'));
    }

    sendBtn.disabled = false;
    msgInput.focus();
  }

  async function loadMessages() {
    if (!sessionId) return;
    try {
      const resp = await fetch(API_URL + '/messages/' + sessionId);
      if (!resp.ok) return;
      const data = await resp.json();

      // Limpar welcome se houver mensagens
      if (data.messages && data.messages.length > 0) {
        const welcome = messagesEl.querySelector('.rpa-chat-welcome');
        if (welcome) welcome.remove();

        // Limpar mensagens existentes (evitar duplicatas)
        messagesEl.innerHTML = '';
        messageCount = 0;

        data.messages.forEach(msg => {
          appendMessage(msg.direction, msg.message, msg.senderName, msg.createdAt);
        });

        // Definir lastMsgTimestamp como a última mensagem
        const lastMsg = data.messages[data.messages.length - 1];
        lastMsgTimestamp = lastMsg.createdAt;
      }
    } catch (err) {
      console.error('[rpa-chat] Load error:', err);
    }
  }

  async function pollMessages() {
    if (!sessionId) return;
    try {
      const url = lastMsgTimestamp
        ? API_URL + '/messages/' + sessionId + '?since=' + encodeURIComponent(lastMsgTimestamp)
        : API_URL + '/messages/' + sessionId;

      const resp = await fetch(url);
      if (!resp.ok) return;
      const data = await resp.json();

      if (data.messages && data.messages.length > 0) {
        data.messages.forEach(msg => {
          appendMessage(msg.direction, msg.message, msg.senderName, msg.createdAt);
          if (msg.direction === 'outgoing' && !isOpen) {
            unreadCount++;
            updateBadge();
          }
        });
        const lastMsg = data.messages[data.messages.length - 1];
        lastMsgTimestamp = lastMsg.createdAt;

        // Notify com som de notificação se tiver msg do admin
        const hasAdminMsg = data.messages.some(m => m.direction === 'outgoing');
        if (hasAdminMsg && !isOpen) {
          unreadCount += data.messages.filter(m => m.direction === 'outgoing').length;
          updateBadge();
          notifySound();
        }
      }
    } catch (err) {
      console.error('[rpa-chat] Poll error:', err);
    }
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(pollMessages, POLL_INTERVAL);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  function appendMessage(direction, text, sender, timestamp) {
    const welcome = messagesEl.querySelector('.rpa-chat-welcome');
    if (welcome) welcome.remove();

    const el = document.createElement('div');
    el.className = 'rpa-msg ' + direction;

    const time = timestamp ? new Date(timestamp) : new Date();
    const timeStr = time.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

    if (direction === 'outgoing') {
      el.innerHTML = `<div class="rpa-msg-sender">${escapeHtml(sender || 'Admin')}</div>` +
        escapeHtml(text) + `<span class="rpa-msg-time">${timeStr}</span>`;
    } else {
      el.innerHTML = escapeHtml(text) + `<span class="rpa-msg-time">${timeStr}</span>`;
    }

    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    messageCount++;
  }

  function appendSystemMessage(text) {
    const el = document.createElement('div');
    el.style.cssText = 'text-align:center;color:#8896b0;font-size:12px;padding:8px;';
    el.textContent = text;
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function updateBadge() {
    badge.textContent = unreadCount;
    badge.classList.toggle('visible', unreadCount > 0);
  }

  function notifySound() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 800;
      gain.gain.value = 0.1;
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
      setTimeout(() => {
        const o2 = ctx.createOscillator();
        const g2 = ctx.createGain();
        o2.connect(g2);
        g2.connect(ctx.destination);
        o2.frequency.value = 1000;
        g2.gain.value = 0.1;
        o2.start();
        o2.stop(ctx.currentTime + 0.15);
      }, 180);
    } catch (e) { /* audio not available */ }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ─── On load: restaurar sessão ─────────────────────────────────────────────────
  if (sessionId) {
    // Sessão existente — iniciar polling mesmo com chat fechado
    startPolling();
  }
})();
