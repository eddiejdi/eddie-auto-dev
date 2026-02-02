"""
title: GitHub Copilot CLI
author: Eddie
version: 1.0.0
description: Executa comandos do GitHub Copilot via gh copilot.
"""

import shlex
import shutil
import subprocess
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        ALLOWED_MODELS: str = Field(
            default="github-agent,eddie-coder,eddie-homelab",
            description="Modelos autorizados a usar o Copilot (separados por vírgula)",
        )
        WORKDIR: str = Field(
            default="/home/edenilson/eddie-auto-dev",
            description="Diretório padrão para execução",
        )
        TIMEOUT_SECONDS: int = Field(
            default=120, description="Timeout máximo de execução (segundos)"
        )
        MAX_OUTPUT_CHARS: int = Field(
            default=4000, description="Limite de caracteres do output"
        )

    def __init__(self):
        self.valves = self.Valves()

    def copilot_cli(
        self,
        args: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        __user__: dict = {},
    ) -> str:
        """
        Executa o comando `gh copilot` com os argumentos informados.
        Use esta ferramenta quando o usuário pedir para usar o GitHub Copilot via CLI.

        :param args: Argumentos para o comando gh copilot (ex: "suggest -q 'list files' -t shell")
        :param cwd: Diretório de trabalho (opcional)
        :param timeout: Timeout em segundos (opcional)
        :return: Resultado da execução
        """
        if not args or not args.strip():
            return "❌ Informe os argumentos para `gh copilot`."

        model_name = self._extract_model_name(__user__)
        if not self._is_model_allowed(model_name):
            allowed = ", ".join(self._allowed_models())
            return (
                "❌ Modelo não autorizado a usar GitHub Copilot.\n"
                f"Modelo detectado: {model_name or 'desconhecido'}\n"
                f"Permitidos: {allowed}"
            )

        if shutil.which("gh") is None:
            return "❌ `gh` não encontrado. Instale o GitHub CLI e autentique antes de usar."

        workdir = cwd or self.valves.WORKDIR
        exec_timeout = timeout or self.valves.TIMEOUT_SECONDS

        try:
            cmd = ["gh", "copilot"] + shlex.split(args)
            result = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=exec_timeout,
            )
        except subprocess.TimeoutExpired:
            return f"⏱️ Timeout: comando excedeu {exec_timeout}s."
        except FileNotFoundError:
            return "❌ `gh` não encontrado no PATH."
        except Exception as e:
            return f"❌ Erro ao executar: {str(e)}"

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = (stdout + ("\n" if stdout and stderr else "") + stderr).strip()
        if not output:
            output = "(sem output)"

        output = self._truncate_output(output)
        return f"$ gh copilot {args}\n\n{output}\n\n(exit code: {result.returncode})"

    def copilot_suggest_and_run(
        self,
        query: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        __user__: dict = {},
    ) -> str:
        """
        Pede ao Copilot um comando shell e executa o comando sugerido automaticamente.
        Use esta ferramenta quando o usuário pedir para "executar com Copilot".

        :param query: Descrição do que o comando deve fazer
        :param cwd: Diretório de trabalho (opcional)
        :param timeout: Timeout em segundos (opcional)
        :return: Resultado da sugestão e execução
        """
        if not query or not query.strip():
            return "❌ Informe uma descrição para o Copilot sugerir o comando."

        model_name = self._extract_model_name(__user__)
        if not self._is_model_allowed(model_name):
            allowed = ", ".join(self._allowed_models())
            return (
                "❌ Modelo não autorizado a usar GitHub Copilot.\n"
                f"Modelo detectado: {model_name or 'desconhecido'}\n"
                f"Permitidos: {allowed}"
            )

        if shutil.which("gh") is None:
            return "❌ `gh` não encontrado. Instale o GitHub CLI e autentique antes de usar."

        workdir = cwd or self.valves.WORKDIR
        exec_timeout = timeout or self.valves.TIMEOUT_SECONDS

        try:
            suggest_cmd = ["gh", "copilot", "suggest", "-t", "shell", "-q", query]
            suggestion = subprocess.run(
                suggest_cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=exec_timeout,
            )
        except subprocess.TimeoutExpired:
            return f"⏱️ Timeout: sugestão excedeu {exec_timeout}s."
        except Exception as e:
            return f"❌ Erro ao executar Copilot: {str(e)}"

        raw = (suggestion.stdout or "").strip()
        if not raw:
            raw = (suggestion.stderr or "").strip()
        if not raw:
            return "❌ Copilot não retornou sugestão."

        cmd = self._extract_command(raw)
        if not cmd:
            return f"❌ Não foi possível extrair um comando da sugestão:\n{raw}"

        if self._is_dangerous_command(cmd):
            return f"❌ Comando bloqueado por segurança: {cmd}"

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=exec_timeout,
            )
        except subprocess.TimeoutExpired:
            return f"⏱️ Timeout: execução excedeu {exec_timeout}s."
        except Exception as e:
            return f"❌ Erro ao executar comando: {str(e)}"

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = (stdout + ("\n" if stdout and stderr else "") + stderr).strip()
        if not output:
            output = "(sem output)"

        output = self._truncate_output(output)
        return (
            "✅ Comando sugerido pelo Copilot e executado:\n"
            f"$ {cmd}\n\n{output}\n\n(exit code: {result.returncode})"
        )

    def _allowed_models(self) -> list:
        return [
            m.strip().lower()
            for m in self.valves.ALLOWED_MODELS.split(",")
            if m.strip()
        ]

    def _extract_model_name(self, user: dict) -> str:
        if not user:
            return ""
        for key in ["model", "model_id", "model_name", "modelId", "modelName"]:
            if key in user and user[key]:
                return str(user[key])
        settings = user.get("settings") or {}
        if isinstance(settings, dict):
            for key in ["model", "model_id", "model_name"]:
                if settings.get(key):
                    return str(settings.get(key))
        return ""

    def _is_model_allowed(self, model_name: str) -> bool:
        allowed = self._allowed_models()
        if not allowed:
            return False
        if not model_name:
            return False
        model_name = model_name.lower()
        return any(a in model_name for a in allowed)

    def _is_dangerous_command(self, command: str) -> bool:
        cmd = command.lower().strip()
        deny = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs",
            "shutdown",
            "reboot",
            "poweroff",
            "halt",
            "init 0",
            "dd if=",
            "wipefs",
            "kill -9 1",
            "systemctl poweroff",
        ]
        return any(x in cmd for x in deny)

    def _extract_command(self, text: str) -> str:
        # Try fenced code block first
        if "```" in text:
            parts = text.split("```")
            for i in range(1, len(parts), 2):
                block = parts[i].strip()
                if not block:
                    continue
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                if lines:
                    return lines[0]

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines:
            if line.startswith("$ "):
                return line[2:].strip()
        for line in lines:
            if line and not line.startswith(("?", "•", "-", "*", "#")):
                return line
        return ""

    def _truncate_output(self, output: str) -> str:
        limit = self.valves.MAX_OUTPUT_CHARS
        if len(output) <= limit:
            return output
        return output[:limit] + "\n... (output truncado)"
