#!/usr/bin/env python3
"""
Agent Chat - Interface de Chat com Agentes Especializados
Similar ao Copilot, mas atendido pelos agentes do sistema.
"""

import streamlit as st
import requests
import json
import subprocess
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import tempfile

# Configuração da página
st.set_page_config(
    page_title="🤖 Agent Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurações
API_BASE = os.getenv("AGENTS_API_URL", "http://localhost:8503")
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
PROJECTS_DIR = Path("/home/homelab/myClaude/specialized_agents/dev_projects")

# CSS customizado
st.markdown("""
<style>
    /* Chat container */
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 1rem;
        border-radius: 10px;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    
    /* Mensagens */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 18px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 0;
        max-width: 80%;
        margin-left: auto;
        box-shadow: 0 2px 10px rgba(102, 126, 234, 0.3);
    }
    
    .agent-message {
        background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
        color: #e2e8f0;
        padding: 12px 18px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 0;
        max-width: 85%;
        border: 1px solid #4a5568;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }
    
    .agent-badge {
        background: linear-gradient(135deg, #38b2ac 0%, #319795 100%);
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
        margin-right: 8px;
    }
    
    /* Code blocks */
    .code-block {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        font-family: 'Fira Code', monospace;
        overflow-x: auto;
    }
    
    /* Execution output */
    .execution-output {
        background: #1e1e1e;
        border-left: 4px solid #38b2ac;
        padding: 10px;
        margin: 8px 0;
        border-radius: 4px;
        font-family: monospace;
        white-space: pre-wrap;
    }
    
    .execution-success {
        border-left-color: #48bb78;
    }
    
    .execution-error {
        border-left-color: #fc8181;
    }
    
    /* Thinking indicator */
    .thinking {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #a0aec0;
        padding: 12px;
    }
    
    .thinking-dot {
        width: 8px;
        height: 8px;
        background: #667eea;
        border-radius: 50%;
        animation: pulse 1.4s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.4; transform: scale(0.8); }
        50% { opacity: 1; transform: scale(1); }
    }
    
    /* Sidebar */
    .sidebar-stat {
        background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
        border: 1px solid #4a5568;
    }
    
    /* Action buttons */
    .action-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        padding: 8px 16px;
        border-radius: 8px;
        color: white;
        cursor: pointer;
        transition: transform 0.2s;
    }
    
    .action-btn:hover {
        transform: scale(1.05);
    }
    
    /* File tree */
    .file-item {
        padding: 4px 8px;
        border-radius: 4px;
        cursor: pointer;
        transition: background 0.2s;
    }
    
    .file-item:hover {
        background: rgba(102, 126, 234, 0.2);
    }
</style>
""", unsafe_allow_html=True)


# ================== Utilidades ==================

def detect_language(code: str, hint: str = "") -> str:
    """Detecta a linguagem do código."""
    hint_lower = hint.lower()
    
    if any(x in hint_lower for x in ["python", "py", "django", "flask", "fastapi"]):
        return "python"
    if any(x in hint_lower for x in ["javascript", "js", "node", "react", "vue"]):
        return "javascript"
    if any(x in hint_lower for x in ["typescript", "ts", "angular", "nest"]):
        return "typescript"
    if any(x in hint_lower for x in ["golang", "go "]):
        return "go"
    if "rust" in hint_lower:
        return "rust"
    
    # Detecção por conteúdo
    if "def " in code or "import " in code or "class " in code:
        return "python"
    if "function " in code or "const " in code or "let " in code:
        return "javascript"
    if "fn " in code or "let mut" in code:
        return "rust"
    if "func " in code or "package " in code:
        return "go"
    
    return "python"  # Default


def extract_code_blocks(text: str) -> List[Tuple[str, str]]:
    """Extrai blocos de código do texto."""
    pattern = r'```(\w*)\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return [(lang or "text", code.strip()) for lang, code in matches]


def call_api(endpoint: str, method: str = "GET", data: Dict = None, timeout: int = 60) -> Dict:
    """Chama a API dos agentes."""
    try:
        url = f"{API_BASE}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        else:
            response = requests.post(url, json=data, timeout=timeout)
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "Timeout na requisição"}
    except Exception as e:
        return {"error": str(e)}


