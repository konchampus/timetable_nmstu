-- Run only on a NEW dedicated application database, as its provisioning administrator.
-- Secrets arrive from protected environment, never command-line --set values.
\set ON_ERROR_STOP on
\set ECHO none
\getenv app_password COMPANION_APP_PASSWORD
\getenv migration_password COMPANION_MIGRATION_PASSWORD
SELECT 1 / CASE WHEN length(:'app_password') >= 24 AND length(:'migration_password') >= 24 THEN 1 ELSE 0 END;
SELECT format('CREATE ROLE companion_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'app_password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='companion_app') \gexec
SELECT format('CREATE ROLE companion_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'migration_password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='companion_migrator') \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE :"DBNAME" TO companion_app, companion_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO companion_migrator;
GRANT USAGE ON SCHEMA public TO companion_app;
ALTER DEFAULT PRIVILEGES FOR ROLE companion_migrator IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO companion_app;
ALTER DEFAULT PRIVILEGES FOR ROLE companion_migrator IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO companion_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO companion_app;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO companion_app;
\unset app_password
\unset migration_password
