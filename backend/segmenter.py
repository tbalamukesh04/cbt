import re

# Strong regex for starting questions
Q_START_REGEX = re.compile(r"^\d+[\.\)]|^Q\s*\d+", re.IGNORECASE)

def _is_noise(line: str) -> bool:
    """Identify lines to completely ignore (headers, whitespace, raw page digits)"""
    val = line.strip().lower()
    if not val:
        return True
    if val.isdigit():  # Unlikely to be useful, probably a standalone page number
        return True
    # Strip common headers
    if any(k in val for k in ["jee", "paper", "time:", "timestamp", "date:", "page"]):
        return True
    return False

def build_questions(lines: list[str]) -> list[dict]:
    questions = []
    current_question = []
    has_seen_question = False
    
    for raw_line in lines:
        line = raw_line.strip()
        
        # 1. Clean Line Stream
        if _is_noise(line):
            continue
            
        # 2. Strong Question Start Detection
        is_q_start = False
        if Q_START_REGEX.match(line) and len(line) > 3:
            is_q_start = True
            
        # 3. Instruction Handling
        if not has_seen_question:
            if is_q_start:
                has_seen_question = True
                current_question.append(line)
            # Else, it's instruction/intro text before first question. Ignore it completely.
            continue
            
        # 4. Segmentation Building
        if is_q_start:
            # Finalize previous question
            if current_question:
                questions.append({
                    "id": f"q{len(questions) + 1}",
                    "text": "\n".join(current_question),
                    "_debug": {"line_count": len(current_question)}
                })
            current_question = [line]
        else:
            # Continuation
            current_question.append(line)
            
    # Push the trailing question
    if current_question:
        questions.append({
            "id": f"q{len(questions) + 1}",
            "text": "\n".join(current_question),
            "_debug": {"line_count": len(current_question)}
        })
        
    # 5. Safe Cleanup
    cleaned = []
    for q in questions:
        # If question is too short to be real, merge it (e.g. stranded digits or cut-off options)
        if len(q["text"]) < 20 and len(cleaned) > 0:
            prev = cleaned[-1]
            prev["text"] += "\n" + q["text"]
            prev["_debug"]["line_count"] += q["_debug"]["line_count"]
        else:
            cleaned.append(q)
            
    # Reindex safely
    for i, q in enumerate(cleaned):
        q["id"] = f"q{i+1}"
            
    return cleaned
