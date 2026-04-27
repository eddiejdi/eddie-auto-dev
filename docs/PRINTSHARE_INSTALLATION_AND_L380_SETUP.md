# PrintShare — Instalação e configuração (Phomemo Q30 & Epson L380)

Data: 24 de abril de 2026
Autor: Shared Auto-Dev / Assistente

## Resumo
Documentação passo-a-passo do processo realizado para instalar o serviço "PrintShare" no homelab (`192.168.15.2`) e integrar a impressora Epson L380 via CUPS. Inclui arquivos criados, comandos executados, verificações e como reproduzir/rollback.

---

## Ambiente
- Servidor homelab: `homelab@192.168.15.2`
- Open WebUI: container `open-webui` (porta 3000 interno -> 3000 host)
- CUPS host/endpoint da L380: `192.168.15.251:631` (printer L380 configurada)
- Diretório usado no host: `/home/homelab/printshare` e `/home/homelab/agents_workspace`

---

## Arquivos adicionados/modificados no repositório
- `deploy/printshare/Dockerfile` — imagem do serviço PrintShare (instala `cups-bsd` + dependências Python).
- `deploy/printshare/requirements.txt` — dependências Python.
- `deploy/printshare/app.py` — API Flask que expõe `/health`, `/status` e `/print` e faz fallback para CUPS ou driver Phomemo.
- `deploy/printshare/docker-compose.yml` — composição (opcional).
- `deploy/printshare/README.md` — instruções rápidas.
- Scripts relevantes já existentes copiados para o host: `scripts/misc/phomemo_print.py`, `scripts/misc/openwebui_printer_function.py`, `scripts/misc/install_printer_function.py` (copiados para `/home/homelab/agents_workspace`).

Links locais:
- Doc criada: [docs/PRINTSHARE_INSTALLATION_AND_L380_SETUP.md](docs/PRINTSHARE_INSTALLATION_AND_L380_SETUP.md)
- Service files: [deploy/printshare/README.md](deploy/printshare/README.md)

---

## Passos executados (resumo cronológico)
1. Copiei os artefatos para o servidor homelab:

```bash
scp -r deploy/printshare/* homelab@192.168.15.2:/home/homelab/printshare/
scp scripts/misc/openwebui_printer_function.py phomemo_print.py install_printer_function.py homelab@192.168.15.2:/home/homelab/agents_workspace/
```

2. Construi a imagem e subi o container PrintShare.

- Build (no host):

```bash
cd /home/homelab/printshare
docker build -t printshare_printshare .
```

- Execução final (container com socket CUPS montado):

```bash
docker rm -f printshare || true
docker run -d --name printshare --restart unless-stopped \
  -p 8085:8085 --privileged \
  -v /dev:/dev \
  -v /home/homelab/agents_workspace:/home/homelab/agents_workspace:ro \
  -v /home/homelab/printshare/app.py:/app/app.py:ro \
  -v /var/run/cups/cups.sock:/var/run/cups/cups.sock \
  -e CUPS_PRINTER=L380 \
  printshare_printshare
```

Observação: a montagem de `/var/run/cups/cups.sock` permite que o container execute `lp` apontando para o CUPS do host.

3. Testes iniciais via API PrintShare:

- Health:

```bash
curl http://127.0.0.1:8085/health
# => {"status":"ok"}
```

- Envio de job de texto (exemplo):

```bash
curl -sS -X POST http://127.0.0.1:8085/print \
  -H "Content-Type: application/json" \
  -d '{"type":"text","content":"PrintShare test via CUPS (socket): OK"}' -w "\nHTTP_CODE:%{http_code}\n"
```

Resposta observada (exemplo):

```json
{"message":"request id is L380-99 (1 file(s))\n","ok":true}
HTTP_CODE:200
```

4. Verificações no host (CUPS):

```bash
lpstat -p L380 -l
lpstat -o
lpstat -v
lpoptions -p L380 -l
sudo tail -n 200 /var/log/cups/error_log
```

Excertos relevantes obtidos:
- `lpstat -v` mostrou: `device for L380: ondemand://127.0.0.1:9877`
- Job enfileirado: `L380-99 root 1024 ...` (mostrado em `lpstat -o`)
- CUPS respondeu às requisições IPP (logs no `error_log`) e processou o pedido.

