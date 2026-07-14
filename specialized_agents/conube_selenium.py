"""Remediação via Selenium no portal Conube."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

CONUBE_FECHAMENTOS_URL = os.getenv(
    "CONUBE_FECHAMENTOS_URL",
    "https://app.conube.com.br/contabil/fechamentos-contabeis?&cd=0",
)
CONUBE_TAREFAS_URL = os.getenv(
    "CONUBE_TAREFAS_URL",
    "https://app.conube.com.br/tarefas?&cd=0",
)


def _wait(agent: Any, condition: Any) -> Any:
    from selenium.webdriver.support.ui import WebDriverWait

    timeout = getattr(agent, "timeout_seconds", 25.0)
    return WebDriverWait(agent.driver, timeout).until(condition)


def _wait_for_document_ready(agent: Any) -> None:
    _wait(agent, lambda driver: driver.execute_script("return document.readyState") == "complete")


def _find_visible_elements(agent: Any, xpath: str) -> list[Any]:
    from selenium.webdriver.common.by import By

    elements = agent.driver.find_elements(By.XPATH, xpath)
    return [element for element in elements if element.is_displayed()]


def _body_text(agent: Any) -> str:
    try:
        return (agent.driver.find_element("tag name", "body").text or "").strip()
    except Exception:
        return ""


def _click_first_text(agent: Any, *texts: str) -> bool:
    normalized_texts = [text.strip() for text in texts if text.strip()]
    if not normalized_texts:
        return False

    for text in normalized_texts:
        xpath = (
            "//*[self::a or self::button or @role='button' or self::span or self::div or self::label]"
            f"[contains(translate(normalize-space(.), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÀÃÂÉÊÍÓÔÕÚÇ', 'abcdefghijklmnopqrstuvwxyzáàãâéêíóôõúç'), "
            f"\"{text.lower()}\")]"
        )
        for element in _find_visible_elements(agent, xpath):
            try:
                agent.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                agent.driver.execute_script("arguments[0].click();", element)
                time.sleep(0.4)
                return True
            except Exception:
                continue
    return False


def _collect_pending_balance_rows(agent: Any) -> list[Any]:
    selectors = [
        "//tr[.//*[contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'atras') or contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'pendent')]]",
        "//*[contains(@class, 'pend') or contains(@class, 'late')]",
        "//div[.//*[contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'atras') or contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'pendent')]]",
    ]
    rows: list[Any] = []
    for xpath in selectors:
        try:
            found = agent.driver.find_elements("xpath", xpath)
        except Exception:
            continue
        for item in found:
            if item.is_displayed() and item not in rows:
                rows.append(item)
    return rows


def _extract_competence_label(element: Any) -> str:
    text = " ".join((element.text or "").split())
    return text[:120] if text else "competencia-sem-identificacao"


def _mark_current_balance_without_movement(agent: Any) -> None:
    from selenium.webdriver.common.by import By

    if not _click_first_text(
        agent,
        "Sem movimentacao",
        "Sem movimentação",
        "Nao houve movimentacao",
        "Não houve movimentação",
        "Inativa",
        "Sem movimento",
    ):
        checkbox_selectors = [
            "//input[@type='checkbox' and (contains(@name, 'mov') or contains(@id, 'mov'))]",
            "//label[contains(., 'Sem moviment')]/preceding::input[1]",
            "//label[contains(., 'Nao houve moviment')]/preceding::input[1]",
        ]
        toggled = False
        for xpath in checkbox_selectors:
            for element in _find_visible_elements(agent, xpath):
                try:
                    agent.driver.execute_script("arguments[0].click();", element)
                    toggled = True
                    break
                except Exception:
                    continue
            if toggled:
                break
        if not toggled:
            raise RuntimeError("Nao foi possivel localizar a opcao sem movimentacao.")

    if not _click_first_text(
        agent,
        "Encerrar balanco",
        "Encerrar balanço",
        "Fechar balanco",
        "Fechar balanço",
        "Salvar",
        "Confirmar",
    ):
        try:
            agent.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        except Exception as exc:
            raise RuntimeError("Nao foi possivel confirmar o encerramento do balanco.") from exc


def close_overdue_balances_without_movement(agent: Any, *, limit: int = 12) -> dict[str, Any]:
    if limit < 1:
        raise RuntimeError("O limite informado para fechamento precisa ser maior que zero.")

    login_result = agent.login()
    if not login_result.get("authenticated"):
        return {
            "status": "error",
            "processed": 0,
            "results": [],
            "message": str(login_result.get("failure_reason") or "Login da Conube nao autenticou."),
        }

    agent.driver.get(CONUBE_FECHAMENTOS_URL)
    _wait_for_document_ready(agent)
    _wait(
        agent,
        lambda driver: any(
            marker in (_body_text(agent).lower())
            for marker in (
                "fechamentos contábeis",
                "fechamentos contabeis",
                "não há nada por aqui",
                "nao ha nada por aqui",
                "competência",
                "competencia",
            )
        ),
    )

    body_text = _body_text(agent).lower()
    if "não há nada por aqui" in body_text or "nao ha nada por aqui" in body_text:
        return {
            "status": "ok",
            "processed": 0,
            "results": [],
            "message": "Nenhum fechamento contábil pendente encontrado.",
        }

    pending_rows = _collect_pending_balance_rows(agent)
    if not pending_rows:
        return {
            "status": "ok",
            "processed": 0,
            "results": [],
            "message": "Nenhum balanco pendente encontrado.",
        }

    results: list[dict[str, str]] = []
    for row in pending_rows[:limit]:
        competence = _extract_competence_label(row)
        try:
            agent.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
            try:
                row.click()
            except Exception:
                action_clicked = False
                for xpath in (
                    ".//*[self::a or self::button][contains(., 'Abrir') or contains(., 'Editar') or contains(., 'Tratar')]",
                    ".//*[self::a or self::button][contains(., 'Pend') or contains(., 'Atras')]",
                ):
                    try:
                        action = row.find_element("xpath", xpath)
                        agent.driver.execute_script("arguments[0].click();", action)
                        action_clicked = True
                        break
                    except Exception:
                        continue
                if not action_clicked:
                    raise RuntimeError("Nao foi possivel abrir a competencia pendente.")

            _mark_current_balance_without_movement(agent)
            results.append(
                {
                    "competence": competence,
                    "status": "closed",
                    "message": "Encerrado como sem movimentacao.",
                }
            )
            agent.driver.get(CONUBE_FECHAMENTOS_URL)
            _wait_for_document_ready(agent)
            time.sleep(0.8)
        except Exception as exc:
            results.append(
                {
                    "competence": competence,
                    "status": "error",
                    "message": str(exc),
                }
            )

    processed = len([item for item in results if item["status"] == "closed"])
    return {
        "status": "ok" if processed else "warning",
        "processed": processed,
        "results": results,
    }


def _collect_task_rows(agent: Any) -> list[Any]:
    selectors = [
        "//tr[.//*[contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'atras') or contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'pendent')]]",
        "//*[contains(@class, 'task') or contains(@class, 'tarefa')][.//*[contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'atras') or contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'pendent')]]",
        "//div[contains(@class, 'card')][.//*[contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'atras') or contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'pendent')]]",
    ]
    rows: list[Any] = []
    for xpath in selectors:
        for item in _find_visible_elements(agent, xpath):
            if item not in rows:
                rows.append(item)
    return rows


def _extract_task_subject(element: Any) -> str:
    text = " ".join((element.text or "").split())
    return text[:160] if text else "tarefa-sem-assunto"


def _attempt_task_completion(agent: Any, subject: str) -> tuple[str, str]:
    lowered = subject.lower()
    if "informe de rendimentos" in lowered:
        if _click_first_text(agent, "Concluir", "Concluída", "Finalizar", "Enviar"):
            return "conclude", "completed"
    if "tfe" in lowered and "taxa municipal" in lowered:
        if _click_first_text(agent, "Solicitar recalculo", "Solicitar recálculo", "Recalcular"):
            return "request_recalculation", "updated"
    if _click_first_text(agent, "Concluir", "Transmitir", "Enviar", "Finalizar", "Confirmar", "Salvar"):
        return "ui_action", "submitted"
    return "none", "unsupported"


def remediate_pending_tasks_selenium(agent: Any, *, limit: int = 20) -> dict[str, Any]:
    if limit < 1:
        raise RuntimeError("O limite informado para tarefas precisa ser maior que zero.")

    login_result = agent.login()
    if not login_result.get("authenticated"):
        return {
            "status": "error",
            "processed": 0,
            "results": [],
            "message": str(login_result.get("failure_reason") or "Login da Conube nao autenticou."),
        }

    opened = False
    if not _click_first_text(agent, "Tarefas"):
        agent.driver.get(CONUBE_TAREFAS_URL)
        opened = True
    _wait_for_document_ready(agent)
    time.sleep(1.2)

    body_text = _body_text(agent).lower()
    if "nao ha tarefas" in body_text or "não há tarefas" in body_text:
        return {
            "status": "ok",
            "processed": 0,
            "results": [],
            "message": "Nenhuma tarefa pendente visivel na UI.",
        }

    task_rows = _collect_task_rows(agent)
    if not task_rows:
        return {
            "status": "ok",
            "processed": 0,
            "results": [],
            "message": "Nenhuma tarefa em atraso encontrada na UI.",
            "opened_via_url": opened,
        }

    results: list[dict[str, Any]] = []
    for row in task_rows[:limit]:
        subject = _extract_task_subject(row)
        try:
            agent.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
            try:
                row.click()
            except Exception:
                for xpath in (
                    ".//*[self::a or self::button][contains(., 'Abrir') or contains(., 'Ver') or contains(., 'Tratar')]",
                    ".//*[self::a or self::button]",
                ):
                    try:
                        action = row.find_element("xpath", xpath)
                        agent.driver.execute_script("arguments[0].click();", action)
                        break
                    except Exception:
                        continue

            time.sleep(0.8)
            action, outcome = _attempt_task_completion(agent, subject)
            results.append(
                {
                    "subject": subject,
                    "action": action,
                    "result": outcome,
                    "status": "completed" if outcome in {"completed", "updated", "submitted"} else outcome,
                }
            )
            if opened:
                agent.driver.get(CONUBE_TAREFAS_URL)
            elif not _click_first_text(agent, "Tarefas", "Voltar"):
                agent.driver.back()
            _wait_for_document_ready(agent)
            time.sleep(0.6)
        except Exception as exc:
            results.append(
                {
                    "subject": subject,
                    "action": "none",
                    "result": "error",
                    "status": "error",
                    "message": str(exc),
                }
            )

    processed = len([item for item in results if item.get("status") == "completed"])
    return {
        "status": "ok" if processed else "warning",
        "processed": processed,
        "results": results,
    }