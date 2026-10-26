BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20261023_0001

CREATE TABLE stores (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    store_name VARCHAR(100) NOT NULL, 
    platform TEXT NOT NULL, 
    external_store_id VARCHAR(100), 
    owner_name VARCHAR(100) NOT NULL, 
    remark VARCHAR(4000), 
    currency TEXT NOT NULL, 
    timezone TEXT NOT NULL, 
    singleton_key INTEGER DEFAULT '1' NOT NULL, 
    CONSTRAINT pk_stores PRIMARY KEY (id), 
    CONSTRAINT ck_stores_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_stores_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_stores_platform_enum CHECK (platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')), 
    CONSTRAINT ck_stores_currency_enum CHECK (currency IN ('CNY')), 
    CONSTRAINT ck_stores_timezone_enum CHECK (timezone IN ('Asia/Shanghai')), 
    CONSTRAINT ck_stores_single_store CHECK (singleton_key = 1), 
    CONSTRAINT uq_stores_singleton_key UNIQUE (singleton_key)
);

CREATE TABLE model_configs (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    provider TEXT NOT NULL, 
    base_url VARCHAR(2048) NOT NULL, 
    model_name VARCHAR(200) NOT NULL, 
    capabilities JSONB NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    execution_mode TEXT NOT NULL, 
    request_timeout_sec INTEGER NOT NULL, 
    secret_env_name TEXT, 
    CONSTRAINT pk_model_configs PRIMARY KEY (id), 
    CONSTRAINT ck_model_configs_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_model_configs_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_model_configs_provider_enum CHECK (provider IN ('openai_compatible', 'image_provider', 'video_provider', 'demo')), 
    CONSTRAINT ck_model_configs_execution_mode_enum CHECK (execution_mode IN ('real', 'demo')), 
    CONSTRAINT ck_model_configs_request_timeout_sec_minimum CHECK (request_timeout_sec >= 10), 
    CONSTRAINT ck_model_configs_request_timeout_sec_maximum CHECK (request_timeout_sec <= 1800)
);

CREATE TABLE queue_settingss (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    text_concurrency INTEGER NOT NULL, 
    image_concurrency INTEGER NOT NULL, 
    video_concurrency INTEGER NOT NULL, 
    max_attempts INTEGER NOT NULL, 
    job_timeout_sec INTEGER NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_queue_settingss PRIMARY KEY (id), 
    CONSTRAINT ck_queue_settingss_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_queue_settingss_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_queue_settingss_text_concurrency_minimum CHECK (text_concurrency >= 1), 
    CONSTRAINT ck_queue_settingss_text_concurrency_maximum CHECK (text_concurrency <= 10), 
    CONSTRAINT ck_queue_settingss_image_concurrency_minimum CHECK (image_concurrency >= 1), 
    CONSTRAINT ck_queue_settingss_image_concurrency_maximum CHECK (image_concurrency <= 10), 
    CONSTRAINT ck_queue_settingss_video_concurrency_minimum CHECK (video_concurrency >= 1), 
    CONSTRAINT ck_queue_settingss_video_concurrency_maximum CHECK (video_concurrency <= 5), 
    CONSTRAINT ck_queue_settingss_max_attempts_minimum CHECK (max_attempts >= 1), 
    CONSTRAINT ck_queue_settingss_max_attempts_maximum CHECK (max_attempts <= 5), 
    CONSTRAINT ck_queue_settingss_job_timeout_sec_minimum CHECK (job_timeout_sec >= 60), 
    CONSTRAINT ck_queue_settingss_job_timeout_sec_maximum CHECK (job_timeout_sec <= 7200), 
    CONSTRAINT ck_queue_settingss_singleton CHECK (id = '00000000-0000-0000-0000-000000000001')
);

CREATE TABLE users (
    id UUID NOT NULL, 
    username VARCHAR(64) NOT NULL, 
    display_name VARCHAR(100) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    version INTEGER NOT NULL, 
    auth_version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT ck_users_ck_users_role CHECK (role IN ('admin','operator','viewer')), 
    CONSTRAINT ck_users_ck_users_status CHECK (status IN ('active','disabled')), 
    CONSTRAINT ck_users_ck_users_versions CHECK (version >= 1 AND auth_version >= 1), 
    CONSTRAINT uq_users_username UNIQUE (username)
);

CREATE TABLE login_limits (
    key VARCHAR(64) NOT NULL, 
    failures INTEGER NOT NULL, 
    window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_login_limits PRIMARY KEY (key)
);

CREATE INDEX ix_login_limits_window_start ON login_limits (window_start);

CREATE TABLE platform_accounts (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    store_id UUID NOT NULL, 
    platform TEXT NOT NULL, 
    account_name VARCHAR(100) NOT NULL, 
    auth_status TEXT NOT NULL, 
    auth_meta JSONB, 
    remark VARCHAR(4000), 
    CONSTRAINT pk_platform_accounts PRIMARY KEY (id), 
    CONSTRAINT ck_platform_accounts_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_platform_accounts_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_platform_accounts_platform_enum CHECK (platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')), 
    CONSTRAINT ck_platform_accounts_auth_status_enum CHECK (auth_status IN ('unconfigured', 'placeholder_authorized', 'expired', 'revoked')), 
    CONSTRAINT fk_platform_accounts_store_id_stores FOREIGN KEY(store_id) REFERENCES stores (id)
);

CREATE INDEX ix_platform_accounts_store_id ON platform_accounts (store_id);

CREATE TABLE products (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    store_id UUID NOT NULL, 
    platform TEXT NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    category VARCHAR(100) NOT NULL, 
    price NUMERIC(14, 2) NOT NULL, 
    cost NUMERIC(14, 2) NOT NULL, 
    target_audience VARCHAR(4000) NOT NULL, 
    selling_points JSONB NOT NULL, 
    product_url VARCHAR(2048), 
    image_file_ids JSONB NOT NULL, 
    status TEXT NOT NULL, 
    last_diagnosis_at TIMESTAMP WITH TIME ZONE, 
    last_review_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_products PRIMARY KEY (id), 
    CONSTRAINT ck_products_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_products_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_products_platform_enum CHECK (platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')), 
    CONSTRAINT ck_products_price_nonnegative CHECK (price >= 0), 
    CONSTRAINT ck_products_cost_nonnegative CHECK (cost >= 0), 
    CONSTRAINT ck_products_status_enum CHECK (status IN ('draft', 'active', 'inactive')), 
    CONSTRAINT fk_products_store_id_stores FOREIGN KEY(store_id) REFERENCES stores (id)
);

CREATE INDEX ix_products_store_id ON products (store_id);

CREATE TABLE system_settingss (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    text_model_config_id UUID, 
    image_model_config_id UUID, 
    video_model_config_id UUID, 
    demo_generation_enabled BOOLEAN NOT NULL, 
    demo_data_enabled BOOLEAN NOT NULL, 
    max_upload_image_bytes INTEGER NOT NULL, 
    max_upload_video_bytes INTEGER NOT NULL, 
    max_import_rows INTEGER NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_system_settingss PRIMARY KEY (id), 
    CONSTRAINT ck_system_settingss_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_system_settingss_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_system_settingss_max_upload_image_bytes_minimum CHECK (max_upload_image_bytes >= 1), 
    CONSTRAINT ck_system_settingss_max_upload_image_bytes_maximum CHECK (max_upload_image_bytes <= 20971520), 
    CONSTRAINT ck_system_settingss_max_upload_video_bytes_minimum CHECK (max_upload_video_bytes >= 1), 
    CONSTRAINT ck_system_settingss_max_upload_video_bytes_maximum CHECK (max_upload_video_bytes <= 524288000), 
    CONSTRAINT ck_system_settingss_max_import_rows_minimum CHECK (max_import_rows >= 1), 
    CONSTRAINT ck_system_settingss_max_import_rows_maximum CHECK (max_import_rows <= 10000), 
    CONSTRAINT ck_system_settingss_singleton CHECK (id = '00000000-0000-0000-0000-000000000001'), 
    CONSTRAINT fk_system_settingss_text_model_config_id_model_configs FOREIGN KEY(text_model_config_id) REFERENCES model_configs (id), 
    CONSTRAINT fk_system_settingss_image_model_config_id_model_configs FOREIGN KEY(image_model_config_id) REFERENCES model_configs (id), 
    CONSTRAINT fk_system_settingss_video_model_config_id_model_configs FOREIGN KEY(video_model_config_id) REFERENCES model_configs (id)
);

CREATE INDEX ix_system_settingss_image_model_config_id ON system_settingss (image_model_config_id);

CREATE INDEX ix_system_settingss_text_model_config_id ON system_settingss (text_model_config_id);

CREATE INDEX ix_system_settingss_video_model_config_id ON system_settingss (video_model_config_id);

CREATE TABLE audit_logs (
    id UUID NOT NULL, 
    actor_id UUID, 
    action VARCHAR(100) NOT NULL, 
    resource_type VARCHAR(100) NOT NULL, 
    resource_id UUID, 
    resource_version INTEGER, 
    request_id UUID NOT NULL, 
    outcome TEXT NOT NULL, 
    summary VARCHAR(4000) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_audit_logs PRIMARY KEY (id), 
    CONSTRAINT ck_audit_logs_resource_version_minimum CHECK (resource_version >= 1), 
    CONSTRAINT ck_audit_logs_resource_version_maximum CHECK (resource_version <= 2147483647), 
    CONSTRAINT ck_audit_logs_outcome_enum CHECK (outcome IN ('succeeded', 'rejected', 'failed')), 
    CONSTRAINT fk_audit_logs_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_audit_logs_actor_id ON audit_logs (actor_id);

CREATE TABLE idempotency_records (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    method VARCHAR(10) NOT NULL, 
    path VARCHAR(2048) NOT NULL, 
    key UUID NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    status INTEGER NOT NULL, 
    response JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_idempotency_records PRIMARY KEY (id), 
    CONSTRAINT uq_idempotency_scope UNIQUE (user_id, method, path, key), 
    CONSTRAINT fk_idempotency_records_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_idempotency_records_expires_at ON idempotency_records (expires_at);

CREATE TABLE login_sessions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    auth_version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_login_sessions PRIMARY KEY (id), 
    CONSTRAINT fk_login_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_login_sessions_expires_at ON login_sessions (expires_at);

CREATE INDEX ix_login_sessions_user_id ON login_sessions (user_id);

CREATE TABLE authorization_sessions (
    authorization_session_id UUID NOT NULL, 
    state VARCHAR(200) NOT NULL, 
    mode TEXT NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    authorization_url VARCHAR(2048), 
    account_id UUID NOT NULL, 
    consumed_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_authorization_sessions PRIMARY KEY (authorization_session_id), 
    CONSTRAINT ck_authorization_sessions_mode_enum CHECK (mode IN ('placeholder')), 
    CONSTRAINT uq_auth_placeholder_state UNIQUE (state), 
    CONSTRAINT fk_authorization_sessions_account_id_platform_accounts FOREIGN KEY(account_id) REFERENCES platform_accounts (id)
);

CREATE INDEX ix_authorization_sessions_account_id ON authorization_sessions (account_id);

CREATE TABLE skus (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    sku_code VARCHAR(64) NOT NULL, 
    sku_name VARCHAR(200) NOT NULL, 
    spec JSONB NOT NULL, 
    price NUMERIC(14, 2) NOT NULL, 
    cost NUMERIC(14, 2) NOT NULL, 
    status TEXT NOT NULL, 
    platform_sku_id VARCHAR(100), 
    CONSTRAINT pk_skus PRIMARY KEY (id), 
    CONSTRAINT ck_skus_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_skus_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_skus_price_nonnegative CHECK (price >= 0), 
    CONSTRAINT ck_skus_cost_nonnegative CHECK (cost >= 0), 
    CONSTRAINT ck_skus_status_enum CHECK (status IN ('active', 'inactive')), 
    CONSTRAINT uq_skus_code UNIQUE (sku_code), 
    CONSTRAINT fk_skus_product_id_products FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE INDEX ix_skus_product_id ON skus (product_id);

CREATE TABLE operating_rounds (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    objective VARCHAR(4000) NOT NULL, 
    round_no INTEGER NOT NULL, 
    previous_round_id UUID, 
    source_review_id UUID, 
    source_review_version INTEGER, 
    adopted_action_ids JSONB NOT NULL, 
    selected_diagnosis_id UUID, 
    selected_diagnosis_version INTEGER, 
    status TEXT NOT NULL, 
    stage TEXT NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    closed_at TIMESTAMP WITH TIME ZONE, 
    close_remark VARCHAR(4000), 
    CONSTRAINT pk_operating_rounds PRIMARY KEY (id), 
    CONSTRAINT ck_operating_rounds_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_operating_rounds_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_operating_rounds_round_no_minimum CHECK (round_no >= 1), 
    CONSTRAINT ck_operating_rounds_round_no_maximum CHECK (round_no <= 2147483647), 
    CONSTRAINT ck_operating_rounds_source_review_version_positive CHECK (source_review_version >= 1), 
    CONSTRAINT ck_operating_rounds_source_review_ref_complete CHECK ((source_review_id IS NULL) = (source_review_version IS NULL)), 
    CONSTRAINT ck_operating_rounds_selected_diagnosis_version_positive CHECK (selected_diagnosis_version >= 1), 
    CONSTRAINT ck_operating_rounds_selected_diagnosis_ref_complete CHECK ((selected_diagnosis_id IS NULL) = (selected_diagnosis_version IS NULL)), 
    CONSTRAINT ck_operating_rounds_status_enum CHECK (status IN ('active', 'completed', 'cancelled')), 
    CONSTRAINT ck_operating_rounds_stage_enum CHECK (stage IN ('draft', 'diagnosing', 'creative', 'generating', 'reviewing', 'planning', 'executing', 'analyzing', 'completed', 'cancelled')), 
    CONSTRAINT uq_round_product_number UNIQUE (product_id, round_no), 
    CONSTRAINT fk_operating_rounds_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_operating_rounds_previous_round_id_operating_rounds FOREIGN KEY(previous_round_id) REFERENCES operating_rounds (id)
);

CREATE UNIQUE INDEX uq_round_active_product ON operating_rounds (product_id) WHERE status = 'active';

CREATE INDEX ix_operating_rounds_selected_diagnosis_id ON operating_rounds (selected_diagnosis_id);

CREATE INDEX ix_operating_rounds_source_review_id ON operating_rounds (source_review_id);

CREATE INDEX ix_operating_rounds_previous_round_id ON operating_rounds (previous_round_id);

CREATE INDEX ix_operating_rounds_product_id ON operating_rounds (product_id);

CREATE TABLE files (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID, 
    file_name VARCHAR(255) NOT NULL, 
    content_type TEXT NOT NULL, 
    byte_size INTEGER NOT NULL, 
    sha256 TEXT NOT NULL, 
    purpose TEXT NOT NULL, 
    storage_status TEXT NOT NULL, 
    execution_mode TEXT NOT NULL, 
    CONSTRAINT pk_files PRIMARY KEY (id), 
    CONSTRAINT ck_files_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_files_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_files_content_type_enum CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')), 
    CONSTRAINT ck_files_byte_size_minimum CHECK (byte_size >= 1), 
    CONSTRAINT ck_files_byte_size_maximum CHECK (byte_size <= 524288000), 
    CONSTRAINT ck_files_purpose_enum CHECK (purpose IN ('product_image', 'reference', 'media', 'import')), 
    CONSTRAINT ck_files_storage_status_enum CHECK (storage_status IN ('available', 'quarantined')), 
    CONSTRAINT ck_files_execution_mode_enum CHECK (execution_mode IN ('real', 'demo')), 
    CONSTRAINT fk_files_product_id_products FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE INDEX ix_files_product_id ON files (product_id);

CREATE TABLE authorization_states (
    id UUID NOT NULL, 
    account_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    login_session_id UUID NOT NULL, 
    state_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_authorization_states PRIMARY KEY (id), 
    CONSTRAINT fk_authorization_states_account_id_platform_accounts FOREIGN KEY(account_id) REFERENCES platform_accounts (id), 
    CONSTRAINT fk_authorization_states_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), 
    CONSTRAINT fk_authorization_states_login_session_id_login_sessions FOREIGN KEY(login_session_id) REFERENCES login_sessions (id), 
    CONSTRAINT uq_authorization_states_state_hash UNIQUE (state_hash)
);

CREATE TABLE platform_mappings (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    platform TEXT NOT NULL, 
    platform_product_id VARCHAR(100) NOT NULL, 
    sku_id UUID, 
    platform_sku_id VARCHAR(100), 
    mapping_status TEXT NOT NULL, 
    CONSTRAINT pk_platform_mappings PRIMARY KEY (id), 
    CONSTRAINT ck_platform_mappings_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_platform_mappings_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_platform_mappings_platform_enum CHECK (platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')), 
    CONSTRAINT ck_platform_mappings_mapping_status_enum CHECK (mapping_status IN ('active', 'inactive')), 
    CONSTRAINT ck_platform_mappings_sku_mapping_pair CHECK ((sku_id IS NULL) = (platform_sku_id IS NULL)), 
    CONSTRAINT fk_platform_mappings_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_platform_mappings_sku_id_skus FOREIGN KEY(sku_id) REFERENCES skus (id)
);

CREATE UNIQUE INDEX uq_mapping_external_sku ON platform_mappings (platform, platform_sku_id) WHERE platform_sku_id IS NOT NULL;

CREATE INDEX ix_platform_mappings_sku_id ON platform_mappings (sku_id);

CREATE INDEX ix_platform_mappings_product_id ON platform_mappings (product_id);

CREATE TABLE inventories (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    sku_id UUID NOT NULL, 
    stock_qty INTEGER NOT NULL, 
    locked_qty INTEGER NOT NULL, 
    warning_threshold INTEGER NOT NULL, 
    location_text VARCHAR(200), 
    CONSTRAINT pk_inventories PRIMARY KEY (id), 
    CONSTRAINT ck_inventories_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_inventories_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_inventories_stock_qty_minimum CHECK (stock_qty >= 0), 
    CONSTRAINT ck_inventories_stock_qty_maximum CHECK (stock_qty <= 2147483647), 
    CONSTRAINT ck_inventories_locked_qty_minimum CHECK (locked_qty >= 0), 
    CONSTRAINT ck_inventories_locked_qty_maximum CHECK (locked_qty <= 0), 
    CONSTRAINT ck_inventories_warning_threshold_minimum CHECK (warning_threshold >= 0), 
    CONSTRAINT ck_inventories_warning_threshold_maximum CHECK (warning_threshold <= 2147483647), 
    CONSTRAINT uq_inventory_sku UNIQUE (sku_id), 
    CONSTRAINT ck_inventories_stock_locked CHECK (stock_qty >= locked_qty), 
    CONSTRAINT fk_inventories_sku_id_skus FOREIGN KEY(sku_id) REFERENCES skus (id)
);

CREATE INDEX ix_inventories_sku_id ON inventories (sku_id);

CREATE TABLE inventory_movements (
    id UUID NOT NULL, 
    sku_id UUID NOT NULL, 
    movement_type TEXT NOT NULL, 
    change_qty INTEGER NOT NULL, 
    before_qty INTEGER NOT NULL, 
    after_qty INTEGER NOT NULL, 
    reason_text VARCHAR(500) NOT NULL, 
    reference_text VARCHAR(200), 
    operator_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    inventory_version INTEGER NOT NULL, 
    CONSTRAINT pk_inventory_movements PRIMARY KEY (id), 
    CONSTRAINT ck_inventory_movements_movement_type_enum CHECK (movement_type IN ('increase', 'decrease')), 
    CONSTRAINT ck_inventory_movements_before_qty_minimum CHECK (before_qty >= 0), 
    CONSTRAINT ck_inventory_movements_before_qty_maximum CHECK (before_qty <= 2147483647), 
    CONSTRAINT ck_inventory_movements_after_qty_minimum CHECK (after_qty >= 0), 
    CONSTRAINT ck_inventory_movements_after_qty_maximum CHECK (after_qty <= 2147483647), 
    CONSTRAINT ck_inventory_movements_inventory_version_minimum CHECK (inventory_version >= 1), 
    CONSTRAINT ck_inventory_movements_inventory_version_maximum CHECK (inventory_version <= 2147483647), 
    CONSTRAINT fk_inventory_movements_sku_id_skus FOREIGN KEY(sku_id) REFERENCES skus (id), 
    CONSTRAINT fk_inventory_movements_operator_id_users FOREIGN KEY(operator_id) REFERENCES users (id)
);

CREATE INDEX ix_inventory_movements_operator_id ON inventory_movements (operator_id);

CREATE INDEX ix_inventory_movements_sku_id ON inventory_movements (sku_id);

CREATE TABLE competitors (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    platform TEXT NOT NULL, 
    url VARCHAR(2048), 
    price NUMERIC(14, 2), 
    sales_hint VARCHAR(500), 
    title VARCHAR(500), 
    main_image_file_id UUID, 
    selling_points JSONB NOT NULL, 
    review_keywords JSONB NOT NULL, 
    status TEXT NOT NULL, 
    CONSTRAINT pk_competitors PRIMARY KEY (id), 
    CONSTRAINT ck_competitors_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_competitors_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_competitors_platform_enum CHECK (platform IN ('taobao', 'tmall', 'jd', 'pdd', 'douyin', 'kuaishou', 'other')), 
    CONSTRAINT ck_competitors_price_nonnegative CHECK (price >= 0), 
    CONSTRAINT ck_competitors_status_enum CHECK (status IN ('active', 'archived')), 
    CONSTRAINT fk_competitors_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_competitors_main_image_file_id_files FOREIGN KEY(main_image_file_id) REFERENCES files (id)
);

CREATE INDEX ix_competitors_main_image_file_id ON competitors (main_image_file_id);

CREATE INDEX ix_competitors_product_id ON competitors (product_id);

CREATE TABLE round_snapshots (
    id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    product JSONB NOT NULL, 
    skus JSONB NOT NULL, 
    competitors JSONB NOT NULL, 
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID, 
    CONSTRAINT pk_round_snapshots PRIMARY KEY (id), 
    CONSTRAINT fk_round_snapshots_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id), 
    CONSTRAINT fk_round_snapshots_product_id_products FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE INDEX ix_round_snapshots_product_id ON round_snapshots (product_id);

CREATE INDEX ix_round_snapshots_round_id ON round_snapshots (round_id);

CREATE TABLE promotion_links (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    link_name VARCHAR(100) NOT NULL, 
    target_url VARCHAR(2048) NOT NULL, 
    utm JSONB NOT NULL, 
    scene_text VARCHAR(500) NOT NULL, 
    status TEXT NOT NULL, 
    tracking_code VARCHAR(64) NOT NULL, 
    short_url VARCHAR(2048) NOT NULL, 
    click_count INTEGER NOT NULL, 
    CONSTRAINT pk_promotion_links PRIMARY KEY (id), 
    CONSTRAINT ck_promotion_links_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_promotion_links_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_promotion_links_status_enum CHECK (status IN ('active', 'disabled')), 
    CONSTRAINT ck_promotion_links_click_count_minimum CHECK (click_count >= 0), 
    CONSTRAINT ck_promotion_links_click_count_maximum CHECK (click_count <= 2147483647), 
    CONSTRAINT uq_promotion_tracking UNIQUE (tracking_code), 
    CONSTRAINT fk_promotion_links_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_promotion_links_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id)
);

CREATE INDEX ix_promotion_links_round_id ON promotion_links (round_id);

CREATE INDEX ix_promotion_links_product_id ON promotion_links (product_id);

CREATE TABLE review_reports (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    period_start DATE NOT NULL, 
    period_end DATE NOT NULL, 
    granularity TEXT NOT NULL, 
    experiment_ids JSONB NOT NULL, 
    performance_record_refs JSONB NOT NULL, 
    metric_snapshot JSONB NOT NULL, 
    content JSONB NOT NULL, 
    provenance JSONB NOT NULL, 
    CONSTRAINT pk_review_reports PRIMARY KEY (id), 
    CONSTRAINT ck_review_reports_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_review_reports_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_review_reports_granularity_enum CHECK (granularity IN ('product_day', 'experiment_day')), 
    CONSTRAINT ck_review_reports_period_dates CHECK (period_end >= period_start), 
    CONSTRAINT fk_review_reports_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_review_reports_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id)
);

CREATE INDEX ix_review_reports_product_id ON review_reports (product_id);

CREATE INDEX ix_review_reports_round_id ON review_reports (round_id);

CREATE TABLE resource_revisions (
    revision_id UUID NOT NULL, 
    resource_type TEXT NOT NULL, 
    resource_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_by UUID, 
    change_reason VARCHAR(4000), 
    resource JSONB NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID, 
    CONSTRAINT pk_resource_revisions PRIMARY KEY (revision_id), 
    CONSTRAINT ck_resource_revisions_resource_type_enum CHECK (resource_type IN ('diagnosis', 'creative_plan', 'ad_recommendation', 'review_report')), 
    CONSTRAINT ck_resource_revisions_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_resource_revisions_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT uq_resource_revision_version UNIQUE (resource_type, resource_id, version), 
    CONSTRAINT fk_resource_revisions_created_by_users FOREIGN KEY(created_by) REFERENCES users (id), 
    CONSTRAINT fk_resource_revisions_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_resource_revisions_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id)
);

CREATE INDEX ix_resource_revisions_product_id ON resource_revisions (product_id);

CREATE INDEX ix_resource_revisions_round_id ON resource_revisions (round_id);

CREATE INDEX ix_resource_revisions_created_by ON resource_revisions (created_by);

CREATE TABLE import_batches (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    import_type TEXT NOT NULL, 
    file_id UUID NOT NULL, 
    store_id UUID NOT NULL, 
    product_id UUID, 
    round_id UUID, 
    status TEXT NOT NULL, 
    total_rows INTEGER NOT NULL, 
    valid_rows INTEGER NOT NULL, 
    invalid_rows INTEGER NOT NULL, 
    succeeded_rows INTEGER NOT NULL, 
    failed_rows INTEGER NOT NULL, 
    preview_token VARCHAR(200), 
    preview_expires_at TIMESTAMP WITH TIME ZONE, 
    errors_count INTEGER NOT NULL, 
    error_message VARCHAR(4000), 
    CONSTRAINT pk_import_batches PRIMARY KEY (id), 
    CONSTRAINT ck_import_batches_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_import_batches_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_import_batches_import_type_enum CHECK (import_type IN ('products', 'sku_inventory', 'performance_records', 'platform_mappings')), 
    CONSTRAINT ck_import_batches_status_enum CHECK (status IN ('validating', 'preview_ready', 'committing', 'succeeded', 'partially_succeeded', 'failed', 'expired')), 
    CONSTRAINT ck_import_batches_total_rows_minimum CHECK (total_rows >= 0), 
    CONSTRAINT ck_import_batches_total_rows_maximum CHECK (total_rows <= 2147483647), 
    CONSTRAINT ck_import_batches_valid_rows_minimum CHECK (valid_rows >= 0), 
    CONSTRAINT ck_import_batches_valid_rows_maximum CHECK (valid_rows <= 2147483647), 
    CONSTRAINT ck_import_batches_invalid_rows_minimum CHECK (invalid_rows >= 0), 
    CONSTRAINT ck_import_batches_invalid_rows_maximum CHECK (invalid_rows <= 2147483647), 
    CONSTRAINT ck_import_batches_succeeded_rows_minimum CHECK (succeeded_rows >= 0), 
    CONSTRAINT ck_import_batches_succeeded_rows_maximum CHECK (succeeded_rows <= 2147483647), 
    CONSTRAINT ck_import_batches_failed_rows_minimum CHECK (failed_rows >= 0), 
    CONSTRAINT ck_import_batches_failed_rows_maximum CHECK (failed_rows <= 2147483647), 
    CONSTRAINT ck_import_batches_errors_count_minimum CHECK (errors_count >= 0), 
    CONSTRAINT ck_import_batches_errors_count_maximum CHECK (errors_count <= 2147483647), 
    CONSTRAINT fk_import_batches_file_id_files FOREIGN KEY(file_id) REFERENCES files (id), 
    CONSTRAINT fk_import_batches_store_id_stores FOREIGN KEY(store_id) REFERENCES stores (id), 
    CONSTRAINT fk_import_batches_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_import_batches_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id)
);

CREATE INDEX ix_import_batches_store_id ON import_batches (store_id);

CREATE INDEX ix_import_batches_product_id ON import_batches (product_id);

CREATE INDEX ix_import_batches_file_id ON import_batches (file_id);

CREATE INDEX ix_import_batches_round_id ON import_batches (round_id);

CREATE TABLE file_storage (
    file_id UUID NOT NULL, 
    bucket VARCHAR(255) NOT NULL, 
    object_name VARCHAR(1024) NOT NULL, 
    width INTEGER, 
    height INTEGER, 
    duration_seconds NUMERIC(12, 3), 
    checksum VARCHAR(64), 
    CONSTRAINT pk_file_storage PRIMARY KEY (file_id), 
    CONSTRAINT uq_file_storage_object UNIQUE (bucket, object_name), 
    CONSTRAINT fk_file_storage_file_id_files FOREIGN KEY(file_id) REFERENCES files (id)
);

CREATE TABLE competitor_monitors (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    competitor_id UUID NOT NULL, 
    monitor_status TEXT NOT NULL, 
    interval_minutes INTEGER NOT NULL, 
    next_run_at TIMESTAMP WITH TIME ZONE, 
    last_error VARCHAR(4000), 
    CONSTRAINT pk_competitor_monitors PRIMARY KEY (id), 
    CONSTRAINT ck_competitor_monitors_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_competitor_monitors_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_competitor_monitors_monitor_status_enum CHECK (monitor_status IN ('active', 'paused')), 
    CONSTRAINT ck_competitor_monitors_interval_minutes_minimum CHECK (interval_minutes >= 60), 
    CONSTRAINT ck_competitor_monitors_interval_minutes_maximum CHECK (interval_minutes <= 2147483647), 
    CONSTRAINT uq_monitor_competitor UNIQUE (competitor_id), 
    CONSTRAINT fk_competitor_monitors_competitor_id_competitors FOREIGN KEY(competitor_id) REFERENCES competitors (id)
);

CREATE INDEX ix_competitor_monitors_competitor_id ON competitor_monitors (competitor_id);

CREATE TABLE diagnoses (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    snapshot_id UUID NOT NULL, 
    content JSONB NOT NULL, 
    provenance JSONB NOT NULL, 
    edit_remark VARCHAR(4000), 
    CONSTRAINT pk_diagnoses PRIMARY KEY (id), 
    CONSTRAINT ck_diagnoses_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_diagnoses_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT fk_diagnoses_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_diagnoses_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id), 
    CONSTRAINT fk_diagnoses_snapshot_id_round_snapshots FOREIGN KEY(snapshot_id) REFERENCES round_snapshots (id)
);

CREATE INDEX ix_diagnoses_snapshot_id ON diagnoses (snapshot_id);

CREATE INDEX ix_diagnoses_round_id ON diagnoses (round_id);

CREATE INDEX ix_diagnoses_product_id ON diagnoses (product_id);

CREATE TABLE import_state (
    import_id UUID NOT NULL, 
    context JSONB NOT NULL, 
    rows JSONB NOT NULL, 
    commit_options JSONB NOT NULL, 
    CONSTRAINT pk_import_state PRIMARY KEY (import_id), 
    CONSTRAINT fk_import_state_import_id_import_batches FOREIGN KEY(import_id) REFERENCES import_batches (id)
);

CREATE TABLE click_events (
    id UUID NOT NULL, 
    link_id UUID NOT NULL, 
    clicked_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    counted BOOLEAN NOT NULL, 
    request_fingerprint VARCHAR(64), 
    ip_hash VARCHAR(64), 
    CONSTRAINT pk_click_events PRIMARY KEY (id), 
    CONSTRAINT fk_click_events_link_id_promotion_links FOREIGN KEY(link_id) REFERENCES promotion_links (id)
);

CREATE INDEX ix_click_dedup_window ON click_events (link_id, request_fingerprint, clicked_at);

CREATE INDEX ix_click_events_link_id ON click_events (link_id);

CREATE TABLE monitor_snapshots (
    id UUID NOT NULL, 
    monitor_id UUID NOT NULL, 
    competitor_id UUID NOT NULL, 
    price NUMERIC(14, 2), 
    sales_hint VARCHAR(500), 
    selling_points JSONB NOT NULL, 
    source_url VARCHAR(2048) NOT NULL, 
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    completeness TEXT NOT NULL, 
    warnings JSONB NOT NULL, 
    CONSTRAINT pk_monitor_snapshots PRIMARY KEY (id), 
    CONSTRAINT ck_monitor_snapshots_price_nonnegative CHECK (price >= 0), 
    CONSTRAINT ck_monitor_snapshots_completeness_enum CHECK (completeness IN ('complete', 'partial')), 
    CONSTRAINT fk_monitor_snapshots_monitor_id_competitor_monitors FOREIGN KEY(monitor_id) REFERENCES competitor_monitors (id), 
    CONSTRAINT fk_monitor_snapshots_competitor_id_competitors FOREIGN KEY(competitor_id) REFERENCES competitors (id)
);

CREATE INDEX ix_monitor_snapshots_monitor_id ON monitor_snapshots (monitor_id);

CREATE INDEX ix_monitor_snapshots_competitor_id ON monitor_snapshots (competitor_id);

CREATE TABLE creative_plans (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    plan_type TEXT NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    content JSONB NOT NULL, 
    rationale_text VARCHAR(4000) NOT NULL, 
    status TEXT NOT NULL, 
    diagnosis_id UUID NOT NULL, 
    diagnosis_version INTEGER NOT NULL, 
    snapshot_id UUID NOT NULL, 
    provenance JSONB NOT NULL, 
    CONSTRAINT pk_creative_plans PRIMARY KEY (id), 
    CONSTRAINT ck_creative_plans_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_creative_plans_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_creative_plans_plan_type_enum CHECK (plan_type IN ('main_image', 'video_script', 'title')), 
    CONSTRAINT ck_creative_plans_status_enum CHECK (status IN ('draft', 'selected', 'archived')), 
    CONSTRAINT ck_creative_plans_diagnosis_version_positive CHECK (diagnosis_version >= 1), 
    CONSTRAINT fk_creative_plans_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_creative_plans_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id), 
    CONSTRAINT fk_creative_plans_diagnosis_id_diagnoses FOREIGN KEY(diagnosis_id) REFERENCES diagnoses (id), 
    CONSTRAINT fk_creative_plans_snapshot_id_round_snapshots FOREIGN KEY(snapshot_id) REFERENCES round_snapshots (id)
);

CREATE INDEX ix_creative_plans_snapshot_id ON creative_plans (snapshot_id);

CREATE UNIQUE INDEX uq_plan_selected_kind ON creative_plans (round_id, plan_type) WHERE status = 'selected';

CREATE INDEX ix_creative_plans_round_id ON creative_plans (round_id);

CREATE INDEX ix_creative_plans_diagnosis_id ON creative_plans (diagnosis_id);

CREATE INDEX ix_creative_plans_product_id ON creative_plans (product_id);

CREATE TABLE ad_recommendations (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    diagnosis_id UUID NOT NULL, 
    diagnosis_version INTEGER NOT NULL, 
    content JSONB NOT NULL, 
    budget_cap NUMERIC(14, 2) NOT NULL, 
    daily_cap NUMERIC(14, 2) NOT NULL, 
    duration_days INTEGER NOT NULL, 
    confirm_status TEXT NOT NULL, 
    latest_confirmation JSONB, 
    provenance JSONB NOT NULL, 
    CONSTRAINT pk_ad_recommendations PRIMARY KEY (id), 
    CONSTRAINT ck_ad_recommendations_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_ad_recommendations_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_ad_recommendations_diagnosis_version_positive CHECK (diagnosis_version >= 1), 
    CONSTRAINT ck_ad_recommendations_budget_cap_nonnegative CHECK (budget_cap >= 0), 
    CONSTRAINT ck_ad_recommendations_daily_cap_nonnegative CHECK (daily_cap >= 0), 
    CONSTRAINT ck_ad_recommendations_duration_days_minimum CHECK (duration_days >= 1), 
    CONSTRAINT ck_ad_recommendations_duration_days_maximum CHECK (duration_days <= 90), 
    CONSTRAINT ck_ad_recommendations_confirm_status_enum CHECK (confirm_status IN ('pending', 'confirmed', 'rejected')), 
    CONSTRAINT fk_ad_recommendations_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_ad_recommendations_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id), 
    CONSTRAINT fk_ad_recommendations_diagnosis_id_diagnoses FOREIGN KEY(diagnosis_id) REFERENCES diagnoses (id)
);

