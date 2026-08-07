import os
import time
import sys
import json
import shutil
import threading
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, Field
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from app.services.billing_prediction_service import BillingPredictionRequest, BillingPredictionService

# Force stdout to UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

app = FastAPI(title="Port Land Lease RAG AI Assistant API")

# Enable CORS for frontend integration done vs
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Test user ID (hardcoded for now — replace with real auth later)
TEST_USER_ID = os.getenv("RAG_USER_ID", "local-user")

# Global services references
embedder = None
db = None
prompt_builder = None
llm = None
guardrail = None
ingestion_service = None
router = None
database_agent = None
agent_coordinator = None
services_ready = False
services_loading = False
init_error = None
billing_predictor = None
billing_error = None

# Track upload/ingestion status per filename
upload_status = {}

def load_services_bg():
    global embedder, db, prompt_builder, llm, guardrail, ingestion_service, router, database_agent, agent_coordinator, services_ready, services_loading, init_error, billing_predictor, billing_error
    if services_ready or services_loading:
        return
    services_loading = True
    try:
        try:
            billing_predictor = BillingPredictionService()
            billing_error = None
        except Exception as billing_exception:
            billing_error = str(billing_exception)
            print(f"[WARN] Billing forecast unavailable: {billing_exception}")
        print("=" * 70)
        print("Initializing Real Enterprise RAG Pipeline Services in background...")
        print("=" * 70)

        from app.services.embedding_service import EmbeddingService
        from app.services.postgres_service import PostgreSQLService
        from app.services.prompt_builder import PromptBuilder
        from app.services.llm_service import LLMService
        try:
            from app.services.guardrail_service import GuardrailService
        except Exception:
            GuardrailService = None
        from app.services.router_service import RouterService
        from app.services.database_agent import DatabaseAgent
        from app.services.agent_coordinator import AgentCoordinatorService

        embedder = EmbeddingService()
        db = PostgreSQLService()
        prompt_builder = PromptBuilder()
        llm = LLMService()
        guardrail = GuardrailService() if GuardrailService else None
        try:
            from app.services.ingestion_service import IngestionService
            ingestion_service = IngestionService(embedder=embedder, db=db)
        except Exception as ingestion_error:
            ingestion_service = None
            print(f"[WARN] Document ingestion disabled until optional parsers are installed: {ingestion_error}")
        router = RouterService(model_name="qwen2.5:7b")
        database_agent = DatabaseAgent(model_name="qwen2.5:7b")
        agent_coordinator = AgentCoordinatorService(
            embedder=embedder,
            db=db,
            database_agent=database_agent,
            llm_service=llm,
            router_service=router
        )
        
        services_ready = True
        init_error = None
        print("=" * 70)
        print("[SUCCESS] RAG services loaded; optional model/vector backends are reported separately.")
        print("=" * 70)
    except Exception as e:
        services_ready = False
        init_error = str(e)
        print("!" * 70)
        print(f"[ERROR] Error during RAG service initialization: {e}")
        print("!" * 70)
    finally:
        services_loading = False

class ChatRequest(BaseModel):
    question: str
    context: Optional[str] = "Board Note"
    top_k: Optional[int] = 3
    prediction_context_id: Optional[str] = None

class BillingRequest(BaseModel):
    customer_id: Optional[str] = None
    target_year: int = 0
    target_month: int = 0
    bill_type: str = ""
    current_year: Optional[int] = None
    current_month: Optional[int] = None
    structure_type: Optional[str] = None
    water_tax_included: Optional[bool] = None
    present_year: Optional[int] = None
    present_month: Optional[int] = None
    present_amount: Optional[float] = None
    present_cgst: Optional[float] = None
    present_sgst: Optional[float] = None
    billing_charge: Optional[float] = None
    billing_frequency: Optional[str] = None
    area: Optional[float] = None
    line_category: Optional[str] = None
    rates: dict[str, float] = Field(default_factory=dict)

