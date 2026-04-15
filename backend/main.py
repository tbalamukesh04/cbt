import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

# Pipeline Modules
from pdf_extractor import extract_raw_blocks
from layout import (
    reconstruct_reading_order,
    build_lines,
    build_paragraphs
)
from classifier import classify_paragraph
from segmenter import segment_document

app = FastAPI(title="JEE Parser MVP - Layout Aware Pipeline")

# ── Static frontend ────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

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

    # 2. Extract Raw Blocks
    raw_blocks = extract_raw_blocks(doc)
    if not raw_blocks:
        raise HTTPException(status_code=400, detail="No text blocks found.")

    # 3. Layout Reconstruction
    ordered_blocks = reconstruct_reading_order(raw_blocks)
    lines = build_lines(ordered_blocks)
    paragraphs, left_margin = build_paragraphs(lines)

    # 4. Paragraph Classification
    has_seen_question = False
    for p in paragraphs:
        p_class, is_ambiguous = classify_paragraph(p, left_margin, tolerance=15.0, has_seen_question=has_seen_question)
        p["class"] = p_class
        p["ambiguous"] = is_ambiguous
        print("PARAGRAPH:", repr(p["text"][:30]), p["x0"], p_class, is_ambiguous)
        
        if p_class == "question_start":
            has_seen_question = True

    # 5. Segmentation
    questions = segment_document(paragraphs, left_margin, tolerance=15.0)

    if not questions:
        raise HTTPException(status_code=422, detail="No questions detected after segmentation.")

    return {"total": len(questions), "questions": questions}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
