#!/usr/bin/env python3
"""
Push Interceptor — Bloqueia push autônomo dos agents para branches protegidas

Fluxo:
  Agent.push_code(branch="main") → PushInterceptor checks → 403 Forbidden
  Agent.push_code(branch="feature/xyz") → OK (feature branch liberada)
  Agent quer mergeliber para main → ReviewAgent aprova → merge automático

Integração:
  Todos os push_code/push_project chamam interceptor primeiro
"""
import logging
from typing import Dict, List
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Branches protegidas que agents NÃO podem fazer push
PROTECTED_BRANCHES = [
    "main",
    "master",
    "develop",
    "production",
    "prod",
]

# Prefixos de branch liberados para agents
ALLOWED_BRANCH_PREFIXES = [
    "feature/",
    "fix/",
    "chore/",
    "docs/",
    "refactor/",
    "test/",
    "dev/",
    "wip/",
]


def check_push_allowed(
    branch: str,
    agent_name: str,
    source: str = "agent",
) -> bool:
    """
    Verificar se um push é permitido.
    
    Args:
        branch: branch de destino
        agent_name: agent que tá tentando fazer push
        source: "agent" ou "review_service" (review_service bypassa)
    
    Returns:
        True se permitido, levanta exception se não
    
    Raises:
        HTTPException: 403 se push bloqueado
    """
    
    # ReviewService é confiado, pode fazer push para main
    if source == "review_service":
        logger.info("✅ Push permitido (ReviewService): %s → %s", agent_name, branch)
        return True
    
    # Agentes só podem fazer push em branches não-protegidas
    if branch.lower() in PROTECTED_BRANCHES:
        logger.warning(
            "❌ Push bloqueado: agent %s tentou push para %s (protegida)",
            agent_name,
            branch
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Push para branch protegida bloqueado",
                "branch": branch,
                "reason": "Use ReviewAgent para submeter para main",
                "alternative": "POST /review/submit",
                "guide": "docs/REVIEW_QUALITY_GATE.md"
            }
        )
    
    # Verificar se branch tem prefixo permitido
    allowed = any(branch.lower().startswith(prefix) for prefix in ALLOWED_BRANCH_PREFIXES)
    
    if not allowed:
        logger.warning(
            "❌ Push bloqueado: branch %s não segue padrão permitido",
            branch
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Branch não segue convenção permitida",
                "branch": branch,
                "allowed_prefixes": ALLOWED_BRANCH_PREFIXES,
            }
        )
    
    logger.info("✅ Push permitido: %s → %s", agent_name, branch)
    return True


def get_review_branch(agent_name: str, feature_name: str) -> str:
    """
    Gerar nome de branch para um feature antes de review.
    
    Exemplo: python_agent + "add-cache" → "feature/python-add-cache"
    """
    return f"feature/{agent_name.split('_')[0]}-{feature_name}"


def block_autonomous_push_decorator(f):
    """
    Decorator para metodos push em agent_manager/github_client.
    Se branch é protegida e source é agent, bloqueia.
    """
    async def wrapper(
        self,
        *args,
        branch: str = "main",
        agent_source: str = "agent",
        **kwargs
    ):
        # Check antes de executar
        try:
            check_push_allowed(branch, agent_source)
        except HTTPException as e:
            logger.error("Push bloqueado: %s", e.detail)
            raise
        
        # OK, prosseguir
        return await f(self, *args, branch=branch, **kwargs)
    
    return wrapper
