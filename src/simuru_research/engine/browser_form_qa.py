from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


@dataclass(frozen=True, slots=True)
class FormQASummary:
    target_url: str
    title: str
    username_field_found: bool
    email_field_found: bool
    password_field_found: bool
    submit_button_found: bool


def _validate_target_url(url: str) -> str:
    parsed = urlparse(url)
    allowed_hosts = {
        item.strip().lower()
        for item in os.getenv("BROWSER_QA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
        if item.strip()
    }
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or hostname not in allowed_hosts:
        raise ValueError(
            "Browser QA target is not allowlisted. Use localhost/127.0.0.1 "
            "or add your owned staging hostname to BROWSER_QA_ALLOWED_HOSTS."
        )
    if parsed.username or parsed.password:
        raise ValueError("Credentials must not be embedded in the target URL.")
    return url


def inspect_registration_form(
    url: str,
    *,
    timeout_seconds: int = 10,
    headless: bool = False,
) -> FormQASummary:
    """Inspect a registration form on an explicitly allowlisted local/staging site.

    This routine only inspects the page. It does not submit forms, create accounts,
    solve CAPTCHAs, read OTPs, or attempt to evade access controls.
    """
    if not 1 <= timeout_seconds <= 60:
        raise ValueError("timeout_seconds must be between 1 and 60.")
    target = _validate_target_url(url)

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(timeout_seconds)
        driver.get(target)
        wait = WebDriverWait(driver, timeout_seconds)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        def exists(css: str) -> bool:
            return bool(driver.find_elements(By.CSS_SELECTOR, css))

        return FormQASummary(
            target_url=target,
            title=driver.title,
            username_field_found=exists(
                'input[name="username"], input#username, input[autocomplete="username"]'
            ),
            email_field_found=exists(
                'input[type="email"], input[name="email"], input#email'
            ),
            password_field_found=exists(
                'input[type="password"], input[name="password"]'
            ),
            submit_button_found=exists(
                'button[type="submit"], input[type="submit"]'
            ),
        )
    except TimeoutException as exc:
        raise RuntimeError("Timed out while loading the allowlisted QA page.") from exc
    except WebDriverException as exc:
        raise RuntimeError(f"Chrome WebDriver failed: {type(exc).__name__}") from exc
    finally:
        driver.quit()
