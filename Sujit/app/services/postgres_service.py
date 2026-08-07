"""RAG storage with PostgreSQL/pgvector and a transparent local fallback.

Business data remains in PostgreSQL.  When pgvector is unavailable, only RAG
embeddings are stored in a local SQLite file so the application can still run;
no business tables are copied or modified.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class PostgreSQLService:
    def __init__(self):
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.dbname = os.getenv("POSTGRES_DB", "postgres")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD", "")
        self.schema = os.getenv("POSTGRES_SCHEMA", "rag")
        self.connection = psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            options=f"-c search_path={self.schema},public",
        )
        self.cursor = self.connection.cursor()
        self.pgvector_enabled = self._detect_pgvector()
        self.sqlite = None
        if self.pgvector_enabled:
            self.ensure_pg_tables()
            self.backend = "postgresql+pgvector"
        else:
            self._open_sqlite_fallback()
            self.backend = "sqlite-cosine-fallback"
        print(f"Connected to PostgreSQL {self.host}:{self.port}/{self.dbname}; RAG backend: {self.backend}.")

    def _detect_pgvector(self) -> bool:
        try:
            self.cursor.execute("SELECT to_regtype('vector') IS NOT NULL")
            return bool(self.cursor.fetchone()[0])
        except Exception:
            self.connection.rollback()
            return False

    def _open_sqlite_fallback(self):
        data_dir = Path(__file__).resolve().parents[2] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite = sqlite3.connect(str(data_dir / "rag_vectors.sqlite3"), check_same_thread=False)
        self.sqlite.row_factory = sqlite3.Row
        self.sqlite.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY, document_name TEXT, document_type TEXT,
                document_hash TEXT, title TEXT, language TEXT, file_size INTEGER,
                page_count INTEGER, character_count INTEGER, word_count INTEGER,
                access_scope TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY, doc_name TEXT, folder_path TEXT,
                page_number INTEGER, heading TEXT, language TEXT, parent_text TEXT,
                child_text TEXT, embedding TEXT NOT NULL, tsv TEXT
            );
            CREATE TABLE IF NOT EXISTS user_chunks (
                chunk_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, doc_name TEXT,
                folder_path TEXT, page_number INTEGER, heading TEXT, language TEXT,
                parent_text TEXT, child_text TEXT, embedding TEXT NOT NULL, tsv TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_user_chunks_user_id ON user_chunks(user_id);
        """)
        self.sqlite.commit()

    def ensure_pg_tables(self):
        self.cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')
        self.cursor.execute(f'''CREATE TABLE IF NOT EXISTS "{self.schema}".documents (
            document_id TEXT PRIMARY KEY, document_name TEXT, document_type TEXT,
            document_hash TEXT, title TEXT, language TEXT, file_size INTEGER,
            page_count INTEGER, character_count INTEGER, word_count INTEGER,
            access_scope TEXT, created_at TIMESTAMPTZ
        )''')
        for table, user_column in (("chunks", ""), ("user_chunks", "user_id TEXT NOT NULL,")):
            extra = "" if not user_column else user_column
            self.cursor.execute(f'''CREATE TABLE IF NOT EXISTS "{self.schema}".{table} (
                chunk_id TEXT PRIMARY KEY, {extra} doc_name TEXT, folder_path TEXT,
                page_number INTEGER, heading TEXT, language TEXT, parent_text TEXT,
                child_text TEXT, embedding vector(1024), tsv tsvector
            )''')
        self.cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{self.schema}_user_chunks_user_id ON "{self.schema}".user_chunks(user_id)')
        self.connection.commit()

    @staticmethod
    def _vector(value):
        if isinstance(value, str):
            return json.loads(value)
        return list(value or [])

    @staticmethod
    def _cosine(a, b):
        numerator = sum(x * y for x, y in zip(a, b))
        denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
        return numerator / denominator if denominator else 0.0

    def save_document(self, document):
        values = (
            document["document_id"], document["document_name"], document["document_type"],
            document["metadata"].get("document_hash"), document["metadata"].get("title"),
            document["language"], document["metadata"].get("file_size"), document["page_count"],
            document["metadata"].get("character_count"), document["metadata"].get("word_count"),
            document["access_scope"], document["metadata"].get("created_at"),
        )
        if self.pgvector_enabled:
            self.cursor.execute(f'''INSERT INTO "{self.schema}".documents
                (document_id, document_name, document_type, document_hash, title, language,
                 file_size, page_count, character_count, word_count, access_scope, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (document_id) DO UPDATE SET document_name=EXCLUDED.document_name''', values)
            self.connection.commit()
        else:
            self.sqlite.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", values)
            self.sqlite.commit()

    def _save_chunks(self, table, chunks, user_id=None):
        for chunk in chunks:
            child = chunk.get("child_text") or chunk.get("text", "")
            parent = chunk.get("parent_text") or child
            values = (chunk["chunk_id"], *( (user_id,) if user_id is not None else ()),
                      chunk.get("doc_name") or chunk.get("document_name", ""), chunk.get("folder_path", ""),
                      chunk.get("page_number"), chunk.get("heading") or "Untitled", chunk.get("language") or "en",
                      parent, child, self._vector(chunk.get("embedding")), child)
            if self.pgvector_enabled:
                vector = str(values[-2])
                if user_id is None:
                    sql = f'''INSERT INTO "{self.schema}".{table}
                        (chunk_id,doc_name,folder_path,page_number,heading,language,parent_text,child_text,embedding,tsv)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,to_tsvector('english',%s))
                        ON CONFLICT (chunk_id) DO UPDATE SET child_text=EXCLUDED.child_text, embedding=EXCLUDED.embedding'''
                    params = values[:-2] + (vector, values[-1])
                else:
                    sql = f'''INSERT INTO "{self.schema}".{table}
                        (chunk_id,user_id,doc_name,folder_path,page_number,heading,language,parent_text,child_text,embedding,tsv)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,to_tsvector('english',%s))
                        ON CONFLICT (chunk_id) DO UPDATE SET child_text=EXCLUDED.child_text, embedding=EXCLUDED.embedding'''
                    params = values[:-2] + (vector, values[-1])
                self.cursor.execute(sql, params)
            else:
                if user_id is None:
                    sqlite_values = values[:-2] + (json.dumps(values[-2]), values[-1])
                    self.sqlite.execute("INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)", sqlite_values)
                else:
                    sqlite_values = values[:-2] + (json.dumps(values[-2]), values[-1])
                    self.sqlite.execute("INSERT OR REPLACE INTO user_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)", sqlite_values)
        if self.pgvector_enabled:
            self.connection.commit()
        else:
            self.sqlite.commit()

    def save_chunks(self, chunks):
        self._save_chunks("chunks", chunks)

    def save_user_chunks(self, user_id, chunks):
        self._save_chunks("user_chunks", chunks, user_id=user_id)

    def _search(self, table, query_embedding, top_k=5, user_id=None):
        emb = self._vector(query_embedding)
        if self.pgvector_enabled:
            where = "WHERE user_id = %s" if user_id is not None else ""
            params = [str(emb)] + ([user_id] if user_id is not None else []) + [str(emb), top_k]
            rows = self.cursor.execute(f'''SELECT chunk_id,doc_name,folder_path,page_number,heading,language,parent_text,child_text,
                    embedding <=> %s::vector AS distance FROM "{self.schema}".{table} {where}
                    ORDER BY embedding <=> %s::vector LIMIT %s''', params).fetchall()
        else:
            sql = "SELECT * FROM user_chunks WHERE user_id=?" if user_id is not None else "SELECT * FROM chunks"
            rows = self.sqlite.execute(sql, (user_id,) if user_id is not None else ()).fetchall()
            scored = []
            for row in rows:
                distance = 1.0 - self._cosine(emb, self._vector(row["embedding"]))
                scored.append((row, distance))
            scored.sort(key=lambda item: item[1])
            return [self._row_to_result(row, distance, table) for row, distance in scored[:top_k]]
        return [self._row_to_result(row, row[8], table) for row in rows]

    @staticmethod
    def _row_to_result(row, distance, table):
        return {"chunk_id": row[0], "doc_name": row[1], "folder_path": row[2], "page_number": row[3],
                "heading": row[4], "language": row[5], "parent_text": row[6], "child_text": row[7],
                "text": row[7], "distance": float(distance), "source_table": table}

    def search_similar_chunks(self, query_embedding, top_k=5):
        return self._search("chunks", query_embedding, top_k)

    def hybrid_search(self, query_embedding, user_id, top_k=3):
        results = self._search("chunks", query_embedding, top_k) + self._search("user_chunks", query_embedding, top_k, user_id)
        results.sort(key=lambda item: item.get("distance", float("inf")))
        return results[:top_k]

    def get_user_documents(self, user_id: str):
        if self.pgvector_enabled:
            rows = self.cursor.execute(f'''SELECT doc_name,COUNT(*),MAX(folder_path),MIN(page_number),MAX(page_number)
                FROM "{self.schema}".user_chunks WHERE user_id=%s GROUP BY doc_name ORDER BY doc_name''', (user_id,)).fetchall()
        else:
            rows = self.sqlite.execute("SELECT doc_name,COUNT(*),MAX(folder_path),MIN(page_number),MAX(page_number) FROM user_chunks WHERE user_id=? GROUP BY doc_name ORDER BY doc_name", (user_id,)).fetchall()
        return [{"doc_name": row[0], "chunk_count": row[1], "folder_path": row[2], "min_page": row[3], "max_page": row[4], "status": "completed"} for row in rows]

    def status(self):
        return {"backend": self.backend, "postgres": f"{self.host}:{self.port}/{self.dbname}", "schema": self.schema, "pgvector_enabled": self.pgvector_enabled}

    def close(self):
        if self.sqlite:
            self.sqlite.close()
        self.cursor.close()
        self.connection.close()
