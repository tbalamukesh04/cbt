"""patch2_index.py — fix the 2 remaining missed patches"""
import sys

path = r'C:\Projects\CBT\frontend\index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Insert paperSessionId variable — find a unique substring around the comment
TARGET1 = '// \u2500\u2500 Upload \u2500\u2500'
if TARGET1 in content:
    idx = content.index(TARGET1)
    # Find the newline just before it
    line_start = content.rfind('\n', 0, idx) + 1
    old_line = content[line_start:content.index('\n', idx)]
    # insert the let declaration before this whole comment block
    content = content[:line_start] + '  let paperSessionId = localStorage.getItem("jee_session_id") || "";\n\n  ' + content[line_start:]
    print("OK: inserted paperSessionId")
else:
    print("MISS: upload comment not found")

# 2. Fix debug table filter (forEach entry)
OLD2 = '(data.debug_lines || []).forEach(entry => {'
NEW2 = '(data.debug_lines || [])\n        .filter(e => e.category !== "header")\n        .forEach(entry => {'
if OLD2 in content:
    content = content.replace(OLD2, NEW2, 1)
    print("OK: debug filter patched")
else:
    print("MISS: debug forEach not found — searching...")
    idx = content.find('debug_lines')
    print(repr(content[idx:idx+120]))

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done.")
