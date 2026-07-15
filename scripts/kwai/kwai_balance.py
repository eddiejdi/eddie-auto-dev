"""Saldo da conta Kwai — persistência local, env e scrape opcional."""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(
    os.getenv("KWAI_VIEWER_DATA_DIR", str(Path.home() / ".local/share/kwai-viewer"))
)
BALANCE_FILE = Path(os.getenv("KWAI_BALANCE_FILE", str(DEFAULT_DATA_DIR / "balance.json")))
HISTORY_FILE = Path(os.getenv("KWAI_BALANCE_HISTORY_FILE", str(DEFAULT_DATA_DIR / "balance-history.csv")))
DEFAULT_BALANCE_URL = os.getenv("KWAI_BALANCE_URL", "https://m-wallet.kwai.com/main/transfer")
KWAI_BALANCE_SCRAPE = os.getenv("KWAI_BALANCE_SCRAPE", "0").lower() in {"1", "true", "yes"}
KWAI_COOKIE_SOURCE = os.getenv(
    "KWAI_COOKIE_SOURCE",
    "/home/homelab/docker/kwai-browser/config/.config/chromium/Default/Cookies",
)
BALANCE_URLS = tuple(
    url.strip()
    for url in os.getenv(
        "KWAI_BALANCE_URLS",
        "https://m-wallet.kwai.com/main/transfer,https://m-wallet.kwai.com/,https://m-creative.kwai.com/creator/center,https://www.kwai.com/discover",
    ).split(",")
    if url.strip()
)
INVALID_PAGE_HINTS = (
    "page not found",
    "404",
    "cannot be found",
    "página não encontrada",
    "pagina nao encontrada",
    "foi excluída",
)
BALANCE_PATTERN = re.compile(
    r"(?:(?:R\$|BRL)\s*)?([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})|[0-9]+(?:[.,][0-9]{2})?)"
    r"|([0-9]+(?:[.,][0-9]+)?)\s*(?:moedas?|coins?|kwai|kwaizinhos?)",
    re.IGNORECASE,
)
MONEY_PATTERN = re.compile(
    r"(?:R\$|BRL)\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})|[0-9]+(?:[.,][0-9]{2})?)",
    re.IGNORECASE,
)
JSON_BALANCE_KEYS = (
    "balance",
    "walletBalance",
    "availableBalance",
    "cashBalance",
    "totalBalance",
    "coinBalance",
    "rewardAmount",
    "withdrawAmount",
    "availableAmount",
    "wallet_amount",
)
LOGIN_HINTS = (
    "entrar",
    "login",
    "sign in",
    "faça login",
    "fazer login",
    "continuar com",
    "qr code",
    "código qr",
)
WALLET_LABELS = (
    "carteira",
    "wallet",
    "saldo",
    "balance",
    "recompensa",
    "reward",
    "ganhos",
    "saque",
    "withdraw",
    "kwaizinho",
    "moeda",
)


@dataclass
class BalanceSnapshot:
    balance: float
    currency: str
    source: str
    updated_at: str
    raw_text: str | None = None
    url: str | None = None


def _normalize_amount(value: str) -> float:
    cleaned = value.strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def parse_kwai_wallet_text(text: str) -> tuple[float | None, str]:
    if not text:
        return None, "BRL"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[tuple[float, str]] = []

    for index, line in enumerate(lines):
        lower = line.lower()
        # Captura qualquer número após "cash" (pode ser 0 ou valor real)
        if lower == "cash" and index + 1 < len(lines):
            try:
                val = _normalize_amount(lines[index + 1])
                candidates.append((val, "BRL"))
            except ValueError:
                pass
        if lower in {"carteira", "saldo", "dinheiro"} and index + 1 < len(lines):
            try:
                candidates.append((_normalize_amount(lines[index + 1]), "BRL"))
            except ValueError:
                pass
        if "kwai gold" in lower and index + 1 < len(lines):
            try:
                candidates.append((_normalize_amount(lines[index + 1]), "KWG"))
            except ValueError:
                pass
        if lower.startswith("r$"):
            try:
                candidates.append((_normalize_amount(lower.replace("r$", "", 1)), "BRL"))
            except ValueError:
                pass

    if candidates:
        # Retorna o maior valor > 0, ou 0 se só houver zeros
        positive = [c for c in candidates if c[0] > 0]
        if positive:
            return max(positive, key=lambda x: x[0])
        return candidates[0]

    return None, "BRL"


