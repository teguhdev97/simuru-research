from __future__ import annotations

import keyring
import pytest

from simuru_research.security.mailbox_vault import MailboxCredentialVault


def test_vault_saves_and_reads_password(monkeypatch):
    values = {}

    def set_password(service, username, password):
        values[(service, username)] = password

    def get_password(service, username):
        return values.get((service, username))

    monkeypatch.setattr(keyring, "set_password", set_password)
    monkeypatch.setattr(keyring, "get_password", get_password)

    vault = MailboxCredentialVault()
    vault.save("QA-01@TEGUHHARITS.COM", "local-test-secret")
    assert vault.get("qa-01@teguhharits.com") == "local-test-secret"


def test_vault_save_many_ignores_unverified_rows(monkeypatch):
    values = {}
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, username, password: values.__setitem__((service, username), password),
    )
    monkeypatch.setattr(
        keyring,
        "get_password",
        lambda service, username: values.get((service, username)),
    )
    vault = MailboxCredentialVault()
    vault.save_many([
        {"email": "qa-01@teguhharits.com", "password": "secret-1", "status": "created"},
        {"email": "qa-02@teguhharits.com", "password": "secret-2", "status": "failed"},
    ])
    assert len(values) == 1
    assert vault.get("qa-01@teguhharits.com") == "secret-1"


def test_vault_surfaces_os_credential_store_errors(monkeypatch):
    def fail(*args, **kwargs):
        raise keyring.errors.KeyringError("credential store unavailable")

    monkeypatch.setattr(keyring, "set_password", fail)
    with pytest.raises(RuntimeError, match="Credential Manager"):
        MailboxCredentialVault().save("qa-01@teguhharits.com", "secret")
