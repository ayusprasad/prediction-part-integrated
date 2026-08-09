-- RAG PostgreSQL/pgvector runtime reference queries
--
-- Used by app/services/postgres_service.py when POSTGRES_SCHEMA points to a
-- PostgreSQL schema with pgvector enabled. Replace `rag` only when the local
-- POSTGRES_SCHEMA setting uses another schema. Values must stay parameterised.

-- name: detect_pgvector
SELECT to_regtype('vector') IS NOT NULL AS pgvector_available;

-- name: upsert_document
INSERT INTO rag.documents (
    document_id, document_name, document_type, document_hash, title, language,
    file_size, page_count, character_count, word_count, access_scope, created_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (document_id)
DO UPDATE SET document_name = EXCLUDED.document_name;

-- name: upsert_shared_chunk
INSERT INTO rag.chunks (
    chunk_id, doc_name, folder_path, page_number, heading, language,
    parent_text, child_text, embedding, tsv
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, to_tsvector('english', %s))
ON CONFLICT (chunk_id)
DO UPDATE SET
    child_text = EXCLUDED.child_text,
    embedding = EXCLUDED.embedding;

-- name: upsert_user_chunk
INSERT INTO rag.user_chunks (
    chunk_id, user_id, doc_name, folder_path, page_number, heading, language,
    parent_text, child_text, embedding, tsv
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, to_tsvector('english', %s))
ON CONFLICT (chunk_id)
DO UPDATE SET
    child_text = EXCLUDED.child_text,
    embedding = EXCLUDED.embedding;

-- name: semantic_search_shared_chunks
-- Parameters: query embedding twice, result limit.
SELECT
    chunk_id, doc_name, folder_path, page_number, heading, language,
    parent_text, child_text,
    embedding <=> %s::vector AS distance
FROM rag.chunks
ORDER BY embedding <=> %s::vector
LIMIT %s;

-- name: semantic_search_user_chunks
-- Parameters: query embedding, user ID, query embedding, result limit.
SELECT
    chunk_id, doc_name, folder_path, page_number, heading, language,
    parent_text, child_text,
    embedding <=> %s::vector AS distance
FROM rag.user_chunks
WHERE user_id = %s
ORDER BY embedding <=> %s::vector
LIMIT %s;

-- name: user_document_inventory
-- Parameter 1: user ID.
SELECT
    doc_name,
    COUNT(*) AS chunk_count,
    MAX(folder_path) AS folder_path,
    MIN(page_number) AS min_page,
    MAX(page_number) AS max_page
FROM rag.user_chunks
WHERE user_id = %s
GROUP BY doc_name
ORDER BY doc_name;
