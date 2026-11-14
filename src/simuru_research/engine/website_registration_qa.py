from __future__ import annotations

from urllib.parse import urlparse


class WebsiteRegistrationQAError(ValueError):
    """Website QA error with structured diagnostics."""


def validate_registration_target(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise WebsiteRegistrationQAError("Masukkan URL website lengkap dengan HTTP(S).")
    if parsed.username or parsed.password:
        raise WebsiteRegistrationQAError("URL tidak boleh berisi username atau password.")
    allowed_hosts = {
        host.strip().lower()
        for host in __import__("os").getenv(
            "WEBSITE_QA_ALLOWED_HOSTS", "localhost,127.0.0.1"
        ).split(",")
        if host.strip()
    }
    hostname = (parsed.hostname or "").lower()
    if hostname not in allowed_hosts:
        raise WebsiteRegistrationQAError(
            "Target tidak ada di allowlist. Gunakan localhost atau domain staging "
            "yang Anda miliki dan masukkan ke WEBSITE_QA_ALLOWED_HOSTS."
        )
    if parsed.scheme != "https" and hostname not in {"localhost", "127.0.0.1"}:
        raise WebsiteRegistrationQAError("Website staging remote harus menggunakan HTTPS.")
    return url.strip()


def inspect_registration_form(url: str) -> dict[str, object]:
    """Inspect the allowlisted page without clicking submit or completing challenges."""
    target = validate_registration_target(url)
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as exc:
        raise WebsiteRegistrationQAError(
            "Playwright belum tersedia. Jalankan uv sync lalu playwright install chromium."
        ) from exc

    script = r"""
    () => {
      const visible = el => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0
          && style.display !== 'none' && style.visibility !== 'hidden';
      };
      const uniqueSelector = el => {
        if (el.id) return '#' + CSS.escape(el.id);
        const attrs = ['name','type','autocomplete','placeholder'];
        for (const attr of attrs) {
          const value = el.getAttribute(attr);
          if (value) {
            const selector = el.tagName.toLowerCase() + '[' + attr + '="' +
              CSS.escape(value).replaceAll('"','\\"') + '"]';
            if (document.querySelectorAll(selector).length === 1) return selector;
          }
        }
        return '';
      };
      const inputs = [...document.querySelectorAll('input,textarea,select')]
        .filter(visible)
        .map(el => ({
          type: (el.type || el.tagName).toLowerCase(),
          name: el.name || '',
          label: (el.labels && [...el.labels].map(x=>x.innerText.trim()).join(' ')) ||
            el.getAttribute('aria-label') || el.placeholder || el.name || '',
          selector: uniqueSelector(el),
          required: Boolean(el.required)
        }));
      const buttons = [...document.querySelectorAll('button,input[type=submit],[role=button]')]
        .filter(visible)
        .map(el => ({
          text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim(),
          type: el.getAttribute('type') || '',
          selector: uniqueSelector(el)
        }));
      const form = [...document.querySelectorAll('form')].find(visible);
      return {
        title: document.title,
        url: location.href,
        formFound: Boolean(form),
        formCount: [...document.querySelectorAll('form')].filter(visible).length,
        inputs,
        buttons,
        challengeDetected: Boolean(document.querySelector(
          'iframe[src*="captcha" i],iframe[title*="captcha" i],' +
          '[class*="captcha" i],[id*="captcha" i],input[type="checkbox"]'
        ))
      };
    }
    """
    playwright = sync_playwright().start()
    browser = None
    try:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(target, wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(900)
        data = page.evaluate(script)
        inputs = data.get("inputs", [])
        if not isinstance(inputs, list):
            inputs = []
        def find(predicate):
            return next((item for item in inputs if predicate(item)), {})
        email = find(lambda item: item["type"] == "email" or "email" in item["label"].lower())
        password = find(lambda item: item["type"] == "password")
        confirm = next(
            (item for item in inputs if item["type"] == "password" and item != password),
            {},
        )
        name = find(
            lambda item: item["type"] in {"text", "input"}
            and any(word in item["label"].lower() for word in ("nama","name","full"))
        )
        result = dict(data)
        result["suggested_selectors"] = {
            "name": name.get("selector", ""),
            "email": email.get("selector", ""),
            "password": password.get("selector", ""),
            "confirm_password": confirm.get("selector", ""),
        }
        return result
    except PlaywrightError as exc:
        raise WebsiteRegistrationQAError(
            f"Inspeksi gagal: {type(exc).__name__}: {exc}"
        ) from exc
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()
