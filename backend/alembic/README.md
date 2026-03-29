# Alembic Workflow

This repository now uses Alembic for the legacy baseline plus all schema changes introduced in phase 2 and later.

## Upgrade any database

The baseline revision is defensive: it creates missing legacy tables when needed and skips tables that already exist. That means both fresh databases and existing local databases can use the same command:

```sh
alembic upgrade head
```

## Optional manual stamping

If you have already applied these revisions out-of-band and only need to align the version table, you can stamp directly:

```sh
alembic stamp 20260323_0002
```

## Create future migrations

```sh
alembic revision -m "describe change"
alembic upgrade head
alembic downgrade -1
```
