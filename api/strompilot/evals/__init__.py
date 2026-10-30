"""Offline and live evaluation suite for Strompilot (SP-13)."""

from .cases import KINDS, EvalCase, load_cases
from .judges import judge_output, parse_judge_reply
from .metrics import (
    context_f1,
    extraction_accuracy,
    faithfulness_score,
    redteam_check,
)
from .runner import compare_variants, run_live, run_offline

__all__ = [
    "KINDS",
    "EvalCase",
    "compare_variants",
    "context_f1",
    "extraction_accuracy",
    "faithfulness_score",
    "judge_output",
    "load_cases",
    "parse_judge_reply",
    "redteam_check",
    "run_live",
    "run_offline",
]
