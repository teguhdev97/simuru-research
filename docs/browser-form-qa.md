# Browser Form QA (Selenium)

This optional module supports form inspection and sequential, manual browser QA on
a local application or a staging/QA environment that you own or are explicitly
authorized to test.

## Scope and safeguards

- Uses standard Selenium Chrome WebDriver, not an anti-detection/stealth driver.
- Defaults to localhost and 127.0.0.1.
- Additional QA hosts must be explicitly listed in BROWSER_QA_ALLOWED_HOSTS.
- Form inspection only checks whether common username, email, password, and submit
  controls exist; it does not submit forms or create accounts.
- Sequential sessions open one temporary Chrome profile at a time. Each profile
  has independent cookies and web storage, and is deleted when that session closes.
- A new Chrome profile is not a new physical device and does not spoof device
  fingerprints or bypass registration limits.
- The session runner leaves all page interaction to the operator. It does not fill
  or submit registration forms, create accounts, solve CAPTCHAs, read OTPs, rotate
  proxies, or evade access controls.
- CAPTCHA detection is heuristic and advisory. When a likely challenge is found,
  it is reported and the browser remains open for manual inspection/completion.
  The runner also pauses for operator confirmation on every session.
- Prefer a staging/QA tenant with documented test identities and a test email
  provider (for example, Mailpit). Avoid bulk account creation on production.

## Install

```powershell
uv sync --extra browser-qa
```

Install Google Chrome separately if it is not already installed. Selenium Manager
will manage the compatible ChromeDriver when the browser check is first run.

## Inspect form controls

```powershell
$env:BROWSER_QA_ALLOWED_HOSTS = "localhost,127.0.0.1"
uv run simuru-browser-qa --url http://127.0.0.1:8000/register
```

For an owned QA/staging environment, explicitly add its hostname:

```powershell
$env:BROWSER_QA_ALLOWED_HOSTS = "localhost,127.0.0.1,staging.example.org"
uv run simuru-browser-qa --url https://staging.example.org/register --mode inspect
```

## Open sequential temporary Chrome sessions

The following opens one Chrome window at a time. Perform authorized manual QA in
the window, complete any challenge yourself if appropriate, then return to the
terminal and press Enter to close the temporary profile and open the next session.
Type q then Enter to stop early.

```powershell
$env:BROWSER_QA_ALLOWED_HOSTS = "localhost,127.0.0.1,staging.example.org"
uv run simuru-browser-qa --url https://staging.example.org/register --mode sessions --sessions 8
```

The command prints a JSON summary with each session's status, page title, CAPTCHA
hint, and profile-cleanup result. CAPTCHA detection cannot guarantee that every
challenge is recognized; inspect the browser page yourself.

Do not add third-party identity-provider hosts to the allowlist. Keep test data
synthetic and use the site's documented test accounts and verification mechanisms.