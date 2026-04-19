import uuid
import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from extractor import extract_lines
from segmenter import build_questions, nodes_to_sections
from renderer import render_questions
from solution_parser import parse_solutions
from aligner import align
from document_model import PaperSession

app = FastAPI(title="JEE Parser — Unified Document Model")

# ── Static frontend ────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def root():
    resp = FileResponse(str(FRONTEND_DIR / "index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"]        = "no-cache"
    return resp

@app.get("/exam", include_in_schema=False)
async def exam():
    resp = FileResponse(str(FRONTEND_DIR / "exam.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"]        = "no-cache"
    return resp

@app.get("/results", include_in_schema=False)
async def results():
    resp = FileResponse(str(FRONTEND_DIR / "results.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"]        = "no-cache"
    return resp

@app.get("/review", include_in_schema=False)
async def review():
    resp = FileResponse(str(FRONTEND_DIR / "review.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"]        = "no-cache"
    return resp

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory session store ────────────────────────────────────────────────────
# Maps session_id (str) → PaperSession
# Cleared on server restart (fine for single-user dev).
_sessions: dict[str, PaperSession] = {}

MAX_SESSIONS = 20   # avoid unbounded growth during dev


def _store_session(session: PaperSession):
    if len(_sessions) >= MAX_SESSIONS:
        # Evict oldest session
        oldest = next(iter(_sessions))
        del _sessions[oldest]
    _sessions[session.session_id] = session


# ── Helpers ────────────────────────────────────────────────────────────────────
def has_text_layer(doc: fitz.Document) -> bool:
    for page_num in range(min(3, len(doc))):
        text = doc[page_num].get_text("text").strip()
        if len(text) > 30:
            return True
    return False


# ── /upload — question paper ───────────────────────────────────────────────────
@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit.")

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not open PDF.")

    if not has_text_layer(doc):
        raise HTTPException(
            status_code=400,
            detail="No text layer detected. Scanned PDFs are unsupported."
        )

    # ── Parse ──────────────────────────────────────────────────────────────────
    lines = extract_lines(doc)
    if not lines:
        raise HTTPException(status_code=400, detail="No readable text lines found.")

    nodes = build_questions(lines)
    q_count = sum(1 for n in nodes if n["type"] == "question")
    if q_count == 0:
        raise HTTPException(
            status_code=422, detail="No questions detected after segmentation."
        )

    rendered = render_questions(doc, nodes)

    # ── Build structural section model + persist in session ────────────────────
    # Wrapped in try/except so any failure here NEVER breaks the upload response.
    session_id = ""
    sections_summary = []
    try:
        sections  = nodes_to_sections(nodes)
        session   = PaperSession(
            session_id = str(uuid.uuid4()),
            sections   = sections,
        )
        _store_session(session)
        session_id = session.session_id
        sections_summary = [
            {
                "label":          f"{s.subject} {s.name}",
                "answer_type":    s.answer_type,
                "q_count":        s.actual_count,
                "expected_count": s.expected_count,
            }
            for s in sections
        ]
        print(f"[SESSION] stored {session_id} with "
              f"{sum(len(s.questions) for s in sections)} questions")
    except Exception as e:
        print(f"[WARN] nodes_to_sections failed — alignment will be disabled: {e}")
        import traceback; traceback.print_exc()

    return {
        "total":      q_count,
        "nodes":      rendered,
        "session_id": session_id,
        "sections":   sections_summary,
    }


# ── /upload_solutions — solutions PDF ─────────────────────────────────────────
@app.post("/upload_solutions")
async def upload_solutions(
    file:       UploadFile = File(...),
    session_id: str        = "",
):
    """
    Accepts a solutions PDF and an optional session_id from the question-paper upload.
    If session_id is provided, returns a full per-section ValidationReport.
    Always returns the flat answer key for the exam UI.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        global_answers, section_answers, debug_lines, solution_images = parse_solutions(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Solutions parse error: {e}")

    # JSON-serialisable flat answer key (string keys).
    # Each entry: {parsed, hint, image} so the frontend can display
    # the answer options, explanation text, AND a cropped solution image.
    answers_str = {
        str(k): {
            "parsed": v.parsed,
            "hint":   v.hint,
            "image":  solution_images.get(k),   # base64 PNG data URL or None
        }
        for k, v in global_answers.items()
    }

    # ── Alignment + validation (only if session_id is known) ──────────────────
    validation = None
    if session_id and session_id in _sessions:
        paper_session = _sessions[session_id]
        report = align(paper_session.sections, global_answers)
        validation = report.to_json()
    else:
        if session_id:
            print(f"[WARN] session_id {session_id!r} not found — skipping alignment")

    return {
        "answers":     answers_str,
        "count":       len(answers_str),
        "debug_lines": debug_lines,
        "validation":  validation,   # None if no session, full report otherwise
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
