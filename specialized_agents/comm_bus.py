#!/usr/bin/env python3
"""
Parte 3: Communication Bus - Inter-agent message routing

Responsabilidades:
- Pub/sub message routing entre Master Controller, Resource Manager, e Agents
- Priority-based message delivery (URGENT > NORMAL > BACKGROUND)
- Message serialization (routing decisions, execution outcomes)
- Async-first design compatible with FastAPI

Message types:
- DECISION: Master Controller → Agent (routing decision)
- OUTCOME: Agent → Master Controller (execution result)
- STATUS: Resource Manager → Master Controller (resource status)
- ALERT: Any component → All (broadcast alerts)
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Message types"""
    DECISION = "decision"           # Master Controller → Agent
    OUTCOME = "outcome"             # Agent → Master Controller
    STATUS = "status"               # Resource Manager → Master Controller
    ALERT = "alert"                 # Broadcast alert
    REQUEST = "request"             # Generic request
    RESPONSE = "response"           # Generic response
    ACK = "ack"                     # Acknowledgement


class MessagePriority(str, Enum):
    """Message priority levels"""
    URGENT = "urgent"
    NORMAL = "normal"
    BACKGROUND = "background"


@dataclass
class Message:
    """Inter-agent message structure"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.REQUEST
    source: str = ""                # Component sending message
    target: str = ""                # Component receiving message (or "broadcast" for all)
    priority: MessagePriority = MessagePriority.NORMAL
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    conversation_id: Optional[str] = None
    reply_to: Optional[str] = None  # For request/response patterns
    ttl: int = 3600                 # Time to live in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        data = asdict(self)
        data['message_type'] = self.message_type.value
        data['priority'] = self.priority.value
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Deserialize from dict"""
        data['message_type'] = MessageType(data.get('message_type', 'request'))
        data['priority'] = MessagePriority(data.get('priority', 'normal'))
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class MessageQueue:
    """Priority-aware message queue"""
    
    def __init__(self):
        # Separate queues per priority
        self.urgent = asyncio.Queue()
        self.normal = asyncio.Queue()
        self.background = asyncio.Queue()
        self.all_queues = [self.urgent, self.normal, self.background]
    
    async def put(self, message: Message) -> None:
        """Enqueue message at appropriate priority"""
        if message.priority == MessagePriority.URGENT:
            await self.urgent.put(message)
        elif message.priority == MessagePriority.NORMAL:
            await self.normal.put(message)
        else:
            await self.background.put(message)
    
    async def get(self) -> Message:
        """Dequeue message respecting priority (URGENT > NORMAL > BACKGROUND)"""
        while True:
            # Check urgent first
            if not self.urgent.empty():
                return self.urgent.get_nowait()
            if not self.normal.empty():
                return self.normal.get_nowait()
            if not self.background.empty():
                return self.background.get_nowait()
            
            # All empty, wait for any
            done, _ = await asyncio.wait(
                [q.get() for q in self.all_queues],
                return_when=asyncio.FIRST_COMPLETED
            )
            result = done.pop()
            return await result
    
    def size(self) -> int:
        """Total message count"""
        return self.urgent.qsize() + self.normal.qsize() + self.background.qsize()


