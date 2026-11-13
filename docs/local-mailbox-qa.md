# Local five-mailbox QA

The Streamlit dashboard can create **exactly five new mailboxes per click** on a domain
you control. Everything runs from the local Windows laptop. The mailbox provider call
uses cPanel UAPI `Email::add_pop`; credentials remain in the local `.env` file.

## How it works

1. Click **Create five mailboxes** in the Registration QA tab.
2. SIMURU generates a unique run suffix and five local parts:
   `qa-<run-suffix>-01` through `qa-<run-suffix>-05`.
3. The app calls cPanel UAPI over HTTPS and creates each mailbox with the configured quota.
4. Each mailbox receives a distinct deterministic password derived from
   `QA_MAILBOX_MASTER_PASSWORD` using HMAC-SHA256. The mailbox passwords are not
   persisted to SQLite or printed in the dashboard.
5. The five addresses are saved to the existing SQLite run history and can be exported.

The action creates mailboxes only. It does not submit registration forms to a website.

## cPanel setup

Create a cPanel API token and use the server hostname shown by your hosting provider.
The API token needs permission to manage email accounts. cPanel documents the
authorization header as `Authorization: cpanel USERNAME:APITOKEN` and the endpoint
as `/execute/Email/add_pop`.

If **Manage API Tokens** is missing from your cPanel menu, ask your hosting provider
to enable the feature or provide the correct supported account-level API access.
Do not copy browser `cpsess` URLs, cookies, or session IDs into the application.

## Local configuration

Copy `.env.example` to `.env`, then set:

- `QA_MAIL_DOMAIN=teguhharits.com`
- `QA_MAIL_PREFIX=qa`
- `QA_CPANEL_HOST`: cPanel server hostname, without `https://` or a port.
- `QA_CPANEL_USERNAME`: cPanel account username.
- `QA_CPANEL_API_TOKEN`: API token, stored locally only.
- `QA_MAILBOX_MASTER_PASSWORD`: a long random secret of at least 24 characters.
- `QA_MAILBOX_QUOTA_MB`: quota for each new mailbox.
- `QA_IMAP_HOST`, `QA_IMAP_PORT`, `QA_SMTP_HOST`, `QA_SMTP_PORT`: copy the exact
  secure settings from cPanel's **Connect Devices** screen.

Each mailbox password is derived from the master secret plus its complete email address.
Keep the master secret safe: without it, the app cannot log in to the created mailboxes.
Changing it later will change the derived passwords and will not update existing mailbox
passwords automatically.

## Run on Windows

```powershell
Copy-Item .env.example .env
# Edit .env and fill the cPanel values
uv sync --extra dev
uv run streamlit run app.py
```

Open **Registration QA** and click **Create five mailboxes**. Every click creates five
new mailboxes with a new run suffix. Avoid clicking repeatedly unless you intend to
create another five.

## OTP retrieval

`ImapOTPReader` can read fresh unseen messages from one generated mailbox. It requires:
- a recipient address on `QA_MAIL_DOMAIN` with the configured `QA_MAIL_PREFIX`;
- a sender matching `QA_OTP_ALLOWED_SENDERS`;
- a subject containing one of `QA_OTP_SUBJECT_KEYWORDS`;
- a message date newer than the requested cutoff.

Configure the exact sender and subject format from your own staging app. The reader
does not bypass CAPTCHA or access controls and is not wired to submit external
registration forms in this change.
