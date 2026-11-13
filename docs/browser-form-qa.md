# Browser Form QA (Selenium)

This optional module inspects registration forms on a local application or a staging
environment that you own or are explicitly authorized to test.

## Scope and safeguards

- Uses standard Selenium Chrome WebDriver, not an anti-detection/stealth driver.
- Defaults to `localhost` and `127.0.0.1`.
- Additional staging hosts must be explicitly listed in `BROWSER_QA_ALLOWED_HOSTS`.
- The current implementation only checks whether common username, email, password,
  and submit controls exist. It does not submit a form or create an account.
- CAPTCHA and OTP challenges must remain under the control of the site owner and
  be completed manually in an authorized test environment.
- No proxy rotation, CAPTCHA-solving service, OTP interception, or account-creation
  flow is implemented.

## Install

The browser QA extra is optional:

```powershell
uv sync --extra browser-qa
```

Install Google Chrome separately if it is not already installed. Selenium Manager
will manage the compatible ChromeDriver when the browser check is first run.

## Run a form inspection

Start your local application, then run:

```powershell
$env:BROWSER_QA_ALLOWED_HOSTS = "localhost,127.0.0.1"
uv run simuru-browser-qa --url http://127.0.0.1:8000/register
```

For an owned staging environment, explicitly add its hostname:

```powershell
$env:BROWSER_QA_ALLOWED_HOSTS = "localhost,127.0.0.1,staging.example.org"
uv run simuru-browser-qa --url https://staging.example.org/register --headless
```

Do not add third-party identity-provider hosts to the allowlist. Keep test data
synthetic and use the staging provider's documented test accounts and verification
mechanisms.
