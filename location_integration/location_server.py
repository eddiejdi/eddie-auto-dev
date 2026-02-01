#!/usr/bin/env python3
"""
Servidor de Localização - Integração OwnTracks + IA
Recebe localização do celular e integra com:
- Telegram Bot
- Automações SmartLife/Tuya
- Histórico em SQLite
- Geofencing (chegou/saiu de lugares)
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from math import radians, cos, sin, asin, sqrt
from dataclasses import dataclass
from enum import Enum

# FastAPI
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
import uvicorn

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configurações
from tools.secrets_loader import get_telegram_token

TELEGRAM_BOT_TOKEN = get_telegram_token()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "948686300")
DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "locations.db"

# Criar diretório de dados
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="Eddie Location Server",
    description="Servidor de localização integrado com IA",
    version="1.0.0",
)


class EventType(Enum):
    ENTER = "enter"
    LEAVE = "leave"
    LOCATION = "location"


@dataclass
class GeoFence:
    """Define uma área de geofencing"""

    name: str
    latitude: float
    longitude: float
    radius_meters: float  # Raio em metros
    icon: str = "📍"

    # Automações
    on_enter: Optional[Dict] = None  # {"action": "turn_on", "device": "luz_sala"}
    on_leave: Optional[Dict] = None


def load_geofences_from_config() -> Dict[str, GeoFence]:
    """Carrega geofences do arquivo config.json"""
    config_path = DATA_DIR.parent / "config.json"
    geofences = {}

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            for fence_id, fence_data in config.get("geofences", {}).items():
                geofences[fence_id] = GeoFence(
                    name=fence_data.get("name", fence_id),
                    latitude=fence_data.get("latitude", 0),
                    longitude=fence_data.get("longitude", 0),
                    radius_meters=fence_data.get("radius_meters", 100),
                    icon=fence_data.get("icon", "📍"),
                    on_enter=fence_data.get("on_enter"),
                    on_leave=fence_data.get("on_leave"),
                )
            print(f"✅ Carregados {len(geofences)} geofences do config.json")
        except Exception as e:
            print(f"⚠️ Erro ao carregar config.json: {e}")

    # Fallback se não houver config
    if not geofences:
        print(
            "⚠️ Usando geofences padrão - configure config.json com suas coordenadas!"
        )
        geofences = {
            "casa": GeoFence(
                name="Casa",
                latitude=-23.5505,  # Substitua pela sua latitude
                longitude=-46.6333,  # Substitua pela sua longitude
                radius_meters=100,
                icon="🏠",
                on_enter={"action": "chegou_casa"},
                on_leave={"action": "saiu_casa"},
            ),
        }

    return geofences


# Carregar geofences do config
GEOFENCES: Dict[str, GeoFence] = load_geofences_from_config()


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distância em metros entre duas coordenadas"""
    R = 6371000  # Raio da Terra em metros

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    return R * c


