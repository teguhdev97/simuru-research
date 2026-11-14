# Product Requirements Document (PRD) — SIMURU Research

- **Status:** Living document / in development
- **Version:** 0.6 draft
- **Platform:** Local Windows desktop workflow
- **Primary users:** Project owner and authorized development/QA collaborators
- **Repository:** https://github.com/teguhdev97/simuru-research

## 1. Problem statement

The project owner needs one local dashboard to manage mailbox and QA workflows without repeatedly editing source code or configuration files. The current experience has one important friction point:

1. The cPanel page can visibly show an authenticated Tools screen while SIMURU reports that the cPanel session is not authenticated. The application needs reliable UAPI-based session diagnostics across browser tabs.

The project also needs durable product and engineering documentation so another developer or AI coding agent can collaborate without relying on chat history.

## 2. Product vision

SIMURU Research is a local-first mailbox and QA workbench. Users connect owned infrastructure, run bounded local tests, and review reproducible results.

## 3. Goals

- Reliable cPanel browser-session detection with actionable diagnostics.
- A safe, explicit mailbox creation workflow for a domain the operator controls.
- A simple dashboard for domain email and local QA.
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

1. User opens List email.
2. User clicks Connect cPanel.
3. SIMURU opens or attaches to its persistent local Chromium profile.
4. User signs into their own cPanel manually.
5. User returns to Streamlit.
6. User checks the cPanel session; SIMURU probes matching cPanel tabs through UAPI.
7. Dashboard reports verified UAPI access or a precise, redacted reason.

**Acceptance criteria**
- The check does not require creating a mailbox.
- It checks all tabs matching the configured cPanel host.
- It accepts numeric or string UAPI status value 1.
- It distinguishes no browser/tab, missing session path, HTTP failure, redirect, non-JSON response, and UAPI application error.
- Diagnostics never reveal the cpsess value, cookies, or credentials.
- If one tab is authenticated, that exact tab is used by later mailbox operations.
- Inbox contents and mailbox lists are refreshed only after a user action.

### 5.2 Create mailbox batch

1. User checks that the cPanel UAPI session is ready.
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

## 6. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-003 | cPanel manager attaches to local persistent Chromium through CDP | P0 |
| FR-004 | cPanel session check probes all matching tabs | P0 |
| FR-005 | UAPI diagnostics distinguish transport, redirect, JSON, and API errors | P0 |
| FR-006 | Diagnostics redact cPanel session identifiers | P0 |
| FR-007 | Mailbox creation is gated on successful UAPI authentication | P0 |
| FR-008 | Mailbox results are verified with a follow-up list operation | P0 |
| FR-009 | cPanel close action attempts logout and always closes local browser | P1 |
| FR-012 | QA run history and CSV export | P1 |
| FR-013 | Project and PRD documents stay current | P0 |
| FR-014 | Inbox refresh is user initiated; no periodic inbox polling | P0 |
| FR-015 | Create exactly five mailboxes and verify all five before reporting success | P0 |

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

### M0 — cPanel connection and mailbox safety
- [x] Add cPanel browser-session mode and UAPI session checks.
- [x] Verify mailbox creation with a follow-up list operation.
- [x] Keep inbox loading manual and avoid periodic inbox polling.
- [ ] Verify session behavior on the configured cPanel account.
- [ ] Confirm server-side logout behavior.

### M1 — Mailbox dashboard
- [x] Display the domain mailbox list, selected inbox, and message details.
- [x] Use six-item numbered pagination on mailbox and latest-run tables.
- [x] Use the configured master password as an automatic inbox login default.
- [x] Provide a collapsed per-address disclosure for long mailbox names.
- [ ] Continue improving responsive layout and accessibility.

### M2 — Quality and collaboration
- [ ] Add CI for pytest and Ruff.
- [ ] Keep setup, troubleshooting, and project documentation current.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| cPanel login page visible but UAPI is not authenticated | Probe UAPI, not just page title or URL |
| Multiple cPanel tabs with different sessions | Probe every matching tab and choose the one that succeeds |
| Streamlit rerun loses Playwright client | Reattach to independent Chromium CDP process on each run |
| Session ID leaks through logs | Redact all session prefixes before rendering diagnostics |
| Partial mailbox creation | Verify each address and report partial success precisely |
| Provider security challenge | Stop and require owner interaction; never bypass |
| Incorrect IMAP password | Distinguish mailbox credentials from cPanel credentials and surface authentication errors |

## 12. Definition of done

A feature is complete only when:
- implementation and UI behavior match this PRD;
- unit tests cover expected success and failure paths;
- Ruff and pytest pass, or unrun checks are clearly reported;
- secrets and session IDs are redacted;
- docs are updated;
- no external resource-creating action is claimed tested unless it was actually exercised in an authorized environment.

### UAPI envelope compatibility

The UAPI parser supports nested `result.status` and direct root-level `status/data/errors`
responses. Session diagnostics include only structural keys and redacted errors; never
dump raw response bodies, email account lists, or session URLs.

### Mailbox credential handling and IMAP

- `QA_MAILBOX_MASTER_PASSWORD` is the default inbox password; entered alternatives remain in the active app session and are not saved to the OS credential manager.
- Passwords are never stored in SQLite, logs, Markdown, or Git.
- IMAP access reads the selected mailbox using its configured or temporary password.
- OTP polling is bounded, checks only unseen messages after a cutoff, and uses the configured sender and subject filters.
- The browser-session cPanel flow does not require `QA_CPANEL_API_TOKEN`.
