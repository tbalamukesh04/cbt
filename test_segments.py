import fitz
import json
import sys, os
sys.path.insert(0, os.path.abspath('backend'))
from extractor import extract_lines
from segmenter import build_questions

doc = fitz.open()
page1 = doc.new_page(width=600, height=800)

y = 50
page1.insert_text((50, y), "1. Calculate the kinetic energy limit.", fontsize=12)
y += 20
# Two adjacent math-corrupted lines → should merge into ONE region image
page1.insert_text((50, y), "\ufffd = 1/2 m v □", fontsize=12)
y += 16
page1.insert_text((50, y), "□ + 3/4 □ r^2", fontsize=12)
y += 30

# Clean text line
page1.insert_text((50, y), "2. What is the value of force?", fontsize=12)
y += 20
page1.insert_text((50, y), "The answer is 42 Newtons.", fontsize=12)

doc.save("test_region.pdf")

doc2 = fitz.open("test_region.pdf")
lines = extract_lines(doc2)

print("=== EXTRACTED LINE SEGMENTS ===")
for i, l in enumerate(lines):
    seg_summary = []
    for s in l["segments"]:
        if s["type"] == "text":
            seg_summary.append(f'TEXT("{s["content"]}")')
        elif s["type"] == "math_block":
            seg_summary.append(f'MATH_BLOCK(b64_len={len(s["src"])})')
    print(f"  Line {i}: text_only={repr(l['text_only'])}  segs={seg_summary}")

print()

questions = build_questions(lines)

print("=== SEGMENTED QUESTIONS ===")
for q in questions:
    seg_summary = []
    for s in q["segments"]:
        if s["type"] == "text":
            seg_summary.append(f'TEXT("{s["content"]}")')
        elif s["type"] == "math_block":
            seg_summary.append(f'MATH_BLOCK(b64_len={len(s["src"])})')
        elif s["type"] == "linebreak":
            seg_summary.append("BR")
    print(f'  {q["id"]}: lines={q["_debug"]["line_count"]}  segs={seg_summary}')
