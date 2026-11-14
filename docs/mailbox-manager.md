# Mailbox Manager (local cPanel browser session)

This tab opens a visible Chromium profile on the user's laptop. The user signs in to
their own Rumahweb cPanel manually. SIMURU does not ask for, read, print, or store the
cPanel password, session cookie, or `cpsess` token.

After login, the **Create 5 New Emails** action calls same-origin cPanel UAPI
`Email/list_pops` and `Email/add_pop` using the browser's active session. It creates
five unique addresses on the configured domain, then verifies them with another
`list_pops` request.

## Run locally

```powershell
uv sync --extra dev
uv run playwright install chromium
uv run streamlit run app.py
```

Open **List email**, click **Connect cPanel**, then finish login manually in the opened
Chromium window. Click **Refresh email list** in the Domain inbox to load all addresses.
After signing in, use **Check cPanel session** first; the refresh action appears only
after UAPI confirms the session.
The list and inbox are never polled automatically. After a successful mailbox-creation
flow, refresh the list manually to display the new addresses. Newly created addresses
from the latest app flow appear first; other addresses retain cPanel's returned order.
For QA mailbox creation, open **Mailbox management**; cPanel status is checked when
the view renders, without a periodic polling timer.

The persistent browser profile is stored under `data/cpanel-browser-profile`.
It contains the authenticated browser session and must remain local. Do not commit
that directory, upload it, or share it. The five generated mailbox passwords are
shown once in the dashboard; download the CSV and store it securely.


## Domain-wide read-only inbox

The **Domain inbox** view displays a three-pane email workspace: all addresses
returned by cPanel, the selected mailbox's inbox, and the selected message body.
After signing in, click **Check cPanel session**, then **Refresh email list**. Select
an address to make one initial inbox connection attempt when a configured password is
available. Use **Load inbox** or **Refresh inbox** for later manual loads and refreshes;
there is no background polling. The address list shows 6 mailboxes per page with
numbered pagination. Selecting
a message displays its plain-text contents.
`QA_MAILBOX_MASTER_PASSWORD` is used as the default password and is tried automatically.
If it is absent or rejected, enter a mailbox password under **Mailbox login** and choose
**Connect / retry**. Passwords entered in this view are kept only in the active
Streamlit session and are not saved to Windows Credential Manager. If IMAP rejects the
password, confirm it is the mailbox password, not the cPanel password. Long addresses
are shortened in the list; expand **Full address** on a row to see it in full.
Any mailbox on the configured domain can be selected, not only the `qa-` test addresses.

Select **Mailbox management** to access the five-mailbox QA creation, credential
import, and OTP tools. Website Automation and Team Accounts are not available in the
current dashboard.
The Registration QA page can also create a five-mailbox batch and run local auth checks
using those addresses. This path requires `QA_MAILBOX_MASTER_PASSWORD`, does not persist
mailbox passwords to Windows Credential Manager, and keeps email/SMS OTP verification
inside the local test outbox.
The OTP mailbox picker uses a theme-matched autocomplete with removable email chips.
Select options with Enter, Tab, or a comma; each selection clears the search field.
IMAP checks and OTP waits run for all selected mailboxes, concurrently for OTP waits.

Set `QA_IMAP_HOST` and `QA_IMAP_PORT` to the IMAP values shown by cPanel under
**Connect Devices** (normally port `993` for IMAP over SSL). A POP host or port is
not interchangeable with IMAP. The panel connects directly to the configured IMAP
server, opens `INBOX` read-only, and fetches messages with `BODY.PEEK`; it does not
mark them as read, store them in the project database, or forward them to Gmail.
Search filters the loaded sender, subject, and date locally. Message bodies are
displayed as plain text; active HTML and attachments are not rendered.


## Session status

While **Mailbox management** is open, cPanel status is read on normal page renders.
Mailbox creation stays disabled until UAPI confirms the session. No background
refresh timer is used.
