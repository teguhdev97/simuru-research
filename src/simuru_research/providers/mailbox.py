from __future__ import annotations

import base64
import hashlib
import hmac
import imaplib
import os
import re
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

import httpx
from dotenv import load_dotenv

OTP_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")
LOCAL_PART_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


@dataclass(frozen=True, slots=True)
class MailboxSettings:
    domain: str
    prefix: str
    cpanel_host: str
    cpanel_username: str
    cpanel_api_token: str
    mailbox_master_password: str
    mailbox_quota_mb: int
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    sender_allowlist: tuple[str, ...]
    subject_keywords: tuple[str, ...]

    @classmethod
    def from_env(cls) -> MailboxSettings:
        load_dotenv()
        domain = os.getenv("QA_MAIL_DOMAIN", "teguhharits.com").strip().lower()
        return cls(
            domain=domain,
            prefix=os.getenv("QA_MAIL_PREFIX", "qa").strip().lower(),
            cpanel_host=os.getenv("QA_CPANEL_HOST", "").strip(),
            cpanel_username=os.getenv("QA_CPANEL_USERNAME", "").strip(),
            cpanel_api_token=os.getenv("QA_CPANEL_API_TOKEN", "").strip(),
            mailbox_master_password=os.getenv("QA_MAILBOX_MASTER_PASSWORD", "").strip(),
            mailbox_quota_mb=int(os.getenv("QA_MAILBOX_QUOTA_MB", "50")),
            imap_host=os.getenv("QA_IMAP_HOST", f"mail.{domain}").strip(),
            imap_port=int(os.getenv("QA_IMAP_PORT", "993")),
            smtp_host=os.getenv("QA_SMTP_HOST", f"mail.{domain}").strip(),
            smtp_port=int(os.getenv("QA_SMTP_PORT", "465")),
            sender_allowlist=tuple(
                item.strip().lower()
                for item in os.getenv("QA_OTP_ALLOWED_SENDERS", "").split(",")
                if item.strip()
            ),
            subject_keywords=tuple(
                item.strip().lower()
                for item in os.getenv(
                    "QA_OTP_SUBJECT_KEYWORDS", "verification,verify,otp,code"
                ).split(",")
                if item.strip()
            ),
        )

    def validate_provisioning(self) -> None:
        if not self.domain or "." not in self.domain:
            raise MailboxError("QA_MAIL_DOMAIN is not a valid domain.")
        if not LOCAL_PART_PATTERN.fullmatch(self.prefix):
            raise MailboxError("QA_MAIL_PREFIX contains unsupported characters.")
        if not all((self.cpanel_host, self.cpanel_username, self.cpanel_api_token)):
            raise MailboxError(
                "Set QA_CPANEL_HOST, QA_CPANEL_USERNAME, and QA_CPANEL_API_TOKEN in .env."
            )
        if len(self.mailbox_master_password) < 24:
            raise MailboxError(
                "Set QA_MAILBOX_MASTER_PASSWORD to a secret of at least 24 characters."
            )
        if not 1 <= self.mailbox_quota_mb <= 5000:
            raise MailboxError("QA_MAILBOX_QUOTA_MB must be between 1 and 5000.")
        if self.cpanel_host.startswith(("http://", "https://")):
            raise MailboxError("QA_CPANEL_HOST must be a hostname only, without scheme.")


class MailboxError(RuntimeError):
    """Mailbox provisioning or OTP retrieval failed."""