CREATE INDEX ix_ad_recommendations_product_id ON ad_recommendations (product_id);

CREATE INDEX ix_ad_recommendations_diagnosis_id ON ad_recommendations (diagnosis_id);

CREATE INDEX ix_ad_recommendations_round_id ON ad_recommendations (round_id);

CREATE TABLE generation_jobs (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID, 
    round_id UUID, 
    creative_plan_id UUID, 
    job_kind TEXT NOT NULL, 
    job_status TEXT NOT NULL, 
    dispatch_status TEXT NOT NULL, 
    execution_mode TEXT NOT NULL, 
    attempts INTEGER NOT NULL, 
    max_attempts INTEGER NOT NULL, 
    cancellation_requested BOOLEAN NOT NULL, 
    result_resources JSONB NOT NULL, 
    error_code VARCHAR(100), 
    error_message VARCHAR(4000), 
    next_run_at TIMESTAMP WITH TIME ZONE, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    progress INTEGER NOT NULL, 
    creative_plan_version INTEGER, 
    model_config_id UUID, 
    source_url VARCHAR(2048), 
    submitted_by UUID, 
    queued_at TIMESTAMP WITH TIME ZONE, 
    deadline_at TIMESTAMP WITH TIME ZONE, 
    model_config_version INTEGER, 
    CONSTRAINT pk_generation_jobs PRIMARY KEY (id), 
    CONSTRAINT ck_generation_jobs_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_generation_jobs_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_generation_jobs_job_kind_enum CHECK (job_kind IN ('diagnosis', 'main_image_plan', 'video_script', 'title_plan', 'image', 'video', 'ad_recommendation', 'ad_experiment', 'review_report', 'public_link_parse', 'asset_sync', 'timeout_sweep', 'competitor_monitor_sweep', 'demo_data')), 
    CONSTRAINT ck_generation_jobs_job_status_enum CHECK (job_status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled', 'timeout')), 
    CONSTRAINT ck_generation_jobs_dispatch_status_enum CHECK (dispatch_status IN ('awaiting_dispatch', 'queued', 'dispatched')), 
    CONSTRAINT ck_generation_jobs_execution_mode_enum CHECK (execution_mode IN ('real', 'demo')), 
    CONSTRAINT ck_generation_jobs_attempts_minimum CHECK (attempts >= 0), 
    CONSTRAINT ck_generation_jobs_attempts_maximum CHECK (attempts <= 2147483647), 
    CONSTRAINT ck_generation_jobs_max_attempts_minimum CHECK (max_attempts >= 1), 
    CONSTRAINT ck_generation_jobs_max_attempts_maximum CHECK (max_attempts <= 5), 
    CONSTRAINT ck_generation_jobs_progress_minimum CHECK (progress >= 0), 
    CONSTRAINT ck_generation_jobs_progress_maximum CHECK (progress <= 100), 
    CONSTRAINT ck_generation_jobs_creative_plan_version_minimum CHECK (creative_plan_version >= 1), 
    CONSTRAINT ck_generation_jobs_creative_plan_version_maximum CHECK (creative_plan_version <= 2147483647), 
    CONSTRAINT ck_generation_jobs_model_config_version_minimum CHECK (model_config_version >= 1), 
    CONSTRAINT ck_generation_jobs_model_config_version_maximum CHECK (model_config_version <= 2147483647), 
    CONSTRAINT fk_generation_jobs_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_generation_jobs_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id), 
    CONSTRAINT fk_generation_jobs_creative_plan_id_creative_plans FOREIGN KEY(creative_plan_id) REFERENCES creative_plans (id), 
    CONSTRAINT fk_generation_jobs_model_config_id_model_configs FOREIGN KEY(model_config_id) REFERENCES model_configs (id), 
    CONSTRAINT fk_generation_jobs_submitted_by_users FOREIGN KEY(submitted_by) REFERENCES users (id)
);

