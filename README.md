# Simuru Research

Local Windows research workspace for checking Simuru API connectivity and running
synthetic registration/verification QA against a **local sandbox only**.

## Scope and safety

This project is deliberately limited to:

- A read-only Simuru API connection check using **GET /api/profile**.
- A local sandbox batch runner for up to 100 synthetic test identities.
- A bounded worker pool (default: 3 workers; maximum: 10).
- SQLite run history and CSV export.
- A Streamlit dashboard for monitoring test runs.

The sandbox generates reserved test identities only:

- Email addresses under **example.test**.
- Fictional phone numbers in the North American 555-0100–0199 range.
- No real inboxes, phone numbers, OTPs, passwords, or third-party accounts.

It does **not** rent email addresses or phone numbers, retrieve verification codes,
create third-party accounts, automate Instagram signup, rotate proxies, or bypass
platform anti-abuse controls. Do not add those workflows to this project.

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

Open **.env** and optionally add your Simuru API key:

~~~env
SIMURU_BASE_URL=https://simuru.com/api
SIMURU_API_KEY=your_api_key_here
DATABASE_PATH=data/simuru_research.sqlite3
DEFAULT_TOTAL_JOBS=40
DEFAULT_MAX_WORKERS=3
~~~

The API key is optional. The local sandbox works without it. Keep **.env** private;
it is excluded by **.gitignore**.

## Run the dashboard

~~~powershell
uv run streamlit run app.py
~~~

Open the local URL printed by Streamlit, usually:

~~~text
http://localhost:8501
~~~

### Dashboard features

1. **Overview** — latest run totals and API connection status.
2. **Sandbox Batch** — run 40 synthetic QA identities with a bounded worker pool.
3. **Run History** — inspect previous local test runs.
4. **Export** — download a run's synthetic results as CSV.
5. **Simuru Connection** — optionally validate the API key with the read-only profile endpoint.

The Simuru client intentionally exposes only the profile check. It does not include
purchase, rental, order, inbox, phone, or OTP endpoints.

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

All tests use mocked HTTP responses or local SQLite files; they do not spend API
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
│       ├── providers/sandbox.py
│       ├── providers/simuru_client.py
│       └── storage/database.py
└── tests/
    ├── test_runner.py
    └── test_simuru_client.py
~~~
