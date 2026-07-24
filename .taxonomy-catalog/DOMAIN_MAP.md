# Taxonomy Domain Map

**Generated:** 2026-07-24T20:01:32.531020

Diagrama Mermaid dos hubs de domínio (contagens do grafo).

```mermaid
flowchart LR
  classDef hub fill:#1f2937,stroke:#93c5fd,color:#e5e7eb
  trading["trading\nT:32 A:10 V:43"]:::hub
  storage["storage\nT:0 A:30 V:16"]:::hub
  social["social\nT:0 A:25 V:48"]:::hub
  health["health\nT:0 A:14 V:0"]:::hub
  llm["llm\nT:0 A:12 V:425"]:::hub
  agents["agents\nT:0 A:9 V:4"]:::hub
  auth["auth\nT:0 A:9 V:0"]:::hub
  infra["infra\nT:0 A:8 V:5"]:::hub
  monitoring["monitoring\nT:0 A:8 V:21"]:::hub
  marketing["marketing\nT:5 A:2 V:0"]:::hub
  platform["platform\nT:0 A:7 V:0"]:::hub
  secrets["secrets\nT:0 A:7 V:125"]:::hub
  ops["ops\nT:0 A:6 V:0"]:::hub
  content["content\nT:5 A:0 V:0"]:::hub
  meetings["meetings\nT:0 A:5 V:0"]:::hub
  sentiment["sentiment\nT:5 A:0 V:0"]:::hub
  portal["portal\nT:4 A:0 V:0"]:::hub
  acervo["acervo\nT:0 A:3 V:0"]:::hub
  banking["banking\nT:0 A:3 V:1"]:::hub
  cmdb["cmdb\nT:0 A:3 V:7"]:::hub
  trading -.-> secrets
  trading -.-> llm
  storage -.-> secrets
  marketing -.-> social
  agents -.-> llm
  agents -.-> ipc
  banking -.-> secrets
  portal -.-> storage
  wiki -.-> llm
  monitoring -.-> infra
```

Ver também: [docs/taxonomy/GRAPH.md](../docs/taxonomy/GRAPH.md), `graph.json`, [TAXONOMY_QUICK_START.md](../TAXONOMY_QUICK_START.md).