CREATE INDEX ix_generation_jobs_creative_plan_id ON generation_jobs (creative_plan_id);

CREATE INDEX ix_generation_jobs_model_config_id ON generation_jobs (model_config_id);

CREATE INDEX ix_generation_jobs_round_id ON generation_jobs (round_id);

CREATE INDEX ix_generation_jobs_product_id ON generation_jobs (product_id);

CREATE INDEX ix_generation_jobs_submitted_by ON generation_jobs (submitted_by);

CREATE TABLE confirmations (
    id UUID NOT NULL, 
    resource_version INTEGER NOT NULL, 
    decision TEXT NOT NULL, 
    operator_id UUID NOT NULL, 
    remark VARCHAR(2000) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    recommendation_id UUID NOT NULL, 
    product_id UUID, 
    round_id UUID, 
    CONSTRAINT pk_confirmations PRIMARY KEY (id), 
    CONSTRAINT ck_confirmations_resource_version_minimum CHECK (resource_version >= 1), 
    CONSTRAINT ck_confirmations_resource_version_maximum CHECK (resource_version <= 2147483647), 
    CONSTRAINT ck_confirmations_decision_enum CHECK (decision IN ('confirmed', 'rejected')), 
    CONSTRAINT fk_confirmations_operator_id_users FOREIGN KEY(operator_id) REFERENCES users (id), 
    CONSTRAINT fk_confirmations_recommendation_id_ad_recommendations FOREIGN KEY(recommendation_id) REFERENCES ad_recommendations (id), 
    CONSTRAINT fk_confirmations_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_confirmations_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id)
);

