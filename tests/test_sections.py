import fitz
import json
import sys, os
sys.path.insert(0, os.path.abspath("backend"))
from extractor import extract_lines
from segmenter import build_questions
from renderer import render_questions

doc = fitz.open()

# Page 1 — two sections with different answer types
p1 = doc.new_page(width=600, height=800)
y = 50

p1.insert_text((50, y), "SECTION 1 — One or More than one correct answer", fontsize=13)
y += 30
p1.insert_text((50, y), "1. Which of the following are prime numbers?", fontsize=12)
y += 16
p1.insert_text((60, y), "(A) 2  (B) 4  (C) 7  (D) 9", fontsize=11)
y += 30
p1.insert_text((50, y), "2. Select all even numbers below:", fontsize=12)
y += 16
p1.insert_text((60, y), "(A) 3  (B) 6  (C) 8  (D) 11", fontsize=11)
y += 40

p1.insert_text((50, y), "SECTION 2 — Single correct answer", fontsize=13)
y += 30
p1.insert_text((50, y), "3. What is the capital of India?", fontsize=12)
y += 16
p1.insert_text((60, y), "(A) Mumbai  (B) Delhi  (C) Kolkata  (D) Chennai", fontsize=11)
y += 30

# Q4 starts on page 1 and continues on page 2
p1.insert_text((50, y), "4. A train travels at 60 km/h for the first half of a journey", fontsize=12)
y += 16
p1.insert_text((60, y), "and 90 km/h for the second half.", fontsize=12)

# Page 2 — continuation of Q4 + new section
p2 = doc.new_page(width=600, height=800)
y2 = 50
p2.insert_text((60, y2), "What is the average speed?", fontsize=12)
y2 += 16
p2.insert_text((60, y2), "(A) 72  (B) 75  (C) 70  (D) 80", fontsize=11)
y2 += 40

p2.insert_text((50, y2), "SECTION 3 — Single Digit Integer type", fontsize=13)
y2 += 30
p2.insert_text((50, y2), "5. How many prime numbers are there below 10?", fontsize=12)
y2 += 40

p2.insert_text((50, y2), "SECTION 4 — Numerical / Decimal value type", fontsize=13)
y2 += 30
p2.insert_text((50, y2), "6. Calculate the value of pi to 2 decimal places.", fontsize=12)

doc.save("test_sections.pdf")

# Run the pipeline
doc_read = fitz.open("test_sections.pdf")
lines = extract_lines(doc_read)
questions = build_questions(lines)
rendered = render_questions(doc_read, questions)

print(f"Total questions: {len(rendered)}\n")
for q in rendered:
    sec = q["section"]
    print(f'{q["id"]}:')
    print(f'  section:     {sec["answer_type"]}')
    print(f'  images:      {len(q["images"])} (sizes: {[len(i) for i in q["images"]]})')
    print(f'  line_count:  {q["_debug"]["line_count"]}')
    print()
