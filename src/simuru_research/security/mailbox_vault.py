from __future__ import annotations

import keyring
from keyring.errors import KeyringError


class MailboxCredentialVault:
    """Store mailbox passwords in the operating system credential manager."""

    SERVICE = "simuru-research/mailbox"

    def save(self, email: str, password: str) -> None:
        normalized = email.strip().lower()
        if not normalized or not password:
            raise ValueError("Email and password are required.")
        try:
            keyring.set_password(self.SERVICE, normalized, password)
        except KeyringError as exc:
            raise RuntimeError(
                "Windows Credential Manager could not save this mailbox credential."
            ) from exc

    def save_many(self, rows: list[dict[str, str]]) -> None:
        for row in rows:
            if row.get("status") != "created":
                continue
            email = row.get("email", "").strip().lower()
            password = row.get("password", "")
            if not email or not password:
                continue
            self.save(email, password)

    def get(self, email: str) -> str | None:
        try:
            return keyring.get_password(self.SERVICE, email.strip().lower())
        except KeyringError as exc:
            raise RuntimeError(
                "Cannot read mailbox credentials from the OS credential store."
            ) from exc

    def delete(self, email: str) -> None:
        try:
            keyring.delete_password(self.SERVICE, email.strip().lower())
        except keyring.errors.PasswordDeleteError:
            return
        except KeyringError as exc:
            raise RuntimeError(
                "Cannot delete mailbox credential from the OS credential store."
            ) from exc
