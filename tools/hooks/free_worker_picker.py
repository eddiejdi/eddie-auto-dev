#!/usr/bin/env python3
"""Escolhe um worker free funcional para sidequests.

DEV: prefere Xiaomi MiMo, depois DeepSeek, se o catálogo/probe confirmar.
PROD: só fleet OpenRouter PASS (sem LLM chinês).
Fallback local: Pi + Ollama (sem evict de trading-*).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from runtime_env import is_prod

FLEET_PATH: Final[Path] = Path.home() / "apps/agents/agents/free-openrouter/fleet.yaml"
CACHE_PATH: Final[Path] = Path.home() / ".grok/state/sidequests/worker-cache.json"
CACHE_TTL_SEC: Final[int] = 300
OPENROUTER_MODELS_URL: Final[str] = "https://openrouter.ai/api/v1/models"
PROBE_TIMEOUT_SEC: Final[float] = 2.5

DEV_PREFERRED: Final[tuple[dict[str, str], ...]] = (
    {
        "name": "mimo-v2.5",
        "harness": "openrouter",
        "model": "openrouter:xiaomi/mimo-v2.5",
        "family": "mimo",
    },
    {
        "name": "mimo-v2.5-pro",
        "harness": "openrouter",
        "model": "openrouter:xiaomi/mimo-v2.5-pro",
        "family": "mimo",
    },
    {
        "name": "deepseek-v3.2",
        "harness": "openrouter",
        "model": "openrouter:deepseek/deepseek-v3.2",
        "family": "deepseek",
    },
    {
        "name": "deepseek-chat",
        "harness": "openrouter",
        "model": "openrouter:deepseek/deepseek-chat",
        "family": "deepseek",
    },
)

LOCAL_FALLBACK: Final[dict[str, str]] = {
    "name": "pi-ollama-local",
    "harness": "pi",
    "model": "ollama/coordinator:11437",
    "family": "local",
}


@dataclass(frozen=True)
class WorkerPick:
    """Worker escolhido para um sidequest."""

    name: str
    harness: str
    model: str
    family: str
    source: str
    env: str
    functional: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        """Serializa para JSON."""
        return asdict(self)

    def one_liner(self) -> str:
        """Linha curta para additionalContext."""
        status = "funcional" if self.functional else "não-provado"
        return (
            f"{self.harness} model={self.model} "
            f"(family={self.family}, env={self.env}, {status}, via {self.source})"
        )


def _parse_fleet_active(text: str) -> list[dict[str, str]]:
    """Parser mínimo do bloco ``active:`` do fleet.yaml (sem PyYAML)."""
    workers: list[dict[str, str]] = []
    in_active = False
    current: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("excluded:"):
            if current.get("model"):
                workers.append(current)
            break
        if stripped.startswith("active:"):
            in_active = True
            continue
        if not in_active:
            continue
        if stripped.startswith("- name:"):
            if current.get("model"):
                workers.append(current)
            current = {"name": stripped.split(":", 1)[1].strip()}
            continue
        if stripped.startswith("model:") and current is not None:
            current["model"] = stripped.split(":", 1)[1].strip()
            current.setdefault("harness", "openrouter")
            current.setdefault("family", "fleet")
        if stripped.startswith("status:") and current is not None:
            current["status"] = stripped.split(":", 1)[1].strip()
    if current.get("model") and current.get("status", "pass") == "pass":
        workers.append(current)
    return [w for w in workers if w.get("status", "pass") == "pass" and w.get("model")]


def load_fleet_workers(fleet_path: Path | None = None) -> list[dict[str, str]]:
    """Lê workers PASS do fleet.yaml."""
    path = fleet_path or FLEET_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return _parse_fleet_active(text)


def _normalize_model_id(model: str) -> str:
    return model.replace("openrouter:", "").strip().lower()


def fetch_openrouter_model_ids(
    url: str = OPENROUTER_MODELS_URL,
    timeout: float = PROBE_TIMEOUT_SEC,
) -> set[str] | None:
    """Lista ids do catálogo OpenRouter. None se a rede falhar."""
    req = urllib.request.Request(url, headers={"User-Agent": "rpa4all-sidequest/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return None
    ids: set[str] = set()
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            ids.add(str(item["id"]).strip().lower())
    return ids or None


def _read_cache(path: Path) -> set[str] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    ts = float(raw.get("ts") or 0)
    if time.time() - ts > CACHE_TTL_SEC:
        return None
    ids = raw.get("ids")
    if not isinstance(ids, list):
        return None
    return {str(i).lower() for i in ids}


def _write_cache(path: Path, ids: set[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"ts": time.time(), "ids": sorted(ids)}),
            encoding="utf-8",
        )
    except OSError:
        pass


def catalog_model_ids(
    *,
    probe: Callable[[], set[str] | None] | None = None,
    cache_path: Path | None = None,
    use_network: bool = True,
) -> set[str] | None:
    """Catálogo funcional (cache + probe opcional)."""
    path = cache_path or CACHE_PATH
    cached = _read_cache(path)
    if cached is not None:
        return cached
    if not use_network:
        return None
    fetcher = probe or fetch_openrouter_model_ids
    ids = fetcher()
    if ids:
        _write_cache(path, ids)
    return ids


def _is_listed(model: str, catalog: set[str] | None) -> bool:
    if catalog is None:
        return True
    nid = _normalize_model_id(model)
    if nid in catalog:
        return True
    return any(nid == cid or nid.endswith(f"/{cid}") or cid.endswith(nid) for cid in catalog)


def pick_worker(
    *,
    cwd: str | None = None,
    environ: Mapping[str, str] | None = None,
    fleet_path: Path | None = None,
    catalog: set[str] | None | object = ...,
    use_network: bool = True,
) -> WorkerPick:
    """Escolhe o primeiro worker funcional segundo a política DEV/PROD.

    Args:
        cwd: Diretório para resolver o ambiente.
        environ: Env override.
        fleet_path: fleet.yaml alternativo.
        catalog: set de ids; ``None`` = assumir listado; omitido = probe/cache.
        use_network: Se False, não chama OpenRouter.
    """
    env_name = "prod" if is_prod(cwd=cwd, environ=environ) else "dev"
    if catalog is ...:
        catalog = catalog_model_ids(use_network=use_network)

    candidates: Sequence[dict[str, str]]
    source: str
    if env_name == "dev":
        fleet = load_fleet_workers(fleet_path)
        candidates = list(DEV_PREFERRED) + fleet
        source = "dev-preferred+fleet"
    else:
        candidates = load_fleet_workers(fleet_path)
        source = "prod-fleet-pass"

    for cand in candidates:
        model = cand.get("model", "")
        if not model:
            continue
        listed = _is_listed(model, catalog if isinstance(catalog, set) or catalog is None else None)
        if not listed:
            continue
        return WorkerPick(
            name=cand.get("name", model),
            harness=cand.get("harness", "openrouter"),
            model=model,
            family=cand.get("family", "fleet"),
            source=source,
            env=env_name,
            functional=catalog is not None,
            reason="listado no catálogo" if catalog is not None else "sem probe; primeiro preferido",
        )

    fb = LOCAL_FALLBACK
    return WorkerPick(
        name=fb["name"],
        harness=fb["harness"],
        model=fb["model"],
        family=fb["family"],
        source="local-fallback",
        env=env_name,
        functional=False,
        reason="nenhum OpenRouter funcional; use Pi+Ollama sem evict de trading-*",
    )


def main() -> int:
    """CLI: imprime o worker escolhido em JSON."""
    pick = pick_worker()
    print(json.dumps(pick.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
