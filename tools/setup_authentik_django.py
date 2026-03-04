#!/usr/bin/env python3
"""Configura providers OAuth2 e applications no Authentik via Django ORM."""
from __future__ import annotations

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.core.models import Application
from authentik.flows.models import Flow
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

# Buscar flow de autorização
auth_flow = Flow.objects.filter(designation="authorization").first()
if not auth_flow:
    print("ERRO: Nenhum flow de autorização encontrado!")
    raise SystemExit(1)
print(f"Flow de autorização: {auth_flow.slug} (pk={auth_flow.pk})")

# Buscar scope mappings
scope_mappings = list(ScopeMapping.objects.all())
print(f"Scope mappings: {len(scope_mappings)} encontrados")
for sm in scope_mappings:
    print(f"  - {sm.scope_name}: {sm.name}")

# Configuração dos serviços
SERVICES = [
    {
        "provider_name": "Nextcloud Provider",
        "client_id": "authentik-nextcloud",
        "client_secret": "nextcloud-sso-secret-2026",
        "redirect_uris": "https://nextcloud.rpa4all.com/apps/oidc_login/oidc\nhttps://nextcloud.rpa4all.com/apps/user_oidc/code",
        "app_name": "Nextcloud",
        "app_slug": "nextcloud",
        "launch_url": "https://nextcloud.rpa4all.com",
    },
    {
        "provider_name": "Grafana Provider",
        "client_id": "authentik-grafana",
        "client_secret": "grafana-sso-secret-2026",
        "redirect_uris": "https://grafana.rpa4all.com/login/generic_oauth",
        "app_name": "Grafana",
        "app_slug": "grafana",
        "launch_url": "https://grafana.rpa4all.com",
    },
    {
        "provider_name": "OpenWebUI Provider",
        "client_id": "authentik-openwebui",
        "client_secret": "openwebui-sso-secret-2026",
        "redirect_uris": "https://openwebui.rpa4all.com/oauth/oidc/callback",
        "app_name": "OpenWebUI",
        "app_slug": "openwebui",
        "launch_url": "https://openwebui.rpa4all.com",
    },
]

for svc in SERVICES:
    print(f"\n--- {svc['app_name']} ---")

    # Criar ou obter provider
    provider, created = OAuth2Provider.objects.get_or_create(
        name=svc["provider_name"],
        defaults={
            "authorization_flow": auth_flow,
            "client_type": "confidential",
            "client_id": svc["client_id"],
            "client_secret": svc["client_secret"],
            "redirect_uris": svc["redirect_uris"],
            "sub_mode": "hashed_user_id",
            "include_claims_in_id_token": True,
            "issuer_mode": "per_provider",
        },
    )
    if created:
        provider.property_mappings.set(scope_mappings)
        provider.save()
        print(f"  Provider CRIADO: pk={provider.pk}, client_id={provider.client_id}")
    else:
        print(f"  Provider já existe: pk={provider.pk}, client_id={provider.client_id}")

    # Criar ou obter application
    app, app_created = Application.objects.get_or_create(
        slug=svc["app_slug"],
        defaults={
            "name": svc["app_name"],
            "provider": provider,
            "meta_launch_url": svc["launch_url"],
            "policy_engine_mode": "any",
        },
    )
    if app_created:
        print(f"  Application CRIADA: {app.slug}")
    else:
        if app.provider != provider:
            app.provider = provider
            app.save()
            print(f"  Application ATUALIZADA com provider: {app.slug}")
        else:
            print(f"  Application já existe: {app.slug}")

print("\n=== RESUMO OIDC ===")
for svc in SERVICES:
    slug = svc["app_slug"]
    print(f"\n{svc['app_name']}:")
    print(f"  Client ID:     {svc['client_id']}")
    print(f"  Client Secret: {svc['client_secret']}")
    print(f"  Issuer:        https://auth.rpa4all.com/application/o/{slug}/")
    print(f"  Authorize URL: https://auth.rpa4all.com/application/o/authorize/")
    print(f"  Token URL:     https://auth.rpa4all.com/application/o/token/")
    print(f"  UserInfo URL:  https://auth.rpa4all.com/application/o/userinfo/")
    print(f"  JWKS URL:      https://auth.rpa4all.com/application/o/{slug}/jwks/")

print("\n=== SETUP COMPLETO ===")
