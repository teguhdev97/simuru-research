# Simuru Research

Local Windows research workspace for SIMURU API exploration, team account metadata,
synthetic QA, and a local registration/authentication test service.

## Current release

- Version: 0.5.0
- Python: 3.12
- Runtime: local Windows machine
- Dashboard: Streamlit
- Local QA API: FastAPI + Uvicorn, loopback only
- Database: SQLite
- SIMURU API: https://simuru.com/api
- SIMURU API documentation: https://simuru.com/api-docs

## Important platform boundaries

This project does **not** create Instagram accounts, automate Instagram sign-up,
rent temporary phone numbers or email inboxes for Instagram registration, retrieve
Instagram OTPs, or bypass Instagram verification and anti-abuse controls.

SIMURU's own terms prohibit mass-creating fake accounts and evading bans. Use
SIMURU only for activities and applications you own or are authorized to test.

Meta's official Instagram APIs support eligible professional accounts (Creator and
Business), not consumer/personal Instagram accounts. A Meta app test user is not a
new Instagram account. This repository does not claim to create or connect Instagram
accounts.

## New in v0.5.0: Local Registration QA

The **Registration QA** tab now runs up to 100 end-to-end test registrations for
the team's own local application. The default batch is 40 jobs with 3 concurrent
workers.

Each job executes:

1. Register a QA user in the local SQLite database.
2. Generate a six-digit email verification code in the local test outbox.
3. Verify the email address.
4. Generate and verify a separate SMS verification code in the local test outbox.
5. Hash and verify the password using PBKDF2-HMAC-SHA256.
6. Log in and validate the resulting session token.
7. Save the job result to the existing run history and allow CSV export.

### Test-only data boundaries

- Email addresses use the reserved example.test domain.
- Phone numbers use the fictional +1-202-555-0100 through +1-202-555-0199 range.
- Passwords are randomly generated in memory and stored only as salted password hashes.
- OTPs are held temporarily in a local QA outbox and cleared when consumed.
- Access tokens are stored as SHA-256 hashes in SQLite.
- The QA API rejects non-loopback clients; run it on 127.0.0.1.
- No real email, SMS, SIMURU rental, Temp-Mail, Temp-Number, or Instagram request is made by this local QA flow.

These test users can authenticate against the **local QA API only**. They are not
Instagram accounts and cannot log in to Instagram.

## Local Registration QA API

A small FastAPI service is included to make the registration flow inspectable and
testable independently of the Streamlit dashboard.

### Start the API

Open a terminal in the repository:

~~~powershell
uv run uvicorn simuru_research.api:app --host 127.0.0.1 --port 8000
~~~

Open the interactive API documentation:

~~~text
http://127.0.0.1:8000/docs
~~~

The API supports:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Local service health |
| POST | /auth/register | Register a local QA user |
| GET | /qa/outbox/email?destination=... | Read local email test code |
| GET | /qa/outbox/sms?destination=... | Read local SMS test code |
| POST | /auth/verify | Verify email or SMS code |
| POST | /auth/login | Authenticate a verified QA user |
| GET | /auth/me | Validate the bearer session |

The test outbox is available only to loopback clients. Do not bind this API to
0.0.0.0, expose it through a tunnel, or deploy it publicly.

### Example: register and verify one local QA user (PowerShell)

Start the API first, then open another PowerShell terminal:

~~~powershell
$email = "manual_qa@example.test"
$phone = "+12025550150"
$password = "Local-QA-Password-123!"

$registerBody = @{
    username = "manual_qa"
    email = $email
    phone = $phone
    password = $password
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/auth/register" -ContentType "application/json" -Body $registerBody

$emailQuery = [uri]::EscapeDataString($email)
$phoneQuery = [uri]::EscapeDataString($phone)

$emailCode = Invoke-RestMethod -Uri "http://127.0.0.1:8000/qa/outbox/email?destination=$emailQuery"
$smsCode = Invoke-RestMethod -Uri "http://127.0.0.1:8000/qa/outbox/sms?destination=$phoneQuery"

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/auth/verify" -ContentType "application/json" -Body (@{ channel = "email"; destination = $email; code = $emailCode.code } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/auth/verify" -ContentType "application/json" -Body (@{ channel = "sms"; destination = $phone; code = $smsCode.code } | ConvertTo-Json)

$login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/auth/login" -ContentType "application/json" -Body (@{ email = $email; password = $password } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer " + $login.access_token }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/auth/me" -Headers $headers
~~~

Use a unique username and email for each manual registration. The automated batch
runner creates unique email addresses and usernames itself.

