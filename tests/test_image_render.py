import fitz
import json
import sys, os
sys.path.insert(0, os.path.abspath("backend"))
from extractor import extract_lines
from segmenter import build_questions
from renderer import render_questions

# Build a synthetic 2-page PDF
doc = fitz.open()

# Page 1
p1 = doc.new_page(width=600, height=800)
y = 50
p1.insert_text((50, y), "Instructions: Read carefully.", fontsize=12)
y += 30
p1.insert_text((50, y), "1. A particle moves with velocity v = 3t^2 + 2t.", fontsize=12)
y += 18
p1.insert_text((60, y), "Find the acceleration at t = 2s.", fontsize=12)
y += 18
p1.insert_text((60, y), "(A) 14 m/s^2  (B) 12 m/s^2  (C) 10 m/s^2  (D) 8 m/s^2", fontsize=11)
y += 30
p1.insert_text((50, y), "2. Calculate the work done by a force F = 5x over", fontsize=12)
y += 18
p1.insert_text((60, y), "a displacement from x=0 to x=4.", fontsize=12)

# Page 2 — continuation of Q2 + Q3
p2 = doc.new_page(width=600, height=800)
y2 = 50
p2.insert_text((60, y2), "(A) 40J  (B) 50J  (C) 60J  (D) 80J", fontsize=11)
y2 += 30
p2.insert_text((50, y2), "3. What is the SI unit of electric charge?", fontsize=12)
y2 += 18
p2.insert_text((60, y2), "(A) Ampere  (B) Coulomb  (C) Volt  (D) Ohm", fontsize=11)

doc.save("test_image.pdf")
doc_read = fitz.open("test_image.pdf")

lines = extract_lines(doc_read)
questions = build_questions(lines)
rendered = render_questions(doc_read, questions)

print(f"Total questions: {len(rendered)}\n")
for q in rendered:
    print(f"{q['id']}:")
    print(f"  type:        {q['type']}")
    print(f"  images:      {len(q['images'])} image(s), sizes: {[len(img) for img in q['images']]}")
    print(f"  answer_type: {q['answer_type']}")
    print(f"  _debug:      {q['_debug']}")
    print()
