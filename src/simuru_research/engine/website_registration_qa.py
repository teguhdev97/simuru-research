from __future__ import annotations

import os
from urllib.parse import urlparse


class WebsiteRegistrationQAError(ValueError):
    """An invalid or unavailable website registration QA target."""


def validate_registration_target(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise WebsiteRegistrationQAError("Enter a complete HTTP(S) website URL.")
    if parsed.username or parsed.password:
        raise WebsiteRegistrationQAError("URL credentials are not allowed.")
    allowlist = {
        host.strip().lower()
        for host in os.getenv("WEBSITE_QA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
        if host.strip()
    }
    hostname = parsed.hostname.lower()
    if hostname not in allowlist:
        raise WebsiteRegistrationQAError(
            "Target is not allowlisted. Add its exact hostname to WEBSITE_QA_ALLOWED_HOSTS."
        )
    if parsed.scheme != "https" and hostname not in {"localhost", "127.0.0.1"}:
        raise WebsiteRegistrationQAError("Remote QA sites must use HTTPS.")
    return url.strip()


def inspect_registration_form(url: str) -> dict[str, object]:
    """Read visible registration controls only; never submit the form."""
    target = validate_registration_target(url)
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise WebsiteRegistrationQAError(
            "Playwright is unavailable. Install project dependencies first."
        ) from exc

    script = r"""() => {
      const visible = el => {
        const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
      };
      const selector = el => el.id ? '#' + CSS.escape(el.id) :
        (el.name ? el.tagName.toLowerCase() + '[name="' + CSS.escape(el.name) + '"]' : '');
      const inputs = [...document.querySelectorAll('input,textarea,select')]
        .filter(visible)
        .map(el => ({
          type: (el.type || el.tagName).toLowerCase(),
          name: el.name || '',
          label: (el.labels && [...el.labels].map(x => x.innerText.trim()).join(' ')) ||
            el.getAttribute('aria-label') || el.placeholder || el.name || '',
          selector: selector(el),
          required: Boolean(el.required)
        }));
      const buttons = [...document.querySelectorAll('button,input[type=submit],[role=button]')]
        .filter(visible).map(el => ({
          text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim(),
          selector: selector(el)
        }));
      return {
        title: document.title, url: location.href,
        formFound: [...document.querySelectorAll('form')].some(visible),
        inputs, buttons,
        challengeDetected: Boolean(document.querySelector(
          'iframe[src*="captcha" i],iframe[title*="captcha" i],' +
          '[class*="captcha" i],[id*="captcha" i]'
        ))
      };
    }"""
    playwright = sync_playwright().start()
    browser = None
    try:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(target, wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(700)
        data = page.evaluate(script)
        inputs = data.get("inputs", [])
        if not isinstance(inputs, list):
            inputs = []

        def find(predicate):
            return next((item for item in inputs if predicate(item)), {})

        password = find(lambda item: item["type"] == "password")
        confirm = next(
            (item for item in inputs if item["type"] == "password" and item != password),
            {},
        )
        data["suggested_selectors"] = {
            "name": find(
                lambda item: any(
                    word in item["label"].lower() for word in ("name", "nama")
                )
            ).get("selector", ""),
            "email": find(
                lambda item: item["type"] == "email"
                or "email" in item["label"].lower()
            ).get("selector", ""),
            "password": password.get("selector", ""),
            "confirm_password": confirm.get("selector", ""),
        }
        return data
    except PlaywrightError as exc:
        raise WebsiteRegistrationQAError(f"Inspection failed: {type(exc).__name__}") from exc
    finally:
        if browser:
            browser.close()
        playwright.stop()
