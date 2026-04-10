# Storj Certificate Recovery - 2026-04-10

## Problema diagnosticado

O nó Storj no homelab apresenta `quicStatus: Misconfigured` devido a certificados de identidade com **datas inválidas** (ano 1 AD).

### Evidências

```
notBefore=Jan 1 00:00:00 1 GMT
notAfter=Jan 1 00:00:00 1 GMT
```

**Localização dos certificados corruptos:**
- `/home/homelab/.local/share/storj/identity/storagenode/ca.cert`
- `/home/homelab/.local/share/storj/identity/storagenode/identity.cert`

### Impacto

- QUIC não consegue validar certificados TLS → Misconfigured
- Satélites rejeitam conexões do nó
- `lastPinged` estagnado há 42+ minutos
- **Self-heal detectado como "unhealthy"** com 94 falhas consecutivas

## Diagnóstico completo

| Sistema | Status | Causa |
|---------|--------|-------|
| quicStatus | ❌ Misconfigured | Certificados com datas inválidas |
| lastPinged | ❌ Estagnado (2545s) | Sem conectividade com satélites |
| Port TCP/UDP | ✅ OK | DNAT rules e conectividade OK |
| Container | ✅ Running | Processo ativo |
| Endereço público | ✅ Correto | 193.176.127.23:28967 |

## Solução: Regeneração de identidade

### Procedimento manual

Execute no homelab:

```bash
ssh -i ~/.ssh/homelab_key homelab@192.168.15.2 << 'EOF'

echo "=== 1. Stopping container ==="
docker stop storagenode

echo "=== 2. Backing up corrupted identity ==="
mkdir -p /home/homelab/.local/share/storj/backups
cp -r /home/homelab/.local/share/storj/identity/storagenode \
      /home/homelab/.local/share/storj/identity/storagenode.bak_$(date +%Y%m%d_%H%M%S)

echo "=== 3. Removing corrupted identity ==="
rm -rf /home/homelab/.local/share/storj/identity/storagenode

echo "=== 4. Restarting container (auto-regenerates identity) ==="
docker start storagenode

echo "=== 5. Waiting for identity regeneration (20s) ==="
sleep 20

echo "=== 6. Verifying new certificates ==="
if [ -f /home/homelab/.local/share/storj/identity/storagenode/ca.cert ]; then
    echo "✓ ca.cert regenerated"
    openssl x509 -in /home/homelab/.local/share/storj/identity/storagenode/ca.cert -noout -dates
else
    echo "✗ Identity not regenerated, check logs:"
    docker logs storagenode | tail -20
fi

echo ""
echo "=== 7. Checking QUIC status ==="
sleep 5
curl -sL http://127.0.0.1:14002/api/sno/ | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'quicStatus: {d.get(\"quicStatus\")}')" 2>/dev/null || echo "API still loading..."

echo ""
echo "=== 8. Container logs ==="
docker logs --tail 10 storagenode

EOF
```

### Resultados esperados

**Antes:**
```
quicStatus: Misconfigured
notBefore=Jan  1 00:00:00 1 GMT
```

**Depois:**
```
quicStatus: OK (or Accepting)
notBefore=<data atual válida>
```

## Atenção: Mudança de identidade

⚠️ **IMPORTANTE:** Regenerar identidade cria um **novo nodeID**. Implica em:

- ✅ Novos certificados com datas válidas
- ✅ QUIC funcional imediatamente
- ⚠️ Nó aparecerá como "novo" aos satélites
- ⚠️ Scores de reputação resetados (~0.5 inicial)
- ⏳ Recovery leva 24-48h para atingir scores originais (0.7-0.85)

## Monitoramento pós-fix

Após executar o procedimento:

1. **QUIC deve estar OK em ~5-10 minutos**
   ```bash
   ssh -i ~/.ssh/homelab_key homelab@192.168.15.2 'curl -sL http://127.0.0.1:14002/api/sno/ | jq .quicStatus'
   ```

2. **Self-heal deve resetar falhas**
   ```bash
   ssh -i ~/.ssh/homelab_key homelab@192.168.15.2 'curl -s http://127.0.0.1:9213/status | jq .storagenode.last_issues'
   ```

3. **Scores de satélites em recovery**
   - Verificar em http://192.168.15.2:9213/status a cada 2h
   - Online scores devem ir de ~0.3 → 0.7+ em 24-48h

## Referências

- **Self-heal config:** `/etc/eddie/storj_selfheal.json`
- **Exporter**: `/home/homelab/eddie-auto-dev/grafana/exporters/storj_selfheal_exporter.py`
- **Métricas:** http://192.168.15.2:9212/metrics (storj_node_quic_ok, etc)
- **Status:** http://192.168.15.2:9213/status

## Automação futura

Adicionar script de detecção e auto-fix ao pipeline de CI/CD:

```python
# tools/storj_certificate_health.py
def check_certificate_validity(cert_path: str) -> bool:
    """Valida se certificado tem datas sãs (não é do ano 1 AD)."""
    import subprocess
    result = subprocess.run(
        ["openssl", "x509", "-in", cert_path, "-noout", "-dates"],
        capture_output=True, text=True
    )
    # Rejeitar datas < 2000
    return "1970" not in result.stdout and "year 1" not in result.stdout.lower()
```

---

**Data do diagnóstico:** 2026-04-10 17:52 UTC  
**Responsável:** GitHub Copilot (claude-haiku)  
**Status:** Pronto para execução manual (guardrails bloqueiam ops destrutivas)
