#!/usr/bin/env python3
"""Detecta se o agente está em DEV ou PROD.

Política 2026-08-17: LLM chinês (MiMo/DeepSeek/Qwen/…) é banido em **PROD**.
Em **DEV** (workstation, Traycer worktree, OpenRouter sidequest) é permitido.

Variáveis (primeira que estiver definida vence):
  RPA4ALL_ENV, HOMELAB_ENV, SHARED_AUTO_DEV_ENV, APP_ENV, ENVIRONMENT

Valores prod: prod, production, prd
Valores dev:  dev, development, local, test, ci

Sem variável: path contendo ``agents_workspace/prod`` → prod; caso contrário → dev.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

PROD_ENV_VALUES: Final[frozenset[str]] = frozenset({"prod", "production", "prd"})
DEV_ENV_VALUES: Final[frozenset[str]] = frozenset({"dev", "development", "local", "test", "ci"})

ENV_KEYS: Final[tuple[str, ...]] = (
    "RPA4ALL_ENV",
    "HOMELAB_ENV",
    "SHARED_AUTO_DEV_ENV",
    "APP_ENV",
    "ENVIRONMENT",
)

PROD_PATH_MARKERS: Final[tuple[str, ...]] = (
    "/agents_workspace/prod",
    "/home/homelab/prod/",
)


def resolve_runtime_env(
    cwd: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Retorna ``prod`` ou ``dev``.

    Args:
        cwd: Diretório atual. Default: ``os.getcwd()``.
        environ: Mapping de ambiente. Default: ``os.environ``.

    Returns:
        ``"prod"`` ou ``"dev"``.
    """
    env = environ if environ is not None else os.environ
    for key in ENV_KEYS:
        raw = str(env.get(key, "")).strip().lower()
        if raw in PROD_ENV_VALUES:
            return "prod"
        if raw in DEV_ENV_VALUES:
            return "dev"

    path = (cwd if cwd is not None else os.getcwd()).replace("\\", "/")
    if any(marker in path for marker in PROD_PATH_MARKERS):
        return "prod"
    return "dev"


def is_prod(cwd: str | None = None, environ: Mapping[str, str] | None = None) -> bool:
    """True quando o runtime é produção."""
    return resolve_runtime_env(cwd=cwd, environ=environ) == "prod"


def is_dev(cwd: str | None = None, environ: Mapping[str, str] | None = None) -> bool:
    """True quando o runtime é desenvolvimento (não-prod)."""
    return not is_prod(cwd=cwd, environ=environ)
