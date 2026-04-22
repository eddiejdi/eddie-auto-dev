# Incidente iVentoy PXE — estado `noimg` (2026-04-22)

Resumo
-----
- Data: 2026-04-22
- Impacto: clientes PXE não listavam imagens para boot (menu vazio). TFTP/DHCP loader era transferido, mas não havia imagens válidas para fase 2.

Diagnóstico (causa raiz)
------------------------
- iVentoy inicializou em estado `noimg` porque o diretório de imagens estava vazio: `/opt/iventoy/iso` apontava para `/mnt/raid1/isos` sem ISOs válidas.
- Regras de firewall (mangle/drop) estavam bloqueando tráfego DHCP/TFTP em momentos anteriores, o que agravou a situação durante a investigação.

Timeline resumida
------------------
1. iVentoy subiu com `No image file detected` e menu vazio.
2. Testes mostraram que o loader (`iventoy_loader_16000.0`) era servido via TFTP com sucesso, porém não havia imagem para carregar (fase2).
3. Colocamos ISOs temporárias/placeholder para validar transferência de loader e reativar serviços.
4. Removemos placeholders (para não poluir o repositório) e recriamos um symlink `real_boot.iso` apontando para o underlay (não copiamos arquivo para evitar uso de espaço).
5. iVentoy parseou `iso/real_boot.iso` com sucesso: `Phase2 parse image <iso/real_boot.iso> finished success` — menu atualizado.

Ações executadas
-----------------
- Verificação dos paths: `/opt/iventoy` e `/opt/iventoy/iso` (aponta para `/mnt/raid1/isos`).
- Remoção de arquivos placeholder (`placeholder-netboot.iso`) e remoção temporária do symlink quebrado `real_boot.iso`.
- Recriação segura do symlink `real_boot.iso` apontando para o local fonte (underlay) — sem copiar a ISO para `/mnt/raid1/isos`.
- Reinício de `iventoy` (systemd) e validação via logs `/opt/iventoy/log/log.txt`.
- Validação: TFTP e DHCP serviços ativos; `IMG TREE DUMP` mostrou `real_boot.iso` listado.

Estado atual
-------------
- `iventoy.service`: ativo (iVentoy 1.0.25)
- `/opt/iventoy/iso` → `/mnt/raid1/isos` contém apenas um symlink `real_boot.iso` apontando para o underlay (sem cópia local).
- Logs confirmam parse/phase2 success e menu atualizado.

Arquivos de referência
----------------------
- Logs iVentoy: `/opt/iventoy/log/log.txt`
- Log de remoção/criação de symlink: `/home/homelab/iventoy_removed_iso_log.txt`
- Config dnsmasq relevante: `/etc/dnsmasq.d/homelab-lan.conf`

Lições aprendidas e recomendações
---------------------------------
- Sempre verificar conteúdo de `/opt/iventoy/iso` (ou o target do symlink) como primeiro passo ao investigar menu vazio.
- Monitorar/alertar: (1) número de arquivos em `/opt/iventoy/iso`, (2) porta UDP 69 escutando, (3) entradas `Phase2 parse image ... finished success` nos logs.
- Evitar usar apenas symlinks para underlays não garantidos em produção — preferir ter cópias locais para ISOs essenciais ou um procedimento automatizado que garanta availability.
- Aplicar regras de firewall com exceções explícitas para UDP 67/68/69/4011 e validar ordem das regras (mangle antes de drop pode afetar DHCP/TFTP).
- Automatizar um check simples no boot do `iventoy` que avise via Telegram/Grafana se `No image file detected` for encontrado.

Próximos passos sugeridos
------------------------
1. Adicionar um healthcheck (script ou exporter) para `iventoy` que verifique presença mínima de ISOs e porta 69.
2. Considerar manter um pequeno conjunto de ISOs locais para recuperação rápida (policy definida por espaço disponível).
3. Atualizar página de operação (`/docs/OPERATIONAL_STATUS_2026-04-13.md`) com referência a este incidente.

Autor e auditoria
-----------------
- Autor: Automação (executado via Copilot) — ações validadas por logs em host `homelab`.
- Data da atualização: 2026-04-22
