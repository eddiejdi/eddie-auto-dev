"""
Voice Assistant — Escuta microfone para wake word "OK HOME {comando}".

Fluxo:
  1. Captura áudio contínuo do microfone
  2. Detecta wake word "OK HOME" via speech recognition
  3. Extrai o comando após a wake word
  4. Tenta executar via Home Automation API
  5. Se comando desconhecido → tenta implementar via LLM local (Ollama)
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import struct
import threading
import time
import unicodedata
from typing import TYPE_CHECKING, Any, Dict, Optional

import io
import subprocess
import tempfile

import httpx

from system_tray_agent.config import (
    CRYPTO_API_URL,
    LLM_MODEL,
    MIC_DEVICE_INDEX,
    OLLAMA_URL,
    VOICE_ENERGY_THRESHOLD,
    VOICE_LANGUAGE,
    WAKE_WORD,
)
from system_tray_agent.history_db import log_voice_command

if TYPE_CHECKING:
    import speech_recognition as _sr_type
    sr: _sr_type  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Verificar disponibilidade do speech_recognition
try:
    import speech_recognition as sr  # type: ignore[no-redef]
    _SR_OK = True
except ImportError:
    _SR_OK = False
    sr = None  # type: ignore[assignment]
    logger.warning("speech_recognition não instalado — voice assistant desabilitado")


class VoiceAssistant:
    """Escuta microfone em background e processa comandos 'OK HOME ...'."""

    # Voice states for tray icon feedback
    STATE_IDLE = "idle"
    STATE_LISTENING = "listening"
    STATE_PROCESSING = "processing"
    STATE_SUCCESS = "success"
    STATE_ERROR = "error"

    def __init__(self, on_state_change=None):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._api = CRYPTO_API_URL.rstrip("/")
        self._recognizer = sr.Recognizer() if _SR_OK else None
        self._microphone = None
        self._last_command_time = 0
        self._mic_ok = _SR_OK  # atualizado em runtime se mic falhar
        self._command_cooldown = 2.0  # Segundos entre comandos
        self._enabled = True
        self._pa = None  # PyAudio instance for beeps
        self._beep_ok = False
        self._tts_ok = False
        self._on_state_change = on_state_change  # callback(state: str)
        try:
            import pyaudio
            self._pa = pyaudio.PyAudio()
            self._beep_ok = True
        except Exception:
            logger.debug("PyAudio indisponível — sem feedback sonoro")
        try:
            from gtts import gTTS as _gTTS  # noqa: F401
            self._tts_ok = True
        except ImportError:
            logger.debug("gTTS indisponível — sem resposta por voz")

    # ──────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return self._mic_ok

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def start(self):
        if not _SR_OK:
            logger.warning("🎙️  VoiceAssistant não pode iniciar — speech_recognition ausente")
            return
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="voice-assistant")
        self._thread.start()
        logger.info("🎙️  VoiceAssistant iniciado (wake_word='%s', lang=%s)",
                     WAKE_WORD, VOICE_LANGUAGE)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
        logger.info("🎙️  VoiceAssistant parado")

    def trigger_listen(self):
        """Aciona escuta manualmente (simula detecção do wake word).

        Toca o beep de wake e escuta um comando por até 8 segundos.
        Roda em thread própria para não bloquear a UI.
        """
        if not _SR_OK or not self._recognizer:
            logger.warning("🎙️  trigger_listen: speech_recognition indisponível")
            return

        def _do():
            self._beep_wake()
            logger.info("🎙️  Acionamento manual — aguardando comando...")
            try:
                mic = sr.Microphone(device_index=MIC_DEVICE_INDEX)
                with mic as source:
                    audio = self._recognizer.listen(source, timeout=8, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                logger.info("🎙️  Timeout — nenhum comando capturado")
                self._beep_error()
                return
            except Exception as exc:
                logger.warning("🎙️  Erro ao capturar áudio: %s", exc)
                self._beep_error()
                return

            text = self._recognize(audio)
            if not text:
                logger.info("🎙️  Não entendi o comando (manual)")
                self._beep_error()
                return

            command = self._normalize(text)
            logger.info("🎙️  Comando manual: '%s'", command)
            self._notify_state(self.STATE_PROCESSING)
            self._process_command(command, text)

        threading.Thread(target=_do, daemon=True, name="voice-trigger").start()

    # ──────────────────────────────────────────────────────
    # Feedback sonoro
    # ──────────────────────────────────────────────────────

    def _beep(self, freq: int = 880, duration: float = 0.15, volume: float = 0.5):
        """Gera um beep curto via PyAudio (não-bloqueante)."""
        if not self._beep_ok or not self._pa:
            return
        try:
            import pyaudio
            rate = 22050
            n_samples = int(rate * duration)
            samples = b"".join(
                struct.pack("h", int(volume * 32767 * math.sin(2.0 * math.pi * freq * i / rate)))
                for i in range(n_samples)
            )
            stream = self._pa.open(
                format=pyaudio.paInt16, channels=1, rate=rate, output=True,
            )
            stream.write(samples)
            stream.stop_stream()
            stream.close()
        except Exception as exc:
            logger.debug("Beep falhou: %s", exc)

    def _notify_state(self, state: str):
        """Notifica mudança de estado para callback externo (tray icon)."""
        if self._on_state_change:
            try:
                self._on_state_change(state)
            except Exception as exc:
                logger.debug("State change callback error: %s", exc)

    def _beep_wake(self):
        """Som curto agudo — wake word detectado, ouvindo comando."""
        self._notify_state(self.STATE_LISTENING)
        self._beep(freq=880, duration=0.12, volume=0.4)

    def _beep_success(self):
        """Dois beeps curtos — comando executado com sucesso."""
        self._notify_state(self.STATE_SUCCESS)
        self._beep(freq=660, duration=0.1, volume=0.35)
        time.sleep(0.08)
        self._beep(freq=880, duration=0.1, volume=0.35)

    def _beep_error(self):
        """Beep grave longo — erro no comando."""
        self._notify_state(self.STATE_ERROR)
        self._beep(freq=330, duration=0.3, volume=0.4)

    # ──────────────────────────────────────────────────────
    # Text-to-Speech
    # ──────────────────────────────────────────────────────

    def _speak(self, text: str):
        """Fala texto via gTTS + aplay (non-blocking)."""
        if not self._tts_ok:
            logger.debug("TTS indisponível, não falando: %s", text)
            return
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang="pt", slow=False)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                tts.save(fp.name)
                tmp_path = fp.name
            # Reproduzir via mpv/ffplay/aplay (o que estiver disponível)
            for player_cmd in (
                ["mpv", "--no-terminal", "--no-video", tmp_path],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                ["play", tmp_path],  # sox
            ):
                try:
                    subprocess.run(player_cmd, timeout=15, capture_output=True)
                    break
                except FileNotFoundError:
                    continue
                except subprocess.TimeoutExpired:
                    break
            import os
            os.unlink(tmp_path)
        except Exception as exc:
            logger.debug("TTS falhou: %s", exc)

    # ──────────────────────────────────────────────────────
    # Main listen loop
    # ──────────────────────────────────────────────────────

    # Regex que aceita variações comuns de "ok home" em pt-BR:
    #   ok/okay/oq/oque + home/ome/hom/rome
    #   Inclui "ok google" porque Google Speech tem viés forte para esse texto.
    #   Inclui "pokemon/pokémon" porque Google Speech frequentemente confunde
    #   "ok home" com "pokémon" em pt-BR.
    #   Sem ^ — aceita match em qualquer posição da frase (mic pode captar
    #   palavras antes do wake word).
    _WAKE_RE = re.compile(
        r"(?:"
        r"(?:ok(?:ay|ei)?|oq(?:ue)?)\s+(?:h?ome|rome|romi|google)"
        r"|pok[eé]mon"
        r")\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize(text: str) -> str:
        """Remove acentos e normaliza para comparação."""
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    def _match_wake_word(self, text: str) -> Optional[str]:
        """Retorna o comando após o wake word, ou None se não casar."""
        normalized = self._normalize(text)
        m = self._WAKE_RE.search(normalized)
        if m:
            cmd = normalized[m.end():].strip()
            logger.debug("🎙️  Wake word match: '%s' → cmd='%s'", m.group(), cmd)
            return cmd
        return None

    def _listen_loop(self):
        """Loop principal de escuta do microfone."""
        assert self._recognizer is not None  # guarded by start() → _SR_OK
        recognizer = self._recognizer
        recognizer.dynamic_energy_threshold = False  # fixo — dynamic sobe demais no mic notebook
        recognizer.pause_threshold = 1.5  # esperar mais antes de "cortar" a frase
        recognizer.phrase_threshold = 0.3  # mínimo de áudio para considerar fala
        recognizer.non_speaking_duration = 0.8  # silêncio antes/depois da fala

        try:
            mic = sr.Microphone(device_index=MIC_DEVICE_INDEX)
            _dev_name = "default" if MIC_DEVICE_INDEX is None else f"index={MIC_DEVICE_INDEX}"
            logger.info("🎙️  Usando microfone: %s", _dev_name)
        except Exception as exc:
            logger.warning("🎙️  Microfone indisponível (device_index=%s): %s", MIC_DEVICE_INDEX, exc)
            self._mic_ok = False
            return

        # Threshold fixo — NÃO usar adjust_for_ambient_noise().
        # A calibração automática sobe o threshold para ~28000 no mic do notebook,
        # fazendo com que o início da fala seja cortado e o Google não reconheça.
        # Com threshold baixo (300) o mic captura mais ruído, mas o Google Speech
        # filtra bem e reconhece fala normalmente.
        recognizer.energy_threshold = max(VOICE_ENERGY_THRESHOLD, 150)
        logger.info("🎙️  Threshold fixo em %.0f. Escutando...", recognizer.energy_threshold)

        while self._running:
            if not self._enabled:
                time.sleep(1)
                continue

            # ── Fase 1: escutar wake word ──────────────────
            try:
                with mic as source:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            except sr.WaitTimeoutError:
                continue
            except Exception as exc:
                logger.debug("Listen error: %s", exc)
                time.sleep(1)
                continue

            text = self._recognize(audio)
            if not text:
                continue

            logger.info("🎙️  Ouvido: '%s'", text)

            # Verificar se contém wake word
            wake_match = self._match_wake_word(text)
            if wake_match is None:
                continue

            # Cooldown
            now = time.time()
            if now - self._last_command_time < self._command_cooldown:
                continue
            self._last_command_time = now

            # Se já veio comando junto (ex: "ok home acender luz"), usar direto
            if wake_match:
                logger.info("🎙️  Wake + comando junto: '%s'", wake_match)
                self._beep_wake()
                self._notify_state(self.STATE_PROCESSING)
                threading.Thread(
                    target=self._process_command,
                    args=(wake_match, text),
                    daemon=True,
                ).start()
                continue

            # ── Fase 2: beep + escutar comando ─────────────
            logger.info("🎙️  Wake word detectado! Aguardando comando...")
            self._beep_wake()

            try:
                with mic as source:
                    audio_cmd = recognizer.listen(source, timeout=6, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                logger.info("🎙️  Timeout — nenhum comando após wake word")
                self._beep_error()
                continue
            except Exception as exc:
                logger.debug("Listen cmd error: %s", exc)
                continue

            command_text = self._recognize(audio_cmd)
            if not command_text:
                logger.info("🎙️  Não entendi o comando")
                self._beep_error()
                continue

            command = self._normalize(command_text)
            logger.info("🎙️  Comando: '%s'", command)
            self._notify_state(self.STATE_PROCESSING)
            threading.Thread(
                target=self._process_command,
                args=(command, text),
                daemon=True,
            ).start()

    # ──────────────────────────────────────────────────────
    # Speech recognition
    # ──────────────────────────────────────────────────────

    def _recognize(self, audio) -> Optional[str]:
        """Converte áudio em texto usando Google Speech Recognition."""
        assert self._recognizer is not None
        try:
            text = self._recognizer.recognize_google(audio, language=VOICE_LANGUAGE)  # type: ignore[attr-defined]
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as exc:
            logger.warning("Google Speech API error: %s", exc)
            # Fallback: Vosk offline (se disponível)
            return self._recognize_offline(audio)

    def _recognize_offline(self, audio) -> Optional[str]:
        """Fallback offline com Vosk."""
        assert self._recognizer is not None
        try:
            text = self._recognizer.recognize_vosk(audio, language=VOICE_LANGUAGE)  # type: ignore[attr-defined]
            if text:
                data = json.loads(text)
                return data.get("text", "")
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────────────
    # Command processing
    # ──────────────────────────────────────────────────────

    def _process_command(self, command: str, raw_text: str):
        """Processa um comando reconhecido."""
        try:
            result = asyncio.run(self._execute_command(command))
            success = result.get("success", False) if result else False
            response = json.dumps(result, ensure_ascii=False) if result else "no response"

            log_voice_command(
                raw_text=raw_text,
                parsed_cmd=command,
                success=success,
                response=response[:500],
            )

            if success:
                self._beep_success()  # also notifies STATE_SUCCESS
                logger.info("✅ Comando executado: '%s'", command)
                # Feedback de voz: confirmar
                affected = result.get("devices_affected", 0)
                if affected:
                    self._speak(f"Pronto, {command}.")
                else:
                    self._speak("Comando executado.")
            else:
                self._beep_error()
                error_msg = result.get("error", "") if result else ""
                # Checar erros individuais dos dispositivos
                if not error_msg and result:
                    results_list = result.get("results", [])
                    for r in results_list:
                        if not r.get("success") and r.get("error"):
                            error_msg = r["error"]
                            break
                logger.warning("❌ Comando falhou: '%s' → %s", command, error_msg[:200])
                # Feedback de voz: informar o erro
                if "local_key" in error_msg.lower():
                    self._speak(f"Dispositivo encontrado, mas a chave de acesso não está configurada.")
                elif "não encontrado" in error_msg.lower() or "desconhecido" in error_msg.lower():
                    self._speak(f"Desculpe, não encontrei o dispositivo para: {command}")
                elif error_msg:
                    self._speak(f"Não consegui executar: {command}. {error_msg[:80]}")
                else:
                    self._speak(f"Não consegui executar: {command}")
                # Tentar implementar comando desconhecido via LLM
                asyncio.run(self._try_implement_command(command))

        except Exception as exc:
            logger.error("Erro ao processar comando '%s': %s", command, exc)
            self._notify_state(self.STATE_ERROR)
            self._speak(f"Erro ao processar: {command}")
            log_voice_command(raw_text=raw_text, parsed_cmd=command, success=False,
                              response=str(exc))

    async def _execute_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Envia comando para Home Automation API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._api}/home/command",
                    json={"command": command},
                )
                if resp.status_code == 200:
                    return resp.json()
                # Ler body de erro (a API retorna detail com info útil)
                try:
                    body = resp.json()
                    detail = body.get("detail", {})
                    if isinstance(detail, dict):
                        return detail  # já tem success=false, error, parsed
                    return {"success": False, "error": str(detail)}
                except Exception:
                    return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ──────────────────────────────────────────────────────
    # LLM: tentar implementar comando desconhecido
    # ──────────────────────────────────────────────────────

    async def _try_implement_command(self, command: str):
        """
        Usa LLM local (Ollama) para interpretar comando desconhecido
        e gerar uma sequência de ações que o sistema possa executar.
        """
        logger.info("🤖 Tentando implementar comando desconhecido: '%s'", command)

        prompt = f"""Você é um assistente de automação residencial.
