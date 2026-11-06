CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS source_files (
 path text PRIMARY KEY, sha256 text NOT NULL, imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS units (
 id text PRIMARY KEY, session integer NOT NULL CHECK(session BETWEEN 1 AND 6),
 title text NOT NULL, original json NOT NULL, sha256 text NOT NULL,
 source_path text NOT NULL REFERENCES source_files(path), pointer text NOT NULL,
 metadata jsonb NOT NULL, active boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS evidence (
 key text PRIMARY KEY, session integer NOT NULL CHECK(session BETWEEN 1 AND 6), original json NOT NULL
);
CREATE TABLE IF NOT EXISTS unit_revisions (
 unit_id text NOT NULL, sha256 text NOT NULL, original json NOT NULL,
 source_path text NOT NULL, source_sha256 text NOT NULL, pointer text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(unit_id,sha256)
);
CREATE TABLE IF NOT EXISTS unit_evidence (
 unit_id text REFERENCES units(id), source_key text REFERENCES evidence(key), PRIMARY KEY(unit_id,source_key)
);
CREATE TABLE IF NOT EXISTS chunks (
 id text PRIMARY KEY, unit_id text NOT NULL REFERENCES units(id), section text NOT NULL,
 text text NOT NULL, sha256 text NOT NULL, tokens integer NOT NULL,
 search tsvector GENERATED ALWAYS AS (to_tsvector('spanish', text)) STORED,
 active boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS chunks_search ON chunks USING gin(search);
CREATE INDEX IF NOT EXISTS chunks_unit ON chunks(unit_id);
CREATE TABLE IF NOT EXISTS embedding_cache (
 content_hash text NOT NULL, model text NOT NULL, dimensions integer NOT NULL,
 embedding vector NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(content_hash,model,dimensions), CHECK(vector_dims(embedding)=dimensions)
);
CREATE TABLE IF NOT EXISTS edges (
 source_id text REFERENCES units(id), target_id text REFERENCES units(id),
 kind text NOT NULL, provenance text NOT NULL, status text NOT NULL,
 PRIMARY KEY(source_id,target_id,kind)
);
CREATE TABLE IF NOT EXISTS memory (
 id uuid PRIMARY KEY, namespace text NOT NULL CHECK(namespace IN ('user','working')),
 key text NOT NULL, version integer NOT NULL, value jsonb NOT NULL,
 status text NOT NULL CHECK(status IN ('proposed','confirmed')),
 author text NOT NULL, evidence text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(namespace,key,version), CHECK(namespace='user' OR status='proposed')
);
CREATE TABLE IF NOT EXISTS usage_ledger (
 id uuid PRIMARY KEY, provider text NOT NULL, purpose text NOT NULL,
 reserved_usd numeric NOT NULL CHECK(reserved_usd>=0), actual_usd numeric,
 status text NOT NULL CHECK(status IN ('reserved','complete','uncertain','rejected')),
 usage jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE usage_ledger ADD COLUMN IF NOT EXISTS request_hash text;
CREATE TABLE IF NOT EXISTS runs (
 id uuid PRIMARY KEY, agent text NOT NULL, task text NOT NULL,
 status text NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
