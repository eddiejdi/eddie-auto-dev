# 💬 Interface Simples de Conversas

Uma **tela minimalista e responsiva** com um **textbox rolante** para visualizar em tempo real as conversas entre todos os agentes especializados.

## 🎯 Características

✅ **Interface Minimalista**
- Design clean e escuro
- Fácil de ler e navegar
- Sem complexidades desnecessárias

✅ **Textbox Rolante**
- Exibe conversas em tempo real
- Auto-scroll para o final
- Suporte para +50 mensagens por conversa

✅ **Filtros Básicos**
- Filtrar por agente (PythonAgent, JavaScriptAgent, etc)
- Limitar número de mensagens exibidas
- Auto-refresh opcional

✅ **Estatísticas em Tempo Real**
- Total de conversas
- Conversas ativas vs completadas
- Total de mensagens
- Agentes únicos

✅ **Suporte a Cores**
- Mensagens de info (azul)
- Mensagens de sucesso (verde)
- Mensagens de erro (vermelho)
- Mensagens de warning (amarelo)

## 🚀 Como Usar

### Opção 1: Via Script
```bash
bash ~/myClaude/start_simple_viewer.sh
### Opção 2: Direto com Streamlit
```bash
cd ~/myClaude
streamlit run specialized_agents/simple_conversation_viewer.py
### Opção 3: Via API REST
```bash
curl http://localhost:8503/interceptor/conversations/active
## 📍 Acessar

**Interface Web:**
https://heights-treasure-auto-phones.trycloudflare.com
**API REST:**
http://localhost:8503/interceptor/
## 🎮 Controles

| Controle | Descrição |
|----------|-----------|
| 🔄 **Atualizar** | Recarrega conversas imediatamente |
| 🔄 **Auto-refresh** | Atualiza a cada 3 segundos automaticamente |
| 📊 **Filtrar por Agente** | Mostra apenas conversas de um agente específico |
| 📝 **Últimas N mensagens** | Controla quantas mensagens são exibidas |

## 📊 Estatísticas Exibidas

📊 Conversas: Total de conversas capturadas
✅ Ativas: Conversas em progresso
🏁 Completadas: Conversas finalizadas
💬 Mensagens: Total de mensagens interceptadas
🤖 Agentes: Número de agentes diferentes que comunicaram
## 🔧 Estrutura de Uma Conversa

📦 CONVERSA: <conversation_id>
   Status: active/completed
   Fase: initiated/analyzing/planning/coding/testing/deployed
   Mensagens: <número>
   Criada: <timestamp>
## 💬 Formato de Mensagens

Cada mensagem exibida segue este formato:

[HH:MM:SS] <agent_name> | <action> | <content>
### Exemplo:
[14:23:45] PythonAgent      | analyze   | Analisando requisitos do projeto...
[14:23:50] JavaScriptAgent  | coding    | Criando componente React...
[14:24:10] TypeScriptAgent  | testing   | Executando testes unitários...
## 🎨 Cores das Mensagens

- 🔵 **Azul** - Informações
- 🟢 **Verde** - Sucesso
- 🔴 **Vermelho** - Erro
- 🟡 **Amarelo** - Aviso

## 🔄 Auto-Refresh

Quando ativado, a interface se atualiza automaticamente a cada **3 segundos**. Ideal para monitorar em tempo real as atividades dos agentes.

## 📱 Responsividade

A interface se adapta automaticamente a diferentes tamanhos de tela:
- 💻 Desktop (recomendado)
- 📱 Tablet
- 📱 Mobile

## 🐛 Troubleshooting

### Nenhuma conversa aparece?
1. Verifique se os agentes estão rodando
2. Ative o **auto-refresh** para ver atualizações em tempo real
3. Verifique o banco de dados SQLite em `specialized_agents/agent_rag/`

### Textbox não rola?
1. Verifique se está usando um navegador moderno (Chrome, Firefox, Edge)
2. Tente recarregar a página
3. Aumente a altura da área de conversas

### Performance lenta?
1. Reduza o número de mensagens exibidas (limite a 100-200)
2. Desative o auto-refresh temporariamente
3. Feche outras abas/aplicações

## 📋 Funcionalidades Futuras

- [ ] Busca avançada em conversas
- [ ] Exportação de conversas (JSON/PDF)
- [ ] Análise de sentimento
- [ ] Gráficos de atividade
- [ ] Alertas para erros
- [ ] Replay de conversas

## 📖 Documentação Relacionada

- [INTERCEPTOR_README.md](INTERCEPTOR_README.md) - Documentação completa do sistema
- [interceptor_cli.py](interceptor_cli.py) - Interface CLI com 25+ comandos
- [conversation_monitor.py](conversation_monitor.py) - Dashboard Streamlit completo

---

**Versão:** 1.0  
**Data:** Janeiro 2026  
**Status:** ✅ Funcional e Validado
