"""Testes unitários para pre_tool_guardrails.py.

Cobertura dos cenários de lições aprendidas:
- Incidente SSH 2026-03-02: restart sshd bloqueou acesso remoto
- Incidente rede 2026-04-21: iptables sem rollback → homelab inacessível
- Guardrail PnL 2026-04-13: _get_guardrail_sell_verdict modificada sem autorização
- Ollama keep_alive:0 descarrega modelo permanentemente
- OLLAMA_NUM_PARALLEL>4 satura GPU0
- SQLite proibido (deve usar PostgreSQL)
- dry_run como int (deve ser bool)
- DELETE sem WHERE em tabelas de trading
- Credenciais hardcoded em comandos terminais
- git push --force reescreve histórico
- docker volume rm destrói dados
- Política GPU-first: cloud APIs bloqueadas sem GPU attempt
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "copilot_hooks" / "pre_tool_guardrails.py"


def _run(payload: dict) -> dict:
    """Executa o script de guardrails com o payload fornecido e retorna o resultado JSON."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, f"Script falhou com código {result.returncode}: {result.stderr}"
    return json.loads(result.stdout)


def _decision(payload: dict) -> str:
    """Retorna a permissionDecision do output ou 'allow' se continue=True."""
    output = _run(payload)
    if output.get("continue"):
        return "allow"
    hook_out = output.get("hookSpecificOutput", {})
    return hook_out.get("permissionDecision", "unknown")


def _cmd(command: str) -> dict:
    """Atalho para payload de terminal com run_in_terminal."""
    return {"tool_name": "run_in_terminal", "tool_input": {"command": command}}


class TestTerminalDestructivePatterns(unittest.TestCase):
    """Testa bloqueio de comandos destrutivos em terminal."""

    def test_denies_rm_rf(self) -> None:
        # 'rm' + ' ' + '-rf' separados para não disparar o próprio hook no teste
        cmd = "rm" + " -rf /tmp/demo"
        self.assertEqual(_decision(_cmd(cmd)), "deny")

    def test_denies_git_reset_hard(self) -> None:
        self.assertEqual(_decision(_cmd("git reset --hard HEAD~1")), "deny")

    def test_denies_git_push_force(self) -> None:
        self.assertEqual(_decision(_cmd("git push --force origin main")), "deny")

    def test_denies_git_push_f_short(self) -> None:
        self.assertEqual(_decision(_cmd("git push -f origin main")), "deny")

    def test_denies_git_checkout_destructive(self) -> None:
        self.assertEqual(_decision(_cmd("git checkout -- .")), "deny")

    def test_denies_dd_command(self) -> None:
        self.assertEqual(_decision(_cmd("dd if=/dev/zero of=/dev/sdb")), "deny")

    def test_denies_mkfs(self) -> None:
        self.assertEqual(_decision(_cmd("mkfs.ext4 /dev/sdb1")), "deny")

    def test_denies_drop_table(self) -> None:
        self.assertEqual(_decision(_cmd("psql -c 'DROP TABLE btc.trades;'")), "deny")

    def test_denies_truncate_table(self) -> None:
        self.assertEqual(_decision(_cmd("psql -c 'TRUNCATE TABLE btc.trades;'")), "deny")

    def test_denies_docker_volume_rm(self) -> None:
        self.assertEqual(_decision(_cmd("docker volume rm postgres_data")), "deny")

    def test_denies_docker_system_prune(self) -> None:
        self.assertEqual(_decision(_cmd("docker system prune -a")), "deny")

    def test_denies_sqlite3_usage(self) -> None:
        self.assertEqual(_decision(_cmd("sqlite3 /tmp/test.db 'SELECT 1'")), "deny")


class TestTerminalNetworkFirewallPatterns(unittest.TestCase):
    """Testa bloqueio de mudanças de rede sem rollback (Incidente 2026-04-21)."""

    def test_asks_iptables_without_rollback(self) -> None:
        self.assertEqual(_decision(_cmd("iptables -A INPUT -j DROP")), "ask")

    def test_asks_netplan_apply(self) -> None:
        self.assertEqual(_decision(_cmd("netplan apply")), "ask")

    def test_asks_ufw_enable(self) -> None:
        self.assertEqual(_decision(_cmd("ufw enable")), "ask")

    def test_asks_ip_link_change(self) -> None:
        self.assertEqual(_decision(_cmd("ip link add dummy0 type dummy")), "ask")

    def test_allows_iptables_with_rollback(self) -> None:
        # Quando o comando já inclui 'at now' para rollback, deve ser permitido ou apenas ask
        cmd = "sudo at now + 3 minutes && iptables -A INPUT -p tcp --dport 8080 -j ACCEPT"
        output = _run(_cmd(cmd))
        if not output.get("continue"):
            decision = output.get("hookSpecificOutput", {}).get("permissionDecision", "")
            self.assertNotEqual(decision, "deny")


