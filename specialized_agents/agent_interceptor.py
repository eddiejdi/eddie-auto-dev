"""
Agent Conversation Interceptor
Sistema avançado de interceptação, análise e visualização de conversas entre agentes
"""
import asyncio
import json
import sqlite3
import os
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    SQLALCHEMY_AVAILABLE = True
except Exception:
    SQLALCHEMY_AVAILABLE = False
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import threading
import logging
from collections import defaultdict, deque
import hashlib

from .agent_communication_bus import (
    AgentCommunicationBus, AgentMessage, MessageType, get_communication_bus
)
from .config import DATA_DIR


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationPhase(Enum):
    """Fases de uma conversa entre agentes"""
    INITIATED = "initiated"      # Conversa iniciada
    ANALYZING = "analyzing"       # Analisando requisitos
    PLANNING = "planning"         # Planejando solução
    CODING = "coding"             # Desenvolvendo código
    TESTING = "testing"           # Testando solução
    DEPLOYING = "deploying"       # Fazendo deploy
    COMPLETED = "completed"       # Concluída
    FAILED = "failed"             # Falhou


@dataclass
class ConversationSnapshot:
    """Snapshot de uma conversa em um momento no tempo"""
    conversation_id: str
    timestamp: datetime
    phase: ConversationPhase
    participants: List[str]
    message_count: int
    last_message: str
    duration_seconds: float


