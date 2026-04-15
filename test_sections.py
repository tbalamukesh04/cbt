import fitz
import json
import sys, os
sys.path.insert(0, os.path.abspath("backend"))
from extractor import extract_lines
from segmenter import build_questions
from renderer import render_questions

doc = fitz.open()
p1 = doc.new_page(width=600, height=800)
y = 50

p1.insert_text((50, y), "JEE Advanced 2024 - Paper 1", fontsize=14); y += 30

# Section A
p1.insert_text((50, y), "SECTION A", fontsize=13); y += 18
p1.insert_text((50, y), "One or More than one correct type", fontsize=11); y += 25

p1.insert_text((50, y), "1. If f(x) = x^2 + 3x, find f'(x).", fontsize=12); y += 16
p1.insert_text((60, y), "(A) 2x+3  (B) x+3  (C) 2x  (D) 3x+2", fontsize=11); y += 28

p1.insert_text((50, y), "2. Which of the following are alkali metals?", fontsize=12); y += 16
p1.insert_text((60, y), "(A) Na  (B) Fe  (C) K  (D) Cu", fontsize=11); y += 35

# Section B
p1.insert_text((50, y), "SECTION B", fontsize=13); y += 18
p1.insert_text((50, y), "Numerical Value Type", fontsize=11); y += 25

p1.insert_text((50, y), "3. The value of 2+2 is ___.", fontsize=12); y += 28
p1.insert_text((50, y), "4. If area of circle with r=7 is k*pi, find k.", fontsize=12)

doc.save("test_sections.pdf")
doc_read = fitz.open("test_sections.pdf")

lines = extract_lines(doc_read)
questions = build_questions(lines)
rendered = render_questions(doc_read, questions)

print(f"Total: {len(rendered)} questions\n")
for q in rendered:
    sec = q.get("section")
    sec_str = f'{sec["section_name"]} | {sec["section_description"]} | {sec["answer_type"]}' if sec else "None"
    print(f'{q["id"]}:')
    print(f'  section:     {sec_str}')
    print(f'  answer_type: {q["answer_type"]}')
    print(f'  images:      {len(q["images"])}')
    print(f'  _debug:      {q["_debug"]}')
    print()
