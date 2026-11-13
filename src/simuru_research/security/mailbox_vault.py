from __future__ import annotations

from keyring.errors import KeyringError
import keyring


class MailboxCredentialVault:
    """Store mailbox passwords in the OS credential manager, not SQLite or Git."""

    SERVICE = "simuru-research/mailbox"

    def save_many(self, rows: list[dict[str, str]]) -> None:
        saved: list[str] = []
        try:
            for row in rows:
                email = row.get("email", "").strip().lower()
                password = row.get("password", "")
                if row.get("status") != "created" or not email or not password:
                    continue
                keyring.set_password(self.SERVICE, email, password)
                saved.append(email)
        except KeyringError as exc:
            for email in saved:
                try:
                    keyring.delete_password(self.SERVICE, email)
                except KeyringError:
                    pass
            raise RuntimeError(
                "Windows Credential Manager rejected mailbox credential storage. "
                "No mailbox passwords were written to the application database."
            ) from exc

    def get(self, email: str) -> str | None:
        try:
            return keyring.get_password(self.SERVICE, email.strip().lower())
        except KeyringError as exc:
            raise RuntimeError("Cannot read mailbox credentials from the OS credential store.") from exc

    def delete(self, email: str) -> None:
        try:
            keyring.delete_password(self.SERVICE, email.strip().lower())
        except keyring.errors.PasswordDeleteError:
            return
        except KeyringError as exc:
            raise RuntimeError("Cannot delete mailbox credential from the OS credential store.") from exc
