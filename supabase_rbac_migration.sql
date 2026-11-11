-- ==============================================================================
-- Supabase PostgreSQL Migration: Role-Based Access Control (RBAC) & Defense-in-Depth Hardening
-- ==============================================================================
-- Project: NFT Trend Analyzer v3.0
-- Architecture: FastAPI Application Gateway with service_role Backend Access
-- Sensitive Tables Governed:
--   1. public.registered_users
--   2. public.password_reset_tokens
--   3. public.user_work_history
--   4. public.admin_activity_log
--   5. public.admin_verification_tokens
--
-- Security Features & Design:
--   - Wrapped in atomic PostgreSQL transaction: BEGIN ... COMMIT.
--   - Transactional DDL ensures zero partial-state schemas upon any failure.
--   - Pre-migration data audit runs BEFORE column alterations or constraint updates.
--   - Dynamic inspection of pg_constraint identifies and removes ALL legacy check
--     constraints on role and account_status regardless of constraint name,
--     guaranteeing analyst-to-user normalization cannot be blocked.
--   - Strictly preserves unrelated table constraints (primary keys, unique email,
--     check constraints on email or timestamp columns).
--   - Comprehensive defense-in-depth: RLS enabled and forced on all five sensitive tables.
--   - Default-deny RLS posture: no permissive policies granted to anon or authenticated.
--   - Direct client privileges (anon, authenticated, PUBLIC) revoked on all 5 tables and functions.
--   - service_role and postgres privileges fully granted for secure backend gateway execution.
--   - Idempotent and safe against repeated execution.
--
-- Supabase SQL Editor Execution Notes & Limitations:
--   1. Paste the entire script (including BEGIN; and COMMIT;) into the Supabase SQL Editor:
--      https://supabase.com/dashboard/project/<your-project-id>/sql
--   2. Click "Run" once to execute the complete atomic batch.
--   3. Supabase uses connection poolers (Supavisor / PgBouncer) in transaction mode.
--      Do NOT execute BEGIN in one query and COMMIT in a subsequent editor run; separate
--      editor executions map to different connections.
--   4. Standard CREATE INDEX IF NOT EXISTS is transactional in PostgreSQL and works inside BEGIN/COMMIT.
--      (Do NOT use CREATE INDEX CONCURRENTLY inside this transaction block).
--   5. Default statement timeout in Supabase is 120 seconds. This migration executes
--      in milliseconds on typical databases.
-- ==============================================================================

BEGIN;

