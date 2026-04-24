-- Decode Database Setup Script
-- Run as a PostgreSQL superuser (e.g., postgres)
-- Usage: psql -U postgres -f setup.sql

-- Create the database
CREATE DATABASE decode;

-- Connect to the new database
\connect decode

-- Install extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create the application role (non-superuser, used for RLS)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_role') THEN
        CREATE ROLE app_role NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

-- Grant connect to app_role
GRANT CONNECT ON DATABASE decode TO app_role;

-- Note: Run Alembic migrations next to create all tables and RLS policies:
--   cd api && alembic upgrade head
