import tempfile
import os
import json

# Load environment variables BEFORE any auth/config imports
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List

from core.complexity.scorer import compute_complexity
from core.transform import transform_text
from core.ingestion.pdf_reader import extract_text_from_pdf
from core.ingestion.question_parser import parse_questions
from core.ingestion.question_analyzer import analyze_question_block
from core.ingestion.question_cleaner import clean_questions, clean_analyzed_question
from core.transform.unit_builder import build_units
from core.transform.transform_runner import run_transformation, score_all_units, transform_all_units
from core.output.exam_reconstructor import reconstruct_exam
from core.database import init_db, User
from api.auth import router as auth_router
from api.dependencies import get_current_user


app = FastAPI(
    title="Lexora API",
    description="Cognitive-load transformation engine for dyslexic-friendly exam text",
    version="1.0"
)

# Initialize database
init_db()

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)

# Include auth routes
app.include_router(auth_router, prefix="/auth", tags=["authentication"])


# -----------------------------
# Request Models
# -----------------------------

class TextRequest(BaseModel):
    text: str


class BatchRequest(BaseModel):
    questions: List[str]


# -----------------------------
# Root Endpoint
# -----------------------------

@app.get("/")
def root():
    return {"message": "Lexora API running"}


# -----------------------------
# Health Check
# -----------------------------

@app.get("/health")
def health_check():
    return {"status": "ok"}


# -----------------------------
# Analyze Endpoint
# -----------------------------

@app.post("/v1/analyze")
async def analyze_endpoint(req: TextRequest, request: Request, current_user: User = Depends(get_current_user)):
    print(f"Analyze request received from {current_user.email} ({request.client.host})")
    return compute_complexity(req.text)


# -----------------------------
# Transform Single Text
# -----------------------------

@app.post("/v1/transform")
async def transform_endpoint(req: TextRequest, request: Request, current_user: User = Depends(get_current_user)):
    print(f"Transform request received from {current_user.email} ({request.client.host})")
    return transform_text(req.text)


# -----------------------------
# Batch Transformation
# -----------------------------

@app.post("/v1/transform-batch")
async def transform_batch(req: BatchRequest, request: Request, current_user: User = Depends(get_current_user)):

    print(f"Batch transform request from {current_user.email} ({request.client.host})")

    results = []
    modified_count = 0

    for question in req.questions:

        transformation = transform_text(question)

        modified_text = transformation["modified_text"]
        changed = len(transformation["changes"]) > 0

        if changed:
            modified_count += 1

        results.append({
            "original": question,
            "modified": modified_text,
            "changed": changed,
            "metadata": transformation
        })

    return {
        "results": results,
        "summary": {
            "questions_processed": len(req.questions),
            "questions_modified": modified_count
        }
    }


# -----------------------------
# Process PDF (Full Pipeline)
# -----------------------------

