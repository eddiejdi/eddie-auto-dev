from __future__ import annotations

from pathlib import Path
import sys

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import storage_portal_api as api


class FakeAuthentikClient:
    def __init__(self) -> None:
        self.created_users: list[dict[str, str]] = []

    def create_or_update_user(self, username: str, email: str, full_name: str, activation_code: str) -> dict[str, int | str]:
        self.created_users.append(
            {
                "username": username,
                "email": email,
                "full_name": full_name,
                "activation_code": activation_code,
            }
        )
        return {"authentik_user_id": len(self.created_users)}


class FakeMailboxProvisioner:
    def __init__(self) -> None:
        self.created_mailboxes: list[str] = []

    def create_mailbox(self, email_address: str, full_name: str, activation_code: str) -> dict[str, str]:
        self.created_mailboxes.append(email_address)
        return {"status": "created", "email": email_address}


class FakeOnboardingMailer:
    def __init__(self) -> None:
        self.deliveries: list[dict[str, object]] = []

    def send(self, recipients: list[str], context: dict[str, object]) -> None:
        self.deliveries.append({"recipients": recipients, "context": context})


def build_service(tmp_path: Path) -> tuple[api.StoragePortalService, FakeAuthentikClient, FakeMailboxProvisioner, FakeOnboardingMailer]:
    settings = api.Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        workspace_root=tmp_path / "data" / "contracts",
        database_path=tmp_path / "data" / "storage_portal.db",
        authentik_url="https://auth.rpa4all.com",
        authentik_token="fake-token",
        authentik_verify_tls=False,
        authentik_groups=["users"],
        mail_domain="rpa4all.com",
        smtp_host="mail.rpa4all.com",
        smtp_port=587,
        smtp_username="it@rpa4all.com",
        smtp_password="fake-smtp-password",
        smtp_from_email="it@rpa4all.com",
        smtp_from_name="RPA4ALL Onboarding",
        smtp_starttls=True,
        nextcloud_url="https://nextcloud.rpa4all.com",
        nextcloud_base_path="/Storage Contracts",
        authentik_public_url="https://auth.rpa4all.com",
        public_site_url="https://www.rpa4all.com",
        portal_public_url="https://www.rpa4all.com/storage-portal.html",
        api_public_base="https://api.rpa4all.com/agents-api",
        ingest_path="/storage/ingest",
        manage_payments=False,
        mailbox_create_command="",
    )
    authentik = FakeAuthentikClient()
    mailbox = FakeMailboxProvisioner()
    mailer = FakeOnboardingMailer()
    service = api.StoragePortalService(
        settings=settings,
        repository=api.StorageRepository(settings.database_path),
        authentik_client=authentik,
        mailbox_provisioner=mailbox,
        onboarding_mailer=mailer,
    )
    return service, authentik, mailbox, mailer


def sample_request_payload() -> dict[str, object]:
    return {
        "mode": "space",
        "company": "Clinica Horizonte",
        "legal_name": "Clinica Horizonte LTDA",
        "company_document": "12.345.678/0001-90",
        "contact": "Ana Souza",
        "role": "Diretora de Operacoes",
        "email": "ana.souza@gmail.com",
        "personal_email": "ana.souza@gmail.com",
        "phone": "+55 11 99999-0000",
        "representative_document": "123.456.789-01",
        "project": "Arquivamento de exames",
        "address": "Rua das Flores",
        "address_number": "100",
        "address_complement": "Sala 5",
        "district": "Centro",
        "postal_code": "01010-000",
        "temperature": "warm",
        "volume": 20,
        "ingress": 3,
        "retention": "12",
        "retrieval": "rare",
        "sla": "24h",
        "compliance": "standard",
        "redundancy": "single",
        "billing": "monthly",
        "term": 12,
        "start_date": "2026-04-15",
        "city": "Sao Paulo",
        "state": "SP",
        "notes": "Contrato inicial para guarda digital.",
        "monthly_service": 4200,
        "setup_fee": 950,
        "contract_value": 51350,
        "notice_days": 30,
        "breach_penalty": 8400,
    }


def test_request_access_bootstrap_and_finalize(tmp_path: Path, monkeypatch) -> None:
    service, authentik, mailbox, mailer = build_service(tmp_path)
    monkeypatch.setattr(api, "_service_instance", service)
    client = TestClient(api.app)

    create_response = client.post("/storage/request-access", json=sample_request_payload())
    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data["success"] is True
    assert create_data["portal_token"].startswith("stp_")
    assert create_data["corporate_email"].endswith("@rpa4all.com")
    assert Path(tmp_path / create_data["documents"]["html_relative_path"]).exists()
    assert Path(tmp_path / create_data["documents"]["text_relative_path"]).exists()
    assert len(authentik.created_users) == 1
    assert mailbox.created_mailboxes == [create_data["corporate_email"]]
    assert len(mailer.deliveries) == 1
    assert set(mailer.deliveries[0]["recipients"]) == {
        create_data["corporate_email"],
        "ana.souza@gmail.com",
    }

    bootstrap_response = client.get("/storage/portal/bootstrap", params={"portal_token": create_data["portal_token"]})
    assert bootstrap_response.status_code == 200
    bootstrap_data = bootstrap_response.json()
    assert bootstrap_data["contract"]["contract_code"] == create_data["contract_code"]
    assert bootstrap_data["current_user"]["profile"] == "manager"
    assert bootstrap_data["permissions"]["manage_profiles"] is True
    assert bootstrap_data["documents"]["html_relative_path"] == create_data["documents"]["html_relative_path"]

    finalize_response = client.post(
        "/storage/contracts/finalize",
        json={
            "portal_token": create_data["portal_token"],
            "signed_contract_html": "<html><body>Contrato assinado digitalmente</body></html>",
            "signed_contract_filename": "contrato-assinado.html",
        },
    )
    assert finalize_response.status_code == 200
    finalized = finalize_response.json()
    signed_relative_path = finalized["documents"]["signed_relative_path"]
    assert signed_relative_path
    assert Path(tmp_path / signed_relative_path).exists()


def test_create_subuser_and_generate_api_token(tmp_path: Path, monkeypatch) -> None:
    service, authentik, _, mailer = build_service(tmp_path)
    monkeypatch.setattr(api, "_service_instance", service)
    client = TestClient(api.app)

    create_response = client.post("/storage/request-access", json=sample_request_payload())
    portal_token = create_response.json()["portal_token"]

    token_response = client.post(
        "/storage/portal/tokens",
        json={"portal_token": portal_token, "label": "Integracao principal"},
    )
    assert token_response.status_code == 200
    token_data = token_response.json()
    assert token_data["token"]["token"].startswith("sta_")
    assert token_data["api_tokens"][0]["label"] == "Integracao principal"

    subuser_response = client.post(
        "/storage/portal/subusers",
        json={
            "portal_token": portal_token,
            "full_name": "Bruno Lima",
            "email": "bruno.lima@cliente.com.br",
            "profile": "api",
        },
    )
    assert subuser_response.status_code == 200
    subuser_data = subuser_response.json()
    assert len(subuser_data["users"]) == 2
    assert any(user["full_name"] == "Bruno Lima" for user in subuser_data["users"])
    assert len(authentik.created_users) == 2
    assert len(mailer.deliveries) == 2
