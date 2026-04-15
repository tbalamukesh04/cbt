import re

Q_START_REGEX = re.compile(r"^\d+[\.\)]|^Q\s*\d+", re.IGNORECASE)

# Mapping keywords found in "Description" line to answer_type
DESCRIPTION_MAPPING = [
    (re.compile(r"one\s+or\s+more\s+than\s+one\s+correct", re.IGNORECASE), "multiple_correct_mcq"),
    (re.compile(r"multiple\s+correct", re.IGNORECASE), "multiple_correct_mcq"),
    (re.compile(r"single\s+correct", re.IGNORECASE), "single_correct_mcq"),
    (re.compile(r"single\s+digit\s+integer", re.IGNORECASE), "integer_type"),
    (re.compile(r"numerical", re.IGNORECASE), "numerical_type"),
]

DEFAULT_SECTION = {
    "name": "General Section",
    "description": "",
    "answer_type": "single_correct_mcq",
}


def _is_noise(text: str) -> bool:
    """Identify lines to completely ignore."""
    val = text.strip().lower()
    if not val:
        return True
    if val.isdigit():
        return True
    if any(k in val for k in ["jee", "paper", "time:", "timestamp", "date:", "page"]):
        return True
    return False


def _is_section_header(text: str) -> bool:
    """
    A line is a section header ONLY if:
    - contains 'SECTION'
    - OR is uppercase AND short (< 12 words)
    """
    s = text.strip()
    if not s:
        return False
    
    # Exclusion: Option lines like (A) or (1) should never be sections
    if re.match(r"^\(?([A-Da-d0-9])[\.\)]", s):
        return False

    if "SECTION" in s.upper():
        return True
    
    words = s.split()
    if len(words) < 12 and s.isupper():
        # Avoid treating question labels like "Q1." as sections if they are uppercase
        if Q_START_REGEX.match(s):
            return False
        return True
    
    return False


def _map_section_to_type(header: str, description: str) -> str:
    """Maps section text or description to a known answer type."""
    combined = (header + " " + description).lower()
    for pattern, a_type in DESCRIPTION_MAPPING:
        if pattern.search(combined):
            return a_type
    return "single_correct_mcq"  # Fallback


def build_questions(lines: list[dict]) -> list[dict]:
    """
    Segment lines into questions using text-based boundary detection and
    robust section state tracking.
    """
    questions = []
    current_lines = []
    current_section = dict(DEFAULT_SECTION)
    has_seen_question = False

    def flush():
        nonlocal current_lines
        if current_lines:
            questions.append({
                "id": f"q{len(questions) + 1}",
                "lines": list(current_lines),
                "section": dict(current_section),
                "_debug": {"line_count": len(current_lines)},
            })
            current_lines = []

    # Iterate with index to allow lookahead for description
    i = 0
    while i < len(lines):
        line = lines[i]
        text = line["text"].strip()

        if _is_noise(text):
            i += 1
            continue

        # PART 3 - Priority Order: Question starts take priority over section headers
        is_q_start = bool(Q_START_REGEX.match(text)) and len(text) > 3

        if is_q_start:
            # Handle question start
            flush()
            if not has_seen_question:
                has_seen_question = True
            current_lines.append(line)
            i += 1
            continue

        if _is_section_header(text):
            # PART 2 - On Section Detection
            flush()
            
            # Extract Description Line (lookahead)
            description = ""
            header_text = text
            if i + 1 < len(lines):
                desc_line = lines[i+1]
                desc_text = desc_line["text"].strip()
                
                # ONLY consume the next line as a description if it DOES NOT look like a question
                # and is not noise (like a page number)
                if not Q_START_REGEX.match(desc_text) and not _is_noise(desc_text):
                    description = desc_text
                    i += 1 # Advance to consume description line
            
            i += 1 # Advance to consume section header

            current_section = {
                "name": header_text,
                "description": description,
                "answer_type": _map_section_to_type(header_text, description),
            }
            continue

        # Continuation of current question or pre-question noise
        if has_seen_question:
            current_lines.append(line)
        
        i += 1

    flush()

    # Final cleanup (conservative)
    cleaned = []
    for q in questions:
        total_text = " ".join(l["text"] for l in q["lines"])
        if len(total_text.strip()) < 5 and cleaned:
            prev = cleaned[-1]
            prev["lines"].extend(q["lines"])
            prev["_debug"]["line_count"] += q["_debug"]["line_count"]
        else:
            cleaned.append(q)

    for i, q in enumerate(cleaned):
        q["id"] = f"q{i + 1}"

    return cleaned