CREATE INDEX ix_confirmations_operator_id ON confirmations (operator_id);

CREATE INDEX ix_confirmations_product_id ON confirmations (product_id);

CREATE INDEX ix_confirmations_recommendation_id ON confirmations (recommendation_id);

CREATE INDEX ix_confirmations_round_id ON confirmations (round_id);

CREATE TABLE parse_results (
    id UUID NOT NULL, 
    source_url VARCHAR(2048) NOT NULL, 
    name VARCHAR(200), 
    title VARCHAR(500), 
    price NUMERIC(14, 2), 
    sales_hint VARCHAR(500), 
    selling_points JSONB NOT NULL, 
    candidate_image_urls JSONB NOT NULL, 
    missing_fields JSONB NOT NULL, 
    warnings JSONB NOT NULL, 
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    job_id UUID NOT NULL, 
    CONSTRAINT pk_parse_results PRIMARY KEY (id), 
    CONSTRAINT ck_parse_results_price_nonnegative CHECK (price >= 0), 
    CONSTRAINT uq_parse_results_job_id UNIQUE (job_id), 
    CONSTRAINT fk_parse_results_job_id_generation_jobs FOREIGN KEY(job_id) REFERENCES generation_jobs (id)
);

CREATE TABLE job_events (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    sequence INTEGER NOT NULL, 
    attempt INTEGER NOT NULL, 
    event_type TEXT NOT NULL, 
    event_message VARCHAR(4000) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_job_events PRIMARY KEY (id), 
    CONSTRAINT ck_job_events_sequence_minimum CHECK (sequence >= 1), 
    CONSTRAINT ck_job_events_sequence_maximum CHECK (sequence <= 2147483647), 
    CONSTRAINT ck_job_events_attempt_minimum CHECK (attempt >= 0), 
    CONSTRAINT ck_job_events_attempt_maximum CHECK (attempt <= 2147483647), 
    CONSTRAINT ck_job_events_event_type_enum CHECK (event_type IN ('enqueued', 'running', 'succeeded', 'failed', 'retry_scheduled', 'retry_requested', 'cancellation_requested', 'cancelled', 'timeout', 'progress', 'late_result_ignored')), 
    CONSTRAINT uq_job_event_sequence UNIQUE (job_id, sequence), 
    CONSTRAINT fk_job_events_job_id_generation_jobs FOREIGN KEY(job_id) REFERENCES generation_jobs (id)
);

