import re

Q_START_REGEX = re.compile(r"^\d+[\.\)]|^Q\s*\d+", re.IGNORECASE)
SECTION_REGEX = re.compile(
    r"^section\s*[-–—:]?\s*([A-Za-z0-9]+)",
    re.IGNORECASE,
)

# Answer-type inference from section description keywords
_ANSWER_TYPE_MAP = [
    (r"one\s+or\s+more|multiple\s+correct|more\s+than\s+one", "multiple_correct_mcq"),
    (r"single\s+correct|only\s+one\s+correct",                "single_correct_mcq"),
    (r"numerical|integer|numeric\s+value",                     "numerical"),
    (r"matrix\s+match|matching",                               "matrix_match"),
    (r"paragraph|comprehension|passage",                       "comprehension"),
]


def _infer_answer_type(description: str) -> str:
    """Map a section description string to a concrete answer_type enum."""
    desc_lower = description.lower()
    for pattern, answer_type in _ANSWER_TYPE_MAP:
        if re.search(pattern, desc_lower):
            return answer_type
    return "mcq"


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
    return bool(SECTION_REGEX.match(text.strip()))


def build_questions(lines: list[dict]) -> list[dict]:
    """
    Segment lines into questions with section awareness.
    Section headers and their descriptions are captured and attached to
    every question within that section.
    """
    questions = []
    current_lines = []
    has_seen_question = False

    # Active section state
    current_section = None
    pending_section_name = None  # set when we see SECTION header, waiting for description

    def flush():
        nonlocal current_lines
        if current_lines:
            questions.append({
                "id": f"q{len(questions) + 1}",
                "lines": list(current_lines),
                "section": dict(current_section) if current_section else None,
                "_debug": {"line_count": len(current_lines)},
            })
            current_lines = []

    for line in lines:
        text = line["text"].strip()

        if _is_noise(text):
            continue

        # --- Section header detection ---
        m = SECTION_REGEX.match(text)
        if m:
            # Flush any open question before switching section
            flush()
            section_label = m.group(1).upper()
            pending_section_name = f"SECTION {section_label}"
            # The full line might contain the description too
            # (e.g. "SECTION A: One or More than one correct type")
            remainder = text[m.end():].strip().lstrip(":-–—").strip()
            if remainder and len(remainder) > 5:
                current_section = {
                    "section_name": pending_section_name,
                    "section_description": remainder,
                    "answer_type": _infer_answer_type(remainder),
                }
                pending_section_name = None
            continue

        # If we just saw a section header, the next non-noise non-question line
        # is treated as the section description
        if pending_section_name is not None:
            is_q = bool(Q_START_REGEX.match(text)) and len(text) > 3
            if not is_q:
                current_section = {
                    "section_name": pending_section_name,
                    "section_description": text,
                    "answer_type": _infer_answer_type(text),
                }
                pending_section_name = None
                continue
            else:
                # No description line — section had no subtitle
                current_section = {
                    "section_name": pending_section_name,
                    "section_description": "",
                    "answer_type": "mcq",
                }
                pending_section_name = None
                # Fall through to handle this line as a question start

        # --- Question start detection ---
        is_q_start = bool(Q_START_REGEX.match(text)) and len(text) > 3

        if not has_seen_question:
            if is_q_start:
                has_seen_question = True
                current_lines.append(line)
            continue

        if is_q_start:
            flush()
            current_lines.append(line)
        else:
            current_lines.append(line)

    flush()

    # Safe cleanup — merge trivially short questions into previous
    cleaned = []
    for q in questions:
        total_text = " ".join(l["text"] for l in q["lines"])
        if len(total_text) < 20 and cleaned:
            prev = cleaned[-1]
            prev["lines"].extend(q["lines"])
            prev["_debug"]["line_count"] += q["_debug"]["line_count"]
        else:
            cleaned.append(q)

    for i, q in enumerate(cleaned):
        q["id"] = f"q{i + 1}"

    return cleaned