def parse_balance_from_text(text: str) -> float | None:
    wallet_amount, _currency = parse_kwai_wallet_text(text)
    if wallet_amount is not None:
        return wallet_amount

    if not text:
        return None

    candidates: list[float] = []
    keywords = ("saldo", "balance", "carteira", "wallet", "moeda", "coin", "kwai", "disponível", "kwaizinho")
    for line in text.splitlines():
        lower = line.lower()
        if not any(keyword in lower for keyword in keywords):
            continue
        for match in BALANCE_PATTERN.finditer(line):
            amount = match.group(1) or match.group(2)
            if not amount:
                continue
            try:
                candidates.append(_normalize_amount(amount))
            except ValueError:
                continue

    if not candidates:
        money_hits = [MONEY_PATTERN.search(line) for line in text.splitlines()]
        for hit in money_hits:
            if hit:
                try:
                    candidates.append(_normalize_amount(hit.group(1)))
                except ValueError:
                    continue

    if not candidates:
        return None
    return max(candidates)


def page_is_invalid(text: str) -> bool:
    lower = (text or "").lower()
    return any(hint in lower for hint in INVALID_PAGE_HINTS)


def parse_balance_from_html(html: str, *, body_text: str | None = None) -> float | None:
    if not html:
        return None

    visible = body_text if body_text is not None else re.sub(r"<[^>]+>", " ", html)
    if page_is_invalid(visible):
        return None

    candidates: list[float] = []
    for key in JSON_BALANCE_KEYS:
        for match in re.finditer(rf'"{key}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', html, re.IGNORECASE):
            try:
                value = float(match.group(1))
                if value <= 10000:
                    candidates.append(value)
            except ValueError:
                continue

    text_parsed = parse_balance_from_text(visible)
    if text_parsed is not None:
        candidates.append(text_parsed)

    if not candidates:
        return None
    return max(candidates)


def login_required(text: str) -> bool:
    lower = (text or "").lower()
    return any(hint in lower for hint in LOGIN_HINTS)


def _click_visible(driver, labels: tuple[str, ...]) -> bool:
    from selenium.webdriver.common.by import By

    for label in labels:
        xpath = (
            "//*[self::button or self::a or @role='button' or self::span or self::div]"
            f"[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label.lower()}')]"
        )
        for element in driver.find_elements(By.XPATH, xpath):
            if not element.is_displayed():
                continue
            try:
                driver.execute_script("arguments[0].click();", element)
                time.sleep(2)
                return True
            except Exception:
                continue
    return False


def _navigate_to_wallet(driver) -> None:
    from selenium.webdriver.common.by import By

    profile_xpaths = (
        "//*[contains(@href,'profile')]",
        "//*[contains(@aria-label,'Profile') or contains(@aria-label,'Perfil')]",
        "//*[contains(@class,'profile') or contains(@class,'avatar')]",
        "//footer//a[last()]",
        "//nav//a[last()]",
    )
    for xpath in profile_xpaths:
        for element in driver.find_elements(By.XPATH, xpath):
            if not element.is_displayed():
                continue
            try:
                driver.execute_script("arguments[0].click();", element)
                time.sleep(3)
                if _click_visible(driver, WALLET_LABELS):
                    return
            except Exception:
                continue

    _click_visible(driver, WALLET_LABELS)


