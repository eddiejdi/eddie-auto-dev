# 🔔 Setup Systemd Timer (em vez de Cron)

## Vantagens vs Cron

| Aspecto | Systemd Timer | Cron |
|--------|---------------|------|
| **Logs** | systemd journal | /var/log/syslog |
| **Recuperação** | Persistent (faz backup) | Perdido |
| **Precisão** | Nanosegundos | Minuto |
| **Integração** | Nativa no systemd | Separada |
| **Status** | `systemctl status` | Manual |

---

## 📦 Instalação

### 1. Copiar arquivos systemd

```bash
# Service (o que executa)
sudo cp rpa4all-validation.service /etc/systemd/system/

# Timer (quando executa)
sudo cp rpa4all-validation.timer /etc/systemd/system/

# Permissões
sudo chmod 644 /etc/systemd/system/rpa4all-validation.*
### 2. Recarregar systemd

```bash
sudo systemctl daemon-reload
### 3. Ativar o timer

```bash
# Ativar (start + enable)
sudo systemctl enable --now rpa4all-validation.timer

# Verificar status
systemctl status rpa4all-validation.timer

# Ver próximas execuções
systemctl list-timers rpa4all-validation.timer
---

## 📊 Monitoramento

### Ver status

```bash
# Timer ativo?
systemctl is-active rpa4all-validation.timer

# Próximas execuções
systemctl list-timers rpa4all-validation.timer

# Último resultado
systemctl status rpa4all-validation.service
### Ver logs

```bash
# Últimos 50 linhas
journalctl -u rpa4all-validation.service -n 50

# Tempo real
journalctl -u rpa4all-validation.service -f

# Últimas 24h
journalctl -u rpa4all-validation.service --since "24 hours ago"

# Apenas erros
journalctl -u rpa4all-validation.service -p err
### Forçar execução agora

```bash
sudo systemctl start rpa4all-validation.service
---

## ⚙️ Modificar Schedule

### Exemplos de OnCalendar

```ini
# Diariamente às 2 AM (padrão)
OnCalendar=*-*-* 02:00:00

# A cada 6 horas
OnCalendar=*-*-* 00,06,12,18:00:00

# A cada 30 minutos
OnCalendar=*-*-* *:00/30:00

# Segundas às 9 AM
OnCalendar=Mon *-*-* 09:00:00

# Horário comercial (9 AM-5 PM a cada hora)
OnCalendar=*-*-* 09-17:00:00

# Todo final de semana
OnCalendar=Sat,Sun *-*-* 02:00:00
### Editar timer

```bash
# Abrir arquivo
sudo nano /etc/systemd/system/rpa4all-validation.timer

# Depois recarregar
sudo systemctl daemon-reload
sudo systemctl restart rpa4all-validation.timer
---

## 🧪 Teste Completo

```bash
#!/bin/bash

echo "1️⃣  Copiar arquivos..."
sudo cp rpa4all-validation.{service,timer} /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/rpa4all-validation.*

echo "2️⃣  Recarregar systemd..."
sudo systemctl daemon-reload

echo "3️⃣  Ativar timer..."
sudo systemctl enable --now rpa4all-validation.timer

echo "4️⃣  Ver status..."
systemctl status rpa4all-validation.timer

echo "5️⃣  Próximas execuções..."
systemctl list-timers rpa4all-validation.timer

echo "✅ Setup completo!"
---

## 🚨 Troubleshooting

### Timer não inicia

```bash
# Verificar erros
systemctl status rpa4all-validation.timer

# Ver logs
journalctl -u rpa4all-validation.timer -n 20
### Service falha na execução

```bash
# Executar manualmente
sudo systemctl start rpa4all-validation.service

# Ver output
journalctl -u rpa4all-validation.service -f
### Verificar permissões

```bash
ls -la /etc/systemd/system/rpa4all-validation.*
ls -la ~/.telegram_config.json
---

## 🛑 Desativar/Remover

### Parar timer

```bash
sudo systemctl stop rpa4all-validation.timer
sudo systemctl disable rpa4all-validation.timer
### Remover arquivos

```bash
sudo rm /etc/systemd/system/rpa4all-validation.*
sudo systemctl daemon-reload
---

**Pronto para usar!** 🚀

Execute o script de teste acima para ativar o systemd timer.
