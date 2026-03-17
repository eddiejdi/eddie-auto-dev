#!/usr/bin/env python3
"""
Configuração de domínio no Google Workspace via Admin SDK.

Verifica ownership, status de verificação e tenta gerar DKIM
para o domínio rpa4all.com usando OAuth2 com escopos de Admin.
"""

import json
import sys
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Configurações ──────────────────────────────────────────────
DOMAIN = "rpa4all.com"
CUSTOMER_ID = "my_customer"

CREDENTIALS_FILE = Path(__file__).parent.parent.parent / "gmail_data" / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "gmail_data" / "admin_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.domain",
    "https://www.googleapis.com/auth/admin.directory.domain.readonly",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.settings.sharing",
]


def authenticate() -> Credentials:
    """Autentica via OAuth2 com escopos de Admin SDK."""
    creds: Credentials | None = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"✗ Arquivo de credenciais não encontrado: {CREDENTIALS_FILE}")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE),
                scopes=SCOPES,
            )
            creds = flow.run_local_server(port=8085, open_browser=True)

        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
        print(f"✓ Token salvo em {TOKEN_FILE}")

    return creds


def list_domains(service: Any) -> list[dict]:
    """Lista domínios do Google Workspace."""
    try:
        result = service.domains().list(customer=CUSTOMER_ID).execute()
        domains = result.get("domains", [])
        print(f"\n{'='*60}")
        print(f"Domínios no Google Workspace ({len(domains)} encontrados):")
        print(f"{'='*60}")
        for d in domains:
            status = "✓ Verificado" if d.get("verified") else "✗ Não verificado"
            primary = " (PRIMÁRIO)" if d.get("isPrimary") else ""
            print(f"  {d['domainName']}: {status}{primary}")
        return domains
    except HttpError as e:
        if e.resp.status == 403:
            print("✗ Admin SDK API não habilitada ou sem permissão.")
            print("  → Habilite em: https://console.cloud.google.com/apis/library/admin.googleapis.com")
            print(f"  → Projeto: homelab-483803")
        else:
            print(f"✗ Erro ao listar domínios: {e}")
        return []


def get_domain_info(service: Any) -> dict | None:
    """Obtém informações detalhadas do domínio."""
    try:
        domain = service.domains().get(
            customer=CUSTOMER_ID,
            domainName=DOMAIN,
        ).execute()
        print(f"\n{'='*60}")
        print(f"Detalhes do domínio: {DOMAIN}")
        print(f"{'='*60}")
        print(json.dumps(domain, indent=2))
        return domain
    except HttpError as e:
        if e.resp.status == 404:
            print(f"✗ Domínio {DOMAIN} não encontrado no Google Workspace.")
            print(f"  → Adicione em: https://admin.google.com/ac/domains")
        else:
            print(f"✗ Erro ao buscar domínio: {e}")
        return None


def add_domain(service: Any) -> dict | None:
    """Adiciona domínio ao Google Workspace se não existir."""
    try:
        body = {"domainName": DOMAIN}
        result = service.domains().insert(
            customer=CUSTOMER_ID,
            body=body,
        ).execute()
        print(f"✓ Domínio {DOMAIN} adicionado ao Google Workspace")
        print(json.dumps(result, indent=2))
        return result
    except HttpError as e:
        print(f"✗ Erro ao adicionar domínio: {e}")
        return None


def check_gmail_dkim(creds: Credentials) -> None:
    """Tenta verificar/configurar DKIM via Gmail API."""
    try:
        gmail = build("gmail", "v1", credentials=creds)

        # Listar configurações de envio do usuário admin
        result = gmail.users().settings().sendAs().list(userId="me").execute()
        send_as = result.get("sendAs", [])

        print(f"\n{'='*60}")
        print("Configurações de envio (send-as):")
        print(f"{'='*60}")
        for sa in send_as:
            verified = sa.get("verificationStatus", "unknown")
            is_primary = " (PRIMÁRIO)" if sa.get("isPrimary") else ""
            print(f"  {sa['sendAsEmail']}: status={verified}{is_primary}")

        # Verificar se rpa4all.com está nos send-as
        domain_aliases = [sa for sa in send_as if sa["sendAsEmail"].endswith(f"@{DOMAIN}")]
        if domain_aliases:
            print(f"\n✓ Endereços @{DOMAIN} configurados via Gmail")
        else:
            print(f"\n✗ Nenhum endereço @{DOMAIN} encontrado nos send-as")

    except HttpError as e:
        if e.resp.status == 403:
            print("✗ Sem permissão para acessar Gmail settings.")
            print("  → Os escopos gmail.settings podem precisar de aprovação adicional")
        else:
            print(f"✗ Erro ao verificar Gmail settings: {e}")


