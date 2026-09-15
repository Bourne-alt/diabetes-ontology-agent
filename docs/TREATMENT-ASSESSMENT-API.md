# 治疗措施综合评估接口

`POST /patients/{pid}/treatment-assessments` 按患者编号查询 PostgreSQL 规范镜像，返回多维度状态、治疗相关证据、信息缺口和完整 Markdown 报告。接口使用本地规则及模板，不依赖 GraphDB 或外部模型。

## 调用与报告样例

```bash
curl -X POST http://localhost:8100/patients/P90002/treatment-assessments
```

接口只接收路径参数 `pid`。服务端从 `core_patient`、`core_lab_result`、
`core_observation`、`core_diagnosis` 和 `core_medication_use` 组装患者镜像，调用方不再提交快照。

原有离线脚本继续支持显式快照，可生成合成示例的 JSON 和 Markdown 文件：

```bash
python scripts/run_treatment_assessment.py \
  --request docs/treatment-assessment-example.json --patient SYNTHETIC \
  --composer template --out outputs/treatment-assessments
```

离线脚本可用 `--composer llm` 使用所配置的大模型。HTTP 接口只需 `pid`，不接受这些离线配置。接口返回 `rendered_markdown`，可直接保存为 `.md`；`claims` 和 `evidence` 是其结构化来源。

## 内部镜像语义

| 字段 | 含义 |
| --- | --- |
| mode | 当前固定为 prospective，评估镜像中的当前措施 |
| baseline_snapshot | 服务端按 `pid` 从规范患者表组装 |
| interventions | 从 Active 且未过期、未在未来开始的用药组装继续措施的条件评估；OnHold 不视为继续用药；无当前措施时返回明确资料缺口 |
| assessment_domains | 糖代谢、肾脏、心血管、肝脏、安全性、生活方式；安全性始终保留 |
| knowledge_mode | current，使用本地当前知识 |
| composer | template；agent 使用此报告组织回答 |
| extract_pacs / include_demo_appendix | 均为 false |

镜像没有 PACS、历史修订、发布和实际给药信息，缺口记录在 `source_coverage`。
无时区的库内时间按 `DMO_PATIENT_TIMEZONE` 解释（默认 `Asia/Taipei`）。缺少发生时间的记录
以镜像读取时间占位并标记 `event_time_known=false`，不参与时序判断。
下面的显式事件、随访及模型配置仅用于离线脚本/内部评估服务。

事件来源支持 `lis/pacs/emr/medication`。`event_time/available_at/ingested_at` 必须带时区。按截点选当时已知的最高修订版，再处理撤回、初步报告和未来事件，不能先取数据库全局最新版。

`context` 是测量语境，如 fasting/routine；`population_context` 独立表达 Pregnant/NonPregnant/unknown。数值只有 `value_trust=verified` 才参与阈值判断或随访数值比较。调用方应依据真实来源填写，不能为得到结论而将未知改为已核验。

诊断必须包含明确 `concept_code`、`verification=confirmed`、`assertion=present`、`clinical_status=active` 才能触发对应已覆盖的条件规则。否定、疑似、已缓解、冲突状态不会升级确诊。影像抽取即使原文匹配，也保持 `interpretation_unverified`，不作为已确认疾病输入安全规则。

随访比较要求同指标、单位、测量语境，且测量确实发生在基线后。旧报告更正不会被算成治疗响应；两次读数的差值由 Decimal 计算，结果明确不具因果归因。医嘱或自述不是实际给药证据；实际给药需对应 `medication` 事件、匹配 action_id/code 和实施时间。

## 模型配置

新服务只读取根目录下的 `.env.assessment`，文件使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL_TEXT` 三个键。它已被 Git 和 Docker 忽略，不改变原有 `.env` 或语义抽取模型配置。

部署可通过专用环境变量覆盖：`DMO_ASSESSMENT_API_KEY`、`DMO_ASSESSMENT_BASE_URL`、`DMO_ASSESSMENT_MODEL`。不要把真实密钥放进代码或请求体。

当前指定服务为 SiliconFlow，模型名为 `glm-5.2`。短名会在 `/models` 中寻找唯一同名后缀并记录 `requested_model/resolved_model`；未找到或有歧义时明确降级，不自动换用其他模型。完整平台模型 ID 可直接配置。

采用 [SiliconFlow Chat Completions](https://docs.siliconflow.cn/docs/api/chat-completions-post) 的 JSON 输出。默认最多两次综合生成，每次经确定性校验后进行一次模型辅助语义核对；单次请求超时 45 秒。语义核对不能代替临床验证。可选 PACS 抽取会额外调用一次模型。

连通性检查（不发送患者信息）：

```bash
python scripts/check_assessment_model.py
```

开发环境首次连通性检查返回 HTTP 402；当前密钥/账户/模型访问状态需要服务方确认。`MODEL_HTTP_402` 会作为结构化降级原因保留，报告其他部分仍能返回。没有用其他模型代替该模型。

## 证据与输出

每个 claim 有类型、时间范围、依据 ID、规则 ID、缺失前提。规则数值来自本体 seed，知识引文必须在所属本地原文中找到且哈希匹配。药品注意事项必须位于该药品对应的来源段落，不能拿另一药物的真实引文来支持结论。

大模型只综合已有 claims，不能新增无依据的医学事实。校验包括 JSON schema、引用存在性、数值一致性、禁止 demo 充当证据、语义支持检查。完整确定性结论始终保留，摘要不能删掉关键风险。

默认不向大模型发送原始 EMR/PACS 自由文本；结构化数值、措施和已有结论会发送到配置服务。`extract_pacs=true` 是文本发送开关：调用方应只提供评估所需、已去标识的报告正文；基础电话号码/邮箱过滤不等于能自动识别所有个人身份信息。

`status=partial` 表示仍有明确的信息或知识缺口，不代表接口失败。`domains[].status=assessed` 只表示已完成该维度已覆盖规则的评估，不表示整套临床检查完备。`generation_metadata` 记录实际生成器、模型、校验状态、降级原因和模型结构化输出。

设置 `DMO_ASSESSMENT_REPORT_DIR` 可为 API 开启私有 JSON/Markdown 归档；默认关闭。命令行始终按 `--out` 归档。文件权限为 0600，报告 ID 基于输入证据和产物内容，归档用于重现已生成报告，不要求大模型再次生成完全相同文字。

## 现有覆盖范围

- 定量阈值复用 `ontology/src/dmo-threshold-seed.ttl`，单位仅做同义标识映射，不隐式换算浓度。因此 mmol/L 的 FPG 在只有 mg/dL 阈值时显示无适用阈值，保留原始数值。
- 治疗类别和注意事项复用 `dmo-axioms.ttl`；原文在 `ontology/knowledges` 中逐段核验。未覆盖的药品、生活方式/器械、停药影响、联合作用和相互作用明确报告缺口。
- 已支持 start/continue 的条件性资料关联；change 可评估新措施但不模拟撤除旧措施影响；stop 不将启用结论反转成停药效果。
- 原始来源缺失、时效未核验或人群不适用时不能给出完整临床结论。Docker 默认不打包 `ontology/knowledges`，部署需把所需原始语料只读挂载至 `/app/ontology/knowledges`；缺失时服务仍返回资料不足报告。
- 未新增训练模型，未把独立指标预测拼成健康分数，未修改现有 `/simulate` 和 forecast 算法。

对应实现位于 `src/dmo/assessment/`；请求验证、时序状态、证据、规则、模型、校验、渲染、归档分别独立。
