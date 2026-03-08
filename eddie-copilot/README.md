# Shared Copilot 🤖

Uma extensão VS Code de autocompletar código com IA similar ao GitHub Copilot, alimentada pelo Ollama.

## ✨ Funcionalidades

### 🔮 Autocompletar Inline
- **Sugestões em tempo real** enquanto você digita
- **Ghost text** mostrando a sugestão antes de aceitar
- **Tab para aceitar** a sugestão
- **Escape para dispensar** sugestões
- Suporte para todas as linguagens de programação

### 💬 Chat AI
- Painel lateral com chat interativo
- Streaming de respostas em tempo real
- Histórico de conversas
- Chips de sugestões rápidas

### 🛠️ Ações de Código
- **Explicar código** - Selecione código e peça explicação
- **Corrigir código** - Identifique e corrija bugs
- **Gerar testes** - Crie testes unitários automaticamente
- **Adicionar documentação** - Documente seu código
- **Refatorar** - Melhore a estrutura do código

### ⌨️ Atalhos de Teclado

| Atalho | Ação |
|--------|------|
| `Tab` | Aceitar sugestão |
| `Escape` | Dispensar sugestão |
| `Alt+\` | Forçar sugestão inline |
| `Alt+]` | Próxima sugestão |
| `Alt+[` | Sugestão anterior |
| `Ctrl+Shift+I` | Abrir Chat |

### 🖥️ Homelab Agent

Comandos para gerenciar o servidor homelab diretamente do VS Code (via API na porta 8503):

| Comando (Ctrl+Shift+P) | Descrição |
|-------------------------|-----------|
| `Homelab: Executar Comando` | Executa comando arbitrário (validado pela whitelist) |
| `Homelab: Server Health` | Exibe saúde do servidor (CPU, RAM, disco) |
| `Homelab: Docker PS` | Lista containers Docker em execução |
| `Homelab: Docker Logs` | Logs de um container específico |
| `Homelab: Systemd Status` | Status de um serviço systemd |
| `Homelab: Systemd Restart` | Reiniciar um serviço systemd |
| `Homelab: System Logs` | Logs recentes do sistema |

**Segurança**: Todos os comandos passam por 3 camadas — validação IP (rede local), whitelist de comandos, blocklist explícita. Resultados exibidos no Output Channel "Shared Homelab".

**Configuração**: Adicione em `settings.json`:
```json
{
    "shared-copilot.agentsApiUrl": "http://localhost:8503"
}
```

## 🚀 Instalação

### Pré-requisitos

1. **Ollama** instalado e rodando
   ```bash
   # Linux/macOS
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Windows
   # Baixe de https://ollama.com/download
   ```

2. **Modelo de código** instalado
   ```bash
   # Recomendados para code completion
   ollama pull codellama
   ollama pull deepseek-coder
   ollama pull starcoder2
   
   # Para chat
   ollama pull llama2
   ollama pull mistral
   ```

### Instalar Extensão

#### Via VSIX (Local)
```bash
# 1. Clone ou baixe o projeto
cd shared-copilot

# 2. Instale dependências
npm install

# 3. Compile
npm run compile

# 4. Empacote
npm run package

# 5. Instale no VS Code
code --install-extension shared-copilot-1.0.0.vsix
```

#### Via Código Fonte (Desenvolvimento)
```bash
# 1. Abra o projeto no VS Code
code shared-copilot

# 2. Instale dependências
npm install

# 3. Pressione F5 para abrir nova janela com extensão
```

## ⚙️ Configuração

Abra as configurações do VS Code (`Ctrl+,`) e busque por "Shared Copilot":

| Configuração | Padrão | Descrição |
|-------------|--------|-----------|
| `shared-copilot.enable` | `true` | Habilitar/desabilitar a extensão |
| `shared-copilot.ollamaUrl` | `http://localhost:11434` | URL da API Ollama |
| `shared-copilot.model` | `codellama` | Modelo para completar código |
| `shared-copilot.chatModel` | `codellama` | Modelo para chat |
| `shared-copilot.maxTokens` | `500` | Tokens máximos por resposta |
| `shared-copilot.temperature` | `0.2` | Temperatura (criatividade) |
| `shared-copilot.debounceTime` | `300` | Delay antes de sugerir (ms) |
| `shared-copilot.contextLines` | `50` | Linhas de contexto enviadas |
| `shared-copilot.enableAutoComplete` | `true` | Auto-completar automático |
| `shared-copilot.agentsApiUrl` | `http://localhost:8503` | URL da API de agentes (Homelab) |

### Exemplo de settings.json

```json
{
    "shared-copilot.enable": true,
   "shared-copilot.ollamaUrl": "http://${HOMELAB_HOST:-localhost}:11434",
    "shared-copilot.model": "deepseek-coder",
    "shared-copilot.chatModel": "llama2",
    "shared-copilot.maxTokens": 800,
    "shared-copilot.temperature": 0.3
}
```

## 🎯 Uso

### Autocompletar

1. Comece a digitar código normalmente
2. Após uma breve pausa, uma sugestão aparecerá em cinza (ghost text)
3. Pressione `Tab` para aceitar ou continue digitando para ignorar

### Chat

1. Clique no ícone Shared Copilot na barra lateral
2. Digite sua pergunta no campo de texto
3. A resposta será transmitida em tempo real

### Menu de Contexto

1. Selecione um trecho de código
2. Clique com botão direito
3. Escolha uma opção do submenu "Shared Copilot"

## 🏗️ Arquitetura

```
shared-copilot/
├── src/
│   ├── extension.ts           # Ponto de entrada
│   ├── ollamaClient.ts        # Cliente API Ollama
│   ├── homelabAgentClient.ts   # Cliente API Homelab Agent
│   ├── inlineCompletionProvider.ts  # Provider de sugestões
│   ├── chatViewProvider.ts    # Webview do chat
│   ├── statusBar.ts           # Status bar
│   └── codeActionProvider.ts  # Ações de código
├── resources/
│   └── icon.svg               # Ícone da extensão
├── package.json               # Manifesto da extensão
└── tsconfig.json             # Config TypeScript
```

## 🔧 Desenvolvimento

```bash
# Instalar dependências
npm install

# Compilar
npm run compile

# Watch mode
npm run watch

# Lint
npm run lint

# Empacotar
npm run package
```

## 📝 Modelos Recomendados

### Para Code Completion
- **codellama** - Meta's Code Llama, excelente para completar código
- **deepseek-coder** - Ótimo para várias linguagens
- **starcoder2** - StarCoder 2, treinado em código

### Para Chat
- **codellama:instruct** - Code Llama versão instruct
- **llama2** - Bom para explicações
- **mistral** - Rápido e eficiente

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## 🙏 Créditos

- [Ollama](https://ollama.com/) - Backend de IA local
- [VS Code Extension API](https://code.visualstudio.com/api)
- Inspirado pelo [GitHub Copilot](https://github.com/features/copilot)

---

**Shared Copilot** - Seu assistente de código com IA local 🚀
