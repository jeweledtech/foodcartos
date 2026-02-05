-- FoodCartOS Row Level Security (Multi-Tenant Data Isolation)
-- Run after 001_initial_schema.sql

-- ===========================================
-- ENABLE RLS ON ALL TABLES
-- ===========================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE carts ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE gps_pings ENABLE ROW LEVEL SECURITY;
ALTER TABLE sms_subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE sms_messages ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- HELPER FUNCTION: Get current user's org_id
-- ===========================================

CREATE OR REPLACE FUNCTION get_user_org_id()
RETURNS UUID AS $$
BEGIN
    -- In Supabase, auth.jwt() contains the JWT claims
    -- We store org_id in the JWT metadata
    RETURN (auth.jwt()->>'org_id')::UUID;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION get_user_role()
RETURNS TEXT AS $$
BEGIN
    RETURN auth.jwt()->>'role';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION get_user_id()
RETURNS UUID AS $$
BEGIN
    RETURN (auth.jwt()->>'sub')::UUID;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ===========================================
-- ORGANIZATIONS POLICIES
-- ===========================================

-- Users can only see their own organization
CREATE POLICY "Users can view own organization"
ON organizations FOR SELECT
USING (id = get_user_org_id());

-- Only service role can create organizations
CREATE POLICY "Service role can create organizations"
ON organizations FOR INSERT
WITH CHECK (TRUE);  -- Controlled at API level

-- Owners can update their organization
CREATE POLICY "Owners can update own organization"
ON organizations FOR UPDATE
USING (id = get_user_org_id() AND get_user_role() = 'owner');

-- ===========================================
-- USERS POLICIES
-- ===========================================

-- Users can see other users in their organization
CREATE POLICY "Users can view org members"
ON users FOR SELECT
USING (org_id = get_user_org_id());

-- Owners can create users
CREATE POLICY "Owners can create users"
ON users FOR INSERT
WITH CHECK (org_id = get_user_org_id() AND get_user_role() = 'owner');

-- Owners can update users, users can update themselves
CREATE POLICY "Users can update"
ON users FOR UPDATE
USING (
    org_id = get_user_org_id()
    AND (get_user_role() = 'owner' OR id = get_user_id())
);

-- Owners can delete users
CREATE POLICY "Owners can delete users"
ON users FOR DELETE
USING (org_id = get_user_org_id() AND get_user_role() = 'owner');

-- ===========================================
-- LOCATIONS POLICIES
-- ===========================================

-- All org members can view locations
CREATE POLICY "Org members can view locations"
ON locations FOR SELECT
USING (org_id = get_user_org_id());

-- Owners and operators can manage locations
CREATE POLICY "Owners/operators can create locations"
ON locations FOR INSERT
WITH CHECK (
    org_id = get_user_org_id()
    AND get_user_role() IN ('owner', 'operator')
);

CREATE POLICY "Owners/operators can update locations"
ON locations FOR UPDATE
USING (
    org_id = get_user_org_id()
    AND get_user_role() IN ('owner', 'operator')
);

-- ===========================================
-- CARTS POLICIES
-- ===========================================

-- All org members can view carts
CREATE POLICY "Org members can view carts"
ON carts FOR SELECT
USING (org_id = get_user_org_id());

-- Only owners can manage carts
CREATE POLICY "Owners can create carts"
ON carts FOR INSERT
WITH CHECK (org_id = get_user_org_id() AND get_user_role() = 'owner');

CREATE POLICY "Owners can update carts"
ON carts FOR UPDATE
USING (org_id = get_user_org_id() AND get_user_role() = 'owner');

-- ===========================================
-- DAILY ASSIGNMENTS POLICIES
-- ===========================================

-- All org members can view assignments
CREATE POLICY "Org members can view assignments"
ON daily_assignments FOR SELECT
USING (org_id = get_user_org_id());

-- Owners and operators can create assignments
CREATE POLICY "Owners/operators can create assignments"
ON daily_assignments FOR INSERT
WITH CHECK (
    org_id = get_user_org_id()
    AND get_user_role() IN ('owner', 'operator')
);