CREATE INDEX ix_job_events_job_id ON job_events (job_id);

CREATE TABLE assets (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    creative_plan_id UUID, 
    creative_plan_version INTEGER, 
    file_id UUID NOT NULL, 
    asset_type TEXT NOT NULL, 
    origin TEXT NOT NULL, 
    model_name VARCHAR(200), 
    source_job_id UUID, 
    width INTEGER NOT NULL, 
    height INTEGER NOT NULL, 
    duration_sec INTEGER, 
    review_status TEXT NOT NULL, 
    reviewed_by UUID, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    review_remark VARCHAR(4000), 
    version_no INTEGER NOT NULL, 
    parent_asset_id UUID, 
    execution_mode TEXT NOT NULL, 
    usage_scene TEXT NOT NULL, 
    score INTEGER, 
    tags JSONB NOT NULL, 
    remark VARCHAR(4000), 
    output_index INTEGER, 
    CONSTRAINT pk_assets PRIMARY KEY (id), 
    CONSTRAINT ck_assets_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_assets_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_assets_creative_plan_version_minimum CHECK (creative_plan_version >= 1), 
    CONSTRAINT ck_assets_creative_plan_version_maximum CHECK (creative_plan_version <= 2147483647), 
    CONSTRAINT ck_assets_asset_type_enum CHECK (asset_type IN ('image', 'video')), 
    CONSTRAINT ck_assets_origin_enum CHECK (origin IN ('generated', 'uploaded')), 
    CONSTRAINT ck_assets_width_minimum CHECK (width >= 1), 
    CONSTRAINT ck_assets_width_maximum CHECK (width <= 2147483647), 
    CONSTRAINT ck_assets_height_minimum CHECK (height >= 1), 
    CONSTRAINT ck_assets_height_maximum CHECK (height <= 2147483647), 
    CONSTRAINT ck_assets_duration_sec_minimum CHECK (duration_sec >= 1), 
    CONSTRAINT ck_assets_duration_sec_maximum CHECK (duration_sec <= 2147483647), 
    CONSTRAINT ck_assets_review_status_enum CHECK (review_status IN ('pending', 'approved', 'rejected')), 
    CONSTRAINT ck_assets_version_no_minimum CHECK (version_no >= 1), 
    CONSTRAINT ck_assets_version_no_maximum CHECK (version_no <= 2147483647), 
    CONSTRAINT ck_assets_execution_mode_enum CHECK (execution_mode IN ('real', 'demo')), 
    CONSTRAINT ck_assets_usage_scene_enum CHECK (usage_scene IN ('main_image', 'detail_image', 'short_video', 'ad_creative', 'other')), 
    CONSTRAINT ck_assets_score_minimum CHECK (score >= 1), 
    CONSTRAINT ck_assets_score_maximum CHECK (score <= 5), 
    CONSTRAINT uq_asset_job_output UNIQUE (source_job_id, output_index), 
    CONSTRAINT ck_assets_output_index_nonnegative CHECK (output_index IS NULL OR output_index >= 0), 
    CONSTRAINT ck_assets_creative_ref_complete CHECK ((creative_plan_id IS NULL) = (creative_plan_version IS NULL)), 
    CONSTRAINT fk_assets_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_assets_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id), 
    CONSTRAINT fk_assets_creative_plan_id_creative_plans FOREIGN KEY(creative_plan_id) REFERENCES creative_plans (id), 
    CONSTRAINT fk_assets_file_id_files FOREIGN KEY(file_id) REFERENCES files (id), 
    CONSTRAINT fk_assets_source_job_id_generation_jobs FOREIGN KEY(source_job_id) REFERENCES generation_jobs (id), 
    CONSTRAINT fk_assets_reviewed_by_users FOREIGN KEY(reviewed_by) REFERENCES users (id), 
    CONSTRAINT fk_assets_parent_asset_id_assets FOREIGN KEY(parent_asset_id) REFERENCES assets (id)
);

