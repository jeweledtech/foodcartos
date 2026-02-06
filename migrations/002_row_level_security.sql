-- FoodCartOS Row Level Security (Multi-Tenant Data Isolation)
-- Run after 001_initial_schema.sql
-- Uses dedicated 'foodcartos' schema

SET search_path TO foodcartos, public;

-- ===========================================
-- ENABLE RLS ON ALL TABLES
-- ===========================================

ALTER TABLE foodcartos.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.carts ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.daily_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.quality_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.gps_pings ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.sms_subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.sms_messages ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- HELPER FUNCTIONS
-- ===========================================

CREATE OR REPLACE FUNCTION foodcartos.get_user_org_id()
RETURNS UUID AS $$
BEGIN
    RETURN (auth.jwt()->>'org_id')::UUID;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION foodcartos.get_user_role()
RETURNS TEXT AS $$
BEGIN
    RETURN auth.jwt()->>'role';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION foodcartos.get_user_id()
RETURNS UUID AS $$
BEGIN
    RETURN (auth.jwt()->>'sub')::UUID;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ===========================================
-- ORGANIZATIONS POLICIES
-- ===========================================

CREATE POLICY "Users can view own organization"
ON foodcartos.organizations FOR SELECT
USING (id = foodcartos.get_user_org_id());

CREATE POLICY "Service role can create organizations"
ON foodcartos.organizations FOR INSERT
WITH CHECK (TRUE);

CREATE POLICY "Owners can update own organization"
ON foodcartos.organizations FOR UPDATE
USING (id = foodcartos.get_user_org_id() AND foodcartos.get_user_role() = 'owner');

-- ===========================================
-- USERS POLICIES
-- ===========================================

CREATE POLICY "Users can view org members"
ON foodcartos.users FOR SELECT
USING (org_id = foodcartos.get_user_org_id());

CREATE POLICY "Owners can create users"
ON foodcartos.users FOR INSERT
WITH CHECK (org_id = foodcartos.get_user_org_id() AND foodcartos.get_user_role() = 'owner');

CREATE POLICY "Users can update"
ON foodcartos.users FOR UPDATE
USING (
    org_id = foodcartos.get_user_org_id()
    AND (foodcartos.get_user_role() = 'owner' OR id = foodcartos.get_user_id())
);

CREATE POLICY "Owners can delete users"
ON foodcartos.users FOR DELETE
USING (org_id = foodcartos.get_user_org_id() AND foodcartos.get_user_role() = 'owner');

-- ===========================================
-- LOCATIONS POLICIES
-- ===========================================

CREATE POLICY "Org members can view locations"
ON foodcartos.locations FOR SELECT
USING (org_id = foodcartos.get_user_org_id());

CREATE POLICY "Owners/operators can create locations"
ON foodcartos.locations FOR INSERT
WITH CHECK (
    org_id = foodcartos.get_user_org_id()
    AND foodcartos.get_user_role() IN ('owner', 'operator')
);

CREATE POLICY "Owners/operators can update locations"
ON foodcartos.locations FOR UPDATE
USING (
    org_id = foodcartos.get_user_org_id()
    AND foodcartos.get_user_role() IN ('owner', 'operator')
);

-- ===========================================
-- CARTS POLICIES
-- ===========================================

CREATE POLICY "Org members can view carts"
ON foodcartos.carts FOR SELECT
USING (org_id = foodcartos.get_user_org_id());

CREATE POLICY "Owners can create carts"
ON foodcartos.carts FOR INSERT
WITH CHECK (org_id = foodcartos.get_user_org_id() AND foodcartos.get_user_role() = 'owner');

CREATE POLICY "Owners can update carts"
ON foodcartos.carts FOR UPDATE
USING (org_id = foodcartos.get_user_org_id() AND foodcartos.get_user_role() = 'owner');

-- ===========================================
-- DAILY ASSIGNMENTS POLICIES
-- ===========================================

CREATE POLICY "Org members can view assignments"
ON foodcartos.daily_assignments FOR SELECT
USING (org_id = foodcartos.get_user_org_id());

CREATE POLICY "Owners/operators can create assignments"
ON foodcartos.daily_assignments FOR INSERT
WITH CHECK (
    org_id = foodcartos.get_user_org_id()
    AND foodcartos.get_user_role() IN ('owner', 'operator')
);

CREATE POLICY "Authorized users can update assignments"
ON foodcartos.daily_assignments FOR UPDATE
USING (
    org_id = foodcartos.get_user_org_id()
    AND (
        foodcartos.get_user_role() IN ('owner', 'operator')
        OR employee_id = foodcartos.get_user_id()
    )
);

-- ===========================================
-- TRANSACTIONS POLICIES
-- ===========================================

CREATE POLICY "Users can view authorized transactions"
ON foodcartos.transactions FOR SELECT
USING (
    org_id = foodcartos.get_user_org_id()
    AND (
        foodcartos.get_user_role() = 'owner'
        OR cart_id IN (
            SELECT cart_id FROM foodcartos.daily_assignments
            WHERE employee_id = foodcartos.get_user_id()
        )
    )
);

CREATE POLICY "Service can create transactions"
ON foodcartos.transactions FOR INSERT
WITH CHECK (TRUE);

-- ===========================================
-- QUALITY CHECKS POLICIES
-- ===========================================

CREATE POLICY "Users can view quality checks"
ON foodcartos.quality_checks FOR SELECT
USING (
    org_id = foodcartos.get_user_org_id()
    AND (
        foodcartos.get_user_role() IN ('owner', 'operator')
        OR employee_id = foodcartos.get_user_id()
    )
);

CREATE POLICY "Employees can create quality checks"
ON foodcartos.quality_checks FOR INSERT
WITH CHECK (
    org_id = foodcartos.get_user_org_id()
    AND employee_id = foodcartos.get_user_id()
);

CREATE POLICY "Owners can update quality checks"
ON foodcartos.quality_checks FOR UPDATE
USING (org_id = foodcartos.get_user_org_id() AND foodcartos.get_user_role() = 'owner');

-- ===========================================
-- GPS PINGS POLICIES
-- ===========================================

CREATE POLICY "Owners/operators can view GPS"
ON foodcartos.gps_pings FOR SELECT
USING (
    org_id = foodcartos.get_user_org_id()
    AND foodcartos.get_user_role() IN ('owner', 'operator')
);

CREATE POLICY "Hardware can create GPS pings"
ON foodcartos.gps_pings FOR INSERT
WITH CHECK (TRUE);

-- ===========================================
-- SMS SUBSCRIBERS POLICIES
-- ===========================================

CREATE POLICY "Owners/operators can view subscribers"
ON foodcartos.sms_subscribers FOR SELECT
USING (
    org_id = foodcartos.get_user_org_id()
    AND foodcartos.get_user_role() IN ('owner', 'operator')
);

CREATE POLICY "Owners/operators can manage subscribers"
ON foodcartos.sms_subscribers FOR ALL
USING (
    org_id = foodcartos.get_user_org_id()
    AND foodcartos.get_user_role() IN ('owner', 'operator')
);

-- ===========================================
-- SMS MESSAGES POLICIES
-- ===========================================

CREATE POLICY "Owners can view messages"
ON foodcartos.sms_messages FOR SELECT
USING (org_id = foodcartos.get_user_org_id() AND foodcartos.get_user_role() = 'owner');

CREATE POLICY "Service can create messages"
ON foodcartos.sms_messages FOR INSERT
WITH CHECK (TRUE);
