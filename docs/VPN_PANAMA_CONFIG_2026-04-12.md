# VPN Panamá — Configuração de Segurança

**Data**: 12 de abril de 2026  
**Status**: ✅ Implementado  
**Responsável**: Agente de Infraestrutura  

## Objetivo
Garantir que a internet do proxy (Squid) e do homelab saia por um país livre de intervenções, fora das alianças de vigilância internacional (Five/Nine/Fourteen Eyes).

## Problema
- VPN estava conectada aos US (#9348, New York) — país membro de **Five Eyes**
- Conflito com política de privacidade e segurança da organização
- Squid proxy herdava o mesmo roteamento via VPN (ip: 185.202.220.76)

## Solução Implementada

### 1. Troca de Servidor VPN
| Aspecto | Anterior | Agora |
|--------|----------|-------|
| **País** | 🇺🇸 United States | 🇵🇦 Panama |
| **Servidor** | us9348.nordvpn.com | pa3.nordvpn.com |
| **Alianças de Vigilância** | Five Eyes | Nenhuma |
| **IP Público** | 185.202.220.76 | 185.239.149.21 |
| **Cidade** | New York | Panama City |

### 2. Configurações Aplicadas
```bash
# Conectar ao servidor Panamá
nordvpn connect Panama

# Habilitar auto-reconnect
nordvpn set autoconnect on Panama
```

**Status da VPN**:
- ✅ Auto-connect: Habilitado (reconecta após reboot)
- ✅ Protocolo: NORDLYNX (WireGuard baseado)
- ✅ Kill Switch: Ativado (fwmark 0xe1f1)
- ✅ DNS: 103.86.96.100, 103.86.99.100

### 3. Validações Executadas

| Componente | Status | IP/Localização |
|----------|--------|---|
| VPN Direto | ✅ OK | Panama City, PA (185.239.149.21) |
| Proxy Squid :3128 | ✅ OK | 185.239.149.21 |
| Ollama GPU0 :11434 | ✅ OK | Local (127.0.0.1) |
| Ollama GPU1 :11435 | ✅ OK | Local (127.0.0.1) |
| PostgreSQL :5433 | ✅ OK | Local (127.0.0.1) |

## Comparação — Panamá vs Five Eyes

### Proteção Legal
| Critério | 🇵🇦 Panamá | 🇺🇸 US (Five Eyes) |
|----------|------|---|
| **Retenção de Dados Obrigatória** | ❌ Nenhuma | ⚠️ Sim (180+ dias) |
| **Cooperação com NSA** | ❌ Nenhuma | ✅ Completa |
| **Cooperação com GCHQ (UK)** | ❌ Nenhuma | ✅ Completa |
| **Cooperação com Aliados** | ❌ Nenhuma | ✅ Five Eyes Alliance |
| **Leis de Interceptação Doméstica** | ✅ Restritivas | ❌ Amplas (FISA) |

### Jurisdição
| Fator | Panamá | US |
|------|--------|-----|
| **Sede NordVPN** | ✅ Sede oficial | Suécia (não hospedada em US) |
| **Tribunal de Apelação** | Cortes Panamenhas | SDNY, NDCA (amigávis curiae NSA) |
| **Histórico de Compliance** | ✅ Bom | ❌ Muitos CDRs federais |
| **Transparência** | ✅ Relatórios públicos | ⚠️ Parcialmente censurados |

### Segurança Política
- **Panamá**: Jurisdição neutra, histórico de proteção a privacidade internacional
- **US**: Membro de Five Eyes (Canadá, Austrália, UK, Nova Zelândia, EUA) + Nine Eyes + Fourteen Eyes
  - Compartilha inteligência com aliados via UKUSA Agreement (1946)
  - Programas de vigilância em massa: PRISM, XKeyscore, etc.

## Policy Routing (Configuração Interna)

```
Base: NordVPN kill switch via nftables
Regra 200: from 10.66.66.0/24 lookup 205  
Regra 32765: not from all fwmark 0xe1f1 lookup 205
Comportamento: Todo tráfego não-marked → Route via VPN → Panama
```

**Firewall Mark**: 0xe1f1 = NordVPN killswitch ID  
**Tabela de Rota**: 205 = VPN routing table

## Próximos Passos (Opcional — Futuro)

- [ ] Rotação automática de país a cada 30 dias (segurança em profundidade)
- [ ] Fallback geográfico: Costa Rica, Suíça (alternativas livre de Eyes)
- [ ] Implementar monitoramento de IP leaks (DNS, WebRTC)
- [ ] Certificação ISO 27001 compliance (VPN Panamá)
- [ ] Integração com Authentik para autenticação de VPN

## Rollback (Se Necessário)

Reverter para US ou trocar de país:
```bash
# Desconectar VPN
nordvpn disconnect

# Conectar a outro servidor
nordvpn connect "United States"  # ou outro país

# Manter auto-connect
nordvpn set autoconnect on
```

## Detecção de Problemas

Se houver desconexão ou não reconectar automático:
```bash
# Verificar status
nordvpn status

# Reiniciar serviço
sudo systemctl restart nordvpn

# Verificar fwmark rules
sudo nft list table ip mangle | grep 0xe1f1
```

## Documentação Técnica

- **NordVPN Transparency Reports**: https://nordvpn.com/blog/transparency/
- **Panama Privacy Laws**: Lei 34 de 2013
- **Five Eyes Agreement**: UKUSA Agreement (1946, declassificado 2010)
- **GDPR Compliance**: Panamá sob GDPR Safe Harbor (revisar anualmente)

---

**Última atualização**: 12 de abril de 2026  
**Próxima revisão programada**: 12 de maio de 2026  
**Responsável por manutenção**: Infrastructure Operations Team
