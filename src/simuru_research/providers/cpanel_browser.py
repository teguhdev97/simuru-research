from __future__ import annotations

<<<<<<< HEAD
import os
import re
import secrets
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
=======
import secrets
import socket
import string
import subprocess
import time
from pathlib import Path
from typing import Any
>>>>>>> 2e84aec661483ce823d55cc430ea697861497d00
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from simuru_research.providers.mailbox import MailboxError


class CpanelBrowserMailboxManager:
<<<<<<< HEAD
    """Manage a local Chromium session and call cPanel UAPI as the signed-in user.

    Playwright clients are intentionally short-lived: Streamlit reruns UI code and
    may execute fragments on different threads. Chromium itself remains an
    independent process with a persistent local profile and CDP endpoint.
=======
    """Attach Playwright to a persistent local Chromium process.

    Streamlit reruns its script after each button click, so a Playwright object
    must not be kept across Streamlit script threads. Chromium runs independently
    with a local CDP endpoint; each Streamlit run creates a fresh Playwright client
    and attaches to that same browser process.
>>>>>>> 2e84aec661483ce823d55cc430ea697861497d00
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
<<<<<<< HEAD
        mailbox_password: str | None = None,
=======
>>>>>>> 2e84aec661483ce823d55cc430ea697861497d00
    ) -> None:
        self.cpanel_url = cpanel_url.rstrip("/")
        self.domain = domain.lower()
        self.prefix = prefix
        self.quota_mb = quota_mb
        self.profile_dir = Path(profile_dir)
        self.debug_port = debug_port
<<<<<<< HEAD
        self.mailbox_password = mailbox_password or os.getenv("QA_MAILBOX_MASTER_PASSWORD", "").strip()
=======
        self._process: subprocess.Popen | None = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
>>>>>>> 2e84aec661483ce823d55cc430ea697861497d00

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

