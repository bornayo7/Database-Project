# CS 4347 Car Dealership Database Project

A server-rendered Flask application with MySQL persistence for customers, vehicles, dealerships, employees, sales, service records and appointments. Includes SQL reports, CSV demonstration data, and database diagrams.

## Requirements

Python 3.12 or 3.13 and MySQL 8.4. Install the pinned runtime dependencies:

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

The app uses `create_app()` and performs no database changes at import or startup. Runtime dependencies are pinned in `requirements.txt`; tests add `requirements-dev.txt`.

## Initialize a new database

Create an empty database through MySQL Workbench or the MySQL client:

```sql
CREATE DATABASE cardealership CHARACTER SET utf8mb4;
```

Set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` in your shell. For initialization only, use a database administrator or account with CREATE/REFERENCES/INDEX permissions on this database. Then:

```sh
python manage.py init-db
# Optional: import all seven demonstration CSVs into the empty schema.
python manage.py import-demo
```

`schema.sql` is the only canonical initialization schema. Initialization refuses a database that already contains tables. Import refuses a target with entity data. Neither command drops tables, truncates data, disables foreign keys, or silently skips invalid rows. DDL initialization is not transactional in MySQL; after a failed initialization, use a new empty database or inspect the incomplete schema rather than importing into it.

Use a dedicated, password-protected application account for running the web app, not MySQL root. For example, create an account with your own strong password and grant only:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON cardealership.* TO 'dealership_app'@'localhost';
```

Create that account with `CREATE USER` first. Your MySQL administrator should choose the host entry appropriate for the application's actual connection. Running report definitions that create views additionally requires CREATE VIEW; do not grant it to the runtime account solely for the web UI.

## Configure authentication and run

There is one configured administrator, appropriate for a small coursework/portfolio app. Every data page and mutation requires login. Display modes such as `mode=view` are presentation choices, not permissions. There is no public demo account, password, or fallback signing key.

Example Windows PowerShell configuration:

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD_HASH = python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('Admin password: ')))"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
$env:DB_NAME = "cardealership"
$env:DB_USER = "dealership_app"
# Set DB_PASSWORD through your shell or secret manager. Do not commit it.
python InterfaceDatabase.py
```

On macOS/Linux, use `export NAME=value`; use `export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"` to generate the key. Keep the same secret across restarts and workers using a local secret store. Generating a new key invalidates all existing sessions. Password hashes containing `$` must be quoted when assigned manually in shells.

The local server listens at `http://127.0.0.1:5000`; set `PORT` to change it. `.env.example` lists supported names, but `.env` files are **not automatically loaded**. Export variables or configure your process manager explicitly. Never commit credentials, private customer data, or exported database backups.

For an HTTPS deployment, set `APP_ENV=production` to require Secure session cookies. Use a production WSGI server with `InterfaceDatabase:create_app()` and a configured HTTPS reverse proxy. Do not publish the Flask development server directly through ngrok. Apply login rate limiting at the reverse proxy and use a strong administrator password before exposing an instance. This is not a multiuser role-management system.

## Migrate an existing installation safely

The original repository mixed a snake_case `dealership_db` schema and a CamelCase `cardealership` app schema. Do not point the repaired app at those tables unchanged and do not run initialization over existing data.

1. Back up your database. Create a **new, empty target database**, such as `cardealership_v2`.
2. Set `DB_NAME=cardealership_v2` with credentials that can initialize the target and read the source. Run `python manage.py init-db`.
3. Run `python manage.py migrate-legacy --source dealership_db`, or use `--source cardealership` for the original application schema.
4. Compare counts, prices, sample records, and missing legacy relationships before switching the runtime account and app to the new target. Keep the source backup until verified.

The source connection is read-only and is never modified. Target data is copied in one transaction. An error rolls back all imported entity rows; the initialized target schema remains. Invalid foreign keys, duplicate sale VINs, invalid amounts and other constraint violations stop migration rather than silently deleting or fabricating records. Fix such source issues in a reviewed copy and retry into an empty target.

Existing primary IDs are preserved, and MySQL AUTO_INCREMENT then allocates subsequent IDs safely. Legacy zero loans become NULL (no loan). Missing listing prices and missing appointment customer/dealership relationships remain NULL and render safely. The app requires complete fields for new records without hiding incomplete legacy records.

Sales are authoritative during import: vehicles with sale records become `Sold`. Legacy sale reversals have no reliable pre-sale inventory status, so the UI requires an explicit Available/Reserved choice. For sales created by this version, the exact previous inventory status is stored and restored atomically on deletion. This model allows one current sale per VIN; reacquisition and multi-cycle resale history are not implemented. Deleting a sale is a reversal, not a general audit-history feature.

## Demonstration data and reports

The CSVs contain 2,000 customers, 2,000 vehicles, 200 employees, four dealerships, 2,000 sales, 2,000 service records and 2,000 appointments: 10,204 rows total. Every supplied VIN has a sale, so the corrected seeded inventory is entirely sold. Add a new available or reserved vehicle to demonstrate sale creation. The repair reconciles the 1,366 previously contradictory inventory statuses without removing any sales or other rows.

Legacy fixture employee job titles do not always match service duties. These are demonstration records, not validated business operating history. The UI therefore labels the linked record as an employee rather than claiming every historical service was performed by a mechanic.

Select your configured database before running `dealership_queries.sql`. It contains report queries and views, not another schema. Reports use canonical names, count each purchasing customer once for average credit score, and use NULL-safe anti-joins for employees with no sales. Inventory groups remain separate even when dealerships share a city.

The supporting-schema page reads actual columns and foreign keys from MySQL. `ER_Diagram.png` and `CarDealership.mwb` remain historical conceptual artifacts, not current migration definitions. The page no longer relies on external Drive permissions.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Unit tests exercise real Flask routes, authentication, CSRF, validation, template rendering, and cleanup. MySQL tests skip unless `MYSQL_TEST=1` is explicitly enabled. Use only a **disposable local/CI server** with test credentials and permission to create/drop schemas. Tests create uniquely named `dealership_test_*` schemas and remove only those schemas.

```sh
# On a disposable MySQL server only. Set the test DB_HOST/DB_PORT/DB_USER/DB_PASSWORD first.
MYSQL_TEST=1 python -m pytest -q
```

PowerShell: `$env:MYSQL_TEST="1"; python -m pytest -q`. Integration coverage includes full initialization/import, all create/read/delete workflows, NULLs, persisted state across app recreation, report correctness, rollback, concurrent ID allocation, double-selling races, exact VIN deletion, and non-destructive legacy migration. GitHub Actions runs these against MySQL 8.4. It does not connect to or migrate any deployed database.
