# Project Context — SIMURU Research

> Living handoff document for developers and AI coding agents. Read this file before changing architecture or behavior.

## 1. Project summary

**SIMURU Research** is a local-first Windows research and QA workspace built with Python 3.12, Streamlit, Playwright, FastAPI, and SQLite. It combines local synthetic QA workflows, read-only SIMURU API research, and cPanel mailbox administration for a domain the operator controls.

- Repository: https://github.com/teguhdev97/simuru-research
- Primary runtime: Windows 10/11, local laptop
- Dashboard: Streamlit (app.py)
- Dashboard layout: shared breadcrumb and card frame; responsive icon-only sidebar on tablet/mobile
- Package manager: uv
- Persistence: SQLite plus local JSON configuration
- Browser automation: Playwright Chromium over local CDP for cPanel
- Current working branch: feat/five-mailbox-local-qa
- Python requirement: 3.12+

## 2. Product goals

1. Provide a local dashboard for research and QA operations.
2. Keep secrets, browser sessions, databases, and generated credentials on the operator's machine.
3. Support cPanel mailbox administration only for domains the operator owns or is authorized to administer.
4. Make the repository understandable to human contributors and other AI coding agents.

## 3. Current dashboard areas

| Tab | Responsibility |
|---|---|
| Overview | Active domain email count and latest QA run |
| Sandbox Batch | Synthetic local test identities and bounded concurrency |
| List email | Browse domain mailboxes, read inboxes, and manage the five-mailbox QA flow |
| Registration QA | Create five domain mailboxes, then run local registration/login checks with two workers |
| Run History & Export | Review persisted QA results and export CSV |
| SIMURU API | Read-only API research |

## 4. Architecture and important modules

- app.py: Streamlit dashboard and UI orchestration.
- src/simuru_research/config/settings.py: environment-based application settings.
- src/simuru_research/engine/registration_qa.py: local registration QA runner.
- src/simuru_research/providers/cpanel_browser.py: public facade preserving the existing cPanel manager API.
- src/simuru_research/providers/cpanel_browser_session.py: persistent Chromium lifecycle, CDP attach, cPanel session checks, URL validation, and close/logout behavior.
- src/simuru_research/providers/cpanel_mailboxes.py: cPanel UAPI normalization, listing, creation, credential import, and password reset.
- src/simuru_research/ui/mailbox_tab.py: mailbox settings and cPanel connection controls.
- src/simuru_research/ui/mailbox_workflow.py: mailbox workflow composition.
- src/simuru_research/ui/mailbox_session.py: cPanel status and existing-mailbox actions.
- src/simuru_research/ui/mailbox_batch.py: mailbox batch results, password updates, and credential import.
- src/simuru_research/ui/mailbox_otp.py: mailbox connectivity and OTP controls.
- src/simuru_research/providers/mailbox.py: mailbox provider abstractions/errors.
- src/simuru_research/security/auth_qa.py: local auth/OTP test service.
- src/simuru_research/storage/database.py: SQLite repository.
- tests/: automated unit and integration tests.

The shared page frame and responsive sidebar are rendered from `app.py` and
`src/simuru_research/ui/tabs.py`. Sandbox job-count and concurrency controls live on
the Sandbox Batch page rather than in the navigation rail.

## 5. cPanel Mailbox Manager — current behavior

The current browser-session integration does **not** require a cPanel API token.

1. Streamlit asks the local manager to start Chromium with a persistent local profile and remote debugging endpoint (default port 9222).
2. The operator logs into their own cPanel manually.
3. Each explicit Streamlit interaction attaches to Chromium through a fresh Playwright client over CDP.
4. The manager locates open tabs for the configured cPanel host.
5. It calls cPanel UAPI with same-origin browser credentials.
6. Mailbox creation uses Email::add_pop; mailbox listing uses Email::list_pops.
7. The manager verifies the result by listing mailboxes again.
8. The close action attempts cPanel logout, clears local cookies, and closes Chromium.

### Current diagnostic change

The Mailbox management view shows a cPanel session status panel. It checks all open cPanel tabs when the view is rendered and reports:
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

## 6. Removed dashboard surfaces