<<<<<<< HEAD
    @contextmanager
    def _attached_browser(self) -> Iterator[tuple[Browser, BrowserContext, list[Page]]]:
        """Create a fresh Playwright client and attach to the independent Chromium."""
        if not self._cdp_ready():
            raise MailboxError("Chromium cPanel belum aktif. Klik Connect cPanel terlebih dahulu.")
        playwright: Playwright = sync_playwright().start()
        browser: Browser | None = None
        try:
            browser = playwright.chromium.connect_over_cdp(self._cdp_url, timeout=20_000)
            contexts = browser.contexts
            if not contexts:
                raise MailboxError("Chromium aktif tetapi tidak memiliki browser context.")
            context = contexts[0]
            yield browser, context, context.pages
        except MailboxError:
            raise
        except Exception as exc:
            raise MailboxError(
                f"Gagal menghubungkan Playwright ke Chromium CDP: {type(exc).__name__}. "
                "Tutup Chromium SIMURU yang lama, lalu klik Connect cPanel lagi."
            ) from exc
        finally:
            # Stop the Playwright driver only; do not close the user's browser here.
            playwright.stop()

    def _is_cpanel_page(self, page: Page) -> bool:
        host = self.cpanel_url.split("://", 1)[-1].split("/", 1)[0].lower()
        return page.url.lower().startswith("https://") and host in page.url.lower()

    def connect(self) -> str:
        """Start visible Chromium if necessary; user signs in manually."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        if not self._cdp_ready():
            probe = sync_playwright().start()
            try:
                executable = Path(probe.chromium.executable_path)
            finally:
                probe.stop()
=======
    def _attach(self) -> None:
        if self._browser is not None and self._browser.is_connected():
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                pages = self._context.pages
                self._page = pages[0] if pages else self._context.new_page()
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
        self._page = (
            cpanel_pages[0]
            if cpanel_pages
            else pages[0] if pages else self._context.new_page()
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
>>>>>>> 2e84aec661483ce823d55cc430ea697861497d00
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
<<<<<<< HEAD
                subprocess.Popen(
=======
                self._process = subprocess.Popen(
>>>>>>> 2e84aec661483ce823d55cc430ea697861497d00
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            except OSError as exc:
                raise MailboxError(f"Gagal membuka Chromium: {type(exc).__name__}") from exc
<<<<<<< HEAD

            for _ in range(60):
                if self._cdp_ready():
                    break
                time.sleep(0.25)
            if not self._cdp_ready():
                raise MailboxError(
                    "Chromium tidak membuka koneksi lokal pada port debugging. "
                    "Pastikan port 9222 tidak sedang dipakai aplikasi lain."
                )

        return "Browser cPanel dibuka. Selesaikan login manual pada jendela Chromium."

    @staticmethod
    def _probe_page(page: Page) -> dict[str, Any]:
        """Call list_pops without optional filters to isolate session auth from query errors."""
        return page.evaluate(
            """async () => {
              const result = {
                ok: false,
                pageUrl: location.origin + location.pathname.replace(/^\\/cpsess[^/]+/, '/cpsess[redacted]'),
                title: document.title,
                origin: location.origin,
                path: location.pathname.replace(/^\\/cpsess[^/]+/, '/cpsess[redacted]')
              };
              const match = location.pathname.match(/^\\/cpsess[^/]+/);
              if (!match) {
                result.reason = 'URL tab tidak memiliki prefix sesi cPanel.';
                return result;
              }

              const endpoint = new URL(match[0] + '/execute/Email/list_pops', location.origin);
              result.endpointPath = endpoint.pathname.replace(/^\\/cpsess[^/]+/, '/cpsess[redacted]');
              try {
                const response = await fetch(endpoint.href, {
                  method: 'GET',
                  credentials: 'same-origin',
                  cache: 'no-store',
                  headers: {'Accept': 'application/json'}
                });
                result.httpStatus = response.status;
                result.contentType = response.headers.get('content-type') || '';
                const responseUrl = new URL(response.url);
                result.responseUrl = responseUrl.origin + responseUrl.pathname.replace(/^\\/cpsess[^/]+/, '/cpsess[redacted]');
                result.redirected = response.redirected;

                const raw = await response.text();
                let payload;
                try {
                  payload = JSON.parse(raw);
                } catch (_) {
                  result.reason = 'UAPI tidak mengembalikan JSON; kemungkinan dialihkan ke halaman login.';

                  return result;
                }

                // Accept both the documented {result:{status,data,...}} envelope and
                // direct {status,data,...} responses returned by some cPanel integrations.
                const apiResult = payload?.result && typeof payload.result === 'object'
                  ? payload.result : payload;
                const legacy = payload?.cpanelresult && typeof payload.cpanelresult === 'object'
                  ? payload.cpanelresult : null;
                const apiStatus = apiResult?.status
                  ?? legacy?.event?.result
                  ?? legacy?.result
                  ?? null;
                const safe = (value) => value == null ? null
                  : JSON.stringify(value).replace(/cpsess[^/\\s"'<>]+/gi, 'cpsess[redacted]');
                const useful = (value) => value != null
                  && !(Array.isArray(value) && value.length === 0)
                  && !(typeof value === 'string' && value.trim() === '');
                const errors = apiResult?.errors ?? legacy?.reason ?? null;
                const messages = apiResult?.messages ?? null;
                const warnings = apiResult?.warnings ?? null;
                result.apiStatus = apiStatus;
                result.apiErrors = useful(errors) ? safe(errors) : null;
                result.apiMessages = useful(messages) ? safe(messages) : null;
                result.apiWarnings = useful(warnings) ? safe(warnings) : null;
                result.topLevelKeys = Object.keys(payload || {});
                result.resultKeys = apiResult && typeof apiResult === 'object'
                  ? Object.keys(apiResult) : [];
                const data = apiResult?.data ?? legacy?.data;
                result.dataType = Array.isArray(data) ? 'array' : typeof data;
                result.ok = response.ok && String(apiStatus) === '1' && !response.redirected;
                if (!result.ok) {
                  result.reason = response.redirected
                    ? 'UAPI dialihkan ke halaman lain; sesi mungkin kedaluwarsa.'
                    : (result.apiErrors || result.apiMessages || result.apiWarnings
                      || 'HTTP berhasil, tetapi envelope JSON tidak berisi status sukses UAPI. Lihat topLevelKeys dan resultKeys.');
                }
                return result;
              } catch (error) {
                result.reason = 'Fetch UAPI gagal: ' + String(error)
                  .replace(/cpsess[^/\\s"'<>]+/gi, 'cpsess[redacted]');
                return result;
              }
            }"""
        )

    def _find_authenticated_page(self, pages: list[Page]) -> tuple[Page | None, list[dict[str, Any]]]:
        diagnostics: list[dict[str, Any]] = []
        for page in reversed(pages):
            if not self._is_cpanel_page(page):
                continue
            try:
                probe = self._probe_page(page)
                diagnostics.append(probe)
                if probe.get("ok"):
                    return page, diagnostics
            except Exception as exc:
                diagnostics.append({
                    "pageUrl": "cPanel tab (URL disamarkan)",
                    "reason": re.sub(
                        r"cpsess[^/\\s\"'<>]+", "cpsess[redacted]", f"{type(exc).__name__}: {exc}"
                    ),
                })
        return None, diagnostics

    def session_status(self) -> dict[str, Any]:
        """Auto-check all open cPanel tabs and verify actual UAPI access."""
        try:
            with self._attached_browser() as (_, _, pages):
                page, diagnostics = self._find_authenticated_page(pages)
                if page is not None:
                    return {
                        "connected": True,
                        "message": "Sesi cPanel aktif; UAPI Email::list_pops berhasil diakses.",
                        "diagnostics": diagnostics,
                    }
                if not any(self._is_cpanel_page(p) for p in pages):
                    message = "Browser aktif, tetapi tab cPanel tidak ditemukan. Klik Connect cPanel."
                elif diagnostics:
                    last = diagnostics[-1]
                    message = (
                        "Tab cPanel ditemukan, tetapi UAPI gagal. "
                        f"HTTP={last.get('httpStatus', '—')}; "
                        f"API status={last.get('apiStatus', '—')}; "
                        f"Alasan={last.get('reason', 'Tidak diketahui')}"
                    )
                else:
                    message = "Tab cPanel ditemukan, tetapi sesi belum dapat diverifikasi."
                return {
                    "connected": False,
                    "message": message,
                    "diagnostics": diagnostics,
                }
        except MailboxError as exc:
            return {"connected": False, "message": str(exc), "diagnostics": []}

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
            details = normalized.get("errors") or normalized.get("messages") or "Tidak ada detail UAPI."
            raise MailboxError(f"Email::list_pops gagal: {details}")
        data = normalized.get("data") or []
        if not isinstance(data, list):
            raise MailboxError("Format data Email::list_pops tidak dikenali.")
        return data

    def list_domain_mailboxes(self) -> list[str]:
        """Return mailbox addresses on the configured QA domain after UAPI authentication."""
        with self._attached_browser() as (_, _, pages):
            page, _ = self._find_authenticated_page(pages)
            if page is None:
                raise MailboxError("Sesi cPanel belum terverifikasi.")
            rows = self._list_mailboxes(page)
            return sorted({
                str(row.get("email", "")).strip().lower()
                for row in rows
                if isinstance(row, dict)
                and str(row.get("email", "")).strip().lower().endswith("@" + self.domain)
                and str(row.get("email", "")).strip().lower().split("@", 1)[0].startswith(self.prefix)
            })

    @staticmethod
    def _generate_mailbox_password() -> str:
        """Generate a unique password when no shared QA password was configured."""
        alphabet = string.ascii_letters + string.digits + "!@#$%_-"
        while True:
            value = "".join(secrets.choice(alphabet) for _ in range(28))
            if (any(c.islower() for c in value) and any(c.isupper() for c in value)
                and any(c.isdigit() for c in value) and any(c in "!@#$%_-" for c in value)):
                return value

    def create_five(self) -> list[dict[str, str]]:
        """Create exactly five unique mailboxes with a configured or generated QA password."""
        if self.mailbox_password and len(self.mailbox_password) < 12:
            raise MailboxError(
                "Password seragam minimal 12 karakter. Kosongkan field untuk memakai password acak unik."
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
                        details = result.get("errors") or result.get("messages") or "cPanel menolak permintaan."
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
            return created

    def reset_mailbox_passwords(self, emails: list[str]) -> list[dict[str, str]]:
        """Reset up to five explicitly selected QA mailboxes to the local master password."""
        if len(self.mailbox_password) < 12:
            raise MailboxError("QA_MAILBOX_MASTER_PASSWORD belum diatur di .env lokal.")
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
            existing = {str(row.get("email", "")).lower() for row in self._list_mailboxes(page) if isinstance(row, dict)}
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
                    {"localPart": local_part, "domain": self.domain, "password": self.mailbox_password},
                )
                results.append({"email": email, "status": "updated" if self._uapi_succeeded(payload) else "failed"})
        return results

    @staticmethod
    def _validate_oauth_target_url(url: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise MailboxError("Masukkan URL website HTTP(S) yang valid.")
        if parsed.username or parsed.password:
            raise MailboxError("URL target tidak boleh mengandung kredensial.")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise MailboxError("Website remote harus menggunakan HTTPS.")
        return url.strip()

    def open_website_for_oauth_qa(self, url: str) -> str:
        """Open an authorized registration page in the local Chromium session."""
        target = self._validate_oauth_target_url(url)
        with self._attached_browser() as (_, context, _):
            page = context.new_page()
            page.goto(target, wait_until="domcontentloaded", timeout=30_000)
        return "Halaman registrasi dibuka di Chromium. Pilih akun Google yang valid secara manual."

    def start_google_oauth_flow(self, url: str, google_button_selector: str) -> str:
        """Navigate to an authorized registration page and click its Google button.

        Google authentication and consent are deliberately left to the user.
        """
        target = self._validate_oauth_target_url(url)
        selector = google_button_selector.strip()
        if not selector or len(selector) > 500:
            raise MailboxError("Selector tombol Google tidak valid.")
        with self._attached_browser() as (_, context, _):
            page = context.new_page()
            page.goto(target, wait_until="domcontentloaded", timeout=30_000)
            button = page.locator(selector).first
            button.wait_for(state="visible", timeout=10_000)
            button.click(timeout=10_000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:
                # Popup-based Google Identity Services may not navigate this page.
                pass
        return (
            "Tombol Google berhasil diklik. Selesaikan pemilihan akun, login, "
            "dan consent Google secara manual pada Chromium."
        )

    def close(self) -> dict[str, str]:
        """Attempt server-side cPanel logout, clear cookies, then close Chromium."""
        logout_confirmed = False
        try:
            with self._attached_browser() as (browser, context, pages):
                page, _ = self._find_authenticated_page(pages)
                if page is None:
                    page = next((p for p in reversed(pages) if self._is_cpanel_page(p)), None)
                if page is not None:
                    origin = page.evaluate("() => location.origin")
                    path = page.evaluate("() => location.pathname")
                    import re

                    match = re.match(r"^(/cpsess[^/]+)", path)
                    if match:
                        logout_target = page.evaluate(
                            """() => {
                              const link = [...document.querySelectorAll('a[href]')].find(a =>
                                /logout/i.test(a.href) || /log\\s*out/i.test(a.innerText || '')
                              );
                              return link ? link.href : null;
                            }"""
                        )
                        if not logout_target:
                            logout_target = f"{origin}{match.group(1)}/logout/?locale=en"
                        page.goto(logout_target, wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_timeout(500)
                        body_text = page.locator("body").inner_text(timeout=3000).lower()
                        logout_confirmed = "login to cpanel" in body_text or "log in to cpanel" in body_text
                context.clear_cookies()
                browser.close()
        except Exception:
            logout_confirmed = False
        return {
            "browser_closed": "true",
            "server_logout_confirmed": "true" if logout_confirmed else "false",
            "message": (
                "Logout server cPanel terverifikasi; cookie lokal dihapus dan Chromium ditutup."
                if logout_confirmed
                else "Cookie lokal dihapus dan Chromium ditutup, tetapi logout server tidak dapat diverifikasi. Periksa status sesi sebelum digunakan kembali."
            ),
        }
=======
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

    def session_status(self) -> dict[str, Any]:
        try:
            page = self._ensure_attached()
            origin = page.evaluate("() => location.origin")
            if not origin.startswith("https://") or ":2083" not in origin:
                return {"connected": False, "message": "Buka halaman cPanel port 2083."}
            probe = page.evaluate(
                """async (domain) => {
                  const match = location.pathname.match(/^(\\/cpsess[^/]+)/);
                  if (!match) return {ok: false, reason: 'cPanel session prefix not found', path: location.pathname};
                  const endpoint = match[1] + '/execute/Email/list_pops?domain=' + encodeURIComponent(domain);
                  const response = await fetch(endpoint, {credentials: 'same-origin'});
                  if (!response.ok) return {ok: false, status: response.status};
                  const payload = await response.json();
                  return {ok: payload?.result?.status === 1};
                }""",
                self.domain,
            )
            return {
                "connected": bool(probe.get("ok")),
                "message": "Sesi cPanel aktif." if probe.get("ok") else "Login cPanel diperlukan.",
            }
        except Exception as exc:
            return {"connected": False, "message": f"Sesi browser tidak tersedia: {type(exc).__name__}"}

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
              const match = location.pathname.match(/^(\\/cpsess[^/]+)/);
              if (!match) throw new Error('cPanel session prefix not found in URL');
              const endpoint = match[1] + '/execute/Email/list_pops?domain=' + encodeURIComponent(domain);
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
                  const match = location.pathname.match(/^(\\/cpsess[^/]+)/);
                  if (!match) throw new Error('cPanel session prefix not found in URL');
                  const response = await fetch(match[1] + '/execute/Email/add_pop?' + params.toString(), {
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
        """Close the persistent Chromium browser and release this Playwright client."""
        if self._browser is not None and self._browser.is_connected():
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
>>>>>>> 2e84aec661483ce823d55cc430ea697861497d00
