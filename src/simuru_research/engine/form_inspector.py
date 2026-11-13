from __future__ import annotations

from urllib.parse import urlparse


class FormInspectionError(ValueError):
    """Raised when a website form cannot be inspected safely."""


def inspect_form(url: str, *, timeout_ms: int = 20000) -> dict[str, object]:
    """Read visible form controls and suggest unique CSS selectors; never submit."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise FormInspectionError("Masukkan URL lengkap dengan http:// atau https://.")
    if parsed.username or parsed.password:
        raise FormInspectionError("URL tidak boleh berisi username atau password.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise FormInspectionError("Website remote harus menggunakan HTTPS.")

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise FormInspectionError(
            "Playwright belum terpasang. Jalankan: uv sync"
        ) from exc

    script = r"""
    () => {
      const visible = (el) => {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden'
          && rect.width > 0 && rect.height > 0;
      };
      const uniqueSelector = (el) => {
        if (el.id) {
          const byId = '#' + CSS.escape(el.id);
          if (document.querySelectorAll(byId).length === 1) return byId;
        }
        for (const attr of ['name', 'autocomplete', 'type', 'placeholder']) {
          const value = el.getAttribute(attr);
          if (!value) continue;
          const selector = el.tagName.toLowerCase() + '[' + attr + '="' +
            CSS.escape(value).replaceAll('"', '\\"') + '"]';
          if (document.querySelectorAll(selector).length === 1) return selector;
        }
        const parts = [];
        let node = el;
        while (node && node.nodeType === 1 && node !== document.body) {
          let part = node.tagName.toLowerCase();
          if (node.id) {
            part += '#' + CSS.escape(node.id);
            parts.unshift(part);
            break;
          }
          const siblings = node.parentElement
            ? [...node.parentElement.children].filter(x => x.tagName === node.tagName)
            : [];
          if (siblings.length > 1) part += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
          parts.unshift(part);
          node = node.parentElement;
          const candidate = parts.join(' > ');
          if (document.querySelectorAll(candidate).length === 1) return candidate;
        }
        return parts.join(' > ');
      };
      const labelFor = (el) => {
        const labels = el.labels ? [...el.labels].map(x => x.innerText.trim()).filter(Boolean) : [];
        const aria = el.getAttribute('aria-label');
        const placeholder = el.getAttribute('placeholder');
        return labels[0] || aria || placeholder || el.getAttribute('name') || el.id || '';
      };
      const inputs = [...document.querySelectorAll('input, textarea, select')]
        .filter(el => visible(el) && ![
          'hidden', 'submit', 'button', 'reset', 'checkbox', 'radio', 'file'
        ].includes((el.type || '').toLowerCase()))
        .map(el => ({
          tag: el.tagName.toLowerCase(),
          type: (el.type || el.tagName.toLowerCase()).toLowerCase(),
          label: labelFor(el),
          name: el.getAttribute('name') || '',
          id: el.id || '',
          placeholder: el.getAttribute('placeholder') || '',
          autocomplete: el.getAttribute('autocomplete') || '',
          selector: uniqueSelector(el)
        }));
      const buttons = [...document.querySelectorAll('button, input[type=submit], [role=button], a')]
        .filter(visible)
        .map(el => ({
          text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 140),
          selector: uniqueSelector(el),
          type: el.getAttribute('type') || (el.tagName.toLowerCase() === 'button' ? 'submit' : ''),
          href: el.getAttribute('href') || ''
        })).filter(x => x.text || x.href);
      return {title: document.title, url: location.href, inputs, buttons};
    }
    """

    playwright = sync_playwright().start()
    browser = None
    try:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_navigation_timeout(timeout_ms)
        page.goto(url.strip(), wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        data = page.evaluate(script)
    except PlaywrightError as exc:
        raise FormInspectionError(
            f"Gagal memeriksa halaman: {type(exc).__name__}. "
            "Pastikan URL dapat dibuka dan tidak memerlukan login terlebih dahulu."
        ) from exc
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()

    inputs = data.get("inputs", [])
    buttons = data.get("buttons", [])
    if not isinstance(inputs, list) or not isinstance(buttons, list):
        raise FormInspectionError("Struktur halaman tidak dapat dibaca.")
    def first_match(predicate):
        return next((item for item in inputs if predicate(item)), {})

    def searchable_text(item: dict[str, str], *fields: str) -> str:
        return " ".join(item.get(field, "") for field in fields).lower()

    name = first_match(
        lambda item: item["type"] == "text"
        and any(
            keyword in searchable_text(item, "label", "name", "autocomplete")
            for keyword in ("name", "nama", "full")
        )
    )
    email = first_match(
        lambda item: item["type"] == "email"
        or "email" in searchable_text(item, "label", "name", "autocomplete")
    )
    password_fields = [item for item in inputs if item["type"] == "password"]
    password = password_fields[0] if password_fields else {}
    confirm = next(
        (
            item
            for item in password_fields[1:]
            if any(
                keyword in searchable_text(item, "label", "name")
                for keyword in ("confirm", "confirmation", "ulang", "konfirmasi")
            )
        ),
        {},
    )
    if not confirm and len(password_fields) > 1:
        confirm = password_fields[1]
    submit = next((item for item in buttons if item["type"] == "submit"), {})
    google = [
        item
        for item in buttons
        if any(
            keyword in item["text"].lower()
            for keyword in ("google", "continue with", "sign in with")
        )
    ]
    selectors = {
        "name": name.get("selector", ""),
        "email": email.get("selector", ""),
        "password": password.get("selector", ""),
        "confirm_password": confirm.get("selector", ""),
        "submit": submit.get("selector", ""),
    }
    return {
        "title": str(data.get("title", "")),
        "url": str(data.get("url", url)),
        "inputs": inputs,
        "buttons": buttons,
        "selectors": selectors,
        "google_buttons": google,
    }
