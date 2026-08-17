"""dmo —— 糖尿病本体 × 患者事实库的融合查询层。

分层（详见 docs/PATIENT-GRAPH-FUSION-PLAN.md 与 plan 文件）：

    hospital_zd.patient_analysis  【只读 · 一行不改】
        │ etl.py
    onto_db.diabetes.stg_/sim_/map_/core_/pred_
        │ rdf/sync.py（内容哈希 → GSP PUT）
    GraphDB dmo 仓（每患者一命名图）
        │ query/hybrid.py
    CLI / FastAPI

⚠️ 技术验证用途，不是医疗器械，不构成医疗建议。
"""

__version__ = "0.1.0"
