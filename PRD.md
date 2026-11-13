# Product Requirements Document (PRD) — SIMURU Research

- **Status:** Living document / in development
- **Version:** 0.6 draft
- **Platform:** Local Windows desktop workflow
- **Primary users:** Project owner and authorized development/QA collaborators
- **Repository:** https://github.com/teguhdev97/simuru-research

## 1. Problem statement

The project owner needs one local dashboard to manage research and QA workflows without repeatedly editing source code or configuration files. The current experience has two important friction points:

1. The cPanel page can visibly show an authenticated Tools screen while SIMURU reports that the cPanel session is not authenticated. The application needs reliable UAPI-based session diagnostics across browser tabs.
2. Website form selectors currently require manual CSS entry. The dashboard should discover visible form controls and prefill selectors automatically.

The project also needs durable product and engineering documentation so another developer or AI coding agent can collaborate without relying on chat history.

## 2. Product vision

SIMURU Research is a local-first, configurable QA workbench. Users configure targets through the dashboard, inspect forms, connect owned infrastructure, run bounded authorized tests, and review reproducible results.

## 3. Goals

- Reliable cPanel browser-session detection with actionable diagnostics.
- A safe, explicit mailbox creation workflow for a domain the operator controls.
- Visual website profile management.
- Automatic read-only form inspection and selector suggestions.
- Official OAuth configuration/testing support for applications the operator owns.
- Local persistence and export of QA results.
- Clear handoff documentation for contributors and AI coding agents.

## 4. Non-goals

- Bulk creation of Google Accounts or other third-party identities.
- Bypassing CAPTCHA, MFA, anti-bot systems, provider limits, or security controls.
- Creating accounts on websites without ownership or explicit authorization.
- Storing cPanel passwords, raw session IDs, OAuth client secrets, or mailbox passwords in source control.
- Public deployment as part of this local-laptop milestone.
- Replacing Google Auth Platform or the target application's own OAuth client configuration.

## 5. User journeys

### 5.1 Connect and inspect cPanel session

1. User opens Mailbox Manager.
2. User clicks Connect cPanel.
3. SIMURU opens or attaches to its persistent local Chromium profile.
4. User signs into their own cPanel manually.
5. User returns to Streamlit.
6. SIMURU polls UAPI on all matching cPanel tabs every three seconds.
7. Dashboard reports verified UAPI access or a precise, redacted reason without requiring manual refresh.

**Acceptance criteria**
- The check does not require creating a mailbox.
- It checks all tabs matching the configured cPanel host.
- It accepts numeric or string UAPI status value 1.
- It distinguishes no browser/tab, missing session path, HTTP failure, redirect, non-JSON response, and UAPI application error.
- Diagnostics never reveal the cpsess value, cookies, or credentials.
- If one tab is authenticated, that exact tab is used by later mailbox operations.

### 5.2 Create mailbox batch

1. User waits until the automatic cPanel UAPI session check succeeds.
2. User reviews the domain, prefix, and mailbox quota.
3. User clicks Create 5 New Emails.
4. SIMURU creates exactly five unique mailboxes using cPanel UAPI.
5. SIMURU lists mailboxes again and verifies each created address.
6. Credentials and any partial failures are displayed for secure export/review.

**Acceptance criteria**
- Creation is disabled until UAPI authentication is confirmed.
- Existing addresses are not overwritten.
- A partial failure reports how many mailboxes were created and does not claim full success.
- Generated passwords are unique and cryptographically random.
- Credentials are not written to logs or persistent run history.
- The operation is bounded by a configurable maximum.
- The current action creates exactly five mailboxes; the UI must not expose a larger batch size.

### 5.3 Close cPanel session

1. User clicks Close cPanel browser.
2. SIMURU attempts cPanel's supported logout route.
3. SIMURU clears local browser-context cookies and closes Chromium.
4. Dashboard reports whether server-side logout was confirmed or only local cleanup completed.

**Acceptance criteria**
- Browser closure always occurs even if logout navigation fails.
- The UI must not claim server logout succeeded unless it can verify the logged-out state.
- Session IDs remain redacted.
- The user is advised to re-authenticate if logout could not be confirmed.

### 5.4 Configure a website visually