@app.post("/v1/process-pdf")
async def process_pdf(request: Request, file: UploadFile = File(...), current_user: User = Depends(get_current_user)):

    print(f"PDF process request from {current_user.email} ({request.client.host})")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Save uploaded file to temp location
    tmp = None
    try:
        content = await file.read()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(content)
        tmp.close()

        # Stage 1: Extract text
        text = extract_text_from_pdf(tmp.name)

        if not text.strip():
            raise HTTPException(status_code=422, detail="Could not extract text from PDF")

        # Stage 2: Parse questions
        questions = parse_questions(text)

        if not questions:
            raise HTTPException(status_code=422, detail="No questions found in PDF")

        # Save raw parsed text before cleaning (used for "original" view in frontend)
        raw_questions = list(questions)

        # Stage 3: Analyze structure on raw text (preserves paragraph numbers)
        analyzed = [analyze_question_block(q) for q in questions]

        # Stage 3b: Clean layout artifacts on analyzed fields
        # Passages keep paragraph numbers so the frontend can split them.
        for aq in analyzed:
            clean_analyzed_question(aq)

        # Stage 4: Build units
        all_units = []
        for i, q in enumerate(analyzed, start=1):
            all_units.extend(build_units(i, q))

        # Stage 5: Transform
        results = run_transformation(all_units)

        # Stage 6: Reconstruct
        exam_text = reconstruct_exam(results)

        # Build response
        total = len(results)
        changed = [r for r in results if r["changed"]]
        incomplete = [r for r in results if r["risk_before"] is None and r["type"] == "subquestion"]

        unit_details = []
        for r in results:
            unit_details.append({
                "id": r["id"],
                "type": r["type"],
                "original": r.get("original", ""),
                "modified": r.get("modified", ""),
                "risk_before": r["risk_before"],
                "risk_after": r["risk_after"],
                "changed": r["changed"],
                "marks": r["marks"],
                "keywords": r.get("keywords", []),
                "complexity": r.get("complexity"),
            })

        return {
            "exam_text": exam_text,
            "stats": {
                "total_units": total,
                "units_modified": len(changed),
                "incomplete_units": len(incomplete),
                "questions_found": len(questions),
            },
            "raw_questions": [
                {"number": i + 1, "text": q} for i, q in enumerate(raw_questions)
            ],
            "units": unit_details,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp and os.path.exists(tmp.name):
            os.unlink(tmp.name)


# -----------------------------------------
# Process PDF with SSE Progress (Streaming)
# -----------------------------------------

def _sse(event: str, data: dict) -> str:
    """Format a single Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/v1/process-pdf-stream")
async def process_pdf_stream(request: Request, file: UploadFile = File(...), current_user: User = Depends(get_current_user)):

    print(f"PDF stream request from {current_user.email} ({request.client.host})")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Read file into memory before entering the sync generator
    content = await file.read()

    def generate():
        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(content)
            tmp.close()

            # Step 1: Extract text from PDF
            yield _sse("progress", {"step": 1, "label": "Extracting text from PDF"})
            text = extract_text_from_pdf(tmp.name)

            if not text.strip():
                yield _sse("error", {"detail": "Could not extract text from PDF"})
                return

            # Step 2: Parse + analyze + clean + build units
            yield _sse("progress", {"step": 2, "label": "Parsing question structure"})
            questions = parse_questions(text)

            if not questions:
                yield _sse("error", {"detail": "No questions found in PDF"})
                return

            raw_questions = list(questions)
            analyzed = [analyze_question_block(q) for q in questions]
            for aq in analyzed:
                clean_analyzed_question(aq)

            all_units = []
            for i, q in enumerate(analyzed, start=1):
                all_units.extend(build_units(i, q))

            # Step 3: Score cognitive load
            yield _sse("progress", {"step": 3, "label": "Scoring cognitive load"})
            scored = score_all_units(all_units)

            # Step 4: Simplify high-risk sentences
            yield _sse("progress", {"step": 4, "label": "Simplifying high-risk sentences"})
            results = transform_all_units(scored)

            # Step 5: Rebuild exam structure
            yield _sse("progress", {"step": 5, "label": "Rebuilding exam structure"})
            exam_text = reconstruct_exam(results)

            # Build response (same shape as /v1/process-pdf)
            total = len(results)
            changed = [r for r in results if r["changed"]]
            incomplete = [r for r in results if r["risk_before"] is None and r["type"] == "subquestion"]

            unit_details = []
            for r in results:
                unit_details.append({
                    "id": r["id"],
                    "type": r["type"],
                    "original": r.get("original", ""),
                    "modified": r.get("modified", ""),
                    "risk_before": r["risk_before"],
                    "risk_after": r["risk_after"],
                    "changed": r["changed"],
                    "marks": r["marks"],
                    "keywords": r.get("keywords", []),
                    "complexity": r.get("complexity"),
                })

            yield _sse("result", {
                "exam_text": exam_text,
                "stats": {
                    "total_units": total,
                    "units_modified": len(changed),
                    "incomplete_units": len(incomplete),
                    "questions_found": len(questions),
                },
                "raw_questions": [
                    {"number": i + 1, "text": q} for i, q in enumerate(raw_questions)
                ],
                "units": unit_details,
            })

        except Exception as e:
            yield _sse("error", {"detail": str(e)})
        finally:
            if tmp and os.path.exists(tmp.name):
                os.unlink(tmp.name)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )