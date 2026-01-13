#!/usr/bin/env python3
"""
SmartLife Control Panel - Painel Web de Configurações
Interface administrativa para gerenciar dispositivos e configurações Tuya/SmartLife
"""
import json
import time
import hmac
import hashlib
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# Configuração
CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_DIR.mkdir(exist_ok=True)

TUYA_URLS = {
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com", 
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com"
}

app = FastAPI(
    title="SmartLife Control Panel",
    description="Painel de controle para dispositivos SmartLife/Tuya",
    version="1.0.0"
)


# ============================================================================
# Tuya API Client
# ============================================================================

class TuyaCloudClient:
    """Cliente para Tuya Cloud API."""
    
    def __init__(self, access_id: str, access_secret: str, region: str = "us"):
        self.access_id = access_id
        self.access_secret = access_secret
        self.base_url = TUYA_URLS.get(region, TUYA_URLS["us"])
        self.token = None
        self.token_expire = 0
    
    def _sign(self, t: str, token: str = "") -> str:
        """Gera assinatura HMAC-SHA256."""
        str_to_sign = self.access_id + token + t
        return hmac.new(
            self.access_secret.encode('utf-8'),
            str_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
    
    def _get_headers(self, with_token: bool = True) -> dict:
        """Gera headers para requisição."""
        t = str(int(time.time() * 1000))
        token = self.token if with_token and self.token else ""
        
        return {
            "client_id": self.access_id,
            "sign": self._sign(t, token),
            "t": t,
            "sign_method": "HMAC-SHA256",
            "access_token": token
        }
    
    def get_token(self) -> dict:
        """Obtém token de acesso."""
        headers = self._get_headers(with_token=False)
        url = f"{self.base_url}/v1.0/token?grant_type=1"
        
        response = requests.get(url, headers=headers, timeout=10)
        result = response.json()
        
        if result.get("success"):
            self.token = result["result"]["access_token"]
            self.token_expire = time.time() + result["result"]["expire_time"]
        
        return result
    
    def ensure_token(self):
        """Garante que há um token válido."""
        if not self.token or time.time() >= self.token_expire - 60:
            self.get_token()
    
    def get_user_devices(self) -> dict:
        """Lista dispositivos do usuário vinculado."""
        self.ensure_token()
        headers = self._get_headers()
        url = f"{self.base_url}/v1.0/users/devices"
        
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    
    def get_device_info(self, device_id: str) -> dict:
        """Obtém informações de um dispositivo."""
        self.ensure_token()
        headers = self._get_headers()
        url = f"{self.base_url}/v1.0/devices/{device_id}"
        
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    
    def get_device_status(self, device_id: str) -> dict:
        """Obtém status atual de um dispositivo."""
        self.ensure_token()
        headers = self._get_headers()
        url = f"{self.base_url}/v1.0/devices/{device_id}/status"
        
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    
    def send_commands(self, device_id: str, commands: List[dict]) -> dict:
        """Envia comandos para um dispositivo."""
        self.ensure_token()
        
        t = str(int(time.time() * 1000))
        body = json.dumps({"commands": commands})
        
        # Sign para POST inclui body hash
        body_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
        path = f"/v1.0/devices/{device_id}/commands"
        
        string_to_hash = (
            self.access_id + self.token + t + 
            "POST\n" + body_hash + "\n\n" + path
        )
        
        sign = hmac.new(
            self.access_secret.encode('utf-8'),
            string_to_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        
        headers = {
            "client_id": self.access_id,
            "access_token": self.token,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{path}"
        response = requests.post(url, headers=headers, data=body, timeout=10)
        return response.json()


# ============================================================================
# Config Management
# ============================================================================

def load_config() -> dict:
    """Carrega configuração."""
    config_file = CONFIG_DIR / "tuya_cloud.json"
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {}

def save_config(config: dict):
    """Salva configuração."""
    config_file = CONFIG_DIR / "tuya_cloud.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

def get_client() -> Optional[TuyaCloudClient]:
    """Obtém cliente Tuya configurado."""
    config = load_config()
    if config.get("access_id") and config.get("access_secret"):
        return TuyaCloudClient(
            config["access_id"],
            config["access_secret"],
            config.get("region", "us")
        )
    return None


# ============================================================================
# HTML Templates (inline para simplicidade)
# ============================================================================

BASE_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - SmartLife Control Panel</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        :root {{
            --primary-color: #FF6B00;
            --dark-bg: #1a1a2e;
            --card-bg: #16213e;
        }}
        body {{
            background: var(--dark-bg);
            color: #fff;
            min-height: 100vh;
        }}
        .navbar {{
            background: var(--card-bg) !important;
            border-bottom: 2px solid var(--primary-color);
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid rgba(255, 107, 0, 0.3);
            border-radius: 15px;
        }}
        .card-header {{
            background: rgba(255, 107, 0, 0.1);
            border-bottom: 1px solid rgba(255, 107, 0, 0.3);
        }}
        .btn-primary {{
            background: var(--primary-color);
            border-color: var(--primary-color);
        }}
        .btn-primary:hover {{
            background: #ff8533;
            border-color: #ff8533;
        }}
        .device-card {{
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .device-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(255, 107, 0, 0.2);
        }}
        .status-online {{
            color: #00ff88;
        }}
        .status-offline {{
            color: #ff4444;
        }}
        .form-control, .form-select {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: #fff;
        }}
        .form-control:focus, .form-select:focus {{
            background: rgba(255, 255, 255, 0.15);
            border-color: var(--primary-color);
            color: #fff;
            box-shadow: 0 0 0 0.25rem rgba(255, 107, 0, 0.25);
        }}
        .table {{
            color: #fff;
        }}
        .alert-success {{
            background: rgba(0, 255, 136, 0.2);
            border-color: #00ff88;
            color: #00ff88;
        }}
        .alert-danger {{
            background: rgba(255, 68, 68, 0.2);
            border-color: #ff4444;
            color: #ff4444;
        }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark mb-4">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="bi bi-house-gear-fill me-2"></i>SmartLife Control Panel
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link {nav_home}" href="/"><i class="bi bi-speedometer2 me-1"></i>Dashboard</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {nav_devices}" href="/devices"><i class="bi bi-cpu me-1"></i>Dispositivos</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {nav_config}" href="/config"><i class="bi bi-gear me-1"></i>Configurações</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/docs"><i class="bi bi-book me-1"></i>API Docs</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    
    <div class="container">
        {content}
    </div>
    
    <footer class="text-center py-4 mt-5 text-muted">
        <small>SmartLife Control Panel v1.0 | Tuya Cloud API Integration</small>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Auto-refresh status
        function refreshDeviceStatus(deviceId) {{
            fetch(`/api/devices/${{deviceId}}/status`)
                .then(r => r.json())
                .then(data => {{
                    console.log('Status:', data);
                    location.reload();
                }});
        }}
        
        // Send command
        function sendCommand(deviceId, code, value) {{
            fetch(`/api/devices/${{deviceId}}/command`, {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{code: code, value: value}})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('Erro: ' + (data.msg || 'Comando falhou'));
                }}
            }});
        }}
        
        // Toggle device
        function toggleDevice(deviceId, currentState) {{
            sendCommand(deviceId, 'switch_1', !currentState);
        }}
    </script>
</body>
</html>
"""


# ============================================================================
# Web Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Página principal - Dashboard."""
    config = load_config()
    client = get_client()
    
    devices_html = ""
    stats = {"total": 0, "online": 0, "offline": 0}
    
    if client:
        try:
            result = client.get_user_devices()
            if result.get("success") and result.get("result"):
                devices = result["result"]
                stats["total"] = len(devices)
                
                for dev in devices[:6]:  # Mostrar até 6 no dashboard
                    is_online = dev.get("online", False)
                    stats["online" if is_online else "offline"] += 1
                    
                    status_class = "status-online" if is_online else "status-offline"
                    status_icon = "bi-wifi" if is_online else "bi-wifi-off"
                    status_text = "Online" if is_online else "Offline"
                    
                    # Ícone baseado na categoria
                    category = dev.get("category", "")
                    icon = {
                        "fs": "bi-fan",  # Fan/Ventilador
                        "dj": "bi-lightbulb",  # Light
                        "cz": "bi-plug",  # Socket/Tomada
                        "kg": "bi-toggle-on",  # Switch
                        "cl": "bi-thermometer",  # Sensor
                    }.get(category, "bi-cpu")
                    
                    devices_html += f"""
                    <div class="col-md-4 mb-3">
                        <div class="card device-card h-100">
                            <div class="card-body text-center">
                                <i class="bi {icon} display-4 mb-3" style="color: var(--primary-color);"></i>
                                <h5 class="card-title">{dev.get('name', 'Dispositivo')}</h5>
                                <p class="card-text">
                                    <span class="{status_class}">
                                        <i class="bi {status_icon}"></i> {status_text}
                                    </span>
                                </p>
                                <a href="/devices/{dev['id']}" class="btn btn-outline-light btn-sm">
                                    <i class="bi bi-gear"></i> Controlar
                                </a>
                            </div>
                        </div>
                    </div>
                    """
        except Exception as e:
            devices_html = f'<div class="alert alert-danger">Erro ao carregar dispositivos: {e}</div>'
    
    if not devices_html:
        devices_html = """
        <div class="col-12">
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle me-2"></i>
                Nenhum dispositivo encontrado. Verifique se você vinculou sua conta SmartLife na 
                <a href="https://iot.tuya.com" target="_blank">Tuya IoT Platform</a>.
            </div>
        </div>
        """
    
    content = f"""
    <div class="row mb-4">
        <div class="col-md-4">
            <div class="card text-center">
                <div class="card-body">
                    <i class="bi bi-cpu display-4" style="color: var(--primary-color);"></i>
                    <h2 class="mt-2">{stats['total']}</h2>
                    <p class="text-muted mb-0">Total Dispositivos</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card text-center">
                <div class="card-body">
                    <i class="bi bi-wifi display-4 status-online"></i>
                    <h2 class="mt-2">{stats['online']}</h2>
                    <p class="text-muted mb-0">Online</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card text-center">
                <div class="card-body">
                    <i class="bi bi-wifi-off display-4 status-offline"></i>
                    <h2 class="mt-2">{stats['offline']}</h2>
                    <p class="text-muted mb-0">Offline</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h5 class="mb-0"><i class="bi bi-lightning-charge me-2"></i>Dispositivos Recentes</h5>
        </div>
        <div class="card-body">
            <div class="row">
                {devices_html}
            </div>
            <div class="text-center mt-3">
                <a href="/devices" class="btn btn-primary">
                    <i class="bi bi-grid me-2"></i>Ver Todos os Dispositivos
                </a>
            </div>
        </div>
    </div>
    """
    
    return HTMLResponse(BASE_HTML.format(
        title="Dashboard",
        content=content,
        nav_home="active",
        nav_devices="",
        nav_config=""
    ))