1. User creates or selects a website profile.
2. User enters base URL and registration path.
3. User selects authentication type.
4. User clicks Inspect Website & Auto-detect Selectors.
5. Playwright reads visible fields and buttons without submitting.
6. Dashboard displays labels, types, and selector suggestions.
7. User reviews and saves the profile.

**Acceptance criteria**
- Remote URLs require HTTPS; localhost may use HTTP.
- Inspector does not submit forms, click login controls, or enter credentials.
- Selector suggestions are unique within the inspected document where possible.
- Google sign-in buttons are detected as metadata only.
- Inspection failures explain whether the page was inaccessible, timed out, or had no recognizable controls.
- User can edit suggested selectors before saving.

### 5.5 Google OAuth test-user preparation

1. The dashboard reveals this step only after exactly five mailbox addresses are created and verified.
2. The user confirms each mailbox can receive email.
3. The owner creates or links each mailbox address to a Google Account manually using Google's existing-email signup flow.
4. The owner manually adds those Google Accounts under Google Auth Platform → Audience → Test users.
5. SIMURU stores the project name, Client ID, redirect URI, and five email addresses locally; it never stores a Client Secret.

**Acceptance criteria**
- The panel is hidden when fewer than five mailboxes are verified.
- It provides a downloadable list of the five email addresses.
- It clearly explains that a mailbox is not automatically a Google Account.
- It never automates Google Account creation or circumvents CAPTCHA, MFA, or account protections.
- It never stores OAuth Client Secret.

### 5.6 OAuth QA for an owned application

1. User configures the application's own Google OAuth client in Google Auth Platform.
2. User configures authorized redirect URIs and test users.
3. SIMURU stores only non-secret metadata in website profiles.
4. OAuth secrets remain in local secret storage or environment variables.
5. User starts an authorized test and completes provider consent/security prompts normally.
6. Application callback validates tokens according to Google's official guidance.

**Acceptance criteria**
- No Google Account creation automation.
- No CAPTCHA/MFA bypass or browser stealth.
- OAuth callback/redirect URI must match the application configuration.
- Client secrets are never displayed in logs or committed.
- OAuth flow is tested only on an application owned by the user or explicitly authorized for QA.

## 6. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Dashboard provides visual website profile management | P0 |
| FR-002 | Playwright detects visible form controls and suggests selectors | P0 |
| FR-003 | cPanel manager attaches to local persistent Chromium through CDP | P0 |
| FR-004 | cPanel session check probes all matching tabs | P0 |
| FR-005 | UAPI diagnostics distinguish transport, redirect, JSON, and API errors | P0 |
| FR-006 | Diagnostics redact cPanel session identifiers | P0 |
| FR-007 | Mailbox creation is gated on successful UAPI authentication | P0 |
| FR-008 | Mailbox results are verified with a follow-up list operation | P0 |
| FR-009 | cPanel close action attempts logout and always closes local browser | P1 |
| FR-010 | Website profiles persist locally | P0 |
| FR-011 | OAuth QA configuration supports owned applications | P1 |
| FR-012 | QA run history and CSV export | P1 |
| FR-013 | Project and PRD documents stay current | P0 |
| FR-014 | Session status automatically refreshes while the Mailbox Manager is open | P0 |
| FR-015 | Create exactly five mailboxes and verify all five before revealing Google OAuth preparation | P0 |

## 7. Non-functional requirements

- **Security:** secrets and session identifiers must not enter Git, logs, diagnostic UI, or SQLite.
- **Privacy:** browser profiles and data remain local and are ignored by Git.
- **Reliability:** all browser operations have explicit timeouts and actionable errors.
- **Maintainability:** provider logic is separated from Streamlit UI.
- **Testability:** external cPanel responses are mocked in unit tests; no live mailbox creation in CI.
- **Usability:** primary workflows require dashboard controls, not manual JSON editing.
- **Portability:** Windows 10/11 and Python 3.12+ are supported.
- **Bounded execution:** all resource-creating batches have a hard upper limit and explicit confirmation.

## 8. Technical design

### Stack

- Python 3.12+
- Streamlit
- Playwright
- FastAPI
- SQLite
- pandas
- uv