def _expand_wallet_sections(driver) -> None:
    """Tenta expandir seções de saldo (cash, Kwai Golds) clicando nelas."""
    from selenium.webdriver.common.by import By

    for label in ("cash", "carteira", "saldo", "kwai gold", "recompensa"):
        try:
            xpath = f"//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label}')]"
            for el in driver.find_elements(By.XPATH, xpath):
                if el.is_displayed():
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(1.5)
                    except Exception:
                        pass
        except Exception:
            continue


def _collect_page_payload(driver) -> tuple[str, str]:
    body_text = driver.find_element("tag name", "body").text or ""
    page_source = driver.page_source or ""
    return body_text, page_source


def _import_cookies_from_sqlite(driver, cookie_db: Path) -> int:
    import sqlite3

    if not cookie_db.is_file():
        logger.info("Cookie DB nao encontrado: %s", cookie_db)
        return 0

    loaded = 0
    try:
        rows = sqlite3.connect(str(cookie_db)).execute(
            "SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly FROM cookies"
        ).fetchall()
    except Exception:
        logger.exception("Falha ao ler cookies de %s", cookie_db)
        return 0

    for host_key, name, value, path, expires_utc, is_secure, is_httponly in rows:
        if "kwai" not in (host_key or ""):
            continue
        domain = host_key.lstrip(".")
        try:
            driver.get(f"https://{domain}/")
            time.sleep(1)
        except Exception:
            continue
        cookie = {
            "name": name,
            "value": value,
            "domain": host_key,
            "path": path or "/",
            "secure": bool(is_secure),
        }
        if expires_utc:
            cookie["expiry"] = int(expires_utc)
        try:
            driver.add_cookie(cookie)
            loaded += 1
        except Exception:
            continue
    logger.info("Cookies Kwai importados: %s", loaded)
    return loaded


def _save_debug_artifacts(data_dir: Path, *, url: str, body_text: str, page_source: str, driver) -> None:
    debug_dir = data_dir / "balance-debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    (debug_dir / f"{stamp}_body.txt").write_text(body_text[:8000], encoding="utf-8")
    (debug_dir / f"{stamp}_source.html").write_text(page_source[:20000], encoding="utf-8")
    try:
        driver.save_screenshot(str(debug_dir / f"{stamp}.png"))
    except Exception:
        pass
    logger.info("Debug salvo em %s (url=%s)", debug_dir, url)


def _parse_page(driver, *, url: str) -> tuple[float | None, str, str, str]:
    from scripts.kwai.kwai_viewer import _dismiss_consent

    driver.get(url)
    time.sleep(8)
    _dismiss_consent(driver)
    _navigate_to_wallet(driver)
    time.sleep(4)
    _expand_wallet_sections(driver)
    time.sleep(3)
    body_text, page_source = _collect_page_payload(driver)
    if page_is_invalid(body_text) or login_required(body_text):
        return None, body_text, page_source, "BRL"
    parsed, currency = parse_kwai_wallet_text(body_text)
    if parsed is None:
        parsed = parse_balance_from_text(body_text)
        currency = "BRL"
    if parsed is None:
        parsed = parse_balance_from_html(page_source, body_text=body_text)
        currency = "BRL"
    if parsed is not None:
        return parsed, body_text, page_source, currency
    return None, body_text, page_source, "BRL"


def scrape_balance_from_driver(
    driver,
    *,
    urls: tuple[str, ...] = BALANCE_URLS,
    cookie_source: str | None = None,
) -> BalanceSnapshot | None:
    data_dir = DEFAULT_DATA_DIR
    best: BalanceSnapshot | None = None

    cookie_db = Path(cookie_source or KWAI_COOKIE_SOURCE)
    if cookie_db.is_file():
        _import_cookies_from_sqlite(driver, cookie_db)

    for url in urls:
        try:
            parsed, body_text, page_source, currency = _parse_page(driver, url=url)
            _save_debug_artifacts(data_dir, url=url, body_text=body_text, page_source=page_source, driver=driver)
            if parsed is None:
                if page_is_invalid(body_text):
                    logger.warning("Pagina invalida ao extrair saldo Kwai (%s)", url)
                elif login_required(body_text):
                    logger.warning("Login necessario para extrair saldo Kwai (%s)", url)
                else:
                    logger.info("Nao foi possivel extrair saldo Kwai da pagina %s", url)
                continue
            if parsed > 1000:
                logger.warning("Valor suspeito ignorado (%.2f) em %s", parsed, url)
                continue
            snapshot = record_balance(
                parsed,
                currency=currency,
                source="scrape",
                raw_text=body_text[:500],
                url=url,
            )
            logger.info("Saldo Kwai extraido: %.2f BRL (%s)", parsed, url)
            return snapshot
        except Exception:
            logger.exception("Falha ao coletar saldo Kwai em %s", url)

    return best