def call_ollama(prompt: str, model: str = "qwen2.5-coder:14b", system: str = None) -> str:
    """Chama o Ollama diretamente."""
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False
            },
            timeout=120
        )
        result = response.json()
        return result.get("message", {}).get("content", "Sem resposta")
    except Exception as e:
        return f"Erro ao chamar Ollama: {e}"


def execute_code(code: str, language: str) -> Dict:
    """Executa código via API."""
    return call_api("/code/execute", "POST", {
        "code": code,
        "language": language
    }, timeout=120)


def generate_code(prompt: str, language: str) -> Dict:
    """Gera código via API."""
    return call_api("/code/generate", "POST", {
        "description": prompt,
        "language": language,
        "context": ""
    }, timeout=120)


def run_terminal_command(command: str, cwd: str = None) -> Dict:
    """Executa comando no terminal."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cwd or str(PROJECTS_DIR)
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Comando excedeu timeout de 60s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ================== Processamento de Comandos ==================

class AgentChatProcessor:
    """Processador de chat com capacidades de agente."""
    
    SYSTEM_PROMPT = """Você é um assistente de desenvolvimento AI altamente capaz, similar ao GitHub Copilot.
Você pode:
1. Gerar código em múltiplas linguagens (Python, JavaScript, TypeScript, Go, Rust)
2. Executar código e mostrar resultados
3. Criar e modificar arquivos
4. Executar comandos no terminal
5. Explicar código e conceitos
6. Debugar problemas
7. Sugerir melhorias

Quando gerar código, use blocos de código com a linguagem especificada:
```python
# código aqui
```

Quando precisar executar algo, indique claramente com:
- [EXECUTE_CODE] para executar código
- [EXECUTE_COMMAND] para comandos de terminal
- [CREATE_FILE path/to/file] para criar arquivos

