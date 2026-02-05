-- FoodCartOS Initial Database Schema
-- Run this on a fresh Supabase PostgreSQL database

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===========================================
-- ORGANIZATIONS (Tenants)
-- ===========================================

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,  -- e.g., 'eatfirecraft'
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Example: EatFireCraft
COMMENT ON TABLE organizations IS 'Each food cart business is an organization (tenant)';

-- ===========================================
-- USERS
-- ===========================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'operator', 'employee')),
    phone TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

COMMENT ON TABLE users IS 'Users with different roles: owner (Poncho), operator (cart manager), employee (worker)';

-- ===========================================
-- LOCATIONS
-- ===========================================

CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    location_type TEXT,  -- 'dmv', 'courthouse', 'event', 'farmers_market', etc.
    notes TEXT,
    settings JSONB DEFAULT '{}',  -- geofence radius, hours, etc.
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_locations_org_id ON locations(org_id);
CREATE INDEX idx_locations_type ON locations(location_type);

COMMENT ON TABLE locations IS 'Physical locations where carts operate (DMV, Courthouse, etc.)';

-- ===========================================
-- CARTS
-- ===========================================

CREATE TABLE carts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    hardware_id TEXT UNIQUE,  -- Raspberry Pi serial number
    current_location_id UUID REFERENCES locations(id),
    status TEXT DEFAULT 'inactive' CHECK (status IN ('active', 'inactive', 'maintenance')),
    settings JSONB DEFAULT '{}',
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_carts_org_id ON carts(org_id);
CREATE INDEX idx_carts_hardware_id ON carts(hardware_id);
CREATE INDEX idx_carts_status ON carts(status);

COMMENT ON TABLE carts IS 'Physical food carts with optional hardware tracking';

-- ===========================================
-- DAILY ASSIGNMENTS
-- ===========================================

CREATE TABLE daily_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES carts(id) ON DELETE CASCADE,
    location_id UUID REFERENCES locations(id) ON DELETE CASCADE,
    employee_id UUID REFERENCES users(id),
    date DATE NOT NULL,
    shift_start TIME,
    shift_end TIME,
    actual_start TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cart_id, date)  -- One assignment per cart per day
);

CREATE INDEX idx_assignments_org_id ON daily_assignments(org_id);
CREATE INDEX idx_assignments_date ON daily_assignments(date);
CREATE INDEX idx_assignments_cart_id ON daily_assignments(cart_id);
CREATE INDEX idx_assignments_employee_id ON daily_assignments(employee_id);

COMMENT ON TABLE daily_assignments IS 'Which cart goes to which location with which employee each day';

-- ===========================================
-- TRANSACTIONS
-- ===========================================

CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES carts(id),
    location_id UUID REFERENCES locations(id),
    square_id TEXT UNIQUE,
    amount DECIMAL(10, 2) NOT NULL,
    items JSONB DEFAULT '[]',  -- [{name, quantity, price}]
    payment_method TEXT,  -- 'card', 'cash'
    timestamp TIMESTAMPTZ NOT NULL,
    day_of_week INTEGER,  -- 0=Sunday, 6=Saturday
    weather JSONB,  -- Captured at transaction time
    synced_from_local BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transactions_org_id ON transactions(org_id);
CREATE INDEX idx_transactions_cart_id ON transactions(cart_id);
CREATE INDEX idx_transactions_location_id ON transactions(location_id);
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX idx_transactions_day_of_week ON transactions(day_of_week);
CREATE INDEX idx_transactions_square_id ON transactions(square_id);

COMMENT ON TABLE transactions IS 'Revenue data from Square POS (real-time via webhooks or synced from carts)';

-- ===========================================
-- QUALITY CHECKS
-- ===========================================