-- ------------------------------------------------------------------------------
-- 1. Ensure Table Structure Baseline for All 5 Sensitive Tables
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.registered_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    jti TEXT PRIMARY KEY,
    user_email TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.user_work_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email TEXT NOT NULL,
    project_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    dataset_signature TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.admin_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    user_email TEXT,
    action TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.admin_verification_tokens (
    jti TEXT PRIMARY KEY,
    user_email TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 2. Pre-Migration Baseline & Data Audit (Runs BEFORE Altering Schema or Data)
-- ------------------------------------------------------------------------------
-- 2.1 Baseline Schema Compatibility & Completeness Audit
-- Ensure that CREATE TABLE IF NOT EXISTS did not conceal an incomplete or incompatible pre-existing schema.
-- Verify that EVERY required column exists with a compatible data type across all five sensitive tables.
-- Aborts safely if any required column is missing or if existing column data types are incompatible.
DO $$
DECLARE
    r RECORD;
    v_col_type TEXT;
    v_udt_name TEXT;
    v_is_compatible BOOLEAN;
BEGIN
    -- Define expected required columns and compatible type categories:
    -- 'id': uuid, text, character varying
    -- 'text': text, character varying
    -- 'timestamp': timestamp with time zone, timestamp without time zone
    -- 'json': jsonb, json, text
    -- 'boolean': boolean
    FOR r IN (
        SELECT * FROM (VALUES
            -- 1. registered_users base required columns
            ('registered_users', 'id', 'id'),
            ('registered_users', 'email', 'text'),
            ('registered_users', 'name', 'text'),
            ('registered_users', 'password_hash', 'text'),
            ('registered_users', 'role', 'text'),
            ('registered_users', 'created_at', 'timestamp'),
            -- 2. password_reset_tokens required columns
            ('password_reset_tokens', 'jti', 'text'),
            ('password_reset_tokens', 'user_email', 'text'),
            ('password_reset_tokens', 'token_hash', 'text'),
            ('password_reset_tokens', 'expires_at', 'timestamp'),
            ('password_reset_tokens', 'created_at', 'timestamp'),
            -- 3. user_work_history required columns
            ('user_work_history', 'id', 'id'),
            ('user_work_history', 'user_email', 'text'),
            ('user_work_history', 'project_name', 'text'),
            ('user_work_history', 'dataset_name', 'text'),
            ('user_work_history', 'dataset_signature', 'text'),
            ('user_work_history', 'analysis_type', 'text'),
            ('user_work_history', 'summary_json', 'json'),
            ('user_work_history', 'storage_path', 'text'),
            ('user_work_history', 'created_at', 'timestamp'),
            ('user_work_history', 'updated_at', 'timestamp'),
            -- 4. admin_activity_log required columns
            ('admin_activity_log', 'id', 'id'),
            ('admin_activity_log', 'action', 'text'),
            ('admin_activity_log', 'details', 'json'),
            ('admin_activity_log', 'created_at', 'timestamp'),
            -- 5. admin_verification_tokens required columns
            ('admin_verification_tokens', 'jti', 'text'),
            ('admin_verification_tokens', 'user_email', 'text'),
            ('admin_verification_tokens', 'token_hash', 'text'),
            ('admin_verification_tokens', 'expires_at', 'timestamp'),
            ('admin_verification_tokens', 'created_at', 'timestamp')
        ) AS t(tbl, col, cat)
    ) LOOP
        -- Query actual column type and udt_name
        SELECT data_type, udt_name INTO v_col_type, v_udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = r.tbl
          AND column_name = r.col;

        -- Check existence: required column MUST exist
        IF v_col_type IS NULL THEN
            RAISE EXCEPTION 'Pre-migration baseline audit failed: table public.% is missing required column ''%''. Schema is incomplete. Aborting transaction.', r.tbl, r.col;
        END IF;

        -- Check type compatibility based on expected category
        v_is_compatible := false;
        IF r.cat = 'id' THEN
            v_is_compatible := (v_udt_name IN ('uuid', 'text', 'varchar') OR v_col_type IN ('text', 'character varying'));
        ELSIF r.cat = 'text' THEN
            v_is_compatible := (v_col_type IN ('text', 'character varying'));
        ELSIF r.cat = 'timestamp' THEN
            v_is_compatible := (v_col_type IN ('timestamp with time zone', 'timestamp without time zone'));
        ELSIF r.cat = 'json' THEN
            v_is_compatible := (v_col_type IN ('jsonb', 'json', 'text'));
        ELSIF r.cat = 'boolean' THEN
            v_is_compatible := (v_col_type = 'boolean');
        END IF;

        IF NOT v_is_compatible THEN
            RAISE EXCEPTION 'Pre-migration baseline audit failed: column public.%.% has incompatible type % / % (expected category %). Aborting transaction.', r.tbl, r.col, v_col_type, v_udt_name, r.cat;
        END IF;
    END LOOP;

    -- Verify optional / extension columns on registered_users if they pre-exist
    FOR r IN (
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'registered_users'
          AND column_name IN ('account_status', 'email_verified', 'updated_at', 'approved_by', 'approved_at')
    ) LOOP
        IF r.column_name IN ('account_status', 'approved_by') AND r.data_type NOT IN ('text', 'character varying') THEN
            RAISE EXCEPTION 'Pre-migration baseline audit failed: public.registered_users.% has incompatible type % (expected TEXT).', r.column_name, r.data_type;
        ELSIF r.column_name = 'email_verified' AND r.data_type != 'boolean' THEN
            RAISE EXCEPTION 'Pre-migration baseline audit failed: public.registered_users.email_verified has incompatible type % (expected BOOLEAN).', r.column_name, r.data_type;
        ELSIF r.column_name IN ('updated_at', 'approved_at') AND r.data_type NOT IN ('timestamp with time zone', 'timestamp without time zone') THEN
            RAISE EXCEPTION 'Pre-migration baseline audit failed: public.registered_users.% has incompatible type % (expected TIMESTAMPTZ).', r.column_name, r.data_type;
        END IF;
    END LOOP;

    RAISE NOTICE 'Pre-migration baseline schema audit passed: all required columns exist with compatible types across all 5 sensitive tables.';
END $$;

-- 2.2 Pre-Migration Data Audit
-- Inspect all existing records before any column alterations or constraint changes.
-- If unauthorized, corrupted, or unexpected custom roles or statuses exist,
-- fail closed and abort immediately before modifying the database.
DO $$
DECLARE
    v_invalid_roles_count INTEGER := 0;
    v_invalid_statuses_count INTEGER := 0;
    v_has_status_col BOOLEAN := false;
BEGIN
    -- Check for unrecognized roles: only 'user', 'admin', 'analyst', and NULL are permissible legacy values
    SELECT COUNT(*) INTO v_invalid_roles_count
    FROM public.registered_users
    WHERE role IS NOT NULL
      AND role NOT IN ('user', 'admin', 'analyst');

    IF v_invalid_roles_count > 0 THEN
        RAISE EXCEPTION 'Migration pre-check aborted: % record(s) in public.registered_users have unrecognized role values. Aborting transaction.', v_invalid_roles_count;
    END IF;

    -- Dynamically check if account_status column already exists before querying it
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'registered_users'
          AND column_name = 'account_status'
    ) INTO v_has_status_col;

    IF v_has_status_col THEN
        EXECUTE 'SELECT COUNT(*) FROM public.registered_users WHERE account_status IS NOT NULL AND account_status NOT IN (''active'', ''pending'', ''rejected'', ''suspended'')'
        INTO v_invalid_statuses_count;

        IF v_invalid_statuses_count > 0 THEN
            RAISE EXCEPTION 'Migration pre-check aborted: % record(s) in public.registered_users have unrecognized account_status values. Aborting transaction.', v_invalid_statuses_count;
        END IF;
    END IF;

    RAISE NOTICE 'Pre-migration data audit passed: all existing records contain valid or permissible legacy roles and statuses.';
