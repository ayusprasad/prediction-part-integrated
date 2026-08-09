-- SQLite fallback schema for the RAG service.
-- Used only when PostgreSQL/pgvector is unavailable. The application creates
-- this automatically in Sujit/data/rag_vectors.sqlite3; this file exists for
-- audit and portable setup, not for a PostgreSQL/DBeaver connection.

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    document_name TEXT,
    document_type TEXT,
    document_hash TEXT,
    title TEXT,
    language TEXT,
    file_size INTEGER,
    page_count INTEGER,
    character_count INTEGER,
    word_count INTEGER,
    access_scope TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_name TEXT,
    folder_path TEXT,
    page_number INTEGER,
    heading TEXT,
    language TEXT,
    parent_text TEXT,
    child_text TEXT,
    embedding TEXT NOT NULL,
    tsv TEXT
);

CREATE TABLE IF NOT EXISTS user_chunks (
    chunk_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    doc_name TEXT,
    folder_path TEXT,
    page_number INTEGER,
    heading TEXT,
    language TEXT,
    parent_text TEXT,
    child_text TEXT,
    embedding TEXT NOT NULL,
    tsv TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_chunks_user_id ON user_chunks(user_id);
