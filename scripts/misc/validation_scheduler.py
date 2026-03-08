#!/usr/bin/env python3
"""
Scheduler de Validação Selenium com Alertas Telegram
Executa testes periódicos e notifica sobre problemas
"""

import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ requests não instalado. Execute: pip install requests")
    sys.exit(1)


class ValidationScheduler:
    """Agendador de validações com alertas"""
    
    def __init__(self, telegram_token=None, telegram_chat_id=None, log_dir="/tmp/validation_logs"):
        self.telegram_token = telegram_token or self.load_telegram_config()["token"]
        self.telegram_chat_id = telegram_chat_id or self.load_telegram_config()["chat_id"]
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.history_file = self.log_dir / "validation_history.json"
        
    def load_telegram_config(self):
        """Carrega configuração Telegram do arquivo local"""
        config_file = Path.home() / ".telegram_config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    return json.load(f)
            except:
                return {"token": None, "chat_id": None}
        return {"token": None, "chat_id": None}
    
    def send_telegram_alert(self, title, message, status="⚠️"):
        """Envia alerta via Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️  Telegram não configurado")
            return False
        
        text = f"{status} **{title}**\n\n{message}"
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, json=data, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Erro ao enviar Telegram: {e}")
            return False
    
    def run_validation(self, url="https://www.rpa4all.com/"):
        """Executa validação Selenium"""
        print(f"\n🔍 Iniciando validação: {datetime.now().isoformat()}")
        
        try:
            # Executa o bot avançado
            result = subprocess.run(
                ["python3", "/home/edenilson/shared-auto-dev/validate_links_advanced.py", url],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Parse resultado
            output = result.stdout + result.stderr
            
            # Detecta status
            if "✅ TODOS OS LINKS OK" in output:
                status = "success"
                icon = "✅"
            elif "⚠️" in output and "funcionais" in output:
                status = "warning"
                icon = "⚠️"
            else:
                status = "error"
                icon = "❌"
            
            # Extrai estatísticas
            stats = self.parse_stats(output)
            
            result_obj = {
                "timestamp": datetime.now().isoformat(),
                "url": url,
                "status": status,
                "stats": stats,
                "output": output[:500]  # Primeiros 500 chars
            }
            
            # Salva no histórico
            self.save_history(result_obj)
            
            # Envia alerta se necessário
            if status != "success":
                self.send_alert(result_obj, icon)
            
            return result_obj
            
        except subprocess.TimeoutExpired:
            error_msg = "Timeout na execução (> 2 min)"
            self.send_telegram_alert(
                "Validação Timeout",
                f"URL: {url}\nErro: {error_msg}",
                "❌"
            )
            return {"status": "error", "error": error_msg}
        except Exception as e:
            error_msg = str(e)
            self.send_telegram_alert(
                "Erro na Validação",
                f"URL: {url}\nErro: {error_msg}",
                "❌"
            )
            return {"status": "error", "error": error_msg}
    
    def parse_stats(self, output):
        """Parse estatísticas do output"""
        stats = {
            "total": 0,
            "success": 0,
            "failed": 0
        }
        
        # Procura por padrões comuns
        for line in output.split("\n"):
            if "Total de links" in line and ":" in line:
                try:
                    stats["total"] = int(line.split(":")[-1].strip())
                except:
                    pass
            elif "✅ Funcionais" in line:
                try:
                    stats["success"] = int(line.split(":")[-1].strip())
                except:
                    pass
            elif "❌ Com problemas" in line:
                try:
                    stats["failed"] = int(line.split(":")[-1].strip())
                except:
                    pass
        
        return stats
    
    def send_alert(self, result, icon):
        """Envia alerta específico baseado no resultado"""
        stats = result.get("stats", {})
        
        if result["status"] == "error":
            title = "Validação FALHOU"
            message = result.get("error", "Erro desconhecido")
        else:
            total = stats.get("total", 0)
            failed = stats.get("failed", 0)
            title = f"Validação: {failed}/{total} links com problema"
            message = f"Total: {total}\nOK: {stats.get('success', 0)}\nProblemas: {failed}"
        
        self.send_telegram_alert(title, message, icon)
    
    def save_history(self, result):
        """Salva resultado no histórico"""
        history = []
        
        # Carrega histórico existente
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    history = json.load(f)
            except:
                pass
        
        # Adiciona novo resultado
        history.append(result)
        
        # Mantém apenas últimos 30 dias
        cutoff_date = time.time() - (30 * 24 * 3600)
        history = [h for h in history 
                  if datetime.fromisoformat(h["timestamp"]).timestamp() > cutoff_date]
        
        # Salva
        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)
        
        print(f"✅ Resultado salvo no histórico")
    
    def get_summary(self):
        """Retorna resumo do histórico"""
        if not self.history_file.exists():
            return {"total_tests": 0, "success_rate": 0}
        
        try:
            with open(self.history_file) as f:
                history = json.load(f)
            
            if not history:
                return {"total_tests": 0, "success_rate": 0}
            
            success_count = len([h for h in history if h["status"] == "success"])
            total = len(history)
            
            return {
                "total_tests": total,
                "successful": success_count,
                "failed": total - success_count,
                "success_rate": (success_count / total * 100) if total > 0 else 0,
                "last_test": history[-1]["timestamp"] if history else None
            }
        except:
            return {"total_tests": 0, "success_rate": 0}


def main():
    scheduler = ValidationScheduler()
    
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        # Mostrar resumo
        summary = scheduler.get_summary()
        print(f"\n📊 Resumo de Validações")
        print(f"   Total de testes: {summary['total_tests']}")
        print(f"   Sucesso: {summary.get('successful', 0)}")
        print(f"   Falhas: {summary.get('failed', 0)}")
        print(f"   Taxa de sucesso: {summary.get('success_rate', 0):.1f}%")
        print(f"   Último teste: {summary.get('last_test', 'N/A')}")
    else:
        # Executar validação
        url = sys.argv[1] if len(sys.argv) > 1 else "https://www.rpa4all.com/"
        result = scheduler.run_validation(url)
        
        print(f"\n{'='*70}")
        print(f"Status: {result['status'].upper()}")
        print(f"Stats: {result.get('stats', {})}")
        print(f"{'='*70}")
        
        sys.exit(0 if result['status'] == 'success' else 1)


if __name__ == "__main__":
    main()
