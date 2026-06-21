#!/usr/bin/env python3
"""RPA Selenium para rotação de token no BotFather com controles de segurança."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import time
import tarfile
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final


TOKEN_REGEX: Final[re.Pattern[str]] = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")


@dataclass(frozen=True)
class RotateConfig:
    """Configuração de execução do fluxo de rotação de token."""

    bot_username: str
    profile_dir: Path
    timeout_seconds: int
    headless: bool
    chrome_binary: Path | None
    chromedriver_path: Path | None
    profile_archive: Path | None
    profile_archive_clean: bool
    output_token_file: Path | None
    post_rotate_cmd: str | None
    extra_chrome_args: list[str]


def parse_args(argv: list[str]) -> RotateConfig:
    """Converte os argumentos de linha de comando em configuração tipada."""
    parser = argparse.ArgumentParser(
        description=(
            "Rotaciona o token de um bot Telegram via BotFather usando Selenium "
            "e opcionalmente dispara comando pós-rotação."
        )
    )
    parser.add_argument("--bot-username", required=True, help="Username do bot sem @")
    parser.add_argument(
        "--profile-dir",
        default=str(Path.home() / ".cache" / "telegram-rotate-selenium"),
        help="Diretório de perfil do Chrome para manter sessão do Telegram Web",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Tempo máximo de espera por etapas de UI e token",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Executa navegador em modo headless (não recomendado no primeiro login)",
    )
    parser.add_argument(
        "--chrome-binary",
        default="",
        help="Caminho explícito do binário do Chrome/Chromium",
    )
    parser.add_argument(
        "--chromedriver-path",
        default="",
        help="Caminho explícito do chromedriver, bypassa descoberta por PATH",
    )
    parser.add_argument(
        "--profile-archive",
        default="",
        help="Bundle .tar.gz do userdata para restaurar antes da execução",
    )
    parser.add_argument(
        "--profile-archive-clean",
        action="store_true",
        help="Limpa profile-dir antes de extrair o bundle",
    )
    parser.add_argument(
        "--output-token-file",
        default="",
        help="Arquivo para salvar novo token com permissão 0600; vazio usa arquivo temporário",
    )
    parser.add_argument(
        "--post-rotate-cmd",
        default="",
        help=(
            "Comando opcional após rotação. Pode usar {token_file}. "
            "Ex.: '/usr/local/bin/telegram-incident-rotate.sh --token-file {token_file}'"
        ),
    )
    parser.add_argument(
        "--extra-chrome-arg",
        dest="extra_chrome_args",
        action="append",
        default=[],
        help="Argumento adicional para o Chrome (pode ser usado múltiplas vezes). Ex.: --proxy-server=http://localhost:3128",
    )
    args = parser.parse_args(argv)

    output_token_file = Path(args.output_token_file).expanduser() if args.output_token_file else None
    chrome_binary = Path(args.chrome_binary).expanduser() if args.chrome_binary else None
    chromedriver_path = Path(args.chromedriver_path).expanduser() if args.chromedriver_path else None
    profile_archive = Path(args.profile_archive).expanduser() if args.profile_archive else None
    post_rotate_cmd = args.post_rotate_cmd.strip() or None
    return RotateConfig(
        bot_username=args.bot_username.lstrip("@"),
        profile_dir=Path(args.profile_dir).expanduser(),
        timeout_seconds=max(30, int(args.timeout_seconds)),
        headless=bool(args.headless),
        chrome_binary=chrome_binary,
        chromedriver_path=chromedriver_path,
        profile_archive=profile_archive,
        profile_archive_clean=bool(args.profile_archive_clean),
        output_token_file=output_token_file,
        post_rotate_cmd=post_rotate_cmd,
        extra_chrome_args=list(args.extra_chrome_args),
    )


def _resolve_chrome_binary(explicit_binary: Path | None) -> str | None:
    """Resolve binário de navegador válido para o Selenium."""
    candidates: list[str] = []
    if explicit_binary:
        candidates.append(str(explicit_binary.expanduser()))

    for cmd in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(cmd)
        if found:
            candidates.append(found)

    candidates.extend(
        [
            "/opt/google/chrome/chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
    )

    for candidate in candidates:
        path = Path(candidate).expanduser()
        try:
            if path.exists() and path.is_file():
                return str(path)
        except Exception:
            continue
    return None


def _safe_resolve(path: Path) -> Path:
    """Resolve caminho absoluto com expansão de usuário."""
    return path.expanduser().resolve()


def _ensure_within(base: Path, target: Path) -> None:
    """Valida que o caminho de extração não escapa do diretório destino."""
    base_resolved = _safe_resolve(base)
    target_resolved = _safe_resolve(target)
    if not str(target_resolved).startswith(str(base_resolved) + "/") and target_resolved != base_resolved:
        raise ValueError(f"caminho inseguro detectado na extração: {target}")


def restore_profile_archive(archive_file: Path, profile_dir: Path, *, clean: bool) -> Path:
    """Restaura bundle de userdata em profile-dir."""
    archive = _safe_resolve(archive_file)
    if not archive.exists() or not archive.is_file():
        raise FileNotFoundError(f"bundle de profile inexistente: {archive}")

    profile = _safe_resolve(profile_dir)
    profile.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        roots = {m.name.split("/")[0] for m in members if m.name and m.name.strip()}
        if len(roots) != 1:
            raise ValueError("bundle inválido: esperado exatamente um diretório raiz")
        root_name = next(iter(roots))
        extracted_root = profile.parent / root_name

        if clean and extracted_root.exists():
            import shutil

            shutil.rmtree(extracted_root)

        for member in members:
            member_path = profile.parent / member.name
            _ensure_within(profile.parent, member_path)
        tf.extractall(profile.parent)

    if extracted_root != profile:
        if profile.exists():
            import shutil

            shutil.rmtree(profile)
        extracted_root.rename(profile)

    # Remove locks transitórios que podem vir dentro do bundle e quebrar sessão.
    _remove_profile_locks(profile)

    return profile


def _remove_profile_locks(profile_dir: Path) -> None:
    """Remove arquivos de lock/DevTools que impedem inicialização do Chrome."""
    candidates = [
        profile_dir / "DevToolsActivePort",
        profile_dir / "SingletonCookie",
        profile_dir / "SingletonLock",
        profile_dir / "SingletonSocket",
        profile_dir / "lockfile",
    ]
    for path in candidates:
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except Exception:
            continue


def mask_secret(value: str) -> str:
    """Retorna uma versão mascarada de um segredo para logs."""
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def extract_latest_token(raw_text: str) -> str | None:
    """Extrai o último token Telegram identificado em um texto bruto."""
    tokens = TOKEN_REGEX.findall(raw_text)
    if not tokens:
        return None
    return tokens[-1]


def _build_driver(config: RotateConfig):
    """Cria o driver do Chrome com perfil persistente e opções seguras."""
    try:
        from selenium import webdriver
    except Exception as exc:  # pragma: no cover - dependente do ambiente
        raise RuntimeError("selenium não está instalado no ambiente") from exc

    config.profile_dir.mkdir(parents=True, exist_ok=True)
    _remove_profile_locks(config.profile_dir)

    options = webdriver.ChromeOptions()
    chrome_binary = _resolve_chrome_binary(config.chrome_binary)
    if chrome_binary:
        options.binary_location = chrome_binary
    if config.headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-session-crashed-bubble")
    options.add_argument("--window-size=1600,1200")
    options.add_argument(f"--user-data-dir={config.profile_dir}")
    options.add_argument("--profile-directory=Default")
    for extra_arg in config.extra_chrome_args:
        options.add_argument(extra_arg)

    from selenium.webdriver.chrome.service import Service as ChromeService

    service = ChromeService(executable_path=str(config.chromedriver_path)) if config.chromedriver_path else ChromeService()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(config.timeout_seconds)
    return driver


def _send_message(driver, message: str, timeout_seconds: int) -> None:
    """Envia mensagem na conversa corrente com múltiplos seletores de fallback."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    from selenium.webdriver.common.action_chains import ActionChains

    selectors = [
        (By.CSS_SELECTOR, ".input-message-input"),
        (By.CSS_SELECTOR, "div.input-message-container div[contenteditable='true']"),
        (By.CSS_SELECTOR, "div[contenteditable='true'][role='textbox']"),
        (By.CSS_SELECTOR, "div.composer_rich_textarea[contenteditable='true']"),
    ]
    last_error: Exception | None = None
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        for by, selector in selectors:
            try:
                element = WebDriverWait(driver, 5).until(ec.element_to_be_clickable((by, selector)))
                ActionChains(driver).move_to_element(element).click().perform()
                time.sleep(0.3)
                element.send_keys(message)
                element.send_keys(Keys.ENTER)
                return
            except Exception as exc:
                last_error = exc
                continue
        time.sleep(0.4)

    raise RuntimeError(f"falha ao enviar mensagem '{message}'") from last_error


