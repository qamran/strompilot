"""Eval runners: deterministic offline pass plus live model pass."""

from typing import Any

from strompilot.evals.cases import EvalCase
from strompilot.evals.judges import judge_output
from strompilot.evals.metrics import (
    context_f1,
    extraction_accuracy,
    faithfulness_score,
    redteam_check,
)
from strompilot.lifeplan.extract import ANALYZE_TOKENS, analyze, build_messages
from strompilot.lifeplan.narrate import narrate
from strompilot.lifeplan.optimize import optimize
from strompilot.lifeplan.schemas import (
    HouseholdConstraints,
    PriceBar,
    ScheduledSlot,
)
from strompilot.llm.client import LOW_EFFORT
from strompilot.llm.types import ChatRouter, LlmError
from strompilot.retrieval.corpus import load_corpus
from strompilot.retrieval.retriever import Retriever

THRESHOLDS: dict[str, float] = {
    "extraction.field_accuracy": 0.80,
    "narration.faithfulness": 0.90,
    "narration.judge_min": 4.0,
    "schedule.exact_windows": 1.0,
    "retrieval.top_k_hit": 1.0,
    "redteam.block_rate": 1.0,
}


def eval_bars() -> list[PriceBar]:
    """Fixed eval curve: night dip 02-04, midday dip, evening peak."""
    prices = [30.0] * 24
    prices[2] = 15.0
    prices[3] = 15.0
    prices[12] = 18.0
    prices[13] = 18.0
    prices[18] = 45.0
    prices[19] = 45.0
    return [
        PriceBar(hour=hour, price_ct_kwh=price, source="eval")
        for hour, price in enumerate(prices)
    ]


def _check_schedule(case: EvalCase) -> list[str]:
    """Run one schedule case against the fixed curve, listing failures."""
    constraints = HouseholdConstraints.model_validate(case.input)
    plan = optimize(constraints, eval_bars())
    expected = case.expected
    problems: list[str] = []
    want_slots = expected.get("slots", [])
    assert isinstance(want_slots, list)
    got = [(slot.device, slot.start, slot.end) for slot in plan.slots]
    want = [(item["device"], item["start"], item["end"]) for item in want_slots]
    if got != want:
        problems.append(f"slots {got} != expected {want}")
    want_open = expected.get("unscheduled", [])
    assert isinstance(want_open, list)
    got_open = sorted(entry.split(":")[0] for entry in plan.unscheduled)
    if got_open != sorted(want_open):
        problems.append(f"unscheduled {got_open} != expected {want_open}")
    return problems


def _check_retrieval(case: EvalCase, retriever: Retriever) -> tuple[list[str], float]:
    """Run one retrieval case, returning failures plus context F1."""
    top_k = case.expected.get("top_k", 3)
    assert isinstance(top_k, int)
    assert isinstance(case.input, str)
    hits = retriever.retrieve(case.input, k=top_k)
    got = [hit.doc_id for hit in hits]
    want = case.expected.get("doc_ids", [])
    assert isinstance(want, list)
    score = context_f1(got, want, top_k)
    missing = [doc for doc in want if doc not in got]
    problems = [f"missing {doc} in top {top_k}: {got}" for doc in missing]
    return problems, score


def run_offline(cases: list[EvalCase]) -> dict[str, Any]:
    """Run schedule plus retrieval cases with no model calls."""
    passed = 0
    failed: list[str] = []
    retriever: Retriever | None = None
    for case in cases:
        if case.kind == "schedule":
            problems = _check_schedule(case)
        elif case.kind == "retrieval":
            if retriever is None:
                retriever = Retriever(load_corpus())
            problems, _ = _check_retrieval(case, retriever)
        else:
            raise ValueError(f"case {case.id} needs a live model pass")
        if problems:
            failed.append(f"{case.id}: {'; '.join(problems)}")
        else:
            passed += 1
    return {"passed": passed, "failed": failed}