class ChatResponse(BaseModel):
    success: bool
    answer: str
    is_safe: bool = True
    safety_message: Optional[str] = None
    source: Optional[str] = None
    page: Optional[str] = None
    retrieved_chunks: List[dict] = []
    metrics: dict = {}
    error_details: Optional[str] = None

@app.on_event("startup")
def startup_event():
    # Start non-blocking background initialization thread
    thread = threading.Thread(target=load_services_bg, daemon=True)
    thread.start()

@app.get("/api/health")
def health_check():
    db_status = db.status() if db and hasattr(db, "status") else None
    return {
        "status": "online" if services_ready else ("loading" if services_loading else "error"),
        "service": "Port Land RAG Chatbot API",
        "rag_services_ready": services_ready,
        "init_error": init_error,
        "billing_ready": billing_predictor is not None,
        "billing_error": billing_error,
        "vector": db_status,
        "llm_backend": getattr(llm, "backend", None),
        "embedding_backend": getattr(embedder, "backend", None),
    }

@app.get("/api/billing/status")
def billing_status():
    return {"ready": billing_predictor is not None, "error": billing_error, "model": str(getattr(billing_predictor, "model_path", "")) if billing_predictor else None}

@app.get("/api/billing/rules")
def billing_rules():
    if billing_predictor is None:
        raise HTTPException(status_code=503, detail=billing_error or "Billing prediction service is still initializing.")
    return billing_predictor.rules_payload()

@app.post("/api/billing/predict")
def billing_predict(req: BillingRequest):
    if billing_predictor is None:
        raise HTTPException(status_code=503, detail=billing_error or "Billing prediction service is still initializing.")
    try:
        payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        request = BillingPredictionRequest(**{key: value for key, value in payload.items() if value is not None})
        result = billing_predictor.predict_from_inputs(request) if request.present_amount is not None else billing_predictor.predict(request)
        return {"success": True, "summary": result.summary(), "prediction": result.as_dict()}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

def _prediction_requested(question: str) -> bool:
    lowered = question.lower()
    return bool(("predict" in lowered or "forecast" in lowered or "estimate" in lowered) and any(word in lowered for word in ("bill", "billing", "rent", "tax")))

def _prediction_result(question: str, context_id: Optional[str] = None):
    if billing_predictor is None:
        raise ValueError(billing_error or "Billing prediction service is still initializing.")
    return billing_predictor.follow_up(context_id, question) if context_id else billing_predictor.predict_from_prompt(question)