END $$;

-- ------------------------------------------------------------------------------
-- 3. Safely Add Missing Required Columns to public.registered_users
-- ------------------------------------------------------------------------------
ALTER TABLE public.registered_users
ADD COLUMN IF NOT EXISTS account_status TEXT NOT NULL DEFAULT 'active';

ALTER TABLE public.registered_users
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT true;

ALTER TABLE public.registered_users
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE public.registered_users
ADD COLUMN IF NOT EXISTS approved_by TEXT;

ALTER TABLE public.registered_users
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

-- ------------------------------------------------------------------------------
-- 4. Inspect and Remove All Relevant Legacy CHECK Constraints
-- ------------------------------------------------------------------------------
-- Inspect pg_constraint and dynamically identify every CHECK constraint affecting
-- registered_users.role or registered_users.account_status, regardless of its name
-- (e.g. check_user_role, check_account_status, registered_users_role_check,
-- registered_users_role_check1, chk_role, chk_account_status, val_role, etc.).
--
-- This guarantees that legacy constraints restricting role to ('analyst', 'admin')
-- cannot block the analyst-to-user normalization update.
--
-- Precision rule: Only drops constraints where contype = 'c' (CHECK) on registered_users
-- that target 'role' or 'account_status'. Strictly preserves:
--   - Primary keys (contype = 'p')
--   - Unique constraints (contype = 'u', e.g. registered_users_email_key)
--   - Foreign keys (contype = 'f')
--   - Check constraints on unrelated columns (e.g. email, timestamps)
DO $$
DECLARE
    r RECORD;
    v_dropped_count INTEGER := 0;
