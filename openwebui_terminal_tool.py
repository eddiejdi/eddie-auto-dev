"""
title: Terminal do Servidor
author: Eddie
version: 1.0.0
description: Executa comandos no terminal do servidor com controles de segurança.
"""

import os
import subprocess
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        ALLOWED_MODELS: str = Field(
            default="eddie-coder,telegram-terminal,terminal-telegram,proj_terminal_bot",
            description="Modelos autorizados a executar comandos (separados por vírgula)"
        )
        WORKDIR: str = Field(
            default="/home/homelab",
            description="Diretório padrão para execução"
        )
        TIMEOUT_SECONDS: int = Field(
            default=60,
            description="Timeout máximo de execução (segundos)"
        )
        MAX_OUTPUT_CHARS: int = Field(
            default=4000,
            description="Limite de caracteres do output"
        )

    def __init__(self):
        self.valves = self.Valves()

    def run_terminal_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        __user__: dict = {},
    ) -> str:
        """
        Executa um comando no terminal do servidor.
        Use esta ferramenta quando o usuário pedir execução direta de comandos.

        :param command: Comando a executar
        :param cwd: Diretório de trabalho (opcional)
        :param timeout: Timeout em segundos (opcional)
        :return: Resultado da execução
        """
        if not command or not command.strip():
            return "❌ Comando vazio. Informe um comando válido."

        model_name = self._extract_model_name(__user__)
        if not self._is_model_allowed(model_name):
            allowed = ", ".join(self._allowed_models())
            return (
                "❌ Modelo não autorizado a executar comandos no terminal.\n"
                f"Modelo detectado: {model_name or 'desconhecido'}\n"
                f"Permitidos: {allowed}"
            )

        if self._is_dangerous_command(command):
            return "❌ Comando bloqueado por segurança."

        workdir = cwd or self.valves.WORKDIR
        exec_timeout = timeout or self.valves.TIMEOUT_SECONDS

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=exec_timeout,
            )
        except subprocess.TimeoutExpired:
            return f"⏱️ Timeout: comando excedeu {exec_timeout}s."
        except Exception as e:
            return f"❌ Erro ao executar: {str(e)}"

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = (stdout + ("\n" if stdout and stderr else "") + stderr).strip()
        if not output:
            output = "(sem output)"

        output = self._truncate_output(output)
        return f"$ {command}\n\n{output}\n\n(exit code: {result.returncode})"

    def _allowed_models(self) -> list:
        return [m.strip().lower() for m in self.valves.ALLOWED_MODELS.split(",") if m.strip()]

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

    def _truncate_output(self, output: str) -> str:
        limit = self.valves.MAX_OUTPUT_CHARS
        if len(output) <= limit:
            return output
        return output[:limit] + "\n... (output truncado)"