## Streamlit dashboard

The dashboard includes:

1. **Overview** — team account counts and latest QA run.
2. **Team Accounts** — add, import, inspect, and export metadata for existing team-owned accounts.
3. **Sandbox Batch** — synthetic identity/concurrency checks.
4. **Mailbox Manager** — opens a local persistent cPanel browser session and creates eight new mailboxes on the configured owned domain.
5. **Website Automation** — visually configure and save website QA profiles locally; no JSON editing required.
6. **Registration QA** — run 40 local registration, email verification, SMS verification, and login workflows.
7. **Run History & Export** — inspect previous runs and download CSV.
8. **SIMURU API** — browse account profile, balance, services, countries, prices, and country insights.

## Website Automation (visual configuration)

The **Website Automation** tab provides a form-based profile manager and a read-only
Playwright form inspector. Enter a registration page URL and click **Inspect Website &
Auto-detect Selectors** to discover visible inputs, labels, placeholders, submit controls,
and obvious Google sign-in buttons. Suggested CSS selectors are copied into the profile
form for review and can be edited before saving. The inspector never submits a form or
performs a login.
Save, select, preview, or delete profiles in the dashboard.

Profiles are stored locally in `data/website_profiles.json`, which is covered by
`.gitignore`. No manual JSON editing is required. Remote sites must use HTTPS.
A profile must explicitly confirm ownership or authorization before it can be considered
eligible for future QA execution.

This initial release is a **configuration manager only**: it does not submit external
registration forms, create Google Accounts, or automate sign-in to third-party services.
OAuth client credentials and secrets are not collected by this profile form. For an
application you own, configure its OAuth client and redirect URI separately in Google
Auth Platform and keep client secrets in local secret storage.

## Team Account Registry

The registry records existing Instagram accounts the team owns or is explicitly
authorized to manage. It stores usernames and owner/team metadata only.

| Account type | Registry behavior | Official Instagram API |
| --- | --- | --- |
| Personal | Metadata registry only | Not supported |
| Creator | Pending Meta OAuth setup | Eligible, subject to permissions and app access |
| Business | Pending Meta OAuth setup | Eligible, subject to permissions and app access |

Changing a Personal account to Professional can affect privacy and account features.
Only the account owner should make that change after reviewing Meta's guidance.

## SIMURU API integration

The API client uses the X-API-KEY header and reads the key from the local .env.

Read-only endpoints currently implemented:

| Feature | Endpoint |
| --- | --- |
| Account profile | GET /profile |
| Account balance | GET /balance |
| Service catalog | GET /services |
| Country catalog | GET /countries |
| Complete/filtered price list | GET /pricelist |
| Prices and countries by service | GET /services/{service}/countries |
| Available operators | GET /services/{service}/countries/{country}/operators |
| Price offers | GET /services/{service}/countries/{country}/offers |
| Country performance insights | GET /insights/countries |

State-changing operations are deliberately not exposed. Some provider APIs use GET for
transactions, so HTTP method alone is not treated as proof that an endpoint is read-only.
This project does not expose order creation/cancellation, number rental, email rental,
OTP retrieval, deposits, or social-media booster actions.

## Setup on Windows

Requirements:

- Windows 10/11
- Python 3.12
- uv

Clone the repository:

~~~powershell
git clone https://github.com/teguhdev97/simuru-research.git
cd simuru-research
~~~

If you are pulling the v0.5.0 work from the feature branch:

~~~powershell
git fetch origin
git switch feat/internal-registration-qa-v0.5.0
git pull --ff-only origin feat/internal-registration-qa-v0.5.0
~~~

Install dependencies:

~~~powershell
uv sync --extra dev
~~~

Create your local environment file if it does not exist:

~~~powershell
Copy-Item .env.example .env
~~~

Set your SIMURU API key locally in .env:

~~~env
SIMURU_BASE_URL=https://simuru.com/api
SIMURU_API_KEY=your_api_key_here
DATABASE_PATH=data/simuru_research.sqlite3
DEFAULT_TOTAL_JOBS=40
DEFAULT_MAX_WORKERS=3
~~~

Never commit the real API key, Meta App Secret, or access tokens. .env is ignored
by Git.

## Run the Streamlit dashboard

~~~powershell
uv run streamlit run app.py
~~~

Open the local URL printed by Streamlit, usually:

~~~text
http://localhost:8501
~~~

Select **Registration QA**, keep the default 40 jobs and 3 workers, then click
**Run registration QA batch**. The batch creates local QA users, verifies both
channels through the local test outbox, tests login/session validation, and stores
the results in SQLite.

