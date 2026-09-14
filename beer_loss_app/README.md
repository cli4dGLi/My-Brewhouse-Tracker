# Beer Loss Operations

A password-protected Streamlit app for brewery logs and shift, day, WTD, MTD and YTD summaries. PostgreSQL stores live records independently of the Streamlit app server.

## Deploy to Streamlit Community Cloud

- Repository: `cli4dGLi/My-Brewhouse-Tracker`
- Branch: `beer-loss-public`
- Main file: `beer_loss_app/streamlit_app.py`
- Python: **3.12**
- GitHub URL: https://github.com/cli4dGLi/My-Brewhouse-Tracker/blob/beer-loss-public/beer_loss_app/streamlit_app.py

The repository is public. **All live app pages require the application password**, including dashboards, logs, downloads and administration. Public hosting is not anonymous access to the records.

In **Advanced settings → Secrets**, enter your private values:

~~~toml
APP_MODE = "live"
APP_PASSWORD = "REPLACE-WITH-A-UNIQUE-PRIVATE-PASSWORD-16-CHARS-MINIMUM"
DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require"
ADMIN_PIN = "REPLACE-WITH-A-DIFFERENT-LONG-PRIVATE-ADMIN-PIN"
LOG_PIN = ""
~~~

Use a unique, randomly generated application password of at least 16 characters and a different administrator passphrase. Share the application password only with approved staff. Keep the administrator PIN with administrators. A blank LOG_PIN allows **signed-in** staff to log entries; it never bypasses the application login.

Secrets belong only in Streamlit settings, never in GitHub, screenshots or chat. Keep the uploaded production workbook and database backups out of this public repository.

Live mode fails closed without a valid application password, encrypted PostgreSQL connection and administrator PIN. It never falls back to local storage. The app creates its table on first connection; controlled provisioning can initialise SQLAlchemy metadata using a direct connection before using the pooled application connection.

Official instructions: [Deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Login behaviour and limits

- Password fields mask typing. Submitted login passwords are removed from session state after checking.
- Sign out clears authentication, administrator credentials and unsaved form state.
- Access expires after 30 minutes without interaction, or 12 hours after sign-in. Expiry is enforced on the next interaction; a rendered page cannot be recalled from a user's screen.
- Changing APP_PASSWORD invalidates existing sessions on their next interaction. A server restart requires sign-in again.
- A server-wide limit allows ten sign-in attempts per minute across browser sessions. This in-memory limit resets on restart and is not a distributed abuse-prevention service.
- This is shared-password access, not named accounts, MFA or individual role-based identity. Entered operator/reviewer names remain self-reported.

## Historical data and reporting

The attached Beer Loss Calculator workbook is the only initial data source. No production workbook records are embedded in the code or seeded at deployment. Historical migration is pending validation. Missing gravity, shifts, fill references and stock measurements must be reviewed rather than invented. **Historical summaries are incomplete until the relevant historical records have been imported and validated.**

The current version supports fresh entry, retained corrections, full JSON history exports and restore into an empty database. It does not yet include automatic Excel import. See [Guide](docs/Guide.md) for calculations and operating assumptions.

## Retention and recovery

- No automatic expiry or permanent-delete function for production records.
- Corrections retain the old entry's original payload, reviewer, reason and timestamp.
- Transactional writes and duplicate prevention.
- Full JSON backups cover both breweries and active plus voided entries.
- Restore cannot overwrite an existing database.
- Database-provider limits, account availability and backup policies still apply. Persistent storage does not guarantee protection against every form of data loss.
- Provider recovery and independent scheduled backups must be configured and verified before relying on the app as the sole record.

## Before production use

1. Confirm shift boundaries, material factors and operating targets.
2. Validate the workbook migration and missing readings.
3. Save a labelled test entry, confirm it from another browser, reboot Streamlit and confirm it remains.
4. Void the test entry and check its retained audit history.
5. Configure and test backups. Confirm costs before enabling paid options.

## Local demonstration

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
APP_MODE=demo streamlit run streamlit_app.py
~~~

Run from `beer_loss_app`. Demo mode bypasses login and uses a separate temporary SQLite database per session. It never connects to the live database and contains no seeded production records. Do not deploy production with APP_MODE=demo.

## Tests

~~~bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
~~~

The PostgreSQL integration test uses TEST_DATABASE_URL and creates/removes its own disposable schema. Use a dedicated test database, never production. CI uses an isolated PostgreSQL test service without production credentials.