class AgentConversationInterceptor:
    """
    Interceptador avançado de conversas entre agentes.
    Captura, analisa e armazena todas as conversas.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.bus = get_communication_bus()
        self.data_dir = Path(DATA_DIR) / "interceptor_data"
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Database de conversas
        self.db_path = self.data_dir / "conversations.db"
        # Database URL (Postgres or fallback to sqlite file)
        self.database_url = os.environ.get("DATABASE_URL")
        self.engine: Optional[Engine] = None
        if SQLALCHEMY_AVAILABLE and self.database_url:
            try:
                self.engine = create_engine(self.database_url, pool_size=5, max_overflow=10)
                logger.info("Usando SQLAlchemy engine para %s", self.database_url)
            except Exception as e:
                logger.error(f"Falha ao criar engine SQLAlchemy: {e}; fallback para sqlite")
                self.engine = None

        self._init_database()
        
        # Cache de conversas ativas
        self.active_conversations: Dict[str, Dict[str, Any]] = {}
        
        # Subscribers para eventos de conversa
        self.conversation_listeners: List[Callable[[Dict[str, Any]], None]] = []
        
        # Índices para busca rápida
        self.index_by_participants: Dict[str, List[str]] = defaultdict(list)
        self.index_by_phase: Dict[str, List[str]] = defaultdict(list)
        
        # Histórico de conversas em memória (últimas 100)
        self.conversation_history: deque = deque(maxlen=100)
        
        # Estatísticas
        self.stats = {
            "total_conversations": 0,
            "active_conversations": 0,
            "total_messages_intercepted": 0,
            "average_duration": 0,
            "by_phase": {},
            "by_participants": {},
            "start_time": datetime.now()
        }
        
        # Inscrever no bus
        self.bus.subscribe(self._on_message_published)
        
        self._initialized = True
        logger.info("✅ Agent Conversation Interceptor inicializado")
    
    def _init_database(self):
        """Inicializa database SQLite"""
        # Use SQLAlchemy engine if disponível, senão sqlite3 direto
        if self.engine is not None:
            try:
                with self.engine.begin() as conn:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS conversations (
                            id TEXT PRIMARY KEY,
                            started_at TIMESTAMP,
                            ended_at TIMESTAMP,
                            phase TEXT,
                            participants TEXT,
                            total_messages INTEGER,
                            duration_seconds REAL,
                            status TEXT
                        )
                    """))

                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS messages (
                            id TEXT PRIMARY KEY,
                            conversation_id TEXT,
                            timestamp TIMESTAMP,
                            message_type TEXT,
                            source TEXT,
                            target TEXT,
                            content TEXT,
                            metadata TEXT
                        )
                    """))

                    # snapshots
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS conversation_snapshots (
                            id SERIAL PRIMARY KEY,
                            conversation_id TEXT,
                            timestamp TIMESTAMP,
                            phase TEXT,
                            participants TEXT,
                            message_count INTEGER,
                            last_message TEXT
                        )
                    """))

                    # Indexes (Postgres uses IF NOT EXISTS too)
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conv_phase ON conversations(phase)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_msg_source ON messages(source)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_snap_conv ON conversation_snapshots(conversation_id)"))
            except Exception as e:
                logger.error(f"Erro inicializando DB via engine: {e}")
        else:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Tabela de conversas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    started_at TIMESTAMP,
                    ended_at TIMESTAMP,
                    phase TEXT,
                    participants TEXT,
                    total_messages INTEGER,
                    duration_seconds REAL,
                    status TEXT
                )
            """)
            
            # Tabela de mensagens
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    timestamp TIMESTAMP,
                    message_type TEXT,
                    source TEXT,
                    target TEXT,
                    content TEXT,
                    metadata TEXT,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Tabela de snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT,
                    timestamp TIMESTAMP,
                    phase TEXT,
                    participants TEXT,
                    message_count INTEGER,
                    last_message TEXT,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Índices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_phase ON conversations(phase)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_msg_source ON messages(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snap_conv ON conversation_snapshots(conversation_id)")
            
            conn.commit()
            conn.close()
    
    def _on_message_published(self, message: AgentMessage):
        """Callback chamado quando uma mensagem é publicada no bus"""
        # Extrair ou criar conversation_id
        conversation_id = message.metadata.get("conversation_id")
        if not conversation_id:
            conversation_id = self._generate_conversation_id(message.source, message.target)
            message.metadata["conversation_id"] = conversation_id
        
        # Rastrear conversa ativa
        self._update_active_conversation(conversation_id, message)
        
        # Armazenar no banco
        self._store_message(conversation_id, message)
        
        # Atualizar índices
        self._update_indices(conversation_id, message)
        
        # Notificar listeners
        self._notify_listeners(conversation_id, message)
        
        # Atualizar estatísticas
        self.stats["total_messages_intercepted"] += 1
    
    def _generate_conversation_id(self, source: str, target: str) -> str:
        """Gera ID único para conversa"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        participants = "|".join(sorted([source, target]))
        hash_val = hashlib.md5(f"{participants}_{timestamp}".encode()).hexdigest()[:8]
        return f"conv_{timestamp}_{hash_val}"
    
    def _update_active_conversation(self, conversation_id: str, message: AgentMessage):
        """Atualiza rastreamento de conversa ativa"""
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = {
                "id": conversation_id,
                "started_at": message.timestamp,
                "participants": set(),
                "messages": [],
                "phase": ConversationPhase.INITIATED.value,
                "last_update": message.timestamp,
                "duration_seconds": 0
            }
            self.stats["active_conversations"] += 1
        
        conv = self.active_conversations[conversation_id]
        conv["participants"].add(message.source)
        conv["participants"].add(message.target)
        conv["messages"].append(message)
        conv["last_update"] = message.timestamp
        conv["duration_seconds"] = (message.timestamp - conv["started_at"]).total_seconds()
        
        # Detectar fase
        conv["phase"] = self._detect_phase(message.message_type)
    
    def _detect_phase(self, message_type: MessageType) -> str:
        """Detecta fase da conversa baseada no tipo de mensagem"""
        phase_map = {
            MessageType.ANALYSIS: ConversationPhase.ANALYZING.value,
            MessageType.COORDINATOR: ConversationPhase.PLANNING.value,
            MessageType.CODE_GEN: ConversationPhase.CODING.value,
            MessageType.TEST_GEN: ConversationPhase.TESTING.value,
            MessageType.GITHUB: ConversationPhase.DEPLOYING.value,
            MessageType.ERROR: ConversationPhase.FAILED.value,
        }
        return phase_map.get(message_type, ConversationPhase.INITIATED.value)
    
    def _store_message(self, conversation_id: str, message: AgentMessage):
        """Armazena mensagem no banco de dados"""
        try:
            if self.engine is not None:
                with self.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO messages 
                        (id, conversation_id, timestamp, message_type, source, target, content, metadata)
                        VALUES (:id, :conversation_id, :timestamp, :message_type, :source, :target, :content, :metadata)
                    """), {
                        "id": message.id,
                        "conversation_id": conversation_id,
                        "timestamp": message.timestamp.isoformat(),
                        "message_type": message.message_type.value,
                        "source": message.source,
                        "target": message.target,
                        "content": (str(message.content) if not isinstance(message.content, str) else message.content)[:5000],
                        "metadata": json.dumps(message.metadata)
                    })
            else:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO messages 
                    (id, conversation_id, timestamp, message_type, source, target, content, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.id,
                    conversation_id,
                    message.timestamp.isoformat(),
                    message.message_type.value,
                    message.source,
                    message.target,
                    (str(message.content) if not isinstance(message.content, str) else message.content)[:5000],  # Truncar conteúdo
                    json.dumps(message.metadata)
                ))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"Erro ao armazenar mensagem: {e}")
    
    def _update_indices(self, conversation_id: str, message: AgentMessage):
        """Atualiza índices para busca rápida"""
        self.index_by_participants[message.source].append(conversation_id)
        self.index_by_phase[self._detect_phase(message.message_type)].append(conversation_id)
    
    def _notify_listeners(self, conversation_id: str, message: AgentMessage):
        """Notifica listeners de novo evento de conversa"""
        conv = self.active_conversations.get(conversation_id)
        if conv:
            event = {
                "conversation_id": conversation_id,
                "event": "new_message",
                "message": message.to_dict(),
                "conversation": {
                    "id": conv["id"],
                    "started_at": conv["started_at"].isoformat(),
                    "participants": list(conv["participants"]),
                    "message_count": len(conv["messages"]),
                    "phase": conv["phase"],
                    "duration_seconds": conv["duration_seconds"]
                }
            }
            
            for listener in self.conversation_listeners:
                try:
                    listener(event)
                except Exception as e:
                    logger.error(f"Erro ao notificar listener: {e}")
    
    def subscribe_conversation_events(self, callback: Callable[[Dict[str, Any]], None]):
        """Adiciona listener para eventos de conversa"""
        if callback not in self.conversation_listeners:
            self.conversation_listeners.append(callback)
    
    def unsubscribe_conversation_events(self, callback: Callable[[Dict[str, Any]], None]):
        """Remove listener"""
        if callback in self.conversation_listeners:
            self.conversation_listeners.remove(callback)
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Obtém conversa ativa"""
        conv = self.active_conversations.get(conversation_id)
        if conv:
            return {
                "id": conv["id"],
                "started_at": conv["started_at"].isoformat(),
                "last_update": conv["last_update"].isoformat(),
                "participants": list(conv["participants"]),
                "message_count": len(conv["messages"]),
                "phase": conv["phase"],
                "duration_seconds": conv["duration_seconds"],
                "messages": [m.to_dict() for m in conv["messages"][-20:]]  # Últimas 20
            }
        
        # Buscar no banco
        return self._get_conversation_from_db(conversation_id)
    
    def _get_conversation_from_db(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Busca conversa no banco de dados"""
        try:
            if self.engine is not None:
                with self.engine.connect() as conn:
                    res = conn.execute(text("SELECT * FROM conversations WHERE id = :id"), {"id": conversation_id})
                    conv_row = res.fetchone()
                    if not conv_row:
                        return None

                    res = conn.execute(text("""
                        SELECT * FROM messages 
                        WHERE conversation_id = :id 
                        ORDER BY timestamp DESC 
                        LIMIT 50
                    """), {"id": conversation_id})
                    msg_rows = res.fetchall()

                    return {
                        "id": conv_row._mapping.get("id"),
                        "started_at": conv_row._mapping.get("started_at"),
                        "ended_at": conv_row._mapping.get("ended_at"),
                        "phase": conv_row._mapping.get("phase"),
                        "participants": (conv_row._mapping.get("participants") or "").split(",") if conv_row._mapping.get("participants") else [],
                        "message_count": conv_row._mapping.get("total_messages"),
                        "duration_seconds": conv_row._mapping.get("duration_seconds"),
                        "messages": [dict(r._mapping) for r in msg_rows]
                    }
            else:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Buscar conversa
                cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
                conv_row = cursor.fetchone()
                
                if not conv_row:
                    return None
                
                # Buscar mensagens
                cursor.execute("""
                    SELECT * FROM messages 
                    WHERE conversation_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 50
                """, (conversation_id,))
                msg_rows = cursor.fetchall()
                
                conn.close()
                
                return {
                    "id": conv_row["id"],
                    "started_at": conv_row["started_at"],
                    "ended_at": conv_row["ended_at"],
                    "phase": conv_row["phase"],
                    "participants": conv_row["participants"].split(",") if conv_row["participants"] else [],
                    "message_count": conv_row["total_messages"],
                    "duration_seconds": conv_row["duration_seconds"],
                    "messages": [dict(row) for row in msg_rows]
                }
        except Exception as e:
            logger.error(f"Erro ao buscar conversa no DB: {e}")
            return None
    
    def list_active_conversations(self) -> List[Dict[str, Any]]:
        """Lista conversas ativas"""
        result = []
        for conversation_id, conv in self.active_conversations.items():
            result.append({
                "id": conversation_id,
                "started_at": conv["started_at"].isoformat(),
                "participants": list(conv["participants"]),
                "message_count": len(conv["messages"]),
                "phase": conv["phase"],
                "duration_seconds": round(conv["duration_seconds"], 2)
            })
        return sorted(result, key=lambda x: x["started_at"], reverse=True)
    
    def list_conversations(
        self,
        limit: int = 50,
        agent: str = None,
        phase: str = None,
        since: datetime = None,
        include_active: bool = True
    ) -> List[Dict[str, Any]]:
        """Lista conversas com filtros - busca do banco de dados SQLite"""
        results = []
        seen_ids = set()
        
        # 1. Incluir conversas ATIVAS em memória (se existirem)
        if include_active:
            for conv_id, conv in self.active_conversations.items():
                if agent and agent not in conv["participants"]:
                    continue
                if phase and conv["phase"] != phase:
                    continue
                if since and conv["started_at"] < since:
                    continue
                
                messages = []
                for msg in conv["messages"]:
                    try:
                        messages.append({
                            "timestamp": msg.timestamp.isoformat() if hasattr(msg, 'timestamp') else str(msg.get('timestamp', '')),
                            "sender": msg.source if hasattr(msg, 'source') else msg.get('source', 'unknown'),
                            "target": msg.target if hasattr(msg, 'target') else msg.get('target', 'unknown'),
                            "action": msg.message_type.value if hasattr(msg, 'message_type') else msg.get('type', 'info'),
                            "content": msg.content if hasattr(msg, 'content') else msg.get('content', ''),
                            "type": "info"
                        })
                    except Exception:
                        pass
                
                seen_ids.add(conv_id)
                results.append({
                    "id": conv_id,
                    "conversation_id": conv_id,
                    "started_at": conv["started_at"].isoformat() if hasattr(conv["started_at"], 'isoformat') else str(conv["started_at"]),
                    "created_at": conv["started_at"].isoformat() if hasattr(conv["started_at"], 'isoformat') else str(conv["started_at"]),
                    "ended_at": None,
                    "phase": conv["phase"],
                    "current_phase": conv["phase"],
                    "participants": list(conv["participants"]),
                    "message_count": len(conv["messages"]),
                    "messages": messages,
                    "duration_seconds": conv["duration_seconds"],
                    "status": "active"
                })
        
        # 2. Buscar TODAS as mensagens do banco e agrupar por conversation_id
        try:
            if self.engine is not None:
                dialect = self.engine.dialect.name
                if dialect == "sqlite":
                    participants_expr = "GROUP_CONCAT(DISTINCT source) as participants"
                else:
                    participants_expr = "STRING_AGG(DISTINCT source, ',') as participants"

                query = f"""
                    SELECT conversation_id,
                           MIN(timestamp) as started_at,
                           MAX(timestamp) as last_update,
                           COUNT(*) as message_count,
                           {participants_expr}
                    FROM messages
                    WHERE 1=1
                """

                exec_params = {"limit": limit * 2}
                if agent:
                    query += " AND (source LIKE :agent OR target LIKE :agent)"
                    exec_params["agent"] = f"%{agent}%"
                if since:
                    query += " AND timestamp >= :since"
                    exec_params["since"] = since.isoformat() if hasattr(since, 'isoformat') else str(since)

                query += " GROUP BY conversation_id ORDER BY last_update DESC LIMIT :limit"

                with self.engine.connect() as conn:
                    res = conn.execute(text(query), exec_params)
                    rows = res.fetchall()

                    for row in rows:
                        conv_id = row._mapping.get("conversation_id")
                        if conv_id in seen_ids:
                            continue
                        seen_ids.add(conv_id)

                        res2 = conn.execute(text("SELECT * FROM messages WHERE conversation_id = :id ORDER BY timestamp ASC"), {"id": conv_id})
                        msg_rows = res2.fetchall()

                        messages = []
                        participants = set()
                        for msg in msg_rows:
                            participants.add(msg._mapping.get("source"))
                            participants.add(msg._mapping.get("target"))
                            messages.append({
                                "timestamp": msg._mapping.get("timestamp"),
                                "sender": msg._mapping.get("source"),
                                "target": msg._mapping.get("target"),
                                "action": msg._mapping.get("message_type"),
                                "content": msg._mapping.get("content"),
                                "type": "info"
                            })

                        results.append({
                            "id": conv_id,
                            "conversation_id": conv_id,
                            "started_at": row._mapping.get("started_at"),
                            "created_at": row._mapping.get("started_at"),
                            "ended_at": row._mapping.get("last_update"),
                            "phase": "active",
                            "current_phase": "active",
                            "participants": list(participants),
                            "message_count": row._mapping.get("message_count"),
                            "messages": messages,
                            "duration_seconds": 0,
                            "status": "active"
                        })
            else:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Buscar mensagens mais recentes agrupadas por conversation_id
                query = """
                    SELECT conversation_id, 
                           MIN(timestamp) as started_at,
                           MAX(timestamp) as last_update,
                           COUNT(*) as message_count,
                           GROUP_CONCAT(DISTINCT source) as participants
                    FROM messages 
                    WHERE 1=1
                """
                params = []

                if agent:
                    query += " AND (source LIKE ? OR target LIKE ?)"
                    params.extend([f"%{agent}%", f"%{agent}%"])

                if since:
                    query += " AND timestamp >= ?"
                    params.append(since.isoformat() if hasattr(since, 'isoformat') else str(since))

                query += " GROUP BY conversation_id ORDER BY last_update DESC LIMIT ?"
                params.append(limit * 2)  # Pegar mais para compensar filtros

                cursor.execute(query, params)
                rows = cursor.fetchall()

                for row in rows:
                    conv_id = row["conversation_id"]
                    if conv_id in seen_ids:
                        continue
                    seen_ids.add(conv_id)

                    # Buscar mensagens desta conversa
                    cursor.execute("""
                        SELECT * FROM messages 
                        WHERE conversation_id = ? 
                        ORDER BY timestamp ASC
                    """, (conv_id,))
                    msg_rows = cursor.fetchall()

                    messages = []
                    participants = set()
                    for msg in msg_rows:
                        participants.add(msg["source"])
                        participants.add(msg["target"])
                        messages.append({
                            "timestamp": msg["timestamp"],
                            "sender": msg["source"],
                            "target": msg["target"],
                            "action": msg["message_type"],
                            "content": msg["content"],
                            "type": "info"
                        })

                    results.append({
                        "id": conv_id,
                        "conversation_id": conv_id,
                        "started_at": row["started_at"],
                        "created_at": row["started_at"],
                        "ended_at": row["last_update"],
                        "phase": "active",
                        "current_phase": "active",
                        "participants": list(participants),
                        "message_count": row["message_count"],
                        "messages": messages,
                        "duration_seconds": 0,
                        "status": "active"
                    })
                
                conn.close()
        except Exception as e:
            logger.error(f"Erro ao listar conversas do banco: {e}")
        
        # Ordenar por data e limitar
        results.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return results[:limit]
    
    def get_conversation_messages(
        self,
        conversation_id: str,
        message_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Obtém mensagens de uma conversa"""
        # Verificar cache primeiro
        conv = self.active_conversations.get(conversation_id)
        if conv:
            messages = [m.to_dict() for m in conv["messages"]]
            if message_types:
                messages = [m for m in messages if m["type"] in message_types]
            return messages
        
        # Buscar no banco
        try:
            if self.engine is not None:
                query = "SELECT * FROM messages WHERE conversation_id = :id"
                params = {"id": conversation_id}
                if message_types:
                    placeholders = ",".join([f":t{i}" for i in range(len(message_types))])
                    query += f" AND message_type IN ({placeholders})"
                    for i, t in enumerate(message_types):
                        params[f"t{i}"] = t

                query += " ORDER BY timestamp ASC"
                with self.engine.connect() as conn:
                    res = conn.execute(text(query), params)
                    rows = res.fetchall()
                    return [dict(r._mapping) for r in rows]
            else:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = "SELECT * FROM messages WHERE conversation_id = ?"
                params = [conversation_id]

                if message_types:
                    placeholders = ",".join("?" * len(message_types))
                    query += f" AND message_type IN ({placeholders})"
                    params.extend(message_types)

                query += " ORDER BY timestamp ASC"

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao obter mensagens: {e}")
            return []
    
    def analyze_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Análise detalhada de uma conversa"""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        
        messages = conv.get("messages", [])
        
        # Calcular métricas
        message_types = defaultdict(int)
        source_distribution = defaultdict(int)
        target_distribution = defaultdict(int)
        
        for msg in messages:
            message_types[msg["type"]] += 1
            source_distribution[msg["source"]] += 1
            target_distribution[msg["target"]] += 1
        
        return {
            "conversation_id": conversation_id,
            "summary": {
                "participants": conv["participants"],
                "total_messages": conv["message_count"],
                "duration_seconds": conv["duration_seconds"],
                "phase": conv["phase"]
            },
            "message_types": dict(message_types),
            "source_distribution": dict(source_distribution),
            "target_distribution": dict(target_distribution),
            "timeline": {
                "started_at": conv["started_at"],
                "ended_at": conv.get("ended_at"),
                "duration_minutes": round(conv.get("duration_seconds", 0) / 60, 2)
            }
        }
    
    def take_snapshot(self, conversation_id: str) -> ConversationSnapshot:
        """Tira snapshot de conversa em ponto no tempo"""
        conv = self.active_conversations.get(conversation_id)
        if not conv:
            return None
        
        snapshot = ConversationSnapshot(
            conversation_id=conversation_id,
            timestamp=datetime.now(),
            phase=ConversationPhase(conv["phase"]),
            participants=list(conv["participants"]),
            message_count=len(conv["messages"]),
            last_message=conv["messages"][-1].content if conv["messages"] else "",
            duration_seconds=conv["duration_seconds"]
        )
        
        # Armazenar snapshot
        self._store_snapshot(snapshot)
        self.conversation_history.append(snapshot)
        
        return snapshot
    
    def _store_snapshot(self, snapshot: ConversationSnapshot):
        """Armazena snapshot no banco"""
        try:
            if self.engine is not None:
                with self.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO conversation_snapshots
                        (conversation_id, timestamp, phase, participants, message_count, last_message)
                        VALUES (:conversation_id, :timestamp, :phase, :participants, :message_count, :last_message)
                    """), {
                        "conversation_id": snapshot.conversation_id,
                        "timestamp": snapshot.timestamp.isoformat(),
                        "phase": snapshot.phase.value,
                        "participants": ",".join(snapshot.participants),
                        "message_count": snapshot.message_count,
                        "last_message": snapshot.last_message[:1000]
                    })
            else:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO conversation_snapshots
                    (conversation_id, timestamp, phase, participants, message_count, last_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    snapshot.conversation_id,
                    snapshot.timestamp.isoformat(),
                    snapshot.phase.value,
                    ",".join(snapshot.participants),
                    snapshot.message_count,
                    snapshot.last_message[:1000]
                ))

                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"Erro ao armazenar snapshot: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de interceptação"""
        return {
            **self.stats,
            "active_conversations": len(self.active_conversations),
            "active_conversations_list": self.list_active_conversations(),
            "uptime_seconds": (datetime.now() - self.stats["start_time"]).total_seconds()
        }
    
    def export_conversation(self, conversation_id: str, format: str = "json") -> str:
        """Exporta conversa em formato específico"""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        
        if format == "json":
            return json.dumps(conv, indent=2, ensure_ascii=False, default=str)
        
        elif format == "markdown":
            lines = [
                f"# Conversa: {conversation_id}",
                f"\n**Participantes:** {', '.join(conv['participants'])}",
                f"**Fase:** {conv['phase']}",
                f"**Duração:** {conv['duration_seconds']:.2f}s",
                f"**Total de Mensagens:** {conv['message_count']}",
                "\n## Mensagens\n"
            ]
            
            for msg in conv.get("messages", []):
                lines.append(f"### [{msg['timestamp']}] {msg['type'].upper()}")
                lines.append(f"**{msg['source']}** → **{msg['target']}**\n")
                lines.append(f"```\n{msg['content']}\n```\n")
            
            return "\n".join(lines)
        
        else:
            return str(conv)
    
    def finalize_conversation(self, conversation_id: str) -> bool:
        """Finaliza conversa e move para histórico"""
        conv = self.active_conversations.pop(conversation_id, None)
        if not conv:
            return False
        
        try:
            participants = ",".join(conv["participants"])
            if self.engine is not None:
                with self.engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO conversations
                        (id, started_at, ended_at, phase, participants, total_messages, duration_seconds, status)
                        VALUES (:id, :started_at, :ended_at, :phase, :participants, :total_messages, :duration_seconds, :status)
                    """), {
                        "id": conversation_id,
                        "started_at": conv["started_at"].isoformat(),
                        "ended_at": datetime.now().isoformat(),
                        "phase": conv["phase"],
                        "participants": participants,
                        "total_messages": len(conv["messages"]),
                        "duration_seconds": conv["duration_seconds"],
                        "status": "completed"
                    })
            else:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO conversations
                    (id, started_at, ended_at, phase, participants, total_messages, duration_seconds, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conversation_id,
                    conv["started_at"].isoformat(),
                    datetime.now().isoformat(),
                    conv["phase"],
                    participants,
                    len(conv["messages"]),
                    conv["duration_seconds"],
                    "completed"
                ))

                conn.commit()
                conn.close()

            self.stats["total_conversations"] += 1
            return True
        except Exception as e:
            logger.error(f"Erro ao finalizar conversa: {e}")
            return False


# Singleton global
def get_agent_interceptor() -> AgentConversationInterceptor:
    """Obtém instância global do interceptador"""
    return AgentConversationInterceptor()
