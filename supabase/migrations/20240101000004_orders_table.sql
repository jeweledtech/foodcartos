-- Orders Table for Multi-Platform Order Management
-- Stores orders from all sources: Square, DoorDash, UberEats, Grubhub, SMS

-- Create platform enum
CREATE TYPE foodcartos.order_platform AS ENUM (
    'square',
    'doordash',
    'ubereats',
    'grubhub',
    'sms',
    'walk_in'
);

-- Create order status enum
CREATE TYPE foodcartos.order_status AS ENUM (
    'pending',
    'confirmed',
    'preparing',
    'ready',
    'picked_up',
    'delivered',
    'cancelled',
    'refunded'
);

-- Create orders table
CREATE TABLE foodcartos.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    cart_id UUID REFERENCES foodcartos.carts(id) ON DELETE SET NULL,
    location_id UUID REFERENCES foodcartos.locations(id) ON DELETE SET NULL,

    -- Platform info
    platform foodcartos.order_platform NOT NULL DEFAULT 'walk_in',
    external_id TEXT,  -- Platform's order ID (DoorDash order ID, etc.)

    -- Customer info
    customer_name TEXT,
    customer_phone TEXT,
    customer_email TEXT,

    -- Order items (JSONB array)
    items JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Financials
    subtotal DECIMAL(10, 2) NOT NULL DEFAULT 0,
    tax DECIMAL(10, 2) NOT NULL DEFAULT 0,
    tip DECIMAL(10, 2) NOT NULL DEFAULT 0,
    delivery_fee DECIMAL(10, 2) NOT NULL DEFAULT 0,
    platform_fee DECIMAL(10, 2) NOT NULL DEFAULT 0,
    total DECIMAL(10, 2) NOT NULL DEFAULT 0,

    -- Status
    status foodcartos.order_status NOT NULL DEFAULT 'pending',

    -- Delivery info (JSONB for flexibility)
    delivery JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    ready_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Raw platform payload for debugging
    raw_payload JSONB,

    -- Unique constraint on external_id per platform
    CONSTRAINT unique_platform_order UNIQUE (platform, external_id)
);

-- Create indexes
CREATE INDEX idx_orders_org_id ON foodcartos.orders(org_id);
CREATE INDEX idx_orders_cart_id ON foodcartos.orders(cart_id);
CREATE INDEX idx_orders_platform ON foodcartos.orders(platform);
CREATE INDEX idx_orders_status ON foodcartos.orders(status);
CREATE INDEX idx_orders_created_at ON foodcartos.orders(created_at DESC);
CREATE INDEX idx_orders_external_id ON foodcartos.orders(external_id) WHERE external_id IS NOT NULL;

-- GIN index for items search
CREATE INDEX idx_orders_items ON foodcartos.orders USING GIN (items);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION foodcartos.update_orders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER orders_updated_at
    BEFORE UPDATE ON foodcartos.orders
    FOR EACH ROW
    EXECUTE FUNCTION foodcartos.update_orders_updated_at();

-- RLS policies
ALTER TABLE foodcartos.orders ENABLE ROW LEVEL SECURITY;

-- Users can view orders for their organization
CREATE POLICY orders_select ON foodcartos.orders
    FOR SELECT
    USING (
        org_id IN (
            SELECT org_id FROM foodcartos.users
            WHERE id = auth.uid()
        )
    );

-- Users can insert orders for their organization
CREATE POLICY orders_insert ON foodcartos.orders
    FOR INSERT
    WITH CHECK (
        org_id IN (
            SELECT org_id FROM foodcartos.users
            WHERE id = auth.uid()
        )
    );

-- Users can update orders for their organization
CREATE POLICY orders_update ON foodcartos.orders
    FOR UPDATE
    USING (
        org_id IN (
            SELECT org_id FROM foodcartos.users
            WHERE id = auth.uid()
        )
    );

-- Grant permissions
GRANT ALL ON foodcartos.orders TO service_role;
GRANT SELECT, INSERT, UPDATE ON foodcartos.orders TO authenticated;

-- Comment
COMMENT ON TABLE foodcartos.orders IS 'Unified orders from all platforms (Square, DoorDash, UberEats, Grubhub, SMS)';
