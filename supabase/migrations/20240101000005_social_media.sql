-- Social Media Automation Tables
-- Stores connected platform accounts, content queue, and post templates
-- Follows the same multi-platform service pattern as delivery_platforms

-- ===========================================
-- ENUMS
-- ===========================================

CREATE TYPE foodcartos.social_platform AS ENUM (
    'instagram',
    'facebook',
    'tiktok',
    'google_business'
);

CREATE TYPE foodcartos.post_status AS ENUM (
    'draft',
    'pending_approval',
    'approved',
    'scheduled',
    'publishing',
    'published',
    'failed',
    'rejected'
);

CREATE TYPE foodcartos.post_trigger AS ENUM (
    'quality_check',
    'location_arrival',
    'milestone',
    'manual',
    'new_location',
    'order_volume'
);

-- ===========================================
-- SOCIAL ACCOUNTS
-- ===========================================

CREATE TABLE foodcartos.social_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    platform foodcartos.social_platform NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    platform_user_id TEXT,
    platform_username TEXT,
    platform_page_id TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_org_platform_account UNIQUE (org_id, platform, platform_user_id)
);

CREATE INDEX idx_social_accounts_org_id ON foodcartos.social_accounts(org_id);
CREATE INDEX idx_social_accounts_platform ON foodcartos.social_accounts(platform);
CREATE INDEX idx_social_accounts_active ON foodcartos.social_accounts(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE foodcartos.social_accounts IS 'Connected social media accounts per org with OAuth tokens and auto-approve settings';

-- ===========================================
-- SOCIAL POSTS
-- ===========================================

CREATE TABLE foodcartos.social_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    caption TEXT NOT NULL DEFAULT '',
    media_urls TEXT[] NOT NULL DEFAULT '{}',
    hashtags TEXT[] NOT NULL DEFAULT '{}',
    trigger_type foodcartos.post_trigger NOT NULL DEFAULT 'manual',
    trigger_entity_id UUID,
    status foodcartos.post_status NOT NULL DEFAULT 'draft',
    target_platforms foodcartos.social_platform[] NOT NULL DEFAULT '{}',
    platform_post_ids JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_sent_at TIMESTAMPTZ,
    approval_sent_to TEXT,
    approved_at TIMESTAMPTZ,
    approved_by TEXT,
    rejected_at TIMESTAMPTZ,
    scheduled_for TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_social_posts_org_id ON foodcartos.social_posts(org_id);
CREATE INDEX idx_social_posts_status ON foodcartos.social_posts(status);
CREATE INDEX idx_social_posts_trigger_type ON foodcartos.social_posts(trigger_type);
CREATE INDEX idx_social_posts_created_at ON foodcartos.social_posts(created_at DESC);
CREATE INDEX idx_social_posts_scheduled ON foodcartos.social_posts(scheduled_for)
    WHERE status = 'scheduled' AND scheduled_for IS NOT NULL;

COMMENT ON TABLE foodcartos.social_posts IS 'Content queue with full lifecycle: draft -> approval -> publish across platforms';

-- ===========================================
-- SOCIAL TEMPLATES
-- ===========================================

CREATE TABLE foodcartos.social_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES foodcartos.organizations(id) ON DELETE CASCADE,
    trigger_type foodcartos.post_trigger NOT NULL,
    name TEXT NOT NULL,
    caption_template TEXT NOT NULL,
    default_hashtags TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_social_templates_org_id ON foodcartos.social_templates(org_id);
CREATE INDEX idx_social_templates_trigger ON foodcartos.social_templates(trigger_type);

COMMENT ON TABLE foodcartos.social_templates IS 'Org-customizable caption templates per trigger type';

-- ===========================================
-- UPDATED_AT TRIGGERS
-- ===========================================

CREATE TRIGGER update_social_accounts_updated_at
    BEFORE UPDATE ON foodcartos.social_accounts
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();

CREATE TRIGGER update_social_posts_updated_at
    BEFORE UPDATE ON foodcartos.social_posts
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();

CREATE TRIGGER update_social_templates_updated_at
    BEFORE UPDATE ON foodcartos.social_templates
    FOR EACH ROW EXECUTE FUNCTION foodcartos.update_updated_at();

-- ===========================================
-- ROW LEVEL SECURITY
-- ===========================================

ALTER TABLE foodcartos.social_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.social_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE foodcartos.social_templates ENABLE ROW LEVEL SECURITY;

-- Social Accounts: owners can manage, operators can view
CREATE POLICY social_accounts_select ON foodcartos.social_accounts
    FOR SELECT
    USING (org_id = foodcartos.get_user_org_id());

CREATE POLICY social_accounts_insert ON foodcartos.social_accounts
    FOR INSERT
    WITH CHECK (
        org_id = foodcartos.get_user_org_id()
        AND foodcartos.get_user_role() = 'owner'
    );

CREATE POLICY social_accounts_update ON foodcartos.social_accounts
    FOR UPDATE
    USING (
        org_id = foodcartos.get_user_org_id()
        AND foodcartos.get_user_role() = 'owner'
    );

CREATE POLICY social_accounts_delete ON foodcartos.social_accounts
    FOR DELETE
    USING (
        org_id = foodcartos.get_user_org_id()
        AND foodcartos.get_user_role() = 'owner'
    );

-- Social Posts: org members can view, owners/operators can manage
CREATE POLICY social_posts_select ON foodcartos.social_posts
    FOR SELECT
    USING (org_id = foodcartos.get_user_org_id());

CREATE POLICY social_posts_insert ON foodcartos.social_posts
    FOR INSERT
    WITH CHECK (
        org_id = foodcartos.get_user_org_id()
        AND foodcartos.get_user_role() IN ('owner', 'operator')
    );

CREATE POLICY social_posts_update ON foodcartos.social_posts
    FOR UPDATE
    USING (
        org_id = foodcartos.get_user_org_id()
        AND foodcartos.get_user_role() IN ('owner', 'operator')
    );

-- Social Templates: owners can manage, all org members can view
CREATE POLICY social_templates_select ON foodcartos.social_templates
    FOR SELECT
    USING (org_id = foodcartos.get_user_org_id());

CREATE POLICY social_templates_insert ON foodcartos.social_templates
    FOR INSERT
    WITH CHECK (
        org_id = foodcartos.get_user_org_id()
        AND foodcartos.get_user_role() = 'owner'
    );

CREATE POLICY social_templates_update ON foodcartos.social_templates
    FOR UPDATE
    USING (
        org_id = foodcartos.get_user_org_id()
        AND foodcartos.get_user_role() = 'owner'
    );

CREATE POLICY social_templates_delete ON foodcartos.social_templates
    FOR DELETE
    USING (
        org_id = foodcartos.get_user_org_id()
        AND foodcartos.get_user_role() = 'owner'
    );

-- ===========================================
-- GRANTS
-- ===========================================

GRANT ALL ON foodcartos.social_accounts TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON foodcartos.social_accounts TO authenticated;

GRANT ALL ON foodcartos.social_posts TO service_role;
GRANT SELECT, INSERT, UPDATE ON foodcartos.social_posts TO authenticated;

GRANT ALL ON foodcartos.social_templates TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON foodcartos.social_templates TO authenticated;
