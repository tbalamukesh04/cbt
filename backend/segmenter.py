from classifier import ParaClass

def segment_document(paragraphs: list[dict], left_margin: float, tolerance: float = 15.0) -> list[dict]:
    """
    Build questions from classified paragraphs.
    """
    questions = []
    
    current_q_text = []
    current_debug = {"paragraph_count": 0, "weak_joins": 0, "ambiguous_starts": 0}
    q_counter = 0
    last_paragraph = None

    def flush_current():
        nonlocal q_counter, current_q_text, current_debug, last_paragraph
        if current_q_text:
            q_counter += 1
            questions.append({
                "id": f"q{q_counter}",
                "text": "\n".join(current_q_text),
                "_debug": dict(current_debug)
            })
            current_q_text = []
            current_debug = {"paragraph_count": 0, "weak_joins": 0, "ambiguous_starts": 0}
            last_paragraph = None

    for p in paragraphs:
        p_class = p.get("class")
        ambiguous = p.get("ambiguous", False)
        
        if p_class == ParaClass.INSTRUCTION:
            # Drop instructions outright
            continue
            
        elif p_class == ParaClass.QUESTION_START:
            flush_current()
            current_q_text.append(p["text"])
            current_debug["paragraph_count"] += 1
            last_paragraph = p
            
        elif p_class == ParaClass.CONTINUATION:
            if not current_q_text:
                # Stranded continuation (could be options for an unsaved question or top of page)
                # Keep it in buffer, but mark weak
                current_q_text.append(p["text"])
                current_debug["paragraph_count"] += 1
                current_debug["weak_joins"] += 1
                if ambiguous:
                    current_debug["ambiguous_starts"] += 1
                last_paragraph = p
                continue
                
            # Continuation validation
            is_weak = False
            
            # Check indentation consistency
            indent_match = abs(p["x0"] - last_paragraph["x0"]) <= tolerance
            
            # Check vertical proximity if on same page
            v_gap_small = False
            if p["page"] == last_paragraph["page"] and p["col"] == last_paragraph["col"]:
                v_gap = p["y0"] - last_paragraph["y0"]
                # Rough logic: gap smaller than ~3-4 regular lines
                if 0 <= v_gap < 60:
                    v_gap_small = True
                    
            if not (indent_match or v_gap_small):
                is_weak = True

            current_q_text.append(p["text"])
            current_debug["paragraph_count"] += 1
            if is_weak:
                current_debug["weak_joins"] += 1
            if ambiguous:
                current_debug["ambiguous_starts"] += 1
                
            last_paragraph = p

    flush_current()
    
    # Safe Post-Processing (rule 7)
    final_questions = safe_post_process(questions, tolerance, left_margin)
    
    return final_questions


def safe_post_process(questions: list[dict], tolerance: float, left_margin: float) -> list[dict]:
    """
    Merge fragments ONLY if:
    - length < 10 chars
    - contains NO alphabetic chars
    - previous question exists
    - indentation matches previous
    (Indentation is tricky here because 'questions' block lost x0 metadata, 
    but the rule states we shouldn't use aggressive heuristics. 
    We will strictly merge stranded numeric fragments. Since we don't have x0 in Questions output,
    we'll rely heavily on characters.)
    """
    if not questions:
        return []
        
    cleaned = []
    
    for q in questions:
        text = q["text"].strip()
        stripped_alpha = "".join([c for c in text if c.isalpha()])
        
        # Checking if this is a fragment
        if len(text) < 10 and len(stripped_alpha) == 0 and len(cleaned) > 0:
            # Merge into previous
            prev = cleaned[-1]
            prev["text"] += f"\n{text}"
            prev["_debug"]["weak_joins"] += 1
        else:
            cleaned.append(q)
            
    # Re-index
    for idx, q in enumerate(cleaned):
        q["id"] = f"q{idx + 1}"
        
    return cleaned