CREATE INDEX ix_assets_product_id ON assets (product_id);

CREATE INDEX ix_assets_parent_asset_id ON assets (parent_asset_id);

CREATE INDEX ix_assets_source_job_id ON assets (source_job_id);

CREATE INDEX ix_assets_reviewed_by ON assets (reviewed_by);

CREATE INDEX ix_assets_file_id ON assets (file_id);

CREATE INDEX ix_assets_creative_plan_id ON assets (creative_plan_id);

CREATE INDEX ix_assets_round_id ON assets (round_id);

CREATE TABLE job_runtime (
    job_id UUID NOT NULL, 
    input JSONB NOT NULL, 
    lease_token UUID, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    heartbeat_at TIMESTAMP WITH TIME ZONE, 
    provider_state JSONB NOT NULL, 
    result_state JSONB NOT NULL, 
    CONSTRAINT pk_job_runtime PRIMARY KEY (job_id), 
    CONSTRAINT fk_job_runtime_job_id_generation_jobs FOREIGN KEY(job_id) REFERENCES generation_jobs (id)
);

CREATE INDEX ix_job_runtime_lease_until ON job_runtime (lease_until);

CREATE TABLE job_outputs (
    id UUID NOT NULL, 
    job_id UUID NOT NULL, 
    output_index INTEGER NOT NULL, 
    resource_type VARCHAR(100) NOT NULL, 
    resource_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_job_outputs PRIMARY KEY (id), 
    CONSTRAINT uq_job_output_number UNIQUE (job_id, output_index), 
    CONSTRAINT fk_job_outputs_job_id_generation_jobs FOREIGN KEY(job_id) REFERENCES generation_jobs (id)
);