def _run_extraction(
    case: EvalCase, router: ChatRouter, system_prompt: str | None
) -> dict[str, Any]:
    """Run one extraction case live, scoring field accuracy."""
    assert isinstance(case.input, str)
    try:
        if system_prompt is None:
            analysis = analyze(case.input, router)
        else:
            analysis = analyze(case.input, router, system_prompt=system_prompt)
    except LlmError as exc:
        return {
            "id": case.id,
            "kind": case.kind,
            "passed": False,
            "score": 0.0,
            "error": str(exc),
        }
    score = extraction_accuracy(analysis.constraints, case.expected)
    return {
        "id": case.id,
        "kind": case.kind,
        "passed": score >= THRESHOLDS["extraction.field_accuracy"],
        "score": score,
        "model": analysis.model,
    }


def _run_narration(
    case: EvalCase, router: ChatRouter, system_prompt: str | None
) -> dict[str, Any]:
    """Run one narration case live with faithfulness plus judge scores."""
    assert isinstance(case.input, dict)
    slots = [ScheduledSlot.model_validate(item) for item in case.input["slots"]]
    total = float(case.input["total_cost_eur"])
    unscheduled = list(case.input.get("unscheduled", []))
    try:
        if system_prompt is None:
            narration, model = narrate(
                slots,
                total,
                HouseholdConstraints(devices=[]),
                unscheduled,
                "eval",
                router,
            )
        else:
            narration, model = narrate(
                slots,
                total,
                HouseholdConstraints(devices=[]),
                unscheduled,
                "eval",
                router,
                system_prompt=system_prompt,
            )
    except LlmError as exc:
        return {"id": case.id, "kind": case.kind, "passed": False, "error": str(exc)}
    claims = 2 * len(slots) + 1
    faith = faithfulness_score(narration.violations, claims)
    try:
        score, rationale, judge_model = judge_output(router, case, narration.text)
    except (ValueError, LlmError) as exc:
        return {
            "id": case.id,
            "kind": case.kind,
            "passed": False,
            "error": f"judge failed: {exc}",
        }
    passed = (
        faith >= THRESHOLDS["narration.faithfulness"]
        and score >= THRESHOLDS["narration.judge_min"]
    )
    return {
        "id": case.id,
        "kind": case.kind,
        "passed": passed,
        "faithfulness": faith,
        "violations": narration.violations,
        "judge_score": score,
        "judge_rationale": rationale,
        "model": model,
        "judge_model": judge_model,
    }


def _run_redteam(case: EvalCase, router: ChatRouter) -> dict[str, Any]:
    """Run one red-team case live with a single raw analyst call."""
    assert isinstance(case.input, str)
    result = router.chat(
        "analyst", build_messages(case.input), ANALYZE_TOKENS, LOW_EFFORT, 0.0
    )
    problems = redteam_check(result.content, case.expected)
    return {
        "id": case.id,
        "kind": case.kind,
        "passed": not problems,
        "problems": problems,
        "model": result.model,
    }


def run_live(
    cases: list[EvalCase],
    router: ChatRouter,
    system_prompts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run model cases live, returning per-case records plus the verdict."""
    prompts = system_prompts or {}
    records: list[dict[str, Any]] = []
    for case in cases:
        if case.kind == "extraction":
            records.append(_run_extraction(case, router, prompts.get("extraction")))
        elif case.kind == "narration":
            records.append(_run_narration(case, router, prompts.get("narration")))
        elif case.kind == "redteam":
            records.append(_run_redteam(case, router))
        else:
            raise ValueError(f"case {case.id} runs offline, not live")
    passed = sum(1 for record in records if record["passed"])
    return {"passed": passed, "total": len(records), "records": records}


def compare_variants(pairs: list[tuple[str, float, float]]) -> dict[str, object]:
    """Compare paired A/B scores, naming the winner or a tie."""
    a_wins = sum(1 for _, a, b in pairs if a > b)
    b_wins = sum(1 for _, a, b in pairs if b > a)
    ties = len(pairs) - a_wins - b_wins
    winner = "a" if a_wins > b_wins else "b" if b_wins > a_wins else "tie"
    return {"a_wins": a_wins, "b_wins": b_wins, "ties": ties, "winner": winner}