BEGIN
    FOR r IN (
        SELECT DISTINCT c.conname, pg_get_constraintdef(c.oid) AS def
        FROM pg_constraint c
        WHERE c.conrelid = 'public.registered_users'::regclass
          AND c.contype = 'c'
          AND (
              -- Match by explicit target names
              c.conname IN ('check_user_role', 'check_account_status')
              -- Match by column dependency via pg_depend
              OR EXISTS (
                  SELECT 1
                  FROM pg_depend d
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = d.refobjsubid
                  WHERE d.classid = 'pg_constraint'::regclass
                    AND d.objid = c.oid
                    AND d.refclassid = 'pg_class'::regclass
                    AND d.refobjid = c.conrelid
                    AND a.attname IN ('role', 'account_status')
              )
              -- Match by conkey column array (PostgreSQL 11+)
              OR EXISTS (
                  SELECT 1
                  FROM unnest(c.conkey) k
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k
                  WHERE a.attname IN ('role', 'account_status')
              )
              -- NOTE: Broad regex on constraint definition removed to eliminate false positives
              -- on string literals/unrelated expressions (e.g. CHECK (bio <> 'role')).
              -- Strict catalog dependencies (pg_depend and c.conkey) uniquely identify actual column references.
          )
    ) LOOP
        EXECUTE format('ALTER TABLE public.registered_users DROP CONSTRAINT IF EXISTS %I', r.conname);
        v_dropped_count := v_dropped_count + 1;
        RAISE NOTICE 'Dropped legacy check constraint: % (%)', r.conname, r.def;
    END LOOP;

    RAISE NOTICE 'Completed check constraint cleanup: % constraint(s) removed.', v_dropped_count;
END $$;

-- ------------------------------------------------------------------------------
-- 5. Data Normalization: Canonicalize 'analyst' to 'user' & Backfill Defaults
-- ------------------------------------------------------------------------------
-- Safe to execute because conflicting check constraints have been removed.
UPDATE public.registered_users
SET role = 'user'
WHERE role = 'analyst' OR role IS NULL;

ALTER TABLE public.registered_users
ALTER COLUMN role SET DEFAULT 'user';

ALTER TABLE public.registered_users
ALTER COLUMN role SET NOT NULL;

UPDATE public.registered_users
SET account_status = 'active'
WHERE account_status IS NULL;

ALTER TABLE public.registered_users
ALTER COLUMN account_status SET DEFAULT 'active';

ALTER TABLE public.registered_users
ALTER COLUMN account_status SET NOT NULL;

UPDATE public.registered_users
SET email_verified = true
WHERE email_verified IS NULL;

ALTER TABLE public.registered_users
ALTER COLUMN email_verified SET DEFAULT true;

ALTER TABLE public.registered_users
ALTER COLUMN email_verified SET NOT NULL;

UPDATE public.registered_users
SET updated_at = NOW()
WHERE updated_at IS NULL;

ALTER TABLE public.registered_users
ALTER COLUMN updated_at SET DEFAULT NOW();

ALTER TABLE public.registered_users
ALTER COLUMN updated_at SET NOT NULL;

-- ------------------------------------------------------------------------------
-- 6. Post-Normalization Data Audit
-- ------------------------------------------------------------------------------
-- Verify that 100% of existing rows strictly comply with target RBAC constraints.
-- If any record violates canonical role or status, raise exception to rollback.
DO $$
DECLARE
    v_bad_role_count INTEGER;
    v_bad_status_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_bad_role_count
    FROM public.registered_users
    WHERE role IS NULL OR role NOT IN ('user', 'admin');

    IF v_bad_role_count > 0 THEN
        RAISE EXCEPTION 'Post-normalization audit failed: % record(s) violate role IN (''user'', ''admin''). Aborting transaction.', v_bad_role_count;
    END IF;

    SELECT COUNT(*) INTO v_bad_status_count
    FROM public.registered_users
    WHERE account_status IS NULL OR account_status NOT IN ('active', 'pending', 'rejected', 'suspended');

    IF v_bad_status_count > 0 THEN
        RAISE EXCEPTION 'Post-normalization audit failed: % record(s) violate account_status IN (''active'', ''pending'', ''rejected'', ''suspended''). Aborting transaction.', v_bad_status_count;
    END IF;

    RAISE NOTICE 'Post-normalization data audit passed: 100%% of records comply with target RBAC schema.';
