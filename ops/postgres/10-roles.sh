#!/bin/sh
set -eu
runtime_password=$(cat /run/secrets/db_runtime_password)
migrator_password=$(cat /run/secrets/db_migrator_password)
test_password=$(cat /run/secrets/db_test_password)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=runtime_password="$runtime_password" --set=migrator_password="$migrator_password" --set=test_password="$test_password" <<'SQL'
CREATE ROLE pcrstudio_migrator LOGIN PASSWORD :'migrator_password';
CREATE ROLE pcrstudio_runtime LOGIN PASSWORD :'runtime_password';
CREATE ROLE pcrstudio_test LOGIN CREATEDB PASSWORD :'test_password';
ALTER DATABASE pcrstudio OWNER TO pcrstudio_migrator;
REVOKE ALL ON DATABASE pcrstudio FROM PUBLIC;
GRANT CONNECT ON DATABASE pcrstudio TO pcrstudio_runtime;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO pcrstudio_migrator;
GRANT USAGE ON SCHEMA public TO pcrstudio_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE pcrstudio_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pcrstudio_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE pcrstudio_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO pcrstudio_runtime;
CREATE DATABASE pcrstudio_testdb OWNER pcrstudio_test;
REVOKE ALL ON DATABASE pcrstudio_testdb FROM PUBLIC;
SQL
