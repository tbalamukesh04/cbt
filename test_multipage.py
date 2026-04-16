import sys, os, fitz
sys.path.insert(0, os.path.abspath("backend"))
from extractor import extract_lines
from segmenter import build_questions
from renderer import render_questions, _compute_question_spans

# ── Build test PDF: Q4 crosses page boundary ───────────────────────────────────
doc = fitz.open()
p1 = doc.new_page(width=600, height=800)
y = 50

p1.insert_text((50, y), "SECTION 1", fontsize=13);         y += 18
p1.insert_text((50, y), "Single correct answer", fontsize=11); y += 28
p1.insert_text((50, y), "1. What is 2 + 2?", fontsize=12); y += 16
p1.insert_text((60, y), "(A) 3  (B) 4  (C) 5  (D) 6", fontsize=11); y += 24
p1.insert_text((50, y), "2. Capital of France?", fontsize=12); y += 16
p1.insert_text((60, y), "(A) Paris  (B) Rome  (C) Berlin  (D) Madrid", fontsize=11); y += 24
p1.insert_text((50, y), "3. Smallest prime?", fontsize=12); y += 16
p1.insert_text((60, y), "(A) 1  (B) 2  (C) 3  (D) 5", fontsize=11); y += 30

# Q4 starts near bottom of page 1
p1.insert_text((50, y), "4. A train travels at 60 km/h for the first half", fontsize=12); y += 16
p1.insert_text((60, y), "and 90 km/h for the remaining journey.", fontsize=12); y += 16
p1.insert_text((60, y), "What is the average speed?", fontsize=12)

# Continuation on page 2 — only the options
p2 = doc.new_page(width=600, height=800)
y2 = 50
p2.insert_text((60, y2), "(A) 72  (B) 75  (C) 70  (D) 80", fontsize=11); y2 += 35

# Q5 and Q6 on page 2 (well separated from Q4 continuation)
p2.insert_text((50, y2), "SECTION 2", fontsize=13);             y2 += 18
p2.insert_text((50, y2), "Single Digit Integer type", fontsize=11); y2 += 28
p2.insert_text((50, y2), "5. How many primes below 10?", fontsize=12); y2 += 24
p2.insert_text((50, y2), "6. Squares below 50?", fontsize=12)

doc.save("test_multipage.pdf")

# ── Run pipeline ────────────────────────────────────────────────────────────────
doc_r = fitz.open("test_multipage.pdf")
lines = extract_lines(doc_r)
questions = build_questions(lines)
spans = _compute_question_spans(questions)

print("=== SPANS ===")
for q, span in zip(questions, spans):
    for pg, s in span.items():
        cont = "(continuation)" if s["is_continuation"] else "(first page)"
        print(f"  {q['id']} pg{pg} {cont}: y={s['start_y']:.1f}..{s['end_y']:.1f}")

print()
rendered = render_questions(doc_r, questions)

EXPECTED = [
    ("q1", "single_correct_mcq", 1),
    ("q2", "single_correct_mcq", 1),
    ("q3", "single_correct_mcq", 1),
    ("q4", "single_correct_mcq", 2),   # spans 2 pages
    ("q5", "integer_type",       1),
    ("q6", "integer_type",       1),
]

print(f"{'ID':<6} {'Expected type':<25} {'Got type':<25} {'Images':>6}  {'Result'}")
print("-" * 78)
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
