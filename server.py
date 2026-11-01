"""API for the React resume screening interface."""
import os
import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import screener
import candidate_store
from candidate_store import STATUSES
from notifications import update_candidate_status

app = FastAPI(title="TalentLens API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
candidate_store.initialize_db()


class StatusUpdate(BaseModel):
    status: str


class BulkStatusUpdate(BaseModel):
    candidate_ids: list[int]
    status: str


@app.get("/api/health")
def health():
    return {"status": "ok", "configured": bool(os.getenv("GEMINI_API_KEY"))}


@app.post("/api/screen")
async def screen_candidates(
    job_title: str = Form(""),
    job_description: str = Form(...),
    redact_pii: bool = Form(True),
    files: list[UploadFile] = File(...),
):
    if not os.getenv("GEMINI_API_KEY"):
        return {"error": "GEMINI_API_KEY is missing. Add it to your .env file and restart the API."}
    if not job_description.strip() or not files:
        return {"error": "Add a job description and at least one resume."}

    client = screener.get_client()
    rows = []
    for upload in files:
        filename = Path(upload.filename or "resume").name
        row = {"file": filename, "error": ""}
        try:
            suffix = Path(filename).suffix.lower()
            if suffix not in {".pdf", ".docx", ".txt"}:
                raise ValueError("Upload a PDF, DOCX, or TXT resume.")
            content = await upload.read()
            if len(content) > 10 * 1024 * 1024:
                raise ValueError("This file exceeds the 10 MB per-file limit.")
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / filename
                path.write_bytes(content)
                resume_text = screener.extract_text(path)
            if len(resume_text) < 100:
                raise ValueError("Little or no text extracted. This may be a scanned PDF.")
            evaluation = screener.evaluate(
                client, job_description,
                screener.redact_pii(resume_text) if redact_pii else resume_text,
            )
            row.update(screener.compute_result(evaluation))
            row["detail"] = evaluation.model_dump()
            title = job_title.strip()
            if not title:
                match = re.search(r"Job Title:\s*(.+)", job_description)
                title = match.group(1).strip() if match else "Open position"
            name = re.sub(r"^\d+[_\-\s]*", "", Path(filename).stem).replace("_", " ").replace("-", " ").strip().title()
            email_match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", resume_text)
            candidate_record = candidate_store.create_candidate(
                name=name or "Candidate", email=email_match.group(0) if email_match else None,
                job_title=title, resume_file=filename, score=row["total"], result=row,
            )
            row.update(candidate_record)
        except Exception as exc:
            row["error"] = str(exc)
        rows.append(row)
    return {"results": rows}


@app.get("/api/candidates")
def candidates(limit: int = 200):
    return {"candidates": candidate_store.list_candidates(limit)}


@app.patch("/api/candidates/{candidate_id}/status")
def change_candidate_status(candidate_id: int, update: StatusUpdate):
    if update.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"Status must be one of: {', '.join(STATUSES)}")
    result = update_candidate_status(candidate_id, update.status)
    if result is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return result


@app.post("/api/candidates/status/bulk")
def bulk_change_candidate_status(update: BulkStatusUpdate):
    if update.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"Status must be one of: {', '.join(STATUSES)}")
    if not update.candidate_ids:
        raise HTTPException(status_code=422, detail="Provide at least one candidate ID.")
    return {
        "results": [
            {"candidate_id": candidate_id, **(update_candidate_status(candidate_id, update.status)
                                                or {"error": "Candidate not found."})}
            for candidate_id in dict.fromkeys(update.candidate_ids)
        ]
    }


@app.get("/api/notifications")
def notification_history(limit: int = 50, candidate_id: int | None = None):
    return {"notifications": candidate_store.list_notifications(limit, candidate_id)}
