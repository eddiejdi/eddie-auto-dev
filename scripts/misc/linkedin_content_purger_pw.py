#!/usr/bin/env python3
"""LinkedIn Content Purger (Playwright/web-agent) — Exclui posts e comentários antigos.

Usa o Browser do web-agent (/home/edenilson/web-agent) com perfil persistente
(~/.web-agent/browser-profile) — reutiliza a sessão LinkedIn já logada.

Uso (rodar com o venv do web-agent):
  /home/edenilson/web-agent/.venv/bin/python scripts/misc/linkedin_content_purger_pw.py
  ... --cutoff 2026-02-28 [--execute] [--only posts|comments] [--headless]

Sem --execute é DRY-RUN: só gera relatório JSON em data/linkedin_purge/.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/home/edenilson/web-agent")
from agent.browser import Browser  # noqa: E402

import argparse
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from playwright.sync_api import Page


# ---------------------------- Config ---------------------------- #

LINKEDIN_BASE = "https://www.linkedin.com"
ACTION_DELAY = 3.0          # delay entre deleções (anti rate-limit)
SCROLL_PAUSE_MS = 2000      # pause entre scrolls
MAX_SCROLLS = 60            # segurança contra loop infinito
BOUNDARY_DAYS = 45          # margem para buscar data exata
TZ = datetime.now().astimezone().tzinfo
DATA_DIR = Path("data/linkedin_purge")
REPORT_FILE = DATA_DIR / "purge_report.json"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# ---------------------------- Types ---------------------------- #

@dataclass
class ActivityItem:
    kind: str             # "post" ou "comment"
    urn: str              # URN do LinkedIn (ex: urn:li:activity:...)
    permalink: str        # URL direto pro item (pode estar vazio)
    date_text: str        # texto legível (ex: "2 h", "3 sem")
    date_exact: str = ""  # ISO 8601 se obtida via permalink
    date_estimated: str = ""  # ISO 8601 estimada a partir de date_text
    eligible: bool = False    # dentro do corte?
    deleted: bool = False     # deletado com sucesso?
    error: str = ""         # motivo da falha (se houver)
    text_preview: str = ""    # preview do conteúdo (para logs)

# ---------------------------- Helpers ---------------------------- #

def parse_relative_date(text: str, now: datetime) -> datetime | None:
    """Converte texto relativo como '2 h' ou '3 sem' para datetime."""
    if not text:
        return None
    text = text.lower().strip()
    # Remove pontuação e espaços extras
    text = re.sub(r"[^\w\s]", "", text)
    # Casos especiais
    if "agora" in text or "just now" in text:
        return now
    # Expressões como "2 h", "3 horas", "45 min", "2 dias", "1 semana", "2 m", "3 a", etc.
    m = re.search(r"(\d+)\s*(h|hora|horas|m|min|minuto|minutos|d|dia|dias|sem|semana|semanas|mês|meses|a|ano|anos)", text)
    if not m:
        return None
    qtd, unidade = int(m.group(1)), m.group(2)
    mult = {"h": 1/24, "hora": 1/24, "horas": 1/24,
            "min": 1/1440, "minuto": 1/1440, "minutos": 1/1440,
            "d": 1, "dia": 1, "dias": 1,
            "sem": 7, "semana": 7, "semanas": 7,
            "m": 30, "mês": 30, "meses": 30,
            "a": 365, "ano": 365, "anos": 365}.get(unidade[:3] if len(unidade) > 1 else unidade)
    if mult is None:
        return None
    return now - timedelta(days=qtd * mult)


def scroll_to_bottom(page: Page) -> None:
    """Rola até o fim da página (infinite scroll)."""
    last_height = page.evaluate("() => document.body.scrollHeight")
    while True:
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        new_height = page.evaluate("() => document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def goto_retry(page, url: str, retries: int = 3) -> None:
    for attempt in range(retries):
        try:
            page.goto(url, wait_until="domcontentloaded")
            return
        except Exception as e:
            if attempt == retries - 1:
                raise
            logger.warning(f"⚠️ goto falhou ({e.__class__.__name__}), retry {attempt + 1}/{retries}: {url}")
            page.wait_for_timeout(3000)


# ---------------------------- Core Logic ---------------------------- #

def ensure_login(page, email: str, password: str) -> bool:
    page.goto(f"{LINKEDIN_BASE}/feed/", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    if "/feed" in page.url:
        logger.info("✅ Sessão LinkedIn ativa (perfil persistente)")
        return True

    logger.info("🔑 Sessão ausente — tentando login com credenciais")
    page.goto(f"{LINKEDIN_BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    try:
        page.locator("input[autocomplete='username'], input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        page.locator("button[type='submit']").first.click()
        page.wait_for_timeout(6000)
        if "/feed" in page.url:
            logger.info("✅ Login automático OK")
            return True
    except Exception as e:
        logger.warning(f"⚠️ Login automático falhou: {e}")

    logger.info("🔑 Aguardando login manual no navegador (300s)...")
    for _ in range(300):
        page.wait_for_timeout(1000)
        if "/feed" in page.url:
            logger.info("✅ Login manual detectado")
            return True
    return False


def get_profile_slug(page) -> str:
    page.goto(f"{LINKEDIN_BASE}/in/me/", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    m = re.search(r"/in/([^/?]+)", page.url)
    if not m:
        raise RuntimeError(f"Slug do perfil não encontrado (url={page.url})")
    slug = m.group(1)
    logger.info(f"👤 Perfil: {slug}")
    return slug


def comment_permalink(urn: str) -> str:
    """urn:li:comment:(activity:AAA,BBB) → permalink do post com comentário destacado."""
    m = re.match(r"urn:li:comment:\(activity:(\d+),(\d+)\)", urn)
    if not m:
        return ""
    from urllib.parse import quote
    return f"{LINKEDIN_BASE}/feed/update/urn:li:activity:{m.group(1)}?commentUrn={quote(urn, safe='')}"


def fetch_exact_date(page, item: ActivityItem) -> None:
    """Navega pro permalink e tenta extrair a data exata (ISO 8601) do <time datetime>."""
    if not item.permalink:
        return
    try:
        goto_retry(page, item.permalink)
        # Tentativa 1: <time datetime> (mais confiável)
        time_el = page.locator("time[datetime]").first
        if time_el.count():
            dt = time_el.get_attribute("datetime")
            if dt:
                item.date_exact = dt
                return
        # Tentativa 2: texto visível do <time> (menos confiável, mas útil)
        time_el = page.locator("time").first
        if time_el.count():
            txt = time_el.inner_text().strip()
            if txt:
                # Tenta interpretar como data relativa ou absoluta
                parsed = parse_relative_date(txt, datetime.now(TZ))
                if parsed:
                    item.date_exact = parsed.isoformat()
        # Tentativa 3: meta tags ou JSON-LD (fallback avançado)
        # (não implementado por ser específico demais do LinkedIn)
    except Exception as e:
        logger.debug(f"Falha ao buscar data exata para {item.urn}: {e}")


def collect_activity(page, slug: str, kind: str) -> list[ActivityItem]:
    tab = "shares" if kind == "post" else "comments"
    url = f"{LINKEDIN_BASE}/in/{slug}/recent-activity/{tab}/"
    logger.info(f"📥 Coletando {kind}s: {url}")
    goto_retry(page, url)
    try:
        page.wait_for_url("**/recent-activity/**", timeout=10000)
    except Exception:
        pass
    try:
        page.wait_for_selector("div[data-urn], .comments-comment-entity[data-id]", timeout=15000)
    except Exception:
        logger.warning(f"⚠️ Nenhum item apareceu em {page.url} — pode estar vazio ou bloqueado")
    page.wait_for_timeout(3000)
    scroll_to_bottom(page)

    if kind == "comment":
        raw = page.evaluate(
            """() => {
            const out = [];
            for (const c of document.querySelectorAll('.comments-comment-entity[data-id]')) {
              const urn = c.getAttribute('data-id') || '';
              const t = c.querySelector('time');
              const dateText = t ? (t.textContent || '').trim() : '';
              let preview = '';
              const p = c.querySelector(
                '.comments-comment-item__main-content, [class*="main-content"], .comments-comment-item-content-body'
              );
              if (p) preview = (p.textContent || '').trim().slice(0, 200);
              if (urn) out.push({urn, permalink: '', dateText, preview});
            }
            return out;
            }"""
        )
    else:
        # IMPROVED: Better permalink extraction for posts
        raw = page.evaluate(
            """() => {
            const out = [];
            const cards = document.querySelectorAll('div[data-urn]');
            for (const card of cards) {
              const urn = card.getAttribute('data-urn') || '';
              if (!urn.includes(':activity:')) continue;
              
              // MULTIPLE STRATEGIES TO FIND PERMALINK
              let permalink = '';
              
              // Strategy 1: Look for link with href containing the URN
              for (const a of card.querySelectorAll(':scope > * a[href]')) {
                const h = a.href.split('?')[0];
                if ((h.includes('/feed/update/') || h.includes('/posts/')) && h.includes(urn)) {
                  permalink = h; break;
                }
              }
              
              // Strategy 2: Look for any link that looks like a post permalink
              if (!permalink) {
                for (const a of card.querySelectorAll('a[href]')) {
                  const h = a.href.split('?')[0];
                  if (h.includes('/feed/update/') || h.includes('/posts/')) {
                    // Check if this looks like it belongs to this post
                    // Often the URL contains the numeric part of the URN
                    const urnNum = urn.replace('urn:li:activity:', '');
                    if (h.includes(urnNum)) {
                      permalink = h;
                      break;
                    }
                  }
                }
              }
              
              // Strategy 3: Construct from URN as fallback
              if (!permalink && urn.startsWith('urn:li:activity:')) {
                permalink = 'https://www.linkedin.com/feed/update/' + urn + '/';
              }
              
              let dateText = '';
              const t = card.querySelector('time');
              if (t) dateText = (t.getAttribute('datetime') || t.textContent || '').trim();
              if (!dateText) {
                const s = card.querySelector(
                  'span.feed-shared-actor__sub-description, span.update-components-actor__sub-description'
                );
                if (s) dateText = (s.textContent || '').trim();
              }
              let preview = '';
              const p = card.querySelector(
                'div.feed-shared-text, div.update-components-text, span.break-words'
              );
              if (p) preview = (p.textContent || '').trim().slice(0, 200);
              if (urn || permalink) out.push({urn, permalink, dateText, preview});
            }
            return out;
            }"""
        )

    items: list[ActivityItem] = []
    seen: set[str] = set()
    for r in raw:
        key = r["urn"] or r["permalink"]
        if not key or key in seen:
            continue
        seen.add(key)
        permalink = r["permalink"]
        if kind == "comment" and not permalink:
            permalink = comment_permalink(r["urn"])
        if kind == "post" and not permalink and r["urn"].startswith("urn:li:activity:"):
            permalink = f"{LINKEDIN_BASE}/feed/update/{r['urn']}/"
        items.append(
            ActivityItem(
                kind=kind,
                urn=r["urn"],
                permalink=permalink,
                date_text=r["dateText"],
                text_preview=r["preview"],
            )
        )
    logger.info(f"📥 Coletados: {len(items)} {kind}s")
    return items


def delete_comment_in_page(page, slug: str, item: ActivityItem) -> bool:
    """Deleta comentário navegando pro permalink do post e localizando o comentário lá."""
    if not item.permalink:
        item.error = "sem permalink"
        return False
    url = item.permalink
    try:
        goto_retry(page, url)
        try:
            page.wait_for_selector("div[data-urn], .comments-comment-entity[data-id]", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        # Procura pelo comentário pelo data-id (URN do comentário)
        target = None
        for _ in range(MAX_SCROLLS):
            loc = page.locator(f".comments-comment-entity[data-id=\"{item.urn}\"]")
            if loc.count():
                target = loc.first
                break
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(SCROLL_PAUSE_MS)
        if target is None:
            item.error = "comentário não encontrado no post"
            return False
        target.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        # Menu de três pontinhos do comentário
        trigger = target.locator(
            "button[aria-label*='Comentar opções'], "
            "button[aria-label*='Comment options'], "
            "button[aria-label*='opções de comentário']"
        ).first
        if not trigger.count():
            item.error = "menu de comentário não encontrado"
            return False
        trigger.click()
        page.wait_for_timeout(1000)
        # Opção de exclusão
        opt = page.locator(
            ":is(li, div, a, span):has-text('Excluir'), "
            ":is(li, div, a, span):has-text('Delete')"
        ).last
        try:
            opt.wait_for(state="visible", timeout=4000)
        except Exception:
            pass
        if not opt.count():
            item.error = "opção excluir comentário não encontrada"
            page.keyboard.press("Escape")
            return False
        opt.click()
        page.wait_for_timeout(1000)
        # Confirmação
        confirm = page.locator(
            "button:has-text('Excluir'), button:has-text('Delete')"
        ).first
        try:
            confirm.wait_for(state="visible", timeout=4000)
        except Exception:
            pass
        if confirm.count():
            confirm.click()
            page.wait_for_timeout(2000)
            return True
        item.error = "confirmação de comentário não encontrada"
        return False
    except Exception as e:
        item.error = str(e)[:200]
        return False


def delete_post_in_page(page, slug: str, item: ActivityItem) -> bool:
    """Deleta post direto na lista de atividades (dropdown 'menu de controle' -> Excluir publicação).

    Navegar pro permalink individual não funciona para reposts (o menu do permalink
    mostra as opções do AUTOR ORIGINAL, não as do dono da própria republicação/post).
    """
    url = f"{LINKEDIN_BASE}/in/{slug}/recent-activity/shares/"
    try:
        goto_retry(page, url)
        try:
            page.wait_for_selector("div[data-urn]", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        target = None
        for _ in range(MAX_SCROLLS):
            loc = page.locator(f"div[data-urn=\"{item.urn}\"]")
            if loc.count():
                target = loc.first
                break
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(SCROLL_PAUSE_MS)
        if target is None:
            item.error = "post não encontrado na aba"
            return False

        target.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        
        # Find the menu trigger button (three dots / ellipsis)
        trigger = target.locator(
            "button[aria-label*='menu de controle'], "
            "button[aria-label*='control menu'], "
            "button[aria-label*='abrir menu'], "
            "button[aria-label*='open menu'], "
            "button[aria-label*='Mais opções'], "
            "button[aria-label*='More options'], "
            "button[aria-label*='opções']"
        ).first
        if not trigger.count():
            # Fallback: look for the ellipsis button by icon class
            trigger = target.locator(
                "button.artdeco-dropdown__trigger, "
                "button[aria-expanded], "
                "button[aria-label*='...']"
            ).first
        if not trigger.count():
            item.error = "menu não encontrado"
            return False
        
        trigger.click()
        page.wait_for_timeout(2000)

        # Search globally for delete option in any visible dropdown/menu
        # LinkedIn may use different dropdown structures
        delete_selectors = [
            # Direct text match in any visible element
            "li:has-text('Excluir publicação')",
            "li:has-text('Delete post')",
            "li:has-text('Excluir')",
            "li:has-text('Delete')",
            "li:has-text('Remover')",
            "li:has-text('Remove')",
            "li:has-text('Desfazer republicação')",
            "li:has-text('Undo repost')",
            # Button/link variants
            "button:has-text('Excluir publicação')",
            "button:has-text('Delete post')",
            "button:has-text('Excluir')",
            "button:has-text('Delete')",
            "a:has-text('Excluir')",
            "a:has-text('Delete')",
            # Role-based
            "[role='menuitem']:has-text('Excluir')",
            "[role='menuitem']:has-text('Delete')",
            # Artdeco dropdown items
            ".artdeco-dropdown__item:has-text('Excluir')",
            ".artdeco-dropdown__item:has-text('Delete')",
        ]
        
        opt = None
        for selector in delete_selectors:
            try:
                loc = page.locator(selector).last
                if loc.count() > 0 and loc.is_visible():
                    opt = loc
                    break
            except:
                continue
        
        if opt is None:
            item.error = "opção excluir não encontrada"
            page.keyboard.press("Escape")
            return False
        
        opt.click()
        page.wait_for_timeout(2000)

        # Confirm deletion - look for confirmation dialog
        confirm_selectors = [
            "button:has-text('Excluir')",
            "button:has-text('Delete')",
            "button:has-text('Confirmar')",
            "button:has-text('Confirm')",
            "button[data-control-name='confirm_delete']",
            ".artdeco-modal__actionbar button:has-text('Excluir')",
            ".artdeco-modal__actionbar button:has-text('Delete')",
        ]
        
        confirm = None
        for selector in confirm_selectors:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0 and loc.is_visible():
                    confirm = loc
                    break
            except:
                continue
        
        if confirm is not None:
            confirm.click()
            page.wait_for_timeout(3000)
            return True
        
        item.error = "confirmação não encontrada"
        return False
    except Exception as e:
        item.error = str(e)[:200]
        return False


def delete_item(page, item: ActivityItem, slug: str = "") -> bool:
    if item.kind == "comment" and slug:
        return delete_comment_in_page(page, slug, item)
    if item.kind == "post" and slug:
        return delete_post_in_page(page, slug, item)
    item.error = "sem slug"
    return False


# ---------------------------- Main ---------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", default="2026-02-28")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--only", choices=["posts", "comments"], default=None)
    parser.add_argument("--keep-text", action="append", default=[],
                        help="Trecho de texto de posts a PRESERVAR (repetível)")
    parser.add_argument("--report", default=str(REPORT_FILE))
    parser.add_argument("--limit", type=int, default=0, help="Limita exclusões a N itens (0 = sem limite)")
    args = parser.parse_args()

    cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=TZ
    )
    now = datetime.now(TZ)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    mode = "🔴 EXECUTE" if args.execute else "🟡 DRY-RUN"
    logger.info(f"{mode} — corte: {cutoff.date()} (inclusive)")

    email = os.environ.get("LINKEDIN_EMAIL", "")
    password = os.environ.get("LINKEDIN_PASSWORD", "")

    with Browser(headless=args.headless) as br:
        page = br.page
        if not ensure_login(page, email, password):
            logger.error("❌ Falha no login")
            return 1

        slug = get_profile_slug(page)

        kinds = {"posts": ["post"], "comments": ["comment"], None: ["post", "comment"]}[args.only]
        items: list[ActivityItem] = []
        for kind in kinds:
            items.extend(collect_activity(page, slug, kind))

        for item in items:
            estimated = parse_relative_date(item.date_text, now)
            boundary = estimated is not None and abs((estimated - cutoff).days) <= BOUNDARY_DAYS
            if estimated is None or (boundary and item.kind == "post"):
                fetch_exact_date(page, item)
            if estimated is not None:
                item.date_estimated = estimated.isoformat()

            date_str = item.date_exact or item.date_estimated
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=TZ)
                    # Conservador: na borda do corte sem data exata → NÃO deleta
                    if boundary and not item.date_exact:
                        item.eligible = False
                        item.error = "borda do corte sem data exata — revisão manual"
                    else:
                        item.eligible = dt <= cutoff
                except ValueError:
                    logger.warning(f"⚠️ Data inválida '{date_str}'")

        eligible = [i for i in items if i.eligible]
        # Exceções: preservar itens cujo texto contenha qualquer --keep-text
        kept = []
        if args.keep_text:
            for i in list(eligible):
                if any(k.lower() in i.text_preview.lower() for k in args.keep_text):
                    i.eligible = False
                    i.error = "preservado por --keep-text"
                    kept.append(i)
                    eligible.remove(i)
            for i in kept:
                logger.info(f"💚 Preservado: {i.text_preview[:70]}")
        logger.info(
            f"📊 Total: {len(items)} | Elegíveis: {len(eligible)} | Mantidos: {len(items) - len(eligible)}"
        )

        if args.execute:
            batch = eligible[: args.limit] if args.limit else eligible
            for n, item in enumerate(batch, 1):
                logger.info(
                    f"🗑️ [{n}/{len(batch)}] {item.kind} "
                    f"{item.date_exact or item.date_estimated} — {item.text_preview[:60]}"
                )
                if delete_item(page, item, slug=slug):
                    item.deleted = True
                    logger.info("   ✅ Deletado")
                else:
                    logger.warning(f"   ❌ Falha: {item.error}")
                time.sleep(ACTION_DELAY)
            logger.info(f"🏁 Deletados: {sum(1 for i in batch if i.deleted)}/{len(batch)}")

    report = {
        "generated_at": now.isoformat(),
        "cutoff": args.cutoff,
        "mode": "execute" if args.execute else "dry-run",
        "engine": "playwright/web-agent",
        "total": len(items),
        "eligible": len(eligible),
        "deleted": sum(1 for i in items if i.deleted),
        "items": [asdict(i) for i in items],
    }
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"📄 Relatório: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())