def _click_bot_button(driver, bot_username: str, timeout_seconds: int) -> None:
    """Clica no botão inline referente ao bot solicitado no fluxo do /token.

    Tenta primeiro revelar o reply keyboard (se oculto) e depois localizar o
    botão. Como fallback, envia o username como texto para o BotFather.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    # Revela reply keyboard se estiver colapsado (toggle-reply-markup com classe show)
    try:
        toggles = driver.find_elements(By.CSS_SELECTOR, "button.toggle-reply-markup")
        for toggle in toggles:
            if "show" in (toggle.get_attribute("class") or "") and toggle.is_displayed():
                toggle.click()
                time.sleep(1.0)
                break
    except Exception:
        pass

    normalized = bot_username.lower()
    candidates = [
        f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '@{normalized}') ]",
        f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized}') ]",
        f"//*[contains(@class,'reply-markup')]//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized}') ]",
    ]
    for xpath in candidates:
        try:
            button = WebDriverWait(driver, 5).until(ec.element_to_be_clickable((By.XPATH, xpath)))
            button.click()
            return
        except Exception:
            continue

    # Fallback: envia o username como texto (BotFather aceita @username após /token)
    print(f"Botão do bot não encontrado no DOM; enviando @{bot_username} como texto...")
    _send_message(driver, f"@{bot_username}", timeout_seconds)
    time.sleep(1.5)


def _try_direct_revoke(driver, bot_username: str) -> bool:
    """Verifica se já existe contexto de token management para o bot e retorna True se puder revogar diretamente.

    Aguarda um breve período para a página renderizar os reply-markup antes de checar.
    """
    from selenium.webdriver.common.by import By

    # Aguarda reply-markup buttons renderizarem (podem demorar após carregamento)
    time.sleep(2.5)
    try:
        btns = driver.find_elements(By.CSS_SELECTOR, "button.reply-markup-button")
        for btn in btns:
            if "revoke" in btn.text.lower() and btn.is_displayed():
                print(f"Botão 'Revoke current token' já visível — usando contexto direto para @{bot_username}...")
                return True
    except Exception:
        pass
    return False


def _navigate_mybots_to_bot(driver, bot_username: str, timeout_seconds: int) -> None:
    """Navega pelo /mybots → seleciona bot via inline keyboard.

    Após selecionar o bot, o BotFather já expõe 'Revoke current token' no inline keyboard.
    Não é necessário clicar em 'API Token' — o botão de revogação já fica visível.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    print("Enviando /mybots para navegar via inline keyboard...")
    _send_message(driver, "/mybots", timeout_seconds)
    time.sleep(2.5)

    # Clica no botão do bot (inline keyboard com nomes de bots)
    normalized = bot_username.lower()
    bot_xpaths = [
        f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '@{normalized}')]",
        f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized}')]",
    ]
    selected = False
    for xpath in bot_xpaths:
        try:
            btn = WebDriverWait(driver, 10).until(ec.element_to_be_clickable((By.XPATH, xpath)))
            btn.click()
            selected = True
            print(f"Bot @{bot_username} selecionado via /mybots inline keyboard")
            break
        except Exception:
            continue
    if not selected:
        raise RuntimeError(f"Botão do bot @{bot_username} não encontrado após /mybots")

    # Aguarda o menu do bot renderizar (Revoke current token já fica visível aqui)
    time.sleep(2.0)


