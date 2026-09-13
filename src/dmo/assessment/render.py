import html
import re

from .contracts import LABELS


def plain(value) -> str:
    text = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#!|>])", r"\\\1", text)


def render(report: dict) -> str:
    lines = [
        "# 治疗措施综合评估报告",
        "",
        f"评估模式：{report['mode']}；状态：{report['status']}。",
        f"基线时点：{report['snapshot_refs']['baseline']['clinical_as_of']}。",
        "",
        "以下区分患者记录、规则结论和一般知识提示；不把观察到的变化归因于治疗。",
        "本地资料已核验原文位置，但未验证其为最新适用临床指南。",
        "",
    ]
    if report["generation_metadata"]["items"]:
        lines.extend(["## 综合说明", ""])
        for item in report["generation_metadata"]["items"]:
            lines.extend(
                [
                    plain(item["text"])
                    + " "
                    + " ".join(f"[{ref}](#{ref.lower()})" for ref in item["claim_ids"]),
                    "",
                ]
            )
    for domain in report["domains"]:
        lines.extend([f"## {LABELS[domain['domain']]}（{domain['status']}）", ""])
        for claim in report["claims"]:
            if claim["domain"] != domain["domain"]:
                continue
            lines.extend(
                [
                    f"### {claim['claim_id']}",
                    "",
                    f"类型：{claim['kind']}；时段：{claim['time_scope']}。",
                    plain(claim["statement"]),
                    "",
                ]
            )
            if claim["evidence_ids"]:
                lines.extend(
                    [
                        "依据："
                        + "、".join(f"[{ref}](#{ref.lower()})" for ref in claim["evidence_ids"]),
                        "",
                    ]
                )
    lines.extend(["## 证据索引", ""])
    for item in report["evidence"]:
        lines.extend([f"### {item['evidence_id']}", ""])
        if item["kind"] == "knowledge":
            lines.extend(
                [
                    plain(item["source_file"]) + "；" + plain(item["locator"]),
                    plain(item["exact_quote"]),
                    f"原文哈希：{item['content_hash']}；时效性：待复核。",
                    "",
                ]
            )
        elif item["kind"] == "patient_fact":
            lines.extend(
                [
                    f"来源：{item['source']}；记录：{plain(item['event_id'])}。",
                    (
                        f"发生：{item['event_time']}；可见：{item['available_at']}；"
                        f"入库：{item['ingested_at']}。"
                    ),
                    "",
                ]
            )
        else:
            lines.extend(["治疗措施输入：" + plain(item["code"] or "未明确"), ""])
    if report["demo_appendix"]:
        lines.extend(
            ["## 初始化数值演示附件", "", "仅验证计算流程，不作为报告正文或临床结论的依据。", ""]
        )
        for result in report["demo_appendix"]:
            lines.append(plain(result))
    return "\n".join(lines).rstrip() + "\n"
