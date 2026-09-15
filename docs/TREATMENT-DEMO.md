# 患者评估过程演示

## 页面操作

构建前端并启动 Agent 服务，打开页面右侧「评估演示」。选择患者后点击「运行患者评估」。接口只需要路径中的 pid，无请求体；直接演示不依赖 LLM。

```sh
cd frontend
npm install
npm run build
cd ..
.venv/bin/python -m uvicorn agent.api:app --host 127.0.0.1 --port 8201
```

访问 http://127.0.0.1:8201 。已有服务需要重启，浏览器刷新后加载新构建。

评估完成后可播放、暂停、逐步选择、拖动进度和调整速度。11 个步骤包含：读取患者镜像、组装时序事件与措施、筛选有效记录、加载知识、映射本体、检查结果判定、治疗条件规则、六维缺口、引用核验、报告组织、报告输出。每步展示真实输入或输出、记录数、证据和实际耗时。

这是**执行完成后的记录回放**，不是接口运行中的实时进度，也不展示 LLM 私有推理。Agent 调用 `assess_patient_treatment` 时会通过 `assessment_report` 事件把完整报告送到该页；模型上下文收到去重后的结论与证据。

## 八个合成场景

|患者|演示内容|观察点|
|---|---|---|
|P91001|A1C、FPG 与现有用药|血糖规则、独立数值演示|
|P91002|肾脏条件与药物注意事项|UACR、eGFR、已确认 CKD 与条件规则|
|P91003|两项用药和多维资料|联合措施证据缺口、肝脏与生活方式记录|
|P91004|同一时间两条冲突 A1C|暂停血糖阈值判断|
|P91005|未核验检验值|保留事实但不触发阈值结论|
|P91006|原始检验缺少单位|保留原文，不猜单位或制造数值结论|
|P91007|130 天前的检验|超出评估窗口，提示需要近期记录|
|P91008|暂停用药|不当作现行措施，显示缺口|

数据全部为合成数据，写入 `sim_*` 和 `core_*`，来源为 `demo-cohort`，场景前缀为 `TA-DEMO-`。不写原始医院数据库。脚本只替换这八个明确归属本模块的患者；发现 ID 被其他来源占用会拒绝并回滚。日期默认相对播种当天生成，长时间后演示可重新播种刷新时间窗口。

```sh
.venv/bin/python scripts/seed_treatment_demo.py --list
.venv/bin/python scripts/seed_treatment_demo.py
# 固定日期用于复现数据，不保证未来仍处于近期窗口：
.venv/bin/python scripts/seed_treatment_demo.py --reference-date 2026-09-15
```

## 独立数值预测演示

选择 P91001 并点击「运行机器学习模型预测演示」。显示可信 FPG 筛选、登记表单位换算、基线、随机种子、模型初始化、7/14/28 天计算明细及逐点曲线。其他缺少近期 FPG 的场景会显示输入不足。

现有模型**没有训练、没有临床验证**。它使用固定种子初始化系数和指数响应公式，不是患者特异疗效模型；演示动作是显式合成动作，不代表患者实际处方。该入口只允许这八个且来源核验通过的合成患者，评估接口不会自动运行它。

## API 与验证

```sh
curl http://127.0.0.1:8201/demo/treatment-scenarios
curl -X POST http://127.0.0.1:8201/patients/P91001/treatment-assessments
curl -X POST http://127.0.0.1:8201/patients/P91001/prediction-demo
.venv/bin/python scripts/verify_treatment_demo.py
.venv/bin/python -m pytest tests/test_assessment_demo.py tests/test_treatment_assessment.py tests/test_agent.py tests/test_forecast.py -q
```

报告新增 `execution_trace.steps`，每步含 `key/title/status/summary/duration_ms/elapsed_ms/details`。原有报告字段仍保留。`verify_treatment_demo.py` 需要已播种且可连接的 PostgreSQL，验证所有场景的规则与缺口、11 步记录、预测限制及 Agent 内容预算。依赖不可用时返回 503，页面显示失败而不会播放成功记录。