@app.post("/api/chat/stream")
def process_chat_stream(req: ChatRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if req.prediction_context_id or _prediction_requested(question):
        def prediction_events():
            try:
                result = _prediction_result(question, req.prediction_context_id)
                yield f"data: {json.dumps({'type': 'route', 'route': 'PREDICTION', 'table': 'billing'})}\n\n"
                yield f"data: {json.dumps({'type': 'prediction', 'context_id': result.context_id, 'prediction': result.as_dict()})}\n\n"
                for part in [result.summary()[i:i + 80] for i in range(0, len(result.summary()), 80)]:
                    yield f"data: {json.dumps({'type': 'token', 'content': part})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'metrics': {'route': 'PREDICTION'}})}\n\n"
            except Exception as error:
                yield f"data: {json.dumps({'type': 'error', 'message': str(error)})}\n\n"
        return StreamingResponse(prediction_events(), media_type="text/event-stream")

    if not services_ready:
        def err_gen():
            payload = json.dumps({
                "type": "error",
                "message": "Backend connection failed. RAG services (PostgreSQL/Ollama) are not ready."
            })
            yield f"data: {payload}\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    def event_generator():
        # Input Guardrail Check
        try:
            guard_result = guardrail.validate_input(question) if guardrail else None
            if guard_result and not guard_result.is_safe:
                payload = json.dumps({
                    "type": "error",
                    "message": "INPUT GUARDRAIL REJECTION: Query aborted to uphold content safety guidelines."
                })
                yield f"data: {payload}\n\n"
                return
        except Exception as ge:
            print(f"Guardrail error: {ge}")

        if agent_coordinator:
            for event in agent_coordinator.run_multihop_stream(
                question=question,
                user_id=TEST_USER_ID,
                context_filter=req.context,
                top_k=req.top_k or 3
            ):
                yield event
        else:
            err_payload = json.dumps({
                "type": "error",
                "message": "Agent Coordinator is not ready."
            })
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/chat", response_model=ChatResponse)
def process_chat(req: ChatRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if req.prediction_context_id or _prediction_requested(question):
        try:
            result = _prediction_result(question, req.prediction_context_id)
            return ChatResponse(success=True, answer=result.summary(), source="PostgreSQL billing data + XGBoost", metrics={"route": "PREDICTION"})
        except Exception as error:
            return ChatResponse(success=False, answer="Billing prediction failed.", error_details=str(error))

    if not services_ready:
        return ChatResponse(
            success=False,
            answer="Backend connection failed.",
            error_details=init_error or "RAG services (PostgreSQL/Ollama) are initializing or not reachable."
        )

    pipeline_start = time.time()

    try:
        guard_result = guardrail.validate_input(question) if guardrail else None
        if guard_result and not guard_result.is_safe:
            return ChatResponse(
                success=False,
                answer="INPUT GUARDRAIL REJECTION: Query aborted to uphold content safety guidelines.",
                is_safe=False,
                safety_message=guard_result.reason or "Inappropriate content detected.",
                error_details=f"Filtered text: {guard_result.censored_text}"
            )
    except Exception as ge:
        print(f"Guardrail error: {ge}")

    try:
        is_database = False
        if router:
            route_info = router.route_query(question)
            is_database = (route_info.get("route") == "DATABASE")

        if is_database and database_agent:
            # DATABASE ROUTE: Generate and execute SQL using DatabaseAgent
            s_db = time.time()
            answer = database_agent.query(question)
            db_time = time.time() - s_db

            table_name = route_info.get("table") or "Database Tables"
            source_name = f"Table: {table_name}"
            
            total_time = time.time() - pipeline_start

            return ChatResponse(
                success=True,
                answer=answer,
                is_safe=True,
                source=source_name,
                page=None,
                retrieved_chunks=[],
                metrics={
                    "routing_time": f"{time.time() - s_db:.2f}s",
                    "generation_time": f"{db_time:.2f}s",
                    "total_time": f"{total_time:.2f}s"
                }
            )

        # DOCUMENT ROUTE: Embed and Search
        s1 = time.time()
        query_embedding = embedder.embed_text(question)
        embed_time = time.time() - s1

        s2 = time.time()
        retrieved_chunks = db.hybrid_search(
            query_embedding=query_embedding,
            user_id=TEST_USER_ID,
            top_k=req.top_k or 3
        )
        retrieve_time = time.time() - s2

        if req.context and req.context != "All":
            filtered = [
                c for c in retrieved_chunks 
                if req.context.lower() in (c.get("heading", "") + c.get("doc_name", "") + c.get("folder_path", "")).lower()
            ]
            if filtered:
                retrieved_chunks = filtered

        s3 = time.time()
        prompt = prompt_builder.build(question=question, retrieved_chunks=retrieved_chunks)
        prompt_time = time.time() - s3

        s4 = time.time()
        answer = llm.generate(prompt)
        llm_time = time.time() - s4

        source_name = None
        page_str = None

        if retrieved_chunks:
            top_chunk = retrieved_chunks[0]
            source_name = top_chunk.get("doc_name") or top_chunk.get("heading") or "Port Document"
            if top_chunk.get("page_number"):
                page_str = f"Pg {top_chunk.get('page_number')}"

        total_time = time.time() - pipeline_start

        return ChatResponse(
            success=True,
            answer=answer,
            is_safe=True,
            source=source_name,
            page=page_str,
            retrieved_chunks=retrieved_chunks,
            metrics={
                "embedding_time": f"{embed_time:.2f}s",
                "retrieval_time": f"{retrieve_time:.2f}s",
                "prompt_time": f"{prompt_time:.4f}s",
                "generation_time": f"{llm_time:.2f}s",
                "total_time": f"{total_time:.2f}s"
            }
        )

    except Exception as err:
        print(f"[ERROR] RAG Pipeline execution error (V.S): {err}")
        return ChatResponse(
            success=False,
            answer="Backend connection failed.",
            error_details=str(err)
        )

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), context: str = Form("Board Note")):
    try:
        upload_dir = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)

        print(f"\n[Upload API] Received upload request for file: '{file.filename}' (Context: '{context}')")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size_kb = os.path.getsize(file_path) / 1024.0
        print(f"[Upload API] Saved '{file.filename}' ({file_size_kb:.1f} KB) to '{file_path}'")

        # Initialize upload status and trigger background ingestion
        upload_status[file.filename] = {
            "status": "pending",
            "step": "File uploaded, starting ingestion...",
            "pdf_type": None,
            "progress": 5,
        }

        if services_ready and ingestion_service:
            print(f"[Upload API] Spawning background thread for IngestionService.ingest('{file.filename}')...")
            def run_ingestion():
                ingestion_service.ingest(
                    pdf_path=Path(file_path),
                    user_id=TEST_USER_ID,
                    status_dict=upload_status[file.filename],
                )

            thread = threading.Thread(target=run_ingestion, daemon=True)
            thread.start()
        else:
            print(f"[Upload API] [WARN] Cannot start ingestion for '{file.filename}': RAG services not ready.")
            upload_status[file.filename].update({
                "status": "failed",
                "step": "RAG services not ready. Please try again later.",
                "progress": 100,
            })

        return {
            "success": True,
            "filename": file.filename,
            "context": context,
            "message": f"File '{file.filename}' uploaded. Ingestion started in background."
        }
    except Exception as e:
        print(f"[Upload API] [ERROR] Upload failed for '{file.filename}': {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


from urllib.parse import unquote

@app.get("/api/upload/status/{filename}")
def get_upload_status(filename: str):
    """Poll ingestion progress for a specific uploaded file."""
    decoded_name = unquote(filename)
    if decoded_name in upload_status:
        return {"success": True, **upload_status[decoded_name]}
    if filename in upload_status:
        return {"success": True, **upload_status[filename]}
    
    clean_decoded = decoded_name.strip().lower()
    clean_filename = filename.strip().lower()
    for key, val in upload_status.items():
        clean_key = key.strip().lower()
        if clean_key == clean_decoded or clean_key == clean_filename:
            return {"success": True, **val}

    return {"success": False, "status": "unknown", "step": "No ingestion record found."}


@app.get("/api/documents")
def get_user_documents():
    """Retrieve all user-uploaded documents and active ingestion statuses."""
    db_docs = []
    if db and services_ready:
        db_docs = db.get_user_documents(TEST_USER_ID)
    
    indexed_names = {d["doc_name"] for d in db_docs}
    
    active_docs = []
    for fname, info in upload_status.items():
        if fname not in indexed_names:
            active_docs.append({
                "doc_name": fname,
                "chunk_count": info.get("chunks_count", 0),
                "folder_path": None,
                "min_page": None,
                "max_page": None,
                "status": info.get("status", "pending"),
                "step": info.get("step", ""),
                "progress": info.get("progress", 0)
            })
            
    return {
        "success": True,
        "documents": active_docs + db_docs
    }

from app.services.chat_history_service import ChatHistoryService
history_service = ChatHistoryService()


@app.get("/api/sessions")
def get_chat_sessions():
    try:
        sessions = history_service.get_all_sessions()
        return {"success": True, "sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load sessions: {str(e)}")

class SaveSessionsRequest(BaseModel):
    sessions: List[dict]

@app.post("/api/sessions")
def save_chat_sessions(req: SaveSessionsRequest):
    try:
        success = history_service.save_sessions(req.sessions)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save sessions: {str(e)}")

@app.delete("/api/sessions/{session_id}")
def delete_chat_session(session_id: str):
    try:
        success = history_service.delete_session(session_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend index.html not found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api_server:app", host="0.0.0.0", port=8000, reload=True)
