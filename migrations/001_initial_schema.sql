-- FoodCartOS Initial Database Schema
-- Run AFTER 000_create_schema.sql
-- Uses dedicated 'foodcartos' schema to avoid conflicts with other projects

-- Enable UUID extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set search path to foodcartos schema for this session
SET search_path TO foodcartos, public;

-- ===========================================
-- ORGANIZATIONS (Tenants)
-- ===========================================

CREATE TABLE foodcartos.organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,  -- e.g., 'eatfirecraft'
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE foodcartos.organizations IS 'Each food cart business is an organization (tenant)';

-- ===========================================
-- USERS
-- ===========================================

CREATE TABLE foodcartos.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'operator', 'employee')),
    phone TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_org_id ON foodcartos.users(org_id);
CREATE INDEX idx_users_email ON foodcartos.users(email);
CREATE INDEX idx_users_role ON foodcartos.users(role);

COMMENT ON TABLE foodcartos.users IS 'Users with different roles: owner (Poncho), operator (cart manager), employee (worker)';

-- ===========================================
-- LOCATIONS
-- ===========================================

CREATE TABLE foodcartos.locations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
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

CREATE INDEX idx_locations_org_id ON foodcartos.locations(org_id);
CREATE INDEX idx_locations_type ON foodcartos.locations(location_type);

COMMENT ON TABLE foodcartos.locations IS 'Physical locations where carts operate (DMV, Courthouse, etc.)';

-- ===========================================
-- CARTS
-- ===========================================

CREATE TABLE foodcartos.carts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    hardware_id TEXT UNIQUE,  -- Raspberry Pi serial number
    current_location_id UUID REFERENCES foodcartos.locations(id),
    status TEXT DEFAULT 'inactive' CHECK (status IN ('active', 'inactive', 'maintenance')),
    settings JSONB DEFAULT '{}',
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_carts_org_id ON foodcartos.carts(org_id);
CREATE INDEX idx_carts_hardware_id ON foodcartos.carts(hardware_id);
CREATE INDEX idx_carts_status ON foodcartos.carts(status);

COMMENT ON TABLE foodcartos.carts IS 'Physical food carts with optional hardware tracking';

-- ===========================================
-- DAILY ASSIGNMENTS
-- ===========================================

CREATE TABLE foodcartos.daily_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES foodcartos.carts(id) ON DELETE CASCADE,
    location_id UUID REFERENCES foodcartos.locations(id) ON DELETE CASCADE,
    employee_id UUID REFERENCES foodcartos.users(id),
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

CREATE INDEX idx_assignments_org_id ON foodcartos.daily_assignments(org_id);
CREATE INDEX idx_assignments_date ON foodcartos.daily_assignments(date);
CREATE INDEX idx_assignments_cart_id ON foodcartos.daily_assignments(cart_id);
CREATE INDEX idx_assignments_employee_id ON foodcartos.daily_assignments(employee_id);

COMMENT ON TABLE foodcartos.daily_assignments IS 'Which cart goes to which location with which employee each day';

-- ===========================================
-- TRANSACTIONS
-- ===========================================

CREATE TABLE foodcartos.transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES foodcartos.carts(id),
    location_id UUID REFERENCES foodcartos.locations(id),
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

CREATE INDEX idx_transactions_org_id ON foodcartos.transactions(org_id);
CREATE INDEX idx_transactions_cart_id ON foodcartos.transactions(cart_id);
CREATE INDEX idx_transactions_location_id ON foodcartos.transactions(location_id);
CREATE INDEX idx_transactions_timestamp ON foodcartos.transactions(timestamp);
CREATE INDEX idx_transactions_day_of_week ON foodcartos.transactions(day_of_week);
CREATE INDEX idx_transactions_square_id ON foodcartos.transactions(square_id);

COMMENT ON TABLE foodcartos.transactions IS 'Revenue data from Square POS (real-time via webhooks or synced from carts)';

-- ===========================================
-- QUALITY CHECKS
-- ===========================================

