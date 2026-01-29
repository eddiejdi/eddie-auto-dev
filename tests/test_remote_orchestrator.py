import os
import importlib

import pytest


def test_agent_manager_uses_remote_orchestrator(monkeypatch):
    # Force env for remote orchestrator
    monkeypatch.setenv("REMOTE_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.setenv("HOMELAB_HOST", "127.0.0.1")
    monkeypatch.setenv("HOMELAB_USER", "root")

    # Reload modules to pick up new config
    import specialized_agents.config as cfg
    importlib.reload(cfg)

    from specialized_agents.agent_manager import get_agent_manager, reset_agent_manager
    from specialized_agents.remote_orchestrator import RemoteOrchestrator

    reset_agent_manager()
    mgr = get_agent_manager()

    assert getattr(mgr, "_remote_orchestrator", False) is True
    assert isinstance(mgr.docker, RemoteOrchestrator)

    # cleanup
    reset_agent_manager()
