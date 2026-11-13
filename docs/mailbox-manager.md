# Mailbox Manager (local cPanel browser session)

This tab opens a visible Chromium profile on the user's laptop. The user signs in to
their own Rumahweb cPanel manually. SIMURU does not ask for, read, print, or store the
cPanel password, session cookie, or `cpsess` token.

After login, the **Create 8 New Emails** action calls same-origin cPanel UAPI
`Email/list_pops` and `Email/add_pop` using the browser's active session. It creates
eight unique addresses on the configured domain, then verifies them with another
`list_pops` request.

## Run locally

```powershell
uv sync --extra dev
uv run playwright install chromium
uv run streamlit run app.py
```

Open **Mailbox Manager**, click **Connect cPanel**, finish login manually in the
opened Chromium window, return to Streamlit, then click **Create 8 New Emails**.

The persistent browser profile is stored under `data/cpanel-browser-profile`.
It contains the authenticated browser session and must remain local. Do not commit
that directory, upload it, or share it. The eight generated mailbox passwords are
shown once in the dashboard; download the CSV and store it securely.