CREATE TABLE foodcartos.quality_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES foodcartos.carts(id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES foodcartos.daily_assignments(id),
    employee_id UUID REFERENCES foodcartos.users(id),
    check_type TEXT NOT NULL,  -- 'dirty_water', 'garlic_butter', 'cart_display'
    photo_url TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer_id UUID REFERENCES foodcartos.users(id),
    reviewer_notes TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_quality_checks_org_id ON foodcartos.quality_checks(org_id);
CREATE INDEX idx_quality_checks_cart_id ON foodcartos.quality_checks(cart_id);
CREATE INDEX idx_quality_checks_employee_id ON foodcartos.quality_checks(employee_id);
CREATE INDEX idx_quality_checks_timestamp ON foodcartos.quality_checks(timestamp);
CREATE INDEX idx_quality_checks_check_type ON foodcartos.quality_checks(check_type);

COMMENT ON TABLE foodcartos.quality_checks IS 'Photo verification for morning checklist items (dirty water, garlic butter, etc.)';

-- ===========================================
-- GPS PINGS
-- ===========================================

CREATE TABLE foodcartos.gps_pings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES foodcartos.carts(id) ON DELETE CASCADE,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    accuracy DECIMAL(6, 2),  -- meters
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_gps_pings_cart_id ON foodcartos.gps_pings(cart_id);
CREATE INDEX idx_gps_pings_timestamp ON foodcartos.gps_pings(timestamp);

COMMENT ON TABLE foodcartos.gps_pings IS 'Location history from cart GPS (every 5 minutes typically)';

-- ===========================================
-- SMS SUBSCRIBERS
-- ===========================================

CREATE TABLE foodcartos.sms_subscribers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT,
    subscribed BOOLEAN DEFAULT TRUE,
    favorite_locations UUID[],  -- Array of location IDs to notify about
    last_order JSONB,  -- Last order for "same" functionality
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, phone)
);

CREATE INDEX idx_sms_subscribers_org_id ON foodcartos.sms_subscribers(org_id);
CREATE INDEX idx_sms_subscribers_phone ON foodcartos.sms_subscribers(phone);
CREATE INDEX idx_sms_subscribers_subscribed ON foodcartos.sms_subscribers(subscribed);

COMMENT ON TABLE foodcartos.sms_subscribers IS 'Customers who opted in for SMS location alerts and pre-orders';

-- ===========================================
-- SMS MESSAGES (for tracking)
-- ===========================================

CREATE TABLE foodcartos.sms_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    subscriber_id UUID REFERENCES foodcartos.sms_subscribers(id),
    direction TEXT CHECK (direction IN ('outbound', 'inbound')),
    twilio_sid TEXT,
    from_number TEXT,
    to_number TEXT,
    body TEXT,
    status TEXT,  -- 'sent', 'delivered', 'failed', etc.
    message_type TEXT,  -- 'location_alert', 'pre_order', 'marketing', 'reply'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sms_messages_org_id ON foodcartos.sms_messages(org_id);
CREATE INDEX idx_sms_messages_subscriber_id ON foodcartos.sms_messages(subscriber_id);
CREATE INDEX idx_sms_messages_created_at ON foodcartos.sms_messages(created_at);

COMMENT ON TABLE foodcartos.sms_messages IS 'SMS message log for analytics and conversation history';

-- ===========================================
-- HELPER FUNCTIONS
-- ===========================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION foodcartos.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON foodcartos.organizations
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON foodcartos.users
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();

CREATE TRIGGER update_locations_updated_at
    BEFORE UPDATE ON foodcartos.locations
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();

CREATE TRIGGER update_carts_updated_at
    BEFORE UPDATE ON foodcartos.carts
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();

CREATE TRIGGER update_daily_assignments_updated_at
    BEFORE UPDATE ON foodcartos.daily_assignments
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();

CREATE TRIGGER update_sms_subscribers_updated_at
    BEFORE UPDATE ON foodcartos.sms_subscribers
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();
