# Simuru Research

Windows research workspace for exploring the official SIMURU API through a local
Streamlit dashboard, plus a separate synthetic QA sandbox.

## Current release

- Version: 0.3.0
- Python: 3.12
- API base URL: https://simuru.com/api
- API documentation: https://simuru.com/api-docs
- Machine-readable specification: https://simuru.com/openapi.json

## Included SIMURU API integration

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
The complete price list can be downloaded as CSV. Its preview is limited to 100 rows
so the browser does not need to render the entire catalog at once.

### Deliberate transaction boundary

SIMURU documents some state-changing operations as GET requests. HTTP method alone
does not make those operations read-only. This project uses an explicit allowlist and
does not expose order creation, order cancellation, order completion, number rental,
email rental, OTP retrieval, deposits, or social-media booster actions.

The API key is never embedded in source code or sent in a URL. Keep **.env** private;
it is excluded by **.gitignore**.

### Rate limits and catalog freshness

- General documented API rate limit: 1,200 requests/minute per API key.
- Complete pricelist endpoint: 30 requests/minute and a documented 60-second cache.
- The API client requests gzip compression to reduce catalog transfer size.
- Use the dashboard buttons deliberately; it does not poll endpoints automatically.

## Local sandbox

The separate sandbox batch runner tests concurrency, SQLite persistence, and CSV
export using fictional identities only:

- Email domain: **example.test**
- Fictional phone range: North American 555-0100–0199
- Maximum batch size: 100 synthetic records
- Default worker count: 3; maximum: 10

Sandbox identities are not sent to SIMURU or to any third-party registration service.
The sandbox does not create external accounts or retrieve verification codes.

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

Open **.env** and add your API key locally:

~~~env
SIMURU_BASE_URL=https://simuru.com/api
SIMURU_API_KEY=your_api_key_here
DATABASE_PATH=data/simuru_research.sqlite3
DEFAULT_TOTAL_JOBS=40
DEFAULT_MAX_WORKERS=3
~~~

Do not commit the real API key. The **.env** file is ignored by Git.

## Run the dashboard

~~~powershell
uv run streamlit run app.py
~~~

Open the local URL printed by Streamlit, usually:

~~~text
http://localhost:8501
~~~

### Dashboard tabs

1. **Overview** — latest local sandbox run.
2. **Sandbox Batch** — run synthetic QA jobs with bounded concurrency.
3. **Run History & Export** — inspect previous runs and download CSV.
4. **SIMURU API / Account** — read profile and balance.
5. **SIMURU API / Services & Pricelist** — browse services, countries, prices, operators, and offers.
6. **SIMURU API / Country Insights** — inspect country performance summaries.

SIMURU requests are only sent after the corresponding button is clicked. No API key
is required to use the local sandbox.

## CLI usage

Run a 40-job local sandbox batch with three workers:

~~~powershell
uv run simuru-research --jobs 40 --workers 3
~~~

The CLI writes results to the SQLite database configured by **DATABASE_PATH**.

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
│           └── exporter.py
└── tests/
    ├── test_runner.py
    └── test_simuru_client.py
~~~
