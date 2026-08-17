"""IRI 的确定性铸造。

患者 IRI 与命名图名必须**只由 patientid 决定**：同一个 P90002，今天铸出来和
下个月铸出来必须是同一个 IRI，否则每次同步都会在图里留下一个新患者，
而旧的那个不会消失。用 uuid5（确定性）而不是 uuid4（随机）就是这个原因。

命名空间前缀与 `ontology/src/*.ttl`、`source_registry.py:89` 保持一套 `dmo/id/`。
对不上就是两座孤岛：SPARQL 不报错，只是永远查不到。
"""

from __future__ import annotations

import uuid

BASE = "https://example.org/dmo/id/"
VOCAB = "https://example.org/dmo#"

PATIENT_NS = BASE + "patient/"
ENCOUNTER_NS = BASE + "encounter/"
LABRESULT_NS = BASE + "labResult/"
OBSERVATION_NS = BASE + "observation/"
DIAGNOSIS_NS = BASE + "diagnosis/"
MEDUSE_NS = BASE + "medicationUse/"

# uuid5 的命名空间种子。**改了它，所有患者的 IRI 和命名图全变** ——
# 等于把图里已有的患者数据全部变成孤儿。当成常量对待。
_DMO_UUID_NS = uuid.uuid5(uuid.NAMESPACE_URL, PATIENT_NS)


def patient_uuid(patientid: str) -> uuid.UUID:
    return uuid.uuid5(_DMO_UUID_NS, patientid)


def patient_iri(patientid: str) -> str:
    return f"{PATIENT_NS}{patient_uuid(patientid)}"


def patient_graph(patientid: str) -> str:
    """每患者一命名图。`?pg` 本身就是 provenance —— 查询里靠图名就知道这条事实属于谁。"""
    return f"urn:dmo:patient:{patient_uuid(patientid)}"


def _slug(raw: str) -> str:
    """把业务 ID 变成 IRI 局部名。Turtle 的 prefixed name 不接受 '|' '/' 等字符。"""
    return "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in raw)


def encounter_iri(eid: str) -> str:
    return f"{ENCOUNTER_NS}{_slug(eid)}"


def lab_result_iri(lid: str) -> str:
    return f"{LABRESULT_NS}{_slug(lid)}"


def observation_iri(oid: str) -> str:
    return f"{OBSERVATION_NS}{_slug(oid)}"


def diagnosis_iri(did: str) -> str:
    return f"{DIAGNOSIS_NS}{_slug(did)}"


def medication_use_iri(mid: str) -> str:
    return f"{MEDUSE_NS}{_slug(mid)}"