class LocationDatabase:
    """Gerencia histórico de localizações"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Inicializa o banco de dados"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Tabela de localizações
        c.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                altitude REAL,
                accuracy REAL,
                velocity REAL,
                battery REAL,
                wifi_ssid TEXT,
                device_id TEXT,
                raw_data TEXT
            )
        """)

        # Tabela de eventos (entrada/saída de geofences)
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                geofence_name TEXT,
                latitude REAL,
                longitude REAL,
                details TEXT
            )
        """)

        # Tabela de estado atual
        c.execute("""
            CREATE TABLE IF NOT EXISTS current_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Índices
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_locations_timestamp ON locations(timestamp)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)"
        )

        conn.commit()
        conn.close()

    def save_location(self, lat: float, lon: float, data: Dict) -> int:
        """Salva uma localização no histórico"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO locations 
            (latitude, longitude, altitude, accuracy, velocity, battery, wifi_ssid, device_id, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                lat,
                lon,
                data.get("alt"),
                data.get("acc"),
                data.get("vel"),
                data.get("batt"),
                data.get("SSID"),
                data.get("tid", "default"),
                json.dumps(data),
            ),
        )

        location_id = c.lastrowid
        conn.commit()
        conn.close()

        return location_id

    def save_event(
        self,
        event_type: str,
        geofence: str,
        lat: float,
        lon: float,
        details: Dict = None,
    ):
        """Salva um evento de geofencing"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO events (event_type, geofence_name, latitude, longitude, details)
            VALUES (?, ?, ?, ?, ?)
        """,
            (event_type, geofence, lat, lon, json.dumps(details or {})),
        )

        conn.commit()
        conn.close()

    def get_state(self, key: str) -> Optional[str]:
        """Obtém um estado salvo"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT value FROM current_state WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()

        return row[0] if row else None

    def set_state(self, key: str, value: str):
        """Salva um estado"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT OR REPLACE INTO current_state (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
            (key, value),
        )

        conn.commit()
        conn.close()

    def get_last_location(self) -> Optional[Dict]:
        """Obtém a última localização"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            SELECT latitude, longitude, altitude, accuracy, battery, timestamp, raw_data
            FROM locations ORDER BY timestamp DESC LIMIT 1
        """)
        row = c.fetchone()
        conn.close()

        if row:
            return {
                "latitude": row[0],
                "longitude": row[1],
                "altitude": row[2],
                "accuracy": row[3],
                "battery": row[4],
                "timestamp": row[5],
                "raw": json.loads(row[6]) if row[6] else {},
            }
        return None

    def get_history(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Obtém histórico de localizações"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        since = datetime.now() - timedelta(hours=hours)

        c.execute(
            """
            SELECT latitude, longitude, altitude, accuracy, battery, timestamp
            FROM locations 
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (since.isoformat(), limit),
        )

        rows = c.fetchall()
        conn.close()

        return [
            {
                "latitude": r[0],
                "longitude": r[1],
                "altitude": r[2],
                "accuracy": r[3],
                "battery": r[4],
                "timestamp": r[5],
            }
            for r in rows
        ]

    def get_events(self, hours: int = 24) -> List[Dict]:
        """Obtém eventos recentes"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        since = datetime.now() - timedelta(hours=hours)

        c.execute(
            """
            SELECT event_type, geofence_name, latitude, longitude, timestamp, details
            FROM events 
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        """,
            (since.isoformat(),),
        )

        rows = c.fetchall()
        conn.close()

        return [
            {
                "type": r[0],
                "geofence": r[1],
                "latitude": r[2],
                "longitude": r[3],
                "timestamp": r[4],
                "details": json.loads(r[5]) if r[5] else {},
            }
            for r in rows
        ]


# Instância global do banco
db = LocationDatabase(DB_PATH)


async def send_telegram_message(message: str, chat_id: str = None):
    """Envia mensagem para o Telegram"""
    import httpx

    chat_id = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
            )
        except Exception as e:
            print(f"Erro ao enviar Telegram: {e}")


async def trigger_automation(action: str, details: Dict = None):
    """Dispara automação baseada em evento"""

    # Importar SmartLife/Tuya se disponível
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "smartlife_integration"))
        from quick_control import control_device

        SMARTLIFE_AVAILABLE = True
    except ImportError:
        SMARTLIFE_AVAILABLE = False

    print(f"🤖 Automação disparada: {action}")

    if action == "chegou_casa":
        # Exemplo: Ligar luzes quando chegar em casa
        msg = "🏠 <b>Eddie chegou em casa!</b>\n"
        msg += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        await send_telegram_message(msg)

        # Aqui você pode adicionar controle de dispositivos
        # if SMARTLIFE_AVAILABLE:
        #     control_device("luz_sala", "on")

    elif action == "saiu_casa":
        msg = "🚗 <b>Eddie saiu de casa</b>\n"
        msg += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        await send_telegram_message(msg)

        # Desligar dispositivos
        # if SMARTLIFE_AVAILABLE:
        #     control_device("luz_sala", "off")

    elif action == "chegou_trabalho":
        msg = "🏢 <b>Eddie chegou no trabalho</b>\n"
        msg += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        await send_telegram_message(msg)

    elif action == "saiu_trabalho":
        msg = "🏃 <b>Eddie saiu do trabalho</b>\n"
        msg += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        await send_telegram_message(msg)


def check_geofences(lat: float, lon: float) -> List[Dict]:
    """Verifica se entrou/saiu de algum geofence"""
    events = []

    for fence_id, fence in GEOFENCES.items():
        distance = haversine(lat, lon, fence.latitude, fence.longitude)
        is_inside = distance <= fence.radius_meters

        # Verificar estado anterior
        state_key = f"geofence_{fence_id}"
        was_inside = db.get_state(state_key) == "inside"

        if is_inside and not was_inside:
            # Entrou no geofence
            db.set_state(state_key, "inside")
            events.append(
                {
                    "type": EventType.ENTER,
                    "fence": fence,
                    "fence_id": fence_id,
                    "distance": distance,
                }
            )

        elif not is_inside and was_inside:
            # Saiu do geofence
            db.set_state(state_key, "outside")
            events.append(
                {
                    "type": EventType.LEAVE,
                    "fence": fence,
                    "fence_id": fence_id,
                    "distance": distance,
                }
            )

    return events


async def process_location(data: Dict, background_tasks: BackgroundTasks):
    """Processa uma atualização de localização"""

    # Extrair coordenadas (formato OwnTracks)
    lat = data.get("lat")
    lon = data.get("lon")

    if lat is None or lon is None:
        return {"status": "error", "message": "Missing coordinates"}

    # Salvar no histórico
    location_id = db.save_location(lat, lon, data)

    # Verificar geofences
    geofence_events = check_geofences(lat, lon)

    for event in geofence_events:
        fence = event["fence"]
        event_type = event["type"]

        # Salvar evento
        db.save_event(
            event_type.value, fence.name, lat, lon, {"distance": event["distance"]}
        )

        # Disparar automação
        if event_type == EventType.ENTER and fence.on_enter:
            background_tasks.add_task(
                trigger_automation,
                fence.on_enter.get("action"),
                {"fence": fence.name, "lat": lat, "lon": lon},
            )
        elif event_type == EventType.LEAVE and fence.on_leave:
            background_tasks.add_task(
                trigger_automation,
                fence.on_leave.get("action"),
                {"fence": fence.name, "lat": lat, "lon": lon},
            )

    return {
        "status": "ok",
        "location_id": location_id,
        "geofence_events": [
            {"type": e["type"].value, "fence": e["fence"].name} for e in geofence_events
        ],
    }


# ===== ENDPOINTS =====


@app.post("/owntracks")
async def owntracks_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para receber dados do OwnTracks
    Configure no app: HTTP -> URL: http://seu-servidor:8585/owntracks
    """
    try:
        data = await request.json()

        # OwnTracks envia diferentes tipos de mensagens
        msg_type = data.get("_type", "location")

        if msg_type == "location":
            result = await process_location(data, background_tasks)
            return result

        elif msg_type == "transition":
            # Transição de geofence (se configurado no app)
            event = data.get("event", "unknown")
            desc = data.get("desc", "unknown")

            db.save_event(event, desc, data.get("lat"), data.get("lon"), data)

            return {"status": "ok", "type": "transition"}

        elif msg_type == "waypoint":
            # Novo waypoint configurado
            return {"status": "ok", "type": "waypoint"}

        else:
            return {"status": "ok", "type": msg_type}

    except Exception as e:
        print(f"Erro no webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/location")
