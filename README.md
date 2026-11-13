# Simuru Research

Local Windows research workspace for SIMURU API exploration, team account metadata,
synthetic QA, and a local registration/authentication test service.

## Current release

- Version: 0.6.0
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
2. Generate a six-digit email verification code for the QA user.
3. Send the email through local Mailpit SMTP and capture it in the Mailpit inbox.
4. Read the received message through Mailpit's local REST API and extract the OTP.
5. Verify the email address against the application's one-time verification record.
6. Generate and verify a separate SMS code through the local SMS test outbox.
7. Hash and verify the password using PBKDF2-HMAC-SHA256.
8. Log in and validate the resulting session token.
9. Save the job result to the existing run history and allow CSV export.

### Test-only data boundaries

- Email addresses use the reserved example.test domain.
- Email OTPs are sent only to the local Mailpit SMTP listener and captured by its local inbox/API.
- Mailpit SMTP and HTTP ports are published only on 127.0.0.1; no real mailbox receives the test email.
- Phone numbers use the fictional +1-202-555-0100 through +1-202-555-0199 range.
- SMS OTPs remain in the local SQLite test outbox; no SMS provider is contacted.
- Passwords are randomly generated in memory and stored only as salted password hashes.
- OTPs are cleared from the local verification outbox when consumed.
- Access tokens are stored as SHA-256 hashes in SQLite.
- The QA API rejects non-loopback clients; run it on 127.0.0.1.
- No SIMURU rental, Temp-Mail, Temp-Number, or Instagram request is made by this local QA flow.

These test users can authenticate against the **local QA API only**. They are not
Instagram accounts and cannot log in to Instagram.

## Local email testing with Mailpit

Version 0.6.0 uses [Mailpit](https://github.com/axllent/mailpit) to exercise the
real SMTP delivery path without sending messages to public email providers. The
default dashboard provider is **Mailpit SMTP**. The **Local outbox** option remains
available as an offline fallback.

### Start Mailpit on Windows

Requirements: Docker Desktop or Podman with its machine running.

From the repository root, start the pinned Mailpit container:

~~~powershell
podman run -d --name simuru-mailpit -p 127.0.0.1:1025:1025 -p 127.0.0.1:8025:8025 ghcr.io/axllent/mailpit:v1.33.1
~~~

If you use Docker instead of Podman, replace \`podman\` with \`docker\`.

Alternatively, use the included Compose file with a compatible Compose provider:

~~~powershell
podman compose -f compose.mailpit.yml up -d
~~~

Check that the container is running:

~~~powershell
podman ps --filter name=simuru-mailpit
podman logs simuru-mailpit
~~~

Open the local Mailpit inbox:

~~~text
http://127.0.0.1:8025
~~~

Mailpit SMTP listens on \`127.0.0.1:1025\`; its REST API listens on
\`http://127.0.0.1:8025\`. Both published ports are bound to loopback only.

### Configure Simuru Research

Add these values to your local \`.env\` file. Do not commit \`.env\`:

~~~env
MAILPIT_SMTP_HOST=127.0.0.1
MAILPIT_SMTP_PORT=1025
MAILPIT_API_URL=http://127.0.0.1:8025
MAILPIT_FROM_EMAIL=no-reply@simuru.local
MAILPIT_TIMEOUT_SECONDS=5
MAILPIT_POLL_TIMEOUT_SECONDS=15
MAILPIT_POLL_INTERVAL_SECONDS=0.25
~~~

The defaults are also listed in \`.env.example\`. Restart Streamlit after changing
environment variables.

### Run the Mailpit email QA flow

1. Start Mailpit.
2. Start the dashboard with \`uv run streamlit run app.py\`.
3. Open **Registration QA**.
4. Keep **Mailpit SMTP** selected.
5. Click **Check Mailpit connection**; both SMTP and HTTP API must be reachable.
6. Run a small batch first (for example, 2 QA users) and inspect the captured emails at
   \`http://127.0.0.1:8025\`.
7. Increase to 40 QA users after the small test passes.

Each QA email includes a \`SIMURU-QA-OTP\` marker used by the integration test to
extract the code from the message body. The runner checks that the received code
matches the code issued by the local application before completing email verification.

To stop Mailpit:

~~~powershell
podman stop simuru-mailpit
~~~

To start it again:

~~~powershell
podman start simuru-mailpit
~~~

The mailbox is for local development and may be cleared when the container is removed.
Do not use it as a public inbox or expose its SMTP/API ports to a LAN or the internet.

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
4. **Registration QA** — run 40 local registration, email verification, SMS verification, and login workflows.
5. **Run History & Export** — inspect previous runs and download CSV.
6. **SIMURU API** — browse account profile, balance, services, countries, prices, and country insights.

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

Select **Registration QA**, keep **Mailpit SMTP** selected, and first test with 2 jobs and 1-2 workers. After the captured emails and OTP checks pass, increase to 40 jobs and 3 workers. The batch stores local QA users and results in SQLite.

## Run tests and lint

~~~powershell
uv run pytest
uv run ruff check .
~~~

Tests use temporary SQLite databases, mocked Mailpit SMTP/API responses, and local fixtures. They do not contact Instagram, SIMURU transaction endpoints, Temp-Mail, or Temp-Number.

## Project layout

~~~text
simuru-research/
├── app.py
├── .env.example
├── compose.mailpit.yml
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
│       │   ├── mailpit.py
│       │   ├── sandbox.py
│       │   └── simuru_client.py
│       ├── security/
│       │   └── auth_qa.py
│       └── storage/
│           ├── database.py
│           ├── exporter.py
│           └── team_accounts.py
└── tests/
    ├── test_mailpit.py
    ├── test_registration_qa.py
    ├── test_runner.py
    ├── test_simuru_client.py
    └── test_team_accounts.py
~~~
