"""
Testes unitários para o Google Assistant Home Automation Agent.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------
# Mock de módulos pesados que não estão instalados no env local
# (httpx, paramiko, chromadb, etc.) para que os imports não falhem.
# ---------------------------------------------------------------
for _mod in ("httpx", "paramiko", "chromadb", "sentence_transformers"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ---------------------------------------------------------------
# DeviceManager tests
# ---------------------------------------------------------------

class TestDeviceManager:
    """Testes para o gerenciador de dispositivos."""

    def _make_manager(self, tmp_path):
        from specialized_agents.home_automation.device_manager import DeviceManager
        return DeviceManager(data_dir=tmp_path)

    def test_register_and_list(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType, DeviceState
        mgr = self._make_manager(tmp_path)
        dev = Device(id="luz1", name="Luz Sala", device_type=DeviceType.LIGHT, room="Sala")
        mgr.register_device(dev)
        assert len(mgr.devices) == 1
        assert mgr.get_device("luz1").name == "Luz Sala"

    def test_remove_device(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType
        mgr = self._make_manager(tmp_path)
        mgr.register_device(Device(id="d1", name="Dev1", device_type=DeviceType.SWITCH))
        assert mgr.remove_device("d1") is True
        assert mgr.get_device("d1") is None
        assert mgr.remove_device("inexistente") is False

    def test_set_state(self, tmp_path):
        from specialized_agents.home_automation.device_manager import (
            Device, DeviceType, DeviceState, DeviceManager
        )
        mgr = self._make_manager(tmp_path)
        mgr.register_device(Device(id="plug1", name="Tomada Cozinha",
                                    device_type=DeviceType.PLUG, room="Cozinha"))
        updated = mgr.set_device_state("plug1", DeviceState.ON)
        assert updated is not None
        assert updated.state == DeviceState.ON
        assert mgr.set_device_state("inexistente", DeviceState.OFF) is None

    def test_list_rooms(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType
        mgr = self._make_manager(tmp_path)
        mgr.register_device(Device(id="a", name="A", device_type=DeviceType.LIGHT, room="Sala"))
        mgr.register_device(Device(id="b", name="B", device_type=DeviceType.FAN, room="Quarto"))
        rooms = mgr.list_rooms()
        assert "Quarto" in rooms
        assert "Sala" in rooms

    def test_filter_by_type(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType
        mgr = self._make_manager(tmp_path)
        mgr.register_device(Device(id="l1", name="Luz", device_type=DeviceType.LIGHT, room="Sala"))
        mgr.register_device(Device(id="s1", name="Switch", device_type=DeviceType.SWITCH, room="Sala"))
        lights = mgr.list_devices(room="Sala", device_type=DeviceType.LIGHT)
        assert len(lights) == 1
        assert lights[0].device_type == DeviceType.LIGHT

    def test_persistence_roundtrip(self, tmp_path):
        from specialized_agents.home_automation.device_manager import (
            Device, DeviceType, DeviceState, DeviceManager
        )
        mgr1 = self._make_manager(tmp_path)
        mgr1.register_device(Device(id="x1", name="X1", device_type=DeviceType.THERMOSTAT,
                                     room="Sala", temperature=24.5))
        mgr1.set_device_state("x1", DeviceState.ON, target_temperature=22)
        # Reload
        mgr2 = self._make_manager(tmp_path)
        dev = mgr2.get_device("x1")
        assert dev is not None
        assert dev.state == DeviceState.ON
        assert dev.target_temperature == 22

    def test_scene_create_and_activate(self, tmp_path):
        from specialized_agents.home_automation.device_manager import (
            Device, DeviceType, DeviceState, Scene, DeviceManager
        )
        mgr = self._make_manager(tmp_path)
        mgr.register_device(Device(id="l1", name="Luz", device_type=DeviceType.LIGHT))
        mgr.register_device(Device(id="l2", name="Luz2", device_type=DeviceType.LIGHT))
        scene = Scene(
            id="s1", name="Noite",
            actions=[
                {"device_id": "l1", "command": "set_state", "params": {"state": "off"}},
                {"device_id": "l2", "command": "set_state", "params": {"state": "off"}},
            ],
        )
        mgr.create_scene(scene)
        results = mgr.activate_scene("s1")
        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert mgr.get_device("l1").state == DeviceState.OFF

    def test_stats(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType, DeviceState
        mgr = self._make_manager(tmp_path)
        mgr.register_device(Device(id="a", name="A", device_type=DeviceType.LIGHT,
                                    state=DeviceState.ON))
        mgr.register_device(Device(id="b", name="B", device_type=DeviceType.PLUG,
                                    state=DeviceState.OFFLINE))
        s = mgr.stats()
        assert s["total_devices"] == 2
        assert s["devices_online"] == 1
        assert s["devices_offline"] == 1


# ---------------------------------------------------------------
# GoogleAssistantAgent tests
# ---------------------------------------------------------------

class TestGoogleAssistantAgent:
    """Testes para o agente principal."""

    def _make_agent(self, tmp_path):
        """Cria agente com device_manager apontando para tmp_path."""
        from specialized_agents.home_automation.agent import GoogleAssistantAgent
        from specialized_agents.home_automation.device_manager import DeviceManager
        agent = GoogleAssistantAgent.__new__(GoogleAssistantAgent)
        agent.agent_type = "google_assistant"
        agent.device_manager = DeviceManager(data_dir=tmp_path)
        agent._google_token = None
        agent._google_project_id = None
        agent._ollama_url = "http://localhost:11434"
        agent._ollama_model = "test"
        agent._memory = None
        agent._bus = None
        agent._initialized = True
        return agent

    def test_capabilities(self, tmp_path):
        agent = self._make_agent(tmp_path)
        caps = agent.capabilities
        assert len(caps) > 5
        assert any("luz" in c.lower() for c in caps)

    def test_get_status(self, tmp_path):
        agent = self._make_agent(tmp_path)
        status = agent.get_status()
        assert status["agent"] == "Google Assistant Home Agent"
        assert "total_devices" in status

    def test_quick_parse_on_off(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType
        agent = self._make_agent(tmp_path)
        agent.device_manager.register_device(
            Device(id="luz_sala", name="Luz da Sala", device_type=DeviceType.LIGHT, room="Sala")
        )
        result = agent._quick_parse("ligar luz da sala")
        assert result is not None
        assert result["action"] == "on"

    def test_quick_parse_temperature(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType
        agent = self._make_agent(tmp_path)
        agent.device_manager.register_device(
            Device(id="ac1", name="Ar Condicionado", device_type=DeviceType.AC, room="Quarto")
        )
        result = agent._quick_parse("ligar ar condicionado a 22 graus")
        assert result is not None
        assert result["params"].get("temperature") == 22

    def test_resolve_devices_by_name(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType
        agent = self._make_agent(tmp_path)
        agent.device_manager.register_device(
            Device(id="tv1", name="TV Sala", device_type=DeviceType.TV, room="Sala")
        )
        devices = agent._resolve_devices({"target": "tv sala"})
        assert len(devices) == 1
        assert devices[0].id == "tv1"

    def test_resolve_devices_by_room(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType
        agent = self._make_agent(tmp_path)
        agent.device_manager.register_device(
            Device(id="l1", name="Luz1", device_type=DeviceType.LIGHT, room="Quarto")
        )
        agent.device_manager.register_device(
            Device(id="l2", name="Luz2", device_type=DeviceType.LIGHT, room="Quarto")
        )
        devices = agent._resolve_devices({"target": "quarto", "device_type": "light"})
        assert len(devices) == 2

    def test_execute_action_on_off(self, tmp_path):
        import asyncio
        from specialized_agents.home_automation.device_manager import Device, DeviceType, DeviceState
        agent = self._make_agent(tmp_path)
        dev = Device(id="plug1", name="Tomada", device_type=DeviceType.PLUG)
        agent.device_manager.register_device(dev)
        result = asyncio.get_event_loop().run_until_complete(
            agent._execute_action(dev, {"action": "on", "params": {}})
        )
        assert result["success"] is True
        assert agent.device_manager.get_device("plug1").state == DeviceState.ON

    def test_execute_action_brightness(self, tmp_path):
        import asyncio
        from specialized_agents.home_automation.device_manager import Device, DeviceType
        agent = self._make_agent(tmp_path)
        dev = Device(id="lz", name="Luz", device_type=DeviceType.LIGHT)
        agent.device_manager.register_device(dev)
        result = asyncio.get_event_loop().run_until_complete(
            agent._execute_action(dev, {"action": "set_brightness", "params": {"brightness": 75}})
        )
        assert result["success"] is True
        assert result["brightness"] == 75

    def test_process_command_no_device(self, tmp_path):
        import asyncio
        agent = self._make_agent(tmp_path)
        result = asyncio.get_event_loop().run_until_complete(
            agent.process_command("ligar nada")
        )
        assert result["success"] is False

    def test_create_scene(self, tmp_path):
        import asyncio
        agent = self._make_agent(tmp_path)
        scene = asyncio.get_event_loop().run_until_complete(
            agent.create_scene("Teste", [{"device_id": "x", "command": "set_state", "params": {"state": "on"}}])
        )
        assert scene.name == "Teste"
        assert len(agent.device_manager.scenes) == 1

    def test_create_routine(self, tmp_path):
        import asyncio
        agent = self._make_agent(tmp_path)
        routine = asyncio.get_event_loop().run_until_complete(
            agent.create_routine("Wake Up", "0 7 * * *", [])
        )
        assert routine.trigger == "0 7 * * *"
        assert routine.enabled

    def test_command_history(self, tmp_path):
        from specialized_agents.home_automation.device_manager import Device, DeviceType, DeviceState
        agent = self._make_agent(tmp_path)
        agent.device_manager.register_device(
            Device(id="d1", name="D1", device_type=DeviceType.SWITCH)
        )
        agent.device_manager.set_device_state("d1", DeviceState.ON)
        history = agent.get_command_history()
        assert len(history) >= 1
        assert history[-1]["device_id"] == "d1"