def _click_revoke_current_token(driver, timeout_seconds: int) -> None:
    """Clica em 'Revoke current token' no BotFather e confirma se necessário."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    revoke_xpaths = [
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'revoke current token')]",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'revoke token')]",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'revoke')]",
    ]
    revoked = False
    for xpath in revoke_xpaths:
        try:
            btn = WebDriverWait(driver, 15).until(ec.element_to_be_clickable((By.XPATH, xpath)))
            btn.click()
            revoked = True
            break
        except Exception:
            continue
    if not revoked:
        raise RuntimeError("botão 'Revoke current token' não encontrado no BotFather")

    # Confirmar se aparecer diálogo de confirmação (Yes / Sure / Confirm)
    time.sleep(1)
    confirm_xpaths = [
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'yes')]",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sure')]",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'confirm')]",
    ]
    for xpath in confirm_xpaths:
        try:
            btn = WebDriverWait(driver, 5).until(ec.element_to_be_clickable((By.XPATH, xpath)))
            btn.click()
            break
        except Exception:
            continue


def _wait_for_message_input(driver, timeout_seconds: int) -> None:
    """Aguarda o input de mensagem estar clicável na conversa aberta."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    selectors = [
        (By.CSS_SELECTOR, ".input-message-input"),
        (By.CSS_SELECTOR, "div.input-message-container div[contenteditable='true']"),
    ]
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for by, sel in selectors:
            try:
                WebDriverWait(driver, 3).until(ec.element_to_be_clickable((by, sel)))
                return
            except Exception:
                continue
        time.sleep(0.5)


