#!/usr/bin/env bash
# dev helper: truncate all tables (keeps schema + alembic_version)
set -euo pipefail
psql "$1" -Atc "select string_agg(quote_ident(tablename), ', ') from pg_tables where schemaname='public' and tablename<>'alembic_version'" | xargs -I{} psql "$1" -c "TRUNCATE {} CASCADE;"
