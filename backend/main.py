import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from extractor import extract_lines
from segmenter import build_questions
from renderer import render_questions

app = FastAPI(title="JEE Parser MVP — Image-Based")

# ── Static frontend ────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def root():
    resp = FileResponse(str(FRONTEND_DIR / "index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp

@app.get("/exam", include_in_schema=False)
async def exam():
    resp = FileResponse(str(FRONTEND_DIR / "exam.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def has_text_layer(doc: fitz.Document) -> bool:
    for page_num in range(min(3, len(doc))):
        text = doc[page_num].get_text("text").strip()
        if len(text) > 30:
            return True
    return False


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    # 1. Validation
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit.")

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not open PDF.")

    if not has_text_layer(doc):
        raise HTTPException(status_code=400, detail="No text layer detected. Scanned PDFs unsupported.")

    # 2. Extract → Segment → Render
    lines = extract_lines(doc)
    if not lines:
        raise HTTPException(status_code=400, detail="No readable text lines found.")

    questions = build_questions(lines)
    q_count   = sum(1 for n in questions if n["type"] == "question")
    if q_count == 0:
        raise HTTPException(status_code=422, detail="No questions detected after segmentation.")

    rendered = render_questions(doc, questions)

    return {"total": q_count, "nodes": rendered}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