O usuário disse: "{command}"

Traduza isso em um ou mais comandos simples que o sistema pode executar.
Comandos disponíveis:
- ligar/desligar [dispositivo]
- aumentar/diminuir [dispositivo]
- definir temperatura [valor] graus
- definir brilho [valor] por cento
- ativar cena [nome]

Responda APENAS com JSON:
{{"commands": ["comando1", "comando2"], "explanation": "breve explicação"}}

Se não for possível traduzir, retorne:
{{"commands": [], "explanation": "não foi possível interpretar"}}
"""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": LLM_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Ollama respondeu %d", resp.status_code)
                    return

                data = resp.json()
                response_text = data.get("response", "")

            # Parsear JSON
            parsed = json.loads(response_text)
            commands = parsed.get("commands", [])
            explanation = parsed.get("explanation", "")

            if not commands:
                logger.info("🤖 LLM não conseguiu interpretar: %s", explanation)
                self._speak(explanation or f"Não entendi o que fazer com: {command}")
                log_voice_command(
                    raw_text=command, parsed_cmd="llm_failed",
                    success=False, response=explanation,
                )
                return

            logger.info("🤖 LLM sugeriu %d comandos: %s", len(commands), commands)

            # Executar sequência de comandos
            all_ok = True
            for cmd in commands:
                result = await self._execute_command(cmd)
                if not result or not result.get("success"):
                    all_ok = False
                    logger.warning("🤖 Sub-comando falhou: '%s'", cmd)

            log_voice_command(
                raw_text=command,
                parsed_cmd=f"llm:{json.dumps(commands, ensure_ascii=False)}",
                success=all_ok,
                response=explanation,
            )

        except json.JSONDecodeError:
            logger.warning("🤖 LLM retornou JSON inválido")
        except Exception as exc:
            logger.error("🤖 LLM error: %s", exc)
