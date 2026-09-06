# Regression test environments

`python -m pytest -q` runs Flask unit/security tests without MySQL and explicitly skips database-dependent tests.

The CI workflow uses disposable MySQL 8.4 services with Python 3.12 and 3.13. Only uniquely named `dealership_test_*` databases created by the test fixtures are removed. Do not set `MYSQL_TEST=1` against a production server.

Python 3.13 CI also sets `RUN_BROWSER=1` and installs Playwright 1.57.0 plus its Chromium browser. The browser test follows real HTTP requests through Flask to MySQL. It checks login, creation without optional financing/phone fields, refresh persistence, confirmed deletion, logout, the seven creation forms, mobile table containment and JavaScript errors.

To enable the same browser test against your disposable MySQL server:

```sh
python -m pip install -r requirements-dev.txt playwright==1.57.0
python -m playwright install chromium
# Export the disposable DB_HOST, DB_PORT, DB_USER and DB_PASSWORD first.
MYSQL_TEST=1 RUN_BROWSER=1 python -m pytest -q
```

On PowerShell set `$env:MYSQL_TEST="1"` and `$env:RUN_BROWSER="1"` before running pytest. Browser dependencies are test-only and do not belong to the application runtime. Password hashes and signing keys in tests are deliberately test-only values, not deployment defaults.
