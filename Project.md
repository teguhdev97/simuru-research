# Project Context — SIMURU Research

> Living handoff document for developers and AI coding agents. Read this file before changing architecture or behavior.

## 1. Project summary

**SIMURU Research** is a local-first Windows research and QA workspace built with Python 3.12, Streamlit, Playwright, FastAPI, and SQLite. It combines local synthetic QA workflows, team metadata, read-only SIMURU API research, cPanel mailbox administration for a domain the operator controls, and visual configuration for authorized website QA.

- Repository: https://github.com/teguhdev97/simuru-research
- Primary runtime: Windows 10/11, local laptop
- Dashboard: Streamlit (app.py)
- Package manager: uv
- Persistence: SQLite plus local JSON configuration
- Browser automation: Playwright Chromium over local CDP for cPanel; separate headless Playwright for read-only form inspection
- Current working branch: feat/five-mailbox-local-qa
- Python requirement: 3.12+

## 2. Product goals

1. Provide a local dashboard for research and QA operations.
2. Keep secrets, browser sessions, databases, and generated credentials on the operator's machine.
3. Support cPanel mailbox administration only for domains the operator owns or is authorized to administer.
4. Make website QA configuration visual rather than requiring manual JSON edits.
5. Keep external website testing limited to owned systems or explicitly authorized environments.
6. Make the repository understandable to human contributors and other AI coding agents.

## 3. Current dashboard areas

| Tab | Responsibility |
|---|---|
| Overview | Team metadata counts and latest QA run |
| Team Accounts | Metadata registry for existing team-managed accounts |
| Sandbox Batch | Synthetic local test identities and bounded concurrency |
| Mailbox Manager | Open local Chromium, manually authenticate to cPanel, inspect UAPI session, create a bounded mailbox batch |
| Website Automation | Visual website profile editor and read-only Playwright form inspection |
| Registration QA | End-to-end local registration/email/SMS/login tests using local fixtures |
| Run History & Export | Review persisted QA results and export CSV |
| SIMURU API | Read-only API research |

## 4. Architecture and important modules

- app.py: Streamlit dashboard and UI orchestration.
- src/simuru_research/config/settings.py: environment-based application settings.
- src/simuru_research/config/website_profiles.py: validation and local persistence for website profiles.
- src/simuru_research/engine/form_inspector.py: read-only Playwright inspection of visible form controls and suggested CSS selectors.
- src/simuru_research/engine/registration_qa.py: local registration QA runner.
- src/simuru_research/providers/cpanel_browser.py: persistent Chromium lifecycle, CDP attach, cPanel UAPI session checks, mailbox creation, and close/logout behavior.
- src/simuru_research/providers/mailbox.py: mailbox provider abstractions/errors.
- src/simuru_research/security/auth_qa.py: local auth/OTP test service.
- src/simuru_research/storage/database.py: SQLite repository.
- src/simuru_research/storage/team_accounts.py: team metadata registry.
- tests/: automated unit and integration tests.

## 5. cPanel Mailbox Manager — current behavior

The current browser-session integration does **not** require a cPanel API token.

1. Streamlit asks the local manager to start Chromium with a persistent local profile and remote debugging endpoint (default port 9222).
2. The operator logs into their own cPanel manually.
3. A later Streamlit run attaches to Chromium through CDP.
4. The manager locates open tabs for the configured cPanel host.
5. It calls cPanel UAPI with same-origin browser credentials.
6. Mailbox creation uses Email::add_pop; mailbox listing uses Email::list_pops.
7. The manager verifies the result by listing mailboxes again.
8. The close action attempts cPanel logout, clears local cookies, and closes Chromium.

### Current diagnostic change

The Mailbox Manager includes a **Check cPanel Session** action. It checks all open cPanel tabs and reports:
- whether a cPanel tab was found;
- whether the URL contains a cPanel session prefix (the session ID is redacted in diagnostics);
- HTTP status and redirect behavior of the UAPI request;
- cPanel UAPI status/errors/messages.

The dashboard should never print a raw cpsess value, cookies, passwords, API tokens, or mailbox passwords in logs or diagnostic panels.

### Important implementation notes

