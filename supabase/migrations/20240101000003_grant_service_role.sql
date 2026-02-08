-- Grant service_role full access to foodcartos schema
-- This allows the SUPABASE_SERVICE_KEY to bypass RLS and perform admin operations

-- Schema access
GRANT ALL ON SCHEMA foodcartos TO service_role;

-- Grant full access to all existing tables
GRANT ALL ON ALL TABLES IN SCHEMA foodcartos TO service_role;

-- Grant usage on sequences (for auto-generated IDs)
GRANT ALL ON ALL SEQUENCES IN SCHEMA foodcartos TO service_role;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA foodcartos
GRANT ALL ON TABLES TO service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA foodcartos
GRANT ALL ON SEQUENCES TO service_role;