async def simple_location(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint simples para receber localização
    Formato: {"lat": -23.55, "lon": -46.63, "accuracy": 10}
    """
    try:
        data = await request.json()
        result = await process_location(data, background_tasks)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/location/current")
async def get_current_location():
    """Retorna a localização atual"""
    location = db.get_last_location()

    if not location:
        return {"status": "no_data", "message": "Nenhuma localização registrada"}

    # Verificar em qual geofence está
    current_fences = []
    for fence_id, fence in GEOFENCES.items():
        distance = haversine(
            location["latitude"], location["longitude"], fence.latitude, fence.longitude
        )
        if distance <= fence.radius_meters:
            current_fences.append(
                {"name": fence.name, "icon": fence.icon, "distance": round(distance)}
            )

    return {
        "status": "ok",
        "location": location,
        "geofences": current_fences,
        "maps_url": f"https://maps.google.com/?q={location['latitude']},{location['longitude']}",
    }


@app.get("/location/history")
async def get_location_history(hours: int = 24, limit: int = 100):
    """Retorna histórico de localizações"""
    history = db.get_history(hours, limit)
    return {"status": "ok", "count": len(history), "hours": hours, "locations": history}


@app.get("/events")
async def get_events(hours: int = 24):
    """Retorna eventos de geofencing"""
    events = db.get_events(hours)
    return {"status": "ok", "count": len(events), "events": events}


@app.get("/geofences")
async def list_geofences():
    """Lista todos os geofences configurados"""
    return {
        "status": "ok",
        "geofences": {
            fence_id: {
                "name": fence.name,
                "latitude": fence.latitude,
                "longitude": fence.longitude,
                "radius": fence.radius_meters,
                "icon": fence.icon,
            }
            for fence_id, fence in GEOFENCES.items()
        },
    }


@app.post("/geofences/{fence_id}")
async def update_geofence(fence_id: str, request: Request):
    """Atualiza um geofence existente"""
    data = await request.json()

    if fence_id not in GEOFENCES:
        raise HTTPException(status_code=404, detail="Geofence não encontrado")

    fence = GEOFENCES[fence_id]

    if "latitude" in data:
        fence.latitude = data["latitude"]
    if "longitude" in data:
        fence.longitude = data["longitude"]
    if "radius" in data:
        fence.radius_meters = data["radius"]
    if "name" in data:
        fence.name = data["name"]

    return {"status": "ok", "fence": fence_id}


@app.get("/status")
async def get_status():
    """Status do servidor"""
    location = db.get_last_location()

    return {
        "status": "online",
        "server": "Eddie Location Server",
        "version": "1.0.0",
        "last_location": location["timestamp"] if location else None,
        "geofences_count": len(GEOFENCES),
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN),
    }


@app.get("/")
async def root():
    """Página inicial"""
    return {
        "server": "Eddie Location Server",
        "endpoints": {
            "POST /owntracks": "Webhook para OwnTracks",
            "POST /location": "Enviar localização simples",
            "GET /location/current": "Localização atual",
            "GET /location/history": "Histórico de localizações",
            "GET /events": "Eventos de geofencing",
            "GET /geofences": "Listar geofences",
            "GET /status": "Status do servidor",
        },
    }


if __name__ == "__main__":
    print("🌍 Iniciando Eddie Location Server...")
    print(f"📁 Dados em: {DATA_DIR}")
    print(f"📊 Geofences configurados: {len(GEOFENCES)}")
    print("")
    print("📱 Configure o OwnTracks:")
    print("   Mode: HTTP")
    print("   URL: http://SEU-IP:8585/owntracks")
    print("")
    # Allow overriding bind address/port via environment variables so
    # it's possible to bind to a specific LAN IP (e.g. 192.168.15.2)
    SERVER_HOST = os.getenv("LOCATION_SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("LOCATION_SERVER_PORT", "8585"))

    print(f"🔌 Bind: {SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