@app.get("/devices", response_class=HTMLResponse)
async def devices_list():
    """Lista todos os dispositivos."""
    client = get_client()
    
    if not client:
        return RedirectResponse(url="/config?error=not_configured")
    
    devices_html = ""
    try:
        result = client.get_user_devices()
        if result.get("success") and result.get("result"):
            devices = result["result"]
            
            for dev in devices:
                is_online = dev.get("online", False)
                status_class = "status-online" if is_online else "status-offline"
                status_text = "Online" if is_online else "Offline"
                
                category = dev.get("category", "")
                icon = {
                    "fs": "bi-fan",
                    "dj": "bi-lightbulb", 
                    "cz": "bi-plug",
                    "kg": "bi-toggle-on",
                    "cl": "bi-thermometer",
                }.get(category, "bi-cpu")
                
                devices_html += f"""
                <tr>
                    <td><i class="bi {icon} me-2"></i>{dev.get('name', 'Dispositivo')}</td>
                    <td><code>{dev['id'][:16]}...</code></td>
                    <td>{dev.get('product_name', category)}</td>
                    <td><span class="{status_class}"><i class="bi bi-circle-fill me-1"></i>{status_text}</span></td>
                    <td>
                        <a href="/devices/{dev['id']}" class="btn btn-sm btn-primary">
                            <i class="bi bi-sliders"></i> Controlar
                        </a>
                    </td>
                </tr>
                """
        else:
            devices_html = f'<tr><td colspan="5" class="text-center">Erro: {result.get("msg", "Sem dispositivos")}</td></tr>'
    except Exception as e:
        devices_html = f'<tr><td colspan="5" class="text-center text-danger">Erro: {e}</td></tr>'
    
    content = f"""
    <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
            <h5 class="mb-0"><i class="bi bi-cpu me-2"></i>Todos os Dispositivos</h5>
            <button class="btn btn-sm btn-outline-light" onclick="location.reload()">
                <i class="bi bi-arrow-clockwise"></i> Atualizar
            </button>
        </div>
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Nome</th>
                            <th>Device ID</th>
                            <th>Tipo</th>
                            <th>Status</th>
                            <th>Ações</th>
                        </tr>
                    </thead>
                    <tbody>
                        {devices_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    
    return HTMLResponse(BASE_HTML.format(
        title="Dispositivos",
        content=content,
        nav_home="",
        nav_devices="active",
        nav_config=""
    ))


@app.get("/devices/{device_id}", response_class=HTMLResponse)
async def device_detail(device_id: str):
    """Página de controle de um dispositivo."""
    client = get_client()
    
    if not client:
        return RedirectResponse(url="/config?error=not_configured")
    
    try:
        # Obter info e status
        info_result = client.get_device_info(device_id)
        status_result = client.get_device_status(device_id)
        
        if not info_result.get("success"):
            raise Exception(info_result.get("msg", "Dispositivo não encontrado"))
        
        device = info_result["result"]
        status = status_result.get("result", [])
        
        # Nome e info básica
        name = device.get("name", "Dispositivo")
        is_online = device.get("online", False)
        category = device.get("category", "")
        
        # Construir controles baseados no status
        controls_html = ""
        for item in status:
            code = item.get("code", "")
            value = item.get("value")
            
            if code in ["switch", "switch_1", "switch_led"]:
                # Toggle switch
                checked = "checked" if value else ""
                controls_html += f"""
                <div class="mb-3">
                    <label class="form-label">Ligar/Desligar</label>
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" {checked}
                               onchange="sendCommand('{device_id}', '{code}', this.checked)"
                               style="width: 3em; height: 1.5em;">
                        <label class="form-check-label ms-2">
                            {('Ligado' if value else 'Desligado')}
                        </label>
                    </div>
                </div>
                """
            elif code in ["fan_speed", "speed", "fan_speed_percent"]:
                # Speed slider
                max_val = 100 if "percent" in code else 4
                controls_html += f"""
                <div class="mb-3">
                    <label class="form-label">Velocidade: <span id="speed-val">{value}</span></label>
                    <input type="range" class="form-range" min="0" max="{max_val}" value="{value}"
                           oninput="document.getElementById('speed-val').textContent = this.value"
                           onchange="sendCommand('{device_id}', '{code}', parseInt(this.value))">
                    <div class="d-flex justify-content-between mt-2">
                        <button class="btn btn-sm btn-outline-light" onclick="sendCommand('{device_id}', '{code}', 1)">Min</button>
                        <button class="btn btn-sm btn-outline-light" onclick="sendCommand('{device_id}', '{code}', {max_val//2})">Médio</button>
                        <button class="btn btn-sm btn-primary" onclick="sendCommand('{device_id}', '{code}', {max_val})">MAX</button>
                    </div>
                </div>
                """
            elif code in ["bright_value", "bright_value_v2"]:
                # Brightness
                controls_html += f"""
                <div class="mb-3">
                    <label class="form-label">Brilho: <span id="bright-val">{value}</span>%</label>
                    <input type="range" class="form-range" min="10" max="1000" value="{value}"
                           oninput="document.getElementById('bright-val').textContent = Math.round(this.value/10)"
                           onchange="sendCommand('{device_id}', '{code}', parseInt(this.value))">
                </div>
                """
            elif code in ["temp_value", "temp_value_v2"]:
                # Color temperature
                controls_html += f"""
                <div class="mb-3">
                    <label class="form-label">Temperatura de Cor</label>
                    <input type="range" class="form-range" min="0" max="1000" value="{value}"
                           onchange="sendCommand('{device_id}', '{code}', parseInt(this.value))">
                </div>
                """
            elif code == "countdown_1":
                # Timer
                hours = value // 60 if value else 0
                mins = value % 60 if value else 0
                controls_html += f"""
                <div class="mb-3">
                    <label class="form-label">Timer (desligar em)</label>
                    <div class="input-group">
                        <input type="number" class="form-control" id="timer-hours" value="{hours}" min="0" max="24" style="max-width: 80px;">
                        <span class="input-group-text">h</span>
                        <input type="number" class="form-control" id="timer-mins" value="{mins}" min="0" max="59" style="max-width: 80px;">
                        <span class="input-group-text">min</span>
                        <button class="btn btn-primary" onclick="
                            var h = parseInt(document.getElementById('timer-hours').value) || 0;
                            var m = parseInt(document.getElementById('timer-mins').value) || 0;
                            sendCommand('{device_id}', 'countdown_1', h*60 + m);
                        ">Definir</button>
                    </div>
                </div>
                """
            else:
                # Generic display
                controls_html += f"""
                <div class="mb-3">
                    <label class="form-label">{code}</label>
                    <input type="text" class="form-control" value="{value}" readonly>
                </div>
                """
        
        if not controls_html:
            controls_html = '<p class="text-muted">Nenhum controle disponível para este dispositivo.</p>'
        
        # Status JSON
        status_json = json.dumps(status, indent=2)
        
        content = f"""
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">
                            <i class="bi bi-sliders me-2"></i>Controles: {name}
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <span class="{'status-online' if is_online else 'status-offline'}">
                                <i class="bi bi-circle-fill me-1"></i>
                                {'Online' if is_online else 'Offline'}
                            </span>
                        </div>
                        {controls_html}
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="bi bi-code-slash me-2"></i>Status Raw</h5>
                    </div>
                    <div class="card-body">
                        <pre style="color: #00ff88; background: #0a0a0a; padding: 15px; border-radius: 10px; max-height: 400px; overflow: auto;">{status_json}</pre>
                    </div>
                </div>
                
                <div class="card mt-3">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="bi bi-info-circle me-2"></i>Informações</h5>
                    </div>
                    <div class="card-body">
                        <table class="table table-sm">
                            <tr><th>Device ID</th><td><code>{device_id}</code></td></tr>
                            <tr><th>Categoria</th><td>{category}</td></tr>
                            <tr><th>Produto</th><td>{device.get('product_name', '-')}</td></tr>
                            <tr><th>Local Key</th><td><code>{device.get('local_key', 'N/A')}</code></td></tr>
                            <tr><th>IP</th><td>{device.get('ip', 'N/A')}</td></tr>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="mt-3">
            <a href="/devices" class="btn btn-outline-light">
                <i class="bi bi-arrow-left me-2"></i>Voltar
            </a>
        </div>
        """
        
    except Exception as e:
        content = f"""
        <div class="alert alert-danger">
            <i class="bi bi-exclamation-triangle me-2"></i>
            Erro ao carregar dispositivo: {e}
        </div>
        <a href="/devices" class="btn btn-outline-light">
            <i class="bi bi-arrow-left me-2"></i>Voltar
        </a>
        """
    
    return HTMLResponse(BASE_HTML.format(
        title=f"Controle",
        content=content,
        nav_home="",
        nav_devices="active",
        nav_config=""
    ))


@app.get("/config", response_class=HTMLResponse)
async def config_page(error: str = None, success: str = None):
    """Página de configurações."""
    config = load_config()
    
    # Testar conexão
    connection_status = ""
    if config.get("access_id"):
        try:
            client = TuyaCloudClient(
                config["access_id"],
                config["access_secret"],
                config.get("region", "us")
            )
            result = client.get_token()
            if result.get("success"):
                connection_status = '<span class="status-online"><i class="bi bi-check-circle me-1"></i>Conectado</span>'
            else:
                connection_status = f'<span class="status-offline"><i class="bi bi-x-circle me-1"></i>Erro: {result.get("msg")}</span>'
        except Exception as e:
            connection_status = f'<span class="status-offline"><i class="bi bi-x-circle me-1"></i>Erro: {e}</span>'
    
    # Alertas
    alerts = ""
    if error == "not_configured":
        alerts = '<div class="alert alert-warning"><i class="bi bi-exclamation-triangle me-2"></i>Configure suas credenciais primeiro.</div>'
    if success == "saved":
        alerts = '<div class="alert alert-success"><i class="bi bi-check-circle me-2"></i>Configurações salvas com sucesso!</div>'
    
    content = f"""
    {alerts}
    
    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0"><i class="bi bi-gear me-2"></i>Configurações da Tuya Cloud API</h5>
                </div>
                <div class="card-body">
                    <form method="post" action="/config/save">
                        <div class="mb-3">
                            <label class="form-label">Access ID / Client ID</label>
                            <input type="text" class="form-control" name="access_id" 
                                   value="{config.get('access_id', '')}" required
                                   placeholder="Ex: xgkk3vwjnpasrp34hpwf">
                            <small class="text-muted">Obtido na Tuya IoT Platform → Cloud → seu projeto → Overview</small>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Access Secret / Client Secret</label>
                            <div class="input-group">
                                <input type="password" class="form-control" name="access_secret" id="access_secret"
                                       value="{config.get('access_secret', '')}" required
                                       placeholder="Ex: d0b4f1d738a141cbaf45eeffa6363820">
                                <button class="btn btn-outline-secondary" type="button" 
                                        onclick="var x = document.getElementById('access_secret'); x.type = x.type === 'password' ? 'text' : 'password';">
                                    <i class="bi bi-eye"></i>
                                </button>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Região / Data Center</label>
                            <select class="form-select" name="region">
                                <option value="us" {'selected' if config.get('region') == 'us' else ''}>Western America (us)</option>
                                <option value="eu" {'selected' if config.get('region') == 'eu' else ''}>Central Europe (eu)</option>
                                <option value="cn" {'selected' if config.get('region') == 'cn' else ''}>China (cn)</option>
                                <option value="in" {'selected' if config.get('region') == 'in' else ''}>India (in)</option>
                            </select>
                            <small class="text-muted">Deve ser a mesma região onde você criou o projeto na Tuya</small>
                        </div>
                        
                        <button type="submit" class="btn btn-primary">
                            <i class="bi bi-save me-2"></i>Salvar Configurações
                        </button>
                        
                        <button type="button" class="btn btn-outline-light ms-2" onclick="location.href='/config/test'">
                            <i class="bi bi-lightning me-2"></i>Testar Conexão
                        </button>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0"><i class="bi bi-wifi me-2"></i>Status da Conexão</h5>
                </div>
                <div class="card-body">
                    {connection_status if connection_status else '<span class="text-muted">Não configurado</span>'}
                </div>
            </div>
            
            <div class="card mt-3">
                <div class="card-header">
                    <h5 class="mb-0"><i class="bi bi-question-circle me-2"></i>Ajuda</h5>
                </div>
                <div class="card-body">
                    <ol class="mb-0">
                        <li>Acesse <a href="https://auth.tuya.com" target="_blank">auth.tuya.com</a></li>
                        <li>Crie uma conta ou faça login</li>
                        <li>Vá em Cloud → Development</li>
                        <li>Crie um projeto (Smart Home)</li>
                        <li>Copie Access ID e Secret</li>
                        <li>Vincule sua conta SmartLife (Devices → Link App Account)</li>
                    </ol>
                </div>
            </div>
        </div>
    </div>
    """
    
    return HTMLResponse(BASE_HTML.format(
        title="Configurações",
        content=content,
        nav_home="",
        nav_devices="",
        nav_config="active"
    ))


@app.post("/config/save")
async def save_config_form(
    access_id: str = Form(...),
    access_secret: str = Form(...),
    region: str = Form("us")
):
    """Salva configurações do formulário."""
    config = {
        "access_id": access_id.strip(),
        "access_secret": access_secret.strip(),
        "region": region
    }
    save_config(config)
    return RedirectResponse(url="/config?success=saved", status_code=303)


@app.get("/config/test", response_class=HTMLResponse)
async def test_connection():
    """Testa conexão com Tuya Cloud."""
    client = get_client()
    
    if not client:
        return RedirectResponse(url="/config?error=not_configured")
    
    try:
        result = client.get_token()
        
        if result.get("success"):
            # Tentar listar dispositivos
            devices_result = client.get_user_devices()
            devices_count = len(devices_result.get("result", [])) if devices_result.get("success") else 0
            
            content = f"""
            <div class="card">
                <div class="card-header bg-success text-white">
                    <h5 class="mb-0"><i class="bi bi-check-circle me-2"></i>Conexão Bem Sucedida!</h5>
                </div>
                <div class="card-body">
                    <p><i class="bi bi-key me-2"></i>Token obtido com sucesso</p>
                    <p><i class="bi bi-clock me-2"></i>Expira em: {result['result']['expire_time']} segundos</p>
                    <p><i class="bi bi-cpu me-2"></i>Dispositivos encontrados: <strong>{devices_count}</strong></p>
                    
                    <hr>
                    
                    <a href="/devices" class="btn btn-primary">
                        <i class="bi bi-grid me-2"></i>Ver Dispositivos
                    </a>
                    <a href="/config" class="btn btn-outline-light ms-2">
                        <i class="bi bi-arrow-left me-2"></i>Voltar
                    </a>
                </div>
            </div>
            """
        else:
            content = f"""
            <div class="card">
                <div class="card-header bg-danger text-white">
                    <h5 class="mb-0"><i class="bi bi-x-circle me-2"></i>Erro na Conexão</h5>
                </div>
                <div class="card-body">
                    <p>Mensagem: <code>{result.get('msg', 'Erro desconhecido')}</code></p>
                    <p>Código: <code>{result.get('code', '-')}</code></p>
                    
                    <hr>
                    
                    <p>Possíveis causas:</p>
                    <ul>
                        <li>Access ID ou Secret incorretos</li>
                        <li>Região errada (deve corresponder ao Data Center do projeto)</li>
                        <li>Projeto não tem as APIs autorizadas</li>
                    </ul>
                    
                    <a href="/config" class="btn btn-primary">
                        <i class="bi bi-gear me-2"></i>Revisar Configurações
                    </a>
                </div>
            </div>
            """
    except Exception as e:
        content = f"""
        <div class="card">
            <div class="card-header bg-danger text-white">
                <h5 class="mb-0"><i class="bi bi-x-circle me-2"></i>Erro de Conexão</h5>
            </div>
            <div class="card-body">
                <p>Erro: <code>{e}</code></p>
                
                <a href="/config" class="btn btn-primary">
                    <i class="bi bi-arrow-left me-2"></i>Voltar
                </a>
            </div>
        </div>
        """
    
    return HTMLResponse(BASE_HTML.format(
        title="Teste de Conexão",
        content=content,
        nav_home="",
        nav_devices="",
        nav_config="active"
    ))


# ============================================================================
# API REST Endpoints
# ============================================================================

@app.get("/api/devices")
async def api_list_devices():
    """API: Lista dispositivos."""
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Não configurado")
    
    return client.get_user_devices()


@app.get("/api/devices/{device_id}")
async def api_device_info(device_id: str):
    """API: Info do dispositivo."""
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Não configurado")
    
    return client.get_device_info(device_id)


@app.get("/api/devices/{device_id}/status")
async def api_device_status(device_id: str):
    """API: Status do dispositivo."""
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Não configurado")
    
    return client.get_device_status(device_id)


class CommandRequest(BaseModel):
    code: str
    value: Any


@app.post("/api/devices/{device_id}/command")
async def api_send_command(device_id: str, cmd: CommandRequest):
    """API: Envia comando para dispositivo."""
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Não configurado")
    
    return client.send_commands(device_id, [{"code": cmd.code, "value": cmd.value}])


@app.post("/api/devices/{device_id}/commands")
async def api_send_commands(device_id: str, commands: List[dict]):
    """API: Envia múltiplos comandos."""
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Não configurado")
    
    return client.send_commands(device_id, commands)


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║         🏠 SmartLife Control Panel                               ║
║         Painel de Controle para Dispositivos Tuya/SmartLife      ║
╠══════════════════════════════════════════════════════════════════╣
║  Dashboard:      http://localhost:8200                           ║
║  Dispositivos:   http://localhost:8200/devices                   ║
║  Configurações:  http://localhost:8200/config                    ║
║  API Docs:       http://localhost:8200/docs                      ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    uvicorn.run(app, host="0.0.0.0", port=8200)
