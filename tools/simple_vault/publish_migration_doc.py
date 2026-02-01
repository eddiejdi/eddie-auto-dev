#!/usr/bin/env python3
"""Generate Confluence documentation for the Vault -> Simple Vault migration.

Creates a Confluence-format HTML page via the existing `ConfluenceAgent` and
saves it under `specialized_agents/confluence_docs/` and also ensures the
draw.io diagram is present in `diagrams/` (already added).

Usage: python3 tools/simple_vault/publish_migration_doc.py
"""

from pathlib import Path
from datetime import datetime

title = "Migração: Vaultwarden → Simple GPG Vault"


def heading(level, text):
    return f"<h{level}>{text}</h{level}>"


def paragraph(text):
    return f"<p>{text}</p>"


def link(url, text):
    return f'<a href="{url}">{text}</a>'


def bullet_list(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def numbered_list(items):
    return "<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


content_parts = []
content_parts.append(heading(1, title))
content_parts.append(paragraph("Resumo da migração realizada em 2026-01-21."))
content_parts.append(heading(2, "Objetivo"))
content_parts.append(
    paragraph(
        "Substituir o Vaultwarden auto-hospedado por um mecanismo simples e auditable baseado em GPG/SOPS para armazenar chaves de operação críticas."
    )
)

content_parts.append(heading(2, "Ações executadas"))
content_parts.append(
    bullet_list(
        [
            "Identificado e exportado API key do Open WebUI",
            "Rotacionado token admin do Vaultwarden (quando aplicável)",
            "Criado `tools/simple_vault/` com scripts de encrypt/decrypt",
            "Migrado `openwebui/api_key` para `tools/simple_vault/secrets/openwebui_api_key.gpg`",
            "Atualizado `tools/vault/secret_store.py` com fallback para arquivos GPG locais",
        ]
    )
)

content_parts.append(heading(2, "Diagrama da migração"))
content_parts.append(
    paragraph(
        "Diagrama disponível em: "
        + link(
            "../diagrams/migration_vault_to_simple_vault.drawio",
            "migration_vault_to_simple_vault.drawio",
        )
    )
)

content_parts.append(heading(2, "Passos Operacionais para Recuperação"))
content_parts.append(
    numbered_list(
        [
            "Verificar presença de tools/simple_vault/secrets/openwebui_api_key.gpg",
            "Confirmar path da passphrase em SIMPLE_VAULT_PASSPHRASE_FILE",
            "Testar leitura via: python3 tools/vault/secret_store.py get openwebui/api_key password",
            "Atualizar systemd units com EnvironmentFile apontando para passphrase (opcional)",
        ]
    )
)

content = "\n".join(content_parts)

# Save HTML page into specialized_agents/confluence_docs
out_dir = Path(__file__).parent.parent / "specialized_agents" / "confluence_docs"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / (title.replace(" ", "_") + ".html")

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width:900px; margin:40px auto; }}</style>
</head>
<body>
{content}
<hr/>
<p style="color:#6B778C;font-size:12px;">Gerado automaticamente em {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
</body>
</html>"""

with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Generated Confluence-style HTML saved to:", out_path)
print("Draw.io diagram located at: diagrams/migration_vault_to_simple_vault.drawio")
