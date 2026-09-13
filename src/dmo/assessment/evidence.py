"""Local, read-only knowledge snapshot. Never trusts unverified extracted triples.

Quotes must match their owning source. A verified quote is not a claim that the
document is current clinical guidance; publication/applicability remain explicit.
"""

import hashlib
import re
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Namespace

from ..rdf.canonical import collapse, passage_hash
from .snapshot import digest

DMO = Namespace("https://example.org/dmo#")
ROOT = Path(__file__).resolve().parents[3]
UNIT_ALIASES = {
    "%": "percent",
    "mg/dL": "mg-per-dL",
    "mg/g": "mg-per-g",
    "mL/min": "mL-per-min",
    "mmol/L": "mmol-per-L",
}


class KnowledgeStore:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.graph = Graph()
        self.evidence: dict[str, dict] = {}
        self.documents: dict[str, str] = {}
        self.issues: list[str] = []
        self.files: dict[str, str] = {}
        for name in ("dmo-threshold-seed.ttl", "dmo-axioms.ttl"):
            path = root / "ontology/src" / name
            if not path.exists():
                self.issues.append(f"MISSING_KNOWLEDGE:{name}")
                continue
            raw = path.read_bytes()
            self.files[name] = hashlib.sha256(raw).hexdigest()
            self.graph.parse(data=raw, format="turtle")
        for source in sorted(set(self.graph.subjects(DMO.hasPassage, None)), key=str):
            sid = str(source).rsplit("/", 1)[-1]
            self.document(sid)
        self.document("fda-diabetes-drug-classes")

    @property
    def version(self):
        return digest(self.files)

    def document(self, source_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", source_id):
            return ""
        if source_id not in self.documents:
            path = self.root / "ontology/knowledges" / (source_id + ".txt")
            if not path.exists():
                self.issues.append(f"MISSING_SOURCE:{source_id}")
                self.documents[source_id] = ""
            else:
                raw = path.read_bytes()
                self.documents[source_id] = raw.decode("utf-8")
                self.files[source_id + ".txt"] = hashlib.sha256(raw).hexdigest()
        return self.documents[source_id]

    def quote(self, source_id: str, quote: str, *, locator: str = "") -> str | None:
        document = self.document(source_id)
        normalized = collapse(quote)
        if not normalized or normalized not in collapse(document):
            return None
        key = "K-" + digest([source_id, normalized])[:20]
        self.evidence[key] = {
            "evidence_id": key,
            "kind": "knowledge",
            "source_id": source_id,
            "source_file": f"ontology/knowledges/{source_id}.txt",
            "exact_quote": quote,
            "content_hash": passage_hash(quote),
            "document_hash": self.files[source_id + ".txt"],
            "locator": locator,
            "verification": "quote_matches_local_source",
            "currency": "not_verified",
            "population_scope": "以原始来源的适用人群为准，尚未确认适用于该患者",
        }
        return key

    def passage(self, iri) -> str | None:
        quote = str(self.graph.value(iri, DMO.quote) or "")
        expected = str(self.graph.value(iri, DMO.contentHash) or "")
        if expected != passage_hash(quote):
            return None
        for source in self.graph.subjects(DMO.hasPassage, iri):
            key = self.quote(
                str(source).rsplit("/", 1)[-1],
                quote,
                locator=str(self.graph.value(iri, DMO.locator) or iri),
            )
            if key:
                self.evidence[key]["passage_iri"] = str(iri)
                return key
        return None

    def medication(self, code: str):
        # Exact catalog code only; no fuzzy matching or invented drug selection.
        for med in self.graph.subjects(RDF.type, DMO.Medication):
            if str(self.graph.value(med, DMO.medicationCode)).casefold() == code.casefold():
                return med
        return None

    def drug_section(self, code: str) -> tuple[str, str] | None:
        source = "fda-diabetes-drug-classes"
        text = self.document(source)
        match = re.search(r"\t" + re.escape(code) + r"(?:\s|$)", text, re.IGNORECASE)
        if match is None:
            return None
        start = text.rfind("How do they work?", 0, match.start())
        if start < 0:
            return None
        end = text.find("Check the FDA website", match.end())
        if end < 0:
            return None
        quote = text[start:end].strip()
        key = self.quote(source, quote, locator=f"chars:{start}:{end}; medicine:{code}")
        return (key, quote) if key else None

    def thresholds(self, metric: str, unit: str, context: str):
        g = self.graph
        for test in sorted(g.subjects(DMO.labTestCode, None), key=str):
            if str(g.value(test, DMO.labTestCode)) != metric:
                continue
            for threshold in sorted(g.objects(test, DMO.hasThreshold), key=str):
                if str(g.value(threshold, DMO.boundUnit)) != UNIT_ALIASES.get(unit, unit):
                    continue
                population = str(g.value(threshold, DMO.populationContext))
                if population not in {"Any", context}:
                    continue
                refs = [self.passage(p) for p in g.objects(threshold, DMO.thresholdCitesPassage)]
                refs = [p for p in refs if p]
                if not refs:
                    continue
                yield {
                    "id": str(g.value(threshold, DMO.thresholdId)),
                    "iri": str(threshold),
                    "classification": str(g.value(threshold, DMO.classification)),
                    "lower": g.value(threshold, DMO.lowerBound),
                    "upper": g.value(threshold, DMO.upperBound),
                    "lower_operator": str(g.value(threshold, DMO.lowerOperator)),
                    "upper_operator": str(g.value(threshold, DMO.upperOperator)),
                    "population": population,
                    "evidence_ids": refs,
                }

    def condition_matches(self, code: str, target) -> bool:
        # Follow only asserted ontology subclass links, not inferred diagnoses.
        node = Namespace("https://example.org/dmo/id/")[code]
        return target == node or target in set(self.graph.transitive_objects(node, RDFS.subClassOf))