CREATE TABLE monitor_dispatches (
    id UUID NOT NULL, 
    monitor_id UUID NOT NULL, 
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    job_id UUID NOT NULL, 
    CONSTRAINT pk_monitor_dispatches PRIMARY KEY (id), 
    CONSTRAINT uq_monitor_dispatch_time UNIQUE (monitor_id, scheduled_at), 
    CONSTRAINT fk_monitor_dispatches_monitor_id_competitor_monitors FOREIGN KEY(monitor_id) REFERENCES competitor_monitors (id), 
    CONSTRAINT fk_monitor_dispatches_job_id_generation_jobs FOREIGN KEY(job_id) REFERENCES generation_jobs (id)
);

CREATE TABLE model_calls (
    id UUID NOT NULL, 
    job_id UUID, 
    model_config_id UUID, 
    model_config_version INTEGER, 
    provider VARCHAR(100) NOT NULL, 
    model_name VARCHAR(200) NOT NULL, 
    prompt_version VARCHAR(100) NOT NULL, 
    request_id VARCHAR(200), 
    input_tokens INTEGER, 
    output_tokens INTEGER, 
    duration_ms INTEGER, 
    outcome VARCHAR(32) NOT NULL, 
    error_code VARCHAR(100), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_model_calls PRIMARY KEY (id), 
    CONSTRAINT fk_model_calls_job_id_generation_jobs FOREIGN KEY(job_id) REFERENCES generation_jobs (id), 
    CONSTRAINT fk_model_calls_model_config_id_model_configs FOREIGN KEY(model_config_id) REFERENCES model_configs (id)
);

CREATE INDEX ix_model_calls_job_id ON model_calls (job_id);

CREATE TABLE ad_experiments (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    experiment_name VARCHAR(200) NOT NULL, 
    target_text VARCHAR(4000) NOT NULL, 
    audience_text VARCHAR(4000) NOT NULL, 
    budget_amount NUMERIC(14, 2) NOT NULL, 
    daily_cap NUMERIC(14, 2) NOT NULL, 
    success_metric TEXT NOT NULL, 
    target_value NUMERIC(18, 6) NOT NULL, 
    hypothesis_text VARCHAR(4000) NOT NULL, 
    related_asset_id UUID NOT NULL, 
    related_asset_version INTEGER NOT NULL, 
    related_link_id UUID NOT NULL, 
    title_plan_id UUID, 
    title_plan_version INTEGER, 
    planned_start_date DATE NOT NULL, 
    planned_end_date DATE NOT NULL, 
    recommendation_id UUID NOT NULL, 
    recommendation_version INTEGER NOT NULL, 
    experiment_status TEXT NOT NULL, 
    confirmed_by UUID, 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    external_campaign_id VARCHAR(200), 
    actual_start_at TIMESTAMP WITH TIME ZONE, 
    actual_end_at TIMESTAMP WITH TIME ZONE, 
    last_transition_remark VARCHAR(4000), 
    execution_mode TEXT NOT NULL, 
    CONSTRAINT pk_ad_experiments PRIMARY KEY (id), 
    CONSTRAINT ck_ad_experiments_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_ad_experiments_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_ad_experiments_budget_amount_nonnegative CHECK (budget_amount >= 0), 
    CONSTRAINT ck_ad_experiments_daily_cap_nonnegative CHECK (daily_cap >= 0), 
    CONSTRAINT ck_ad_experiments_success_metric_enum CHECK (success_metric IN ('ctr', 'conversion_rate', 'roas', 'cpa')), 
    CONSTRAINT ck_ad_experiments_target_value_nonnegative CHECK (target_value >= 0), 
    CONSTRAINT ck_ad_experiments_related_asset_version_positive CHECK (related_asset_version >= 1), 
    CONSTRAINT ck_ad_experiments_title_plan_version_positive CHECK (title_plan_version >= 1), 
    CONSTRAINT ck_ad_experiments_title_plan_ref_complete CHECK ((title_plan_id IS NULL) = (title_plan_version IS NULL)), 
    CONSTRAINT ck_ad_experiments_recommendation_version_positive CHECK (recommendation_version >= 1), 
    CONSTRAINT ck_ad_experiments_experiment_status_enum CHECK (experiment_status IN ('draft', 'confirmed', 'running', 'finished', 'cancelled')), 
    CONSTRAINT ck_ad_experiments_execution_mode_enum CHECK (execution_mode IN ('real', 'demo')), 
    CONSTRAINT ck_ad_experiments_planned_dates CHECK (planned_end_date >= planned_start_date), 
    CONSTRAINT ck_ad_experiments_actual_dates CHECK (actual_end_at IS NULL OR actual_start_at IS NULL OR actual_end_at >= actual_start_at), 
    CONSTRAINT fk_ad_experiments_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_ad_experiments_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id), 
    CONSTRAINT fk_ad_experiments_related_asset_id_assets FOREIGN KEY(related_asset_id) REFERENCES assets (id), 
    CONSTRAINT fk_ad_experiments_related_link_id_promotion_links FOREIGN KEY(related_link_id) REFERENCES promotion_links (id), 
    CONSTRAINT fk_ad_experiments_title_plan_id_creative_plans FOREIGN KEY(title_plan_id) REFERENCES creative_plans (id), 
    CONSTRAINT fk_ad_experiments_recommendation_id_ad_recommendations FOREIGN KEY(recommendation_id) REFERENCES ad_recommendations (id), 
    CONSTRAINT fk_ad_experiments_confirmed_by_users FOREIGN KEY(confirmed_by) REFERENCES users (id)
);

CREATE INDEX ix_ad_experiments_confirmed_by ON ad_experiments (confirmed_by);

CREATE INDEX ix_ad_experiments_recommendation_id ON ad_experiments (recommendation_id);

CREATE INDEX ix_ad_experiments_title_plan_id ON ad_experiments (title_plan_id);

CREATE INDEX ix_ad_experiments_round_id ON ad_experiments (round_id);

CREATE INDEX ix_ad_experiments_product_id ON ad_experiments (product_id);

CREATE INDEX ix_ad_experiments_related_link_id ON ad_experiments (related_link_id);

CREATE INDEX ix_ad_experiments_related_asset_id ON ad_experiments (related_asset_id);