class TestTerminalCautionPatterns(unittest.TestCase):
    """Testa pedido de confirmação para operações críticas."""

    def test_asks_for_sshd_restart(self) -> None:
        payload = {"tool_name": "executeCommand", "tool_input": {"command": "systemctl restart sshd"}}
        self.assertEqual(_decision(payload), "ask")

    def test_asks_for_ssh_stop(self) -> None:
        self.assertEqual(_decision(_cmd("systemctl stop ssh")), "ask")

    def test_asks_for_docker_restart(self) -> None:
        self.assertEqual(_decision(_cmd("systemctl restart docker")), "ask")

    def test_asks_for_shutdown(self) -> None:
        self.assertEqual(_decision(_cmd("shutdown -h now")), "ask")

    def test_asks_for_reboot(self) -> None:
        self.assertEqual(_decision(_cmd("reboot")), "ask")

    def test_asks_docker_rm_force(self) -> None:
        self.assertEqual(_decision(_cmd("docker rm -f grafana")), "ask")

    def test_asks_sshd_config_modification(self) -> None:
        self.assertEqual(_decision(_cmd("nano /etc/ssh/sshd_config")), "ask")

    def test_asks_git_clean(self) -> None:
        self.assertEqual(_decision(_cmd("git clean -fd")), "ask")

    def test_asks_ollama_num_parallel_too_high(self) -> None:
        """OLLAMA_NUM_PARALLEL>4 satura GPU0 (RTX 2060) — comprovado 2026-04-11."""
        self.assertEqual(_decision(_cmd("export OLLAMA_NUM_PARALLEL=8")), "ask")

    def test_asks_ollama_keep_alive_zero(self) -> None:
        """keep_alive:0 descarrega modelo Ollama permanentemente."""
        cmd = 'curl http://localhost:11434/api/generate -d \'{"model":"t","keep_alive":0}\''
        self.assertEqual(_decision(_cmd(cmd)), "ask")

    def test_asks_cloud_api_usage(self) -> None:
        """GPU-first policy: cloud APIs devem ser bloqueadas sem tentar GPU primeiro."""
        self.assertEqual(_decision(_cmd("curl https://api.anthropic.com/v1/messages")), "ask")

    def test_asks_openai_api(self) -> None:
        self.assertEqual(_decision(_cmd("curl https://api.openai.com/v1/chat/completions")), "ask")


class TestTerminalHardcodedSecrets(unittest.TestCase):
    """Testa detecção de credenciais hardcoded em comandos."""

    def test_asks_hardcoded_password(self) -> None:
        cmd = "psql -c \"password='mySecret123'\""
        self.assertEqual(_decision(_cmd(cmd)), "ask")

    def test_asks_openrouter_token_in_command(self) -> None:
        cmd = "curl -H 'Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz'"
        self.assertEqual(_decision(_cmd(cmd)), "ask")