def print_dns_records() -> None:
    """Exibe os registros DNS necessários para Gmail."""
    print(f"\n{'='*60}")
    print("DNS Records necessários para Gmail (adicionar no Cloudflare):")
    print(f"{'='*60}")

    mx_records = [
        ("MX", "@", "aspmx.l.google.com", 1),
        ("MX", "@", "alt1.aspmx.l.google.com", 5),
        ("MX", "@", "alt2.aspmx.l.google.com", 5),
        ("MX", "@", "alt3.aspmx.l.google.com", 10),
        ("MX", "@", "alt4.aspmx.l.google.com", 10),
    ]

    print("\n📧 MX Records:")
    for tipo, nome, valor, pri in mx_records:
        print(f"  {tipo:4s} {nome:20s} → {valor:35s} (prioridade {pri})")

    print("\n📝 TXT Records:")
    print(f"  TXT  {'@':20s} → v=spf1 include:_spf.google.com ~all")
    print(f"  TXT  {'_dmarc':20s} → v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@{DOMAIN}; pct=100")

    print("\n🔑 DKIM Record (após gerar no Admin Console):")
    print(f"  TXT  {'google._domainkey':20s} → (valor gerado pelo Google Admin)")
    print(f"  → Gerar em: https://admin.google.com/ac/apps/gmail/authenticateemail")


def main() -> None:
    """Fluxo principal de configuração."""
    print(f"🔧 Configuração Google Workspace para {DOMAIN}")
    print(f"   Credenciais: {CREDENTIALS_FILE}")
    print(f"   Token: {TOKEN_FILE}")

    # 1. Autenticar
    print("\n[1/4] Autenticando via OAuth2...")
    creds = authenticate()
    print("✓ Autenticado com sucesso")

    # 2. Admin SDK - Listar domínios
    print("\n[2/4] Verificando domínios no Google Workspace...")
    try:
        admin_service = build("admin", "directory_v1", credentials=creds)
        domains = list_domains(admin_service)

        # Se domínio não está listado, tentar adicionar
        domain_names = [d["domainName"] for d in domains]
        if DOMAIN not in domain_names and domains:
            print(f"\n⚠ Domínio {DOMAIN} não encontrado. Tentando adicionar...")
            add_domain(admin_service)

        # Buscar info detalhada
        if domains:
            get_domain_info(admin_service)
    except Exception as e:
        print(f"⚠ Admin SDK indisponível: {e}")
        print("  Continuando com Gmail API...")

    # 3. Gmail API - Verificar settings
    print("\n[3/4] Verificando configurações do Gmail...")
    check_gmail_dkim(creds)

    # 4. Exibir DNS records necessários
    print("\n[4/4] DNS Records necessários...")
    print_dns_records()

    print(f"\n{'='*60}")
    print("PRÓXIMOS PASSOS:")
    print(f"{'='*60}")
    print("1. Adicione os registros DNS acima no Cloudflare")
    print("2. Remova os MX records antigos do Cloudflare Email Routing")
    print("3. Desabilite Email Routing: Cloudflare → rpa4all.com → Email → Disable")
    print(f"4. Gere DKIM: https://admin.google.com/ac/apps/gmail/authenticateemail")
    print("5. Adicione o TXT record google._domainkey no Cloudflare")
    print("6. Aguarde propagação DNS (até 48h, geralmente <1h)")


if __name__ == "__main__":
    main()
