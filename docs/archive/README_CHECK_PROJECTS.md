# Ativação do Serviço de Revisão Automática de Projetos Python

## Objetivo
Executar periodicamente testes automatizados (pytest) em todos os projetos Python do diretório `dev_projects/python`, atualizando relatórios de CI/CD para a equipe.

## Arquivos necessários
- `check_projects_service.sh` (script de revisão)
- `check_projects.service` (systemd service)
- `check_projects.timer` (systemd timer)

## Passos para ativação no servidor

1. **Copie os arquivos para o servidor**

scp check_projects_service.sh check_projects.service check_projects.timer usuario@servidor:/caminho/destino/
2. **Dê permissão de execução ao script**

sudo chmod +x /caminho/destino/check_projects_service.sh
3. **Mova os arquivos de serviço/timer para o systemd**

sudo cp /caminho/destino/check_projects.service /etc/systemd/system/
sudo cp /caminho/destino/check_projects.timer /etc/systemd/system/
4. **Recarregue o systemd e ative o timer**

sudo systemctl daemon-reload
sudo systemctl enable --now check_projects.timer
5. **Verifique o status**

systemctl status check_projects.timer
systemctl status check_projects.service
## Observações
- O serviço roda a cada 15 minutos e atualiza os arquivos `CI_REPORT.txt` de cada projeto.
- Logs de execução ficam em `/tmp/pytest_<projeto>.log` e `/tmp/pytest_<projeto>.exit`.
- Para desativar: `sudo systemctl disable --now check_projects.timer`

## Checklist para o time de infraestrutura
- [ ] Python 3 e pytest instalados no servidor
- [ ] Permissões de escrita na pasta dos projetos e em `/tmp`
- [ ] Systemd ativo e permissões de root para registrar serviços
- [ ] Teste manual: execute `bash /caminho/destino/check_projects_service.sh` e verifique os relatórios

---
Dúvidas ou problemas? Consulte este README ou acione o responsável pelo CI/CD.
