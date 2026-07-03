"""
Módulo de gestão de usuários com pipeline automático.

Integra Authentik API, tracking em PostgreSQL e email.
"""

import enum
import html
import json
import logging
import os
import smtplib
from base64 import b64decode
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

import requests

from tools.authentik_management.authentik_os_login_guard import ensure_local_account

try:
    import psycopg2
except Exception:  # pragma: no cover - runtime fallback
    psycopg2 = None
logger = logging.getLogger(__name__)

# ── Configuração ───────────────────────────────────────────────────────────
AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "http://localhost:9000")
AUTHENTIK_TOKEN = os.getenv(
    "AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026"
)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/postgres",
)
MAIL_DOMAIN = os.getenv("MAIL_DOMAIN", "rpa4all.com")
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "https://nextcloud.rpa4all.com")
NEXTCLOUD_ANDROID_GPLAY_URL = os.getenv(
    "NEXTCLOUD_ANDROID_GPLAY_URL",
    "https://play.google.com/store/apps/details?id=com.nextcloud.client",
)
NEXTCLOUD_DEFAULT_GROUPS = [
    item.strip()
    for item in os.getenv("NEXTCLOUD_DEFAULT_GROUPS", "users").split(",")
    if item.strip()
]
NEXTCLOUD_TEAM_GROUP_PREFIX = os.getenv("RPA4ALL_TEAM_GROUP_PREFIX", "NC_TEAM_")
SMTP_HOST = os.getenv("SMTP_HOST", "mail.rpa4all.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", os.getenv("SMTP_FROM_EMAIL", "it@rpa4all.com"))
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "it@rpa4all.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "RPA4ALL Onboarding")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434").rstrip("/")
NEXTCLOUD_ONBOARDING_OLLAMA_MODEL = os.getenv(
    "NEXTCLOUD_ONBOARDING_OLLAMA_MODEL",
    os.getenv("OLLAMA_MODEL", "gemma3:1b"),
)
NEXTCLOUD_ONBOARDING_MEDIA_BASE_URL = os.getenv(
    "NEXTCLOUD_ONBOARDING_MEDIA_BASE_URL",
    "http://127.0.0.1:8503/orchestrator/media",
).rstrip("/")
NEXTCLOUD_ONBOARDING_ASSETS_DIR = Path(
    os.getenv(
        "NEXTCLOUD_ONBOARDING_ASSETS_DIR",
        str(Path(__file__).resolve().parent.parent / "data" / "nextcloud_onboarding"),
    )
)
CREATE_OS_USERS = os.getenv("AUTHENTIK_OS_CREATE_LOCAL_USER", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LOCAL_USER_SHELL = os.getenv("AUTHENTIK_OS_LOCAL_SHELL", "/bin/bash")
LOCAL_USER_GROUPS = [
    item.strip()
    for item in os.getenv("AUTHENTIK_OS_LOCAL_GROUPS", "").split(",")
    if item.strip()
]

_HEADERS = {
    "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
    "Content-Type": "application/json",
}

# ── SQL para tabela de tracking ────────────────────────────────────────────
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS user_management (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(200) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    authentik_id INTEGER,
    groups TEXT[] DEFAULT '{}',
    quota_mb INTEGER DEFAULT 5000,
    storage_quota_mb INTEGER DEFAULT 100000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    pipeline_steps JSONB DEFAULT '{}'::jsonb,
    error_message TEXT
);
"""


# ── Enums e dataclasses ───────────────────────────────────────────────────
class UserStatus(enum.Enum):
    """Status do pipeline de criação de usuário."""

    PENDING = "pending"
    AUTHENTIK_CREATED = "authentik_created"
    EMAIL_CREATED = "email_created"
    ENV_SETUP = "env_setup"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class UserConfig:
    """Configuração para criação de usuário."""

    username: str
    email: str
    full_name: str
    password: str
    groups: list[str] = field(default_factory=lambda: ["users"])
    quota_mb: int = 5000
    storage_quota_mb: int = 100000
    create_ssh_key: bool = True
    create_folders: bool = True
    send_welcome_email: bool = True
    provision_email_account: bool = True
    provision_local_account: bool = True
    service_profile: str = "full"


def _default_nextcloud_onboarding_payload() -> dict[str, Any]:
    """Fallback do onboarding caso Ollama ou mídia não estejam disponíveis."""
    return {
        "subject": "RPA4ALL | Seu acesso ao Nextcloud está pronto",
        "preheader": "Instale o app, entre com seu usuário RPA4ALL e ative sua nuvem pessoal.",
        "headline": "Seu Nextcloud RPA4ALL já pode ser usado",
        "intro": (
            "Preparamos seu acesso ao Nextcloud da RPA4ALL para arquivos, fotos, "
            "documentos e sincronização entre dispositivos."
        ),
        "steps": [
            "Abra o portal do Nextcloud pelo link abaixo.",
            "Entre com o usuário e a senha inicial enviados neste email.",
            "Instale o aplicativo Android pela Google Play para sincronizar arquivos e fotos.",
            "No primeiro acesso, confirme que suas pastas e permissões estão corretas.",
        ],
        "mobile_benefits": [
            "Upload automático de fotos e vídeos",
            "Acesso seguro aos arquivos da empresa",
            "Compartilhamento rápido por link",
        ],
        "admin_note": "Após o primeiro login, troque a senha temporária e valide o app no celular.",
        "image_prompts": [
            "Mockup premium de smartphone Android exibindo app Nextcloud corporativo RPA4ALL, tela de arquivos, tema branco e verde, captura de tela de produto SaaS",
            "Mockup premium de smartphone Android exibindo galeria e upload automático no app Nextcloud RPA4ALL, UI limpa, onboarding corporativo",
        ],
    }


def _dedupe(values: list[str]) -> list[str]:
    """Remove duplicidades preservando a ordem original."""
    return list(dict.fromkeys(item for item in values if item))


def _normalize_team_group(manager_username: str) -> str:
    """Converte o responsavel em nome de grupo do Authentik/Nextcloud."""
    normalized = "".join(
        char if char.isalnum() or char == "_" else "_"
        for char in manager_username.strip().lower()
    ).strip("_")
    return f"{NEXTCLOUD_TEAM_GROUP_PREFIX}{normalized}" if normalized else ""


def build_nextcloud_groups(
    extra_groups: Optional[list[str]] = None,
    *,
    manager_username: Optional[str] = None,
) -> list[str]:
    """Calcula os grupos necessarios para um usuario usar o Nextcloud."""
    groups = list(NEXTCLOUD_DEFAULT_GROUPS)
    if extra_groups:
        groups.extend(extra_groups)
    if manager_username:
        team_group = _normalize_team_group(manager_username)
        if team_group:
            groups.append(team_group)
    return _dedupe(groups)


def build_nextcloud_user_config(
    *,
    username: str,
    email: str,
    full_name: str,
    password: str,
    extra_groups: Optional[list[str]] = None,
    manager_username: Optional[str] = None,
    storage_quota_mb: int = 100000,
    send_welcome_email: bool = True,
) -> UserConfig:
    """Monta um perfil enxuto para provisionamento via Authentik/OIDC do Nextcloud."""
    return UserConfig(
        username=username,
        email=email,
        full_name=full_name,
        password=password,
        groups=build_nextcloud_groups(extra_groups, manager_username=manager_username),
        quota_mb=0,
        storage_quota_mb=storage_quota_mb,
        create_ssh_key=False,
        create_folders=False,
        send_welcome_email=send_welcome_email,
        provision_email_account=False,
        provision_local_account=False,
        service_profile="nextcloud",
    )


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extrai um JSON de uma resposta textual do LLM."""
    text = (raw_text or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _generate_nextcloud_onboarding_payload(config: UserConfig) -> dict[str, Any]:
    """Solicita ao Ollama o conteúdo base do onboarding do Nextcloud."""
    fallback = _default_nextcloud_onboarding_payload()
    prompt = f"""
Você está criando um email de onboarding da aplicação RPA4ALL Nextcloud.
Retorne apenas JSON válido com estas chaves:
- subject: string
- preheader: string
- headline: string
- intro: string
- steps: array de 4 strings curtas
- mobile_benefits: array de 3 strings curtas
- admin_note: string
- image_prompts: array com 2 prompts em português para gerar prints ilustrativos do app Android Nextcloud corporativo RPA4ALL

Contexto:
- produto: RPA4ALL Nextcloud
- login web: {NEXTCLOUD_URL}
- link Google Play: {NEXTCLOUD_ANDROID_GPLAY_URL}
- usuário: {config.username}
- nome: {config.full_name}
- grupos: {", ".join(config.groups)}

Tom:
- corporativo
- objetivo
- onboarding claro para usuário final
- mencionar Android e sincronização de arquivos
""".strip()

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": NEXTCLOUD_ONBOARDING_OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=90,
        )
        response.raise_for_status()
        payload = _extract_json_object(response.json().get("response", ""))
    except Exception as exc:
        logger.warning("Falha ao gerar onboarding via Ollama: %s", exc)
        payload = {}

    merged = dict(fallback)
    for key, value in payload.items():
        if key in {"steps", "mobile_benefits", "image_prompts"} and isinstance(value, list) and value:
            merged[key] = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str) and value.strip():
            merged[key] = value.strip()
    return merged