## Run tests and lint

~~~powershell
uv run pytest
uv run ruff check .
~~~

Tests use temporary SQLite databases and local test fixtures. They do not contact
Instagram, SIMURU transaction endpoints, Temp-Mail, or Temp-Number.

## Project layout

~~~text
simuru-research/
├── app.py
├── .env.example
├── pyproject.toml
├── src/
│   └── simuru_research/
│       ├── api.py
│       ├── cli.py
│       ├── config/settings.py
│       ├── engine/
│       │   ├── registration_qa.py
│       │   └── runner.py
│       ├── models.py
│       ├── providers/
│       │   ├── sandbox.py
│       │   └── simuru_client.py
│       ├── security/
│       │   └── auth_qa.py
│       └── storage/
│           ├── database.py
│           ├── exporter.py
│           └── team_accounts.py
└── tests/
    ├── test_registration_qa.py
    ├── test_runner.py
    ├── test_simuru_client.py
    └── test_team_accounts.py
~~~


## Local five-mailbox QA

The Registration QA dashboard can create exactly five real mailboxes per run on a
domain you control. It uses cPanel UAPI `Email::add_pop`, assigns distinct
deterministic mailbox passwords derived from a local master secret, and stores the
five addresses in SQLite run history. It does not submit website registration forms.

See [docs/local-mailbox-qa.md](docs/local-mailbox-qa.md) for cPanel API token setup,
Windows configuration, mailbox naming, IMAP settings, and sender-allowlisted OTP
reader behavior. Keep cPanel tokens and mailbox master secrets in `.env` only.

## Mailbox Manager (eight local cPanel mailboxes)

The **Mailbox Manager** tab opens a persistent, visible Chromium profile on the local
Windows laptop. Sign in manually to your own Rumahweb cPanel, then click **Create 8 New
Emails**. SIMURU uses same-origin cPanel UAPI calls to list existing mailboxes, create
eight unique addresses, and verify the result.

- No cPanel API token is required for this browser-session mode.
- The cPanel password, cookies, and `cpsess` token are never copied into application
  settings, logs, or GitHub.
- The browser profile is stored under `data/cpanel-browser-profile` and is ignored by Git.
- Each mailbox receives a distinct random password. Download the one-time CSV result
  and store it securely; the passwords are not saved in the SQLite run history.
- Use only a cPanel account and domain you own or are authorized to administer.

Install and run:

~~~powershell
uv sync --extra dev
uv run playwright install chromium
uv run streamlit run app.py
~~~

Open **Mailbox Manager**, click **Connect cPanel**, complete login in Chromium, return
to Streamlit, then click **Create 8 New Emails**. See
[docs/mailbox-manager.md](docs/mailbox-manager.md).

## Browser Form QA (Selenium)

An optional Selenium utility can inspect the registration form of a local application
or an explicitly authorized staging site. It reports whether common username, email,
password, and submit controls are present.

### Safety and scope

- The default allowed hosts are `localhost` and `127.0.0.1`.
- Additional staging hosts must be explicitly added to `BROWSER_QA_ALLOWED_HOSTS`.
- The inspector does not submit forms or create accounts.
- CAPTCHA and OTP challenges remain under the control of the application owner and
  must be completed manually in an authorized test environment.
- No stealth/anti-detection driver, proxy rotation, CAPTCHA-solving service, or OTP
  interception is included.
- Third-party identity-provider registration pages are not supported targets.

### Install and run on Windows

Install the optional browser dependency:

~~~powershell
uv sync --extra dev --extra browser-qa
~~~

Install Google Chrome separately if it is not already installed. Selenium Manager
will manage a compatible ChromeDriver when the browser check is first run.

Start your local application, then inspect its registration form:

~~~powershell
$env:BROWSER_QA_ALLOWED_HOSTS = "localhost,127.0.0.1"
uv run simuru-browser-qa --url http://127.0.0.1:8000/register
~~~

To run Chrome headlessly:

~~~powershell
uv run simuru-browser-qa --url http://127.0.0.1:8000/register --headless
~~~

For an owned staging environment, add only the hostname you control:

~~~powershell
$env:BROWSER_QA_ALLOWED_HOSTS = "localhost,127.0.0.1,staging.example.org"
uv run simuru-browser-qa --url https://staging.example.org/register --headless
~~~

See [docs/browser-form-qa.md](docs/browser-form-qa.md) for details. The existing
**Registration QA** runner remains the tool for end-to-end synthetic registration,
email/SMS verification, and login tests against the local QA API.