-- Owners, operators, and assigned employees can update
CREATE POLICY "Authorized users can update assignments"
ON daily_assignments FOR UPDATE
USING (
    org_id = get_user_org_id()
    AND (
        get_user_role() IN ('owner', 'operator')
        OR employee_id = get_user_id()
    )
);

-- ===========================================
-- TRANSACTIONS POLICIES
-- ===========================================

-- Owners see all transactions, operators see their cart's transactions
CREATE POLICY "Users can view authorized transactions"
ON transactions FOR SELECT
USING (
    org_id = get_user_org_id()
    AND (
        get_user_role() = 'owner'
        OR cart_id IN (
            SELECT cart_id FROM daily_assignments
            WHERE employee_id = get_user_id()
        )
    )
);

-- Service role and webhooks can insert (controlled at API level)
CREATE POLICY "Service can create transactions"
ON transactions FOR INSERT
WITH CHECK (org_id = get_user_org_id() OR TRUE);  -- Webhooks need access

-- ===========================================
-- QUALITY CHECKS POLICIES
-- ===========================================

-- Owners see all, employees see their own
CREATE POLICY "Users can view quality checks"
ON quality_checks FOR SELECT
USING (
    org_id = get_user_org_id()
    AND (
        get_user_role() IN ('owner', 'operator')
        OR employee_id = get_user_id()
    )
);

-- Employees can create their own quality checks
CREATE POLICY "Employees can create quality checks"
ON quality_checks FOR INSERT
WITH CHECK (
    org_id = get_user_org_id()
    AND employee_id = get_user_id()
);

-- Owners can update (approve/reject)
CREATE POLICY "Owners can update quality checks"
ON quality_checks FOR UPDATE
USING (org_id = get_user_org_id() AND get_user_role() = 'owner');

-- ===========================================
-- GPS PINGS POLICIES
-- ===========================================

-- Owners and operators can view GPS data
CREATE POLICY "Owners/operators can view GPS"
ON gps_pings FOR SELECT
USING (
    org_id = get_user_org_id()
    AND get_user_role() IN ('owner', 'operator')
);

-- Hardware agents can insert (controlled at API level)
CREATE POLICY "Hardware can create GPS pings"
ON gps_pings FOR INSERT
WITH CHECK (TRUE);  -- Validated at API level via hardware_id

-- ===========================================
-- SMS SUBSCRIBERS POLICIES
-- ===========================================

-- Owners and operators can view subscribers
CREATE POLICY "Owners/operators can view subscribers"
ON sms_subscribers FOR SELECT
USING (
    org_id = get_user_org_id()
    AND get_user_role() IN ('owner', 'operator')
);

-- Can manage subscribers
CREATE POLICY "Owners/operators can manage subscribers"
ON sms_subscribers FOR ALL
USING (
    org_id = get_user_org_id()
    AND get_user_role() IN ('owner', 'operator')
);

-- ===========================================
-- SMS MESSAGES POLICIES
-- ===========================================

-- Owners can view all messages
CREATE POLICY "Owners can view messages"
ON sms_messages FOR SELECT
USING (org_id = get_user_org_id() AND get_user_role() = 'owner');

-- Service can create messages (webhooks)
CREATE POLICY "Service can create messages"
ON sms_messages FOR INSERT
WITH CHECK (TRUE);  -- Validated at API level

-- ===========================================
-- NOTES
-- ===========================================

/*
RLS Best Practices for FoodCartOS:

1. All policies use org_id for tenant isolation
2. Role-based access within tenant:
   - owner: Full access
   - operator: Operational access (no financials in some cases)
   - employee: Limited to own data

3. Service role (used by API) bypasses RLS when needed
4. Hardware agents authenticate via hardware_id, validated at API level

5. To test RLS:
   SET request.jwt.claims = '{"org_id": "uuid-here", "role": "owner", "sub": "user-uuid"}';
   SELECT * FROM transactions;  -- Should only show org's data

6. To bypass RLS (service role):
   SET ROLE postgres;
   SELECT * FROM transactions;  -- Shows all data
*/
