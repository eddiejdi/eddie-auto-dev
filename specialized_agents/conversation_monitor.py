#!/usr/bin/env python3
import streamlit as st
import streamlit.components.v1 as components
import os
import requests
import html as _html

# Minimal rolling conversations view — server-side fetch to avoid CORS.
# Default to homelab host. Use the sidebar input to override at runtime when needed.
INTERCEPTOR_API = os.environ.get("INTERCEPTOR_API", "http://192.168.15.2:8503")

st.set_page_config(page_title="Conversations", layout="wide", initial_sidebar_state="expanded")

# Allow overriding the interceptor API at runtime via sidebar (useful when viewing from laptop).
with st.sidebar:
    user_api = st.text_input('Interceptor API', value=INTERCEPTOR_API, help='URL do serviço interceptor (ex: http://192.168.15.2:8503)')
    if user_api:
        INTERCEPTOR_API = user_api.rstrip('/')

def fetch_conversations():
    try:
        r = requests.get(f"{INTERCEPTOR_API}/interceptor/conversations/active", timeout=3)
        r.raise_for_status()
        data = r.json()
        return data.get("conversations", [])
    except Exception as e:
        return {"error": str(e)}

convs = fetch_conversations()

colors = ['#a8dadc','#ffd6a5','#caffbf','#bdb2ff','#ffc6ff','#ffdbe7','#ffe8d6','#f8d49f']

def fetch_last_message(conv_id: str):
    try:
        r = requests.get(f"{INTERCEPTOR_API}/interceptor/conversations/{conv_id}/messages?limit=1", timeout=2)
        r.raise_for_status()
        data = r.json()
        msgs = data.get('messages') or []
        if msgs:
            m = msgs[-1]
            # messages may be dicts or objects; handle dict
            if isinstance(m, dict):
                return m.get('content') or m.get('message') or str(m)
            else:
                return getattr(m, 'content', str(m))
    except Exception:
        return ''

if isinstance(convs, dict) and convs.get("error"):
    body = f"Erro ao buscar conversas: {_html.escape(convs.get('error'))}"
else:
    parts = []
    for i, c in enumerate(convs):
        conv_id = c.get('id') or c.get('conversation_id')
        p = c.get('participants') or []
        frm = p[0] if len(p) > 0 else 'agent1'
        to = p[1] if len(p) > 1 else (p[0] if p else 'all')
        # fetch last message content from interceptor API
        preview = fetch_last_message(conv_id) if conv_id else ''
        text = f"{_html.escape(frm)} -> {_html.escape(to)}: {_html.escape(str(preview))}"
        color = colors[i % len(colors)]
        parts.append(f"<div class=\"conv\" style=\"background:{color};padding:10px;margin:6px 0;border-radius:6px;\">{text}</div>")
    body = '\n'.join(parts) if parts else '<div style="color:#fff;padding:10px">Nenhuma conversa ativa</div>'

API = INTERCEPTOR_API
WS = API.replace('http://', 'ws://').replace('https://', 'wss://') + '/interceptor/ws/messages'

