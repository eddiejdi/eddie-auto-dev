"""
Dashboard Web em Tempo Real - Conversas de Agentes + Precisão
Acesso: http://localhost:8504 (ou http://192.168.15.2:8504 em PROD)
"""
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
from datetime import datetime
import httpx

app = FastAPI(title="Eddie Auto-Dev Dashboard")

# Configuração
API_URL = "http://localhost:8503"  # Mudar para 192.168.15.2:8503 em PROD

# HTML do Dashboard
HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eddie Auto-Dev - Dashboard Tempo Real</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .status {
            display: inline-block;
            padding: 10px 20px;
            background: #10b981;
            border-radius: 20px;
            font-weight: bold;
            margin-top: 10px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        .card h2 {
            color: #60a5fa;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        
        .conversations {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .conversation {
            background: #0f172a;
            padding: 15px;
            border-left: 4px solid #60a5fa;
            border-radius: 5px;
            transition: all 0.3s ease;
        }
        
        .conversation:hover {
            background: #1e293b;
            transform: translateX(5px);
        }
        
        .conversation .id {
            font-family: monospace;
            font-size: 0.9em;
            color: #94a3b8;
        }
        
        .conversation .phase {
            display: inline-block;
            padding: 4px 12px;
            background: #3b82f6;
            border-radius: 15px;
            font-size: 0.85em;
            margin-top: 8px;
        }
        
        .agents {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .agent {
            background: #0f172a;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #334155;
        }
        
        .agent .name {
            font-weight: bold;
            margin-bottom: 10px;
            color: #60a5fa;
        }
        
        .agent .precision {
            font-size: 2em;
            font-weight: bold;
            color: #10b981;
            margin: 10px 0;
        }
        
        .agent .copilot {
            font-size: 0.9em;
            color: #f59e0b;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #334155;
            border-radius: 4px;
            margin: 10px 0;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #10b981, #06b6d4);
            width: 0%;
            transition: width 0.3s ease;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .stat {
            background: #0f172a;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #334155;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #60a5fa;
        }
        
        .stat-label {
            font-size: 0.9em;
            color: #94a3b8;
            margin-top: 5px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #94a3b8;
        }
        
        .error {
            background: #7f1d1d;
            color: #fecaca;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            .stats {
                grid-template-columns: 1fr 1fr;
            }
            h1 {
                font-size: 1.8em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Eddie Auto-Dev Dashboard</h1>
            <div class="status" id="status">Conectando...</div>
        </header>
        
        <!-- Estatísticas Gerais -->
        <div class="stats" id="stats">
            <div class="stat">
                <div class="stat-value" id="conv-count">0</div>
                <div class="stat-label">Conversas Ativas</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="msg-count">0</div>
                <div class="stat-label">Mensagens</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="agent-count">0</div>
                <div class="stat-label">Agentes Monitorados</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="avg-precision">0%</div>
                <div class="stat-label">Precisão Média</div>
            </div>
        </div>
        
        <!-- Grid Principal -->
        <div class="grid">
            <!-- Conversas -->
            <div class="card">
                <h2>💬 Conversas em Tempo Real</h2>
                <div class="conversations" id="conversations">
                    <div class="loading">Carregando conversas...</div>
                </div>
            </div>
            
            <!-- Precisão dos Agentes -->
            <div class="card">
                <h2>🎯 Precisão dos Agentes</h2>
                <div class="agents" id="agents">
                    <div class="loading">Carregando agentes...</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const API = "http://localhost:8503";  // Mudar em PROD
        
        async function updateDashboard() {
            try {
                // 1. Atualizar conversas
                const convRes = await fetch(`${API}/interceptor/conversations/active`);
                const convData = await convRes.json();
                updateConversations(convData);
                
                // 2. Atualizar agentes
                const agentsRes = await fetch(`${API}/distributed/precision-dashboard`);
                const agentsData = await agentsRes.json();
                updateAgents(agentsData);
                
                // Status OK
                document.getElementById('status').textContent = '✅ Online';
                document.getElementById('status').style.background = '#10b981';
            } catch (error) {
                console.error('Erro ao atualizar:', error);
                document.getElementById('status').textContent = '❌ Desconectado';
                document.getElementById('status').style.background = '#ef4444';
            }
        }
        
        function updateConversations(data) {
            const container = document.getElementById('conversations');
            const count = data.count || 0;
            
            document.getElementById('conv-count').textContent = count;
            
            if (!data.conversations || data.conversations.length === 0) {
                container.innerHTML = '<div class="loading">Sem conversas ativas</div>';
                return;
            }
            
            let html = '';
            let totalMsgs = 0;
            
            data.conversations.forEach(conv => {
                totalMsgs += conv.message_count || 0;
                const time = new Date(conv.started_at).toLocaleTimeString('pt-BR');
                html += `
                    <div class="conversation">
                        <div class="id">ID: ${conv.id}</div>
                        <div>Participantes: ${conv.participants.join(', ')}</div>
                        <div>Mensagens: ${conv.message_count}</div>
                        <div>Duração: ${(conv.duration_seconds || 0).toFixed(1)}s</div>
                        <div class="phase">${conv.phase || 'planning'}</div>
                    </div>
                `;
            });
            
            document.getElementById('msg-count').textContent = totalMsgs;
            container.innerHTML = html;
        }
        
        function updateAgents(data) {
            const container = document.getElementById('agents');
            
            if (!data.agents || data.agents.length === 0) {
                container.innerHTML = '<div class="loading">Sem agentes</div>';
                return;
            }
            
            document.getElementById('agent-count').textContent = data.agents.length;
            
            let html = '';
            let totalPrecision = 0;
            
            data.agents.forEach(agent => {
                const precision = parseFloat(agent.precision) || 0;
                totalPrecision += precision;
                
                const copilot = parseFloat(agent.copilot_usage) || 100;
                const color = precision >= 95 ? '#10b981' : precision >= 85 ? '#f59e0b' : '#ef4444';
                
                html += `
                    <div class="agent">
                        <div class="name">${agent.language.toUpperCase()}</div>
                        <div class="precision" style="color: ${color}">${precision.toFixed(1)}%</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${precision}%"></div>
                        </div>
                        <div class="copilot">Copilot: ${copilot.toFixed(0)}%</div>
                        <div style="font-size: 0.85em; color: #94a3b8; margin-top: 8px;">
                            ${agent.total_tasks} tarefas (${agent.successful} OK)
                        </div>
                    </div>
                `;
            });
            
            const avgPrecision = data.agents.length > 0 ? (totalPrecision / data.agents.length).toFixed(1) : 0;
            document.getElementById('avg-precision').textContent = avgPrecision + '%';
            
            container.innerHTML = html;
        }
        
        // Atualizar a cada 2 segundos
        updateDashboard();
        setInterval(updateDashboard, 2000);
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTML

@app.get("/api/health")
async def health():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/health", timeout=5)
            return {"status": "ok" if response.status_code == 200 else "error"}
    except:
        return {"status": "error"}

if __name__ == "__main__":
    import uvicorn
    print("🎨 Dashboard rodando em http://localhost:8504")
    uvicorn.run(app, host="0.0.0.0", port=8504)
