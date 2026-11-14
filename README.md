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

## New in v0.5.0: Registration QA

The **Registration QA** page creates five new cPanel mailboxes on the configured
domain, then runs the local registration/login checks for those addresses with
two concurrent workers. Sign in to cPanel first from **List email → Mailbox
management**, then return to Registration QA and check the cPanel session.

Each job executes:

1. Register a QA user in the local SQLite database.
2. Generate a six-digit email verification code in the local test outbox.
3. Verify the email address.
4. Generate and verify a separate SMS verification code in the local test outbox.
5. Hash and verify the password using PBKDF2-HMAC-SHA256.
6. Log in and validate the resulting session token.
7. Save the job result to the existing run history and allow CSV export.

### Test-only data boundaries

- Registration QA is limited to the configured QA email domain.
- Phone numbers use the fictional +1-202-555-0100 through +1-202-555-0199 range.
- Passwords are randomly generated in memory and stored only as salted password hashes.
- OTPs are held temporarily in a local QA outbox and cleared when consumed.
- Access tokens are stored as SHA-256 hashes in SQLite.
- The QA API rejects non-loopback clients; run it on 127.0.0.1.
- Creating the five mailboxes is a real cPanel action. The registration email/SMS
  verification steps still use the local test outbox; no OTP email or SMS is sent.
- No SIMURU rental, Temp-Mail, Temp-Number, or Instagram request is made by this local QA flow.

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

The dashboard uses a responsive Sneat/shadcn-inspired sidebar, a fixed full-width
app bar, breadcrumbs, and a rounded card frame with a soft shadow on each page. On
tablet and phone widths, the sidebar collapses to icon-only navigation and reveals
labels on hover or focus; the app logo follows the same behavior. The main content
scrolls independently from the sidebar. In
**List email**, the mailbox page shows domain email accounts (6 per page), the
selected account's inbox, and the opened message in three panes. Verify the cPanel session before
refreshing the email list. `QA_MAILBOX_MASTER_PASSWORD` is tried automatically once
when an account is selected; later inbox refreshes are manual. Passwords entered as
temporary alternatives remain in the active app session and are not saved to Windows
Credential Manager. Newly created addresses from the latest app flow appear first.
Numbered pagination is shared with the latest-run results table. Long addresses are
shortened in the list and can be expanded per row. IMAP access is read-only.

The dashboard includes:

1. **Overview** — active domain email count and latest QA run.
2. **Sandbox Batch** — synthetic identity/concurrency checks.
3. **List email** — lists domain mailboxes, displays the selected inbox and message content, and provides mailbox management for the five-mailbox QA flow.
4. **Registration QA** — create five domain mailboxes, then run local registration and login checks with two workers.
5. **Run History & Export** — inspect previous runs and download CSV.
6. **SIMURU API** — browse account profile, balance, services, countries, prices, and country insights.

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

Select **Registration QA**, confirm the cPanel session, then click **Create 5
mailboxes and run registration QA**. The flow creates five domain mailboxes,
tests registration/login with two local workers, and stores the results in SQLite.

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
│       │   ├── cpanel_browser.py
│       │   ├── cpanel_browser_session.py
│       │   ├── cpanel_mailboxes.py
│       │   ├── sandbox.py
│       │   └── simuru_client.py
│       ├── security/
│       │   └── auth_qa.py
│       ├── storage/
│       │   ├── database.py
│       │   └── exporter.py
│       └── ui/
│           ├── api_tab.py
│           ├── history_tab.py
│           ├── mailbox_tab.py
│           ├── mailbox_workflow.py
│           ├── mailbox_session.py
│           ├── mailbox_batch.py
│           ├── mailbox_otp.py
│           ├── overview_tab.py
│           ├── registration_qa_tab.py
│           ├── sandbox_tab.py
│           ├── tabs.py
│           └── pagination.py
└── tests/
    ├── test_registration_qa.py
    ├── test_runner.py
    └── test_simuru_client.py
~~~


## Project handoff and product requirements

- [Project.md](Project.md) — architecture, current implementation, local setup, security boundaries, and instructions for AI coding agents.
- [PRD.md](PRD.md) — product goals, user journeys, functional requirements, acceptance criteria, milestones, and risks.

## Local five-mailbox QA

The Mailbox Manager can create exactly five real mailboxes per run on a
domain you control. It uses the local cPanel browser session and UAPI, assigns distinct
random mailbox passwords when no shared QA password is configured, and stores those
mailbox passwords in Windows Credential Manager. The five addresses and non-secret
operation results are shown in the dashboard. Website Automation and Team Accounts are
not part of the current dashboard.

See [docs/local-mailbox-qa.md](docs/local-mailbox-qa.md) for cPanel API token setup,
Windows configuration, mailbox naming, IMAP settings, and sender-allowlisted OTP
reader behavior. Keep cPanel tokens and mailbox master secrets in `.env` only.

