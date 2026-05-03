# Correção: RSS Sentiment Exporter — OLLAMA_HOST (2026-05-03)

Data: 2026-05-03

Resumo:
- Problema: o painel de Sentimento (Grafana) mostrava valores nulos/zerados para `BTC`.
- Causa principal: `rss-sentiment-exporter` estava apontando `OLLAMA_HOST` para a porta errada (`:11435`) — tanto `OLLAMA_HOST` (GPU0 no código) quanto `OLLAMA_HOST_GPU1` estavam configurados para `:11435`.

Diagnóstico realizado:
- Procurei referências a `sentiment` no repositório e confirmei que o exporter persiste em `btc.news_sentiment` e expõe métricas Prometheus (`btc_news_*`).
- No homelab, verifiquei `systemctl status` e `journalctl` de `rss-sentiment-exporter.service` — o serviço estava ativo, mas havia respostas inválidas do LLM (garbage) e quedas para heurística (sent=0.00 conf=0.25).
- Confirmei a `DATABASE_URL` usada pelo serviço (`postgresql://postgres:eddie_memory_2026@localhost:5433/btc_trading`) e consultei as últimas linhas em `btc.news_sentiment` (via container `eddie-postgres`).

Ação realizada:
- Atualizei o unit systemd `/etc/systemd/system/rss-sentiment-exporter.service` substituindo:
  - `Environment="OLLAMA_HOST=http://192.168.15.2:11435"`
  por
  - `Environment="OLLAMA_HOST=http://192.168.15.2:11437"`  (coordinator GPU proxy)
- Recarreguei o systemd (`daemon-reload`) e reiniciei o serviço `rss-sentiment-exporter.service`.

Verificação pós-fix:
- Serviço reiniciado com sucesso; novos logs mostram shutdown/startup limpos.
- O exporter agora usa o coordinator correto (`:11437`) como `OLLAMA_HOST` (GPU0 no código), mantendo `OLLAMA_HOST_GPU1` em `:11435`.
- Métricas Prometheus continuam sendo expostas em `:9122`. O número de artigos processados depende de novos feeds; o sistema fará fallback heurístico quando o modelo devolver respostas inválidas.

Observações e próximos passos sugeridos:
1. Monitorar o painel Grafana por 10–15 minutos para confirmar que `btc_news_sentiment{coin="BTC"}` deixa de ser zero quando há artigos relevantes.
2. Opcional: melhorar `detect_coins()`/heurística para atribuir melhor artigos "GENERAL" ao `BTC` quando apropriado (ex.: maior sensibilidade para termos relacionados a bitcoin em títulos/descriptions).
3. Revisar a configuração global de Ollama (coordinator vs GPUs) e aplicar a mesma correção em outros units que apontem para a porta errada.

Comandos executados (resumo):
```
sudo sed -i 's|OLLAMA_HOST=http://192.168.15.2:11435|OLLAMA_HOST=http://192.168.15.2:11437|' /etc/systemd/system/rss-sentiment-exporter.service
sudo systemctl daemon-reload
sudo systemctl restart rss-sentiment-exporter.service
sudo journalctl -u rss-sentiment-exporter.service -n 120 --no-pager
docker exec -i eddie-postgres psql -U postgres -d btc_trading -At -c "SELECT to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS TZ'), coin, sentiment, confidence, title FROM btc.news_sentiment ORDER BY timestamp DESC LIMIT 10;"
curl -sS http://127.0.0.1:9122/metrics | head -n 120
```

Se quiser, eu adiciono esse resumo também como página na wiki do homelab (posso subir automaticamente se quiser). Quer que eu publique na wiki agora?