def _generate_nextcloud_onboarding_images(onboarding: dict[str, Any]) -> list[dict[str, Any]]:
    """Gera prints ilustrativos do app via orquestrador de mídia."""
    prompts = onboarding.get("image_prompts") or []
    if not isinstance(prompts, list):
        return []

    assets: list[dict[str, Any]] = []
    NEXTCLOUD_ONBOARDING_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    for index, prompt in enumerate(prompts[:2], start=1):
        try:
            response = requests.post(
                f"{NEXTCLOUD_ONBOARDING_MEDIA_BASE_URL}/image/generate",
                json={
                    "prompt": str(prompt),
                    "model": "stabilityai/stable-diffusion-xl-base-1.0",
                    "width": 1024,
                    "height": 1536,
                    "steps": 30,
                    "save_to_disk": True,
                },
                timeout=180,
            )
            response.raise_for_status()
            result = response.json().get("result", {})
            image_bytes = b""
            file_path = result.get("file_path")
            if file_path and Path(file_path).exists():
                image_bytes = Path(file_path).read_bytes()
            elif result.get("image_base64"):
                image_bytes = b64decode(result["image_base64"])
                file_path = NEXTCLOUD_ONBOARDING_ASSETS_DIR / f"nextcloud_onboarding_{index}.png"
                Path(file_path).write_bytes(image_bytes)
            if not image_bytes:
                continue
            assets.append(
                {
                    "cid": f"nextcloud-print-{index}",
                    "bytes": image_bytes,
                    "filename": Path(str(file_path)).name if file_path else f"nextcloud_onboarding_{index}.png",
                    "alt": f"Preview {index} do app Nextcloud RPA4ALL",
                }
            )
        except Exception as exc:
            logger.warning("Falha ao gerar print ilustrativo %s: %s", index, exc)
    return assets


