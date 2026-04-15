import re

def is_corrupted(line: str) -> bool:
    """Check if the line contains known corruption patterns."""
    checks = [
        "□" in line,
        "\ufffd" in line,
        re.search(r"C\s*/\s*m\s*[23]", line),
        re.search(r"\d+\s*/\s*\d+\s*[a-zA-Zπ]", line)
    ]
    return any(checks)

def repair_line(line: str) -> str:
    """Targeted repair for known math and character rendering corruptions."""
    if not is_corrupted(line):
        return line
        
    repaired = line
    
    # B. Garbage Symbol Removal (CONDITIONAL)
    repaired = repaired.replace("□", "").replace("\ufffd", "")
    
    # A. Unit Repair (SAFE)
    # Convert C / m 3 -> C/m^3
    repaired = re.sub(r"C\s*/\s*m\s*([23])", r"C/m^\1", repaired)
    
    # C. Fraction Pattern Repair (LIMITED)
    # Convert '5 / 2π' removing spaces around '/'
    repaired = re.sub(
        r"(\d+)\s*/\s*(\d+\s*[a-zA-Zπ])",
        r"\1/\2",
        repaired
    )
    
    # Collapse multiple spaces that might have been created by garbage removal
    # but only if spaces were adjacent to garbage. We must be safe.
    repaired = re.sub(r"\s+", " ", repaired).strip()
    
    return repaired
