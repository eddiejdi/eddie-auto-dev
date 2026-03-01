#!/usr/bin/env python3
"""
Unit Tests for Communication Bus - Parte 3

Testes cobrem:
- Registro de componentes
- Pub/Sub messaging
- Priority queues  
- Request/Response pattern
- Message serialization
- Message history/filtering
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from specialized_agents.comm_bus import (
    CommBus,
    Message,
    MessageType,
    MessagePriority,
    get_comm_bus,
    publish_routing_decision,
    publish_execution_outcome,
    publish_resource_status,
)


class TestMessageDataStructure:
    """Testes da estrutura de mensagem"""
    
    def test_message_creation(self):
        """Criar mensagem com valores padrão"""
        msg = Message(
            message_type=MessageType.DECISION,
            source="controller",
            target="python_agent"
        )
        assert msg.message_type == MessageType.DECISION
        assert msg.source == "controller"
        assert msg.priority == MessagePriority.NORMAL
        assert msg.message_id is not None
    
    def test_message_with_content(self):
        """Criar mensagem com conteúdo"""
        content = {"task_id": "task_123", "priority": "high"}
        msg = Message(
            message_type=MessageType.OUTCOME,
            source="agent",
            content=content
        )
        assert msg.content == content
        assert msg.content["task_id"] == "task_123"
    
    def test_message_serialization(self):
        """Serializar e deserializar mensagem"""
        original = Message(
            message_type=MessageType.DECISION,
            source="controller",
            target="agent",
            content={"key": "value"}
        )
        
        data = original.to_dict()
        restored = Message.from_dict(data)
        
        assert restored.message_type == original.message_type
        assert restored.source == original.source
        assert restored.content == original.content


@pytest.mark.asyncio
class TestCommBusRegistration:
    """Testes de registro de componentes"""
    
    async def test_register_component(self):
        """Registrar componente no bus"""
        bus = CommBus()
        await bus.register_component("controller_1")
        
        assert "controller_1" in bus.inbox
    
    async def test_register_multiple_components(self):
        """Registrar múltiplos componentes"""
        bus = CommBus()
        components = ["controller", "agent_python", "agent_go", "resource_mgr"]
        
        for comp in components:
            await bus.register_component(comp)
        
        assert len(bus.inbox) == len(components)


@pytest.mark.asyncio
class TestCommBusPublishing:
    """Testes de publicação de mensagens"""
    
    async def test_publish_single_target(self):
        """Publicar para alvo específico"""
        bus = CommBus()
        await bus.register_component("controller")
        await bus.register_component("agent")
        
        msg = Message(
            message_type=MessageType.DECISION,
            source="controller",
            target="agent"
        )
        
        msg_id = await bus.publish(msg)
        assert msg_id == msg.message_id
        assert len(bus.message_log) == 1
    
    async def test_publish_to_queue(self):
        """Mensagem deve chegar na fila do alvo"""
        bus = CommBus()
        await bus.register_component("source")
        await bus.register_component("target")
        
        msg = Message(
            message_type=MessageType.REQUEST,
            source="source",
            target="target",
            content={"data": "test"}
        )
        
        await bus.publish(msg)
        
        # Target deve receber mensagem
        received = await asyncio.wait_for(
            bus.get_message("target"),
            timeout=1.0
        )
        assert received.content == {"data": "test"}
    
    async def test_broadcast_message(self):
        """Enviar mensagem em broadcast para todos"""
        bus = CommBus()
        components = ["comp1", "comp2", "comp3"]
        for comp in components:
            await bus.register_component(comp)
        
        msg = Message(
            message_type=MessageType.ALERT,
            source="comp1",
            target="broadcast"
        )
        
        await bus.publish(msg, broadcast=True)
        
        # Todos exceto source devem receber
        for comp in components:
            if comp != "comp1":
                received = await asyncio.wait_for(
                    bus.get_message(comp),
                    timeout=1.0
                )
                assert received.message_type == MessageType.ALERT


@pytest.mark.asyncio
class TestCommBusPriority:
    """Testes de fila com prioridade"""
    
    async def test_urgent_processed_first(self):
        """URGENT processa antes de NORMAL"""
        bus = CommBus()
        await bus.register_component("receiver")
        
        # Enviar NORMAL primeiro
        msg_normal = Message(
            message_type=MessageType.REQUEST,
            source="s1",
            target="receiver",
            priority=MessagePriority.NORMAL,
            content={"order": 1}
        )
        await bus.publish(msg_normal)
        
        # Depois enviar URGENT
        msg_urgent = Message(
            message_type=MessageType.ALERT,
            source="s2",
            target="receiver",
            priority=MessagePriority.URGENT,
            content={"order": 2}
        )
        await bus.publish(msg_urgent)
        
        # URGENT deve ser processado primeiro
        first = await asyncio.wait_for(
            bus.get_message("receiver"),
            timeout=1.0
        )
        assert first.priority == MessagePriority.URGENT
        assert first.content["order"] == 2
    
    async def test_normal_before_background(self):
        """NORMAL processa antes de BACKGROUND"""
        bus = CommBus()
        await bus.register_component("rcv")
        
        await bus.publish(Message(
            source="s1", target="rcv",
            priority=MessagePriority.BACKGROUND,
            content={"order": 1}
        ))
        
        await bus.publish(Message(
            source="s2", target="rcv",
            priority=MessagePriority.NORMAL,
            content={"order": 2}
        ))
        
        # NORMAL primeiro
        first = await asyncio.wait_for(bus.get_message("rcv"), timeout=1.0)
        assert first.priority == MessagePriority.NORMAL


@pytest.mark.asyncio
class TestCommBusSubscription:
    """Testes de subscription"""
    
    async def test_subscribe_component(self):
        """Inscrever componente em tipo de mensagem"""
        bus = CommBus()
        await bus.register_component("agent")
        
        await bus.subscribe("agent", MessageType.DECISION)
        
        assert "agent" in bus.subscribers.get(MessageType.DECISION, [])
    
    async def test_multiple_subscribers(self):
        """Múltiplos subscribers para mesmo tipo"""
        bus = CommBus()
        for comp in ["agent_py", "agent_go", "agent_rs"]:
            await bus.register_component(comp)
            await bus.subscribe(comp, MessageType.DECISION)
        
        assert len(bus.subscribers[MessageType.DECISION]) == 3


@pytest.mark.asyncio
class TestCommBusRequestResponse:
    """Testes de padrão request/response"""
    
    async def test_request_response_cycle(self):
        """Ciclo completo request/response"""
        bus = CommBus()
        await bus.register_component("requester")
        await bus.register_component("responder")
        
        # Enviar request
        request = Message(
            message_type=MessageType.REQUEST,
            source="requester",
            target="responder",
            content={"query": "test"}
        )
        
        # Start responder task
        async def respond_to_request():
            msg = await bus.get_message("responder")
            response = Message(
                message_type=MessageType.RESPONSE,
                source="responder",
                target="requester",
                reply_to=msg.message_id,
                content={"answer": "ok"}
            )
            await bus.send_response(response)
        
        responder_task = asyncio.create_task(respond_to_request())
        
        # Make request
        response = await bus.request_response(request, timeout=2.0)
        
        await responder_task
        
        assert response is not None
        assert response.message_type == MessageType.RESPONSE
        assert response.content["answer"] == "ok"
    
    async def test_request_timeout(self):
        """Request sem response deve timeout"""
        bus = CommBus()
        await bus.register_component("requester")
        await bus.register_component("responder")
        
        request = Message(
            message_type=MessageType.REQUEST,
            source="requester",
            target="responder"
        )
        
        response = await bus.request_response(request, timeout=0.5)
        assert response is None


@pytest.mark.asyncio
class TestCommBusMessageLog:
    """Testes de histórico de mensagens"""
    
    async def test_message_history(self):
        """Mensagens devem ser registradas"""
        bus = CommBus()
        await bus.register_component("src")
        await bus.register_component("tgt")
        
        for i in range(5):
            msg = Message(
                message_type=MessageType.REQUEST if i % 2 == 0 else MessageType.RESPONSE,
                source="src",
                target="tgt",
                content={"num": i}
            )
            await bus.publish(msg)
        
        assert len(bus.message_log) == 5
    
    async def test_filter_by_type(self):
        """Filtrar histórico por tipo"""
        bus = CommBus()
        await bus.register_component("s")
        await bus.register_component("t")
        
        # Publicar mistos
        for i in range(3):
            await bus.publish(Message(
                message_type=MessageType.REQUEST,
                source="s", target="t"
            ))
            await bus.publish(Message(
                message_type=MessageType.RESPONSE,
                source="t", target="s"
            ))
        
        requests = bus.get_message_log(type_filter=MessageType.REQUEST)
        assert len(requests) == 3
    
    async def test_filter_by_component(self):
        """Filtrar histórico por componente"""
        bus = CommBus()
        await bus.register_component("a")
        await bus.register_component("b")
        
        # A envia para B
        for i in range(2):
            await bus.publish(Message(source="a", target="b"))
        
        # B envia para A
        for i in range(3):
            await bus.publish(Message(source="b", target="a"))
        
        a_history = bus.get_message_log(component_filter="a")
        assert len(a_history) == 5  # 2 sent + 3 received


@pytest.mark.asyncio
class TestCommBusStatistics:
    """Testes de estatísticas"""
    
    async def test_get_stats(self):
        """Obter estatísticas do bus"""
        bus = CommBus()
        await bus.register_component("c1")
        await bus.register_component("c2")
        
        await bus.publish(Message(
            message_type=MessageType.REQUEST,
            source="c1", target="c2"
        ))
        
        stats = bus.get_stats()
        assert stats["components"] == 2
        assert stats["total_messages"] == 1


@pytest.mark.asyncio
class TestCommBusHelpers:
    """Testes das funções helper"""
    
    async def test_publish_routing_decision(self):
        """Helper para publicar decisão de routing"""
        # Note: publish_routing_decision uses global singleton
        bus = get_comm_bus()
        
        # Clear previous messages
        bus.message_log.clear()
        bus.inbox.clear()
        
        await bus.register_component("master_controller")
        await bus.register_component("python")
        
        msg_id = await publish_routing_decision(
            controller_id="master_controller",
            agent_language="python",
            task_id="task_123",
            complexity=0.75,
            selected_model="gpt4",
            timeout_ms=5000
        )
        
        assert msg_id is not None
        assert len(bus.message_log) == 1
        
        msg = bus.message_log[0]
        assert msg.message_type == MessageType.DECISION
        assert msg.content["task_id"] == "task_123"
    
    async def test_publish_execution_outcome(self):
        """Helper para publicar resultado de execução"""
        bus = get_comm_bus()
        bus.message_log.clear()
        
        msg_id = await publish_execution_outcome(
            agent_id="python_agent_1",
            task_id="task_123",
            success=True,
            output="Result: 42",
            duration_ms=1234,
            quality_score=0.95
        )
        
        assert msg_id is not None
        msg = bus.message_log[-1]
        assert msg.message_type == MessageType.OUTCOME
        assert msg.content["success"] is True
    
    async def test_publish_resource_status(self):
        """Helper para publicar status de recursos"""
        bus = get_comm_bus()
        bus.message_log.clear()
        
        msg_id = await publish_resource_status(
            resource_manager_id="resource_mgr",
            agent_language="python",
            load=0.65,
            memory_mb=2048,
            active_tasks=3
        )
        
        assert msg_id is not None
        msg = bus.message_log[-1]
        assert msg.message_type == MessageType.STATUS
        assert msg.content["load"] == 0.65


@pytest.mark.asyncio
class TestCommBusSingleton:
    """Testes do padrão singleton"""
    
    async def test_singleton_instance(self):
        """get_comm_bus retorna mesma instância"""
        bus1 = get_comm_bus()
        bus2 = get_comm_bus()
        
        assert bus1 is bus2
    
    async def test_singleton_state_preserved(self):
        """Estado é preservado entre chamadas"""
        bus1 = get_comm_bus()
        await bus1.register_component("test_comp")
        
        bus2 = get_comm_bus()
        assert "test_comp" in bus2.inbox


@pytest.mark.asyncio
class TestCommBusConcurrency:
    """Testes de concorrência"""
    
    async def test_concurrent_publishes(self):
        """Publicar múltiplas mensagens concorrentemente"""
        bus = CommBus()
        await bus.register_component("target")
        
        async def send_message(i):
            msg = Message(
                message_type=MessageType.REQUEST,
                source=f"source_{i}",
                target="target",
                content={"num": i}
            )
            await bus.publish(msg)
        
        # Enviar 10 mensagens concorrentemente
        await asyncio.gather(*[send_message(i) for i in range(10)])
        
        assert len(bus.message_log) == 10
    
    async def test_concurrent_receives(self):
        """Receber múltiplas mensagens concorrentemente"""
        bus = CommBus()
        await bus.register_component("receiver")
        
        # Enviar mensagens
        for i in range(5):
            await bus.publish(Message(
                source=f"s{i}",
                target="receiver",
                content={"num": i}
            ))
        
        # Receber concorrentemente
        async def receive_all():
            msgs = []
            for _ in range(5):
                msg = await bus.get_message("receiver")
                msgs.append(msg)
            return msgs
        
        messages = await asyncio.wait_for(receive_all(), timeout=2.0)
        assert len(messages) == 5
