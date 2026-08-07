import time
import json
from typing import Dict, Any, Generator, Optional, List


class AgentCoordinatorService:

    def __init__(self, embedder=None, db=None, database_agent=None, llm_service=None, router_service=None):
        self.embedder = embedder
        self.db = db
        self.database_agent = database_agent
        self.llm_service = llm_service
        self.router_service = router_service

    def run_multihop_stream(
        self,
        question: str,
        user_id: str = "user-test-0001",
        context_filter: Optional[str] = None,
        top_k: int = 3
    ) -> Generator[str, None, None]:
        """
        Executes a multi-hop RAG stream:
        1. Analyzes whether the query needs DATABASE, DOCUMENT, or MULTI_HOP (Both).
        2. Performs Hop 1 (SQL Database lookup if needed).
        3. Performs Hop 2 (Vector Document retrieval if needed).
        4. Synthesizes a unified response with merged citations.
        """
        pipeline_start = time.time()
        hop_step = 1

        # Step 1: Routing & Plan Generation
        route = "DOCUMENT"
        extracted_table = None

        if self.router_service:
            route_info = self.router_service.route_query(question)
            route = route_info.get("route", "DOCUMENT")
            extracted_table = route_info.get("table")

        # Yield route event
        yield f"data: {json.dumps({'type': 'route', 'route': route, 'table': extracted_table})}\n\n"

        sql_result = None
        sql_time = 0.0
        table_cited = None

        retrieved_chunks = []
        doc_time = 0.0
        doc_cited = None
        page_cited = None

        # --- HOP 1: DATABASE QUERY (If needed) ---
        if route in ["DATABASE", "MULTI_HOP"] and self.database_agent:
            hop_payload = json.dumps({
                "type": "hop",
                "step": hop_step,
                "action": "SQL Database Lookup",
                "details": f"Querying database table: {extracted_table or 'Whitelisted tables'}"
            })
            yield f"data: {hop_payload}\n\n"

            s_db = time.time()
            try:
                sql_result = self.database_agent.query(question)
                sql_time = time.time() - s_db
                table_cited = f"Table: {extracted_table or 'Database Tables'}"
            except Exception as e:
                sql_result = f"Error during SQL query: {str(e)}"
                sql_time = time.time() - s_db
            
            hop_step += 1

        # --- HOP 2: VECTOR DOCUMENT RETRIEVAL (If needed) ---
        if route in ["DOCUMENT", "MULTI_HOP"] and self.embedder and self.db:
            hop_payload = json.dumps({
                "type": "hop",
                "step": hop_step,
                "action": "Vector Document Search",
                "details": "Searching unstructured documents & policies..."
            })
            yield f"data: {hop_payload}\n\n"

            s_doc = time.time()
            try:
                # If multi-hop and we have SQL results, augment the vector search prompt
                search_query = question
                if route == "MULTI_HOP" and sql_result:
                    search_query = f"{question} {sql_result[:200]}"

                query_embedding = self.embedder.embed_text(search_query)
                retrieved_chunks = self.db.hybrid_search(
                    query_embedding=query_embedding,
                    user_id=user_id,
                    top_k=top_k
                )

                if context_filter and context_filter != "All":
                    filtered = [
                        c for c in retrieved_chunks
                        if context_filter.lower() in (c.get("heading", "") + c.get("doc_name", "") + c.get("folder_path", "")).lower()
                    ]
                    if filtered:
                        retrieved_chunks = filtered

                if retrieved_chunks:
                    top_c = retrieved_chunks[0]
                    doc_cited = top_c.get("doc_name") or top_c.get("heading") or "Port Document"
                    if top_c.get("page_number"):
                        page_cited = f"Pg {top_c.get('page_number')}"

                doc_time = time.time() - s_doc
            except Exception as e:
                print(f"[ERROR] Vector search failed during multi-hop: {e}")
                doc_time = time.time() - s_doc

            hop_step += 1

        # --- CITATION MERGING ---
        merged_citations = []
        if table_cited:
            merged_citations.append(table_cited)
        if doc_cited:
            merged_citations.append(doc_cited)

        final_source = " | ".join(merged_citations) if merged_citations else "Port RAG System"

        meta_payload = json.dumps({
            "type": "metadata",
            "source": final_source,
            "page": page_cited
        })
        yield f"data: {meta_payload}\n\n"

        # --- FINAL RESPONSE GENERATION ---
        s_gen = time.time()

        if route == "DATABASE" and sql_result and not retrieved_chunks:
            # Direct SQL response streaming
            for chunk in [sql_result[i:i+15] for i in range(0, len(sql_result), 15)]:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            gen_time = time.time() - s_gen

        else:
            # Synthesize combined prompt
            prompt = self._build_multihop_prompt(question, sql_result, retrieved_chunks)
            
            if self.llm_service:
                for token_chunk in self.llm_service.generate_stream(prompt):
                    yield f"data: {json.dumps({'type': 'token', 'content': token_chunk})}\n\n"
            gen_time = time.time() - s_gen

        total_time = time.time() - pipeline_start

        done_payload = json.dumps({
            "type": "done",
            "metrics": {
                "routing_time": f"{(sql_time + doc_time):.2f}s",
                "sql_execution_time": f"{sql_time:.2f}s" if sql_time > 0 else None,
                "retrieval_time": f"{doc_time:.2f}s" if doc_time > 0 else None,
                "generation_time": f"{gen_time:.2f}s",
                "total_time": f"{total_time:.2f}s"
            }
        })
        yield f"data: {done_payload}\n\n"

    def _build_multihop_prompt(self, question: str, sql_result: Optional[str], chunks: List[Dict[str, Any]]) -> str:
        context_parts = []

        if sql_result:
            context_parts.append(f"### STRUCTURED DATABASE RECORDS:\n{sql_result}")

        if chunks:
            doc_context = "\n\n".join([
                f"[Document: {c.get('doc_name', 'Unknown')}, Page: {c.get('page_number', 'N/A')}]\n{c.get('chunk_text', '')}"
                for c in chunks
            ])
            context_parts.append(f"### UNSTRUCTURED POLICY DOCUMENTS & MANUALS:\n{doc_context}")

        full_context = "\n\n".join(context_parts) if context_parts else "No specific records found."

        return f"""You are the Port Land Lease MMS Multi-Hop AI Assistant.
Answer the user's question using the provided context from structured database records and/or document manuals.

{full_context}

User Question: {question}

Instructions:
- Provide a clear, professional, and well-structured answer.
- Combine information from both database records and policy documents if present.
- State clearly if certain requested details are missing.

Answer:"""
