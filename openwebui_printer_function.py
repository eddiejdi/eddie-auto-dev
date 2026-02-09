"""
Função Open WebUI para impressão em Phomemo Q30
Permite ao usuário descrever o que quer imprimir e valida o tamanho
"""

import json
import subprocess
from typing import Optional
import os

class Pipe:
    """Pipe para impressão em etiqueta via Phomemo Q30"""
    
    class Valves:
        def __init__(self):
            self.PRINTER_SCRIPT = "/home/homelab/agents_workspace/phomemo_print.py"
            self.PRINTER_PORT = ""  # Auto-detect by default
            self.MAX_WIDTH = 384  # pixels (Phomemo max)
            self.MAX_HEIGHT = 600  # pixels
            self.BAUDRATE = 9600
            self.TEMP_DIR = "/tmp"
    
    def __init__(self):
        self.valves = self.Valves()
        self.name = "🖨️ Impressora de Etiquetas"
        
    def validate_label_size(self, text: str, width: int = 384, height: int = 600) -> dict:
        """Valida se o texto/imagem cabe na etiqueta"""
        # Estimativa aproximada
        char_width = 8  # pixels por caractere
        char_height = 16  # pixels de altura
        
        lines = text.split('\n')
        estimated_width = max(len(line) for line in lines) * char_width
        estimated_height = len(lines) * char_height
        
        is_valid_width = estimated_width <= width
        is_valid_height = estimated_height <= height
        
        return {
            "valid": is_valid_width and is_valid_height,
            "estimated_width": estimated_width,
            "estimated_height": estimated_height,
            "max_width": width,
            "max_height": height,
            "width_ok": is_valid_width,
            "height_ok": is_valid_height,
            "warning": self._generate_warning(is_valid_width, is_valid_height, estimated_width, estimated_height, width, height)
        }
    
    def _generate_warning(self, w_ok: bool, h_ok: bool, est_w: int, est_h: int, max_w: int, max_h: int) -> str:
        """Gera mensagem de aviso se houver"""
        warnings = []
        if not w_ok:
            warnings.append(f"⚠️ Largura: {est_w}px (máximo {max_w}px)")
        if not h_ok:
            warnings.append(f"⚠️ Altura: {est_h}px (máximo {max_h}px)")
        return " | ".join(warnings) if warnings else ""
    
    async def pipe(self, body: dict, __user__: dict = None, __event_emitter__=None, __task__=None) -> str:
        """
        Processa requisição de impressão via Pipe
        
        body: dict contendo as mensagens do chat
        """
        # Extrair última mensagem do usuário
        if isinstance(body, dict):
            messages = body.get("messages", [])
            if not messages:
                return "❌ Nenhuma mensagem fornecida"
            
            # Pegar última mensagem do usuário
            user_message = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            if not user_message:
                return "❌ Nenhuma mensagem de usuário encontrada"
            
            content = user_message
        else:
            content = str(body)
        
        """
        Processa requisição de impressão
        
        Entrada esperada:
        - Texto simples: "Imprima TESTE"
        - JSON: {"action": "print", "content": "texto", "validate_only": true}
        """
        
        try:
            # Parse do input
            if content.startswith('{'):
                request = json.loads(content)
            else:
                # Se for apenas texto, criar request padrão
                request = {
                    "action": "print",
                    "content": content,
                    "type": "text",
                    "validate_only": False
                }
            
            action = request.get("action", "print")
            text_to_print = request.get("content", "")
            req_type = request.get("type", "text")
            validate_only = request.get("validate_only", False)

            # Ação para consultar status da impressora
            if action == "status":
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "🔎 Consultando status da impressora..."}
                    })
                status = await self._get_status()
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "✅ Status obtido"}
                    })
                return status
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": f"🔍 Processando requisição de impressão..."}
                })
            
            # Validar tamanho
            if req_type == "text":
                validation = self.validate_label_size(text_to_print)
                
                status_msg = f"""
📊 **Validação da Etiqueta**

✅ **Texto:** {len(text_to_print)} caracteres
📏 **Estimativa:**
   - Largura: {validation['estimated_width']}px / {validation['max_width']}px
   - Altura: {validation['estimated_height']}px / {validation['max_height']}px

**Status:** {"✅ VÁLIDO - Pronto para imprimir" if validation['valid'] else "⚠️ EXCEDE LIMITES"}
{f"**Avisos:** {validation['warning']}" if validation['warning'] else ""}
"""
                
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "✅ Validação concluída"}
                    })
                
                # Se apenas validar, retornar resultado
                if validate_only:
                    return status_msg + "\n\n💾 Use `validate_only: false` para imprimir."
                
                # Se não for válido, não imprimir
                if not validation['valid']:
                    return status_msg + "\n\n❌ Não é possível imprimir - texto não cabe na etiqueta."
                
                # Imprimir
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "🖨️ Enviando para impressora..."}
                    })
                
                result = await self._print_text(text_to_print)
                return status_msg + f"\n\n{result}"
            
            elif req_type == "image":
                if not os.path.exists(text_to_print):
                    return f"❌ Arquivo de imagem não encontrado: {text_to_print}"
                
                if validate_only:
                    return f"📄 Arquivo de imagem encontrado: {text_to_print}\nUse `validate_only: false` para imprimir."
                
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "🖨️ Enviando imagem para impressora..."}
                    })
                
                result = await self._print_image(text_to_print)
                return result
            
            else:
                return f"❌ Tipo não suportado: {req_type}. Use 'text' ou 'image'"
        
        except json.JSONDecodeError:
            return f"❌ JSON inválido: {content[:100]}"
        except Exception as e:
            return f"❌ Erro ao processar: {str(e)}"
    
    async def _print_text(self, text: str) -> str:
        """Envia texto para impressora"""
        try:
            cmd = [
                "python3",
                self.valves.PRINTER_SCRIPT,
                "--text", text,
                "--baud", str(self.valves.BAUDRATE)
            ]
            
            if self.valves.PRINTER_PORT:
                cmd.extend(["--port", self.valves.PRINTER_PORT])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return "✅ **Etiqueta impressa com sucesso!**\n\n📝 Conteúdo enviado para o Phomemo Q30"
            else:
                return f"❌ Erro ao imprimir:\n```\n{result.stderr}\n```"
        
        except subprocess.TimeoutExpired:
            return "❌ Timeout ao imprimir (30s)"
        except Exception as e:
            return f"❌ Erro ao executar impressora: {str(e)}"
    
    async def _print_image(self, image_path: str) -> str:
        """Envia imagem para impressora"""
        try:
            cmd = [
                "python3",
                self.valves.PRINTER_SCRIPT,
                "--image", image_path,
                "--baud", str(self.valves.BAUDRATE)
            ]
            
            if self.valves.PRINTER_PORT:
                cmd.extend(["--port", self.valves.PRINTER_PORT])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return f"✅ **Imagem impressa com sucesso!**\n\n📸 Arquivo: {image_path}"
            else:
                return f"❌ Erro ao imprimir imagem:\n```\n{result.stderr}\n```"
        
        except subprocess.TimeoutExpired:
            return "❌ Timeout ao imprimir (30s)"
        except Exception as e:
            return f"❌ Erro ao executar impressora: {str(e)}"

    async def _get_status(self) -> str:
        """Consulta o status da impressora executando o script driver com --status.

        Retorna uma string amigável com o resultado ou erro.
        """
        try:
            cmd = ["python3", self.valves.PRINTER_SCRIPT, "--status"]
            if self.valves.PRINTER_PORT:
                cmd.extend(["--port", self.valves.PRINTER_PORT])
            cmd.extend(["--baud", str(self.valves.BAUDRATE)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Tentar formatar a saída
                out = result.stdout.strip()
                if not out:
                    out = "✅ Impressora conectada — sem detalhes retornados."
                return f"🟢 Status da impressora:\n\n```
{out}
```"
            else:
                err = result.stderr.strip() or result.stdout.strip()
                return f"🔴 Erro ao obter status:\n\n```
{err}
```"

        except subprocess.TimeoutExpired:
            return "🔴 Timeout ao consultar status da impressora (10s)"
        except FileNotFoundError:
            return f"🔴 Script de impressora não encontrado: {self.valves.PRINTER_SCRIPT}"
        except Exception as e:
            return f"🔴 Erro inesperado ao consultar status: {str(e)}"
