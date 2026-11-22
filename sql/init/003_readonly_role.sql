DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_agent') THEN
        CREATE ROLE db_agent LOGIN PASSWORD 'db_agent_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE agent_demo TO db_agent;
GRANT USAGE ON SCHEMA public TO db_agent;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO db_agent;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO db_agent;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO db_agent;

ALTER ROLE db_agent SET default_transaction_read_only = on;
ALTER ROLE db_agent SET statement_timeout = '5s';