The Website Automation and Team Accounts pages and their supporting implementation
have been removed. Mailbox UI is limited to domain inbox access, mailbox management,
and OTP-related mailbox diagnostics. Existing local data files are not modified.

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


## 12. Five-mailbox and Google OAuth gated workflow

The current Mailbox Manager creates exactly five new mailboxes, then lists all
mailboxes again and marks the batch complete only when all five addresses are found.
The Mailbox management view checks cPanel UAPI during normal Streamlit page renders.
There is no background polling; after manual login in Chromium, use a dashboard
interaction or navigate back to the view to recheck the session.

Only after a five-of-five verified batch does the UI reveal **Google OAuth · Prepare
Test Users**. This panel:
- shows and exports the five mailbox addresses;
- explains how to create a Google Account using each existing mailbox address;
- links to Google Auth Platform → Audience → Test users;
- saves the Google Cloud project name, OAuth Client ID, redirect URI, and five addresses
  locally in data/google_oauth_qa.json;
- never asks for or stores a Google Client Secret.

Google Account creation and adding test users remain manual owner actions. An email
mailbox by itself is not a Google Account. OAuth test-user entries must refer to
actual Google Accounts. See PRD.md for acceptance criteria.


## UAPI response envelope compatibility

The cPanel session probe accepts:
- documented UAPI JSON: `{ "result": { "status": 1, "data": ... } }`;
- direct result envelope: `{ "status": 1, "data": ... }`;
- legacy API 2 envelope: `{ "cpanelresult": { "event": { "result": 1 }, "data": ... } }`.

Diagnostics expose only response shape metadata (`topLevelKeys`, `resultKeys`, `dataType`), HTTP status, and redacted error details. They must not reveal mailbox addresses or session IDs. The Python provider normalizes these envelopes before listing or creating mailboxes.


## Unified mailbox and Google OAuth QA workflow

The Mailbox Manager is the single entry point:
1. Create exactly five owned-domain mailboxes.
2. Verify all five through cPanel UAPI.
3. Optionally reset those five mailboxes to the local shared QA password from
   `QA_MAILBOX_MASTER_PASSWORD` (never commit this value).
4. Only after five-of-five success, reveal a registration URL field and Google test
   account selector.
5. Inspect the authorized staging/local page and detect Google sign-in controls.
6. Open the page in the local Chromium profile for a human-supervised OAuth test.

The mailboxes are not Google Accounts by default. The owner must register each
address as a Google Account and add it to the Google OAuth consent-screen Test Users
list first. The browser flow does not automate Google account creation, credentials,
CAPTCHA, MFA, or consent.


## Google OAuth registration launcher

After five verified mailboxes are available and the owner confirms that the five
addresses correspond to real Google Accounts added as OAuth Test Users, the integrated
QA section accepts an authorized registration URL. Playwright inspects the page,
lists visible Google sign-in controls, and can click the selected detected control in
the local Chromium session. The user completes Google account selection, credentials,
consent, CAPTCHA and MFA manually. The target application's own OAuth callback must
validate the Google ID token and create/link the local application user. The launcher
does not create Google Accounts or infer that an email mailbox is a Google identity.

The public JagoFlutter login page currently presents Google-only login. The public
registration page also lists an email/password signup option. If email/password
registration exists but no email/password login route is implemented, that is a
separate JagoFlutter application feature and must be fixed in the JagoFlutter source
repository, not in SIMURU.


## Mailbox password and IMAP integration (current)

The primary real-mailbox flow is the local cPanel browser-session manager. It does not
use a cPanel API token. The password submitted to cPanel UAPI for each address is the
same password handed to the local Windows Credential Manager via keyring after UAPI
verification. IMAP reads that exact stored password. SMTP is optional and uses the
same stored credential.

The previous `MailboxProvisioner.password_for()` HMAC password derivation belongs
only to the separate legacy API-token provisioning path. Never use its derived value
to authenticate to mailboxes created by the browser-session manager.

Existing mailbox credentials can be imported from the one-time CSV into Windows
Credential Manager. Never save plaintext mailbox passwords in SQLite or GitHub.
