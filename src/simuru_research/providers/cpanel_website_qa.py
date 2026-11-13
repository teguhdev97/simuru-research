from __future__ import annotations

import time

from simuru_research.providers.cpanel_browser_session import CpanelBrowserSession
from simuru_research.providers.mailbox import MailboxError


class CpanelWebsiteQA(CpanelBrowserSession):
    """Run explicitly authorized website registration QA in an isolated context."""

    def run_email_registration_batch(
        self,
        url: str,
        selectors: dict[str, str],
        identities: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Submit five owned-site QA registrations using configured email form selectors."""
        target = self._validate_oauth_target_url(url)
        if len(identities) != 5:
            raise MailboxError("Email fallback requires exactly five QA identities.")

        required = ("email", "password", "submit")
        normalized_selectors = {
            key: str(selectors.get(key, "")).strip()
            for key in ("name", "email", "password", "confirm_password", "submit")
        }
        missing = [key for key in required if not normalized_selectors[key]]
        if missing:
            raise MailboxError(
                "Email fallback selectors are incomplete: " + ", ".join(missing)
            )

        normalized_identities: list[dict[str, str]] = []
        for identity in identities:
            email = str(identity.get("email", "")).strip().lower()
            password = str(identity.get("password", ""))
            if (
                not email.endswith("@" + self.domain)
                or not email.split("@", 1)[0].startswith(self.prefix + "-")
            ):
                raise MailboxError(
                    "Fallback accepts only generated QA mailboxes on the configured domain."
                )
            if len(password) < 12:
                raise MailboxError(
                    "Each generated website QA password must be at least 12 characters."
                )
            normalized_identities.append(
                {
                    "email": email,
                    "password": password,
                    "name": str(identity.get("name", "")).strip(),
                }
            )
        addresses = [item["email"] for item in normalized_identities]
        if len(set(addresses)) != 5:
            raise MailboxError("The five QA email addresses must be unique.")

        results: list[dict[str, str]] = []
        with self._attached_browser() as (browser, _, _):
            # Keep website cookies isolated from the authenticated cPanel profile.
            site_context = browser.new_context()
            page = site_context.new_page()
            for index, identity in enumerate(normalized_identities, start=1):
                result = {
                    "email": identity["email"],
                    "password": identity["password"],
                    "status": "failed",
                    "message": "",
                    "page_url": "",
                }
                try:
                    page.goto(target, wait_until="domcontentloaded", timeout=30_000)
                    values = {
                        "name": identity["name"] or f"SIMURU QA User {index:02d}",
                        "email": identity["email"],
                        "password": identity["password"],
                        "confirm_password": identity["password"],
                    }
                    for field in ("name", "email", "password", "confirm_password"):
                        selector = normalized_selectors[field]
                        if not selector:
                            continue
                        locator = page.locator(selector)
                        count = locator.count()
                        if count != 1:
                            raise MailboxError(
                                f"Selector '{field}' matched {count} elements; "
                                "expected exactly one."
                            )
                        locator.wait_for(state="visible", timeout=8_000)
                        locator.fill(values[field], timeout=8_000)

                    submit = page.locator(normalized_selectors["submit"])
                    submit_count = submit.count()
                    if submit_count != 1:
                        raise MailboxError(
                            f"Submit selector matched {submit_count} elements; "
                            "expected exactly one."
                        )
                    submit.wait_for(state="visible", timeout=8_000)
                    submit.click(timeout=10_000)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=4_000)
                    except Exception:
                        # SPA forms may submit without a full-page navigation.
                        pass
                    page.wait_for_timeout(900)
                    message = ""
                    alert = page.locator("[role='alert']")
                    if alert.count():
                        try:
                            message = alert.first.inner_text(timeout=1_000).strip()[:300]
                        except Exception:
                            message = ""
                    result.update(
                        {
                            "status": "submitted",
                            "message": (
                                message or "Submit action completed; verify the app response."
                            ),
                            "page_url": str(page.url),
                        }
                    )
                except Exception as exc:
                    result["message"] = (
                        str(exc).strip().replace("\\n", " ")[:300]
                        or type(exc).__name__
                    )
                    result["page_url"] = str(getattr(page, "url", ""))
                results.append(result)
                time.sleep(0.35)
        return results

    def open_website_for_oauth_qa(self, url: str) -> str:
        """Open an authorized registration page in the local Chromium session."""
        target = self._validate_oauth_target_url(url)
        with self._attached_browser() as (browser, _, _):
            site_context = browser.new_context()
            page = site_context.new_page()
            page.goto(target, wait_until="domcontentloaded", timeout=30_000)
        return "Halaman registrasi dibuka di context terisolasi. Lanjutkan secara manual."

    def start_google_oauth_flow(self, url: str, google_button_selector: str) -> str:
        """Navigate to an authorized registration page and click its Google button.

        Google authentication and consent are deliberately left to the user.
        """
        target = self._validate_oauth_target_url(url)
        selector = google_button_selector.strip()
        if not selector or len(selector) > 500:
            raise MailboxError("Selector tombol Google tidak valid.")
        with self._attached_browser() as (browser, _, _):
            site_context = browser.new_context()
            page = site_context.new_page()
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
