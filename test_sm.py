import sys, os, fitz
sys.path.insert(0, os.path.abspath("backend"))
from extractor import extract_lines
from segmenter import build_questions
from renderer import render_questions

# ── Build test PDF ─────────────────────────────────────────────────
doc = fitz.open()
p1 = doc.new_page(width=600, height=800)
y = 50

# Section 1 — multiple correct
p1.insert_text((50, y), "SECTION 1", fontsize=13); y += 18
p1.insert_text((50, y), "One or More than one correct answer", fontsize=11); y += 25
p1.insert_text((50, y), "1. Which are prime numbers?", fontsize=12); y += 16
p1.insert_text((60, y), "(A) 2  (B) 4  (C) 7  (D) 9", fontsize=11); y += 24
p1.insert_text((50, y), "2. Select all even numbers:", fontsize=12); y += 16
p1.insert_text((60, y), "(A) 3  (B) 6  (C) 8  (D) 11", fontsize=11); y += 30

# Section 2 — single correct
p1.insert_text((50, y), "SECTION 2", fontsize=13); y += 18
p1.insert_text((50, y), "Single correct answer", fontsize=11); y += 25
p1.insert_text((50, y), "3. Capital of India?", fontsize=12); y += 16
p1.insert_text((60, y), "(A) Mumbai  (B) Delhi  (C) Kolkata  (D) Chennai", fontsize=11); y += 24

# Q4 continues to page 2
p1.insert_text((50, y), "4. A train at 60 km/h for first half", fontsize=12); y += 16
p1.insert_text((60, y), "and 90 km/h for second half.", fontsize=12)

p2 = doc.new_page(width=600, height=800)
y2 = 50
p2.insert_text((60, y2), "(A) 72  (B) 75  (C) 70  (D) 80", fontsize=11); y2 += 35

# Section 3 — integer
p2.insert_text((50, y2), "SECTION 3", fontsize=13); y2 += 18
p2.insert_text((50, y2), "Single Digit Integer type", fontsize=11); y2 += 25
p2.insert_text((50, y2), "5. How many primes below 10?", fontsize=12); y2 += 35

# Section 4 — numerical
p2.insert_text((50, y2), "SECTION 4", fontsize=13); y2 += 18
p2.insert_text((50, y2), "Numerical / Decimal value", fontsize=11); y2 += 25
p2.insert_text((50, y2), "6. Value of pi to 2 decimal places?", fontsize=12)

doc.save("test_sm.pdf")

# ── Run pipeline ───────────────────────────────────────────────────
doc_r = fitz.open("test_sm.pdf")
lines = extract_lines(doc_r)
questions = build_questions(lines)
rendered = render_questions(doc_r, questions)

# ── Validate ───────────────────────────────────────────────────────
EXPECTED = [
    ("q1", "multiple_correct_mcq", 1),
    ("q2", "multiple_correct_mcq", 1),
    ("q3", "single_correct_mcq",   1),
    ("q4", "single_correct_mcq",   2),  # 2 images — multi-page
    ("q5", "integer_type",         1),
    ("q6", "numerical_type",       1),
]

print(f"{'ID':<6} {'Expected type':<25} {'Got type':<25} {'Images':>6}  {'Pass?'}")
print("-" * 75)
all_pass = True
for (exp_id, exp_type, exp_imgs), q in zip(EXPECTED, rendered):
    got_type = q["section"]["answer_type"]
    got_imgs = len(q["images"])
    ok = (got_type == exp_type) and (got_imgs == exp_imgs)
    if not ok:
        all_pass = False
    print(f"{q['id']:<6} {exp_type:<25} {got_type:<25} {got_imgs:>6}  {'PASS' if ok else 'FAIL'}")

print()
print("ALL PASS" if all_pass else "FAILURES DETECTED")