Seja conciso, profissional e proativo. Ofereça soluções completas."""

    def __init__(self):
        self.capabilities = self._load_capabilities()
        
    def _load_capabilities(self) -> Dict:
        """Carrega capacidades dos agentes."""
        try:
            result = call_api("/agents")
            return result
        except:
            return {"available_languages": ["python", "javascript", "typescript", "go", "rust"]}
    
    def process_message(self, message: str, context: List[Dict] = None) -> Dict:
        """Processa mensagem do usuário."""
        message_lower = message.lower()
        
        # Detecta intenções especiais
        if any(x in message_lower for x in ["execute", "rodar", "executar", "run"]):
            return self._handle_execution_request(message, context)
        
        if any(x in message_lower for x in ["criar arquivo", "create file", "novo arquivo"]):
            return self._handle_file_creation(message)
        
        if any(x in message_lower for x in ["terminal", "comando", "command", "shell"]):
            return self._handle_terminal_request(message)
        
        if any(x in message_lower for x in ["status", "health", "agentes"]):
            return self._handle_status_request()
        
        # Requisição geral - usa LLM
        return self._handle_general_request(message, context)
    
    def _handle_execution_request(self, message: str, context: List[Dict] = None) -> Dict:
        """Processa requisição de execução de código."""
        # Procura código no contexto recente
        code_blocks = []
        
        if context:
            for msg in reversed(context[-5:]):
                if msg.get("role") == "assistant":
                    blocks = extract_code_blocks(msg.get("content", ""))
                    code_blocks.extend(blocks)
        
        # Procura código na própria mensagem
        blocks_in_message = extract_code_blocks(message)
        code_blocks = blocks_in_message + code_blocks
        
        if not code_blocks:
            return {
                "type": "text",
                "content": "Não encontrei código para executar. Por favor, forneça o código ou peça para eu gerar primeiro."
            }
        
        # Executa o primeiro bloco encontrado
        lang, code = code_blocks[0]
        if lang == "text":
            lang = detect_language(code, message)
        
        result = execute_code(code, lang)
        
        if "error" in result:
            return {
                "type": "execution",
                "success": False,
                "language": lang,
                "code": code,
                "output": result.get("error", "Erro desconhecido"),
                "content": f"❌ Erro ao executar código {lang}:\n{result.get('error')}"
            }
        
        return {
            "type": "execution",
            "success": result.get("success", False),
            "language": lang,
            "code": code,
            "output": result.get("output", ""),
            "content": f"✅ Código {lang} executado:\n```\n{result.get('output', 'Sem output')}\n```"
        }
    
    def _handle_file_creation(self, message: str) -> Dict:
        """Processa criação de arquivo."""
        # Extrai caminho do arquivo
        path_match = re.search(r'(?:arquivo|file)[:\s]+([^\s]+)', message, re.IGNORECASE)
        
        if not path_match:
            return {
                "type": "text",
                "content": "Por favor, especifique o caminho do arquivo. Exemplo: 'criar arquivo src/utils.py'"
            }
        
        filepath = path_match.group(1)
        
        # Gera conteúdo com LLM
        prompt = f"Gere o conteúdo para o arquivo {filepath}. {message}"
        lang = detect_language("", filepath)
        
        result = generate_code(prompt, lang)
        
        if "error" in result:
            return {
                "type": "text",
                "content": f"Erro ao gerar conteúdo: {result['error']}"
            }
        
        code = result.get("code", "")
        
        return {
            "type": "file_creation",
            "filepath": filepath,
            "code": code,
            "language": lang,
            "content": f"📄 Arquivo `{filepath}` pronto para criação:\n```{lang}\n{code}\n```\n\nDigite 'confirmar' para criar o arquivo."
        }
    
    def _handle_terminal_request(self, message: str) -> Dict:
        """Processa requisição de terminal."""
        # Extrai comando
        cmd_patterns = [
            r'(?:comando|command|execute|rodar)[:\s]+[`\'"]?([^`\'"]+)[`\'"]?',
            r'`([^`]+)`',
            r'\$ (.+)$'
        ]
        
        command = None
        for pattern in cmd_patterns:
            match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
            if match:
                command = match.group(1).strip()
                break
        
        if not command:
            # Pergunta ao LLM qual comando executar
            llm_response = call_ollama(
                f"Baseado nesta requisição, qual comando de terminal devo executar? Responda APENAS com o comando, sem explicações.\n\nRequisição: {message}",
                system="Você é um expert em linha de comando. Responda apenas com o comando apropriado."
            )
            command = llm_response.strip().replace('`', '')
        
        # Executa comando
        result = run_terminal_command(command)
        
        output = result.get("stdout", "") or result.get("stderr", "") or result.get("error", "Sem output")
        success = result.get("success", False)
        
        return {
            "type": "terminal",
            "command": command,
            "success": success,
            "output": output,
            "content": f"{'✅' if success else '❌'} Comando: `{command}`\n```\n{output}\n```"
        }
    
    def _handle_status_request(self) -> Dict:
        """Retorna status do sistema."""
        agents = call_api("/agents")
        autoscaler = call_api("/autoscaler/status")
        instructor = call_api("/instructor/status")
        
        content = "## 📊 Status do Sistema\n\n"
        
        # Agentes
        content += "### 🤖 Agentes Disponíveis\n"
        for lang in agents.get("available_languages", []):
            content += f"- {lang.capitalize()}\n"
        
        # Auto-scaler
        if "current_agents" in autoscaler:
            content += f"\n### ⚡ Auto-Scaler\n"
            content += f"- Agentes ativos: {autoscaler.get('current_agents', 0)}\n"
            content += f"- CPU: {autoscaler.get('current_cpu', 0):.1f}%\n"
        
        # Instructor
        if instructor.get("running"):
            content += f"\n### 🎓 Instructor\n"
            content += f"- Status: Ativo\n"
            content += f"- Sessões: {instructor.get('total_sessions', 0)}\n"
            content += f"- Horários: {', '.join(instructor.get('training_schedule', []))}\n"
        
        return {
            "type": "status",
            "content": content,
            "data": {
                "agents": agents,
                "autoscaler": autoscaler,
                "instructor": instructor
            }
        }
    
    def _handle_general_request(self, message: str, context: List[Dict] = None) -> Dict:
        """Processa requisição geral com LLM."""
        # Constrói contexto
        context_str = ""
        if context:
            for msg in context[-6:]:
                role = "Usuário" if msg["role"] == "user" else "Assistente"
                context_str += f"{role}: {msg['content'][:500]}\n\n"
        
        # Detecta se precisa gerar código
        needs_code = any(x in message.lower() for x in [
            "código", "code", "função", "function", "classe", "class",
            "script", "programa", "implementar", "criar", "gerar",
            "escreva", "write", "desenvolva", "build"
        ])
        
        if needs_code:
            # Detecta linguagem
            lang = detect_language("", message)
            
            # Usa API de geração
            result = generate_code(message, lang)
            
            if "code" in result:
                code = result["code"]
                return {
                    "type": "code_generation",
                    "language": lang,
                    "code": code,
                    "content": f"```{lang}\n{code}\n```\n\nDigite 'executar' para rodar este código."
                }
        
        # Requisição geral - usa Ollama
        full_prompt = f"""Contexto da conversa:
{context_str}

