-- Run after installing pgvector in the PostgreSQL server.
-- This migration only creates the isolated RAG schema; public business tables
-- remain the source of truth and are not changed.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE IF NOT EXISTS rag.documents (
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
    created_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rag.chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_name TEXT,
    folder_path TEXT,
    page_number INTEGER,
    heading TEXT,
    language TEXT,
    parent_text TEXT,
    child_text TEXT,
    embedding vector(1024),
    tsv tsvector
);

CREATE TABLE IF NOT EXISTS rag.user_chunks (
    chunk_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    doc_name TEXT,
    folder_path TEXT,
    page_number INTEGER,
    heading TEXT,
    language TEXT,
    parent_text TEXT,
    child_text TEXT,
    embedding vector(1024),
    tsv tsvector
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding ON rag.chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_rag_user_chunks_embedding ON rag.user_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_rag_user_chunks_user_id ON rag.user_chunks(user_id);