- Streamlit reruns its script on interaction. Do not keep Playwright sync objects across Streamlit runs/threads. Attach a fresh Playwright client to the independently running Chromium process each run.
- Never assume the first browser tab is the authenticated cPanel tab. Probe all tabs belonging to the configured cPanel host and retain the tab whose UAPI request succeeds.
- Use the authenticated page returned by the successful probe for subsequent mailbox operations.
- A visible cPanel Tools page alone is not proof that the UAPI request works.
- Do not silently report login success if UAPI has redirected to a login page or returned an error.
- cPanel API responses may encode status as a number or string; normalize before comparison.
- Do not expose raw cPanel session identifiers in errors, screenshots, logs, or generated docs.

## 6. Website Automation — current behavior

The visual Website Automation tab stores website profiles locally in data/website_profiles.json. It supports:
- profile name and base URL;
- registration path;
- authentication method;
- CSS selectors for common form fields;
- Google OAuth QA flag;
- explicit ownership/authorization acknowledgement.

The form inspector opens the supplied page in a separate headless Playwright browser and reads visible form controls. It suggests selectors and identifies obvious Google sign-in controls. It is read-only: it must not submit registration forms or perform a login.

Profiles are configuration only. Do not claim that a profile can register users until a separately reviewed, bounded QA execution engine exists.

## 7. Local development

Requirements:
- Windows 10/11
- Python 3.12+
- uv

Setup:

~~~powershell
git clone https://github.com/teguhdev97/simuru-research.git
cd simuru-research
uv sync --extra dev
uv run playwright install chromium
Copy-Item .env.example .env
uv run streamlit run app.py
~~~

Run checks:

~~~powershell
uv run pytest
uv run ruff check .
~~~

Local dashboard: http://localhost:8501.

## 8. Environment and secrets

- .env is local-only and must never be committed.
- data/ is local-only and ignored by Git; it may contain browser profile data, SQLite databases, and website profiles.
- Do not store cPanel passwords, cPanel API tokens, cpsess, Google client secrets, mailbox passwords, or OAuth tokens in source code, SQLite logs, Markdown docs, screenshots, or Git history.
- The browser-session cPanel mode does not need CPANEL_API_TOKEN.
- If a future API-token mode is implemented, use a dedicated least-privilege token and an OS-backed secret store where possible.
- Rotate any secret or session token accidentally shared in chat, screenshots, terminal output, or commits.

## 9. Safety and authorization boundaries

- cPanel automation is limited to domains and hosting accounts the operator owns or is authorized to administer.
- Website QA must target localhost, owned environments, or explicitly authorized test targets.
- Google OAuth testing uses the OAuth client configured by the application owner. Do not create Google Accounts in bulk, bypass Google security checks, or automate third-party account creation.
- Do not add stealth drivers, anti-detection, proxy rotation, CAPTCHA solving, OTP interception, or rate-limit evasion.
- Keep test batches bounded and show a confirmation before actions that create real resources.

## 10. Engineering conventions for AI contributors

Before making changes:
1. Read this file and PRD.md.
2. Inspect the current branch and relevant modules; do not assume older chat summaries reflect current code.
3. Preserve existing behavior unless the task explicitly changes it.
4. Keep changes focused and add tests for parsing, validation, error handling, and state transitions.
5. Never put secrets or real session identifiers in fixtures.
6. Run uv run pytest and uv run ruff check . when the environment is available.
7. Report tests that could not be run; do not claim unexecuted tests passed.
8. Update this document and PRD.md when architecture or scope changes.

## 11. Known follow-up work

- Add unit tests for cPanel session response normalization and diagnostic redaction.
- Add integration tests with mocked UAPI responses (success, redirect-to-login, non-JSON, API error, expired session).
- Verify cPanel logout route behavior with Rumahweb; do not claim server-side invalidation until confirmed.
- Add an explicit configurable mailbox batch size with a hard upper bound and preview.
- Consider encrypted one-time credential export and secure deletion guidance.
- Improve the form inspector with interactive element picking and iframe-aware inspection.
- Add OAuth test configuration for applications the operator owns, using official Google OAuth flows.
- Add CI that runs pytest and Ruff on pull requests.
