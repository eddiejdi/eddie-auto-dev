from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait


SITE_DIR = Path(__file__).resolve().parents[1] / "site"


@dataclass
class MockUser:
    company: str = "Mock Industria de Dados Ltda."
    legal_name: str = "Mock Industria de Dados Ltda."
    company_document: str = "12.345.678/0001-90"
    contact: str = "Mariana Rocha"
    role: str = "Diretora de Tecnologia"
    email: str = "mariana.rocha@mockindustria.test"
    phone: str = "+55 11 98888-7777"
    representative_document: str = "123.456.789-09"
    project: str = "Arquivo juridico e backups regulados"
    address: str = "Avenida Paulista"
    address_number: str = "1500"
    address_complement: str = "12 andar"
    district: str = "Bela Vista"
    postal_code: str = "01310-200"
    city: str = "Sao Paulo"
    state: str = "SP"
    notes: str = "Necessita trilha de auditoria, politica de restore e revisao juridica."
    start_date: str = "2026-04-15"


class MockStoragePortalState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.base_url = ""
        self.portal_token = "stp_mock_main_token"
        self.contract_code = "STR-MOCK-20260315"
        self.contract_id = "ctr_mock_20260315"
        self.workspace_relative_dir = "Portal_Storage/STR-MOCK-20260315"
        self.workspace_path = "/mnt/mock/RPA4ALL/Portal_Storage/STR-MOCK-20260315"
        self.company = "Mock Industries"
        self.project = "Mock Storage Contract"
        self.primary_email = "gestor@mockindustria.test"
        self.primary_contact = "Gestor Mock"
        self.term_months = 12
        self.monthly_service = 4200
        self.status = "active"
        self.manager_user = {
            "id": 1,
            "username": "mock.manager",
            "full_name": "Gestor Mock",
            "email": "gestor@mockindustria.test",
            "profile": "manager",
            "profile_label": "Gestor",
            "status": "active",
        }
        self.api_tokens: list[dict[str, object]] = []
        self.users: list[dict[str, object]] = [dict(self.manager_user)]
        self.payments: list[dict[str, object]] = []
        self.directories: dict[str, list[dict[str, object]]] = {
            ".": [
                {
                    "name": f"CONTRATO-{self.contract_code}.html",
                    "path": f"CONTRATO-{self.contract_code}.html",
                    "kind": "file",
                    "size": 24137,
                    "modified_at": self._now(),
                },
                {
                    "name": f"CONTRATO-{self.contract_code}.txt",
                    "path": f"CONTRATO-{self.contract_code}.txt",
                    "kind": "file",
                    "size": 6821,
                    "modified_at": self._now(),
                },
                {
                    "name": "README.txt",
                    "path": "README.txt",
                    "kind": "file",
                    "size": 2048,
                    "modified_at": self._now(),
                }
            ]
        }
        self.next_api_token_id = 1
        self.next_user_id = 2
        self.next_payment_id = 1
        self.last_request_payload: dict[str, object] | None = None

    def _documents(self) -> dict[str, str]:
        return {
            "reference": f"RPA4ALL-STORAGE-{self.contract_code}",
            "html_name": f"CONTRATO-{self.contract_code}.html",
            "text_name": f"CONTRATO-{self.contract_code}.txt",
            "html_path": f"{self.workspace_path}/CONTRATO-{self.contract_code}.html",
            "text_path": f"{self.workspace_path}/CONTRATO-{self.contract_code}.txt",
            "html_relative_path": f"{self.workspace_relative_dir}/CONTRATO-{self.contract_code}.html",
            "text_relative_path": f"{self.workspace_relative_dir}/CONTRATO-{self.contract_code}.txt",
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _connections(self) -> dict[str, str]:
        api_base = f"{self.base_url}/agents-api"
        token_preview = self.api_tokens[-1]["preview"] if self.api_tokens else "stg_live_mock..."
        nextcloud_dir = f"/{self.workspace_relative_dir}"
        return {
            "api_base": api_base,
            "ingest_endpoint": f"{api_base}/storage/ingest",
            "workspace_host_path": self.workspace_path,
            "workspace_relative_dir": self.workspace_relative_dir,
            "nextcloud_dir": nextcloud_dir,
            "nextcloud_hint": f"Apps/RPA4ALL/{self.contract_code}",
            "nextcloud_url": f"{self.base_url}/mock-nextcloud",
            "nextcloud_workspace_url": f"{self.base_url}/mock-nextcloud/apps/files/?dir={nextcloud_dir}",
            "authentik_url": f"{self.base_url}/mock-authentik",
            "curl_example": (
                "curl -X POST "
                + f"{api_base}/storage/ingest "
                + "-H 'Authorization: Bearer "
                + str(token_preview)
                + "' "
                + "-H 'Content-Type: application/json' "
                + "-d '{\"relative_path\":\"lote-01/backup.tar\",\"bytes\":2048}'"
            ),
        }

    def _list_path(self, path: str) -> dict[str, object]:
        normalized = path or "."
        entries = list(self.directories.get(normalized, []))
        total_bytes = sum(int(entry.get("size") or 0) for entry in entries if entry.get("kind") == "file")
        return {
            "path": normalized,
            "entries": entries,
            "total_bytes": total_bytes,
        }

    def bootstrap(self, token: str) -> dict[str, object]:
        if token != self.portal_token:
            raise PermissionError("Portal token invalido ou expirado.")
        return {
            "contract": {
                "id": self.contract_id,
                "contract_code": self.contract_code,
                "company": self.company,
                "project": self.project,
                "monthly_service": self.monthly_service,
                "term_months": self.term_months,
                "status": self.status,
                "workspace_relative_dir": self.workspace_relative_dir,
                "workspace_path": self.workspace_path,
            },
            "documents": self._documents(),
            "current_user": dict(self.manager_user),
            "permissions": {
                "generate_tokens": True,
                "manage_profiles": True,
                "manage_payments": True,
            },
            "connections": self._connections(),
            "api_tokens": list(self.api_tokens),
            "users": list(self.users),
            "payments": list(self.payments),
            "files": self._list_path("."),
            "inventory": {
                "host": "mock-homelab",
                "cpu": {"model": "AMD Ryzen Mock", "cores": 8},
                "memory": {"available_gb": 48},
                "disks": [
                    {"mountpoint": "/mnt/mock", "used_gb": 512, "total_gb": 2048},
                    {"mountpoint": "/mnt/mock-archive", "used_gb": 128, "total_gb": 1024},
                ],
                "services": [
                    {"name": "authentik", "status": "running"},
                    {"name": "nextcloud", "status": "running"},
                    {"name": "mercadopago-gateway", "status": "running"},
                ],
            },
        }

    def apply_request_access(self, payload: dict[str, object]) -> dict[str, object]:
        with self.lock:
            self.last_request_payload = dict(payload)
            self.company = str(payload.get("company") or self.company)
            self.project = str(payload.get("project") or self.project)
            self.primary_email = str(payload.get("email") or self.primary_email)
            self.primary_contact = str(payload.get("contact") or self.primary_contact)
            self.term_months = int(payload.get("term") or self.term_months)
            self.monthly_service = int(payload.get("monthly_service") or self.monthly_service)
            self.manager_user.update(
                {
                    "full_name": self.primary_contact,
                    "email": self.primary_email,
                    "username": "mock." + self.primary_contact.lower().replace(" ", "."),
                }
            )
            self.users[0] = dict(self.manager_user)
            return {
                "status": "ok",
                "request_id": "storage-mock-20260315-0001",
                "username": self.manager_user["username"],
                "recipient_email": self.primary_email,
                "login_url": f"{self.base_url}/mock-authentik",
                "contract_code": self.contract_code,
                "portal_url": f"{self.base_url}/storage-portal.html?portal={self.portal_token}",
                "documents": self._documents(),
                "message": "Acesso gerado e enviado para " + self.primary_email,
            }

    def create_api_token(self, label: str) -> dict[str, object]:
        with self.lock:
            token = f"stg_live_mock_{self.next_api_token_id:02d}_secret"
            preview = token[:16] + "..."
            entry = {
                "id": self.next_api_token_id,
                "label": label,
                "preview": preview,
                "status": "active",
                "created_at": self._now(),
            }
            self.api_tokens.append(entry)
            self.next_api_token_id += 1
            return {
                "token": {"token": token, "preview": preview, "label": label, "status": "active"},
                "api_tokens": list(self.api_tokens),
                "connections": self._connections(),
            }

    def create_subuser(self, full_name: str, email: str, profile: str) -> dict[str, object]:
        with self.lock:
            username = "mock." + full_name.lower().replace(" ", ".")
            entry = {
                "id": self.next_user_id,
                "username": username,
                "full_name": full_name,
                "email": email,
                "profile": profile,
                "profile_label": {
                    "manager": "Gestor",
                    "operations": "Operacoes",
                    "api": "Integracao API",
                    "readonly": "Somente leitura",
                }.get(profile, profile),
                "status": "active",
            }
            self.users.append(entry)
            self.next_user_id += 1
            return {"users": list(self.users)}

    def update_user(self, user_id: int, profile: str | None, status: str | None) -> dict[str, object]:
        with self.lock:
            for user in self.users:
                if int(user["id"]) == user_id:
                    if profile:
                        user["profile"] = profile
                        user["profile_label"] = {
                            "manager": "Gestor",
                            "operations": "Operacoes",
                            "api": "Integracao API",
                            "readonly": "Somente leitura",
                        }.get(profile, profile)
                    if status:
                        user["status"] = status
                    break
            return {"users": list(self.users)}

    def create_payment(self, amount_brl: float, description: str) -> dict[str, object]:
        with self.lock:
            entry = {
                "id": self.next_payment_id,
                "amount_brl": amount_brl,
                "description": description,
                "created_at": self._now(),
                "external_reference": f"pay-{self.next_payment_id:03d}",
                "init_point": f"{self.base_url}/mock-checkout/{self.next_payment_id}",
                "sandbox_init_point": f"{self.base_url}/mock-checkout/{self.next_payment_id}?sandbox=1",
            }
            self.payments.append(entry)
            self.next_payment_id += 1
            return {"payments": list(self.payments)}

    def create_folder(self, folder_path: str) -> dict[str, object]:
        with self.lock:
            normalized = (folder_path or "").strip().strip("/")
            if not normalized:
                raise ValueError("folder_path obrigatorio")
            parent = normalized.rsplit("/", 1)[0] if "/" in normalized else "."
            name = normalized.rsplit("/", 1)[-1]
            self.directories.setdefault(parent, [])
            self.directories.setdefault(normalized, [])
            if not any(entry["path"] == normalized for entry in self.directories[parent]):
                self.directories[parent].append(
                    {
                        "name": name,
                        "path": normalized,
                        "kind": "folder",
                        "size": 0,
                        "modified_at": self._now(),
                    }
                )
            return {"files": self._list_path(parent)}


class MockSiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, **kwargs) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    @property
    def state(self) -> MockStoragePortalState:
        return self.server.state  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/agents-api/storage/portal/bootstrap":
            token = parse_qs(parsed.query).get("portal_token", [""])[0]
            try:
                self._write_json(self.state.bootstrap(token))
            except PermissionError as exc:
                self._write_json({"detail": str(exc)}, status=HTTPStatus.UNAUTHORIZED)
            return
        if parsed.path == "/agents-api/storage/portal/files":
            token = parse_qs(parsed.query).get("portal_token", [""])[0]
            path = parse_qs(parsed.query).get("path", ["."])[0]
            if token != self.state.portal_token:
                self._write_json({"detail": "Portal token invalido ou expirado."}, status=HTTPStatus.UNAUTHORIZED)
                return
            self._write_json(self.state._list_path(path))
            return
        if parsed.path == "/mock-nextcloud" or parsed.path.startswith("/mock-nextcloud/apps/files/"):
            requested_dir = parse_qs(parsed.query).get("dir", ["/"])[0]
            self._write_html(self._render_mock_nextcloud(requested_dir))
            return
        if parsed.path in {"/mock-authentik"} or parsed.path.startswith("/mock-checkout/"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Mock endpoint</h1></body></html>")
            return
        super().do_GET()

    def _write_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _render_mock_nextcloud(self, requested_dir: str) -> str:
        workspace_dir = "/" + self.state.workspace_relative_dir
        current_dir = requested_dir if requested_dir and requested_dir != "/" else workspace_dir
        relative = current_dir.lstrip("/")
        if relative.startswith(self.state.workspace_relative_dir):
            relative = relative[len(self.state.workspace_relative_dir):].lstrip("/")
        listing_path = "." if not relative else relative
        listing = self.state._list_path(listing_path)

        items_html = "".join(
            [
                "<tr>"
                + f"<td>{entry['name']}</td>"
                + f"<td>{entry['kind']}</td>"
                + f"<td>{entry.get('size', 0)}</td>"
                + f"<td>{entry.get('modified_at', '-')}</td>"
                + "</tr>"
                for entry in listing.get("entries", [])
            ]
        ) or "<tr><td colspan='4'>Nenhum arquivo</td></tr>"

        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nextcloud Mock - {self.state.company}</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; margin: 0; background: #0e1726; color: #eaf2ff; }}
    .wrap {{ max-width: 1120px; margin: 0 auto; padding: 20px; }}
    .head {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; }}
    .chip {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: #123051; color: #8cd2ff; font-size: 12px; }}
    .panel {{ border: 1px solid #223753; border-radius: 14px; background: #101e33; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #243c5a; font-size: 13px; }}
    th {{ color: #8cd2ff; text-transform: uppercase; font-size: 11px; letter-spacing: 0.08em; }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="head">
      <div>
        <h1 style="margin:0;font-size:22px;">Nextcloud - Arquivos do Contrato</h1>
        <p style="margin:6px 0 0;color:#b7c8de;">Cliente: {self.state.company} | Contrato: {self.state.contract_code}</p>
      </div>
      <span class="chip">Workspace: {workspace_dir}</span>
    </section>
    <section class="panel">
      <p style="margin:0 0 8px;"><strong>Diretório atual:</strong> {current_dir}</p>
      <table>
        <thead>
          <tr><th>Nome</th><th>Tipo</th><th>Tamanho</th><th>Modificado em</th></tr>
        </thead>
        <tbody>{items_html}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/agents-api/llm-tools/chat":
            self._write_json(
                {
                    "answer": (
                        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 900'>"
                        "<rect width='1600' height='900' fill='#081420'/>"
                        "<circle cx='380' cy='250' r='180' fill='rgba(56,189,248,0.25)'/>"
                        "<circle cx='1200' cy='580' r='220' fill='rgba(34,197,94,0.15)'/>"
                        "</svg>"
                    )
                }
            )
            return

        payload = self._read_json()
        if parsed.path == "/agents-api/storage/request-access":
            self._write_json(self.state.apply_request_access(payload))
            return
        if parsed.path == "/agents-api/storage/portal/tokens":
            self._require_portal_token(payload)
            label = str(payload.get("label") or "Integracao principal")
            self._write_json(self.state.create_api_token(label))
            return
        if parsed.path == "/agents-api/storage/portal/subusers":
            self._require_portal_token(payload)
            full_name = str(payload.get("full_name") or "").strip()
            email = str(payload.get("email") or "").strip()
            profile = str(payload.get("profile") or "readonly")
            self._write_json(self.state.create_subuser(full_name, email, profile))
            return
        if parsed.path == "/agents-api/storage/portal/payments":
            self._require_portal_token(payload)
            amount = float(payload.get("amount_brl") or 0)
            description = str(payload.get("description") or "Mensalidade storage gerenciado")
            self._write_json(self.state.create_payment(amount, description))
            return
        if parsed.path == "/agents-api/storage/portal/files/folder":
            self._require_portal_token(payload)
            folder_path = str(payload.get("folder_path") or "")
            self._write_json(self.state.create_folder(folder_path))
            return

        self._write_json({"detail": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/agents-api/storage/portal/users/"):
            self._write_json({"detail": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        payload = self._read_json()
        self._require_portal_token(payload)
        user_id = int(parsed.path.rsplit("/", 1)[-1])
        self._write_json(
            self.state.update_user(
                user_id,
                str(payload.get("profile")) if payload.get("profile") is not None else None,
                str(payload.get("status")) if payload.get("status") is not None else None,
            )
        )

    def _read_json(self) -> dict[str, object]:
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _write_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _require_portal_token(self, payload: dict[str, object]) -> None:
        if str(payload.get("portal_token") or "") != self.state.portal_token:
            self._write_json({"detail": "Portal token invalido ou expirado."}, status=HTTPStatus.UNAUTHORIZED)
            raise PermissionError("portal token invalido")


@pytest.fixture
def mock_user() -> MockUser:
    return MockUser()


@pytest.fixture
def mock_site_server():
    state = MockStoragePortalState()
    handler = partial(MockSiteHandler, directory=str(SITE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.state = state  # type: ignore[attr-defined]
    state.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield SimpleNamespace(base_url=state.base_url, state=state)
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _wait(driver, timeout: int = 10) -> WebDriverWait:
    driver.set_window_size(1480, 1400)
    return WebDriverWait(driver, timeout)


def _set_input(driver, selector: str, value: str) -> None:
    element = _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
    element.click()
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(value)


def _select_value(driver, selector: str, value: str) -> None:
    element = _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    Select(element).select_by_value(value)


def test_index_page_storage_actions_and_revenda_contract(mock_site_server, driver):
    driver.get(mock_site_server.base_url + "/index.html#storage")

    _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#storage.panel.active")))
    assert "Solicitar sizing" in driver.page_source
    assert "Portal de gestão" in driver.page_source

    driver.execute_script("document.querySelector('[data-target=revenda]').click();")
    _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#revenda.panel.active")))

    assert "Minuta contratual" in driver.page_source
    assert "Instrumento base para parceria de revenda de storage" in driver.page_source


def test_storage_request_page_generates_formal_contract_preview(mock_site_server, mock_user, driver):
    driver.get(mock_site_server.base_url + "/storage-request.html?mode=sizing")

    _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#storageRequestForm")))
    assert "Imprimir contrato" in driver.page_source
    _set_input(driver, "#requestCompany", mock_user.company)
    _set_input(driver, "#requestLegalName", mock_user.legal_name)
    _set_input(driver, "#requestCompanyDocument", mock_user.company_document)
    _set_input(driver, "#requestContact", mock_user.contact)
    _set_input(driver, "#requestRole", mock_user.role)
    _set_input(driver, "#requestEmail", mock_user.email)
    _set_input(driver, "#requestPhone", mock_user.phone)
    _set_input(driver, "#requestRepresentativeDocument", mock_user.representative_document)
    _set_input(driver, "#requestProject", mock_user.project)
    _set_input(driver, "#requestAddress", mock_user.address)
    _set_input(driver, "#requestAddressNumber", mock_user.address_number)
    _set_input(driver, "#requestAddressComplement", mock_user.address_complement)
    _set_input(driver, "#requestDistrict", mock_user.district)
    _set_input(driver, "#requestPostalCode", mock_user.postal_code)
    _set_input(driver, "#requestCity", mock_user.city)
    _set_input(driver, "#requestState", mock_user.state)
    _set_input(driver, "#requestStartDate", mock_user.start_date)
    _set_input(driver, "#requestNotes", mock_user.notes)

    preview = _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#requestContractPreview")))
    _wait(driver).until(lambda d: mock_user.company in preview.text)

    preview_text = preview.text
    assert "Minuta particular de prestação de serviços de storage gerenciado" in preview_text
    assert "INSTRUMENTO PARTICULAR" in preview_text
    assert "DOCUMENTO PERSONALIZADO PARA" in preview_text
    assert "Lei nº 13.709/2018" in preview_text
    assert "Medida Provisória nº 2.200-2/2001" in preview_text
    assert "CNPJ sob nº" in preview_text
    assert mock_user.company in preview_text


def test_storage_portal_page_bootstraps_with_mock_token(mock_site_server, driver):
    driver.get(mock_site_server.base_url + "/storage-portal.html?portal=" + mock_site_server.state.portal_token)

    contract_code = _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#portalContractCode")))
    _wait(driver).until(lambda d: contract_code.text == mock_site_server.state.contract_code)

    assert mock_site_server.state.contract_code in driver.page_source
    assert "Mock Industries" in driver.page_source
    assert mock_site_server.base_url + "/agents-api" in driver.page_source
    assert mock_site_server.state.workspace_relative_dir in driver.page_source
    assert "CONTRATO-" + mock_site_server.state.contract_code + ".html" in driver.page_source


def test_storage_mock_user_flow_chain(mock_site_server, mock_user, driver):
    driver.get(mock_site_server.base_url + "/index.html#storage")
    _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#storage.panel.active")))

    _select_value(driver, "#storageTemperature", "archive")
    _set_input(driver, "#storageVolume", "48")
    _set_input(driver, "#storageIngress", "6")
    _select_value(driver, "#storageRetention", "24")
    _select_value(driver, "#storageRetrieval", "monthly")

    continue_button = _wait(driver).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".storage-results-actions a[href='storage-request.html?mode=sizing']"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", continue_button)
    driver.execute_script("arguments[0].click();", continue_button)
    _wait(driver).until(EC.url_contains("storage-request.html?mode=sizing"))
    _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#storageRequestForm")))

    assert driver.find_element(By.CSS_SELECTOR, "#requestVolume").get_attribute("value") == "48"
    assert driver.find_element(By.CSS_SELECTOR, "#requestIngress").get_attribute("value") == "6"
    assert driver.find_element(By.CSS_SELECTOR, "#requestRetention").get_attribute("value") == "24"

    _set_input(driver, "#requestCompany", mock_user.company)
    _set_input(driver, "#requestLegalName", mock_user.legal_name)
    _set_input(driver, "#requestCompanyDocument", mock_user.company_document)
    _set_input(driver, "#requestContact", mock_user.contact)
    _set_input(driver, "#requestRole", mock_user.role)
    _set_input(driver, "#requestEmail", mock_user.email)
    _set_input(driver, "#requestPhone", mock_user.phone)
    _set_input(driver, "#requestRepresentativeDocument", mock_user.representative_document)
    _set_input(driver, "#requestProject", mock_user.project)
    _set_input(driver, "#requestAddress", mock_user.address)
    _set_input(driver, "#requestAddressNumber", mock_user.address_number)
    _set_input(driver, "#requestAddressComplement", mock_user.address_complement)
    _set_input(driver, "#requestDistrict", mock_user.district)
    _set_input(driver, "#requestPostalCode", mock_user.postal_code)
    _set_input(driver, "#requestCity", mock_user.city)
    _set_input(driver, "#requestState", mock_user.state)
    _set_input(driver, "#requestStartDate", mock_user.start_date)
    _set_input(driver, "#requestNotes", mock_user.notes)

    driver.find_element(By.CSS_SELECTOR, "#requestProvisionAccessButton").click()
    status = _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#requestProvisionStatus")))
    _wait(driver).until(lambda d: "Acesso gerado" in status.text)

    driver.get(mock_site_server.base_url + "/storage-portal.html?portal=" + mock_site_server.state.portal_token)
    contract_code = _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#portalContractCode")))
    _wait(driver).until(lambda d: contract_code.text == mock_site_server.state.contract_code)
    _wait(driver).until(lambda d: mock_user.company in d.find_element(By.CSS_SELECTOR, "#portalCompanyName").text)

    _set_input(driver, "#portalTokenLabel", "Pipeline primario")
    driver.find_element(By.CSS_SELECTOR, "#portalCreateTokenButton").click()
    latest_token = _wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#portalLatestTokenValue")))
    _wait(driver).until(lambda d: latest_token.text.startswith("stg_live_mock_"))

    _set_input(driver, "#portalSubUserName", "Ana Operacoes")
    _set_input(driver, "#portalSubUserEmail", "ana.operacoes@mockindustria.test")
    _select_value(driver, "#portalSubUserProfile", "operations")
    driver.find_element(By.CSS_SELECTOR, "#portalCreateUserButton").click()
    _wait(driver).until(lambda d: "Ana Operacoes" in d.find_element(By.CSS_SELECTOR, "#portalUsersTable").text)

    _set_input(driver, "#portalPaymentAmount", "5800")
    _set_input(driver, "#portalPaymentDescription", "Mensalidade inicial mock")
    driver.find_element(By.CSS_SELECTOR, "#portalCreatePaymentButton").click()
    _wait(driver).until(lambda d: "Mensalidade inicial mock" in d.find_element(By.CSS_SELECTOR, "#portalPaymentsList").text)

    _set_input(driver, "#portalFolderPath", "lote-qa")
    driver.find_element(By.CSS_SELECTOR, "#portalCreateFolderButton").click()
    _wait(driver).until(lambda d: "lote-qa" in d.find_element(By.CSS_SELECTOR, "#portalFilesList").text)
    driver.find_element(By.CSS_SELECTOR, ".portal-folder-open[data-path='lote-qa']").click()
    _wait(driver).until(lambda d: d.find_element(By.CSS_SELECTOR, "#portalFilesPath").text == "lote-qa")
