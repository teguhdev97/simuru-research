from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from simuru_research.providers.mailbox import MailboxError
from simuru_research.security.mailbox_vault import MailboxCredentialVault


class CpanelBrowserSession:
    """Manage the persistent local Chromium session used for cPanel access."""

    def __init__(
        self,
        *,
        cpanel_url: str,
        domain: str = "teguhharits.com",
        prefix: str = "qa",
        quota_mb: int = 50,
        profile_dir: str = "data/cpanel-browser-profile",
        debug_port: int = 9222,
        mailbox_password: str | None = None,
        credential_vault: MailboxCredentialVault | None = None,
    ) -> None:
        self.cpanel_url = cpanel_url.rstrip("/")
        self.domain = domain.lower()
        self.prefix = prefix
        self.quota_mb = quota_mb
        self.profile_dir = Path(profile_dir)
        self.debug_port = debug_port
        self.mailbox_password = mailbox_password or os.getenv(
            "QA_MAILBOX_MASTER_PASSWORD", ""
        ).strip()
        self.credential_vault = credential_vault or MailboxCredentialVault()

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
                pageUrl: location.origin + location.pathname.replace(
                  /^\\/cpsess[^/]+/,
                  '/cpsess[redacted]'
                ),
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
              result.endpointPath = endpoint.pathname.replace(
                /^\\/cpsess[^/]+/,
                '/cpsess[redacted]'
              );
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
                result.responseUrl = responseUrl.origin + responseUrl.pathname.replace(
                  /^\\/cpsess[^/]+/,
                  '/cpsess[redacted]'
                );
                result.redirected = response.redirected;

                const raw = await response.text();
                let payload;
                try {
                  payload = JSON.parse(raw);
                } catch (_) {
                  result.reason = (
                    'UAPI tidak mengembalikan JSON; kemungkinan dialihkan ke halaman login.'
                  );

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
                      || 'HTTP berhasil, tetapi envelope JSON tidak berisi status sukses UAPI. '
                      + 'Lihat topLevelKeys dan resultKeys.');
                }
                return result;
              } catch (error) {
                result.reason = 'Fetch UAPI gagal: ' + String(error)
                  .replace(/cpsess[^/\\s"'<>]+/gi, 'cpsess[redacted]');
                return result;
              }
            }"""
        )

    def _find_authenticated_page(self, pages: list[Page]) -> tuple[Page | None, list[dict[str, Any]]]:  # noqa: E501
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
                    message = "Browser aktif, tetapi tab cPanel tidak ditemukan. Klik Connect cPanel."  # noqa: E501
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
    def _validate_oauth_target_url(url: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise MailboxError("Masukkan URL website HTTP(S) yang valid.")
        if parsed.username or parsed.password:
            raise MailboxError("URL target must not contain credentials.")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise MailboxError("Website remote harus menggunakan HTTPS.")
        return url.strip()

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
                        logout_confirmed = "login to cpanel" in body_text or "log in to cpanel" in body_text  # noqa: E501
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
                else "Cookie lokal dihapus dan Chromium ditutup, tetapi logout server tidak dapat diverifikasi. Periksa status sesi sebelum digunakan kembali."  # noqa: E501
            ),
        }
