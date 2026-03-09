from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List

from core.complexity.scorer import compute_complexity
from core.transform import transform_text


app = FastAPI(
    title="Lexora API",
    description="Cognitive-load transformation engine for dyslexic-friendly exam text",
    version="1.0"
)


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
async def analyze_endpoint(req: TextRequest, request: Request):
    print("Analyze request received from:", request.client.host)
    return compute_complexity(req.text)


# -----------------------------
# Transform Single Text
# -----------------------------

@app.post("/v1/transform")
async def transform_endpoint(req: TextRequest, request: Request):
    print("Transform request received from:", request.client.host)
    return transform_text(req.text)


# -----------------------------
# Batch Transformation
# -----------------------------

@app.post("/v1/transform-batch")
async def transform_batch(req: BatchRequest, request: Request):

    print("Batch transform request from:", request.client.host)

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