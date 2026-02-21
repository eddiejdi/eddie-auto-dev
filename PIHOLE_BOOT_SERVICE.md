# Pi-hole Boot Service (homelab)

Este documento descreve como configurar o Pi-hole do homelab para iniciar
automaticamente no boot usando um serviço systemd. Embora o container esteja
localizado em `~/pihole` no servidor, a abordagem abaixo é genérica e pode ser
reaplicada em outras máquinas da infraestrutura.

## Unidade systemd

Crie o arquivo `/etc/systemd/system/pihole.service` com o conteúdo:

```ini
[Unit]
Description=Pi-hole Container
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/homelab/pihole
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down

[Install]
WantedBy=multi-user.target
```

Ele simplesmente executa `docker-compose up -d` e `docker-compose down` no
diretório onde o `docker-compose.yml` do Pi-hole vive.

## Habilitando o serviço

```sh
ssh homelab@192.168.15.2 <<'EOF'
sudo systemctl daemon-reload
sudo systemctl enable pihole.service
sudo systemctl start pihole.service
EOF
```

A partir daí o container será levantado sempre que o servidor reiniciar e você
pode controlar o processo com `systemctl status|start|stop pihole.service`.

### Observações

* Se alterar a configuração no `docker-compose.yml` (por exemplo senha ou
  servidores DNS upstream), execute `sudo systemctl restart pihole.service` para
  aplicar as mudanças.
* O health‑check do homelab (`scripts/homelab-health-check.sh`) já verifica se
  esta unidade existe e se o container está funcionando.
* Este guia é uma boa prática para qualquer serviço containerizado leve que não
  possua um orchestration platform; facilita reinícios e manutenção.
