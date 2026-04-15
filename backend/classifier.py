import re

class ParaClass:
    QUESTION_START = "question_start"
    INSTRUCTION = "instruction"
    CONTINUATION = "continuation"

# Strict regex
Q_START_REGEX = re.compile(
    r"^(?:Question|Q)\s*\.?\s*([0-9]+)\s*[\.\-\)]|"
    r"^([0-9]+)\s*[\.\)]"
)

# Weak/ambiguous regex (looks like a question number but lacks structure)
Q_WEAK_REGEX = re.compile(r"^[0-9]+")

INSTRUCTION_KEYWORDS = [
    "instructions",
    "read the following",
    "answer all",
    "section",
    "part "
]

def classify_paragraph(p: dict, left_margin: float, tolerance: float = 15.0, has_seen_question: bool = False) -> tuple[str, bool]:
    """
    Classify a paragraph block.
    Returns (classification_string, is_ambiguous_start)
    """
    text = p["text"]
    x0 = p["x0"]
    text_lower = text.lower()
    
    # Check align
    is_left_aligned = abs(x0 - left_margin) <= tolerance
    
    # Check instructions FIRST
    is_keyword_match = any(kw in text_lower[:50] for kw in INSTRUCTION_KEYWORDS)
    if is_keyword_match or (not has_seen_question and len(text) > 10 and not Q_START_REGEX.match(text)):
        return ParaClass.INSTRUCTION, False

    # Check Question Start
    if Q_START_REGEX.match(text):
        if is_left_aligned:
            return ParaClass.QUESTION_START, False
        # If it matches regex but is heavily indented, it's ambiguous
        return ParaClass.CONTINUATION, True
        
    # Weak match fallback
    if Q_WEAK_REGEX.match(text) and is_left_aligned:
        return ParaClass.CONTINUATION, True

    return ParaClass.CONTINUATION, False