## Mailbox Manager (five local cPanel mailboxes)

The **Mailbox Manager** tab opens a persistent, visible Chromium profile on the local
Windows laptop. Sign in manually to your own Rumahweb cPanel, then click **Create 5 New
Emails**. SIMURU uses same-origin cPanel UAPI calls to list existing mailboxes, create
five unique addresses, and verify the result.

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
to Streamlit, then click **Create 5 New Emails**. See
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
**Registration QA** runner uses verified domain mailbox addresses for local
registration and login checks. Its email/SMS codes still come from the local QA
outbox; browser-form checks against an authorized staging site remain a separate flow.


## Google OAuth QA test-user preparation

After a successful five-mailbox batch, the Mailbox Manager reveals a Google OAuth
preparation panel. It provides a copy/download list of the five addresses and stores
only the Google Cloud project name, OAuth Client ID, redirect URI, and email list in
`data/google_oauth_qa.json`. It never stores a Client Secret.

Each address must first be a real Google Account. Google supports signing up with an
existing non-Gmail address by choosing **Use your existing email** and verifying the
code delivered to that mailbox. Then, for an External app in Testing mode, add those
Google Accounts manually under Google Auth Platform → Audience → Test users. SIMURU
does not automate Google Account creation or bypass Google's account-security flow.

Official guides: [Create a Google Account using an existing email](https://support.google.com/accounts/answer/27441)
and [Configure OAuth consent / test users](https://developers.google.com/workspace/guides/configure-oauth-consent).


### Integrated five-mailbox → Google OAuth QA workflow

The Mailbox Manager accepts an optional shared password in its dashboard field or
from local `QA_MAILBOX_MASTER_PASSWORD`. If it is left blank, SIMURU generates a
strong random password per mailbox, preserving the previous successful flow. A
password entered in the dashboard is kept in the local Streamlit session; a persistent
value belongs only in your ignored `.env` file. Example placeholder:

```dotenv
QA_MAILBOX_MASTER_PASSWORD=<your-local-temporary-password>
```

The five mailboxes already created with random passwords can be found with **Refresh existing mailbox list**, selected in the dashboard, and reset with **Set same password for selected existing mailboxes** after the cPanel session is verified. The current batch can also be reset with **Set same password for these 5 mailboxes**.
New batches use the configured password from the start. This shared password is only
for short-lived QA and should be rotated after testing.

Once all five mailboxes are verified, the same Mailbox Manager shows **Google OAuth
Registration QA**. Enter the authorized staging/local registration URL, select one
of the five test identities, confirm the Google Accounts are already set up and added
as OAuth Test Users, then inspect the page and open it in Chromium. Google account
selection, consent, CAPTCHA and MFA remain manual; this flow does not create Google
Accounts from mailboxes.


### Google OAuth registration launcher

After the five mailbox batch is verified and the five addresses have been created as
Google Accounts and added to OAuth Test Users, enter the authorized registration URL.
SIMURU will inspect the page, let you choose a detected Google sign-in control, then
open the page and click that control in local Chromium. Complete Google sign-in,
account selection, consent, CAPTCHA, and MFA manually. The target app must implement
the OAuth callback that validates Google's ID token and creates or links its local user.

This launcher does not create Google Accounts. A mailbox address alone is not a
Google Account.


## Local mailbox credentials and IMAP OTP

The browser-session cPanel workflow creates exactly five mailboxes without a cPanel API token. Passwords for verified mailboxes are stored in the local Windows Credential Manager through `keyring`; they are never written to the SQLite run history. The exact password submitted to cPanel is the password used by IMAP and optional SMTP.

- If `QA_MAILBOX_MASTER_PASSWORD` is blank, each newly created mailbox gets a different cryptographically random password.
- If a shared QA password is entered in the dashboard, the same value is submitted for the five new mailboxes. Use only temporary QA secrets.
- To use mailboxes created before the credential vault was added, expand **Import existing mailbox password from CSV**, enter each old QA address and its password from the previously downloaded CSV, and save it to Windows Credential Manager.
- **Check IMAP connection** authenticates and opens INBOX; it does not wait for an email.
- **Wait for fresh verification code** is separate. Configure exact sender addresses/domains in `QA_OTP_ALLOWED_SENDERS` before using it. The reader only searches fresh unseen messages and configured subjects.
- SMTP is optional. Incoming OTP requires IMAP only.

Example local `.env` values (confirm host/ports against cPanel → Email Accounts → Connect Devices):

```dotenv
QA_IMAP_HOST=mail.teguhharits.com
QA_IMAP_PORT=993
QA_OTP_ALLOWED_SENDERS=verification-sender@example.test
QA_OTP_SUBJECT_KEYWORDS=verification,verify,otp,code
```
