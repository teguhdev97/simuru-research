from __future__ import annotations

import imaplib
import re
import secrets
import smtplib
import ssl
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from datetime import UTC, datetime, timedelta
from typing import Iterable

OTP_PATTERN = re.compile(r"(?<!\\d)(\\d{6})(?!\\d)")


@dataclass(frozen=True, slots=True)
class MailboxSettings:
    domain: str
    addresses: tuple[str, ...]
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    sender_allowlist: tuple[str, ...]
    subject_keywords: tuple[str, ...]


class MailboxError(RuntimeError):
    """Mailbox provisioning or OTP retrieval failed."""


class MailboxProvisioner:
    """Create up to five mailboxes through an authenticated SMTP/cPanel-compatible API.

    This class deliberately does not scrape a cPanel browser session or use session tokens.
    If the hosting provider has no mailbox-provisioning API, mailboxes must be created
    manually in its control panel; IMAP is used only for reading inboxes.
    """

    def __init__(self, settings: MailboxSettings) -> None:
        self.settings = settings

    def addresses_for_batch(self, run_id: str) -> tuple[str, ...]:
        if len(self.settings.addresses) != 5:
            raise MailboxError("Exactly five pre-created QA mailbox addresses are required.")
        if any(not address.lower().endswith("@" + self.settings.domain.lower())
               for address in self.settings.addresses):
            raise MailboxError("Every QA mailbox must belong to the configured domain.")
        return self.settings.addresses


class ImapOTPReader:
    """Read a fresh OTP only from the configured QA inbox and allowlisted senders."""

    def __init__(self, settings: MailboxSettings) -> None:
        self.settings = settings

    def wait_for_otp(
        self,
        destination: str,
        *,
        since: datetime | None = None,
        timeout_seconds: int = 120,
        poll_interval: float = 3.0,
    ) -> str:
        import time

        if destination.lower() not in {a.lower() for a in self.settings.addresses}:
            raise MailboxError("Destination is not one of the configured QA mailboxes.")
        if timeout_seconds < 1 or timeout_seconds > 300:
            raise ValueError("timeout_seconds must be between 1 and 300.")
        cutoff = since or (datetime.now(UTC) - timedelta(minutes=5))
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            try:
                with imaplib.IMAP4_SSL(
                    self.settings.imap_host,
                    self.settings.imap_port,
                    ssl_context=ssl.create_default_context(),
                    timeout=15,
                ) as client:
                    client.login(self.settings.username, self.settings.password)
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
                        if not any(allowed.lower() in sender for allowed in self.settings.sender_allowlist):
                            continue
                        try:
                            received = parsedate_to_datetime(message.get("Date", ""))
                            if received.tzinfo is None:
                                received = received.replace(tzinfo=UTC)
                            if received.astimezone(UTC) < cutoff.astimezone(UTC):
                                continue
                        except (TypeError, ValueError, OverflowError):
                            continue
                        body = _message_text(message)
                        for match in OTP_PATTERN.finditer(body):
                            code = match.group(1)
                            if self._subject_matches(message.get("Subject", "")):
                                return code
            except (imaplib.IMAP4.error, OSError) as exc:
                raise MailboxError(f"IMAP access failed: {type(exc).__name__}") from exc
            time.sleep(poll_interval)
        raise MailboxError("No matching fresh OTP arrived before timeout.")

    def _subject_matches(self, subject: str) -> bool:
        if not self.settings.subject_keywords:
            return True
        decoded = _decode_header(subject).lower()
        return any(keyword.lower() in decoded for keyword in self.settings.subject_keywords)


class SmtpMailboxSender:
    """Send a harmless mailbox connectivity test; does not create provider mailboxes."""

    def __init__(self, settings: MailboxSettings) -> None:
        self.settings = settings

    def send_test(self, destination: str) -> None:
        if destination.lower() not in {a.lower() for a in self.settings.addresses}:
            raise MailboxError("Destination is not one of the configured QA mailboxes.")
        message = EmailMessage()
        message["Subject"] = "SIMURU QA mailbox connectivity test"
        message["From"] = self.settings.username
        message["To"] = destination
        message.set_content("This is a local QA mailbox connectivity check.")
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            self.settings.smtp_host, self.settings.smtp_port, context=context, timeout=20
        ) as client:
            client.login(self.settings.username, self.settings.password)
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
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    else:
        payload = message.get_payload(decode=True)
        if payload:
            chunks.append(payload.decode(message.get_content_charset() or "utf-8", errors="replace"))
    return "\\n".join(chunks)