def _wait_until_logged_in(driver, timeout_seconds: int) -> None:
    """Aguarda tela principal do Telegram Web estar disponível."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    selectors = [
        (By.CSS_SELECTOR, ".chatlist"),
        (By.CSS_SELECTOR, ".chats-container"),
        (By.CSS_SELECTOR, "#column-left"),
        (By.CSS_SELECTOR, ".input-search"),
    ]
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for by, selector in selectors:
            try:
                WebDriverWait(driver, 5).until(ec.presence_of_element_located((by, selector)))
                return
            except Exception:
                continue
        time.sleep(0.4)

    raise RuntimeError(
        "login no Telegram Web não detectado no tempo limite; "
        "faça login manual (QR/2FA) e execute novamente"
    )


def _read_page_text(driver) -> str:
    """Lê o texto atual da página para busca de token."""
    try:
        return (driver.find_element("tag name", "body").text or "").strip()
    except Exception:
        return ""


def write_secret_file(token: str, requested_path: Path | None) -> Path:
    """Salva token em arquivo com permissão restrita e retorna o caminho final."""
    if requested_path is None:
        handle = tempfile.NamedTemporaryFile(prefix="telegram_rotated_token_", suffix=".txt", delete=False)
        path = Path(handle.name)
        handle.close()
    else:
        path = requested_path
        path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(token, encoding="utf-8")
    path.chmod(0o600)
    return path


def render_post_rotate_command(command_template: str, token_file: Path) -> str:
    """Renderiza o comando pós-rotação substituindo placeholders suportados."""
    return command_template.replace("{token_file}", str(token_file))


def run_post_rotate_cmd(command: str) -> int:
    """Executa comando pós-rotação e devolve o código de saída."""
    completed = subprocess.run(command, shell=True, check=False)
    return int(completed.returncode)


def rotate_token(config: RotateConfig) -> tuple[str, Path]:
    """Executa o fluxo de rotação no BotFather e retorna token + arquivo salvo."""
    if config.profile_archive:
        restored = restore_profile_archive(
            archive_file=config.profile_archive,
            profile_dir=config.profile_dir,
            clean=config.profile_archive_clean,
        )
        print(f"Profile restaurado em: {restored}")

    driver = _build_driver(config)
    try:
        print("Abrindo conversa do BotFather...")
        driver.get("https://web.telegram.org/k/#@BotFather")
        _wait_until_logged_in(driver, config.timeout_seconds)
        _wait_for_message_input(driver, config.timeout_seconds)

        # Tenta revogar diretamente se já estiver no contexto de token management.
        # Caso contrário, navega via /mybots (inline keyboard, mais confiável que /token).
        if not _try_direct_revoke(driver, config.bot_username):
            _send_message(driver, "/cancel", config.timeout_seconds)
            time.sleep(1.0)
            _navigate_mybots_to_bot(driver, config.bot_username, config.timeout_seconds)

        print("Revogando token atual para gerar novo...")
        _click_revoke_current_token(driver, config.timeout_seconds)

        print("Aguardando novo token aparecer na conversa...")
        deadline = time.monotonic() + config.timeout_seconds
        token: str | None = None
        while time.monotonic() < deadline:
            token = extract_latest_token(_read_page_text(driver))
            if token:
                break
            time.sleep(0.8)

        if not token:
            raise RuntimeError("não foi possível capturar o token no tempo limite")

        token_file = write_secret_file(token, config.output_token_file)
        return token, token_file
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do utilitário de rotação Selenium."""
    config = parse_args(argv or sys.argv[1:])
    print(f"Iniciando rotação para @{config.bot_username}...")

    token, token_file = rotate_token(config)
    print(f"Token rotacionado (mascarado): {mask_secret(token)}")
    print(f"Token salvo em arquivo seguro: {token_file}")

    if config.post_rotate_cmd:
        rendered = render_post_rotate_command(config.post_rotate_cmd, token_file)
        print("Executando comando pós-rotação...")
        code = run_post_rotate_cmd(rendered)
        if code != 0:
            print(f"Falha no comando pós-rotação, exit={code}")
            return code
        print("Comando pós-rotação concluído com sucesso.")

    print("Fluxo finalizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
