"""
document_model.py
=================
Shared data model for both the question-paper pipeline and the solutions pipeline.
Both parsers emit these types; the aligner consumes them.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Union


# ── Answer ─────────────────────────────────────────────────────────────────────
@dataclass
class Answer:
    raw:        str                        # "AD", "3", "2.50"
    parsed:     Union[list[str], str]      # ["A","D"] | "3"
    confidence: float = 1.0               # 1.0 = direct match, 0.7 = table, 0.5 = inferred
    hint:       str   = ""                # solution/explanation text from PDF

    def to_json(self):
        return {
            "raw":        self.raw,
            "parsed":     self.parsed,
            "confidence": self.confidence,
            "hint":       self.hint,
        }


# ── Question ────────────────────────────────────────────────────────────────────
@dataclass
class Question:
    section_index:  int          # 1-based within its section
    global_index:   int          # 1-based across the whole paper (1–54)
    lines:          list = field(default_factory=list)   # raw line dicts from extractor
    images:         list = field(default_factory=list)   # filled by renderer
    answer:         Optional[Answer] = None
    binding_status: str = "unbound"   # unbound | bound | missing

    def to_json(self):
        return {
            "section_index":  self.section_index,
            "global_index":   self.global_index,
            "images":         self.images,
            "answer":         self.answer.to_json() if self.answer else None,
            "binding_status": self.binding_status,
        }


# ── Section ─────────────────────────────────────────────────────────────────────
@dataclass
class Section:
    name:           str
    subject:        str
    answer_type:    str
    expected_count: Optional[int] = None   # from "This section contains N questions"
    questions:      list = field(default_factory=list)   # list[Question]

    @property
    def actual_count(self) -> int:
        return len(self.questions)

    @property
    def count_ok(self) -> bool:
        if self.expected_count is None:
            return True
        return self.actual_count == self.expected_count

    def to_json(self):
        return {
            "name":           self.name,
            "subject":        self.subject,
            "answer_type":    self.answer_type,
            "expected_count": self.expected_count,
            "actual_count":   self.actual_count,
            "questions":      [q.to_json() for q in self.questions],
        }


# ── Per-section solution bucket ──────────────────────────────────────────────────
@dataclass
class SectionAnswers:
    subject:      str
    section_name: str
    answers:      dict = field(default_factory=dict)   # {global_q_num (int) → Answer}


# ── Validation ──────────────────────────────────────────────────────────────────
@dataclass
class SectionValidation:
    section_label:  str
    subject:        str
    section_name:   str
    answer_type:    str
    q_count:        int
    ans_count:      int
    expected_count: Optional[int]
    status:         str     # OK | PARTIAL | NO_SOLUTIONS | COUNT_MISMATCH
    issues:         list = field(default_factory=list)   # list[str]

    def to_json(self):
        return {
            "section_label":  self.section_label,
            "subject":        self.subject,
            "section_name":   self.section_name,
            "answer_type":    self.answer_type,
            "q_count":        self.q_count,
            "ans_count":      self.ans_count,
            "expected_count": self.expected_count,
            "status":         self.status,
            "issues":         self.issues,
        }


@dataclass
class ValidationReport:
    sections:        list = field(default_factory=list)   # list[SectionValidation]
    is_aligned:      bool = False
    total_questions: int  = 0
    total_bound:     int  = 0
    warnings:        list = field(default_factory=list)   # list[str]

    def to_json(self):
        return {
            "is_aligned":      self.is_aligned,
            "total_questions": self.total_questions,
            "total_bound":     self.total_bound,
            "sections":        [s.to_json() for s in self.sections],
            "warnings":        self.warnings,
        }


# ── Session payload (stored in-memory between /upload and /upload_solutions) ────
@dataclass
class PaperSession:
    session_id: str
    sections:   list    # list[Section]

    @property
    def total_questions(self) -> int:
        return sum(len(s.questions) for s in self.sections)
