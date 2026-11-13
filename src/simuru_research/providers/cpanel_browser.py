from __future__ import annotations

import secrets
import string
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from simuru_research.providers.mailbox import MailboxError


class CpanelBrowserMailboxManager:
    """Use the user's interactive cPanel browser session without exporting cookies/tokens."""

    def __init__(
        self,
        *,
        cpanel_url: str,
        domain: str = "teguhharits.com",
        prefix: str = "qa",
        quota_mb: int = 50,
        profile_dir: str = "data/cpanel-browser-profile",
    ) -> None:
        self.cpanel_url = cpanel_url.rstrip("/")
        self.domain = domain.lower()
        self.prefix = prefix
        self.quota_mb = quota_mb
        self.profile_dir = Path(profile_dir)
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

        if not self.cpanel_url.startswith("https://"):
            raise MailboxError("cPanel must use HTTPS.")
        if not self.domain or "." not in self.domain:
            raise MailboxError("Invalid mailbox domain.")
        if not self.prefix.replace("-", "").isalnum():
            raise MailboxError("Mailbox prefix may contain only letters, numbers, and hyphens.")
        if not 1 <= self.quota_mb <= 5000:
            raise MailboxError("Mailbox quota must be between 1 and 5000 MB.")

    def connect(self) -> str:
        """Open a visible persistent browser; the user completes login manually."""
        if self._context is None:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            self._playwright = sync_playwright().start()
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir.resolve()),
                headless=False,
                viewport={"width": 1440, "height": 960},
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        assert self._page is not None
        self._page.goto(self.cpanel_url, wait_until="domcontentloaded")
        return self._page.url

    def session_status(self) -> dict[str, Any]:
        if self._page is None or self._page.is_closed():
            return {"connected": False, "message": "Browser belum dibuka."}
        return self._page.evaluate(
            """() => ({
              url: location.origin + location.pathname,
              loggedIn: !document.body.innerText.toLowerCase().includes('login to cpanel')
            })"""
        ) | {"connected": True}

    def create_eight(self) -> list[dict[str, str]]:
        """Create exactly eight unique mailboxes using same-origin UAPI fetch."""
        if self._page is None or self._page.is_closed():
            raise MailboxError("Klik Connect cPanel dan login terlebih dahulu.")
        page = self._page
        origin = page.evaluate("() => location.origin")
        if not origin.startswith("https://") or ":2083" not in origin:
            raise MailboxError("Browser tidak berada pada cPanel HTTPS port 2083.")
        status = self.session_status()
        if not status.get("connected"):
            raise MailboxError("Sesi browser cPanel belum tersedia.")

        existing = page.evaluate(
            """async (domain) => {
              const response = await fetch('/execute/Email/list_pops?domain=' + encodeURIComponent(domain), {
                credentials: 'same-origin'
              });
              if (!response.ok) throw new Error('list_pops HTTP ' + response.status);
              return await response.json();
            }""",
            self.domain,
        )
        result = existing.get("result", {})
        if result.get("status") != 1:
            raise MailboxError("cPanel list_pops gagal. Pastikan sudah login ke akun hosting.")
        current = {
            str(item.get("email", "")).lower()
            for item in (result.get("data") or [])
            if isinstance(item, dict)
        }

        batch = secrets.token_hex(4)
        alphabet = string.ascii_letters + string.digits + "!@#$%_-"
        created: list[dict[str, str]] = []
        for index in range(1, 9):
            local_part = f"{self.prefix}-{batch}-{index:02d}"
            address = f"{local_part}@{self.domain}"
            if address.lower() in current:
                raise MailboxError(f"Alamat {address} sudah ada. Jalankan batch baru.")
            password = "".join(secrets.choice(alphabet) for _ in range(24)) + "aA9!"
            payload = page.evaluate(
                """async ({localPart, domain, password, quota}) => {
                  const params = new URLSearchParams({
                    email: localPart,
                    domain,
                    password,
                    quota: String(quota),
                    send_welcome_email: '0'
                  });
                  const response = await fetch('/execute/Email/add_pop?' + params.toString(), {
                    method: 'GET',
                    credentials: 'same-origin'
                  });
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
            add_result = payload.get("result", {})
            if add_result.get("status") != 1:
                details = add_result.get("errors") or add_result.get("messages") or []
                raise MailboxError(
                    f"Gagal membuat {address} setelah {len(created)} mailbox. "
                    f"{'; '.join(map(str, details)) or 'cPanel menolak permintaan.'}"
                )
            created.append({"email": address, "password": password, "status": "created"})
            time.sleep(0.25)

        verified = page.evaluate(
            """async (domain) => {
              const response = await fetch('/execute/Email/list_pops?domain=' + encodeURIComponent(domain), {
                credentials: 'same-origin'
              });
              if (!response.ok) throw new Error('list_pops HTTP ' + response.status);
              return await response.json();
            }""",
            self.domain,
        )
        verified_items = verified.get("result", {}).get("data") or []
        verified_addresses = {
            str(item.get("email", "")).lower()
            for item in verified_items
            if isinstance(item, dict)
        }
        for item in created:
            if item["email"].lower() not in verified_addresses:
                item["status"] = "created_unverified"
        return created

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._context = None
        self._playwright = None
        self._page = None
