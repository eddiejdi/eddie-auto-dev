Tools & Utilities
=================

## 🚀 Copilot Artifact Creator

Criar skills, agents, prompts e instructions para GitHub Copilot com validação automática.

```bash
python create_copilot_artifact.py
```

**O que faz:**
- Guia interativo para escolher tipo de artefato
- Coleta informações e gera frontmatter YAML
- Valida com `lint-frontmatter.py` antes de salvar
- Cria estrutura correta em local apropriado

**Exemplos:**
- Skill (workflow multi-step): testing, security, deployment
- Agent (persona): security-auditor, testing-specialist, trading-analyst
- Prompt (tarefa única): code-review, design-api
- Instruction (regras globais): python-coding, trading-db

Veja: [CREATE_ARTIFACT.md](/docs/copilot/CREATE_ARTIFACT.md)

---

## Auto-retraining

Automatizar criação do Modelfile e validação no Ollama.

Uso rápido:

```bash
python3 auto_retrain.py --data /path/to/whatsapp_training_data.jsonl \
  --out-dir /home/homelab/myClaude --model-name shared-whatsapp --create
```

Para testar localmente sem criar o modelo (útil para CI):

```bash
python3 auto_retrain.py --data tests/sample.jsonl --out-dir /tmp/out --dry-run
```

---

## Outros Utilitários

- **copilot_hooks/**: Hooks de validação e guardrails para Copilot
- **vault/**: Gerenciamento de segredos
- **deploy/**: Scripts de deployment
- **homelab/**: Utilitários de homelab
- **trading_agent_desk_test.py**: Testa agent de trading
- E muitos outros...

(Veja listagem completa em `ls -la` direito neste diretório)
