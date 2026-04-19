import fitz, sys, os, json
sys.path.insert(0, os.path.abspath("backend"))
from extractor import extract_lines
from segmenter import build_questions

doc = fitz.open("test_sections.pdf")
lines = extract_lines(doc)
questions = build_questions(lines)
for q in questions:
    texts = [l["text"][:50] for l in q["lines"]]
    sec = q["section"]["answer_type"]
    print(q["id"] + " (" + sec + "): " + str(texts))