class CommBus:
    """
    Central communication bus for master controller, resource manager, and agents.
    
    Singleton pattern with pub/sub capabilities.
    """
    
    def __init__(self):
        self.inbox: Dict[str, MessageQueue] = {}       # Per-component inboxes
        self.subscribers: Dict[MessageType, List[str]] = {}  # Subscriptions
        self.message_log: List[Message] = []            # Message history
        self.response_futures: Dict[str, asyncio.Future] = {}  # For request/response
        self.lock = asyncio.Lock()
    
    async def register_component(self, component_id: str) -> None:
        """Register a new component (controller, agent, etc.)"""
        async with self.lock:
            if component_id not in self.inbox:
                self.inbox[component_id] = MessageQueue()
                logger.info(f"CommBus registered component: {component_id}")
    
    async def subscribe(
        self,
        component_id: str,
        message_type: MessageType,
    ) -> None:
        """Subscribe component to message type"""
        async with self.lock:
            if message_type not in self.subscribers:
                self.subscribers[message_type] = []
            if component_id not in self.subscribers[message_type]:
                self.subscribers[message_type].append(component_id)
                logger.info(
                    f"CommBus subscription: {component_id} -> {message_type.value}"
                )
    
    async def publish(
        self,
        message: Message,
        broadcast: bool = False,
    ) -> str:
        """
        Publish message to target(s).
        
        Returns message_id for tracking.
        """
        async with self.lock:
            message.timestamp = datetime.now()
            self.message_log.append(message)
            
            # Route to targets
            if broadcast or message.target == "broadcast":
                targets = list(self.inbox.keys())
            else:
                targets = [message.target] if message.target in self.inbox else []
            
            for target_id in targets:
                if target_id != message.source:  # Don't send to self
                    await self.inbox[target_id].put(message)
            
            logger.debug(
                f"CommBus published: {message.message_type.value} "
                f"from {message.source} → {targets}"
            )
            
            return message.message_id
    
    async def get_message(self, component_id: str, timeout: Optional[float] = None) -> Optional[Message]:
        """Get next message for component"""
        if component_id not in self.inbox:
            return None
        
        try:
            if timeout:
                return await asyncio.wait_for(self.inbox[component_id].get(), timeout)
            else:
                return await self.inbox[component_id].get()
        except asyncio.TimeoutError:
            return None
    
    async def request_response(
        self,
        request: Message,
        timeout: float = 30.0,
    ) -> Optional[Message]:
        """
        Send request and wait for response (request/response pattern).
        
        Returns response message or None if timeout.
        """
        # Setup future for response
        future: asyncio.Future = asyncio.Future()
        self.response_futures[request.message_id] = future
        
        try:
            # Publish request
            await self.publish(request)
            
            # Wait for response
            response = await asyncio.wait_for(future, timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"CommBus request timeout: {request.message_id}")
            return None
        finally:
            self.response_futures.pop(request.message_id, None)
    
    async def send_response(self, response: Message) -> None:
        """
        Send response to a previous request.
        
        response.reply_to should point to request.message_id
        """
        if response.reply_to and response.reply_to in self.response_futures:
            future = self.response_futures[response.reply_to]
            if not future.done():
                future.set_result(response)
        
        # Also publish to normal inbox
        await self.publish(response)
    
    def get_message_log(
        self,
        component_filter: Optional[str] = None,
        type_filter: Optional[MessageType] = None,
        limit: int = 100,
    ) -> List[Message]:
        """Get message history with optional filtering"""
        results = self.message_log
        
        if component_filter:
            results = [
                m for m in results
                if m.source == component_filter or m.target == component_filter
            ]
        
        if type_filter:
            results = [m for m in results if m.message_type == type_filter]
        
        # Return most recent first
        return sorted(results, key=lambda m: m.timestamp, reverse=True)[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bus statistics"""
        return {
            "components": len(self.inbox),
            "total_messages": len(self.message_log),
            "message_by_type": {
                mt.value: len(
                    [m for m in self.message_log if m.message_type == mt]
                )
                for mt in MessageType
            },
            "pending_messages": {
                cid: queue.size()
                for cid, queue in self.inbox.items()
            },
            "pending_responses": len(self.response_futures),
        }


# Singleton instance
_comm_bus: Optional[CommBus] = None


def get_comm_bus() -> CommBus:
    """Get or create singleton CommBus"""
    global _comm_bus
    if _comm_bus is None:
        _comm_bus = CommBus()
    return _comm_bus


# ============================================================================
# Helper Message Builders
# ============================================================================


async def publish_routing_decision(
    controller_id: str,
    agent_language: str,
    task_id: str,
    complexity: float,
    selected_model: str,
    timeout_ms: int,
    priority: MessagePriority = MessagePriority.NORMAL,
) -> str:
    """Helper to publish routing decision from controller"""
    bus = get_comm_bus()
    
    decision_msg = Message(
        message_type=MessageType.DECISION,
        source=controller_id,
        target=agent_language,
        priority=priority,
        content={
            "task_id": task_id,
            "complexity": complexity,
            "selected_model": selected_model,
            "timeout_ms": timeout_ms,
            "timestamp": datetime.now().isoformat(),
        }
    )
    
    return await bus.publish(decision_msg)


async def publish_execution_outcome(
    agent_id: str,
    task_id: str,
    success: bool,
    output: str,
    duration_ms: int,
    quality_score: float = 0.5,
) -> str:
    """Helper to publish execution outcome from agent"""
    bus = get_comm_bus()
    
    outcome_msg = Message(
        message_type=MessageType.OUTCOME,
        source=agent_id,
        target="master_controller",
        priority=MessagePriority.NORMAL,
        content={
            "task_id": task_id,
            "success": success,
            "output": output,
            "duration_ms": duration_ms,
            "quality_score": quality_score,
            "timestamp": datetime.now().isoformat(),
        }
    )
    
    return await bus.publish(outcome_msg)


async def publish_resource_status(
    resource_manager_id: str,
    agent_language: str,
    load: float,
    memory_mb: float,
    active_tasks: int,
) -> str:
    """Helper to publish resource status from manager"""
    bus = get_comm_bus()
    
    status_msg = Message(
        message_type=MessageType.STATUS,
        source=resource_manager_id,
        target="master_controller",
        priority=MessagePriority.NORMAL,
        content={
            "agent_language": agent_language,
            "load": load,
            "memory_mb": memory_mb,
            "active_tasks": active_tasks,
            "timestamp": datetime.now().isoformat(),
        }
    )
    
    return await bus.publish(status_msg)
