import fitz
import json
import sys, os
sys.path.insert(0, os.path.abspath('backend'))
from extractor import extract_lines
from segmenter import build_questions

# We don't need a mock, because PyMuPDF directly supports local pixmap caching rendering
# The only requirement is that we test against physical elements so PyMuPDF doesn't render empty spans

doc = fitz.open()
page1 = doc.new_page(width=600, height=800)

y = 50
page1.insert_text((50, y), "1. Calculate the kinetic energy limit.", fontsize=12)
y += 20
# Corrupted line: The formula renders as two unreadable elements
page1.insert_text((50, y), "\ufffd = 1/2 m v □", fontsize=12)
y += 30

# Clean line
page1.insert_text((50, y), "2. What is the value of force?", fontsize=12)

doc.save("test_visual.pdf")

doc2 = fitz.open("test_visual.pdf")
lines = extract_lines(doc2)

# Print intermediate lines
print("--- PRE-SEGMENTATION EXTRACTED LINES (VISUAL HYBRID APPLIED) ---")
for l in lines:
    txt = l["text"]
    # Truncate large base64 payload strings so console is somewhat readable
    if "<math_image" in txt:
       start = txt.find("<math_image")
       end = txt.find("/>", start) + 2
       txt = txt[:start] + "<math_image src=\"data:image/png;base64,[...TRUNCATED_FOR_VIEW...]\"/>" + txt[end:]
    print(txt)


print("\n--- FINAL SEGMENTED OUTPUT ---")
res = build_questions(lines)
for r in res:
    txt = r["text"]
    if "<math_image" in txt:
       start = txt.find("<math_image")
       end = txt.find("/>", start) + 2
       txt = txt[:start] + "<math_image src=\"data:image/png;base64,[...TRUNCATED_FOR_VIEW...]\"/>" + txt[end:]
    r["text"] = txt

print(json.dumps(res, indent=2))
