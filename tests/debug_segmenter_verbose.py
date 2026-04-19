import sys, os, json, re
sys.path.insert(0, os.path.abspath("backend"))
import fitz
from extractor import extract_lines

# Copied from segmenter.py to debug
Q_START_REGEX = re.compile(r"^\d+[\.\)]|^Q\s*\d+", re.IGNORECASE)
SECTION_PATTERNS = [
    (re.compile(r"one\s+or\s+more\s+than\s+one\s+correct", re.IGNORECASE), "multiple_correct_mcq"),
    (re.compile(r"multiple\s+correct", re.IGNORECASE), "multiple_correct_mcq"),
    (re.compile(r"single\s+correct", re.IGNORECASE), "single_correct_mcq"),
    (re.compile(r"single\s+digit\s+integer", re.IGNORECASE), "integer_type"),
    (re.compile(r"numerical|decimal", re.IGNORECASE), "numerical_type"),
]
DEFAULT_SECTION = {"name": "", "description": "", "answer_type": "single_correct_mcq"}

def _is_noise(text: str) -> bool:
    val = text.strip().lower()
    return not val or val.isdigit() or any(k in val for k in ["jee", "paper", "time:", "timestamp", "date:", "page"])

def _detect_section(text: str) -> dict | None:
    for pattern, answer_type in SECTION_PATTERNS:
        if pattern.search(text):
            return {"name": text.strip(), "description": text.strip(), "answer_type": answer_type}
    return None

def build_questions_debug(lines: list[dict]):
    questions = []
    current_lines = []
    current_section = dict(DEFAULT_SECTION)
    has_seen_question = False

    def flush():
        nonlocal current_lines
        if current_lines:
            print(f"DEBUG: Flushing {len(current_lines)} lines with section {current_section['answer_type']}")
            questions.append({
                "id": f"q{len(questions) + 1}",
                "lines": list(current_lines),
                "section": dict(current_section),
                "_debug": {"line_count": len(current_lines)},
            })
            current_lines = []

    for i, line in enumerate(lines):
        text = line["text"].strip()
        print(f"DEBUG: Processing Line {i}: '{text[:40]}...'")
        
        if _is_noise(text):
            print(f"DEBUG: Skipping Line {i} (noise)")
            continue

        sec = _detect_section(text)
        if sec is not None:
            print(f"DEBUG: Detected Section change at Line {i}: {sec['answer_type']}")
            current_section = sec
            continue

        is_q_start = bool(Q_START_REGEX.match(text)) and len(text) > 3
        print(f"DEBUG: Line {i} is_q_start={is_q_start}")

        if not has_seen_question:
            if is_q_start:
                print(f"DEBUG: First question started at Line {i}")
                has_seen_question = True
                current_lines.append(line)
            continue

        if is_q_start:
            flush()
            current_lines.append(line)
        else:
            current_lines.append(line)

    flush()
    print(f"DEBUG: Total questions before cleanup: {len(questions)}")
    
    cleaned = []
    for q in questions:
        total_text = " ".join(l["text"] for l in q["lines"])
        print(f"DEBUG: Question {q['id']} total_text length: {len(total_text.strip())}")
        if len(total_text.strip()) < 5 and cleaned:
            print(f"DEBUG: Merging Question {q['id']} into prev")
            prev = cleaned[-1]
            prev["lines"].extend(q["lines"])
            prev["_debug"]["line_count"] += q["_debug"]["line_count"]
        else:
            cleaned.append(q)
    return cleaned

doc = fitz.open("test_sections.pdf")
lines = extract_lines(doc)
questions = build_questions_debug(lines)
for q in questions:
    print(f"FINAL: {q['id']} ({q['section']['answer_type']}) - {q['lines'][0]['text'][:30]}...")
