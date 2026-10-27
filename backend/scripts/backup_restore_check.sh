#!/usr/bin/env bash
# Dump the configured database, restore it into a temporary database, and verify
# that the application schema and row counts survived.
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be set (for example: source backend/.env)." >&2
  exit 1
fi

DB_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"
TEMP_DB="sthalo_restore_check_$(date +%s)_$$"
WORK_DIR="$(mktemp -d /tmp/sthalo-restore-XXXXXX)"
DUMP_FILE="$WORK_DIR/sthalo.dump"

cleanup() {
  psql "$DB_URL" -v ON_ERROR_STOP=0 -c "DROP DATABASE IF EXISTS \"$TEMP_DB\" WITH (FORCE);" >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

echo "Dumping the sthalo application schema..."
pg_dump --schema=sthalo --format=custom --no-owner --no-acl "$DB_URL" > "$DUMP_FILE"

echo "Preparing auth ID mapping and extensions in $TEMP_DB..."
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$TEMP_DB\";" >/dev/null
TEMP_URL="${DB_URL%/*}/$TEMP_DB"
psql "$DB_URL" -At -F $'\t' -c "SELECT id, coalesce(email, '') FROM auth.users" > "$WORK_DIR/auth_users.tsv"
psql "$TEMP_URL" -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS postgis SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS btree_gist SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA extensions;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY, email text);
SQL
psql "$TEMP_URL" -v ON_ERROR_STOP=1 -c "COPY auth.users (id, email) FROM STDIN" < "$WORK_DIR/auth_users.tsv" >/dev/null

echo "Restoring application data..."
pg_restore --exit-on-error --no-owner --no-acl --dbname="$TEMP_URL" "$DUMP_FILE"

SOURCE_USERS="$(psql "$DB_URL" -Atc "SELECT count(*) FROM sthalo.users")"
RESTORED_USERS="$(psql "$TEMP_URL" -Atc "SELECT count(*) FROM sthalo.users")"
RESTORED_MIGRATION="$(psql "$TEMP_URL" -Atc "SELECT version_num FROM sthalo.alembic_version")"
RESTORED_TABLES="$(psql "$TEMP_URL" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname = 'sthalo'")"

if [[ "$SOURCE_USERS" != "$RESTORED_USERS" ]]; then
  echo "User count mismatch: source=$SOURCE_USERS restored=$RESTORED_USERS" >&2
  exit 1
fi

echo "Restore verified: users=$RESTORED_USERS migration=$RESTORED_MIGRATION sthalo_tables=$RESTORED_TABLES"
