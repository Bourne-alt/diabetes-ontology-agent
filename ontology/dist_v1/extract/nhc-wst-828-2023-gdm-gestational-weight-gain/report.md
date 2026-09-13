# 抽取质量报告 — nhc-wst-828-2023-gdm-gestational-weight-gain

- 源文件：`ontology/knowledges/pdfs/nhc-wst-828-2023-gdm-gestational-weight-gain.pdf`（sha256 `00f3244f099e…`）
- 目标图：`urn:dmo:extract:nhc-wst-828-2023-gdm-gestational-weight-gain`
- schema：`ontology/graph/diabetes-ontology-v2.json`，抽取目标 14 类
- 分块：1

## 质量指标

| 指标 | 值 | 含义 |
|---|---|---|
| quote 命中率 | **84.6%** | 通过逐字校验的比例，低于阈值说明模型在编 |
| schema 槽位覆盖 | 14.5% | 图里定义的字段有多少真被填上，过低说明图设计过度 |
| 关系悬空率 | 100.0% | 指向不存在实体的关系占比，过高说明抽取顺序或分块有问题 |
| 平均提及次数 | 2.2 | 每个实体被多少条记录支持 |

## 计数

| 项 | 数量 |
|---|---|
| 原始记录 | 13 |
| 通过校验 | 11 |
| 丢弃 | 2 |
| 消解后实体 | 5 |
| 关系边 | 0 |
| 悬空关系 | 9 |
| 合并冲突 | 12 |

## 丢弃原因

| 原因 | 次数 |
|---|---|
| `quote_not_found` | 2 |

## 各类型产出

| 实体类型 | 数量 |
|---|---|
| recommendation | 3 |
| contraindication | 2 |

## 合并冲突样例

