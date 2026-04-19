"""
aligner.py
==========
Binds solution answers to question-paper questions using:
  1. Global sequential indexing (1–54 across the whole paper)
  2. Per-section validation with structural invariants

The aligner is intentionally separate from both parsers — it is the
constraint-enforcement layer that makes the system fault-tolerant
instead of "mostly working".

Invariants checked
------------------
  I1: For each section S, |answers_in_S| == |questions_in_S|   → PARTIAL / NO_SOLUTIONS
  I2: For each section S, answer types match expected type family  → TYPE_WARNING
  I3: Overall: total_bound == total_questions                     → is_aligned = False
"""

from document_model import (
    Section, Answer, ValidationReport, SectionValidation,
)

ABBREV = {
    "Physics":     "Phy",
    "Chemistry":   "Chem",
    "Mathematics": "Math",
    "Maths":       "Math",
}

# What answer shape is expected for each answer type?
_EXPECTED_SHAPES = {
    "single_correct_mcq":   "letter",
    "multiple_correct_mcq": "letter",
    "integer_type":         "numeric",
    "numerical_type":       "numeric",
}


def _answer_shape(ans: Answer) -> str:
    """Is the answer a 'letter' (MCQ) or 'numeric' (integer/decimal)?"""
    return "letter" if isinstance(ans.parsed, list) else "numeric"


def align(
    paper_sections: list[Section],
    global_answers: dict[int, Answer],
) -> ValidationReport:
    """
    Bind global_answers to questions in paper_sections.
    Returns a ValidationReport with per-section status.

    Binding is positional by global_index — no assumptions about
    section-internal numbering in the solutions PDF.
    """
    section_validations: list[SectionValidation] = []
    total_bound   = 0
    total_questions = sum(len(s.questions) for s in paper_sections)
    global_warnings: list[str] = []

    for sec in paper_sections:
        bound_count = 0
        type_warnings: list[str] = []
        missing_nums: list[int] = []

        expected_shape = _EXPECTED_SHAPES.get(sec.answer_type, "letter")

        for q in sec.questions:
            ans = global_answers.get(q.global_index)

            if ans is None:
                q.binding_status = "missing"
                missing_nums.append(q.global_index)
            else:
                q.answer         = ans
                q.binding_status = "bound"
                bound_count     += 1

                # I2: type consistency check
                if _answer_shape(ans) != expected_shape:
                    type_warnings.append(
                        f"Q{q.global_index}: expected {expected_shape}, "
                        f"got {_answer_shape(ans)} ({ans.raw!r})"
                    )

        total_bound += bound_count

        # ── Determine status ──────────────────────────────────────────────
        n_qs = len(sec.questions)
        if bound_count == 0:
            status = "NO_SOLUTIONS"
        elif bound_count == n_qs:
            status = "OK" if not type_warnings else "TYPE_WARNING"
        else:
            status = "PARTIAL"

        # ── Build issues list ─────────────────────────────────────────────
        issues: list[str] = []

        if sec.expected_count and sec.actual_count != sec.expected_count:
            issues.append(
                f"Header said {sec.expected_count} questions; "
                f"parsed {sec.actual_count}"
            )

        if missing_nums:
            issues.append(
                f"{len(missing_nums)} answer(s) not found: "
                + ", ".join(f"Q{n}" for n in missing_nums)
            )

        issues.extend(type_warnings)

        subj_abbrev = ABBREV.get(sec.subject, sec.subject[:4])
        section_validations.append(SectionValidation(
            section_label  = f"{subj_abbrev} {sec.name}",
            subject        = sec.subject,
            section_name   = sec.name,
            answer_type    = sec.answer_type,
            q_count        = n_qs,
            ans_count      = bound_count,
            expected_count = sec.expected_count,
            status         = status,
            issues         = issues,
        ))

    # ── Global invariant I3 ───────────────────────────────────────────────────
    if total_bound < total_questions:
        global_warnings.append(
            f"Only {total_bound}/{total_questions} questions have answers bound."
        )

    report = ValidationReport(
        sections        = section_validations,
        is_aligned      = (total_bound == total_questions),
        total_questions = total_questions,
        total_bound     = total_bound,
        warnings        = global_warnings,
    )

    print(f"[ALIGNER] {total_bound}/{total_questions} bound  "
          f"aligned={report.is_aligned}")
    for sv in section_validations:
        flag = "✓" if sv.status == "OK" else "✗"
        print(f"  {flag} {sv.section_label}: {sv.ans_count}/{sv.q_count}  [{sv.status}]")
        for issue in sv.issues:
            print(f"      → {issue}")

    return report
