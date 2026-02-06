-- FoodCartOS Schema Creation
-- Run this FIRST before other migrations
-- This creates an isolated schema so FoodCartOS doesn't conflict with other projects

-- Create dedicated schema for FoodCartOS
CREATE SCHEMA IF NOT EXISTS foodcartos;

-- Grant usage to authenticated users
GRANT USAGE ON SCHEMA foodcartos TO authenticated;
GRANT USAGE ON SCHEMA foodcartos TO anon;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA foodcartos
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA foodcartos
GRANT SELECT ON TABLES TO anon;

COMMENT ON SCHEMA foodcartos IS 'FoodCartOS - Food cart operations management system';
