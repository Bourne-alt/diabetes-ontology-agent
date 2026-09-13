import re

from .contracts import Narrative


class NarrativeError(ValueError):
    pass


def validate_narrative(narrative: Narrative, claims: list[dict]) -> None:
    index = {c["claim_id"]: c for c in claims}
    for item in narrative.items:
        if any(ref not in index for ref in item.claim_ids):
            raise NarrativeError("UNKNOWN_CLAIM_REFERENCE")
        support = [index[ref] for ref in item.claim_ids]
        if any(c["kind"] == "demo" for c in support):
            raise NarrativeError("DEMO_USED_AS_EVIDENCE")
        if re.search(r"https?://|<[^>]+>|!\[", item.text):
            raise NarrativeError("UNAPPROVED_LINK_OR_MARKUP")
        allowed = set(re.findall(r"\d+(?:\.\d+)?", " ".join(c["statement"] for c in support)))
        if set(re.findall(r"\d+(?:\.\d+)?", item.text)) - allowed:
            raise NarrativeError("UNSUPPORTED_NUMBER")
        if any(word in item.text for word in ("保证治愈", "绝对安全", "无任何风险", "一定会改善")):
            raise NarrativeError("UNSUPPORTED_CERTAINTY")


def validate_claim_references(claims: list[dict], evidence: dict[str, dict]):
    for claim in claims:
        refs = claim["evidence_ids"]
        if any(ref not in evidence for ref in refs):
            raise ValueError("INTERNAL_DANGLING_EVIDENCE")
        if claim["kind"] in {"rule_conclusion", "knowledge_expectation"} and not any(
            evidence[ref]["kind"] == "knowledge" for ref in refs
        ):
            raise ValueError("INTERNAL_MISSING_KNOWLEDGE_SUPPORT")