END $$;

-- ------------------------------------------------------------------------------
-- 7. Add Canonical Named CHECK Constraints
-- ------------------------------------------------------------------------------
ALTER TABLE public.registered_users
ADD CONSTRAINT check_user_role
CHECK (role IS NOT NULL AND role IN ('user', 'admin'));

ALTER TABLE public.registered_users
ADD CONSTRAINT check_account_status
CHECK (account_status IS NOT NULL AND account_status IN ('active', 'pending', 'rejected', 'suspended'));

-- ------------------------------------------------------------------------------
-- 8. Performance & Integrity Indexes
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_role_status
ON public.registered_users (role, account_status);

CREATE INDEX IF NOT EXISTS idx_users_email_lower
ON public.registered_users (LOWER(TRIM(email)));

CREATE INDEX IF NOT EXISTS idx_users_created_at
ON public.registered_users (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_email
ON public.password_reset_tokens (LOWER(TRIM(user_email)), used_at);

CREATE INDEX IF NOT EXISTS idx_work_hist_user_email
ON public.user_work_history (LOWER(TRIM(user_email)), created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_activity_log_created_at
ON public.admin_activity_log (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_activity_log_action
ON public.admin_activity_log (action);

CREATE INDEX IF NOT EXISTS idx_admin_activity_log_email
ON public.admin_activity_log (LOWER(TRIM(user_email)));

CREATE INDEX IF NOT EXISTS idx_admin_verify_tokens_jti
ON public.admin_verification_tokens (jti);

CREATE INDEX IF NOT EXISTS idx_admin_verify_tokens_email
ON public.admin_verification_tokens (LOWER(TRIM(user_email)), used_at);

-- ------------------------------------------------------------------------------
-- 9. Stored Functions (Advisory Lock, Search Path Fixed, Security Definer)
-- ------------------------------------------------------------------------------

-- 9.1 initialize_first_admin
CREATE OR REPLACE FUNCTION public.initialize_first_admin(
    p_id TEXT,
    p_email TEXT,
    p_name TEXT,
    p_password_hash TEXT,
    p_created_at TIMESTAMPTZ DEFAULT NOW()
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_admin_exists BOOLEAN;
    v_target_uuid UUID;
    v_new_user RECORD;
    v_existing_id UUID;
BEGIN
    -- Advisory lock serializes concurrent bootstrap calls
    PERFORM pg_advisory_xact_lock(hashtext('first_admin_setup_lock'));

    -- Check if ANY established administrator already exists on the platform
    SELECT EXISTS (
        SELECT 1
        FROM public.registered_users
        WHERE role = 'admin'
          AND (
              approved_by = 'initial_setup'
              OR account_status IN ('active', 'suspended', 'rejected')
          )
    ) INTO v_admin_exists;

    IF v_admin_exists THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Initial administrator setup has already been completed and is permanently disabled.'
        );
    END IF;

    -- Check for existing record by email
    SELECT id INTO v_existing_id
    FROM public.registered_users
    WHERE LOWER(TRIM(email)) = LOWER(TRIM(p_email));

    IF v_existing_id IS NOT NULL THEN
        -- Promote existing pending admin applicant if email matches
        IF EXISTS (
            SELECT 1
            FROM public.registered_users
            WHERE id = v_existing_id
              AND role = 'admin'
              AND account_status = 'pending'
        ) THEN
            UPDATE public.registered_users
            SET name = TRIM(p_name),
                password_hash = p_password_hash,
                account_status = 'active',
                email_verified = true,
                approved_by = 'initial_setup',
                approved_at = p_created_at,
                updated_at = p_created_at
            WHERE id = v_existing_id
            RETURNING * INTO v_new_user;

            RETURN jsonb_build_object(
                'success', true,
                'user_id', v_new_user.id::TEXT
            );
        ELSE
            RETURN jsonb_build_object(
                'success', false,
                'error', 'An account with this email address already exists.'
            );
        END IF;
    END IF;

    -- Safely parse or generate UUID for registered_users.id
    IF p_id IS NOT NULL AND TRIM(p_id) != '' THEN
        BEGIN
            v_target_uuid := TRIM(p_id)::UUID;
        EXCEPTION WHEN invalid_text_representation THEN
            v_target_uuid := gen_random_uuid();
        END;
    ELSE
        v_target_uuid := gen_random_uuid();
    END IF;

    INSERT INTO public.registered_users (
        id, email, name, password_hash, role, account_status, email_verified, approved_by, approved_at, updated_at, created_at
    ) VALUES (
        v_target_uuid, LOWER(TRIM(p_email)), TRIM(p_name), p_password_hash, 'admin', 'active', true, 'initial_setup', p_created_at, p_created_at, p_created_at
    )
    RETURNING * INTO v_new_user;

    RETURN jsonb_build_object(
        'success', true,
        'user_id', v_new_user.id::TEXT
    );
END;
$$;

-- 9.2 approve_admin_request
CREATE OR REPLACE FUNCTION public.approve_admin_request(
    p_user_id TEXT,
    p_approved_by TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_target_uuid UUID;
    v_updated RECORD;
BEGIN
    BEGIN
        v_target_uuid := TRIM(p_user_id)::UUID;
    EXCEPTION WHEN invalid_text_representation THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Invalid user ID format: must be a valid UUID.'
        );
    END;

    UPDATE public.registered_users
    SET account_status = 'active',
        approved_by = p_approved_by,
        approved_at = NOW(),
        updated_at = NOW()
    WHERE id = v_target_uuid
      AND role = 'admin'
      AND account_status = 'pending'
      AND email_verified = true
    RETURNING * INTO v_updated;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Application not eligible for approval: must be an administrator in pending status with verified email.'
        );
    END IF;

    RETURN jsonb_build_object(
        'success', true,
        'user_id', v_updated.id::TEXT,
        'status', v_updated.account_status
    );
END;
$$;

-- 9.3 reject_admin_request
CREATE OR REPLACE FUNCTION public.reject_admin_request(
    p_user_id TEXT,
    p_rejected_by TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_target_uuid UUID;
    v_updated RECORD;
BEGIN
    BEGIN
        v_target_uuid := TRIM(p_user_id)::UUID;
    EXCEPTION WHEN invalid_text_representation THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Invalid user ID format: must be a valid UUID.'
        );
    END;

    UPDATE public.registered_users
    SET account_status = 'rejected',
        approved_by = p_rejected_by,
        approved_at = NOW(),
        updated_at = NOW()
    WHERE id = v_target_uuid
      AND role = 'admin'
      AND account_status = 'pending'
    RETURNING * INTO v_updated;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Application not eligible for rejection: must be an administrator in pending status.'
        );
    END IF;

    RETURN jsonb_build_object(
        'success', true,
        'user_id', v_updated.id::TEXT,
        'status', v_updated.account_status
    );
END;
$$;

-- ------------------------------------------------------------------------------
-- 10. Review, Hardened RLS & Privilege Grants for ALL FIVE Sensitive Tables
-- ------------------------------------------------------------------------------
-- Sensitive Tables Governed:
--   1. public.registered_users
--   2. public.password_reset_tokens
--   3. public.user_work_history
--   4. public.admin_activity_log
--   5. public.admin_verification_tokens
--
-- Defense-in-depth Strategy:
-- 1) Inspect and drop ALL existing policies across all five sensitive tables.
-- 2) Enable and Force Row Level Security (RLS) on all five tables.
-- 3) Maintain default-deny RLS posture: NO policies granted to anon or authenticated.
-- 4) Revoke ALL table permissions from PUBLIC, anon, and authenticated.
-- 5) Grant ALL permissions exclusively to service_role (used by FastAPI backend) and postgres.