5. Alternativa/driver Phomemo
- O serviço também suporta enviar jobs direto ao Phomemo Q30 via `phomemo_print.py` quando a impressora estiver disponível como `/dev/rfcomm0` ou `/dev/ttyUSB*`.
- Para isso, defina `PRINTER_PORT=/dev/rfcomm0` ou use o `--hint PHOMEMO` e não monte o socket CUPS no container.

---

## Integração com Open WebUI
- Havia um script `install_printer_function.py` que tenta registrar a função no Open WebUI via API. A tentativa inicial falhou porque o Open WebUI está configurado com OIDC/Authentik e o endpoint de autenticação não aceita login JSON simples.
- Opções para integrar a função no Open WebUI:
  - Usar a própria UI administrativa do Open WebUI para criar/colar o código da função (`openwebui_printer_function.py`).
  - Inserir a função diretamente no banco `webui.db` do container (SQLite) e ativar `is_active=1` (exige cuidado, backup e reinício do container). Um script de exemplo `recreate_printer_complete.py` existe no repositório para auxiliar.

Atenção: alterar o DB do container requer backup e autorização operacional.

---

## Comandos úteis para manutenção e diagnóstico
- Ver status do container:

```bash
docker ps --filter name=printshare
```

- Ver logs do serviço:

```bash
docker logs printshare --tail 200
```

- Ver fila CUPS e detalhes:

```bash
lpstat -p L380 -l
lpstat -o
sudo tail -n 200 /var/log/cups/error_log
```

- Testar driver Phomemo diretamente (host):

```bash
cd /home/homelab/agents_workspace
. .venv_printer/bin/activate  # se usou venv
python3 phomemo_print.py --list
python3 phomemo_print.py --text "TESTE" --port /dev/rfcomm0
```

- Recriar container (rollback rápido):

```bash
docker rm -f printshare || true
docker run -d --name printshare --restart unless-stopped -p 8085:8085 \
  --privileged -v /dev:/dev -v /home/homelab/agents_workspace:/home/homelab/agents_workspace:ro \
  -v /var/run/cups/cups.sock:/var/run/cups/cups.sock -e CUPS_PRINTER=L380 printshare_printshare
```

- Remover imagem e artefatos (rollback completo):

```bash
docker rm -f printshare || true
docker rmi printshare_printshare || true
rm -rf /home/homelab/printshare
# (opcional) remover scripts copiados em /home/homelab/agents_workspace
```

---

## Observações de segurança e recomendações
- O container foi executado com `--privileged` e acesso a `/dev` e ao socket CUPS — conveniente para POC, mas inseguro em produção; recomenda-se:
  - Restringir o container (evitar `--privileged`), mapear só a porta serial necessária ou usar um serviço host que aceite jobs via API autenticada.
  - Criar um usuário de serviço que tenha acesso ao socket CUPS, em vez de montar o socket como root.
  - Habilitar autenticação/controle de acesso à API PrintShare (atualmente sem autenticação).

- Integração com Open WebUI: preferir registro via API usando OIDC ou via UI administrativa para evitar escrita direta no DB.

---

## Próximos passos sugeridos
- Se desejar, faço a integração automática da função no Open WebUI (requer autorização para editar o DB do container ou configurar credenciais OIDC corretas).
- Se preferir que o Phomemo seja usado por serial (rfcomm), oriento o pareamento Bluetooth e configuro `PRINTER_PORT=/dev/rfcomm0`.

---

## Logs/evidências (trechos)
- Solicitação API PrintShare (resultado): `request id is L380-99 (1 file(s))`
- `lpstat -o` mostrou `L380-99 root 1024` (job submetido ao CUPS)
- `lpstat -v` mostrou `device for L380: ondemand://127.0.0.1:9877` (printer configurada no CUPS remoto)


---

Se quiser, eu adiciono este serviço ao `docker-compose` do homelab ou crio um systemd unit para gerenciar o container. Também posso prosseguir com a integração final no Open WebUI (precisa de autorização).