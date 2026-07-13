# KuCoin News Feed — Integração RSS Sentiment

## Visão geral

A KuCoin **não expõe feed RSS/XML público**. Os endpoints comuns (`/rss`, `/feed`, `/blog/feed`) retornam HTML (SPA), não XML.

Para incluir notícias KuCoin no pipeline de sentimento (`rss-sentiment-exporter`), o sistema consome duas fontes alternativas:

| Fonte | Tipo | Endpoint | Conteúdo |
|-------|------|----------|----------|
| **kucoin_flash** | Sitemap XML | `https://www.kucoin.com/site-map_flash_{lang}_1.xml` | Flash news de mercado (BTC, ETH, SOL, etc.) |
| **kucoin_announcements** | API CMS JSON | `https://www.kucoin.com/_api/cms/articles` | Anúncios oficiais (listings, delistings, manutenção) |

Atualização do sitemap flash: ~30 minutos.

---

## Arquitetura

```
site-map_flash_en_1.xml          _api/cms/articles?page=1&pageSize=N
         │                                    │
         └──────── kucoin_news_fetcher.py ────┘
                         │
                  collect_kucoin_items()
                         │
              rss_sentiment_exporter.py
                  fetch_kucoin_articles()
                         │
                  detect_coins() → NewsArticle
                         │
              classify_sentiment_ollama()
                         │
                  btc.news_sentiment (PostgreSQL)
```

### Arquivos

| Arquivo | Função |
|---------|--------|
| `grafana/exporters/kucoin_news_fetcher.py` | Coleta e normaliza flash + anúncios |
| `grafana/exporters/rss_sentiment_exporter.py` | Integra via `fetch_kucoin_articles()` em `fetch_all_feeds()` |
| `tests/test_kucoin_news_fetcher.py` | Testes do coletor |
| `tests/test_rss_sentiment_exporter.py` | Testes de integração |

---

## Configuração

Variáveis de ambiente (opcionais):

| Variável | Default | Descrição |
|----------|---------|-----------|
| `KUCOIN_NEWS_ENABLED` | `1` | `0`/`false` desativa fontes KuCoin |
| `KUCOIN_NEWS_SITEMAP_LANG` | `en` | Idioma do sitemap flash (`pt`, `en`, etc.) |
| `KUCOIN_NEWS_FLASH_MAX` | `50` | Máximo de itens flash por ciclo |
| `KUCOIN_NEWS_ANNOUNCEMENTS_MAX` | `20` | Máximo de anúncios CMS por ciclo |
| `KUCOIN_NEWS_FETCH_TIMEOUT` | `30` | Timeout HTTP em segundos |

Exemplo no envfile do serviço:

```bash
KUCOIN_NEWS_ENABLED=1
KUCOIN_NEWS_SITEMAP_LANG=en
KUCOIN_NEWS_FLASH_MAX=50
KUCOIN_NEWS_ANNOUNCEMENTS_MAX=20
```

---

## Formato dos dados

### Flash news (sitemap)

Cada entrada XML traz `loc` (URL) e `lastmod` (data). O título é derivado do slug da URL:

```
/news/flash/bitcoin-etfs-end-8-week-redemption-streak-with-197m-inflow
→ "Bitcoin Etfs End 8 Week Redemption Streak With 197m Inflow"
```

### Anúncios (CMS API)

Resposta JSON paginada:

```json
{
  "success": true,
  "items": [
    {
      "title": "Changes to Funding Rate Intervals for PARTIUSDT...",
      "summary": "...",
      "path": "/en-changes-to-funding-rate-intervals...",
      "publish_at": "2026-07-13 01:21:00",
      "publish_ts": 1783876860
    }
  ]
}
```

URL final: `https://www.kucoin.com/announcement{path}`

---

## Sources no PostgreSQL

Artigos KuCoin aparecem em `btc.news_sentiment` com:

- `source = 'kucoin_flash'` — notícias de mercado
- `source = 'kucoin_announcements'` — anúncios operacionais

A detecção de moedas (`detect_coins`) filtra apenas artigos com menção a BTC, ETH, XRP, SOL, DOGE, ADA ou termos crypto genéricos (`GENERAL`).

---

## Deploy

```bash
# Copiar módulos para o homelab
sudo install -o trading-svc -g trading-svc -m 0644 \
  grafana/exporters/kucoin_news_fetcher.py \
  /apps/crypto-trader/trading/grafana/exporters/kucoin_news_fetcher.py

sudo install -o trading-svc -g trading-svc -m 0644 \
  grafana/exporters/rss_sentiment_exporter.py \
  /apps/crypto-trader/trading/grafana/exporters/rss_sentiment_exporter.py

sudo systemctl restart rss-sentiment-exporter.service
```

Verificar logs:

```bash
journalctl -u rss-sentiment-exporter -f | grep -E 'kucoin|Feed kucoin'
```

Saída esperada:

```
Feed kucoin_flash: 42 artigos relevantes
Feed kucoin_announcements: 8 artigos relevantes
```

---

## Testes

```bash
pytest tests/test_kucoin_news_fetcher.py tests/test_rss_sentiment_exporter.py::TestFetchKucoinArticles -v
pytest tests/test_rss_sentiment_exporter.py::TestFetchAllFeeds -v
pytest tests/test_rss_sentiment_exporter.py::TestConfiguracao::test_kucoin_sources_configuradas -v
```

---

## Limitações

1. **Sem RSS nativo** — depende de sitemap + API CMS; mudanças no site podem quebrar o coletor.
2. **Títulos flash** — derivados do slug; menos precisos que o HTML da página.
3. **Sem auth** — API CMS é pública; rate limits não documentados.
4. **Anúncios operacionais** — delistings e manutenção impactam trading, mas podem ter sentimento neutro.

---

## Referências

- Flash news: https://www.kucoin.com/news/flash
- Anúncios: https://www.kucoin.com/announcement
- Sitemap índice flash: https://www.kucoin.com/site-map_flash.xml
- Doc geral RSS Sentiment: `docs/RSS_SENTIMENT_EXPORTER_IMPLEMENTATION.md`