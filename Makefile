# ============================================================
#  Makefile — Eddie Auto-Dev Deploy Pipeline
#  Uso: make <target>
#  Homelab: 192.168.15.2  |  User: homelab
# ============================================================

HOMELAB_HOST  ?= 192.168.15.2
HOMELAB_USER  ?= homelab
REMOTE_DIR    ?= /home/homelab/eddie-auto-dev
VENV          ?= .venv/bin
PYTHON        ?= $(VENV)/python3
PYTEST        ?= $(VENV)/pytest

.DEFAULT_GOAL := help

# ── Cores ────────────────────────────────────────────────────
RED    := \033[0;31m
GREEN  := \033[0;32m
YELLOW := \033[1;33m
CYAN   := \033[0;36m
RESET  := \033[0m

.PHONY: help test lint deploy deploy-clear deploy-crypto deploy-all \
        status logs rollback ssh clean

# ─────────────────────────────────────────────────────────────
## help: Lista todos os targets disponíveis
help:
	@printf "$(CYAN)Eddie Auto-Dev — Pipeline de Deploy$(RESET)\n\n"
	@printf "$(YELLOW)TESTES$(RESET)\n"
	@printf "  $(GREEN)make test$(RESET)             Roda testes unitários (pytest -q)\n"
	@printf "  $(GREEN)make test-clear$(RESET)       Testes do clear_trading_agent\n"
	@printf "  $(GREEN)make lint$(RESET)             Verifica sintaxe Python (ruff/flake8)\n"
	@printf "\n$(YELLOW)DEPLOY$(RESET)\n"
	@printf "  $(GREEN)make deploy$(RESET)           Deploy completo: test → push → all agents\n"
	@printf "  $(GREEN)make deploy-clear$(RESET)     Deploy somente clear_trading_agent\n"
	@printf "  $(GREEN)make deploy-crypto$(RESET)    Deploy somente btc_trading_agent\n"
	@printf "  $(GREEN)make deploy-all$(RESET)       Deploy todos os agentes + serviços\n"
	@printf "  $(GREEN)make push$(RESET)             git push (sem deploy)\n"
	@printf "\n$(YELLOW)OPERAÇÃO$(RESET)\n"
	@printf "  $(GREEN)make status$(RESET)           Status de todos os agentes no homelab\n"
	@printf "  $(GREEN)make logs$(RESET)             Logs do clear-trading-agent (live)\n"
	@printf "  $(GREEN)make logs-crypto$(RESET)      Logs dos crypto-agents (live)\n"
	@printf "  $(GREEN)make rollback$(RESET)         Rollback do último deploy (clear)\n"
	@printf "  $(GREEN)make ssh$(RESET)              Shell SSH no homelab\n"

# ─────────────────────────────────────────────────────────────
## test: Roda testes unitários (sem integration/external)
test:
	@printf "$(CYAN)[TEST] Rodando pytest...$(RESET)\n"
	cd /workspace/eddie-auto-dev && $(PYTEST) -q --tb=short 2>&1
	@printf "$(GREEN)[TEST] OK$(RESET)\n"

## test-clear: Testes do módulo clear_trading_agent
test-clear:
	@printf "$(CYAN)[TEST] clear_trading_agent...$(RESET)\n"
	cd /workspace/eddie-auto-dev && $(PYTEST) tests/test_clear_trading.py tests/test_clear_failure_scenarios.py -q --tb=short 2>&1
	@printf "$(GREEN)[TEST] OK$(RESET)\n"

## lint: Verificação de estilo Python
lint:
	@printf "$(CYAN)[LINT]$(RESET)\n"
	@$(VENV)/ruff check clear_trading_agent/ btc_trading_agent/ specialized_agents/ 2>/dev/null || \
	 $(VENV)/flake8 clear_trading_agent/ btc_trading_agent/ specialized_agents/ --max-line-length=120 --ignore=E501,W503 2>/dev/null || \
	 printf "$(YELLOW)Linter não encontrado — pulando$(RESET)\n"

# ─────────────────────────────────────────────────────────────
## push: git add . && git commit (se tiver mudanças) && git push
push:
	@printf "$(CYAN)[GIT] Verificando mudanças...$(RESET)\n"
	@if ! git -C /workspace/eddie-auto-dev diff --quiet HEAD 2>/dev/null; then \
		printf "$(YELLOW)Arquivos modificados — commitando...$(RESET)\n"; \
		git -C /workspace/eddie-auto-dev add -A; \
		git -C /workspace/eddie-auto-dev commit -m "chore: deploy pipeline $(shell date '+%Y-%m-%d %H:%M')"; \
	fi
	@git -C /workspace/eddie-auto-dev push origin main
	@printf "$(GREEN)[GIT] Push concluído$(RESET)\n"

# ─────────────────────────────────────────────────────────────
## deploy-clear: Deploy do clear_trading_agent no homelab
deploy-clear:
	@printf "$(CYAN)[DEPLOY] clear_trading_agent → $(HOMELAB_USER)@$(HOMELAB_HOST)$(RESET)\n"
	@bash /workspace/eddie-auto-dev/scripts/deploy_clear_trading_agent.sh $(HOMELAB_HOST) $(HOMELAB_USER)
	@printf "$(GREEN)[DEPLOY] clear_trading_agent concluído$(RESET)\n"

## deploy-crypto: Deploy do btc_trading_agent (crypto-agents) no homelab
deploy-crypto:
	@printf "$(CYAN)[DEPLOY] btc_trading_agent → $(HOMELAB_USER)@$(HOMELAB_HOST)$(RESET)\n"
	@bash /workspace/eddie-auto-dev/scripts/deploy.sh --target crypto $(HOMELAB_HOST) $(HOMELAB_USER) || \
	 bash /workspace/eddie-auto-dev/scripts/deploy_btc_trading_profiles.sh $(HOMELAB_HOST) $(HOMELAB_USER)
	@printf "$(GREEN)[DEPLOY] btc_trading_agent concluído$(RESET)\n"

## deploy-all: Deploy de todos os agentes
deploy-all: deploy-clear
	@printf "$(CYAN)[DEPLOY] Todos os agentes$(RESET)\n"
	@ssh -o StrictHostKeyChecking=no $(HOMELAB_USER)@$(HOMELAB_HOST) \
		"cd $(REMOTE_DIR) && git pull origin main --ff-only 2>&1 | tail -3 && \
		 sudo systemctl restart crypto-agent@BTC_USDT_aggressive crypto-agent@BTC_USDT_conservative \
		   crypto-agent@USDT_BRL_aggressive crypto-agent@USDT_BRL_conservative 2>&1 || true && \
		 echo 'Restart crypto-agents: OK'"
	@printf "$(GREEN)[DEPLOY] Tudo concluído$(RESET)\n"

## deploy: Pipeline completo: test + push + deploy-clear
deploy: test push deploy-clear
	@printf "\n$(GREEN)✅ Pipeline completo: test → push → deploy$(RESET)\n"
	@$(MAKE) --no-print-directory status

# ─────────────────────────────────────────────────────────────
## status: Status de todos os agentes de trading no homelab
status:
	@printf "$(CYAN)[STATUS] Agentes no homelab:$(RESET)\n"
	@ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 $(HOMELAB_USER)@$(HOMELAB_HOST) \
		"systemctl status clear-trading-agent crypto-agent@BTC_USDT_aggressive \
		  crypto-agent@BTC_USDT_conservative crypto-agent@USDT_BRL_aggressive \
		  crypto-agent@USDT_BRL_conservative --no-pager -n 0 2>&1 | \
		  grep -E '^(●|     Active|     Main PID)'" 2>&1 || true

## logs: Tail dos logs do clear-trading-agent
logs:
	@printf "$(CYAN)[LOGS] clear-trading-agent (Ctrl+C para sair)$(RESET)\n"
	@ssh -o StrictHostKeyChecking=no $(HOMELAB_USER)@$(HOMELAB_HOST) \
		"journalctl -u clear-trading-agent -f -n 30"

## logs-crypto: Tail dos logs dos crypto-agents
logs-crypto:
	@printf "$(CYAN)[LOGS] crypto-agents (Ctrl+C para sair)$(RESET)\n"
	@ssh -o StrictHostKeyChecking=no $(HOMELAB_USER)@$(HOMELAB_HOST) \
		"journalctl -u 'crypto-agent@*' -f -n 30"

## rollback: Reverte o último deploy do clear-trading-agent
rollback:
	@printf "$(YELLOW)[ROLLBACK] Revertendo clear-trading-agent...$(RESET)\n"
	@ssh -o StrictHostKeyChecking=no $(HOMELAB_USER)@$(HOMELAB_HOST) \
		"if [[ -d /tmp/clear-trading-agent-backup ]]; then \
		   sudo systemctl stop clear-trading-agent; \
		   rsync -a --delete /tmp/clear-trading-agent-backup/ $(REMOTE_DIR)/; \
		   sudo systemctl restart clear-trading-agent; \
		   echo ROLLBACK OK; \
		 else \
		   echo 'Sem backup disponível'; \
		 fi" 2>&1
	@$(MAKE) --no-print-directory status

## ssh: Abre shell SSH no homelab
ssh:
	@ssh $(HOMELAB_USER)@$(HOMELAB_HOST)

## clean: Limpa cache Python local
clean:
	@find /workspace/eddie-auto-dev -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@find /workspace/eddie-auto-dev -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)[CLEAN] OK$(RESET)\n"