def scrape_balance_with_browser(
    *,
    headless: bool = False,
    chrome_binary: str | None = None,
    urls: tuple[str, ...] = BALANCE_URLS,
) -> BalanceSnapshot | None:
    from scripts.kwai.kwai_browser import build_driver

    driver = None
    try:
        driver = build_driver(
            headless=headless,
            chrome_binary=chrome_binary,
            start_url=urls[0] if urls else DEFAULT_BALANCE_URL,
        )
        driver.set_page_load_timeout(60)
        return scrape_balance_from_driver(driver, urls=urls)
    finally:
        if driver is not None:
            driver.quit()


def load_balance(path: Path | None = None) -> BalanceSnapshot | None:
    path = path or BALANCE_FILE
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return BalanceSnapshot(
            balance=float(payload.get("balance") or 0),
            currency=str(payload.get("currency") or "BRL"),
            source=str(payload.get("source") or "unknown"),
            updated_at=str(payload.get("updated_at") or ""),
            raw_text=payload.get("raw_text"),
            url=payload.get("url"),
        )
    except (TypeError, ValueError):
        return None


def save_balance(
    snapshot: BalanceSnapshot,
    *,
    path: Path | None = None,
    history_path: Path | None = None,
) -> None:
    path = path or BALANCE_FILE
    history_path = history_path or HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(snapshot), indent=2, ensure_ascii=False), encoding="utf-8")

    history_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not history_path.exists() or history_path.stat().st_size == 0
    with history_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(["updated_at", "balance", "currency", "source"])
        writer.writerow([snapshot.updated_at, f"{snapshot.balance:.4f}", snapshot.currency, snapshot.source])


def record_balance(
    balance: float,
    *,
    currency: str = "BRL",
    source: str = "manual",
    raw_text: str | None = None,
    url: str | None = None,
    path: Path | None = None,
    history_path: Path | None = None,
) -> BalanceSnapshot:
    snapshot = BalanceSnapshot(
        balance=float(balance),
        currency=currency,
        source=source,
        updated_at=datetime.now(UTC).isoformat(),
        raw_text=raw_text,
        url=url,
    )
    save_balance(snapshot, path=path, history_path=history_path)
    return snapshot


def balance_from_env() -> BalanceSnapshot | None:
    raw = (os.getenv("KWAI_ACCOUNT_BALANCE") or "").strip()
    if not raw:
        return None
    try:
        return record_balance(
            float(raw.replace(",", ".")),
            currency=os.getenv("KWAI_ACCOUNT_CURRENCY", "BRL"),
            source="env",
        )
    except ValueError:
        logger.warning("KWAI_ACCOUNT_BALANCE invalido: %s", raw)
        return None


def refresh_balance(driver: Any | None = None) -> BalanceSnapshot | None:
    env_snapshot = balance_from_env()
    if env_snapshot is not None:
        return env_snapshot

    if driver is not None and KWAI_BALANCE_SCRAPE:
        scraped = scrape_balance_from_driver(driver)
        if scraped is not None:
            return scraped

    return load_balance()


def format_balance_line(snapshot: BalanceSnapshot | None) -> str | None:
    if snapshot is None:
        return None
    return f"Saldo Kwai: <b>{snapshot.balance:.2f} {snapshot.currency}</b> ({snapshot.source})"