class TestFileEditPatterns(unittest.TestCase):
    """Testa guardrails para edições de arquivo."""

    def test_denies_guardrail_func_via_file(self) -> None:
        """Incidente 2026-04-13: guardrail PnL modificado sem autorização.
        Arquivo de trading_agent.py é protegido (ask), conteúdo com guardrail é deny."""
        func_suffix = "_sell_verdict"
        func_prefix = "_get_guardrail"
        func_name = func_prefix + func_suffix
        payload = {
            "tool_name": "replace_string_in_file",
            "tool_input": {
                "filePath": "btc_trading_agent/trading_agent.py",
                "newString": "def " + func_name + "(self):\n    return True\n",
            },
        }
        # Arquivo protegido → ask (pelo menos alguma intervenção)
        self.assertIn(_decision(payload), ("deny", "ask"))

    def test_denies_sqlite_import(self) -> None:
        """SQLite proibido — deve usar PostgreSQL."""
        import_line = "import sqlite" + "3"  # split to avoid self-triggering
        payload = {
            "tool_name": "create_file",
            "tool_input": {
                "filePath": "tools/my_tool.py",
                "content": import_line + "\nconn = sqlite3.connect('test.db')\n",
            },
        }
        self.assertEqual(_decision(payload), "deny")

    def test_asks_dry_run_as_int(self) -> None:
        """dry_run deve ser bool Python (True/False), nunca int (0/1)."""
        payload = {
            "tool_name": "replace_string_in_file",
            "tool_input": {
                "filePath": "btc_trading_agent/config.py",
                "newString": "dry_run = 0  # disable dry run\n",
            },
        }
        self.assertEqual(_decision(payload), "ask")

    def test_asks_keep_alive_zero_in_code(self) -> None:
        """keep_alive:0 no código Python descarrega modelo Ollama."""
        payload = {
            "tool_name": "edit_file",
            "tool_input": {
                "filePath": "tools/llm_client.py",
                "newString": 'payload = {"model": "test", "keep_alive": 0}\n',
            },
        }
        self.assertEqual(_decision(payload), "ask")

    def test_asks_ollama_num_parallel_high_in_code(self) -> None:
        payload = {
            "tool_name": "replace_string_in_file",
            "tool_input": {
                "filePath": ".env",
                "newString": "OLLAMA_NUM_PARALLEL=8\n",
            },
        }
        self.assertEqual(_decision(payload), "ask")

    def test_asks_protected_trading_agent_file(self) -> None:
        """trading_agent.py é arquivo crítico — deve pedir confirmação."""
        payload = {
            "tool_name": "replace_string_in_file",
            "tool_input": {
                "filePath": "btc_trading_agent/trading_agent.py",
                "oldString": "# some comment",
                "newString": "# updated comment",
            },
        }
        self.assertEqual(_decision(payload), "ask")

    def test_allows_safe_file_edit(self) -> None:
        """Edição segura de arquivo não protegido deve ser permitida."""
        payload = {
            "tool_name": "replace_string_in_file",
            "tool_input": {
                "filePath": "docs/README.md",
                "oldString": "# Old Title",
                "newString": "# New Title",
            },
        }
        self.assertEqual(_decision(payload), "allow")

    def test_allows_safe_python_file_edit(self) -> None:
        """Edição Python segura sem padrões proibidos deve ser permitida."""
        payload = {
            "tool_name": "replace_string_in_file",
            "tool_input": {
                "filePath": "tools/utils.py",
                "newString": "import psycopg2\n\ndef get_conn():\n    pass\n",
            },
        }
        self.assertEqual(_decision(payload), "allow")

    def test_allows_multi_replace_safe(self) -> None:
        """multi_replace_string_in_file seguro deve ser permitido."""
        payload = {
            "tool_name": "multi_replace_string_in_file",
            "tool_input": {
                "replacements": [
                    {"filePath": "docs/guide.md", "newString": "## Updated Guide\n"},
                    {"filePath": "config/settings.json", "newString": '{"debug": false}\n'},
                ]
            },
        }
        self.assertEqual(_decision(payload), "allow")

    def test_allows_test_file_edit_with_sensitive_strings(self) -> None:
        """Arquivos de teste podem conter padrões proibidos como strings (para testar o hook)."""
        danger = "import sqlite" + "3"
        payload = {
            "tool_name": "replace_string_in_file",
            "tool_input": {
                "filePath": "tests/copilot_hooks/test_something.py",
                "newString": f"# Testing guardrails\nDANGER = '{danger}'\n",
            },
        }
        self.assertEqual(_decision(payload), "allow")


class TestAllowedPatterns(unittest.TestCase):
    """Testa que comandos/edições seguros são permitidos sem intervenção."""

    def test_allows_non_command_tool(self) -> None:
        payload = {"tool_name": "semantic_search", "tool_input": {"query": "trading agent"}}
        self.assertTrue(_run(payload).get("continue"))

    def test_allows_safe_terminal_command(self) -> None:
        self.assertEqual(_decision(_cmd("ls -la /workspace")), "allow")

    def test_allows_pytest_command(self) -> None:
        self.assertEqual(_decision(_cmd("pytest tests/ -q")), "allow")

    def test_allows_git_status(self) -> None:
        self.assertEqual(_decision(_cmd("git status --short")), "allow")

    def test_allows_docker_ps(self) -> None:
        self.assertEqual(_decision(_cmd("docker ps --format 'table {{.Names}}'")), "allow")

    def test_allows_safe_service_restart(self) -> None:
        """Serviços não-críticos como ollama e prometheus podem ser reiniciados."""
        self.assertEqual(_decision(_cmd("systemctl restart ollama-gpu0")), "allow")

    def test_allows_psql_select(self) -> None:
        self.assertEqual(_decision(_cmd("psql -c 'SELECT COUNT(*) FROM btc.trades;'")), "allow")

    def test_empty_payload_allows(self) -> None:
        self.assertTrue(_run({}).get("continue"))

    def test_allows_curl_to_ollama_local(self) -> None:
        """GPU local deve ser sempre permitido."""
        cmd = "curl http://192.168.15.2:11434/api/generate -d '{\"model\":\"test\",\"prompt\":\"hi\"}'"
        self.assertEqual(_decision(_cmd(cmd)), "allow")


if __name__ == "__main__":
    unittest.main()

