import sys, os
sys.path.insert(0, os.path.abspath("backend"))
from extractor import extract_lines
from segmenter import build_questions
import fitz

doc = fitz.open("test_sections.pdf")
lines = extract_lines(doc)
questions = build_questions(lines)

print(f"Total questions: {len(questions)}")
for q in questions:
    print(f"{q['id']} ({q['section']['answer_type']}): {[l['text'][:40] for l in q['lines']]}")
