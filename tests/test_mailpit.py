from __future__ import annotations

from email.message import EmailMessage

import pytest

from simuru_research.engine.registration_qa import LocalRegistrationQARunner
from simuru_research.providers.mailpit import MailpitEmailProvider
from simuru_research.security.auth_qa import LocalAuthQAService
from simuru_research.storage.database import SQLiteRepository


class FakeSMTP:
    sent_messages: list[EmailMessage] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def noop(self) -> tuple[int, bytes]:
        return 250, b"OK"

    def send_message(self, message: EmailMessage) -> dict[str, tuple[int, bytes]]:
        self.sent_messages.append(message)
        return {}


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


def test_mailpit_sends_and_reads_local_verification_email(monkeypatch) -> None:
    FakeSMTP.sent_messages = []
    monkeypatch.setattr(
        "simuru_research.providers.mailpit.smtplib.SMTP",
        FakeSMTP,
    )

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/api/v1/info"):
            return FakeResponse({"Version": "1.33.1"})
        if url.endswith("/api/v1/messages"):
            return FakeResponse(
                {
                    "messages": [
                        {
                            "ID": "mailpit-message-1",
                            "To": [{"Address": "qa-user@example.test"}],
                        }
                    ]
                }
            )
        if url.endswith("/api/v1/message/mailpit-message-1"):
            return FakeResponse({"Text": "SIMURU-QA-OTP: 123456"})
        raise AssertionError(f"Unexpected Mailpit URL: {url}")

    monkeypatch.setattr(
        "simuru_research.providers.mailpit.httpx.get",
        fake_get,
    )

    provider = MailpitEmailProvider(
        poll_interval_seconds=0.001,
        poll_timeout_seconds=0.1,
    )

    info = provider.check_connection()
    provider.send_verification_code(
        recipient="qa-user@example.test",
        code="123456",
        run_id="run-123",
        job_index=1,
    )
    received_code = provider.wait_for_verification_code(
        recipient="qa-user@example.test",
    )

    assert info["Version"] == "1.33.1"
    assert received_code == "123456"
    assert len(FakeSMTP.sent_messages) == 1
    message = FakeSMTP.sent_messages[0]
    assert message["To"] == "qa-user@example.test"
    assert message["X-Simuru-QA-Run-ID"] == "run-123"
    assert "SIMURU-QA-OTP: 123456" in message.get_content()


def test_mailpit_provider_rejects_non_loopback_services() -> None:
    with pytest.raises(ValueError, match="loopback"):
        MailpitEmailProvider(api_url="http://192.168.1.10:8025")

    with pytest.raises(ValueError, match="loopback"):
        MailpitEmailProvider(smtp_host="mailpit.example.com")


def test_mailpit_provider_rejects_non_reserved_recipient() -> None:
    provider = MailpitEmailProvider()

    with pytest.raises(ValueError, match="example.test"):
        provider.send_verification_code(
            recipient="real-user@example.com",
            code="123456",
            run_id="run-123",
            job_index=1,
        )


def test_registration_batch_uses_mailpit_provider_for_email_otp(tmp_path) -> None:
    class FakeEmailProvider:
        sent: dict[str, str] = {}

        def send_verification_code(
            self,
            *,
            recipient: str,
            code: str,
            run_id: str,
            job_index: int,
        ) -> None:
            self.sent[recipient] = code

        def wait_for_verification_code(self, *, recipient: str) -> str:
            return self.sent[recipient]

    database_path = tmp_path / "mailpit-qa.sqlite3"
    repository = SQLiteRepository(database_path)
    auth_service = LocalAuthQAService(database_path)
    provider = FakeEmailProvider()

    summary = LocalRegistrationQARunner(
        repository,
        auth_service,
        email_provider=provider,
    ).run_batch(total_jobs=4, max_workers=2)

    assert summary.passed == 4
    assert summary.failed == 0
    assert len(provider.sent) == 4
    assert all(email.endswith("@example.test") for email in provider.sent)
