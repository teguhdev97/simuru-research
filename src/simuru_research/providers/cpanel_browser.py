from __future__ import annotations

import secrets
import string
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from simuru_research.providers.mailbox import MailboxError


class CpanelBrowserMailboxManager:
    """Manage a local Chromium session and call cPanel UAPI as the signed-in user.

    Playwright clients are intentionally short-lived: Streamlit reruns UI code and
    may execute fragments on different threads. Chromium itself remains an
    independent process with a persistent local profile and CDP endpoint.
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
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            except OSError as exc:
                raise MailboxError(f"Gagal membuka Chromium: {type(exc).__name__}") from exc

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
                const responseUrl = new URL(response.url);
                result.responseUrl = responseUrl.origin + responseUrl.pathname.replace(/^\\/cpsess[^/]+/, '/cpsess[redacted]');
                result.redirected = response.redirected;

                const raw = await response.text();
                let payload;
                try {
                  payload = JSON.parse(raw);
                } catch (_) {
                  result.reason = 'UAPI tidak mengembalikan JSON; kemungkinan dialihkan ke halaman login.';
                  result.responsePreview = raw.slice(0, 240).replace(/\\s+/g, ' ')
                    .replace(/cpsess[^/\\s"'<>]+/gi, 'cpsess[redacted]');
                  return result;
                }

                const apiStatus = payload?.result?.status;
                const safe = (value) => value == null ? null
                  : JSON.stringify(value).replace(/cpsess[^/\\s"'<>]+/gi, 'cpsess[redacted]');
                result.apiStatus = apiStatus ?? null;
                result.apiErrors = safe(payload?.result?.errors);
                result.apiMessages = safe(payload?.result?.messages);
                result.resultKeys = payload?.result && typeof payload.result === 'object'
                  ? Object.keys(payload.result) : [];
                result.dataType = Array.isArray(payload?.result?.data)
                  ? 'array' : typeof payload?.result?.data;
                result.ok = response.ok && String(apiStatus) === '1' && !response.redirected;
                if (!result.ok) {
                  result.reason = response.redirected
                    ? 'UAPI dialihkan ke halaman lain; sesi mungkin kedaluwarsa.'
                    : (result.apiErrors || result.apiMessages
                      || safe(payload?.result) || 'UAPI mengembalikan status selain 1.');
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
                    "reason": f"{type(exc).__name__}: {exc}",
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
    def _uapi_succeeded(payload: dict[str, Any]) -> bool:
        return str(payload.get("result", {}).get("status", "")) == "1"

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
        if not self._uapi_succeeded(payload):
            result = payload.get("result", {})
            details = result.get("errors") or result.get("messages") or "Tidak ada detail UAPI."
            raise MailboxError(f"Email::list_pops gagal: {details}")
        data = payload.get("result", {}).get("data") or []
        if not isinstance(data, list):
            raise MailboxError("Format data Email::list_pops tidak dikenali.")
        return data

    def create_five(self) -> list[dict[str, str]]:
        """Create exactly five unique mailboxes, preserving partial results safely."""
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
            alphabet = string.ascii_letters + string.digits + "!@#$%_-"
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

                password = "".join(secrets.choice(alphabet) for _ in range(24)) + "aA9!"
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
                            match[0] + '/execute/Email/add_pop?' + params.toString(),
                            {method: 'GET', credentials: 'same-origin', cache: 'no-store'}
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