def _render_nextcloud_onboarding_html(
    config: UserConfig,
    onboarding: dict[str, Any],
    image_assets: list[dict[str, Any]],
) -> str:
    """Renderiza HTML do onboarding do Nextcloud."""
    steps = "".join(
        f"<li style='margin:0 0 10px;'>{html.escape(step)}</li>"
        for step in onboarding.get("steps", [])
    )
    benefits = "".join(
        f"<li style='margin:0 0 8px;'>{html.escape(item)}</li>"
        for item in onboarding.get("mobile_benefits", [])
    )
    screenshots = "".join(
        (
            "<td style='padding:8px;' valign='top'>"
            f"<img src='cid:{html.escape(asset['cid'])}' alt='{html.escape(asset['alt'])}' "
            "style='display:block;width:100%;max-width:220px;height:auto;border-radius:18px;border:1px solid #d6e3dd;'>"
            "</td>"
        )
        for asset in image_assets
    )
    screenshots_block = (
        "<table role='presentation' width='100%' style='margin-top:18px;'><tr>"
        f"{screenshots}</tr></table>"
        if screenshots
        else ""
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<body style="margin:0;background:#f5f7f9;font-family:Arial,sans-serif;color:#173042;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f7f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="680" cellspacing="0" cellpadding="0" style="max-width:680px;background:#ffffff;border-radius:24px;overflow:hidden;">
          <tr>
            <td style="padding:32px;background:linear-gradient(135deg,#0f766e,#155e75);color:#ffffff;">
              <div style="font-size:12px;letter-spacing:.12em;text-transform:uppercase;opacity:.82;">RPA4ALL Nextcloud</div>
              <h1 style="margin:10px 0 8px;font-size:28px;line-height:1.15;">{html.escape(onboarding['headline'])}</h1>
              <p style="margin:0;font-size:15px;line-height:1.6;opacity:.96;">{html.escape(onboarding['intro'])}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 32px;">
              <p style="margin:0 0 16px;">Olá, <strong>{html.escape(config.full_name)}</strong>.</p>
              <p style="margin:0 0 18px;line-height:1.7;">
                Seu acesso já foi provisionado. Use as credenciais abaixo para entrar no ambiente web e no aplicativo Android.
              </p>
              <div style="background:#f7faf9;border:1px solid #dcebe6;border-radius:18px;padding:18px 20px;margin-bottom:20px;">
                <p style="margin:0 0 8px;"><strong>Login:</strong> {html.escape(config.username)}</p>
                <p style="margin:0 0 8px;"><strong>Senha inicial:</strong> {html.escape(config.password)}</p>
                <p style="margin:0;"><strong>Portal:</strong> <a href="{html.escape(NEXTCLOUD_URL)}">{html.escape(NEXTCLOUD_URL)}</a></p>
              </div>
              <h2 style="margin:0 0 12px;font-size:18px;">Primeiros passos</h2>
              <ol style="margin:0 0 20px;padding-left:20px;line-height:1.7;">{steps}</ol>
              <h2 style="margin:0 0 12px;font-size:18px;">Aplicativo Android</h2>
              <p style="margin:0 0 10px;line-height:1.7;">
                Instale pela Google Play: <a href="{html.escape(NEXTCLOUD_ANDROID_GPLAY_URL)}">{html.escape(NEXTCLOUD_ANDROID_GPLAY_URL)}</a>
              </p>
              <ul style="margin:0;padding-left:20px;line-height:1.7;">{benefits}</ul>
              {screenshots_block}
              <div style="margin-top:22px;padding:16px 18px;background:#fff7ed;border:1px solid #fed7aa;border-radius:16px;">
                <strong>Observação:</strong> {html.escape(onboarding['admin_note'])}
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _render_nextcloud_onboarding_text(config: UserConfig, onboarding: dict[str, Any]) -> str:
    """Renderiza versão texto do onboarding."""
    steps = "\n".join(f"- {step}" for step in onboarding.get("steps", []))
    benefits = "\n".join(f"- {item}" for item in onboarding.get("mobile_benefits", []))
    return (
        f"{onboarding['headline']}\n\n"
        f"{onboarding['intro']}\n\n"
        f"Login: {config.username}\n"
        f"Senha inicial: {config.password}\n"
        f"Portal: {NEXTCLOUD_URL}\n"
        f"Google Play: {NEXTCLOUD_ANDROID_GPLAY_URL}\n\n"
        f"Primeiros passos:\n{steps}\n\n"
        f"Benefícios no Android:\n{benefits}\n\n"
        f"{onboarding['admin_note']}\n"
    )


def _send_nextcloud_onboarding_email(config: UserConfig) -> dict[str, Any]:
    """Envia email de onboarding com conteúdo criado via Ollama e prints ilustrativos."""
    if not SMTP_PASSWORD:
        raise RuntimeError("SMTP_PASSWORD não configurado para envio do onboarding Nextcloud.")

    onboarding = _generate_nextcloud_onboarding_payload(config)
    image_assets = _generate_nextcloud_onboarding_images(onboarding)
    html_body = _render_nextcloud_onboarding_html(config, onboarding, image_assets)
    text_body = _render_nextcloud_onboarding_text(config, onboarding)

    message = MIMEMultipart("related")
    message["Subject"] = onboarding["subject"]
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = config.email

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(text_body, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(alternative)

    for asset in image_assets:
        image_part = MIMEImage(asset["bytes"], _subtype="png")
        image_part.add_header("Content-ID", f"<{asset['cid']}>")
        image_part.add_header("Content-Disposition", "inline", filename=asset["filename"])
        message.attach(image_part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        if SMTP_STARTTLS:
            smtp.starttls()
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)

    return {
        "success": True,
        "recipient": config.email,
        "images_generated": len(image_assets),
        "google_play_url": NEXTCLOUD_ANDROID_GPLAY_URL,
        "subject": onboarding["subject"],
    }


# ── Conexão DB ─────────────────────────────────────────────────────────────
def _get_conn() -> Any:
    """Obtém conexão PostgreSQL com autocommit."""
    if psycopg2 is None:
        raise RuntimeError("psycopg2 não disponível no runtime")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _ensure_table() -> None:
    """Cria tabela de tracking se não existir."""
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        conn.close()
    except Exception as exc:
        logger.warning(f"Não foi possível criar tabela: {exc}")


_ensure_table()


# ── Authentik API ──────────────────────────────────────────────────────────
def _authentik_api(
    method: str,
    endpoint: str,
    data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Faz requisição à API do Authentik."""
    url = f"{AUTHENTIK_URL}/api/v3{endpoint}"
    try:
        resp = requests.request(
            method,
            url,
            json=data,
            headers=_HEADERS,
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json() if resp.text else {}
    except requests.RequestException as exc:
        logger.error(f"Authentik API error: {exc}")
        return {"error": str(exc)}


# ── Funções de pipeline ───────────────────────────────────────────────────
def _step_create_authentik(config: UserConfig) -> dict[str, Any]:
    """Cria usuário no Authentik."""
    payload = {
        "username": config.username,
        "email": config.email,
        "name": config.full_name,
        "is_active": True,
        "password": config.password,
    }
    result = _authentik_api("POST", "/core/users/", payload)

    if "error" in result:
        return {"success": False, "error": result["error"]}

    # Adicionar a grupos
    user_pk = result.get("pk")
    if user_pk and config.groups:
        for group_name in config.groups:
            groups_resp = _authentik_api(
                "GET", f"/core/groups/?search={group_name}"
            )
            group_results = groups_resp.get("results", [])
            if group_results:
                group_pk = group_results[0]["pk"]
                user_detail = _authentik_api("GET", f"/core/users/{user_pk}/")
                current_groups = user_detail.get("groups", [])
                if group_pk not in current_groups:
                    current_groups.append(group_pk)
                    _authentik_api(
                        "PATCH",
                        f"/core/users/{user_pk}/",
                        {"groups": current_groups},
                    )

    return {"success": True, "authentik_id": user_pk}


def _step_create_email(config: UserConfig) -> dict[str, Any]:
    """Registra email no pipeline (placeholder — Dovecot/Postfix)."""
    if not config.provision_email_account:
        logger.info("Provisionamento de email desabilitado para %s", config.username)
        return {"success": True, "skipped": True}

    # TODO: Integrar com Dovecot/Postfix quando email server estiver pronto
    logger.info(f"Email step placeholder para {config.email}")
    return {"success": True, "email": config.email}


def _step_send_welcome_email(config: UserConfig) -> dict[str, Any]:
    """Envia onboarding do serviço quando solicitado."""
    if not config.send_welcome_email:
        logger.info("Onboarding por email desabilitado para %s", config.username)
        return {"success": True, "skipped": True}

    try:
        result = _send_nextcloud_onboarding_email(config)
        logger.info("Onboarding Nextcloud enviado para %s", config.email)
        return result
    except Exception as exc:
        logger.error("Falha ao enviar onboarding para %s: %s", config.email, exc)
        return {"success": False, "error": str(exc)}


def _step_setup_env(config: UserConfig) -> dict[str, Any]:
    """Provisiona conta local do SO para usuarios gerenciados no Authentik."""
    if not config.provision_local_account:
        logger.info("Provisionamento local desabilitado para %s", config.username)
        return {"success": True, "skipped": True}

    if not CREATE_OS_USERS:
        logger.info("Criação de conta local desabilitada para %s", config.username)
        return {"success": True, "skipped": True}

    try:
        result = ensure_local_account(
            config.username,
            config.full_name,
            shell=LOCAL_USER_SHELL,
            local_groups=LOCAL_USER_GROUPS,
        )
        logger.info("Conta local preparada para %s (created=%s)", config.username, result["created"])
        return {"success": True, **result}
    except Exception as exc:
        logger.error("Falha ao preparar conta local para %s: %s", config.username, exc)
        return {"success": False, "error": str(exc)}


# ── Pipeline principal ────────────────────────────────────────────────────
async def pipeline(config: UserConfig) -> dict[str, Any]:
    """Executa o pipeline completo de criação de usuário."""
    steps: dict[str, str] = {}
    authentik_id: Optional[int] = None

    try:
        # 1. Authentik
        result = _step_create_authentik(config)
        if not result["success"]:
            steps["authentik"] = "✗"
            _save_user(config, UserStatus.FAILED, steps, error=result["error"])
            return {"success": False, "error": result["error"], "steps": steps}
        steps["authentik"] = "✓"
        authentik_id = result.get("authentik_id")
        _save_user(config, UserStatus.AUTHENTIK_CREATED, steps, authentik_id=authentik_id)

        # 2. Email
        result = _step_create_email(config)
        if not result["success"]:
            steps["email"] = "✗"
            _save_user(config, UserStatus.FAILED, steps, authentik_id=authentik_id, error=result.get("error"))
            return {"success": False, "error": result.get("error", "Email step failed"), "steps": steps}
        steps["email"] = "✓"
        _save_user(config, UserStatus.EMAIL_CREATED, steps, authentik_id=authentik_id)

        # 3. Environment
        result = _step_setup_env(config)
        if not result["success"]:
            steps["environment"] = "✗"
            _save_user(config, UserStatus.FAILED, steps, authentik_id=authentik_id, error=result.get("error"))
            return {"success": False, "error": result.get("error", "Env step failed"), "steps": steps}
        steps["environment"] = "✓"

        # 4. Welcome email
        result = _step_send_welcome_email(config)
        if not result["success"]:
            steps["welcome_email"] = "✗"
            _save_user(config, UserStatus.FAILED, steps, authentik_id=authentik_id, error=result.get("error"))
            return {"success": False, "error": result.get("error", "Welcome email failed"), "steps": steps}
        if not result.get("skipped"):
            steps["welcome_email"] = "✓"

        # 5. Completo
        _save_user(config, UserStatus.COMPLETE, steps, authentik_id=authentik_id)
        return {"success": True, "steps": steps}

    except Exception as exc:
        logger.exception("Pipeline error")
        return {"success": False, "error": str(exc), "steps": steps}


async def create_user(config: UserConfig) -> dict[str, Any]:
    """Cria usuário pelo pipeline completo."""
    return await pipeline(config)


async def create_nextcloud_user(
    *,
    username: str,
    email: str,
    full_name: str,
    password: str,
    extra_groups: Optional[list[str]] = None,
    manager_username: Optional[str] = None,
    storage_quota_mb: int = 100000,
    send_welcome_email: bool = True,
) -> dict[str, Any]:
    """Cria um usuario pronto para acesso ao Nextcloud via Authentik OIDC."""
    config = build_nextcloud_user_config(
        username=username,
        email=email,
        full_name=full_name,
        password=password,
        extra_groups=extra_groups,
        manager_username=manager_username,
        storage_quota_mb=storage_quota_mb,
        send_welcome_email=send_welcome_email,
    )
    result = await pipeline(config)
    result["nextcloud"] = {
        "login_url": NEXTCLOUD_URL,
        "android_google_play_url": NEXTCLOUD_ANDROID_GPLAY_URL,
        "groups": config.groups,
        "service_profile": config.service_profile,
        "provisioning_mode": "authentik_oidc_auto_provision",
        "welcome_email_enabled": config.send_welcome_email,
    }
    return result


async def delete_user(username: str) -> dict[str, Any]:
    """Remove usuário do Authentik e do tracking."""
    try:
        # Buscar no Authentik
        users_resp = _authentik_api("GET", f"/core/users/?search={username}")
        results = users_resp.get("results", [])
        target = next((u for u in results if u["username"] == username), None)

        if target:
            _authentik_api("DELETE", f"/core/users/{target['pk']}/")

        # Remover do tracking
        try:
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_management WHERE username = %s",
                    (username,),
                )
            conn.close()
        except Exception as db_err:
            logger.warning(f"DB delete warning: {db_err}")

        return {"success": True}
    except Exception as exc:
        logger.error(f"Delete user error: {exc}")
        return {"success": False, "error": str(exc)}


# ── Funções de consulta ───────────────────────────────────────────────────
def list_users() -> list[dict[str, Any]]:
    """Lista todos os usuários do tracking DB + Authentik."""
    users: list[dict[str, Any]] = []

    # Tentar buscar do DB primeiro
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, email, full_name, status, authentik_id, "
                "groups, quota_mb, created_at, updated_at "
                "FROM user_management ORDER BY created_at DESC"
            )
            for row in cur.fetchall():
                users.append({
                    "username": row[0],
                    "email": row[1],
                    "full_name": row[2],
                    "status": row[3],
                    "authentik_id": row[4],
                    "groups": row[5] or [],
                    "quota_mb": row[6],
                    "created_at": row[7],
                    "updated_at": row[8],
                })
        conn.close()
        if users:
            return users
    except Exception as exc:
        logger.warning(f"DB list fallback: {exc}")

    # Fallback: Authentik API
    try:
        resp = _authentik_api("GET", "/core/users/?format=json")
        for u in resp.get("results", []):
            # Ignorar service accounts
            if u.get("username", "").startswith("ak-"):
                continue
            users.append({
                "username": u["username"],
                "email": u.get("email", ""),
                "full_name": u.get("name", ""),
                "status": UserStatus.COMPLETE.value,
                "authentik_id": u.get("pk"),
                "groups": [g.get("name", "") for g in u.get("groups_obj", [])],
                "quota_mb": 5000,
                "created_at": u.get("date_joined", datetime.now().isoformat()),
                "updated_at": u.get("last_login") or u.get("date_joined", datetime.now().isoformat()),
            })
    except Exception as exc:
        logger.error(f"Authentik list error: {exc}")

    return users


def get_user(username: str) -> Optional[dict[str, Any]]:
    """Busca usuário pelo username."""
    # Tentar DB
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, email, full_name, status, authentik_id, "
                "groups, quota_mb, created_at, updated_at "
                "FROM user_management WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
            if row:
                conn.close()
                return {
                    "username": row[0],
                    "email": row[1],
                    "full_name": row[2],
                    "status": row[3],
                    "authentik_id": row[4],
                    "groups": row[5] or [],
                    "quota_mb": row[6],
                    "created_at": row[7],
                    "updated_at": row[8],
                }
        conn.close()
    except Exception as exc:
        logger.warning(f"DB get fallback: {exc}")

    # Fallback: Authentik
    try:
        resp = _authentik_api("GET", f"/core/users/?search={username}")
        for u in resp.get("results", []):
            if u["username"] == username:
                return {
                    "username": u["username"],
                    "email": u.get("email", ""),
                    "full_name": u.get("name", ""),
                    "status": UserStatus.COMPLETE.value,
                    "authentik_id": u.get("pk"),
                    "groups": [g.get("name", "") for g in u.get("groups_obj", [])],
                    "quota_mb": 5000,
                    "created_at": u.get("date_joined", datetime.now().isoformat()),
                    "updated_at": u.get("last_login") or u.get("date_joined", datetime.now().isoformat()),
                }
    except Exception as exc:
        logger.error(f"Authentik get error: {exc}")

    return None


# ── DB helper ──────────────────────────────────────────────────────────────
def _save_user(
    config: UserConfig,
    status: UserStatus,
    steps: dict[str, str],
    *,
    authentik_id: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """Salva ou atualiza usuário no tracking DB."""
    import json

    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_management
                    (username, email, full_name, status, authentik_id,
                     groups, quota_mb, storage_quota_mb, pipeline_steps, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (username) DO UPDATE SET
                    status = EXCLUDED.status,
                    authentik_id = COALESCE(EXCLUDED.authentik_id, user_management.authentik_id),
                    pipeline_steps = EXCLUDED.pipeline_steps,
                    error_message = EXCLUDED.error_message,
                    updated_at = NOW()
                """,
                (
                    config.username,
                    config.email,
                    config.full_name,
                    status.value,
                    authentik_id,
                    config.groups,
                    config.quota_mb,
                    config.storage_quota_mb,
                    json.dumps(steps),
                    error,
                ),
            )
        conn.close()
    except Exception as exc:
        logger.warning(f"Erro ao salvar tracking: {exc}")
