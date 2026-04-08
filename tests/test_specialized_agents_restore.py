import importlib
import sys
import types
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def test_get_dynamic_num_ctx_table_values() -> None:
    from specialized_agents.config import get_dynamic_num_ctx

    assert get_dynamic_num_ctx("qwen2.5-coder:1.5b") == 32768
    assert get_dynamic_num_ctx("deepseek-coder-v2:16b") == 8192
    assert get_dynamic_num_ctx("unknown-model:30b") == 4096


def test_get_dynamic_num_ctx_env_override(monkeypatch) -> None:
    from specialized_agents.config import get_dynamic_num_ctx

    monkeypatch.setenv("OLLAMA_NUM_CTX_QWEN3_14B", "4096")
    assert get_dynamic_num_ctx("qwen3:14b") == 4096


class DummyMetric:
    def labels(self, *args, **kwargs):
        return self

    def set(self, *args, **kwargs):
        pass

    def inc(self, *args, **kwargs):
        pass


class DummyBus:
    def subscribe(self, callback):
        self.subscribed = callback


def test_agent_network_exporter_import_with_dummy_prometheus(monkeypatch) -> None:
    dummy_prom = types.SimpleNamespace(
        start_http_server=lambda *args, **kwargs: None,
        Gauge=lambda *args, **kwargs: DummyMetric(),
        Counter=lambda *args, **kwargs: DummyMetric(),
        Info=lambda *args, **kwargs: DummyMetric(),
    )
    monkeypatch.setitem(sys.modules, "prometheus_client", dummy_prom)

    # Ensure SQLAlchemy import is not forced to connect during import.
    monkeypatch.setenv("DATABASE_URL", "")

    importer = importlib.import_module("specialized_agents.agent_network_exporter")
    exporter = importer.AgentNetworkExporter(port=9101)

    assert exporter.port == 9101
    assert exporter.engine is None
    assert exporter.messages_between is not None
    assert exporter.active_agents is not None
