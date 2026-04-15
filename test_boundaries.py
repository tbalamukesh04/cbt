import fitz
import json
import sys, os
sys.path.insert(0, os.path.abspath("backend"))
from extractor import extract_lines
from segmenter import build_questions
from renderer import render_questions, _compute_question_spans, _safe_top, _safe_bottom, PADDING_Y

# Build a PDF with tightly packed questions (small gaps)
doc = fitz.open()
p1 = doc.new_page(width=600, height=800)

y = 50
p1.insert_text((50, y), "Instructions: Read carefully.", fontsize=12)
y += 25

# Q1 — starts at ~75, options end at ~125
p1.insert_text((50, y), "1. What is 2 + 2?", fontsize=12); y += 16
p1.insert_text((60, y), "(A) 3  (B) 4  (C) 5  (D) 6", fontsize=11); y += 16

# Only 8px gap before Q2
y += 8

# Q2 — starts at ~115ish
q2_start = y
p1.insert_text((50, y), "2. What is the capital of France?", fontsize=12); y += 16
p1.insert_text((60, y), "(A) London  (B) Paris  (C) Rome  (D) Berlin", fontsize=11); y += 16

# Only 8px gap before Q3
y += 8

# Q3
q3_start = y
p1.insert_text((50, y), "3. Solve: x^2 - 4 = 0", fontsize=12); y += 16
p1.insert_text((60, y), "(A) x=1  (B) x=2  (C) x=3  (D) x=4", fontsize=11)

doc.save("test_tight.pdf")
doc_read = fitz.open("test_tight.pdf")

lines = extract_lines(doc_read)
questions = build_questions(lines)

# Show the raw content bounds vs safe crop bounds
spans = _compute_question_spans(questions)

print("=== RAW vs SAFE BOUNDARIES (page 0) ===")
for qi, q in enumerate(questions):
    cur = spans[qi][0]

    prev_end = None
    for pi in range(qi - 1, -1, -1):
        if 0 in spans[pi]:
            prev_end = spans[pi][0]["end_y"]
            break

    next_start = None
    for ni in range(qi + 1, len(questions)):
        if 0 in spans[ni]:
            next_start = spans[ni][0]["start_y"]
            break

    safe_t = _safe_top(cur["start_y"], prev_end)
    safe_b = _safe_bottom(cur["end_y"], next_start)

    print(f"\n{q['id']}:")
    print(f"  Raw content:   y0={cur['start_y']:.1f}  y1={cur['end_y']:.1f}")
    print(f"  Old crop (±20): y0={cur['start_y']-20:.1f}  y1={cur['end_y']+20:.1f}")
    print(f"  Safe crop:      y0={safe_t:.1f}  y1={safe_b:.1f}")

    if qi > 0:
        old_overlap = (cur["start_y"] - 20) < spans[qi-1][0]["end_y"]
        safe_overlap = safe_t < spans[qi-1][0]["end_y"]
        print(f"  Old overlaps prev? {old_overlap}   Safe overlaps prev? {safe_overlap}")

# Render and report sizes
rendered = render_questions(doc_read, questions)
print(f"\n=== RENDERED: {len(rendered)} questions ===")
for q in rendered:
    print(f"  {q['id']}: {len(q['images'])} image(s), b64 sizes: {[len(i) for i in q['images']]}")
