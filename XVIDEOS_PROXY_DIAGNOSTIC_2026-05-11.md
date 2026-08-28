# Diagnóstico: Acesso a xvideos.com via Proxy Homelab

**Data**: 11 de maio de 2026  
**Status**: ✅ **PROXY FUNCIONANDO NORMALMENTE**  
**Homelab**: 192.168.15.2 (Squid:3128, Pi-hole:53)

---

## 1. Achados

| Componente | Status | Evidência |
|-----------|--------|-----------|
| **DNS (Pi-hole)** | ✅ Funcionando | `nslookup www.xvideos.com 127.0.0.1` → resolvido em 89.222.127.x |
| **Squid Proxy** | ✅ Funcionando | Log: `TCP_TUNNEL/200` para www.xvideos.com:443 |
| **HTTP Request** | ✅ Funcionando | `curl -x http://127.0.0.1:3128 -I https://www.xvideos.com` → `HTTP/2 200` |
| **Blocklists (Pi-hole)** | ✅ Sem bloqueio | xvideos.com não aparece em nenhuma gravity list |
| **ACLs (Squid)** | ✅ Sem bloqueio | ACL `xvideos_ads` bloqueia apenas domínios de ads/tracking, não o site principal |
| **Firewall (nftables)** | ✅ Sem bloqueio | Nenhuma regra bloqueando tráfego para xvideos.com |

---

## 2. Logs do Squid

```
1778504101.426  12764 192.168.15.109 TCP_TUNNEL/200 35770 CONNECT www.xvideos.com:443 - HIER_DIRECT/89.222.127.8 -
```

- **TCP_TUNNEL/200**: Conexão ESTABELECIDA com sucesso (status 200 = OK)
- **HIER_DIRECT**: Rota direta para 89.222.127.8
- **Timestamp**: 2026-05-11 12:56:48 GMT

---

## 3. ACLs do Squid

Existe uma ACL `xvideos_ads` que bloqueia domínios de publicidade/tracking:

```
acl xvideos_ads dstdomain .exoclick.com .trafficjunky.net .sexcash.com ...
http_access deny xvideos_ads
```

**Importante**: Isso bloqueia IPs de ads, **NÃO** o domínio xvideos.com principal.

---

## 4. Próximas Etapas (se ainda há bloqueio no cliente)

Se o usuário ainda experiencia bloqueio, o problema está no **cliente**, não no proxy:

### 4.1 Diagnóstico no Cliente

```bash
# Testar via proxy (Windows/macOS/Linux)
curl -x http://192.168.15.2:3128 -I https://www.xvideos.com

# Ou via browser (definir proxy manual):
# Configurações → Proxy → 192.168.15.2:3128
```

### 4.2 Causas Possíveis no Cliente

1. **Firewall local** bloqueando porta 3128 → Abrir porta 3128/TCP
2. **VPN ativa** com bloqueios próprios → Desativar ou whitelisting
3. **Antivírus** bloqueando → Verificar configurações
4. **Proxy anterior** em cache → Limpar cache do browser
5. **DNS cache** → `ipconfig /flushdns` (Windows) ou `sudo dscacheutil -flushcache` (macOS)

### 4.3 Se Houver Bloqueio de Ads

O Squid bloqueia publicidade. Se houver erro `TCP_DENIED/403` para ads-domains, é **esperado e seguro**.

Para whitelist de um domínio de ads, editar `/etc/squid/squid.conf`:

```squid
# Adicionar ANTES da regra deny
http_access allow <novo_whitelist>
```

---

## 5. Comando para Verificar Bloqueios em Tempo Real

No homelab, monitore bloqueios com:

```bash
sudo tail -f /var/log/squid/access.log | grep -i xvideos
```

Se retornar nada, nenhuma requisição está sendo bloqueada.

---

## 6. Resumo Executivo

✅ **O proxy homelab FUNCIONA corretamente para xvideos.com**

Se há bloqueio na experiência do usuário:
- ❌ Não é Pi-hole
- ❌ Não é Squid
- ❌ Não é firewall homelab
- ✅ É problema no cliente/rede local

**Ação recomendada**: Validar configuração do proxy no cliente e verificar firewall/VPN locais.