### cPanel session probe

The session probe should:
1. Discover tabs for the configured cPanel host and port.
2. Read each tab's current origin and path.
3. Extract the session prefix only in memory.
4. Call /execute/Email/list_pops?domain=... with same-origin credentials.
5. Parse response text as JSON defensively.
6. Normalize UAPI status with str(status) == "1".
7. Detect redirects and login HTML.
8. Return safe diagnostics with all session prefixes redacted.
9. Select the page that actually passed the probe.

Never use a URL copied from user screenshots as a static session endpoint.

## 9. Error handling and observability

Every failed cPanel check should report:
- whether CDP is reachable;
- whether a cPanel tab was found;
- whether the session path exists (without exposing its value);
- UAPI HTTP status;
- whether the response redirected;
- whether JSON parsing succeeded;
- UAPI status and safe error messages.

Never expose:
- raw cpsess values;
- cookies;
- passwords;
- API tokens;
- Google client secrets;
- mailbox passwords.

## 10. Milestones

### M0 — Stabilize cPanel connection
- [x] Add cPanel browser-session mode.
- [x] Add UAPI session check.
- [x] Auto-refresh session status every three seconds and show detailed UAPI diagnostics.
- [ ] Verify session check on Rumahweb account.
- [ ] Add mocked tests for UAPI response cases.
- [ ] Confirm server-side logout behavior.

### M1 — Visual website configuration
- [x] Website profile editor.
- [x] Read-only selector auto-detection.
- [ ] Interactive click-to-pick selector UI.
- [ ] Add iframe-aware inspection.

### M2 — Mailbox workflow
- [x] Create exactly five mailboxes through cPanel UAPI and gate OAuth preparation on five-of-five verification.
- [x] Verify created addresses with list operation.
- [ ] Add batch-size control and hard cap.
- [ ] Add IMAP connectivity test.
- [ ] Add sender allowlist and OTP parser for owned test mailboxes, with strict TTL and no third-party OTP interception.

### M3 — Owned-app OAuth QA
- [ ] Add OAuth settings UI for an application the user owns.
- [ ] Validate redirect URI and callback configuration.
- [ ] Add official Google OAuth test flow.
- [ ] Add token validation tests and secret handling.

### M4 — Quality and collaboration
- [ ] Add CI for pytest and Ruff.
- [ ] Add setup and troubleshooting docs.
- [ ] Keep Project.md and PRD.md updated.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| cPanel login page visible but UAPI is not authenticated | Probe UAPI, not just page title or URL |
| Multiple cPanel tabs with different sessions | Probe every matching tab and choose the one that succeeds |
| Streamlit rerun loses Playwright client | Reattach to independent Chromium CDP process on each run |
| Session ID leaks through logs | Redact all session prefixes before rendering diagnostics |
| Partial mailbox creation | Verify each address and report partial success precisely |
| Provider security challenge | Stop and require owner interaction; never bypass |
| OAuth secret leaks | Keep secret out of profiles, logs, SQLite, and Git |
| External website testing without permission | Require explicit ownership/authorization and constrain target scope |

## 12. Definition of done

A feature is complete only when:
- implementation and UI behavior match this PRD;
- unit tests cover expected success and failure paths;
- Ruff and pytest pass, or unrun checks are clearly reported;
- secrets and session IDs are redacted;
- docs are updated;
- no external resource-creating action is claimed tested unless it was actually exercised in an authorized environment.


### M3 — Google OAuth test-user preparation
- [x] Reveal the preparation panel only after a verified five-mailbox batch.
- [x] Export the five email addresses for Google Auth Platform Test Users.
- [x] Save non-secret OAuth metadata locally.
- [ ] Verify each mailbox as a Google Account manually.
- [ ] Add the five Google Accounts under Audience → Test users.
- [ ] Implement and test the OAuth callback in the owned application.


### UAPI envelope compatibility

The UAPI parser must support the documented nested `result.status` object and direct root-level `status/data/errors` responses. A legacy `cpanelresult.event.result` envelope may be recognized for diagnosis, but new requests continue to use UAPI. Session diagnostics include only structural keys and redacted errors; never dump raw response bodies, email account lists, or session URLs.
