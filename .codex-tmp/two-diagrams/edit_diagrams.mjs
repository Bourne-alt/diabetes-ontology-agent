import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const starterPath = "/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/two-diagrams/template-starter.pptx";
const finalPath = "/Users/fabivs/myfile/code/diabetes-ontology-agent/output-claude/project-presentation-with-agent-and-ontology-diagrams.pptx";
const renderDir = "/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/two-diagrams/final-render";
const layoutDir = "/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/two-diagrams/final-layout";

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
}

async function textRecords(presentation) {
  const snapshot = await presentation.inspect({
    kind: "slide,textbox,shape,notes,layout",
    include: "id,slide,name,text,textPreview,bbox,isPlaceholder,placeholders",
    maxChars: 160000,
  });
  return snapshot.ndjson.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

async function replaceExact(presentation, slideNumber, oldText, newText) {
  const records = await textRecords(presentation);
  const matches = records.filter((record) =>
    record.slide === slideNumber &&
    (record.text === oldText || record.textPreview === oldText) &&
    typeof record.id === "string" && record.id.startsWith("sh/")
  );
  if (matches.length !== 1) throw new Error(`Expected one match on slide ${slideNumber} for ${JSON.stringify(oldText)}, found ${matches.length}`);
  const target = presentation.resolve(matches[0].id);
  if (oldText.includes("\n")) target.text = newText;
  else target.text.replace(oldText, newText);
}

async function main() {
  await fs.mkdir(renderDir, { recursive: true });
  await fs.mkdir(layoutDir, { recursive: true });
  const presentation = await PresentationFile.importPptx(await FileBlob.load(starterPath));

  const ontology = [
    ["一 · 知识库是怎么建出来的", "本体提取工作流 · 从原文到可执行知识"],
    ["知识库不是手写出来的，是“造”出来的", "候选可以自动抽取，知识入库必须经过门禁"],
    ["从一份概念框架和几份指南原文出发，经过加工和三道体检，才变成机器能直接查的知识网。每一步都留痕，改了什么、谁改的，都查得到。", "资料登记、候选抽取、人工复核、结构校验和装载验收彼此分离；模型不直接写入高风险规则。"],
    ["原料", "输入"], ["加工", "语义抽取"], ["把关", "质量门禁"], ["成品", "发布"],
    ["概念框架", "领域模型 JSON"], ["有哪些概念、谁连谁", "概念 · 关系 · Schema"],
    ["指南原文", "指南与资料"], ["TXT / PDF 文件", "原文 · 版本 · 来源哈希"],
    ["自动生成骨架", "登记来源"], ["不用人工同步多份文件", "记录文件指纹与版本"],
    ["给每份文件按内容算指纹", "按 Schema 抽取"], ["改一个字，指纹就变", "概念 · 关系 · 引文候选"],
    ["让 AI 照原文摘句", "人工审高危项"], ["只摘，不下判断", "阈值 · 禁忌 · 规则边界"],
    ["结构体检", "SHACL 结构校验"], ["格式和安全约束", "字段与关系必须完整"],
    ["原文逐字核对", "引文逐字核对"], ["引用是不是真的那句话", "quote + sha256 回到原文"],
    ["装载验收", "装载后验收"], ["进库后再查一遍", "查询 · 规则 · 命名图"],
    ["可查询的知识网", "OWL / RDF 本体"], ["概念 · 关系 · 出处", "概念 · 关系 · 来源"],
    ["可执行的判定规则", "SPARQL / SHACL"], ["机器直接跑", "规则 · 约束 · 可验证"],
    ["×   诊断切点 · 控制目标", "LLM 只产候选"], ["由人工写定，AI 不参与", "高风险知识必须人工确认"],
    ["现状如实说：原文逐字核对 31 / 31 全过；结构体检目前还有 2 条新问题没修 —— 这不是一条全绿的流水线。", "进入 GraphDB 前同时通过四道检查：结构 · 来源 · 规则 · 装载"],
  ];
  for (const [oldText, newText] of ontology) await replaceExact(presentation, 4, oldText, newText);

  const agent = [
    ["四 · 智能体是怎么“想”的", "智能体架构 · 计划、调用、观察、收敛"],
    ["想一步，查一步，看一眼结果，再想下一步", "模型负责调度，确定性工具负责查证"],
    ["ReAct = Reason（想）+ Act（做）。它不是把问题一次性丢给模型，而是每做一个动作前必须先说理由，做完必须看结果，不够就再来一轮。", "Agent 使用 ReAct 循环选择 Skill；每一步都读取结构化结果，证据不足就停止，不绕过 API 自由编造。"],
    ["1  想", "1  计划"], ["这个问题该问哪一层？\n是问“是什么”，\n还是问“凭什么”？", "识别问题类型，\n列出结论所需的\n事实、规则与来源。"],
    ["2  做", "2  路由"], ["只调这一层\n够用的那几个工具，\n不为“更完整”多调。", "选择最窄的\nSkill / Tool，\n通过 API 执行。"],
    ["3  看", "3  观察"], ["读返回的数据，\n缺什么就记下什么，\n不脑补。", "读取结构化返回，\n记录证据、状态\n与缺口。"],
    ["4  够了吗", "4  收敛"], ["不够 → 回到第一步；\n够了才动笔写答案。", "证据足够才回答；\n否则返回缺口\n与停止原因。"],
    ["这个“助手”本身在仓库之外（例如 Claude）。\n仓库提供的是它的行动手册和可调用的工具，不含内置对话模型。", "仓库提供 Skill、Tool 与 API；外部模型可以替换，\n但确定性的证据执行链保持不变。"],
    ["五条护栏 —— 它和普通聊天机器人的区别", "五层运行时护栏 —— 模型不能绕过"],
    ["先体检", "健康检查"], ["两个仓库通不通？不通就停，不用常识补", "PostgreSQL / GraphDB 不通就停"],
    ["分层走", "范围约束"], ["问“是什么”去表库，问“凭什么”去图库", "只用白名单接口与受控查询"],
    ["由窄到宽", "术语约束"], ["先用现成接口，自由查询是最后手段", "未映射不猜名，不做相似替换"],
    ["不猜名字", "证据约束"], ["术语查不到就说查不到，不换个说法再试一遍", "结论必须带规则、来源与原始事实"],
    ["有预算", "预算约束"], ["一个目标最多试 4 次，用完就说“没推出来”", "限制轮次；失败返回原因与缺口"],
    ["护栏的作用：让它答不出来的时候，老实说答不出来。", "Agent 输出 = 结论状态 + 证据链 + 来源 + 缺口"],
  ];
  for (const [oldText, newText] of agent) await replaceExact(presentation, 7, oldText, newText);

  const pages = [
    [2, "01 / 10", "01 / 11"], [3, "02 / 10", "02 / 11"], [4, "03 / 10", "03 / 11"],
    [5, "04 / 10", "04 / 11"], [6, "05 / 10", "05 / 11"], [7, "06 / 10", "06 / 11"],
    [8, "06 / 10", "07 / 11"], [9, "07 / 10", "08 / 11"], [10, "08 / 10", "09 / 11"],
    [11, "09 / 10", "10 / 11"], [12, "10 / 10", "11 / 11"],
  ];
  for (const [slide, oldText, newText] of pages) await replaceExact(presentation, slide, oldText, newText);

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(`${renderDir}/${stem}.png`, await presentation.export({ slide, format: "png", scale: 1 }));
    await fs.writeFile(`${layoutDir}/${stem}.layout.json`, await (await slide.export({ format: "layout" })).text());
  }
  await writeBlob("/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/two-diagrams/final-montage.webp", await presentation.export({ format: "webp", montage: true, scale: 1 }));
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(finalPath);
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