template = """
<!doctype html>
<html>
<head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>Conversations (live)</title>
    <style>
        html,body{height:100%;margin:0;background:#0b1220;color:#000;font-family:Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial}
        #box{padding:12px;box-sizing:border-box;max-width:1200px;margin:8px auto;}
        .conv{white-space:pre-wrap;font-weight:600;padding:10px;margin:6px 0;border-radius:8px;transition:background-color .12s linear}
        .text{display:block;color:#111}
        .meta{font-size:12px;color:#333;margin-top:6px}
    </style>
</head>
<body>
        <div style="max-width:1200px;margin:8px auto;padding:8px;display:flex;align-items:center;justify-content:space-between;">
            <div style="color:#fff;font-weight:700">Conversations (live)</div>
            <div id="ws-status" style="padding:6px 10px;border-radius:8px;background:#ff9800;color:#fff;font-weight:600;font-size:13px">WS: connecting</div>
        </div>
        <div id="box">__BODY__</div>

    <script>
    const API = "__API__";
    const WS_URL = "__WS__";
    const CONV_API = API + '/interceptor/conversations/active';

    function setStatus(text, bg){
        try{
            const s = document.getElementById('ws-status');
            if(s){ s.textContent = 'WS: ' + text; s.style.background = bg; }
        }catch(e){ }
    }

    function createConvElement(id, color, text){
        const el = document.createElement('div');
        el.className = 'conv';
        el.style.background = color;
        el.id = 'conv-' + id;
        const span = document.createElement('div');
        span.className = 'text';
        span.textContent = text;
        el.appendChild(span);
        return el;
    }

    async function fetchInitial(){
        // No-op: initial conversation HTML is already rendered server-side
        return;
    }

    function updateMessage(msg){
        const cid = msg.conversation_id || msg.conversationId || msg.conversation || 'unknown';
        const source = msg.source || msg.from || '';
        const target = msg.target || msg.to || '';
        const content = msg.content || msg.message || '';
        const id = 'conv-' + cid;
        const existing = document.getElementById(id);
        const text = source + ' -> ' + target + ': ' + content;
        if(existing){
            const span = existing.querySelector('.text');
            if(span) span.textContent = text;
            existing.style.opacity = '0.98';
            setTimeout(()=> existing.style.opacity = '1', 60);
        } else {
            const color = '#caffbf';
            const el = createConvElement(cid, color, text);
            const box = document.getElementById('box');
            box.insertBefore(el, box.firstChild);
        }
    }

    function connectWS(){
        try{
            setStatus('connecting', '#ff9800');
            const ws = new WebSocket(WS_URL);
            ws.onopen = ()=> { console.log('ws open'); setStatus('connected', '#4caf50'); };
            ws.onmessage = (evt)=>{
                try{
                    const data = JSON.parse(evt.data);
                    if(Array.isArray(data)){
                        data.forEach(d=>updateMessage(d));
                    } else if(data.message || data.content || data.conversation_id){
                        updateMessage(data);
                    } else if(data.type === 'conversation_event' && data.payload){
                        updateMessage(data.payload);
                    }
                }catch(e){console.warn('ws parse', e, evt.data)}
            };
            ws.onclose = ()=>{ console.log('ws closed, reconnecting'); setStatus('disconnected', '#f44336'); setTimeout(connectWS, 2000); };
            ws.onerror = (e)=>{ console.warn('ws error', e); setStatus('error', '#f44336'); ws.close(); };
        }catch(e){ console.warn('ws connect error', e); }
    }

    fetchInitial();
    connectWS();

    // Polling removed to avoid cross-origin fetches from the browser; rely on WebSocket updates

    </script>
</body>
</html>
"""

html = template.replace('__API__', API).replace('__WS__', WS).replace('__BODY__', body)

# Render a taller component so the live conversation feed fills the page.
components.html(html, height=800, scrolling=True)

# Replace blocking polling with an inject-button for test messages stored in session_state
if 'injected_messages' not in st.session_state:
    st.session_state.injected_messages = []

col1, col2 = st.columns([1, 3])
with col1:
    if st.button('Inject test message'):
        import time as _t
        ts = _t.strftime('%Y%m%d%H%M%S')
        conv_id = f'test_injected_{ts}'
        st.session_state.injected_messages.insert(0, {
            'id': conv_id,
            'participants': ['TestAgent','Dashboard'],
            'preview': f'INJECTED_TEST_MESSAGE_{ts}'
        })
with col2:
    st.write('Use this to simulate live updates (local only).')

# When rendering, include injected messages at the top
if st.session_state.injected_messages:
    injected_parts = []
    for i, c in enumerate(st.session_state.injected_messages):
        frm = (c.get('participants') or ['TestAgent'])[0]
        to = (c.get('participants') or ['Dashboard'])[1] if len(c.get('participants',[]))>1 else 'Dashboard'
        preview = c.get('preview','')
        color = colors[i % len(colors)]
        injected_parts.append(f"<div class=\"conv\" style=\"background:{color};padding:10px;margin:6px 0;border-radius:6px;\">{_html.escape(frm)} -> {_html.escape(to)}: {_html.escape(preview)}</div>")
    # display injected messages above the component content by rendering another small HTML block
    components.html("""<div style='max-width:1200px;margin:8px auto;">""" + '\n'.join(injected_parts) + "</div>", height=160, scrolling=True)