class MailboxProvisioner:
    """Create exactly five domain mailboxes with the cPanel UAPI add_pop endpoint."""

    def __init__(self, settings: MailboxSettings) -> None:
        self.settings = settings

    def create_five(self, run_id: str) -> tuple[str, ...]:
        self.settings.validate_provisioning()
        run_suffix = re.sub(r"[^a-f0-9]", "", run_id.lower())[:8]
        if len(run_suffix) != 8:
            raise MailboxError("A valid run ID is required to generate mailbox names.")

        created: list[str] = []
        url = f"https://{self.settings.cpanel_host}:2083/execute/Email/add_pop"
        headers = {
            "Authorization": (
                f"cpanel {self.settings.cpanel_username}:{self.settings.cpanel_api_token}"
            )
        }
        try:
            with httpx.Client(timeout=30.0, verify=True) as client:
                for index in range(1, 6):
                    local_part = f"{self.settings.prefix}-{run_suffix}-{index:02d}"
                    address = f"{local_part}@{self.settings.domain}"
                    response = client.get(
                        url,
                        headers=headers,
                        params={
                            "email": local_part,
                            "domain": self.settings.domain,
                            "password": self.password_for(address),
                            "quota": self.settings.mailbox_quota_mb,
                            "send_welcome_email": 0,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    result = payload.get("result", {})
                    if result.get("status") != 1:
                        details = result.get("errors") or result.get("messages") or []
                        raise MailboxError(
                            f"cPanel rejected {address} after creating "
                            f"{len(created)} mailbox(es): "
                            f"{', '.join(map(str, details)) or 'unknown error'}. "
                            f"Already created: {', '.join(created) or 'none'}"
                        )
                    created.append(address)
        except httpx.HTTPError as exc:
            raise MailboxError(
                f"cPanel UAPI request failed after {len(created)} mailbox(es): "
                f"{type(exc).__name__}. Created mailboxes: {', '.join(created) or 'none'}"
            ) from exc
        return tuple(created)

    def password_for(self, address: str) -> str:
        """Derive a distinct deterministic password without persisting mailbox secrets."""
        digest = hmac.new(
            self.settings.mailbox_master_password.encode("utf-8"),
            address.lower().encode("utf-8"),
            hashlib.sha256,
        ).digest()
        token = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"{token[:32]}aA9!"


class ImapOTPReader:
    """Read fresh OTP only from an owned-domain mailbox and allowlisted sender."""

    def __init__(self, settings: MailboxSettings) -> None:
        self.settings = settings
        self.provisioner = MailboxProvisioner(settings)

    def wait_for_otp(
        self,
        destination: str,
        *,
        since: datetime | None = None,
        timeout_seconds: int = 120,
        poll_interval: float = 3.0,
    ) -> str:
        if timeout_seconds < 1 or timeout_seconds > 300:
            raise ValueError("timeout_seconds must be between 1 and 300.")
        if not destination.lower().endswith("@" + self.settings.domain.lower()):
            raise MailboxError("Destination is outside the configured QA domain.")
        if not destination.lower().startswith(self.settings.prefix.lower() + "-"):
            raise MailboxError("Destination does not use the configured QA mailbox prefix.")
        if not self.settings.sender_allowlist:
            raise MailboxError("Configure QA_OTP_ALLOWED_SENDERS before reading OTP messages.")
        if not self.settings.subject_keywords:
            raise MailboxError("Configure QA_OTP_SUBJECT_KEYWORDS before reading OTP messages.")

        cutoff = since or (datetime.now(UTC) - timedelta(minutes=5))
        deadline = time.monotonic() + timeout_seconds
        mailbox_password = self.provisioner.password_for(destination)

        while time.monotonic() < deadline:
            try:
                with imaplib.IMAP4_SSL(
                    self.settings.imap_host,
                    self.settings.imap_port,
                    ssl_context=ssl.create_default_context(),
                    timeout=15,
                ) as client:
                    client.login(destination, mailbox_password)
                    status, _ = client.select("INBOX", readonly=True)
                    if status != "OK":
                        raise MailboxError("Cannot select IMAP INBOX.")
                    status, data = client.search(None, "UNSEEN")
                    if status != "OK":
                        raise MailboxError("Cannot search IMAP inbox.")
                    message_ids = data[0].split()[-30:]
                    for message_id in reversed(message_ids):
                        status, parts = client.fetch(message_id, "(RFC822)")
                        if status != "OK" or not parts or not isinstance(parts[0], tuple):
                            continue
                        message = message_from_bytes(parts[0][1])
                        sender = _decode_header(message.get("From", "")).lower()
                        if not any(allowed in sender for allowed in self.settings.sender_allowlist):
                            continue
                        try:
                            received = parsedate_to_datetime(message.get("Date", ""))
                            if received.tzinfo is None:
                                received = received.replace(tzinfo=UTC)
                            if received.astimezone(UTC) < cutoff.astimezone(UTC):
                                continue
                        except (TypeError, ValueError, OverflowError):
                            continue
                        if not self._subject_matches(message.get("Subject", "")):
                            continue
                        match = OTP_PATTERN.search(_message_text(message))
                        if match:
                            return match.group(1)
            except (imaplib.IMAP4.error, OSError) as exc:
                raise MailboxError(f"IMAP access failed: {type(exc).__name__}") from exc
            time.sleep(poll_interval)
        raise MailboxError("No matching fresh OTP arrived before timeout.")

    def _subject_matches(self, subject: str) -> bool:
        decoded = _decode_header(subject).lower()
        return any(keyword in decoded for keyword in self.settings.subject_keywords)


class SmtpMailboxSender:
    """Send a mailbox connectivity test to one of the generated QA mailboxes."""

    def __init__(self, settings: MailboxSettings) -> None:
        self.settings = settings
        self.provisioner = MailboxProvisioner(settings)

    def send_test(self, destination: str) -> None:
        if not destination.lower().endswith("@" + self.settings.domain.lower()):
            raise MailboxError("Destination is outside the configured QA domain.")
        message = EmailMessage()
        message["Subject"] = "SIMURU QA mailbox connectivity test"
        message["From"] = destination
        message["To"] = destination
        message.set_content("This is a local QA mailbox connectivity check.")
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            self.settings.smtp_host, self.settings.smtp_port, context=context, timeout=20
        ) as client:
            client.login(destination, self.provisioner.password_for(destination))
            client.send_message(message)


def _decode_header(value: str) -> str:
    output: list[str] = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            output.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            output.append(part)
    return "".join(output)


def _message_text(message) -> str:
    chunks: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() not in {"text/plain", "text/html"}:
                continue
            payload = part.get_payload(decode=True)
            if payload:
                chunks.append(
                    payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                )
    else:
        payload = message.get_payload(decode=True)
        if payload:
            chunks.append(
                payload.decode(message.get_content_charset() or "utf-8", errors="replace")
            )
    return "\n".join(chunks)
