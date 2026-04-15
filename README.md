# JEE Parser – MVP

Validates the core assumption: can a text-based JEE PDF be parsed into usable question units with minimal manual correction?

---

## Project Structure

```
CBT/
├── backend/
│   ├── main.py           # FastAPI server + parsing logic
│   └── requirements.txt  # Python dependencies
└── frontend/
    └── index.html        # Zero-build UI (open directly in browser)
```

---

## Running Locally

### 1. Backend

```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the API server
python main.py
```

The backend will be available at `http://127.0.0.1:8000`.

You can verify it is running by visiting `http://127.0.0.1:8000/docs` in your browser.

### 2. Frontend

Open `frontend/index.html` directly in any modern browser (Chrome or Firefox recommended).  
No `npm install`, no build step.

---

## How to Use

1. Open `frontend/index.html` in your browser.
2. Click **Choose File** and select a text-based JEE PDF.
3. Click **Upload & Parse**.
4. The parser segments the document into question blocks.
5. Use the correction tools:
   - **Split after this line** – Hover over any line to split the current block at that point. Creates a new question block from the lines below.
   - **Merge with next** – Combines the current block with the one immediately below it.

---

## Limits (MVP)

| Constraint         | Value         |
|--------------------|---------------|
| Max file size      | 10 MB         |
| Supported input    | Text-based PDF only (no scanned images) |
| Storage            | In-memory only (no database) |
| Auth               | None          |
| Async queue        | None          |

---

## What is parsed

- **Text blocks** extracted via PyMuPDF (`fitz`)
- **Sort order:** page → y-position (snapped to 10px grid) → x-position
- **Question boundary detection** using regex:
  - `1.` or `1)`
  - `(1)` 
  - `Q1`, `Q.1`, `Q. 1`
  - `Question 1`, `Question 1.`

## What is NOT parsed (deferred)

- Options (A/B/C/D)
- Sections
- Images and diagrams
- Question types
- Math formatting
