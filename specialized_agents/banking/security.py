"""
Gerenciamento de segurança para integração bancária.
Lida com OAuth2, certificados mTLS, criptografia de credenciais e auditoria.
"""

import os
import json
import hashlib
import hmac
import secrets
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

# Criptografia
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# Vault do projeto
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from tools.simple_vault import vault_store
    VAULT_AVAILABLE = True
except Exception:
    VAULT_AVAILABLE = False


@dataclass
class OAuthToken:
    """Token OAuth2 para APIs bancárias"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    issued_at: datetime = field(default_factory=datetime.now)
    provider: str = ""

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.issued_at + timedelta(seconds=self.expires_in - 60)

    @property
    def authorization_header(self) -> str:
        return f"{self.token_type} {self.access_token}"


class BankingSecurityManager:
    """
    Gerenciador de segurança para integrações bancárias.

    Responsabilidades:
    - Armazenamento seguro de credenciais (Fernet encryption)
    - Gerenciamento de tokens OAuth2
    - Cache de tokens com expiração automática
    - Geração de PKCE (Proof Key for Code Exchange)
    - Validação de webhooks (HMAC)
    - Auditoria de acessos
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or Path(__file__).parent.parent.parent / "agent_data" / "banking"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._token_cache: Dict[str, OAuthToken] = {}
        self._audit_log: list = []
        self._fernet: Optional[Any] = None

        if CRYPTO_AVAILABLE:
            self._init_encryption()

    # ──────────── Encryption ────────────

    def _init_encryption(self):
        """Inicializa Fernet com chave derivada de master key."""
        key_file = self._data_dir / ".banking_key"
        if key_file.exists():
            key = key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            key_file.chmod(0o600)
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Criptografa dado sensível."""
        if not self._fernet:
            return base64.b64encode(plaintext.encode()).decode()
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Descriptografa dado sensível."""
        if not self._fernet:
            return base64.b64decode(ciphertext.encode()).decode()
        return self._fernet.decrypt(ciphertext.encode()).decode()

    # ──────────── Credenciais ────────────

    def store_credentials(self, provider: str, credentials: Dict[str, str]) -> None:
        """
        Armazena credenciais bancárias de forma segura.
        Credenciais são criptografadas antes de persistir.
        """
        encrypted = {k: self.encrypt(v) for k, v in credentials.items()}
        cred_file = self._data_dir / f".cred_{provider}"
        cred_file.write_text(json.dumps(encrypted))
        cred_file.chmod(0o600)
        self._audit("store_credentials", provider, "Credenciais armazenadas")

    def load_credentials(self, provider: str) -> Optional[Dict[str, str]]:
        """Carrega e descriptografa credenciais de um provider."""
        cred_file = self._data_dir / f".cred_{provider}"
        if not cred_file.exists():
            # Tentar carregar de variáveis de ambiente
            return self._load_from_env(provider)
        try:
            encrypted = json.loads(cred_file.read_text())
            decrypted = {k: self.decrypt(v) for k, v in encrypted.items()}
            self._audit("load_credentials", provider, "Credenciais carregadas")
            return decrypted
        except Exception as e:
            self._audit("load_credentials_error", provider, str(e))
            return None

    def _load_from_env(self, provider: str) -> Optional[Dict[str, str]]:
        """Fallback: carrega credenciais de variáveis de ambiente."""
        prefix = f"BANK_{provider.upper()}_"
        creds = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                clean_key = key[len(prefix):].lower()
                creds[clean_key] = value
        return creds if creds else None

    def delete_credentials(self, provider: str) -> bool:
        """Remove credenciais de um provider."""
        cred_file = self._data_dir / f".cred_{provider}"
        if cred_file.exists():
            cred_file.unlink()
            self._audit("delete_credentials", provider, "Credenciais removidas")
            return True
        return False

    # ──────────── OAuth2 Token Management ────────────

    def cache_token(self, provider: str, token: OAuthToken) -> None:
        """Armazena token no cache em memória."""
        token.provider = provider
        self._token_cache[provider] = token
        self._audit("cache_token", provider, f"Token cacheado (expira em {token.expires_in}s)")

    def get_cached_token(self, provider: str) -> Optional[OAuthToken]:
        """Retorna token do cache se ainda válido."""
        token = self._token_cache.get(provider)
        if token and not token.is_expired:
            return token
        if token and token.is_expired:
            del self._token_cache[provider]
            self._audit("token_expired", provider, "Token expirado removido do cache")
        return None

    def invalidate_token(self, provider: str) -> None:
        """Remove token do cache."""
        self._token_cache.pop(provider, None)
        self._audit("invalidate_token", provider, "Token invalidado")

    # ──────────── PKCE (OAuth2) ────────────

    @staticmethod
    def generate_pkce() -> Tuple[str, str]:
        """
        Gera code_verifier e code_challenge para PKCE.
        Retorna (code_verifier, code_challenge).
        """
        code_verifier = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return code_verifier, code_challenge

    @staticmethod
    def generate_state() -> str:
        """Gera state parameter para OAuth2."""
        return secrets.token_urlsafe(32)

    # ──────────── Webhook Validation ────────────

    @staticmethod
    def validate_webhook_signature(
        payload: bytes, signature: str, secret: str, algorithm: str = "sha256"
    ) -> bool:
        """Valida assinatura HMAC de webhook bancário."""
        expected = hmac.new(
            secret.encode(), payload, getattr(hashlib, algorithm)
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ──────────── mTLS Certificate Paths ────────────

    def get_cert_paths(self, provider: str) -> Optional[Dict[str, str]]:
        """
        Retorna paths dos certificados mTLS para Open Finance.
        Espera:
          - agent_data/banking/certs/{provider}/client.pem
          - agent_data/banking/certs/{provider}/client.key
          - agent_data/banking/certs/{provider}/ca.pem  (opcional)
        """
        cert_dir = self._data_dir / "certs" / provider
        client_cert = cert_dir / "client.pem"
        client_key = cert_dir / "client.key"
        ca_cert = cert_dir / "ca.pem"

        if not client_cert.exists() or not client_key.exists():
            return None

        paths = {"cert": str(client_cert), "key": str(client_key)}
        if ca_cert.exists():
            paths["ca"] = str(ca_cert)
        return paths

    def store_certificate(self, provider: str, cert_type: str, content: bytes) -> Path:
        """Armazena certificado mTLS."""
        cert_dir = self._data_dir / "certs" / provider
        cert_dir.mkdir(parents=True, exist_ok=True)
        cert_path = cert_dir / cert_type
        cert_path.write_bytes(content)
        cert_path.chmod(0o600)
        self._audit("store_certificate", provider, f"Certificado {cert_type} armazenado")
        return cert_path

    # ──────────── Masking ────────────

    @staticmethod
    def mask_document(document: str) -> str:
        """Mascara CPF/CNPJ para exibição segura."""
        digits = "".join(c for c in document if c.isdigit())
        if len(digits) == 11:  # CPF
            return f"{digits[:3]}.***.**{digits[-2:]}"
        elif len(digits) == 14:  # CNPJ
            return f"{digits[:2]}.***.***/****-{digits[-2:]}"
        return f"{'*' * max(0, len(digits) - 4)}{digits[-4:]}" if len(digits) > 4 else "****"

    @staticmethod
    def mask_account(number: str) -> str:
        """Mascara número de conta."""
        if len(number) > 4:
            return f"{'*' * (len(number) - 4)}{number[-4:]}"
        return "****"

    # ──────────── Audit ────────────

    def _audit(self, action: str, provider: str, detail: str):
        """Registra evento de auditoria (LGPD compliance)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "provider": provider,
            "detail": detail,
        }
        self._audit_log.append(entry)
        # Manter apenas os últimos 1000 eventos em memória
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-500:]

    def get_audit_log(self, provider: Optional[str] = None, limit: int = 50) -> list:
        """Retorna log de auditoria (filtrado opcionalmente por provider)."""
        logs = self._audit_log
        if provider:
            logs = [e for e in logs if e["provider"] == provider]
        return logs[-limit:]

    def export_audit_log(self, path: Optional[Path] = None) -> Path:
        """Exporta log de auditoria para arquivo JSON."""
        out = path or self._data_dir / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(self._audit_log, indent=2, ensure_ascii=False))
        return out
