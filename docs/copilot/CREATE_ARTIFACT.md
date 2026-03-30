# Como Criar Novos Artefatos de Customização

Use o script `tools/create_copilot_artifact.py` para criar skills, agents, prompts e instructions com scaffolding automático.

## Quick Start

```bash
python tools/create_copilot_artifact.py
```

O script é interativo e vai guiá-lo por:
1. **Escolha do tipo** (skill, agent, prompt ou instruction)
2. **Coleta de informações** (nome, descrição, conteúdo)
3. **Geração automática** de frontmatter YAML com validação
4. **Validação local** via `lint-frontmatter.py` antes de salvar

## O que cada tipo faz

### 1. **Skill** (Workflow multi-step, recorrente)
Para padrões complexos, multi-step. Exemplo: `testing-strategy`, `security-hardening`

**Quando usar:**
- Workflow com 3+ passos sequenciais
- Aplicável a múltiplos casos de uso (recorrente)
- Bundled com assets (templates, checklists, exemplos)

**Estrutura:**
- Objetivo e escopo (quando usar / não usar)
- Workflow detalhado com passos
- Validação (como saber se deu certo)
- Erros comuns e soluções

**Output:** `.github/skills/<nome>/SKILL.md`

### 2. **Agent** (Persona especializada)
Para agentar com papel específico e tool restrictions. Exemplo: `security-auditor`, `trading-analyst`

**Quando usar:**
- Único ou poucos casos de uso (diferente de skill)
- Requer tool access específico (read, edit, execute, search)
- Persona bem-definida

**Estrutura:**
- Descrição com trigger phrases
- Persona e responsabilidades
- Ferramentas permitidas
- Workflow típico

**Output:** `.github/agents/<nome>.agent.md`

### 3. **Prompt** (Tarefa única, workflow específico)
Para workflows de uma tarefa. Exemplo: `code-review-security`, `design-api-schema`

**Quando usar:**
- Objetivo único e bem-definido
- Workflow direto (1-3 passos)
- Entrada/saída bem-definida

**Estrutura:**
- Descrição com trigger phrases
- Objetivo único
- Entrada esperada (exemplo)
- Saída esperada
- Validação

**Output:** `.github/prompts/<nome>.prompt.md`

### 4. **Instruction** (Regras globais por path)
Para padrões codebase: estilos, convenções, guardrails. Exemplo: `python-coding`, `trading-database`

**Quando usar:**
- Regras que se aplicam a múltiplos arquivos
- Padrões codebase-wide (Python, APIs, trading)
- Enforcement via IA em arquivos matching glob

**Estrutura:**
- Scope (glob pattern)
- Regras principais (1 por linha)
- Exemplos do certo
- Contra-exemplos (evitar)

**Output:** `.github/instructions/<nome>.instructions.md`

## Exemplo de Execução

```bash
$ python tools/create_copilot_artifact.py

============================================================
🚀 Copilot Artifact Creator
============================================================

🎯 Qual tipo de artefato deseja criar?
  1. Skill (workflow multi-step, recorrente)
  2. Agent (persona especializada)
  3. Prompt (tarefa única, workflow específico)
  4. Instruction (regras globais por path)

Escolha (1-4): 1

📚 Criando novo Skill

Nome do skill (ex: api-design, testing-advanced): advanced-api-testing
Descrição (trigger phrase, ex: 'Use when: designing REST APIs'): Use when: testing complex APIs with mocking and integration scenarios

📝 Estrutura do Skill:
  - Objetivo: O que a skill ensina/permite
  - Escopo: Quando usar / quando NÃO usar
  - Workflow: Passos principais
  - Validação: Como verificar sucesso

Objetivo do skill: Ensinar padrões avançados de teste de APIs, incluindo mocking, fixtures compartilhadas e cenários de integração

Quando usar (1-2 linhas): Quando testando APIs com múltiplas dependências ou padrões complexos de setup/teardown

Quando NÃO usar (1-2 linhas): Para testes unitários simples; use testing-strategy base em vez disso

Workflow dos passos (termine com linha vazia):
1. Identifique dependências externas (DBs, APIs)
2. Implemente fixtures compartilhadas com conftest.py
3. Use mocks para isolar o SUT (system under test)
4. Teste cenários de erro além do happy path
5. Valide cobertura e regressão

📂 Destino: .github/skills/advanced-api-testing/SKILL.md
Criar artefato? (s/n): s

✅ Artefato criado: .github/skills/advanced-api-testing/SKILL.md

🔍 Validando frontmatter...
✅ Validação passou

🎉 Sucesso! Seu skill está pronto:
   .github/skills/advanced-api-testing/SKILL.md

Próximos passos:
  1. Edite o arquivo para adicionar conteúdo detalhado
  2. Execute 'git add' e 'git commit'
  3. Push para PR e aguarde validação em CI
```

## Validação Automática

Todo artefato criado é validado **antes de ser salvo**:

✅ **Frontmatter YAML** (estrutura correta)
✅ **Campos obrigatórios** (description, etc)
✅ **applyTo patterns** (não muito broad, ex: `**`)
✅ **Naming conventions** (lowercase, hífens)

Se validação falhar:
- Arquivo é **removido**
- Erro específico é exibido
- Você pode tentar novamente

## Workflow Pós-Criação

Depois de criar:

1. **Edite o arquivo** para adicionar conteúdo detalhado
   ```bash
   vim .github/skills/seu-skill/SKILL.md
   ```

2. **Valide localmente** rodando linter novamente
   ```bash
   python .github/hooks/lint-frontmatter.py
   ```

3. **Commit e push**
   ```bash
   git add .github/skills/seu-skill/SKILL.md
   git commit -m "feat(skills): add seu-skill"
   git push
   ```

4. **CI valida** (GitHub Actions: `lint-instructions.yml`)
   - Se passar: ✅ pronto para merge
   - Se falhar: ❌ ajuste frontmatter e tente novamente

## Troubleshooting

**❌ "Validação falhou: missing required field: description"**
- Certifique-se de fornecer uma descrição clara (trigger phrases)
- Descrição deve estar entre aspas duplas no YAML

**❌ "applyTo is too broad"**
- Padrão `**` ou `*/**` é muito genérico
- Prefira globs específicos: `**/tests/**`, `src/api/**.py`
- Para instruction sem restricão de path, omita `applyTo`

**❌ "Artefato já existe"**
- O arquivo já foi criado
- Use comando `git status` para listar artefatos pendentes

**❌ "Linter não encontrado"**
- `.github/hooks/lint-frontmatter.py` não existe
- Verifique que você está no diretório raiz do repo

## Integração com Decisões

Não tem certeza se criar skill/agent/prompt? Consulte:

- **Frameworks**: `docs/copilot/SKILL_FRAMEWORK.md`, `docs/copilot/AGENT_FRAMEWORK.md`
- **Checklists**: `assets/copilot/checklists/pre-skill-creation.md`
- **Exemplos**: `assets/copilot/examples/`

## Veja também

- [FRONTMATTER_REFERENCE.md](../docs/copilot/FRONTMATTER_REFERENCE.md) — Especificação YAML
- [CUSTOMIZATION_GUIDE.md](../docs/copilot/CUSTOMIZATION_GUIDE.md) — Guia completo
- [TROUBLESHOOTING.md](../docs/copilot/TROUBLESHOOTING.md) — Problemas comuns