-- 10.1 Safely Remove Any Existing Policies Across All Five Sensitive Tables
DO $$
DECLARE
    pol RECORD;
    v_dropped_policies INTEGER := 0;
BEGIN
    FOR pol IN (
        SELECT schemaname, tablename, policyname
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN (
              'registered_users',
              'password_reset_tokens',
              'user_work_history',
              'admin_activity_log',
              'admin_verification_tokens'
          )
    ) LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I.%I', pol.policyname, pol.schemaname, pol.tablename);
        v_dropped_policies := v_dropped_policies + 1;
        RAISE NOTICE 'Dropped existing policy % on table %.%', pol.policyname, pol.schemaname, pol.tablename;
    END LOOP;
    RAISE NOTICE 'Policy cleanup complete: % existing policy/policies removed.', v_dropped_policies;
END $$;

-- Table 1: registered_users
ALTER TABLE public.registered_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.registered_users FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.registered_users FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE public.registered_users TO service_role, postgres;

-- Table 2: password_reset_tokens
ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_reset_tokens FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.password_reset_tokens FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE public.password_reset_tokens TO service_role, postgres;

-- Table 3: user_work_history
ALTER TABLE public.user_work_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_work_history FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.user_work_history FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE public.user_work_history TO service_role, postgres;

-- Table 4: admin_activity_log
ALTER TABLE public.admin_activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_activity_log FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.admin_activity_log FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE public.admin_activity_log TO service_role, postgres;

