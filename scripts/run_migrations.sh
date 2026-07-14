#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres to be ready and then apply the init-postgres.sql script
echo "Waiting for Postgres to be ready..."
until docker-compose exec -T postgres pg_isready -U postgres -d claim2car_db >/dev/null 2>&1; do
  echo "Postgres is starting... sleeping 1s"
  sleep 1
done

echo "Applying init-postgres.sql"
docker-compose exec -T postgres psql -U postgres -d claim2car_db -f /docker-entrypoint-initdb.d/init-postgres.sql

echo "Migrations applied."
