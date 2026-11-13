from __future__ import annotations

import secrets
import socket
import string
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from simuru_research.providers.mailbox import MailboxError


class CpanelBrowserMailboxManager:
    """Attach Playwright to a persistent local Chromium process.

    Streamlit reruns its script after each button click, so a Playwright object
    must not be kept across Streamlit script threads. Chromium runs independently
    with a local CDP endpoint; each Streamlit run creates a fresh Playwright client
    and attaches to that same browser process.
    """

    def __init__(
        self,
        *,
        cpanel_url: str,
        domain: str = "teguhharits.com",
        prefix: str = "qa",
        quota_mb: int = 50,
        profile_dir: str = "data/cpanel-browser-profile",
        debug_port: int = 9222,
    ) -> None:
        self.cpanel_url = cpanel_url.rstrip("/")
        self.domain = domain.lower()
        self.prefix = prefix
        self.quota_mb = quota_mb
        self.profile_dir = Path(profile_dir)
        self.debug_port = debug_port
        self._process: subprocess.Popen | None = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
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
        if not 1024 <= self.debug_port <= 65535:
            raise MailboxError("Invalid local Chromium debugging port.")

    @property
    def _cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.debug_port}"

    def _cdp_ready(self) -> bool:
        try:
            with urlopen(f"{self._cdp_url}/json/version", timeout=1) as response:
                return response.status == 200
        except (OSError, URLError):
            return False

    def _attach(self) -> None:
        if self._browser is not None and self._browser.is_connected():
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                pages = self._context.pages
                cpanel_pages = [
                    page for page in pages
                    if "juwana.iixcp.rumahweb.net" in page.url and ":2083" in page.url
                ]
                self._page = cpanel_pages[0] if cpanel_pages else (
                    pages[0] if pages else self._context.new_page()
                )
                return

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(
                self._cdp_url, timeout=60_000
            )
        except Exception:
            self._playwright.stop()
            self._playwright = None
            raise
        contexts = self._browser.contexts
        self._context = contexts[0] if contexts else self._browser.new_context()
        pages = self._context.pages
        cpanel_pages = [
            page for page in pages
            if "juwana.iixcp.rumahweb.net" in page.url and ":2083" in page.url
        ]
        self._page = cpanel_pages[0] if cpanel_pages else (
            pages[0] if pages else self._context.new_page()
        )

    def connect(self) -> str:
        """Start/attach to visible Chromium; user signs in manually."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        if not self._cdp_ready():
            # Read the installed Playwright Chromium path, then stop the driver
            # before launching the browser as an independent persistent process.
            probe = sync_playwright().start()
            executable = Path(probe.chromium.executable_path)
            probe.stop()
            if not executable.exists():
                raise MailboxError(
                    "Chromium belum terpasang. Jalankan: uv run playwright install chromium"
                )
            command = [
                str(executable),
                f"--remote-debugging-port={self.debug_port}",
                f"--user-data-dir={self.profile_dir.resolve()}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--new-window",
                self.cpanel_url,
            ]
            try:
                self._process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            except OSError as exc:
                raise MailboxError(f"Gagal membuka Chromium: {type(exc).__name__}") from exc
            for _ in range(40):
                if self._cdp_ready():
                    break
                if self._process.poll() is not None:
                    raise MailboxError(
                        "Chromium berhenti saat startup. Tutup semua jendela Chromium "
                        "yang memakai profil SIMURU lalu coba lagi."
                    )
                time.sleep(0.25)
            if not self._cdp_ready():
                raise MailboxError(
                    "Chromium tidak membuka koneksi lokal. Pastikan port 9222 tidak dipakai "
                    "aplikasi lain, lalu coba lagi."
                )

        try:
            self._attach()
        except Exception as exc:
            raise MailboxError(
                "Chromium aktif tetapi Playwright gagal menyelesaikan handshake CDP. "
                "Tutup semua proses Chromium SIMURU, pastikan port 9222 tidak dipakai, "
                "lalu klik Connect cPanel lagi. Detail: "
                f"{type(exc).__name__}"
            ) from exc
        assert self._page is not None
        if self._page.url in {"about:blank", "chrome://newtab/"}:
            self._page.goto(self.cpanel_url, wait_until="domcontentloaded")
        return self._page.url

    def _ensure_attached(self) -> Page:
        if not self._cdp_ready():
            raise MailboxError(
                "Browser cPanel belum aktif. Klik Connect cPanel terlebih dahulu."
            )
        self._attach()
        assert self._page is not None
        return self._page

    def _cpanel_pages(self) -> list[Page]:
        """Return all tabs belonging to the configured cPanel host."""
        if not self._cdp_ready():
            return []
        self._attach()
        assert self._context is not None
        expected_host = self.cpanel_url.split("://", 1)[-1].split("/", 1)[0].lower()
        return [
            page for page in reversed(self._context.pages)
            if page.url.lower().startswith("https://")
            and expected_host in page.url.lower()
            and ":2083" in page.url.lower()
        ]

    @staticmethod
    def _probe_cpanel_page(page: Page, domain: str) -> dict[str, Any]:
        return page.evaluate(
            """async (domain) => {
              const result = {
                ok: false,
                pageUrl: location.href,
                title: document.title,
                origin: location.origin,
                path: location.pathname
              };
              const match = location.pathname.match(/^\\/cpsess[^/]+/);
              if (!match) {
                result.reason = 'URL tab tidak memiliki prefix sesi /cpsess...';
                return result;
              }
              const endpoint = new URL(
                match[0] + '/execute/Email/list_pops?domain=' + encodeURIComponent(domain),
                location.origin
              );
              result.endpointPath = endpoint.pathname;
              try {
                const response = await fetch(endpoint.href, {
                  method: 'GET',
                  credentials: 'same-origin',
                  cache: 'no-store',
                  headers: {'Accept': 'application/json'}
                });
                result.httpStatus = response.status;
                result.responseUrl = response.url;
                result.redirected = response.redirected;
                const raw = await response.text();
                let payload;
                try { payload = JSON.parse(raw); }
                catch (_) {
                  result.reason = 'UAPI tidak mengembalikan JSON; kemungkinan diarahkan ke halaman login.';
                  result.responsePreview = raw.slice(0, 180).replace(/\\s+/g, ' ');
                  return result;
                }
                const apiStatus = payload?.result?.status;
                result.apiStatus = apiStatus ?? null;
                result.apiErrors = payload?.result?.errors ?? null;
                result.apiMessages = payload?.result?.messages ?? null;
                result.ok = response.ok && String(apiStatus) === '1' && !response.redirected;
                if (!result.ok) {
                  result.reason = response.redirected
                    ? 'Permintaan UAPI dialihkan; sesi mungkin kedaluwarsa.'
                    : (result.apiErrors || result.apiMessages || 'UAPI menolak permintaan atau status API bukan 1.');
                }
                return result;
              } catch (error) {
                result.reason = 'Fetch UAPI gagal: ' + String(error);
                return result;
              }
            }""",
            domain,
        )

    def session_status(self) -> dict[str, Any]:
        """Check authenticated UAPI access across all open cPanel tabs."""
        try:
            pages = self._cpanel_pages()
            if not pages:
                return {
                    "connected": False,
                    "message": "Tab cPanel tidak ditemukan pada Chromium SIMURU. Klik Connect cPanel.",
                    "diagnostics": [],
                }
            diagnostics: list[dict[str, Any]] = []
            for page in pages:
                try:
                    probe = self._probe_cpanel_page(page, self.domain)
                    diagnostics.append(probe)
                    if probe.get("ok"):
                        self._page = page
                        return {
                            "connected": True,
                            "message": "Sesi cPanel aktif; UAPI Email::list_pops berhasil diakses.",
                            "diagnostics": diagnostics,
                        }
                except Exception as exc:
                    diagnostics.append({
                        "pageUrl": page.url,
                        "reason": f"{type(exc).__name__}: {exc}",
                    })
            last = diagnostics[-1] if diagnostics else {}
            reason = last.get("reason") or "Tidak ada tab cPanel yang lolos pemeriksaan UAPI."
            return {
                "connected": False,
                "message": f"Browser cPanel ditemukan, tetapi UAPI belum terautentikasi: {reason}",
                "diagnostics": diagnostics,
            }
        except Exception as exc:
            return {
                "connected": False,
                "message": f"Gagal memeriksa browser cPanel: {type(exc).__name__}: {exc}",
                "diagnostics": [],
            }

    def create_eight(self) -> list[dict[str, str]]:
        """Create exactly eight unique mailboxes using the authenticated cPanel session."""
        page = self._ensure_attached()
        status = self.session_status()
        if not status.get("connected"):
            raise MailboxError(
                "Sesi cPanel belum login. Klik Connect cPanel dan selesaikan login manual."
            )

        existing = page.evaluate(
            """async (domain) => {
              const match = location.pathname.match(/^\/cpsess[^/]+/);
              if (!match) throw new Error('cPanel session prefix not found in URL');
              const endpoint = match[0] + '/execute/Email/list_pops?domain=' + encodeURIComponent(domain);
              const response = await fetch(endpoint, {credentials: 'same-origin'});
              if (!response.ok) throw new Error('list_pops HTTP ' + response.status);
              return await response.json();
            }""",
            self.domain,
        )
        result = existing.get("result", {})
        if result.get("status") != 1:
            raise MailboxError("cPanel list_pops gagal. Pastikan login ke akun hosting.")
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
                  const match = location.pathname.match(/^\/cpsess[^/]+/);
                  if (!match) throw new Error('cPanel session prefix not found in URL');
                  const response = await fetch(match[0] + '/execute/Email/add_pop?' + params.toString(), {
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
              const match = location.pathname.match(/^\/cpsess[^/]+/);
              if (!match) throw new Error('cPanel session prefix not found in URL');
              const endpoint = match[0] + '/execute/Email/list_pops?domain=' + encodeURIComponent(domain);
              const response = await fetch(endpoint, {credentials: 'same-origin'});
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
        """Log out of cPanel, clear this browser context, then close Chromium."""
        logout_result = "not_connected"
        try:
            page = self._ensure_attached() if self._cdp_ready() else None
            if page is not None:
                origin = page.evaluate("() => location.origin")
                path = page.evaluate("() => location.pathname")
                match = __import__("re").match(r"^(/cpsess[^/]+)", path)
                if match and origin.startswith("https://") and ":2083" in origin:
                    session_prefix = match.group(1)
                    logout_target = page.evaluate(
                        """() => {
                          const link = [...document.querySelectorAll('a[href]')].find(a =>
                            /logout/i.test(a.href) || /log\s*out/i.test(a.innerText || '')
                          );
                          return link ? link.href : null;
                        }"""
                    )
                    if not logout_target:
                        logout_target = f"{origin}{session_prefix}/logout/?locale=en"
                    # Navigate through cPanel's own logout route so the server
                    # invalidates the authenticated session (not merely the local tab).
                    page.goto(logout_target, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(500)
                    logout_result = "logout_requested"
                else:
                    logout_result = "no_cpanel_session"
        except Exception:
            # Still close the local browser even if cPanel is unreachable.
            logout_result = "logout_unconfirmed"

        try:
            if self._context is not None:
                self._context.clear_cookies()
        except Exception:
            pass
        try:
            if self._browser is not None and self._browser.is_connected():
                self._browser.close()
        finally:
            if self._playwright is not None:
                self._playwright.stop()
            self._playwright = None
            self._browser = None
            self._context = None
            self._page = None
        if logout_result == "logout_unconfirmed":
            raise MailboxError(
                "Browser ditutup dan cookie lokal dibersihkan, tetapi logout server cPanel "
                "belum dapat dikonfirmasi. Periksa status login cPanel sebelum digunakan lagi."
            )
