from __future__ import annotations

import imaplib
import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from html.parser import HTMLParser

from simuru_research.providers.mailbox import (
    LOCAL_PART_PATTERN,
    MailboxError,
    MailboxSettings,
)
from simuru_research.security.mailbox_vault import MailboxCredentialVault


@dataclass(frozen=True, slots=True)
class InboxMessage:
    message_id: str
    sender: str
    subject: str
    date: str


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._hidden_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._hidden_depth += 1
        elif tag in {"br", "p", "div", "li"} and not self._hidden_depth:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1
        elif tag in {"p", "div", "li"} and not self._hidden_depth:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self._chunks.append(data)

    def text(self) -> str:
        return "\n".join(
            line.strip()
            for line in "".join(self._chunks).splitlines()
            if line.strip()
        )


class ImapInboxReader:
    """Read mailbox headers and plain-text message bodies over read-only IMAP."""

    def __init__(
        self,
        settings: MailboxSettings,
        credential_vault: MailboxCredentialVault | None = None,
        *,
        allow_non_qa_mailboxes: bool = False,
    ) -> None:
        self.settings = settings
        self.credential_vault = credential_vault or MailboxCredentialVault()
        self.allow_non_qa_mailboxes = allow_non_qa_mailboxes

    def list_messages(
        self,
        destination: str,
        *,
        limit: int = 50,
    ) -> list[InboxMessage]:
        normalized = self._validate_destination(destination)
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        password = self._password_for(normalized)
        try:
            with self._connect(normalized, password) as client:
                status, data = client.search(None, "ALL")
                if (
                    status != "OK"
                    or not data
                    or not isinstance(data[0], bytes)
                ):
                    raise MailboxError("Could not list messages in IMAP INBOX.")
                message_ids = data[0].split()[-limit:]
                messages: list[InboxMessage] = []
                for message_id in reversed(message_ids):
                    status, parts = client.fetch(
                        message_id,
                        "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])",
                    )
                    if status != "OK":
                        raise MailboxError("Could not read an IMAP inbox message header.")
                    raw = self._first_message_bytes(parts)
                    if raw is None:
                        raise MailboxError("An IMAP inbox message has no readable header.")
                    message = message_from_bytes(raw)
                    messages.append(
                        InboxMessage(
                            message_id=message_id.decode("ascii", errors="replace"),
                            sender=_decode_header(message.get("From", "")),
                            subject=_decode_header(message.get("Subject", ""))
                            or "(tanpa subjek)",
                            date=message.get("Date", ""),
                        )
                    )
                return messages
        except (imaplib.IMAP4.error, OSError) as exc:
            raise MailboxError(f"IMAP inbox access failed: {type(exc).__name__}") from exc

    def read_message(self, destination: str, message_id: str) -> dict[str, str]:
        normalized = self._validate_destination(destination)
        if not message_id.isascii() or not message_id.isdecimal():
            raise MailboxError("Invalid IMAP message identifier.")
        password = self._password_for(normalized)
        try:
            with self._connect(normalized, password) as client:
                status, parts = client.fetch(
                    message_id.encode("ascii"),
                    "(BODY.PEEK[])",
                )
                if status != "OK":
                    raise MailboxError("Could not open the selected inbox message.")
                raw = self._first_message_bytes(parts)
                if raw is None:
                    raise MailboxError("The selected inbox message has no readable body.")
                message = message_from_bytes(raw)
                return {
                    "sender": _decode_header(message.get("From", "")),
                    "subject": _decode_header(message.get("Subject", ""))
                    or "(tanpa subjek)",
                    "date": message.get("Date", ""),
                    "body": _message_body(message)[:20_000],
                }
        except (imaplib.IMAP4.error, OSError) as exc:
            raise MailboxError(f"IMAP message access failed: {type(exc).__name__}") from exc

    def _validate_destination(self, destination: str) -> str:
        normalized = destination.strip().lower()
        if normalized.count("@") != 1:
            raise MailboxError("Destination must be a single valid email address.")
        local_part, domain = normalized.split("@")
        if domain != self.settings.domain.lower():
            raise MailboxError("Destination is outside the configured QA domain.")
        if not LOCAL_PART_PATTERN.fullmatch(local_part):
            raise MailboxError("Destination contains an invalid mailbox name.")
        if (
            not self.allow_non_qa_mailboxes
            and not local_part.startswith(self.settings.prefix.lower() + "-")
        ):
            raise MailboxError("Destination does not use the configured QA mailbox prefix.")
        return normalized

    def _password_for(self, destination: str) -> str:
        password = (self.settings.mailbox_passwords or {}).get(destination)
        password = password or self.settings.mailbox_master_password.strip()
        password = password or self.credential_vault.get(destination)
        if not password:
            raise MailboxError(
                "Mailbox password is not configured. Set QA_MAILBOX_MASTER_PASSWORD "
                "or enter a temporary password in the inbox."
            )
        return password

    @contextmanager
    def _connect(self, destination: str, password: str) -> Iterator[imaplib.IMAP4_SSL]:
        try:
            with imaplib.IMAP4_SSL(
                self.settings.imap_host,
                self.settings.imap_port,
                ssl_context=ssl.create_default_context(),
                timeout=15,
            ) as client:
                client.login(destination, password)
                status, _ = client.select("INBOX", readonly=True)
                if status != "OK":
                    raise MailboxError(
                        "IMAP login succeeded, but INBOX could not be opened."
                    )
                yield client
        except imaplib.IMAP4.error as exc:
            if _is_authentication_error(str(exc)):
                raise MailboxError(
                    "IMAP menolak kredensial mailbox. Pastikan password yang digunakan "
                    "adalah password mailbox (bukan password cPanel). Periksa "
                    "QA_MAILBOX_MASTER_PASSWORD atau coba password mailbox sementara."
                ) from exc
            raise MailboxError(
                f"IMAP connection failed: {type(exc).__name__}"
            ) from exc

    @staticmethod
    def _first_message_bytes(parts: object) -> bytes | None:
        if not isinstance(parts, list):
            return None
        return next(
            (
                item[1]
                for item in parts
                if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes)
            ),
            None,
        )


def _decode_header(value: str) -> str:
    chunks: list[str] = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            chunks.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            chunks.append(part)
    return "".join(chunks)


def _message_body(message: Message) -> str:
    plain_text: list[str] = []
    html_text: list[str] = []
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        content = payload.decode(
            part.get_content_charset() or "utf-8",
            errors="replace",
        )
        if content_type == "text/plain":
            plain_text.append(content)
        else:
            parser = _HTMLTextExtractor()
            parser.feed(content)
            html_text.append(parser.text())
    return "\n\n".join(plain_text or html_text).strip()


def _is_authentication_error(message: str) -> bool:
    normalized = message.casefold()
    return any(
        marker in normalized
        for marker in (
            "authenticationfailed",
            "authentication failed",
            "login failed",
            "invalid credentials",
            "not authenticated",
        )
    )
