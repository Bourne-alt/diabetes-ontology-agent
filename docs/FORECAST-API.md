# 初始化模型治疗模拟接口

新增 `POST /patients/{pid}/forecasts`，不访问 PostgreSQL/GraphDB、不写患者事实、不调用原 `/simulate`。请求直接携带 LIS/PACS 等标准化事件快照，因此不需要配置外部模型或 API key。

```bash
curl -X POST http://localhost:8100/patients/P1/forecasts \
  -H 'Content-Type: application/json' \
  --data-binary @docs/forecast-example.json
```

可运行请求见 [forecast-example.json](forecast-example.json)。启动方式沿用项目 `dmo serve`；安装 `.[serve]` 提供 FastAPI/Pydantic。`model` 目前只有 `untrained_demo`，`seed` 默认 42，同输入同种子可复现。

当前功能：

- 从 V2 RDF 生成全部 25 个 frozen dataclass（`dmo.domain.generated`）；字段保留原 RDF IRI/range，关系保存实体 IRI，基数映射为单值/元组。运行 `python scripts/generate_domain.py` 重新生成。
- 快照事件必须包含患者、来源、记录标识、修订版、事件/报告可见/入库时间。支持 `lis`、`pacs`、`emr`、`medication`；仅已可见且已入库的最终版本可用，撤回不会回退旧值，迟到更正不污染旧快照。
- action 接受明确药品编码及开始时间，目前只支持 `start`。不自动选药；未给药品返回 `needs_clarification`。计划起始时间前的预测点没有 action 响应。
- 当前目标为 FPG、mmol/L；默认输出 7/14/28 天，允许 1–90 天。基线默认最长 7 天，缺失/过期/不匹配返回 `insufficient_data`。
- 返回模拟值、相对基线变化和下降量（负数代表上升），以及输入来源、排除原因、模型公式/参数和版本哈希。

模型为可替换的 `InitializedResponseModel`，随机初始化一个响应系数，以基线值和治疗后经过时间计算平滑响应。它是机器学习的参数化演示模型，不是通用医学模型，也不是训练完成的机器学习预测器。不同药品不会产生经过学习的差异；种子可导致上升或下降，因此不能用于比较药品效果。`trained=false`、`clinically_validated=false` 始终返回；无校准区间，无因果疗效估计。

PACS/EMR/用药事件目前只保存语义投影与出处，不参与模型数值计算。首期无 NLP 报告抽取、剂量建模、历史数据库持久化、临床禁忌验证或自动读取院内快照。调用方将已有快照按契约传入，事件历史由调用方保管。时序输入校验和初始化模拟可运行，后续可替换独立 model 模块接入训练产物。

HTTP 422 表示结构、时间或患者身份不合法；合法但无法模拟使用业务状态和解释。原 `/simulate` 的模型、规则、返回结构和调用路径均保持原样。
