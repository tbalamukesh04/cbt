import fitz
from pdf_extractor import extract_raw_blocks
from layout import reconstruct_reading_order, build_lines, build_paragraphs
from classifier import classify_paragraph
from segmenter import segment_document

doc = fitz.open('test_jee.pdf')
raw = extract_raw_blocks(doc)
ordered = reconstruct_reading_order(raw)
lines = build_lines(ordered)
paras, lm = build_paragraphs(lines)
print("LeftMargin:", lm)
seen = False
for i, p in enumerate(paras):
    cls, ambig = classify_paragraph(p, lm, 15.0, seen)
    p["class"] = cls
    p["ambiguous"] = ambig
    if cls == "question_start": seen = True
    print(f"[{i}] {cls} (ambig={ambig}):\n{p['text']}\n---")
