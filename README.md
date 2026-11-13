# Simuru Research

Local Windows research workspace for exploring the official SIMURU API, managing
metadata for existing team Instagram accounts, and running synthetic QA batches.

## Current release

- Version: 0.4.0
- Python: 3.12
- Runtime: local Windows machine
- API base URL: https://simuru.com/api
- SIMURU API documentation: https://simuru.com/api-docs
- Meta Instagram API documentation: https://www.postman.com/meta/instagram/documentation/

## Important platform boundaries

This project does **not** create Instagram accounts, automate Instagram sign-up,
rent temporary phone numbers or email inboxes, retrieve Instagram OTPs, or bypass
Instagram verification and anti-abuse controls.

SIMURU's own Terms of Service prohibit mass-creating fake accounts and evading bans.
Use SIMURU only for accounts and activities you own or are lawfully authorized to
manage, and follow the provider's current terms.

Meta's official Instagram APIs are for eligible Instagram professional accounts
(Business and Creator). Consumer/personal Instagram accounts are not available
through the Instagram API. A Meta Graph API Test User is a Facebook app test user;
it is not a newly created Instagram account.

## Team Account Registry (v0.4.0)

The local **Team Accounts** tab records existing Instagram accounts that the team
owns or is explicitly authorized to manage.

Stored fields:

- Instagram username
- Owner/team label
- Account type: personal, creator, or business
- Owner authorization confirmation
- Local API-readiness status
- Optional notes and timestamps

The registry supports:

- Adding one existing account at a time.
- Importing authorized account metadata from CSV.
- Exporting the registry to CSV.
- Counting accounts by type.
- Duplicate username detection (case-insensitive).

### Account type behavior

| Account type | Registry behavior | Instagram API |
| --- | --- | --- |
| Personal | Metadata registry only | Not supported by the official Instagram API |
| Creator | Pending Meta OAuth setup | Eligible, subject to app setup and permissions |
| Business | Pending Meta OAuth setup | Eligible, subject to app setup and permissions |

Changing a Personal account to Professional can affect privacy and account features.
Only the account owner should make that change after reviewing Meta's current guidance.
This application does not change account types.

### CSV format

Required columns:

~~~csv
username,owner_label,account_type,owner_approved,notes
sample_team_account,Marketing Team,personal,true,Replace with an authorized account
~~~

Only rows with owner_approved=true are imported. Do not include passwords, OTPs,
phone numbers, email credentials, session cookies, or access tokens in this CSV.

## SIMURU API integration

The API client follows the public SIMURU documentation and authenticates with the
**X-API-KEY** request header. The API key is loaded from the local **.env** file.

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

The dashboard is split into Account, Services & Pricelist, and Country Insights.
The complete price list can be downloaded as CSV.

### Deliberate transaction boundary

SIMURU documents some state-changing operations as GET requests. HTTP method alone
does not make those operations read-only. This project uses an explicit allowlist and
does not expose order creation, order cancellation, order completion, number rental,
email rental, OTP retrieval, deposits, or social-media booster actions.

The API key is never embedded in source code or sent in a URL. Keep **.env** private;
it is excluded by **.gitignore**.

## Synthetic QA sandbox

The separate sandbox batch runner tests concurrency, SQLite persistence, and CSV
export using fictional identities only:

- Email domain: **example.test**
- Fictional phone range: North American 555-0100–0199
- Maximum batch size: 100 synthetic records
- Default worker count: 3; maximum: 10

Sandbox identities are not sent to SIMURU or to any third-party registration service.
The sandbox does not create external accounts or retrieve verification codes.

## Future Meta OAuth integration

A later release can add OAuth for existing Creator/Business accounts after:

1. The team selects one Meta app and verifies that the Instagram API product is enabled.
2. An account owner explicitly authorizes the app through Meta's official login flow.
3. The app is configured with the required redirect URI, permissions, roles, and review/access level.
4. The app stores tokens in an OS-backed secret store, not in source control or CSV files.

This release does not implement Meta OAuth or claim that any Instagram account is connected.
Do not paste Meta App Secret or access tokens into chat or commit them to GitHub.

## Requirements

- Windows 10/11
- Python 3.12
- [uv](https://docs.astral.sh/uv/)

The repository pins Python 3.12 in **.python-version**.

## Setup on Windows PowerShell

Clone the repository:

~~~powershell
git clone https://github.com/teguhdev97/simuru-research.git
cd simuru-research
~~~

Install dependencies:

~~~powershell
uv sync --extra dev
~~~

Create your local environment file:

~~~powershell
Copy-Item .env.example .env
~~~

Open **.env** and add your SIMURU API key locally:

~~~env
SIMURU_BASE_URL=https://simuru.com/api
SIMURU_API_KEY=your_api_key_here
DATABASE_PATH=data/simuru_research.sqlite3
DEFAULT_TOTAL_JOBS=40
DEFAULT_MAX_WORKERS=3
~~~

Do not commit the real API key. The **.env** file is ignored by Git.

## Run the dashboard locally

~~~powershell
uv run streamlit run app.py
~~~

Open the local URL printed by Streamlit, usually:

~~~text
http://localhost:8501
~~~

### Dashboard tabs

1. **Overview** — team account counts and latest synthetic QA run.
2. **Team Accounts** — add, import, inspect, and export authorized account metadata.
3. **Sandbox Batch** — run synthetic QA jobs with bounded concurrency.
4. **Run History & Export** — inspect previous runs and download CSV.
5. **SIMURU API** — browse account profile, balance, services, countries, prices, and insights.

SIMURU requests are only sent after the corresponding button is clicked. No API key
is required to use the local registry or sandbox.

## CLI usage

Run a 40-job local sandbox batch with three workers:

~~~powershell
uv run simuru-research --jobs 40 --workers 3
~~~

The CLI writes results to the SQLite database configured by DATABASE_PATH.

## Tests and lint

~~~powershell
uv run pytest
uv run ruff check .
~~~

Tests use mocked HTTP responses or local SQLite files. They do not spend SIMURU
balance or contact third-party registration services.

## Project layout

~~~text
simuru-research/
├── app.py
├── .env.example
├── pyproject.toml
├── src/
│   └── simuru_research/
│       ├── cli.py
│       ├── config/settings.py
│       ├── engine/runner.py
│       ├── models.py
│       ├── providers/
│       │   ├── sandbox.py
│       │   └── simuru_client.py
│       └── storage/
│           ├── database.py
│           ├── exporter.py
│           └── team_accounts.py
└── tests/
    ├── test_runner.py
    ├── test_simuru_client.py
    └── test_team_accounts.py
~~~
