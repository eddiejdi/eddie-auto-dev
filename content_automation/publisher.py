"""Publicação de conteúdo (mock + Kwai real via Selenium)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from content_automation.models import GeneratedContent, PublishResult, VideoArtifact

logger = logging.getLogger(__name__)


class BasePublisher:  # stub-ok
    def publish(
        self,
        content: GeneratedContent,
        video: VideoArtifact,
        *,
        platform: str,
    ) -> PublishResult:
        raise NotImplementedError  # stub-ok


class MockPublisher(BasePublisher):
    """Simula publicação salvando manifesto JSON + cópia de metadados."""

    def __init__(self, output_dir: Path) -> None:
        self.posts_dir = output_dir / "posts"
        self.posts_dir.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        content: GeneratedContent,
        video: VideoArtifact,
        *,
        platform: str,
    ) -> PublishResult:
        post_id = uuid.uuid4().hex[:12]
        published_at = datetime.now(UTC).isoformat()
        manifest = {
            "post_id": post_id,
            "platform": platform,
            "published_at": published_at,
            "mock": True,
            "content": content.to_dict(),
            "video": {
                "mp4_path": video.mp4_path,
                "duration_seconds": video.duration_seconds,
                "srt_path": video.srt_path,
            },
        }
        manifest_path = self.posts_dir / f"{post_id}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        result = PublishResult(
            platform=platform,
            external_id=post_id,
            url=f"mock://{platform}/posts/{post_id}",
            published_at=published_at,
            mock=True,
        )
        logger.info(
            "content_published_mock",
            extra={
                "extra_fields": {
                    "post_id": post_id,
                    "platform": platform,
                    "manifest": str(manifest_path),
                }
            },
        )
        return result


class KwaiPublisher(BasePublisher):
    """Publica vídeos reais no Kwai usando o perfil Chrome logado via kwai_browser."""

    # Validado em 2026-07-15: https://www.kwai.com/upload retorna 404 e o site
    # público não expõe upload; o caminho candidato é a Central do Criador,
    # que exige perfil Chrome logado (container kwai-browser).
    DEFAULT_UPLOAD_URL = "https://m-creative.kwai.com/creator/center"
    UPLOAD_TIMEOUT_SECONDS = 300
    PUBLISH_TIMEOUT_SECONDS = 120

    _PUBLISH_BUTTON_LABELS = ("publicar", "publish", "post", "发布")
    _LOGIN_WALL_MARKERS = ("o login é obrigatório", "faça login", "fazer login")

    def __init__(self, upload_url: str | None = None) -> None:
        import os

        from scripts.kwai.kwai_browser import build_driver

        self._build_driver = build_driver
        self.upload_url = (
            upload_url
            or os.getenv("KWAI_UPLOAD_URL", "").strip()
            or self.DEFAULT_UPLOAD_URL
        )

    def publish(
        self,
        content: GeneratedContent,
        video: VideoArtifact,
        *,
        platform: str,
    ) -> PublishResult:
        if platform != "kwai":
            raise ValueError("KwaiPublisher só suporta platform=kwai")

        mp4_path = Path(video.mp4_path).resolve()
        if not mp4_path.exists():
            raise RuntimeError(f"Vídeo não encontrado: {mp4_path}")

        driver = None
        try:
            driver = self._build_driver(
                headless=False,
                chrome_binary=None,
                start_url=self.upload_url,
            )
            driver.get(self.upload_url)
            self._assert_page_valid(driver)
            self._assert_logged_in(driver)
            self._send_video_file(driver, mp4_path)
            self._fill_caption(driver, content.title, content.script)
            self._wait_upload_complete(driver)
            self._click_publish(driver)
            final_url = self._wait_publish_confirmation(driver)

            published_at = datetime.now(UTC).isoformat()
            post_id = self._extract_post_id(final_url) or uuid.uuid4().hex[:12]
            result = PublishResult(
                platform="kwai",
                external_id=post_id,
                url=final_url,
                published_at=published_at,
                mock=False,
            )
            logger.info(
                "kwai_published",
                extra={
                    "extra_fields": {
                        "post_id": post_id,
                        "url": final_url,
                        "video": video.mp4_path,
                        "title": content.title,
                    }
                },
            )
            return result
        finally:
            if driver:
                driver.quit()

    def _assert_page_valid(self, driver) -> None:
        import time

        from selenium.webdriver.common.by import By

        time.sleep(5)
        body = ""
        try:
            body = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
        except Exception:
            pass
        if "page not found" in body or "\n404\n" in f"\n{body}\n":
            raise RuntimeError(
                f"Página de upload do Kwai não existe (404): {self.upload_url}. "
                "Ajuste KWAI_UPLOAD_URL ou kwai.upload_url na config."
            )

    def _assert_logged_in(self, driver) -> None:
        from selenium.webdriver.common.by import By

        url = driver.current_url.lower()
        if "login" in url or "passport" in url:
            raise RuntimeError(
                "Perfil Chrome do Kwai não está logado (redirecionado para login). "
                "Faça login manual no perfil usado por scripts/kwai/kwai_browser.py."
            )
        body = ""
        try:
            body = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
        except Exception:
            pass
        if any(marker in body for marker in self._LOGIN_WALL_MARKERS):
            raise RuntimeError(
                "Página do Kwai exige login e o perfil Chrome não tem sessão ativa. "
                "Faça login manual no container kwai-browser (https://127.0.0.1:3016/) "
                "e aponte KWAI_CHROME_PROFILE_DIR para o perfil logado."
            )

    def _send_video_file(self, driver, mp4_path: Path) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        file_input = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(str(mp4_path))

    def _fill_caption(self, driver, title: str, script: str) -> None:
        from selenium.webdriver.common.by import By

        caption = title.strip()
        if script.strip():
            caption = f"{caption}\n{script.strip()}"
        caption = caption[:500]

        selectors = (
            "textarea",
            "div[contenteditable='true']",
            "input[placeholder]",
        )
        for selector in selectors:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                if not element.is_displayed():
                    continue
                try:
                    element.click()
                    element.send_keys(caption)
                    return
                except Exception:
                    continue
        logger.warning("Campo de legenda do Kwai não encontrado; publicando sem texto.")

    def _wait_upload_complete(self, driver) -> None:
        import time

        from selenium.webdriver.common.by import By

        deadline = time.monotonic() + self.UPLOAD_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self._find_publish_button(driver, By) is not None:
                return
            time.sleep(3)
        raise RuntimeError(
            f"Upload não concluiu em {self.UPLOAD_TIMEOUT_SECONDS}s "
            "(botão de publicar não habilitou)."
        )

    def _find_publish_button(self, driver, By):
        for button in driver.find_elements(By.CSS_SELECTOR, "button"):
            label = (button.text or "").strip().lower()
            if not label or not button.is_displayed():
                continue
            if any(word in label for word in self._PUBLISH_BUTTON_LABELS):
                if button.is_enabled() and "disabled" not in (button.get_attribute("class") or ""):
                    return button
        return None

    def _click_publish(self, driver) -> None:
        from selenium.webdriver.common.by import By

        button = self._find_publish_button(driver, By)
        if button is None:
            raise RuntimeError("Botão de publicar do Kwai não encontrado.")
        driver.execute_script("arguments[0].click();", button)

    def _wait_publish_confirmation(self, driver) -> str:
        import time

        upload_url = self.upload_url.rstrip("/")
        deadline = time.monotonic() + self.PUBLISH_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            current = driver.current_url.rstrip("/")
            if current != upload_url:
                return driver.current_url
            time.sleep(3)
        raise RuntimeError(
            f"Sem confirmação de publicação em {self.PUBLISH_TIMEOUT_SECONDS}s "
            "(página continua em /upload)."
        )

    @staticmethod
    def _extract_post_id(url: str) -> str | None:
        for marker in ("/video/", "/short-video/", "photoId="):
            if marker in url:
                tail = url.split(marker, 1)[1]
                candidate = tail.split("?")[0].split("&")[0].split("/")[0]
                if candidate:
                    return candidate
        return None


def build_publisher(mode: str, output_dir: Path) -> BasePublisher:
    if mode == "mock":
        return MockPublisher(output_dir)
    if mode == "kwai":
        return KwaiPublisher()
    raise ValueError(f"Publisher mode não suportado: {mode}")