-- Table 5: admin_verification_tokens
ALTER TABLE public.admin_verification_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_verification_tokens FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.admin_verification_tokens FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE public.admin_verification_tokens TO service_role, postgres;

-- Secure SECURITY DEFINER functions: Revoke from PUBLIC, anon, authenticated; grant only to service_role, postgres
REVOKE ALL ON FUNCTION public.initialize_first_admin(TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.initialize_first_admin(TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ) TO service_role, postgres;

REVOKE ALL ON FUNCTION public.approve_admin_request(TEXT, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.approve_admin_request(TEXT, TEXT) TO service_role, postgres;

REVOKE ALL ON FUNCTION public.reject_admin_request(TEXT, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reject_admin_request(TEXT, TEXT) TO service_role, postgres;

-- ------------------------------------------------------------------------------
-- 11. Schema & Security Verification Audits (Run Within Transaction)
-- ------------------------------------------------------------------------------
DO $$
DECLARE
    v_missing_table TEXT;
    v_unsecured_table TEXT;
    v_remaining_policies INTEGER := 0;
    v_public_grant_count INTEGER := 0;
    v_service_role_grant_tables INTEGER := 0;
    v_public_func_grant_count INTEGER := 0;
    v_service_role_func_count INTEGER := 0;
BEGIN
    -- Verify all 5 tables exist
    FOR v_missing_table IN (
        SELECT t.tablename
        FROM (VALUES 
            ('registered_users'),
            ('password_reset_tokens'),
            ('user_work_history'),
            ('admin_activity_log'),
            ('admin_verification_tokens')
        ) AS t(tablename)
        WHERE NOT EXISTS (
            SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = t.tablename
        )
    ) LOOP
        RAISE EXCEPTION 'Schema verification failed: required table public.% does not exist.', v_missing_table;
    END LOOP;

    -- Verify RLS is both enabled (relrowsecurity) and forced (relforcerowsecurity) on all 5 tables
    FOR v_unsecured_table IN (
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN ('registered_users', 'password_reset_tokens', 'user_work_history', 'admin_activity_log', 'admin_verification_tokens')
          AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
    ) LOOP
        RAISE EXCEPTION 'Security verification failed: table public.% does not have RLS enabled and forced.', v_unsecured_table;
    END LOOP;

    -- Verify zero policies remain in pg_policies for all 5 sensitive tables (default-deny posture)
    SELECT COUNT(*) INTO v_remaining_policies
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename IN ('registered_users', 'password_reset_tokens', 'user_work_history', 'admin_activity_log', 'admin_verification_tokens');

    IF v_remaining_policies > 0 THEN
        RAISE EXCEPTION 'Security verification failed: % policy/policies still exist in pg_policies.', v_remaining_policies;
    END IF;

    -- Verify zero table privileges exist for anon, authenticated, or PUBLIC on the 5 sensitive tables
    SELECT COUNT(*) INTO v_public_grant_count
    FROM information_schema.table_privileges
    WHERE table_schema = 'public'
      AND table_name IN ('registered_users', 'password_reset_tokens', 'user_work_history', 'admin_activity_log', 'admin_verification_tokens')
      AND grantee IN ('anon', 'authenticated', 'PUBLIC');

    IF v_public_grant_count > 0 THEN
        RAISE EXCEPTION 'Security verification failed: % table privileges still granted to anon/authenticated/PUBLIC.', v_public_grant_count;
    END IF;

    -- Verify service_role holds permissions on all 5 sensitive tables
    SELECT COUNT(DISTINCT table_name) INTO v_service_role_grant_tables
    FROM information_schema.table_privileges
    WHERE table_schema = 'public'
      AND table_name IN ('registered_users', 'password_reset_tokens', 'user_work_history', 'admin_activity_log', 'admin_verification_tokens')
      AND grantee = 'service_role';

    IF v_service_role_grant_tables < 5 THEN
        RAISE EXCEPTION 'Security verification failed: service_role lacks table privileges on one or more sensitive tables (found % of 5).', v_service_role_grant_tables;
    END IF;

    -- Verify zero function execute privileges for anon, authenticated, or PUBLIC
    SELECT COUNT(*) INTO v_public_func_grant_count
    FROM information_schema.routine_privileges
    WHERE specific_schema = 'public'
      AND routine_name IN ('initialize_first_admin', 'approve_admin_request', 'reject_admin_request')
      AND grantee IN ('anon', 'authenticated', 'PUBLIC');

    IF v_public_func_grant_count > 0 THEN
        RAISE EXCEPTION 'Security verification failed: % stored function privilege(s) still granted to anon/authenticated/PUBLIC.', v_public_func_grant_count;
    END IF;

    -- Verify service_role holds execute privileges on all 3 stored functions
    SELECT COUNT(DISTINCT routine_name) INTO v_service_role_func_count
    FROM information_schema.routine_privileges
    WHERE specific_schema = 'public'
      AND routine_name IN ('initialize_first_admin', 'approve_admin_request', 'reject_admin_request')
      AND grantee = 'service_role'
      AND privilege_type = 'EXECUTE';

    IF v_service_role_func_count < 3 THEN
        RAISE EXCEPTION 'Security verification failed: service_role lacks execute privileges on stored functions (found % of 3).', v_service_role_func_count;
    END IF;

    RAISE NOTICE 'Schema and privilege verification passed: all 5 sensitive tables exist, RLS is active and forced, 0 permissive policies exist, and direct public/anon/authenticated access is completely blocked.';
END $$;

COMMIT;

-- ==============================================================================
-- Post-Migration Diagnostic Queries (Optional Inspection After COMMIT)
-- ==============================================================================
-- 1. Inspect RLS Status across all 5 sensitive tables
SELECT 
    schemaname,
    tablename,
    rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('registered_users', 'password_reset_tokens', 'user_work_history', 'admin_activity_log', 'admin_verification_tokens')
ORDER BY tablename;

-- 2. Inspect Active CHECK constraints on registered_users
SELECT
    conname AS constraint_name,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conrelid = 'public.registered_users'::regclass
  AND contype = 'c'
ORDER BY conname;

-- 3. Inspect Table Privileges (Confirm only service_role and postgres hold permissions)
SELECT
    table_name,
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public'
  AND table_name IN ('registered_users', 'password_reset_tokens', 'user_work_history', 'admin_activity_log', 'admin_verification_tokens')
ORDER BY table_name, grantee, privilege_type;

-- 4. Inspect Function Execution Privileges
SELECT
    routine_name,
    grantee,
    privilege_type
FROM information_schema.routine_privileges
WHERE specific_schema = 'public'
  AND routine_name IN ('initialize_first_admin', 'approve_admin_request', 'reject_admin_request')
ORDER BY routine_name, grantee;
