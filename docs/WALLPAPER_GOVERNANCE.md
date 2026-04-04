# Governanca de Wallpapers RPA4ALL

Fonte unica e empresarial:
- Registro canonico: `site/wallpapers/registry.json`
- URL de gestao prevista: `https://auth.rpa4all.com/wallpapers/`
- Ativos aprovados: `assets/wallpapers/`

Regra operacional:
- Nenhum wallpaper entra em uso sem `request_id` registrado no registry.
- O registry eh a referencia para aprovacao, auditoria e uso no SO.
- Briefs corporativos ao Ollama usam GPU0 (`http://192.168.15.2:11434`) com `phi4-mini:latest`.
- GPU1 (`http://192.168.15.2:11435`) fica para pedidos pequenos ou fallback controlado.

Fluxo padrao:
1. Registrar a demanda no registry:
   `/workspace/eddie-auto-dev/.venv/bin/python scripts/generation/wallpaper_governance.py request --title "Wallpaper Auth Portal" --business-goal "Fundo institucional para portal SSO" --audience "Usuarios internos" --style-direction "Corporativo, IA aplicada, azul/ciano"`
2. Enviar o prompt salvo no arquivo gerado em `site/wallpapers/requests/` ao Ollama.
3. Gerar o ativo final em `assets/wallpapers/`.
4. Registrar o ativo aprovado:
   `/workspace/eddie-auto-dev/.venv/bin/python scripts/generation/wallpaper_governance.py register-asset --file assets/wallpapers/arquivo.svg --title "Wallpaper Auth Portal" --request-id <request_id>`
5. Somente depois aplicar o ativo no SO ou em publicacao web.

Publicacao em `auth.rpa4all.com`:
- Publicar `site/wallpapers/` como rota estatica protegida no portal.
- A pagina `site/wallpapers/index.html` foi preparada para ser servida em `/wallpapers/` e ler o proprio `registry.json`.
- Isso centraliza catalogo, regras, requests pendentes e contrato de prompt em um unico ponto de consulta.
- Para gerar um bundle pronto para deploy: `/workspace/eddie-auto-dev/.venv/bin/python scripts/generation/wallpaper_governance.py export-site --output-dir /workspace/eddie-auto-dev/artifacts/wallpapers-site`
- O bundle exportado inclui `index.html`, `registry.json`, `requests/*.json` e os ativos aprovados em `assets/` com caminhos ajustados para publicacao.
- Template Nginx versionado: `site/deploy/auth-wallpapers-location.nginx.conf` para incluir dentro do `server_name auth.rpa4all.com`.

Estado atual:
- Dois ativos aprovados ja constam no registry.
- O slideshow do SO pode usar os ativos locais, mas a governanca passa a vir do registry central.