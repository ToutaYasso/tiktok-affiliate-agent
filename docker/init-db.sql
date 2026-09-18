-- Initialisation base affiliate_agent
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    asin VARCHAR(50),
    title TEXT NOT NULL,
    price DECIMAL(10,2),
    commission_rate DECIMAL(5,2),
    affiliate_link TEXT,
    category VARCHAR(100),
    score DECIMAL(5,2),
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    script TEXT,
    audio_url TEXT,
    video_url TEXT,
    blob_path TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    tiktok_video_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tiktok_metrics (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id),
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    watch_rate DECIMAL(5,2),
    ctr DECIMAL(5,2),
    affiliate_clicks INTEGER DEFAULT 0,
    affiliate_sales INTEGER DEFAULT 0,
    revenue DECIMAL(10,2) DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_rules (
    id SERIAL PRIMARY KEY,
    rule_type VARCHAR(100),
    rule_description TEXT,
    confidence DECIMAL(5,2),
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_embedding ON products USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_rules_embedding ON agent_rules USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
