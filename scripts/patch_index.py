"""
patch_index.py  — applies the session_id + ValidationReport patches to index.html
"""
path = r'C:\Projects\CBT\frontend\index.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

patches = []

# 1. Add paperSessionId variable declaration before the upload listener
patches.append((
    '  // \u2500\u2500 Upload \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n  document.getElementById("uploadBtn")',
    '  // \u2500\u2500 Upload \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n  let paperSessionId = localStorage.getItem("jee_session_id") || "";\n\n  document.getElementById("uploadBtn")',
))

# 2. Capture session_id from /upload response
patches.append((
    '''      nodes = data.nodes;
      render();
      setStatus(''',
    '''      nodes = data.nodes;
      paperSessionId = data.session_id || "";
      localStorage.setItem("jee_nodes",      JSON.stringify(nodes));
      localStorage.setItem("jee_session_id", paperSessionId);
      render();
      setStatus(''',
))

# 3. Remove the old localStorage.setItem("jee_nodes"...) line (now done above)
patches.append((
    '''      localStorage.setItem("jee_nodes", JSON.stringify(nodes));
      document.getElementById("startExamBar")''',
    '''      document.getElementById("startExamBar")''',
))

# 4. Solutions handler: pass session_id in URL
patches.append((
    '      const res  = await fetch(`${API}/upload_solutions`, { method: "POST", body: fd });',
    '      const url  = `${API}/upload_solutions?session_id=${encodeURIComponent(paperSessionId)}`;\n      const res  = await fetch(url, { method: "POST", body: fd });',
))

# 5. Add ValidationReport section before answer chips
patches.append((
    '      // Detected answer chips\n      const ansGrid = document.getElementById("ansGrid");',
    '''      // \u2500\u2500 Section Alignment Report (\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
      if (data.validation) {
        document.getElementById("validationWrap").style.display = "block";
        const vBody = document.getElementById("valTableBody");
        vBody.innerHTML = "";
        const ICON = { OK:"\u2705", PARTIAL:"\u26a0\ufe0f", NO_SOLUTIONS:"\u274c", COUNT_MISMATCH:"\u26a0\ufe0f", TYPE_WARNING:"\u26a0\ufe0f" };
        const BG   = { OK:"#f0fdf4", PARTIAL:"#fffbeb", NO_SOLUTIONS:"#fef2f2", COUNT_MISMATCH:"#fffbeb", TYPE_WARNING:"#fffbeb" };
        const TL   = { single_correct_mcq:"Single", multiple_correct_mcq:"Multi",
                       integer_type:"Integer", numerical_type:"Numerical" };
        data.validation.sections.forEach(s => {
          const tr = document.createElement("tr");
          tr.style.background = BG[s.status] || "";
          tr.innerHTML = `
            <td style="font-weight:600">${s.section_label}</td>
            <td>${TL[s.answer_type] || s.answer_type}</td>
            <td style="text-align:center">${s.expected_count ?? "\u2014"}</td>
            <td style="text-align:center">${s.q_count}</td>
            <td style="text-align:center;font-weight:700">${s.ans_count}</td>
            <td>${ICON[s.status] || "?"} ${s.status}</td>
            <td style="font-size:10px;color:#64748b">${s.issues.join(" | ") || "\u2014"}</td>`;
          vBody.appendChild(tr);
        });
      }

      // Detected answer chips
      const ansGrid = document.getElementById("ansGrid");''',
))

# 6. Filter header lines in debug table
patches.append((
    '      (data.debug_lines || []).forEach(entry => {\n        if (entry.category === "header") return;',
    '      (data.debug_lines || [])\n        .filter(e => e.category !== "header")\n        .forEach(entry => {',
))

result = content
for old, new in patches:
    if old in result:
        result = result.replace(old, new, 1)
        print(f"OK: {repr(old[:60])}")
    else:
        print(f"MISS: {repr(old[:80])}")

with open(path, 'w', encoding='utf-8') as f:
    f.write(result)
print("Done.")
