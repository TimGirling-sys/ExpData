"""Reference linker that prioritizes deterministic rules before LLM fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.llm_client import LLMClient

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class Candidate:
    id: str
    label: str
    text: str = ""
    aliases: tuple[str, ...] = ()
    table_id: str | None = None
    row_index: int | None = None
    mention_index: int | None = None


@dataclass(frozen=True)
class Reference:
    id: str
    text: str
    mention_index: int | None = None
    table_id: str | None = None
    row_index: int | None = None


@dataclass
class LinkResult:
    reference_id: str
    candidate_id: str | None
    link_confidence: float
    link_method: str
    review_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Linker:
    """Resolve references to candidates using rules and optional LLM arbitration."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        *,
        review_threshold: float = 0.65,
        mention_window: int = 4,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.review_threshold = review_threshold
        self.mention_window = mention_window
        self._system_prompt = _load_prompt("linking_system.txt")
        self._user_template = _load_prompt("linking_user.txt")

    def link(self, references: Iterable[Reference], candidates: Iterable[Candidate]) -> list[LinkResult]:
        candidate_list = list(candidates)
        return [self._link_one(reference, candidate_list) for reference in references]

    def _link_one(self, reference: Reference, candidates: list[Candidate]) -> LinkResult:
        rule_scores: dict[str, float] = {}
        matches: dict[str, Candidate] = {}

        exact = self._exact_label_match(reference, candidates)
        if exact:
            matches["exact_label"] = exact
            rule_scores[exact.id] = max(rule_scores.get(exact.id, 0.0), 0.96)

        row_match = self._table_row_alignment(reference, candidates)
        if row_match:
            matches["table_row"] = row_match
            rule_scores[row_match.id] = max(rule_scores.get(row_match.id, 0.0), 0.88)

        nearest = self._nearest_mention(reference, candidates)
        if nearest:
            matches["nearest_window"] = nearest
            rule_scores[nearest.id] = max(rule_scores.get(nearest.id, 0.0), 0.74)

        # Deterministic certainty path.
        if "exact_label" in matches:
            candidate = matches["exact_label"]
            confidence = rule_scores[candidate.id]
            return self._result(reference, candidate.id, confidence, "rule")

        # Deterministic consensus path.
        if rule_scores:
            ranked = sorted(rule_scores.items(), key=lambda kv: kv[1], reverse=True)
            best_id, best_score = ranked[0]
            second_best = ranked[1][1] if len(ranked) > 1 else 0.0
            if best_score - second_best >= 0.2:
                return self._result(reference, best_id, best_score, "rule")

        # LLM fallback for ambiguity.
        llm_candidate_id, llm_conf = self._llm_fallback(reference, candidates)
        if llm_candidate_id and llm_conf is not None:
            if rule_scores and llm_candidate_id in rule_scores:
                combined = min(1.0, 0.6 * rule_scores[llm_candidate_id] + 0.4 * llm_conf)
                return self._result(reference, llm_candidate_id, combined, "hybrid")
            return self._result(reference, llm_candidate_id, llm_conf, "llm")

        if rule_scores:
            best_id, best_score = sorted(rule_scores.items(), key=lambda kv: kv[1], reverse=True)[0]
            return self._result(reference, best_id, best_score * 0.85, "rule")

        return self._result(reference, None, 0.0, "llm", reason="No deterministic or LLM link found")

    def _exact_label_match(self, reference: Reference, candidates: list[Candidate]) -> Candidate | None:
        needle = _normalize(reference.text)
        for candidate in candidates:
            labels = {_normalize(candidate.label), *(_normalize(alias) for alias in candidate.aliases)}
            if needle and needle in labels:
                return candidate
        return None

    def _table_row_alignment(self, reference: Reference, candidates: list[Candidate]) -> Candidate | None:
        if reference.table_id is None or reference.row_index is None:
            return None
        aligned = [
            candidate
            for candidate in candidates
            if candidate.table_id == reference.table_id and candidate.row_index == reference.row_index
        ]
        return aligned[0] if len(aligned) == 1 else None

    def _nearest_mention(self, reference: Reference, candidates: list[Candidate]) -> Candidate | None:
        if reference.mention_index is None:
            return None
        in_window = [
            candidate
            for candidate in candidates
            if candidate.mention_index is not None
            and abs(candidate.mention_index - reference.mention_index) <= self.mention_window
        ]
        if not in_window:
            return None
        return sorted(in_window, key=lambda cand: abs(cand.mention_index - reference.mention_index))[0]

    def _llm_fallback(self, reference: Reference, candidates: list[Candidate]) -> tuple[str | None, float | None]:
        if not self.llm_client.enabled:
            return None, None

        user_prompt = self._user_template.format(
            reference_text=reference.text,
            reference_id=reference.id,
            candidates_json=json.dumps(
                [
                    {
                        "id": c.id,
                        "label": c.label,
                        "text": c.text,
                        "table_id": c.table_id,
                        "row_index": c.row_index,
                        "mention_index": c.mention_index,
                    }
                    for c in candidates
                ],
                ensure_ascii=False,
            ),
        )
        response = self.llm_client.complete_json(system_prompt=self._system_prompt, user_prompt=user_prompt, temperature=0.0)
        if not response:
            return None, None

        candidate_id = response.get("candidate_id")
        confidence = response.get("confidence")
        if not isinstance(candidate_id, str):
            return None, None
        if not isinstance(confidence, (int, float)):
            confidence = 0.55
        return candidate_id, float(max(0.0, min(1.0, confidence)))

    def _result(
        self,
        reference: Reference,
        candidate_id: str | None,
        confidence: float,
        method: str,
        reason: str | None = None,
    ) -> LinkResult:
        review_reason = reason
        if review_reason is None and confidence < self.review_threshold:
            review_reason = f"Low confidence ({confidence:.2f}) below threshold {self.review_threshold:.2f}"

        return LinkResult(
            reference_id=reference.id,
            candidate_id=candidate_id,
            link_confidence=confidence,
            link_method=method,
            review_reason=review_reason,
        )


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8").strip()