CREATE TABLE quality_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES carts(id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES daily_assignments(id),
    employee_id UUID REFERENCES users(id),
    check_type TEXT NOT NULL,  -- 'dirty_water', 'garlic_butter', 'cart_display'
    photo_url TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer_id UUID REFERENCES users(id),
    reviewer_notes TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_quality_checks_org_id ON quality_checks(org_id);
CREATE INDEX idx_quality_checks_cart_id ON quality_checks(cart_id);
CREATE INDEX idx_quality_checks_employee_id ON quality_checks(employee_id);
CREATE INDEX idx_quality_checks_timestamp ON quality_checks(timestamp);
CREATE INDEX idx_quality_checks_check_type ON quality_checks(check_type);

COMMENT ON TABLE quality_checks IS 'Photo verification for morning checklist items (dirty water, garlic butter, etc.)';

-- ===========================================
-- GPS PINGS
-- ===========================================

CREATE TABLE gps_pings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES carts(id) ON DELETE CASCADE,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    accuracy DECIMAL(6, 2),  -- meters
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Partition by month for performance (optional for large deployments)
CREATE INDEX idx_gps_pings_cart_id ON gps_pings(cart_id);
CREATE INDEX idx_gps_pings_timestamp ON gps_pings(timestamp);

COMMENT ON TABLE gps_pings IS 'Location history from cart GPS (every 5 minutes typically)';

-- ===========================================
-- SMS SUBSCRIBERS
-- ===========================================

CREATE TABLE sms_subscribers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT,
    subscribed BOOLEAN DEFAULT TRUE,
    favorite_locations UUID[],  -- Array of location IDs to notify about
    last_order JSONB,  -- Last order for "same" functionality
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, phone)
);

CREATE INDEX idx_sms_subscribers_org_id ON sms_subscribers(org_id);
CREATE INDEX idx_sms_subscribers_phone ON sms_subscribers(phone);
CREATE INDEX idx_sms_subscribers_subscribed ON sms_subscribers(subscribed);

COMMENT ON TABLE sms_subscribers IS 'Customers who opted in for SMS location alerts and pre-orders';

-- ===========================================
-- SMS MESSAGES (for tracking)
-- ===========================================

CREATE TABLE sms_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    subscriber_id UUID REFERENCES sms_subscribers(id),
    direction TEXT CHECK (direction IN ('outbound', 'inbound')),
    twilio_sid TEXT,
    from_number TEXT,
    to_number TEXT,
    body TEXT,
    status TEXT,  -- 'sent', 'delivered', 'failed', etc.
    message_type TEXT,  -- 'location_alert', 'pre_order', 'marketing', 'reply'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sms_messages_org_id ON sms_messages(org_id);
CREATE INDEX idx_sms_messages_subscriber_id ON sms_messages(subscriber_id);
CREATE INDEX idx_sms_messages_created_at ON sms_messages(created_at);

COMMENT ON TABLE sms_messages IS 'SMS message log for analytics and conversation history';

-- ===========================================
-- HELPER FUNCTIONS
-- ===========================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_locations_updated_at
    BEFORE UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_carts_updated_at
    BEFORE UPDATE ON carts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_daily_assignments_updated_at
    BEFORE UPDATE ON daily_assignments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_sms_subscribers_updated_at
    BEFORE UPDATE ON sms_subscribers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ===========================================
-- INITIAL DATA (Optional)
-- ===========================================

-- Uncomment to create a demo organization
/*
INSERT INTO organizations (name, slug) VALUES ('EatFireCraft', 'eatfirecraft');

INSERT INTO users (org_id, email, name, role)
SELECT id, 'poncho@eatfirecraft.com', 'Poncho', 'owner'
FROM organizations WHERE slug = 'eatfirecraft';

INSERT INTO locations (org_id, name, address, latitude, longitude, location_type, notes)
SELECT id, 'Courthouse', '123 Main St, Vacaville, CA', 38.3566, -121.9877, 'courthouse',
       'Jury duty days are Thursday - 74% higher revenue!'
FROM organizations WHERE slug = 'eatfirecraft';

INSERT INTO locations (org_id, name, address, latitude, longitude, location_type, notes)
SELECT id, 'DMV', '456 Oak Ave, Vacaville, CA', 38.3600, -121.9800, 'dmv',
       'Tuesdays are renewal day - best revenue'
FROM organizations WHERE slug = 'eatfirecraft';
*/
