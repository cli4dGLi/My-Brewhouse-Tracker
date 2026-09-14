# Verification and deployment status

Checked on 14 September 2026.

## Local checks

32 tests passed on Python 3.12. The PostgreSQL integration test was skipped when TEST_DATABASE_URL was absent. A separate attempt to reach Neon's PostgreSQL endpoint from this workspace failed at DNS resolution, before any SQL ran.

Login checks cover anonymous access blocking, missing/weak configuration, incorrect and Unicode passwords, login and logout, removal of session credentials, idle/absolute expiry, password rotation, and cross-session attempt limiting.

Core checks cover calculations, reporting boundaries, site separation, missing measurements, duplicate prevention, voided history, backups, fills and Streamlit forms.

## Continuous integration

[Run 34897159549](https://github.com/cli4dGLi/My-Brewhouse-Tracker/actions/runs/34897159549) passed all **33 tests** on Python 3.12 with an isolated PostgreSQL 16 service. Tested application-code commit: `1503a864ef70e358b3d07d427c9b7d8d8bd7a9d4`. Its test records and credentials were synthetic.

The initial schema was then applied successfully through the Neon connection on an isolated check branch and on the dedicated production database. Both contain zero production records. The live Streamlit-to-database connection still needs verification after deployment.

## Deployment checks still required

- Final Streamlit sign-in, secret configuration, deployment and verified public URL.
- End-to-end live storage, cross-browser visibility and reboot retention.
- Validated migration of the attached historical Excel workbook.
- Provider recovery and independent backup schedule verification.

No production rows or credentials are included in the public source.
