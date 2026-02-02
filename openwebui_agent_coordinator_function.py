"""
title: Agent Coordinator
author: Eddie
version: 2.0.0
description: Integra Open WebUI com o Agent Coordinator - Análise de requisitos, geração de código, execução e RAG.
"""

import httpx
import json
import uuid
from typing import Optional, Callable, Awaitable, Dict
from pydantic import BaseModel, Field


class Pipe:
    """
    Agent Coordinator Pipe - Sistema de desenvolvimento com análise de requisitos.

    Fluxo:
    1. /projeto <descrição> - Inicia análise de requisitos
    2. Agent faz perguntas para esclarecer
    3. Usuário responde
    4. Quando completo, gera código
    """

    class Valves(BaseModel):
        COORDINATOR_URL: str = Field(
            default="http://192.168.15.2:8503",
            description="URL da API do Agent Coordinator",
        )
        OLLAMA_URL: str = Field(
            default="http://192.168.15.2:11434", description="URL do Ollama"
        )
        ANALYST_MODEL: str = Field(
            default="qwen2.5-coder:7b", description="Modelo para análise de requisitos"
        )
        ENABLE_CODE_EXECUTION: bool = Field(
            default=True, description="Permitir execução de código"
        )
        ENABLE_RAG: bool = Field(default=True, description="Habilitar busca RAG")

    def __init__(self):
        self.valves = self.Valves()
        self.name = "Agent Coordinator"
        # Armazena sessões de projetos em análise
        self.project_sessions: Dict[str, dict] = {}

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """
        Processa mensagens e roteia para o Agent Coordinator.
        """

        messages = body.get("messages", [])
        if not messages:
            return "Nenhuma mensagem recebida."

        last_message = messages[-1].get("content", "").strip()
        user_id = __user__.get("id", "default") if __user__ else "default"

        # Emitir status
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "🤖 Agent Coordinator processando...",
                        "done": False,
                    },
                }
            )

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Verificar se usuário tem projeto em análise
                session_key = f"{user_id}_project"

                # Comandos especiais
                if last_message.startswith("/"):
                    result = await self._handle_command(
                        client, last_message, user_id, messages, __event_emitter__
                    )

                # Se tem sessão ativa de projeto, continuar análise
                elif session_key in self.project_sessions:
                    result = await self._continue_analysis(
                        client, last_message, user_id, messages, __event_emitter__
                    )

                # Mensagem normal
                else:
                    result = await self._smart_response(
                        client, last_message, messages, __event_emitter__
                    )

                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {"description": "✅ Concluído", "done": True},
                        }
                    )

                return result

        except Exception as e:
            error_msg = f"❌ Erro ao conectar com Agent Coordinator: {str(e)}"
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": error_msg, "done": True}}
                )
            return error_msg

    async def _handle_command(
        self,
        client: httpx.AsyncClient,
        message: str,
        user_id: str,
        messages: list,
        emitter: Optional[Callable],
    ) -> str:
        """Processa comandos especiais."""

        parts = message.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/projeto":
            if not args:
                return """📋 **Iniciar Novo Projeto**

Use: `/projeto <descrição do projeto>`

**Exemplo:**
`/projeto criar uma API REST para gerenciar tarefas com autenticação JWT`

O Agent Especializado irá:
1. 🔍 Analisar sua descrição
2. ❓ Fazer perguntas para esclarecer requisitos
3. 📝 Documentar os requisitos
4. 🔧 Gerar o código quando estiver completo
"""
            return await self._start_project_analysis(client, args, user_id, emitter)

        elif command == "/gerar":
            return await self._generate_from_requirements(client, user_id, emitter)

        elif command == "/cancelar":
            session_key = f"{user_id}_project"
            if session_key in self.project_sessions:
                del self.project_sessions[session_key]
                return "🚫 Análise de projeto cancelada."
            return "Nenhum projeto em análise."

        elif command == "/requisitos":
            return await self._show_requirements(user_id)

        elif command == "/agents":
            return await self._list_agents(client)

        elif command == "/status":
            return await self._get_status(client)

        elif command == "/exec":
            if not args:
                return "Uso: `/exec <código>`\nExemplo: `/exec print('Hello World')`"
            return await self._execute_code(client, args)

        elif command == "/rag":
            if not args:
                return "Uso: `/rag <query>`\nExemplo: `/rag como configurar docker`"
            return await self._search_rag(client, args)

        elif command == "/bug" or command == "/reportar":
            if not args:
                return """🐛 **Reportar Bug / Problema**

Use: `/bug <descrição do problema>`

**Exemplo:**
`/bug o sistema está lento ao carregar dashboards`

O Agent de Operações irá:
1. 🔍 Analisar o problema reportado
2. 🔧 Verificar logs e status dos serviços
3. 💡 Sugerir soluções ou escalar se necessário
"""
            return await self._report_bug(client, args, user_id, emitter)

        elif command == "/help":
            return self._get_help()

        else:
            return f"Comando desconhecido: `{command}`\n\n{self._get_help()}"

    async def _start_project_analysis(
        self,
        client: httpx.AsyncClient,
        description: str,
        user_id: str,
        emitter: Optional[Callable],
    ) -> str:
        """Inicia análise de requisitos para um novo projeto."""

        session_key = f"{user_id}_project"

        if emitter:
            await emitter(
                {
                    "type": "status",
                    "data": {"description": "🔍 Analisando projeto...", "done": False},
                }
            )

        # Criar sessão do projeto
        self.project_sessions[session_key] = {
            "id": str(uuid.uuid4())[:8],
            "description": description,
            "requirements": [],
            "clarifications": [],
            "language": None,
            "phase": "analysis",
            "questions_asked": 0,
        }

        # Usar LLM para gerar perguntas de esclarecimento
        analysis_prompt = f"""Você é um Analista de Requisitos especializado. 
O usuário quer criar o seguinte projeto:

"{description}"

Analise esta descrição e faça 3-5 perguntas ESSENCIAIS para esclarecer os requisitos.
Foque em:
1. Funcionalidades principais
2. Tecnologias/linguagem preferida
3. Integrações necessárias
4. Requisitos de segurança/autenticação
5. Expectativas de escala/performance

Formato da resposta:
- Liste as perguntas numeradas
- Seja específico e direto
- Perguntas que ajudem a definir o escopo"""

        try:
            response = await client.post(
                f"{self.valves.OLLAMA_URL}/api/generate",
                json={
                    "model": self.valves.ANALYST_MODEL,
                    "prompt": analysis_prompt,
                    "stream": False,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                questions = data.get("response", "")

                self.project_sessions[session_key]["pending_questions"] = questions

                return f"""🚀 **Novo Projeto Iniciado**

**Descrição:** {description}

---

📋 **Análise de Requisitos**

O Agent Especializado precisa de algumas informações para garantir que o projeto atenda suas necessidades:

{questions}

---

💡 **Responda as perguntas acima** para continuar.
Use `/cancelar` para cancelar ou `/gerar` quando estiver satisfeito com os requisitos.
"""
            else:
                return f"Erro ao iniciar análise: {response.status_code}"

        except Exception as e:
            return f"❌ Erro na análise: {str(e)}"

    async def _continue_analysis(
        self,
        client: httpx.AsyncClient,
        user_response: str,
        user_id: str,
        messages: list,
        emitter: Optional[Callable],
    ) -> str:
        """Continua a análise de requisitos com a resposta do usuário."""

        session_key = f"{user_id}_project"
        session = self.project_sessions[session_key]

        if emitter:
            await emitter(
                {
                    "type": "status",
                    "data": {
                        "description": "🔄 Processando suas respostas...",
                        "done": False,
                    },
                }
            )

        # Salvar resposta do usuário
        session["clarifications"].append(
            {"question": session.get("pending_questions", ""), "answer": user_response}
        )
        session["questions_asked"] += 1

        # Construir contexto da conversa
        context = f"""Projeto: {session["description"]}

Esclarecimentos anteriores:
"""
        for i, c in enumerate(session["clarifications"], 1):
            context += (
                f"\nRodada {i}:\nPerguntas: {c['question']}\nRespostas: {c['answer']}\n"
            )

        # Decidir se precisa mais perguntas ou está pronto
        decision_prompt = f"""Você é um Analista de Requisitos.

{context}

Com base nas informações coletadas, decida:

1. Se precisar de MAIS esclarecimentos (máximo 2 rodadas adicionais), faça 2-3 perguntas específicas.

2. Se tiver informações SUFICIENTES, responda com:
"REQUISITOS_COMPLETOS"
Seguido de um resumo estruturado dos requisitos em formato:
- Linguagem: [detectada ou sugerida]
- Funcionalidades:
  - [lista]
- Tecnologias:
  - [lista]
- Requisitos não-funcionais:
  - [lista]

Lembre-se: seja prático, não faça perguntas desnecessárias."""

        try:
            response = await client.post(
                f"{self.valves.OLLAMA_URL}/api/generate",
                json={
                    "model": self.valves.ANALYST_MODEL,
                    "prompt": decision_prompt,
                    "stream": False,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                llm_response = data.get("response", "")

                # Verificar se está completo
                if "REQUISITOS_COMPLETOS" in llm_response:
                    # Extrair requisitos
                    requirements_text = llm_response.replace(
                        "REQUISITOS_COMPLETOS", ""
                    ).strip()
                    session["requirements_summary"] = requirements_text
                    session["phase"] = "ready"

                    # Detectar linguagem
                    lang_keywords = {
                        "python": ["python", "django", "flask", "fastapi"],
                        "javascript": ["javascript", "node", "express", "react"],
                        "typescript": ["typescript", "angular", "nestjs"],
                        "go": ["go", "golang", "gin"],
                        "rust": ["rust", "actix", "rocket"],
                    }

                    for lang, keywords in lang_keywords.items():
                        if any(kw in requirements_text.lower() for kw in keywords):
                            session["language"] = lang
                            break

                    if not session["language"]:
                        session["language"] = "python"  # default

                    return f"""✅ **Análise de Requisitos Completa!**

{requirements_text}

---

🎯 **Linguagem detectada:** {session["language"]}

**Próximos passos:**
- Use `/gerar` para gerar o código do projeto
- Use `/requisitos` para ver o resumo dos requisitos
- Use `/cancelar` para começar outro projeto
"""
                else:
                    # Precisa mais perguntas
                    session["pending_questions"] = llm_response

                    return f"""📝 **Obrigado pelas informações!**

Preciso de mais alguns esclarecimentos:

{llm_response}

---

💡 Responda acima ou use `/gerar` se já tiver informações suficientes.
"""
            else:
                return f"Erro ao processar: {response.status_code}"

        except Exception as e:
            return f"❌ Erro: {str(e)}"

    async def _generate_from_requirements(
        self, client: httpx.AsyncClient, user_id: str, emitter: Optional[Callable]
    ) -> str:
        """Gera código baseado nos requisitos coletados."""

        session_key = f"{user_id}_project"

        if session_key not in self.project_sessions:
            return (
                "❌ Nenhum projeto em análise. Use `/projeto <descrição>` para iniciar."
            )

        session = self.project_sessions[session_key]

        if emitter:
            await emitter(
                {
                    "type": "status",
                    "data": {"description": "🔧 Gerando código...", "done": False},
                }
            )

        # Construir prompt detalhado para geração
        context = f"""Projeto: {session["description"]}

Requisitos coletados:
{session.get("requirements_summary", "Não especificados")}

Esclarecimentos do usuário:
"""
        for c in session["clarifications"]:
            context += f"- {c['answer']}\n"

        language = session.get("language", "python")

        try:
            # Tentar usar o Agent Coordinator primeiro
            response = await client.post(
                f"{self.valves.COORDINATOR_URL}/code/generate",
                json={
                    "language": language,
                    "description": context,
                    "requirements": session.get("requirements", []),
                },
                timeout=120.0,
            )

            if response.status_code == 200:
                data = response.json()
                code = data.get("code", "")

                if code:
                    # Limpar sessão
                    del self.project_sessions[session_key]

                    return f"""🎉 **Projeto Gerado com Sucesso!**

**Linguagem:** {language}

```{language}
{code}
```

---

📁 **Próximos passos:**
- Use `/exec <código>` para testar partes do código (Python)
- Copie o código para seu projeto
- Use `/projeto` para iniciar outro projeto

💡 Se precisar de ajustes, descreva o que precisa mudar!
"""
                else:
                    return "⚠️ Código gerado está vazio. Tente novamente com mais detalhes."
            else:
                # Fallback para Ollama direto
                return await self._generate_with_ollama(client, context, language)

        except Exception as e:
            return f"❌ Erro ao gerar código: {str(e)}"

    async def _generate_with_ollama(
        self, client: httpx.AsyncClient, context: str, language: str
    ) -> str:
        """Fallback: gera código diretamente com Ollama."""

        prompt = f"""Você é um desenvolvedor expert em {language}.

Gere código completo e funcional para:

{context}

Requisitos:
- Código limpo e bem documentado
- Seguir boas práticas de {language}
- Incluir comentários explicativos
- Código pronto para produção

Responda APENAS com o código, sem explicações adicionais."""

        try:
            response = await client.post(
                f"{self.valves.OLLAMA_URL}/api/generate",
                json={
                    "model": self.valves.ANALYST_MODEL,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=120.0,
            )

            if response.status_code == 200:
                data = response.json()
                code = data.get("response", "")

                return f"""🔧 **Código Gerado ({language}):**

```{language}
{code}
```
"""
            return f"Erro ao gerar: {response.status_code}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"

    async def _show_requirements(self, user_id: str) -> str:
        """Mostra requisitos do projeto atual."""

        session_key = f"{user_id}_project"

        if session_key not in self.project_sessions:
            return "❌ Nenhum projeto em análise."

        session = self.project_sessions[session_key]

        result = f"""📋 **Requisitos do Projeto**

**ID:** {session["id"]}
**Descrição:** {session["description"]}
**Fase:** {session["phase"]}
**Linguagem:** {session.get("language", "A definir")}

**Esclarecimentos coletados:**
"""
        for i, c in enumerate(session["clarifications"], 1):
            result += f"\n**Rodada {i}:**\n{c['answer'][:200]}...\n"

        if session.get("requirements_summary"):
            result += f"\n**Resumo dos Requisitos:**\n{session['requirements_summary']}"

        return result

    async def _smart_response(
        self,
        client: httpx.AsyncClient,
        message: str,
        history: list,
        emitter: Optional[Callable],
    ) -> str:
        """Resposta inteligente para mensagens sem comando."""

        # Detectar intenção
        project_keywords = [
            "criar",
            "desenvolver",
            "fazer",
            "construir",
            "implementar",
            "projeto",
            "aplicação",
            "app",
            "sistema",
        ]

        if any(kw in message.lower() for kw in project_keywords):
            return f"""🤔 Parece que você quer iniciar um projeto!

Use o comando `/projeto` seguido da descrição:

```
/projeto {message}
```

Isso iniciará a **análise de requisitos** onde o Agent Especializado fará perguntas para entender melhor suas necessidades antes de gerar o código.

---

Ou use `/help` para ver todos os comandos disponíveis.
"""

        # Buscar no RAG
        if self.valves.ENABLE_RAG:
            try:
                rag_response = await client.post(
                    f"{self.valves.COORDINATOR_URL}/rag/search",
                    json={"query": message, "top_k": 3},
                )
                if rag_response.status_code == 200:
                    rag_data = rag_response.json()
                    if rag_data.get("results"):
                        result = "📚 **Encontrei no RAG:**\n\n"
                        for i, doc in enumerate(rag_data["results"][:2], 1):
                            content = doc.get("content", "")[:400]
                            result += f"{i}. {content}...\n\n"
                        return result
            except:
                pass

        return """Não entendi completamente. Aqui estão algumas opções:

📋 **Para iniciar um projeto:**
`/projeto <descrição do que você quer criar>`

🔍 **Para buscar documentação:**
`/rag <sua pergunta>`

⚡ **Para executar código:**
`/exec <código python>`

📖 **Para ver todos os comandos:**
`/help`
"""

    async def _list_agents(self, client: httpx.AsyncClient) -> str:
        """Lista agentes disponíveis."""
        try:
            response = await client.get(f"{self.valves.COORDINATOR_URL}/agents")
            if response.status_code == 200:
                agents = response.json()
                result = "🤖 **Agentes Disponíveis:**\n\n"
                for agent in agents:
                    name = agent.get("name", "Unknown")
                    lang = agent.get("language", "")
                    status = "✅" if agent.get("is_active") else "⚪"
                    caps = ", ".join(agent.get("capabilities", [])[:3])
                    result += (
                        f"{status} **{name}** ({lang})\n   Capacidades: {caps}\n\n"
                    )
                return result
            return f"Erro ao listar agentes: {response.status_code}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"

    async def _get_status(self, client: httpx.AsyncClient) -> str:
        """Obtém status do sistema."""
        try:
            response = await client.get(f"{self.valves.COORDINATOR_URL}/status")
            if response.status_code == 200:
                data = response.json()
                result = "📊 **Status do Agent Coordinator:**\n\n"
                result += f"- **Agentes ativos:** {data.get('active_agents', 0)}\n"
                result += (
                    f"- **Docker:** {'✅' if data.get('docker_available') else '❌'}\n"
                )
                result += (
                    f"- **GitHub:** {'✅' if data.get('github_configured') else '❌'}\n"
                )
                result += f"- **RAG:** {'✅' if data.get('rag_available') else '❌'}\n"

                llm = data.get("llm_config", {})
                result += (
                    f"- **LLM:** {llm.get('model', 'N/A')} @ {llm.get('host', 'N/A')}\n"
                )

                return result
            return f"Erro ao obter status: {response.status_code}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"

    async def _execute_code(self, client: httpx.AsyncClient, code: str) -> str:
        """Executa código Python."""
        if not self.valves.ENABLE_CODE_EXECUTION:
            return "⚠️ Execução de código está desabilitada."

        try:
            response = await client.post(
                f"{self.valves.COORDINATOR_URL}/code/execute",
                json={"language": "python", "code": code},
            )

            if response.status_code == 200:
                data = response.json()
                output = data.get("output", "")
                error = data.get("error", "")
                exit_code = data.get("exit_code", 0)

                result = "⚡ **Execução:**\n\n"
                if output:
                    result += f"**Output:**\n```\n{output}\n```\n"
                if error:
                    result += f"**Erro:**\n```\n{error}\n```\n"
                result += f"\n**Exit code:** {exit_code}"
                return result
            return f"Erro ao executar: {response.status_code}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"

    async def _search_rag(self, client: httpx.AsyncClient, query: str) -> str:
        """Busca no sistema RAG."""
        try:
            response = await client.post(
                f"{self.valves.COORDINATOR_URL}/rag/search",
                json={"query": query, "top_k": 5},
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                if not results:
                    return "📚 Nenhum resultado encontrado no RAG."

                result = f"📚 **Resultados RAG para:** {query}\n\n"
                for i, doc in enumerate(results, 1):
                    content = doc.get("content", "")[:300]
                    source = doc.get("metadata", {}).get("source", "Unknown")
                    result += f"**{i}. {source}**\n{content}...\n\n"

                return result
            return f"Erro na busca RAG: {response.status_code}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"

    async def _report_bug(
        self,
        client: httpx.AsyncClient,
        description: str,
        user_id: str,
        emitter: Optional[Callable],
    ) -> str:
        """Reporta bug e aciona Agent de Operações para troubleshooting."""

        if emitter:
            await emitter(
                {
                    "type": "status",
                    "data": {
                        "description": "🔍 Agent de Operações analisando...",
                        "done": False,
                    },
                }
            )

        # Coletar informações do sistema
        system_info = {}

        try:
            # Status do coordinator
            status_resp = await client.get(f"{self.valves.COORDINATOR_URL}/status")
            if status_resp.status_code == 200:
                system_info["coordinator"] = status_resp.json()
        except:
            system_info["coordinator"] = {"error": "Não disponível"}

        try:
            # Lista de containers Docker
            docker_resp = await client.get(
                f"{self.valves.COORDINATOR_URL}/docker/containers"
            )
            if docker_resp.status_code == 200:
                system_info["containers"] = docker_resp.json()
        except:
            system_info["containers"] = {"error": "Não disponível"}

        try:
            # Health check
            health_resp = await client.get(f"{self.valves.COORDINATOR_URL}/health")
            if health_resp.status_code == 200:
                system_info["health"] = health_resp.json()
        except:
            system_info["health"] = {"error": "Não disponível"}

        # Criar prompt para o Agent de Operações
        ops_prompt = f"""Você é um Agent de Operações especializado em troubleshooting de sistemas.

**Bug Reportado pelo Usuário:**
"{description}"

**Informações do Sistema:**
- Status Coordinator: {json.dumps(system_info.get("coordinator", {}), indent=2)}
- Containers Docker: {json.dumps(system_info.get("containers", {}), indent=2)[:500]}
- Health Check: {json.dumps(system_info.get("health", {}), indent=2)}

**Sua tarefa:**
1. Analise o problema reportado
2. Correlacione com as informações do sistema
3. Identifique possíveis causas
4. Sugira soluções passo a passo
5. Se necessário, indique comandos de diagnóstico

Formato da resposta:
- 🔍 **Análise:** [sua análise]
- 🎯 **Possíveis Causas:** [lista]
- 🔧 **Soluções Sugeridas:** [passos]
- 📋 **Comandos de Diagnóstico:** [se aplicável]
- ⚠️ **Escalar para:** [se precisar de intervenção humana]"""

        try:
            response = await client.post(
                f"{self.valves.OLLAMA_URL}/api/generate",
                json={
                    "model": self.valves.ANALYST_MODEL,
                    "prompt": ops_prompt,
                    "stream": False,
                },
                timeout=90.0,
            )

            if response.status_code == 200:
                data = response.json()
                analysis = data.get("response", "Não foi possível analisar.")

                # Criar ticket ID
                ticket_id = f"BUG-{str(uuid.uuid4())[:8].upper()}"

                return f"""🐛 **Bug Reportado - {ticket_id}**

**Problema:** {description}

---

🤖 **Agent de Operações - Análise**

{analysis}

---

📊 **Status do Sistema no momento do report:**
- **Coordinator:** {"✅ Online" if system_info.get("health", {}).get("status") == "healthy" else "⚠️ Verificar"}
- **Docker:** {"✅" if system_info.get("coordinator", {}).get("docker_available") else "❌"}
- **Containers ativos:** {len(system_info.get("containers", [])) if isinstance(system_info.get("containers"), list) else "N/A"}

---

💡 **Próximos passos:**
- Se o problema persistir, execute os comandos de diagnóstico sugeridos
- Use `/status` para verificar o status atual
- Use `/bug <nova descrição>` para reportar mais detalhes
"""
            else:
                return f"❌ Erro ao analisar bug: {response.status_code}"

        except Exception as e:
            return f"""🐛 **Bug Reportado**

**Problema:** {description}

⚠️ **Agent de Operações indisponível:** {str(e)}

**Ações manuais sugeridas:**
1. Verifique se o Ollama está rodando: `curl http://192.168.15.2:11434/api/tags`
2. Verifique os logs: `docker logs open-webui`
3. Status do sistema: `systemctl status ipv6-proxy`

Use `/status` para mais informações.
"""

    def _get_help(self) -> str:
        """Retorna ajuda dos comandos."""
        return """📖 **Agent Coordinator - Comandos**

**🚀 Desenvolvimento de Projetos:**
- `/projeto <descrição>` - Inicia análise de requisitos
  O Agent Especializado fará perguntas para entender o projeto
  
- `/gerar` - Gera código após análise completa
- `/requisitos` - Mostra requisitos coletados
- `/cancelar` - Cancela projeto em análise

**🐛 Suporte e Operações:**
- `/bug <descrição>` - Reporta problema ao Agent de Operações
- `/reportar <descrição>` - Mesmo que /bug
  Exemplo: `/bug sistema lento ao carregar página`

**⚡ Execução:**
- `/exec <código>` - Executa código Python
  Exemplo: `/exec print("Hello World")`

**🔍 Busca:**
- `/rag <query>` - Busca documentação no RAG
  Exemplo: `/rag como usar docker compose`

**📊 Sistema:**
- `/agents` - Lista agentes disponíveis
- `/status` - Status do sistema
- `/help` - Esta ajuda

---

**💡 Fluxos Disponíveis:**

**Desenvolvimento:**
1. `/projeto <sua ideia>` → Responda perguntas → `/gerar`

**Suporte:**
1. `/bug <problema>` → Agent analisa → Soluções sugeridas
"""
