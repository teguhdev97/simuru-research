from __future__ import annotations

import secrets
import string
import time
from typing import Any

from playwright.sync_api import Page

from simuru_research.providers.cpanel_browser_session import CpanelBrowserSession
from simuru_research.providers.mailbox import LOCAL_PART_PATTERN, MailboxError


class CpanelMailboxOperations(CpanelBrowserSession):
    """List, create, import, and reset QA mailboxes through cPanel UAPI."""

    @staticmethod
    def _uapi_result(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize standard UAPI, direct-result and legacy cPanel API 2 envelopes."""
        nested = payload.get("result")
        if isinstance(nested, dict):
            return nested
        direct_keys = {"status", "data", "errors", "messages", "warnings"}
        if direct_keys.intersection(payload):
            return payload
        legacy = payload.get("cpanelresult")
        if isinstance(legacy, dict):
            event = legacy.get("event")
            status = event.get("result") if isinstance(event, dict) else legacy.get("result")
            return {
                "status": status,
                "data": legacy.get("data", []),
                "errors": legacy.get("reason"),
                "messages": None,
                "warnings": None,
            }
        return {}

    @classmethod
    def _uapi_succeeded(cls, payload: dict[str, Any]) -> bool:
        return str(cls._uapi_result(payload).get("status", "")) == "1"

    def _list_mailboxes(self, page: Page) -> list[dict[str, Any]]:
        payload = page.evaluate(
            """async () => {
              const match = location.pathname.match(/^\\/cpsess[^/]+/);
              if (!match) throw new Error('Prefix sesi cPanel tidak ditemukan.');
              const endpoint = match[0] + '/execute/Email/list_pops';
              const response = await fetch(endpoint, {
                method: 'GET',
                credentials: 'same-origin',
                cache: 'no-store',
                headers: {'Accept': 'application/json'}
              });
              if (!response.ok) throw new Error('list_pops HTTP ' + response.status);
              return await response.json();
            }"""
        )
        normalized = self._uapi_result(payload)
        if not self._uapi_succeeded(payload):
            details = normalized.get("errors") or normalized.get("messages") or "Tidak ada detail UAPI."  # noqa: E501
            raise MailboxError(f"Email::list_pops gagal: {details}")
        data = normalized.get("data") or []
        if not isinstance(data, list):
            raise MailboxError("Format data Email::list_pops tidak dikenali.")
        return data

    def list_domain_mailboxes(self) -> list[str]:
        """Return mailbox addresses on the configured QA domain after UAPI authentication."""
        addresses = self.list_domain_email_addresses()
        return [
            email
            for email in addresses
            if email.split("@", 1)[0].startswith(self.prefix)
        ]

    def list_domain_email_addresses(self) -> list[str]:
        """Return all valid mailbox addresses on the configured domain."""
        with self._attached_browser() as (_, _, pages):
            page, _ = self._find_authenticated_page(pages)
            if page is None:
                raise MailboxError("Sesi cPanel belum terverifikasi.")
            rows = self._list_mailboxes(page)
            addresses: list[str] = []
            seen: set[str] = set()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                email = str(row.get("email", "")).strip().lower()
                if email.count("@") != 1:
                    continue
                local_part, domain = email.split("@")
                if (
                    domain == self.domain.lower()
                    and LOCAL_PART_PATTERN.fullmatch(local_part)
                    and email not in seen
                ):
                    addresses.append(email)
                    seen.add(email)
            return addresses

    @staticmethod
    def _generate_mailbox_password() -> str:
        """Generate a unique password when no shared QA password was configured."""
        alphabet = string.ascii_letters + string.digits + "!@#$%_-"
        while True:
            value = "".join(secrets.choice(alphabet) for _ in range(28))
            if (any(c.islower() for c in value) and any(c.isupper() for c in value)
                and any(c.isdigit() for c in value) and any(c in "!@#$%_-" for c in value)):
                return value

    def create_five(self, *, save_credentials: bool = True) -> list[dict[str, str]]:
        """Create five unique mailboxes and optionally persist their passwords."""
        if self.mailbox_password and len(self.mailbox_password) < 12:
            raise MailboxError(
                "Password seragam minimal 12 karakter. Kosongkan field untuk memakai password acak unik."  # noqa: E501
            )
        with self._attached_browser() as (_, _, pages):
            page, diagnostics = self._find_authenticated_page(pages)
            if page is None:
                last = diagnostics[-1] if diagnostics else {}
                raise MailboxError(
                    "Sesi cPanel belum terverifikasi. "
                    f"Detail: {last.get('reason', 'tidak ada tab cPanel aktif')}"
                )

            current = {
                str(item.get("email", "")).lower()
                for item in self._list_mailboxes(page)
                if isinstance(item, dict)
                and str(item.get("email", "")).lower().endswith("@" + self.domain)
            }

            batch = secrets.token_hex(4)
            created: list[dict[str, str]] = []
            for index in range(1, 6):
                local_part = f"{self.prefix}-{batch}-{index:02d}"
                address = f"{local_part}@{self.domain}"
                if address.lower() in current:
                    created.append({
                        "email": address,
                        "password": "",
                        "status": "failed",
                        "error": "Alamat sudah ada; tidak ada akun yang ditimpa.",
                    })
                    break

                password = self.mailbox_password or self._generate_mailbox_password()
                record = {
                    "email": address,
                    "password": password,
                    "status": "pending",
                    "error": "",
                }
                created.append(record)
                try:
                    payload = page.evaluate(
                        """async ({localPart, domain, password, quota}) => {
                          const match = location.pathname.match(/^\\/cpsess[^/]+/);
                          if (!match) throw new Error('Prefix sesi cPanel tidak ditemukan.');
                          const params = new URLSearchParams({
                            email: localPart,
                            domain,
                            password,
                            quota: String(quota),
                            send_welcome_email: '0'
                          });
                          const response = await fetch(
                            match[0] + '/execute/Email/add_pop',
                            {method: 'POST', credentials: 'same-origin', cache: 'no-store',
                             headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                             body: params.toString()}
                          );
                          if (!response.ok) throw new Error('add_pop HTTP ' + response.status);
                          return await response.json();
                        }""",
                        {
                            "localPart": local_part,
                            "domain": self.domain,
                            "password": password,
                            "quota": self.quota_mb,
                        },
                    )
                    if self._uapi_succeeded(payload):
                        record["status"] = "created_pending_verification"
                    else:
                        result = payload.get("result", {})
                        details = result.get("errors") or result.get("messages") or "cPanel menolak permintaan."  # noqa: E501
                        record["status"] = "failed"
                        record["error"] = str(details)
                        break
                except Exception as exc:
                    record["status"] = "unknown"
                    record["error"] = (
                        f"Respons add_pop tidak dapat dipastikan: {type(exc).__name__}. "
                        "Alamat akan dicek ulang melalui list_pops."
                    )
                    break
                time.sleep(0.25)

            try:
                verified = self._list_mailboxes(page)
                verified_addresses = {
                    str(item.get("email", "")).lower()
                    for item in verified
                    if isinstance(item, dict)
                }
                for record in created:
                    if record["email"].lower() in verified_addresses:
                        record["status"] = "created"
                        record["error"] = ""
                    elif record["status"] != "failed":
                        record["status"] = "failed"
                        record["error"] = (
                            record["error"]
                            or "Alamat tidak ditemukan pada verifikasi list_pops."
                        )
            except Exception as exc:
                for record in created:
                    if record["status"] != "failed":
                        record["status"] = "unverified"
                        record["error"] = (
                            f"Mailbox belum dapat diverifikasi: {type(exc).__name__}. "
                            "Jangan menganggap batch ini berhasil."
                        )
            for record in created:
                if record.get("status") != "created":
                    continue
                if not save_credentials:
                    record["credential_storage"] = "not_saved"
                    continue
                try:
                    self.credential_vault.save(record["email"], record["password"])
                    record["credential_storage"] = "saved"
                except (RuntimeError, ValueError) as exc:
                    record["credential_storage"] = "failed"
                    record["error"] = f"Credential storage failed: {type(exc).__name__}"
            return created

    def import_mailbox_credential(self, email: str, password: str) -> None:
        """Import an owner-provided QA mailbox password into the local OS credential store."""
        normalized = email.strip().lower()
        if not normalized.endswith('@' + self.domain):
            raise MailboxError('Mailbox email is outside the configured domain.')
        if not normalized.split('@', 1)[0].startswith(self.prefix + '-'):
            raise MailboxError('Mailbox email does not use the configured QA prefix.')
        if not password:
            raise MailboxError('Mailbox password cannot be empty.')
        self.credential_vault.save_many(
            [{"email": normalized, "password": password, "status": "created"}]
        )

    def reset_mailbox_passwords(self, emails: list[str]) -> list[dict[str, str]]:
        """Reset up to five explicitly selected QA mailboxes to the configured local password."""
        if len(self.mailbox_password) < 12:
            raise MailboxError("Masukkan shared QA mailbox password di dashboard (minimal 12 karakter).")  # noqa: E501
        normalized = [email.strip().lower() for email in emails]
        if not normalized or len(normalized) > 5 or len(set(normalized)) != len(normalized):
            raise MailboxError("Pilih satu sampai lima alamat mailbox yang unik.")
        if any(not email.endswith("@" + self.domain) for email in normalized):
            raise MailboxError("Reset hanya diizinkan untuk mailbox pada domain QA ini.")
        results: list[dict[str, str]] = []
        with self._attached_browser() as (_, _, pages):
            page, _ = self._find_authenticated_page(pages)
            if page is None:
                raise MailboxError("Sesi cPanel belum terverifikasi.")
            existing = {str(row.get("email", "")).lower() for row in self._list_mailboxes(page) if isinstance(row, dict)}  # noqa: E501
            for email in normalized:
                if email not in existing:
                    results.append({"email": email, "status": "not_found"})
                    continue
                local_part = email.rsplit("@", 1)[0]
                payload = page.evaluate(
                    """async ({localPart, domain, password}) => {
                      const match = location.pathname.match(/^\\/cpsess[^/]+/);
                      if (!match) throw new Error('Prefix sesi cPanel tidak ditemukan.');
                      const params = new URLSearchParams({email: localPart, domain, password});
                      const response = await fetch(match[0] + '/execute/Email/passwd_pop',
                        {method: 'POST', credentials: 'same-origin', cache: 'no-store',
                         headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                         body: params.toString()});
                      if (!response.ok) throw new Error('passwd_pop HTTP ' + response.status);
                      return await response.json();
                    }""",
                    {"localPart": local_part, "domain": self.domain, "password": self.mailbox_password},  # noqa: E501
                )
                updated = self._uapi_succeeded(payload)
                results.append({"email": email, "status": "updated" if updated else "failed"})
                if updated:
                    self.credential_vault.save_many([{"email": email, "password": self.mailbox_password, "status": "created"}])  # noqa: E501
        return results