- recommendation/gdm诊断后妊娠中期和妊娠晚期每周体重增长值: statement: '妊娠期糖尿病妇女在GDM诊断后妊娠中期和妊娠晚期的每周体重增长值推荐为0.46（0.37～0.56）kg/week，适用于低体重（BMI＜18.5 kg/m²）者。' vs '妊娠期糖尿病妇女在GDM诊断后妊娠中期和妊娠晚期的每周体重增长值推荐为0.37（0.26～0.48）kg/week，适用于正常体重（18.5 kg/m²≤BMI＜24.0 kg/m²）者。'
- recommendation/gdm诊断后妊娠中期和妊娠晚期每周体重增长值: populationScope: '低体重（BMI＜18.5 kg/m²）的妊娠期糖尿病妇女' vs '正常体重（18.5 kg/m²≤BMI＜24.0 kg/m²）的妊娠期糖尿病妇女'
- recommendation/gdm诊断后妊娠中期和妊娠晚期每周体重增长值: statement: '妊娠期糖尿病妇女在GDM诊断后妊娠中期和妊娠晚期的每周体重增长值推荐为0.46（0.37～0.56）kg/week，适用于低体重（BMI＜18.5 kg/m²）者。' vs '妊娠期糖尿病妇女在GDM诊断后妊娠中期和妊娠晚期的每周体重增长值推荐为0.26（0.19～0.32）kg/week，适用于超重（24.0 kg/m²≤BMI＜28.0 kg/m²）者。'
- recommendation/gdm诊断后妊娠中期和妊娠晚期每周体重增长值: populationScope: '低体重（BMI＜18.5 kg/m²）的妊娠期糖尿病妇女' vs '超重（24.0 kg/m²≤BMI＜28.0 kg/m²）的妊娠期糖尿病妇女'
- recommendation/gdm诊断后妊娠中期和妊娠晚期每周体重增长值: statement: '妊娠期糖尿病妇女在GDM诊断后妊娠中期和妊娠晚期的每周体重增长值推荐为0.46（0.37～0.56）kg/week，适用于低体重（BMI＜18.5 kg/m²）者。' vs '妊娠期糖尿病妇女在GDM诊断后妊娠中期和妊娠晚期的每周体重增长值推荐为0.18（0.12～0.23）kg/week，适用于肥胖（BMI≥28.0 kg/m²）者。'
- recommendation/gdm诊断后妊娠中期和妊娠晚期每周体重增长值: populationScope: '低体重（BMI＜18.5 kg/m²）的妊娠期糖尿病妇女' vs '肥胖（BMI≥28.0 kg/m²）的妊娠期糖尿病妇女'
- recommendation/gdm诊断前妊娠中期每周体重增长值: statement: '妊娠期糖尿病妇女在GDM诊断前妊娠中期的每周体重增长值推荐为0.46（0.37～0.56）kg/week，适用于低体重（BMI＜18.5 kg/m²）者。' vs '妊娠期糖尿病妇女在GDM诊断前妊娠中期的每周体重增长值推荐为0.37（0.26～0.48）kg/week，适用于正常体重（18.5 kg/m²≤BMI＜24.0 kg/m²）者。'
- recommendation/gdm诊断前妊娠中期每周体重增长值: populationScope: '低体重（BMI＜18.5 kg/m²）的妊娠期糖尿病妇女' vs '正常体重（18.5 kg/m²≤BMI＜24.0 kg/m²）的妊娠期糖尿病妇女'
- recommendation/gdm诊断前妊娠中期每周体重增长值: statement: '妊娠期糖尿病妇女在GDM诊断前妊娠中期的每周体重增长值推荐为0.46（0.37～0.56）kg/week，适用于低体重（BMI＜18.5 kg/m²）者。' vs '妊娠期糖尿病妇女在GDM诊断前妊娠中期的每周体重增长值推荐为0.30（0.22～0.37）kg/week，适用于超重（24.0 kg/m²≤BMI＜28.0 kg/m²）者。'
- recommendation/gdm诊断前妊娠中期每周体重增长值: populationScope: '低体重（BMI＜18.5 kg/m²）的妊娠期糖尿病妇女' vs '超重（24.0 kg/m²≤BMI＜28.0 kg/m²）的妊娠期糖尿病妇女'
- recommendation/gdm诊断前妊娠中期每周体重增长值: statement: '妊娠期糖尿病妇女在GDM诊断前妊娠中期的每周体重增长值推荐为0.46（0.37～0.56）kg/week，适用于低体重（BMI＜18.5 kg/m²）者。' vs '妊娠期糖尿病妇女在GDM诊断前妊娠中期的每周体重增长值推荐为0.22（0.15～0.30）kg/week，适用于肥胖（BMI≥28.0 kg/m²）者。'
- recommendation/gdm诊断前妊娠中期每周体重增长值: populationScope: '低体重（BMI＜18.5 kg/m²）的妊娠期糖尿病妇女' vs '肥胖（BMI≥28.0 kg/m²）的妊娠期糖尿病妇女'

## 悬空关系样例

- `gdm诊断后妊娠中期和妊娠晚期每周体重增长值` --definesTarget--> `GDM诊断后妊娠中期和妊娠晚期每周体重增长值`（未找到）
- `gdm诊断后妊娠中期和妊娠晚期每周体重增长值` --definesTarget--> `GDM诊断后妊娠中期和妊娠晚期每周体重增长值`（未找到）
- `gdm诊断后妊娠中期和妊娠晚期每周体重增长值` --definesTarget--> `GDM诊断后妊娠中期和妊娠晚期每周体重增长值`（未找到）
- `gdm诊断后妊娠中期和妊娠晚期每周体重增长值` --definesTarget--> `GDM诊断后妊娠中期和妊娠晚期每周体重增长值`（未找到）
- `gdm诊断前妊娠中期每周体重增长值` --definesTarget--> `GDM诊断前妊娠中期每周体重增长值`（未找到）
- `gdm诊断前妊娠中期每周体重增长值` --definesTarget--> `GDM诊断前妊娠中期每周体重增长值`（未找到）
- `gdm诊断前妊娠中期每周体重增长值` --definesTarget--> `GDM诊断前妊娠中期每周体重增长值`（未找到）
- `gdm诊断前妊娠中期每周体重增长值` --definesTarget--> `GDM诊断前妊娠中期每周体重增长值`（未找到）
- `妊娠早期体重增长值` --definesTarget--> `妊娠早期体重增长值`（未找到）
