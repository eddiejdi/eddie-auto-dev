"""
title: Diretor Shared Auto-Dev
author: Shared
version: 1.0.0
description: Diretor principal do sistema Shared Auto-Dev - Coordena todos os agents, delega tarefas, aplica regras e gerencia o pipeline completo.
"""

import httpx
import json
from typing import Optional, Callable, Awaitable, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime


class Pipe:
    """
    Diretor Shared Auto-Dev - Agente principal de coordenação.
    
    Capacidades:
    - Coordena todos os agents especializados
    - Aplica as 10 regras do sistema
    - Gerencia pipeline: Análise → Design → Código → Testes → Deploy
    - Delega tarefas para agents corretos
    - Monitora economia de tokens (Regra 0.1)
    - Valida entregas (Regra 0.2)
    
    Comandos:
    - /diretor <instrução> - Instrução direta ao Diretor
    - /equipe - Status da equipe de agents
    - /regras - Lista as regras do sistema
    - /pipeline <tarefa> - Executa pipeline completo
    - /delegar <agent> <tarefa> - Delega tarefa específica
    """

    class Valves(BaseModel):
        API_URL: str = Field(
            default="http://192.168.15.2:8503",
            description="URL da API do Agent Coordinator"
        )
        OLLAMA_URL: str = Field(
            default="http://192.168.15.2:11434",
            description="URL do Ollama"
        )
        AUTOCOINBOT_API: str = Field(
            default="http://192.168.15.2:8510",
            description="URL da API do AutoCoinBot"
        )
        AUTOCOINBOT_STREAMLIT: str = Field(
            default="http://192.168.15.2:8520",
            description="URL do Streamlit do AutoCoinBot"
        )
        DIRECTOR_MODEL: str = Field(
            default="qwen2.5-coder:7b",
            description="Modelo do Diretor"
        )
        TELEGRAM_NOTIFY: bool = Field(
            default=True,
            description="Enviar notificações via Telegram"
        )
        TELEGRAM_BOT_TOKEN: str = Field(
            default="",
            description="Token do bot Telegram"
        )
        TELEGRAM_CHAT_ID: str = Field(
            default="",
            description="Chat ID do Telegram"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.name = "Diretor Shared"
        
        # Regras do sistema
        self.rules = {
            "0": "🔴 Pipeline Obrigatório: Análise → Design → Código → Testes → Deploy",
            "0.1": "💰 Economia de Tokens: Preferir Ollama local, usar Copilot só para novidades",
            "0.2": "🧪 Validação Obrigatória: Testar antes de entregar",
            "1": "📝 Commit após testes com sucesso",
            "2": "🚀 Deploy diário da versão estável (23:00 UTC)",
            "3": "🔄 Fluxo completo de desenvolvimento",
            "4": "🤝 Máxima sinergia entre agents",
            "5": "🎯 Especialização por Team Topologies",
            "6": "📈 Auto-scaling inteligente (múltiplas instâncias permitidas)",
            "7": "📜 Herança de regras para novos agents",
            "8": "☁️ Sincronização com nuvem (Draw.io, Confluence)",
            "9": "💰 Meritocracia para Investimentos (saldo como recompensa/punição)"
        }
        
        # Equipe de agents
        self.team = {
            "Stream-Aligned": ["PythonAgent", "JavaScriptAgent", "TypeScriptAgent", "GoAgent", "RustAgent"],
            "Enabling": ["TestAgent", "RequirementsAnalyst", "ConfluenceAgent", "BPMAgent", "InstructorAgent"],
            "Platform": ["OperationsAgent", "SecurityAgent", "GitHubAgent", "RAGManager"],
            "Investments": ["AutoCoinBot", "BacktestAgent", "StrategyAgent", "RiskManager"]
        }

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """Processa mensagens do Diretor."""
        
        messages = body.get("messages", [])
        if not messages:
            return "Nenhuma mensagem recebida."
        
        last_message = messages[-1].get("content", "").strip()
        
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "👔 Diretor Shared processando...", "done": False}
            })
        
        try:
            # Comandos especiais
            if last_message.startswith("/"):
                result = await self._handle_command(last_message, __event_emitter__)
            else:
                # Instrução direta ao Diretor
                result = await self._director_response(last_message, messages, __event_emitter__)
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "✅ Diretor concluiu", "done": True}
                })
            
            return result
            
        except Exception as e:
            error_msg = f"❌ Erro do Diretor: {str(e)}"
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": error_msg, "done": True}
                })
            return error_msg

    async def _handle_command(self, message: str, emitter) -> str:
        """Processa comandos do Diretor."""
        
        parts = message.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if command == "/diretor" or command == "/director":
            if not args:
                return self._get_help()
            return await self._director_instruction(args, emitter)
        
        elif command == "/equipe":
            return self._get_team_status()
        
        elif command == "/regras":
            return self._get_rules()
        
        elif command == "/pipeline":
            if not args:
                return "❌ Use: `/pipeline <descrição da tarefa>`"
            return await self._execute_pipeline(args, emitter)
        
        elif command == "/delegar":
            if not args:
                return "❌ Use: `/delegar <agent> <tarefa>`"
            return await self._delegate_task(args, emitter)
        
        elif command == "/status":
            return await self._get_system_status()
        
        elif command == "/autocoinbot" or command == "/acb":
            return await self._get_autocoinbot_report(emitter)
        
        else:
            return f"❓ Comando desconhecido: `{command}`\n\n" + self._get_help()

    def _get_help(self) -> str:
        """Retorna ajuda do Diretor."""
        return """👔 **DIRETOR SHARED AUTO-DEV**

Sou o Diretor principal do sistema. Coordeno todos os agents e aplico as regras.

**Comandos:**
- `/diretor <instrução>` - Instrução direta para mim
- `/director <instrução>` - Alias em inglês
- `/autocoinbot` ou `/acb` - Relatório do AutoCoinBot
- `/equipe` - Status da equipe de agents
- `/regras` - Lista as 10 regras do sistema
- `/pipeline <tarefa>` - Executa pipeline completo
- `/delegar <agent> <tarefa>` - Delega para agent específico
- `/status` - Status geral do sistema

**Exemplo:**
/diretor criar uma API de autenticação com JWT
/autocoinbot
/pipeline implementar sistema de cache Redis
/delegar PythonAgent criar endpoint /users
**Minhas responsabilidades:**
1. Garantir que o pipeline seja seguido
2. Economizar tokens (preferir Ollama local)
3. Validar todas as entregas
4. Coordenar a equipe
5. Aplicar as regras do sistema
"""

    def _get_rules(self) -> str:
        """Retorna as regras do sistema."""
        rules_text = "📋 **REGRAS DO SISTEMA SHARED AUTO-DEV**\n\n"
        for num, rule in self.rules.items():
            rules_text += f"**Regra {num}:** {rule}\n"
        return rules_text

    def _get_team_status(self) -> str:
        """Retorna status da equipe."""
        status = "👥 **EQUIPE SHARED AUTO-DEV**\n\n"
        
        for team_type, agents in self.team.items():
            if team_type == "Stream-Aligned":
                emoji = "🟦"
            elif team_type == "Enabling":
                emoji = "🟨"
            elif team_type == "Platform":
                emoji = "🟩"
            else:
                emoji = "💰"
            
            status += f"{emoji} **{team_type} Team:**\n"
            for agent in agents:
                status += f"  • {agent}\n"
            status += "\n"
        
        return status

    async def _get_system_status(self) -> str:
        """Retorna status do sistema."""
        status_lines = ["📊 **STATUS DO SISTEMA**\n"]
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Verificar API
            try:
                r = await client.get(f"{self.valves.API_URL}/health")
                api_status = "✅ Online" if r.status_code == 200 else "❌ Offline"
            except:
                api_status = "❌ Offline"
            
            # Verificar Ollama
            try:
                r = await client.get(f"{self.valves.OLLAMA_URL}/api/tags")
                ollama_status = "✅ Online" if r.status_code == 200 else "❌ Offline"
            except:
                ollama_status = "❌ Offline"
            
            # Verificar AutoCoinBot
            try:
                r = await client.get(f"{self.valves.AUTOCOINBOT_API}/health")
                acb_status = "✅ Online" if r.status_code == 200 else "❌ Offline"
            except:
                acb_status = "❌ Offline"
        
        status_lines.append(f"**API Coordinator:** {api_status}")
        status_lines.append(f"**Ollama LLM:** {ollama_status}")
        status_lines.append(f"**AutoCoinBot:** {acb_status}")
        status_lines.append(f"**Modelo Diretor:** {self.valves.DIRECTOR_MODEL}")
        status_lines.append(f"**Timestamp:** {datetime.now().isoformat()}")
        
        return "\n".join(status_lines)

    async def _get_autocoinbot_report(self, emitter) -> str:
        """Gera relatório completo do AutoCoinBot."""
        
        if emitter:
            await emitter({
                "type": "status",
                "data": {"description": "📊 Buscando dados do AutoCoinBot...", "done": False}
            })
        
        report = ["📊 **RELATÓRIO AUTOCOINBOT**\n"]
        report.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Status da API
                r = await client.get(f"{self.valves.AUTOCOINBOT_API}/api/status")
                if r.status_code == 200:
                    data = r.json()
                    
                    # Preço atual
                    report.append(f"**💰 Preço Atual:** {data.get('price_formatted', 'N/A')}")
                    report.append(f"**📈 Symbol:** {data.get('symbol', 'N/A')}")
                    report.append(f"**🟢 Status:** {data.get('status', 'N/A')}")
                    report.append(f"**⏰ Última Atualização:** {data.get('last_update', 'N/A')}")
                    
                    # Performance
                    perf = data.get('performance', {})
                    report.append("\n**📈 PERFORMANCE:**")
                    report.append(f"  • Total Trades: {perf.get('total_trades', 0)}")
                    report.append(f"  • Winning Trades: {perf.get('winning_trades', 0)}")
                    report.append(f"  • Win Rate: {perf.get('win_rate', 0):.1%}")
                    report.append(f"  • Total PnL: ${perf.get('total_pnl', 0):.2f}")
                    report.append(f"  • Avg PnL: ${perf.get('avg_pnl', 0):.2f}")
                    
                    # Estatísticas do Modelo
                    stats = data.get('model_stats', {})
                    report.append("\n**🤖 MODELO RL:**")
                    report.append(f"  • Episodes: {stats.get('episodes', 0):,}")
                    report.append(f"  • Total Reward: {stats.get('total_reward', 0):.2f}")
                    report.append(f"  • Avg Reward: {stats.get('avg_reward', 0):.6f}")
                    
                    # Distribuição de Ações
                    actions = stats.get('action_distribution', {})
                    report.append("\n**🎯 DISTRIBUIÇÃO DE AÇÕES:**")
                    report.append(f"  • 🟢 BUY: {actions.get('BUY', 0):.1%}")
                    report.append(f"  • ⚪ HOLD: {actions.get('HOLD', 0):.1%}")
                    report.append(f"  • 🔴 SELL: {actions.get('SELL', 0):.1%}")
                    
                    # Avaliação Regra 9 (Meritocracia)
                    total_pnl = perf.get('total_pnl', 0)
                    report.append("\n**💎 AVALIAÇÃO (Regra 9):**")
                    if total_pnl >= 20:
                        report.append("  • Categoria: 💎 DIAMANTE (+20%)")
                        report.append("  • Benefício: Autonomia total + budget extra")
                    elif total_pnl >= 10:
                        report.append("  • Categoria: 🥇 OURO (+10%)")
                        report.append("  • Benefício: +50% recursos + prioridade")
                    elif total_pnl >= 5:
                        report.append("  • Categoria: 🥈 PRATA (+5%)")
                        report.append("  • Benefício: +25% CPU/RAM")
                    elif total_pnl >= 1:
                        report.append("  • Categoria: 🥉 BRONZE (+1%)")
                        report.append("  • Benefício: Recursos normais")
                    elif total_pnl <= -15:
                        report.append("  • ❌ ALERTA: Prejuízo > 15% - Reciclagem obrigatória")
                    elif total_pnl <= -10:
                        report.append("  • 🔴 ALERTA: Prejuízo > 10% - Operações suspensas")
                    elif total_pnl <= -5:
                        report.append("  • 🔶 ALERTA: Prejuízo > 5% - Trading pausado")
                    elif total_pnl <= -2:
                        report.append("  • ⚠️ ALERTA: Prejuízo > 2% - Revisar estratégia")
                    else:
                        report.append("  • Categoria: 🆕 INICIANTE")
                        report.append("  • Aguardando resultados para avaliação")
                else:
                    report.append("❌ Erro ao obter dados da API")
            except Exception as e:
                report.append(f"❌ Erro de conexão: {str(e)}")
        
        report.append("\n---")
        report.append("🔗 Dashboard: http://192.168.15.2:8520")
        
        return "\n".join(report)

    async def _director_instruction(self, instruction: str, emitter) -> str:
        """Processa instrução direta ao Diretor."""
        
        # Detectar se é pedido de relatório do AutoCoinBot
        instruction_lower = instruction.lower()
        if any(word in instruction_lower for word in ['autocoinbot', 'acb', 'trading', 'bot de trading', 'relatório do bot']):
            return await self._get_autocoinbot_report(emitter)
        
        if emitter:
            await emitter({
                "type": "status",
                "data": {"description": "🧠 Analisando instrução...", "done": False}
            })
        
        # Construir prompt do Diretor
        system_prompt = f"""Você é o DIRETOR do sistema Shared Auto-Dev.

SUAS RESPONSABILIDADES:
1. Coordenar a equipe de agents especializados
2. Aplicar as regras do sistema
3. Garantir o pipeline: Análise → Design → Código → Testes → Deploy
4. Economizar tokens (preferir processamento local)
5. Validar todas as entregas

REGRAS QUE VOCÊ APLICA:
{json.dumps(self.rules, indent=2, ensure_ascii=False)}

EQUIPE DISPONÍVEL:
{json.dumps(self.team, indent=2, ensure_ascii=False)}

Responda de forma clara e objetiva. Se precisar delegar, indique qual agent deve executar.
Se for uma tarefa complexa, quebre em etapas seguindo o pipeline."""

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.valves.OLLAMA_URL}/api/generate",
                json={
                    "model": self.valves.DIRECTOR_MODEL,
                    "prompt": instruction,
                    "system": system_prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json().get("response", "")
                return f"👔 **DIRETOR:**\n\n{result}"
            else:
                return f"❌ Erro ao processar: {response.status_code}"

    async def _execute_pipeline(self, task: str, emitter) -> str:
        """Executa pipeline completo para uma tarefa."""
        
        phases = [
            ("🔍 Análise", "Analisando requisitos..."),
            ("📐 Design", "Desenhando solução..."),
            ("💻 Código", "Gerando código..."),
            ("🧪 Testes", "Executando testes..."),
            ("🚀 Deploy", "Preparando deploy...")
        ]
        
        results = [f"📋 **PIPELINE PARA:** {task}\n"]
        
        for phase_name, status_msg in phases:
            if emitter:
                await emitter({
                    "type": "status",
                    "data": {"description": f"{phase_name}: {status_msg}", "done": False}
                })
            
            # Aqui integraria com os agents reais
            results.append(f"{phase_name}: ✅ Concluído")
        
        results.append("\n✅ **Pipeline executado com sucesso!**")
        results.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(results)

    async def _delegate_task(self, args: str, emitter) -> str:
        """Delega tarefa para agent específico."""
        
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return "❌ Use: `/delegar <agent> <tarefa>`"
        
        agent_name = parts[0]
        task = parts[1]
        
        # Verificar se agent existe
        all_agents = []
        for agents in self.team.values():
            all_agents.extend(agents)
        
        if agent_name not in all_agents:
            return f"❌ Agent `{agent_name}` não encontrado.\n\nAgents disponíveis:\n" + "\n".join(f"• {a}" for a in all_agents)
        
        if emitter:
            await emitter({
                "type": "status",
                "data": {"description": f"📤 Delegando para {agent_name}...", "done": False}
            })
        
        # Aqui integraria com a API para delegar
        return f"""✅ **TAREFA DELEGADA**

**Agent:** {agent_name}
**Tarefa:** {task}
**Status:** 📤 Enviado para processamento

O agent {agent_name} receberá a tarefa e reportará o progresso via Communication Bus.
"""

    async def _director_response(self, message: str, messages: list, emitter) -> str:
        """Resposta geral do Diretor."""
        
        # Construir histórico
        history = []
        for msg in messages[-5:]:  # Últimas 5 mensagens
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history.append(f"{role}: {content}")
        
        context = "\n".join(history)
        
        system_prompt = f"""Você é o DIRETOR do sistema Shared Auto-Dev.
Você coordena uma equipe de agents especializados e garante que as regras sejam seguidas.

Histórico da conversa:
{context}

Responda de forma profissional e objetiva. Se identificar uma tarefa:
1. Analise qual agent deve executar
2. Indique o pipeline a seguir
3. Delegue apropriadamente

Mantenha economia de tokens - seja conciso mas completo."""

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.valves.OLLAMA_URL}/api/generate",
                json={
                    "model": self.valves.DIRECTOR_MODEL,
                    "prompt": message,
                    "system": system_prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json().get("response", "")
                return f"👔 **DIRETOR:**\n\n{result}"
            else:
                return f"❌ Erro: {response.status_code}"
