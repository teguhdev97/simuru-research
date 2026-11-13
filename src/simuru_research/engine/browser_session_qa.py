from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from simuru_research.engine.browser_form_qa import _validate_target_url


@dataclass(frozen=True, slots=True)
class SessionResult:
    session_number: int
    status: str
    title: str
    captcha_suspected: bool
    profile_cleaned: bool


_CAPTCHA_SELECTORS = (
    'iframe[src*="captcha" i]',
    'iframe[title*="captcha" i]',
    '[class*="captcha" i]',
    '[id*="captcha" i]',
    'textarea[name*="captcha" i]',
)


def _captcha_may_be_present(driver: object) -> bool:
    """Return a conservative hint only; never solve or interact with a challenge."""
    for selector in _CAPTCHA_SELECTORS:
        try:
            if driver.find_elements("css selector", selector):
                return True
        except Exception:
            # Detection is advisory; the user can always inspect the open browser.
            continue
    return False


def run_sequential_browser_sessions(
    url: str,
    *,
    sessions: int = 1,
    timeout_seconds: int = 20,
) -> list[SessionResult]:
    """Open isolated temporary Chrome profiles one at a time for manual QA.

    The operator performs all website interactions manually. This runner does not
    fill or submit registration forms, create accounts, solve CAPTCHAs, read OTPs,
    or modify browser fingerprints.
    """
    target = _validate_target_url(url)
    if not 1 <= sessions <= 20:
        raise ValueError("sessions must be between 1 and 20.")
    if not 1 <= timeout_seconds <= 120:
        raise ValueError("timeout_seconds must be between 1 and 120.")

    try:
        from selenium import webdriver
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.chrome.options import Options
    except ImportError as exc:
        raise RuntimeError(
            "Browser QA dependencies are missing. Install them with: uv sync --extra browser-qa"
        ) from exc

    results: list[SessionResult] = []
    for number in range(1, sessions + 1):
        profile_dir = Path(tempfile.mkdtemp(prefix=f"simuru-qa-session-{number}-"))
        driver = None
        title = ""
        suspected = False
        status = "completed"
        try:
            options = Options()
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument("--window-size=1440,1000")
            options.add_argument("--no-first-run")
            options.add_argument("--disable-notifications")
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(timeout_seconds)
            driver.get(target)
            title = driver.title
            suspected = _captcha_may_be_present(driver)
            print(f"\n[Session {number}/{sessions}] {target}")
            print(f"Page title: {title or '(no title)'}")
            if suspected:
                print(
                    "Possible CAPTCHA/challenge detected. Complete it manually in Chrome; "
                    "this tool will not solve or bypass it."
                )
            print(
                "Perform the authorized QA steps manually. Press Enter to close this "
                "session and open the next one, or type q then Enter to stop."
            )
            try:
                command = input("> ").strip().lower()
            except EOFError:
                command = "q"
            if command == "q":
                status = "stopped"
        except TimeoutException:
            status = "page_timeout"
            print(f"[Session {number}] Page load timed out; inspect Chrome before continuing.")
            try:
                input("Press Enter to close this session...")
            except EOFError:
                pass
        except WebDriverException as exc:
            status = f"webdriver_error:{type(exc).__name__}"
        finally:
            if driver is not None:
                driver.quit()
            shutil.rmtree(profile_dir, ignore_errors=True)

        results.append(
            SessionResult(
                session_number=number,
                status=status,
                title=title,
                captcha_suspected=suspected,
                profile_cleaned=not profile_dir.exists(),
            )
        )
        if status == "stopped":
            break
    return results