Nova mensagem do usuário:
{message}

Responda de forma útil e profissional."""

        response = call_ollama(full_prompt, system=self.SYSTEM_PROMPT)
        
        return {
            "type": "text",
            "content": response
        }


# ================== Interface Streamlit ==================

def init_session_state():
    """Inicializa estado da sessão."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "processor" not in st.session_state:
        st.session_state.processor = AgentChatProcessor()
    if "pending_file" not in st.session_state:
        st.session_state.pending_file = None
    if "current_language" not in st.session_state:
        st.session_state.current_language = "python"


def render_sidebar():
    """Renderiza sidebar."""
    with st.sidebar:
        st.markdown("## 🤖 Agent Chat")
        st.markdown("---")
        
        # Seleção de linguagem
        st.markdown("### 🔧 Configurações")
        st.session_state.current_language = st.selectbox(
            "Linguagem padrão",
            ["python", "javascript", "typescript", "go", "rust"],
            index=0
        )
        
        # Quick actions
        st.markdown("### ⚡ Ações Rápidas")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Status", use_container_width=True):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "status dos agentes"
                })
                st.rerun()
        
        with col2:
            if st.button("🗑️ Limpar", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        
        # Exemplos
        st.markdown("### 💡 Exemplos")
        examples = [
            "Crie uma função de fibonacci em Python",
            "Gere uma API REST com FastAPI",
            "Execute: print('Hello World')",
            "Comando: ls -la",
            "Crie um componente React"
        ]
        
        for example in examples:
            if st.button(f"📝 {example[:30]}...", key=f"ex_{hash(example)}", use_container_width=True):
                st.session_state.messages.append({
                    "role": "user",
                    "content": example
                })
                st.rerun()
        
        # Status rápido
        st.markdown("### 📈 Sistema")
        try:
            status = call_api("/autoscaler/status")
            if "current_agents" in status:
                st.metric("Agentes Ativos", status["current_agents"])
                st.metric("CPU", f"{status.get('current_cpu', 0):.1f}%")
        except:
            st.warning("API indisponível")


def render_chat():
    """Renderiza área de chat."""
    st.markdown("## 💬 Chat com Agentes Especializados")
    
    # Container de mensagens
    chat_container = st.container()
    
    with chat_container:
        for i, msg in enumerate(st.session_state.messages):
            if msg["role"] == "user":
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-end; margin: 10px 0;">
                    <div class="user-message">
                        {msg["content"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Mensagem do agente
                agent_type = msg.get("type", "text")
                badge = "🤖 Agent"
                
                if agent_type == "execution":
                    badge = "⚡ Executor"
                elif agent_type == "terminal":
                    badge = "💻 Terminal"
                elif agent_type == "code_generation":
                    badge = "📝 Coder"
                elif agent_type == "status":
                    badge = "📊 Monitor"
                
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-start; margin: 10px 0;">
                    <div class="agent-message">
                        <span class="agent-badge">{badge}</span><br/>
                        {msg["content"].replace(chr(10), '<br/>')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Botões de ação para código
                if agent_type in ["code_generation", "execution"] and msg.get("code"):
                    col1, col2, col3 = st.columns([1, 1, 4])
                    with col1:
                        if st.button("▶️ Executar", key=f"exec_{i}"):
                            result = execute_code(msg["code"], msg.get("language", "python"))
                            st.session_state.messages.append({
                                "role": "assistant",
                                "type": "execution",
                                "content": f"```\n{result.get('output', result.get('error', 'Sem output'))}\n```",
                                "code": msg["code"],
                                "language": msg.get("language", "python")
                            })
                            st.rerun()
                    with col2:
                        if st.button("📋 Copiar", key=f"copy_{i}"):
                            st.code(msg["code"], language=msg.get("language", "python"))


def render_input():
    """Renderiza área de input."""
    st.markdown("---")
    
    # Input de mensagem
    user_input = st.chat_input("Digite sua mensagem... (ex: 'crie uma função de ordenação em Python')")
    
    if user_input:
        # Adiciona mensagem do usuário
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Processa com o agente
        with st.spinner("🤔 Processando..."):
            context = [{"role": m["role"], "content": m["content"]} 
                      for m in st.session_state.messages[-10:]]
            
            result = st.session_state.processor.process_message(user_input, context)
        
        # Adiciona resposta
        st.session_state.messages.append({
            "role": "assistant",
            **result
        })
        
        st.rerun()


def render_code_editor():
    """Renderiza editor de código inline."""
    with st.expander("📝 Editor de Código", expanded=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            code = st.text_area(
                "Código",
                height=200,
                placeholder="Cole ou escreva seu código aqui..."
            )
        
        with col2:
            lang = st.selectbox(
                "Linguagem",
                ["python", "javascript", "typescript", "go", "rust"]
            )
            
            if st.button("▶️ Executar", use_container_width=True):
                if code.strip():
                    result = execute_code(code, lang)
                    st.session_state.messages.append({
                        "role": "user",
                        "content": f"Executar:\n```{lang}\n{code}\n```"
                    })
                    st.session_state.messages.append({
                        "role": "assistant",
                        "type": "execution",
                        "content": f"```\n{result.get('output', result.get('error', 'Sem output'))}\n```",
                        "code": code,
                        "language": lang
                    })
                    st.rerun()
            
            if st.button("📤 Enviar", use_container_width=True):
                if code.strip():
                    st.session_state.messages.append({
                        "role": "user",
                        "content": f"```{lang}\n{code}\n```"
                    })
                    st.rerun()


def main():
    """Função principal."""
    init_session_state()
    render_sidebar()
    
    # Layout principal
    col1, col2 = st.columns([3, 1])
    
    with col1:
        render_chat()
        render_input()
    
    with col2:
        render_code_editor()
        
        # Info
        st.markdown("### ℹ️ Dicas")
        st.markdown("""
        - **Gerar código**: "crie uma função de..."
        - **Executar**: "execute" ou "rodar"
        - **Terminal**: "comando: ls -la"
        - **Status**: "status dos agentes"
        """)


if __name__ == "__main__":
    main()
