import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


class GeneratedCopilotResponse(BaseModel):
    answer: str
    support: Literal["supported", "partially_supported", "insufficient_evidence"]
    evidence_ids: list[str] = Field(default_factory=list)


def parse_generated_response(raw: str, trusted_ids: set[str]) -> tuple[str, str | None, list[str], bool]:
    """Parse provider output and retain only citations from the trusted evidence set.

    The fourth return value identifies malformed structured JSON. Plain legacy text
    remains supported for existing providers, but JSON-shaped malformed output is
    treated as unsafe and receives no citations.
    """
    text = (raw or "").strip()
    candidate = text
    if text.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    looks_structured = candidate.startswith("{")
    if looks_structured:
        try:
            parsed = GeneratedCopilotResponse.model_validate(json.loads(candidate))
        except (json.JSONDecodeError, ValidationError, TypeError):
            return text, None, [], True
        valid_ids = [evidence_id for evidence_id in parsed.evidence_ids if evidence_id in trusted_ids]
        support = parsed.support
        if parsed.evidence_ids and not valid_ids:
            support = "insufficient_evidence"
        elif valid_ids and support == "insufficient_evidence":
            support = "partially_supported"
        return parsed.answer, support, valid_ids, False
    return text, None, [], False
