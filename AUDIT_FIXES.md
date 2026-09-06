# Audit repair traceability

Repairs target the independent audit of commit `9d16f6d6e3a3d897210fa4cc805b7f87223f7516`. Validation commands and results are recorded in GitHub Actions, not inferred from static analysis.

| Finding | Implementation | Regression coverage |
|---|---|---|
| DB-01 schema mismatch | Canonical `schema.sql`, canonical report names, explicit initialization and non-destructive legacy migration | Empty initialization, complete CSV import, legacy copy, all read routes and reports on MySQL |
| DB-02 tuple indexing | Database-generated IDs, dictionary cursors, one shared connection boundary | Every create endpoint persists on MySQL |
| DB-03 no access control | Configured administrator login, hashed password, server-side gate on all data routes | Anonymous access, login/logout, protected mutations |
| DB-04 inventory drift | Row-locked sale transaction, unique sale VIN, saved pre-sale status, explicit legacy reversal choice, reconciled CSVs | Concurrent sale race, create/reverse cycle, rollback injection, all fixture VINs |
| DB-05 GET deletion | POST-only deletion and CSRF tokens | GET/HEAD rejection and invalid-token rejection for all entities |
| DB-06 NULL loan crash | NULL-safe numeric filters and legacy-preserving joins | NULL customer rendering and all list pages with legacy NULL values |
| DB-07 optional fields blocked | Optional loan and phone fields agree with server validation | Form requirements and blank optional customer insertion |
| DB-08 ignored primary IDs | Remove primary ID inputs; MySQL owns allocation | All forms and creation tests with an ignored extraneous legacy ID |
| DB-09 ID race | AUTO_INCREMENT, no MAX-plus-one allocator | Concurrent customer creation |
| DB-10 stock includes sold | Only Available and Reserved count as current stock | Sold exclusion and zero-stock dealership |
| DB-11 purchase-weighted credit average | EXISTS-based customer eligibility | Repeat-buyer average remains customer-weighted |
| DB-12 NULL-sensitive anti-join | Correlated NOT EXISTS | NULL salesperson transaction does not hide non-sellers |
| DB-13 wrong VIN deletion | VIN transported in POST body, not concatenated into a URL | Prefix-collision cases with #, ?, / and quote identifiers |
| DB-14 false delete success | Affected-row checks, 404 for missing records | Repeated and nonexistent deletions |
| DB-15 public signing key | Required environment-supplied secret, no default | Fail-closed configuration and no source literal |

Additional corrections: listing prices are collected and displayed; server-side numeric/date/domain validation runs before SQL; failures roll back and close resources; errors are sanitized; lists are paginated; forms retain rejected input; labels and mobile viewport are present; schema documentation comes from the connected database rather than a duplicated Python model; external Drive embeds are no longer required.

No live database is migrated automatically. Refer to README before upgrading an existing installation. The application still represents a small single-administrator project, not an enterprise authorization or immutable accounting system. Legacy diagrams remain labeled historical references. Deployment-specific TLS, proxy rate limiting, backups and secret provisioning must be configured by the operator.