CREATE TABLE performance_records (
    id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    product_id UUID NOT NULL, 
    round_id UUID NOT NULL, 
    granularity TEXT NOT NULL, 
    record_date DATE NOT NULL, 
    experiment_id UUID, 
    source TEXT NOT NULL, 
    impressions BIGINT NOT NULL, 
    clicks BIGINT NOT NULL, 
    conversions BIGINT NOT NULL, 
    spend NUMERIC(14, 2) NOT NULL, 
    revenue NUMERIC(14, 2) NOT NULL, 
    notes VARCHAR(4000), 
    creative_plan_id UUID, 
    creative_plan_version INTEGER, 
    generated_asset_id UUID, 
    generated_asset_version INTEGER, 
    promotion_link_id UUID, 
    ctr NUMERIC(18, 6), 
    conversion_rate NUMERIC(18, 6), 
    roas NUMERIC(18, 6), 
    cpa NUMERIC(14, 2), 
    roi NUMERIC(18, 6), 
    import_id UUID, 
    voided BOOLEAN NOT NULL, 
    void_reason VARCHAR(4000), 
    CONSTRAINT pk_performance_records PRIMARY KEY (id), 
    CONSTRAINT ck_performance_records_version_minimum CHECK (version >= 1), 
    CONSTRAINT ck_performance_records_version_maximum CHECK (version <= 2147483647), 
    CONSTRAINT ck_performance_records_granularity_enum CHECK (granularity IN ('product_day', 'experiment_day')), 
    CONSTRAINT ck_performance_records_source_enum CHECK (source IN ('manual', 'import')), 
    CONSTRAINT ck_performance_records_impressions_minimum CHECK (impressions >= 0), 
    CONSTRAINT ck_performance_records_impressions_maximum CHECK (impressions <= 9007199254740991), 
    CONSTRAINT ck_performance_records_clicks_minimum CHECK (clicks >= 0), 
    CONSTRAINT ck_performance_records_clicks_maximum CHECK (clicks <= 9007199254740991), 
    CONSTRAINT ck_performance_records_conversions_minimum CHECK (conversions >= 0), 
    CONSTRAINT ck_performance_records_conversions_maximum CHECK (conversions <= 9007199254740991), 
    CONSTRAINT ck_performance_records_spend_nonnegative CHECK (spend >= 0), 
    CONSTRAINT ck_performance_records_revenue_nonnegative CHECK (revenue >= 0), 
    CONSTRAINT ck_performance_records_creative_plan_version_positive CHECK (creative_plan_version >= 1), 
    CONSTRAINT ck_performance_records_creative_plan_ref_complete CHECK ((creative_plan_id IS NULL) = (creative_plan_version IS NULL)), 
    CONSTRAINT ck_performance_records_generated_asset_version_positive CHECK (generated_asset_version >= 1), 
    CONSTRAINT ck_performance_records_generated_asset_ref_complete CHECK ((generated_asset_id IS NULL) = (generated_asset_version IS NULL)), 
    CONSTRAINT ck_performance_records_ctr_nonnegative CHECK (ctr >= 0), 
    CONSTRAINT ck_performance_records_conversion_rate_nonnegative CHECK (conversion_rate >= 0), 
    CONSTRAINT ck_performance_records_roas_nonnegative CHECK (roas >= 0), 
    CONSTRAINT ck_performance_records_cpa_nonnegative CHECK (cpa >= 0), 
    CONSTRAINT ck_performance_records_roi_reserved_null CHECK (roi IS NULL), 
    CONSTRAINT ck_performance_records_granularity_reference CHECK ((granularity = 'product_day' AND experiment_id IS NULL) OR (granularity = 'experiment_day' AND experiment_id IS NOT NULL)), 
    CONSTRAINT ck_performance_records_metric_counts CHECK (clicks <= impressions AND conversions <= clicks), 
    CONSTRAINT fk_performance_records_product_id_products FOREIGN KEY(product_id) REFERENCES products (id), 
    CONSTRAINT fk_performance_records_round_id_operating_rounds FOREIGN KEY(round_id) REFERENCES operating_rounds (id), 
    CONSTRAINT fk_performance_records_experiment_id_ad_experiments FOREIGN KEY(experiment_id) REFERENCES ad_experiments (id), 
    CONSTRAINT fk_performance_records_creative_plan_id_creative_plans FOREIGN KEY(creative_plan_id) REFERENCES creative_plans (id), 
    CONSTRAINT fk_performance_records_generated_asset_id_assets FOREIGN KEY(generated_asset_id) REFERENCES assets (id), 
    CONSTRAINT fk_performance_records_promotion_link_id_promotion_links FOREIGN KEY(promotion_link_id) REFERENCES promotion_links (id), 
    CONSTRAINT fk_performance_records_import_id_import_batches FOREIGN KEY(import_id) REFERENCES import_batches (id)
);

CREATE INDEX ix_performance_records_experiment_id ON performance_records (experiment_id);

CREATE INDEX ix_performance_records_round_id ON performance_records (round_id);

CREATE INDEX ix_performance_records_promotion_link_id ON performance_records (promotion_link_id);

CREATE INDEX ix_performance_records_product_id ON performance_records (product_id);

CREATE INDEX ix_performance_records_import_id ON performance_records (import_id);

CREATE INDEX ix_performance_records_generated_asset_id ON performance_records (generated_asset_id);

CREATE INDEX ix_performance_records_creative_plan_id ON performance_records (creative_plan_id);

CREATE UNIQUE INDEX uq_performance_experiment_day ON performance_records (experiment_id, record_date) WHERE NOT voided AND granularity = 'experiment_day';

CREATE UNIQUE INDEX uq_performance_product_day ON performance_records (product_id, record_date) WHERE NOT voided AND granularity = 'product_day';

CREATE TABLE performance_revisions (
    id UUID NOT NULL, 
    record_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    resource JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_by UUID, 
    CONSTRAINT pk_performance_revisions PRIMARY KEY (id), 
    CONSTRAINT uq_performance_revision_version UNIQUE (record_id, version), 
    CONSTRAINT fk_performance_revisions_record_id_performance_records FOREIGN KEY(record_id) REFERENCES performance_records (id), 
    CONSTRAINT fk_performance_revisions_created_by_users FOREIGN KEY(created_by) REFERENCES users (id)
);

ALTER TABLE operating_rounds ADD CONSTRAINT fk_operating_rounds_source_review_id_review_reports FOREIGN KEY(source_review_id) REFERENCES review_reports (id);

ALTER TABLE operating_rounds ADD CONSTRAINT fk_operating_rounds_selected_diagnosis_id_diagnoses FOREIGN KEY(selected_diagnosis_id) REFERENCES diagnoses (id);

CREATE FUNCTION commerce_reject_immutable_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'immutable history cannot be updated or deleted' USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON resource_revisions FOR EACH ROW EXECUTE FUNCTION commerce_reject_immutable_change();

CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON round_snapshots FOR EACH ROW EXECUTE FUNCTION commerce_reject_immutable_change();

CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON performance_revisions FOR EACH ROW EXECUTE FUNCTION commerce_reject_immutable_change();

CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON job_outputs FOR EACH ROW EXECUTE FUNCTION commerce_reject_immutable_change();

CREATE FUNCTION commerce_protect_job_input() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.input IS DISTINCT FROM OLD.input OR NEW.job_id IS DISTINCT FROM OLD.job_id THEN
        RAISE EXCEPTION 'job input snapshot is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER immutable_job_input BEFORE UPDATE ON job_runtime FOR EACH ROW EXECUTE FUNCTION commerce_protect_job_input();

INSERT INTO alembic_version (version_num) VALUES ('20261023_0001') RETURNING alembic_version.version_num;

-- Running upgrade 20261023_0001 -> 20261023_0002

ALTER TABLE performance_records DROP CONSTRAINT ck_performance_records_metric_counts;

UPDATE alembic_version SET version_num='20261023_0002' WHERE alembic_version.version_num = '20261023_0001';

-- Running upgrade 20261023_0002 -> 20261023_0003

ALTER TABLE system_settingss RENAME TO system_settings;

ALTER TABLE queue_settingss RENAME TO queue_settings;

UPDATE alembic_version SET version_num='20261023_0003' WHERE alembic_version.version_num = '20261023_0002';

COMMIT;

