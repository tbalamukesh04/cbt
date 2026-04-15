import fitz  # PyMuPDF
import re
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="JEE Parser MVP")

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
    allow_methods=["*"],
    allow_headers=["*"],
)

# Matches patterns: "1.", "(1)", "Q1", "Q.1", "Q. 1", "Question 1"
Q_START_REGEX = re.compile(
    r"^(?:Question|Q)\s*\.?\s*\(?([0-9]+)\)?\s*[\.\-\)]"
    r"|^([0-9]+)\s*\."
    r"|^\(([0-9]+)\)",
    re.IGNORECASE
)


def has_text_layer(doc: fitz.Document) -> bool:
    """Check if the PDF has a real text layer by sampling first 3 pages."""
    for page_num in range(min(3, len(doc))):
        text = doc[page_num].get_text("text").strip()
        if len(text) > 30:
            return True
    return False


def extract_sorted_blocks(doc: fitz.Document) -> list[dict]:
    """
    Extract all text blocks from the document and sort them in
    reading order: page → y-position (snapped to 10px grid) → x-position.
    """
    raw_blocks = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")  # Each block: (x0, y0, x1, y1, text, block_no, block_type)

        for b in blocks:
            block_type = b[6]
            if block_type != 0:  # Skip image blocks
                continue
            text = b[4].strip()
            if not text:
                continue

            raw_blocks.append({
                "page": page_num,
                "x0": b[0],
                "y0": b[1],
                "text": text,
            })

    # Sort: page asc → y0 snapped to 10px grid asc → x0 asc
    raw_blocks.sort(key=lambda b: (b["page"], round(b["y0"] / 10), b["x0"]))
    return raw_blocks


def segment_questions(blocks: list[dict]) -> list[dict]:
    """
    Scan sorted blocks line-by-line and segment into question chunks
    using the Q_START_REGEX as a boundary trigger.
    """
    questions = []
    current_lines = []
    q_counter = 0

    def flush_current():
        nonlocal q_counter
        if current_lines:
            q_counter += 1
            questions.append({
                "id": f"q{q_counter}",
                "text": "\n".join(current_lines),
            })
            current_lines.clear()

    for block in blocks:
        for raw_line in block["text"].split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            if Q_START_REGEX.match(line):
                flush_current()
                current_lines.append(line)
            else:
                current_lines.append(line)

    flush_current()  # Capture trailing question
    return questions


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    # --- Validation ---
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content) > 10 * 1024 * 1024:  # 10MB hard limit
        raise HTTPException(status_code=400, detail="File exceeds the 10MB size limit.")

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not open PDF. The file may be corrupted.")

    if not has_text_layer(doc):
        raise HTTPException(
            status_code=400,
            detail="No text layer detected. This appears to be a scanned PDF. Only text-based PDFs are supported."
        )

    # --- Extraction & Segmentation ---
    blocks = extract_sorted_blocks(doc)

    if not blocks:
        raise HTTPException(status_code=400, detail="No readable text blocks found in this document.")

    questions = segment_questions(blocks)

    if len(questions) == 0:
        raise HTTPException(
            status_code=422,
            detail="No questions were detected. The document may use an unsupported numbering format."
        )

    return {"total": len(questions), "questions": questions}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
