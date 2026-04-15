import fitz
import json
import sys, os
sys.path.insert(0, os.path.abspath('backend'))
from extractor import extract_lines
from segmenter import build_questions

import ocr_recovery as ocr
original_ocr = ocr.run_ocr_on_region

def mock_ocr(page, bbox):
    # This simulates a perfect OCR read of a broken formula
    return "E = 1/2 m v^2"

import extractor
extractor.run_ocr_on_region = mock_ocr


doc = fitz.open()

# Generate a PDF with Instruction, Questions, and a broken math formula
page1 = doc.new_page(width=600, height=800)

y = 50
page1.insert_text((50, y), "1. Calculate the kinetic energy limit.", fontsize=12)
y += 20
# Corrupted line (will trigger in "□")
page1.insert_text((50, y), "□ = 1/2 m v □", fontsize=12)
y += 30

# Clean line (will be bypassed)
page1.insert_text((50, y), "2. What is the value of force?", fontsize=12)

doc.save("test_ocr.pdf")

doc2 = fitz.open("test_ocr.pdf")
lines = extract_lines(doc2)

# Print intermediate lines
print("--- PRE-SEGMENTATION EXTRACTED LINES (HYBRID RECOVERY APPLIED) ---")
for l in lines:
    print(l["text"])

print("\n--- FINAL SEGMENTED OUTPUT ---")
res = build_questions(lines)
print(json.dumps(res, indent=2))
