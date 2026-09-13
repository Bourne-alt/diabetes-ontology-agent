import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const starterPath = "/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/architecture-slide/template-starter.pptx";
const finalPath = "/Users/fabivs/myfile/code/diabetes-ontology-agent/output-claude/project-presentation-with-architecture.pptx";
const renderDir = "/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/architecture-slide/final-render";
const layoutDir = "/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/architecture-slide/final-layout";

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
}

async function textRecords(presentation) {
  const snapshot = await presentation.inspect({
    kind: "slide,textbox,shape,notes,layout",
    include: "id,slide,name,text,textPreview,bbox,isPlaceholder,placeholders",
    maxChars: 120000,
  });
  return snapshot.ndjson
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

async function replaceExact(presentation, slideNumber, oldText, newText) {
  const records = await textRecords(presentation);
  const matches = records.filter((record) =>
    record.slide === slideNumber &&
    (record.text === oldText || record.textPreview === oldText) &&
    typeof record.id === "string" && record.id.startsWith("sh/")
  );
  if (matches.length !== 1) {
    throw new Error(`Expected one match on slide ${slideNumber} for ${JSON.stringify(oldText)}, found ${matches.length}`);
  }
  const target = presentation.resolve(matches[0].id);
  target.text.replace(oldText, newText);
}

async function main() {
  await fs.mkdir(renderDir, { recursive: true });
  await fs.mkdir(layoutDir, { recursive: true });
  const presentation = await PresentationFile.importPptx(await FileBlob.load(starterPath));

  const architectureReplacements = [
    ["一 · 知识库是怎么建出来的", "总体架构 · 一次回答如何被验证"],
    ["知识库不是手写出来的，是“造”出来的", "四层协作，让每个结论都能回到事实与来源"],
    ["从一份概念框架和几份指南原文出发，经过加工和三道体检，才变成机器能直接查的知识网。每一步都留痕，改了什么、谁改的，都查得到。", "问题进入系统后，智能体只负责编排；事实核验、规则推理与证据回溯，都由确定性服务完成。"],
    ["原料", "交互与编排"],
    ["加工", "能力调用"],
    ["把关", "证据融合"],
    ["成品", "双库底座"],
    ["概念框架", "用户问题"],
    ["有哪些概念、谁连谁", "自然语言提出任务"],
    ["指南原文", "Agent 编排"],
    ["TXT / PDF 文件", "选择 Skill，不直接判断"],
    ["自动生成骨架", "Skills / Tools"],
    ["不用人工同步多份文件", "查询 · 推演 · 溯源 · 裁决"],
    ["给每份文件按内容算指纹", "FastAPI / CLI"],
    ["改一个字，指纹就变", "稳定接口，统一返回"],
    ["让 AI 照原文摘句", "安全边界"],
    ["只摘，不下判断", "不猜测；证据不足就停"],
    ["结构体检", "SQL 收敛患者集"],
    ["格式和安全约束", "先缩小事实范围"],
    ["原文逐字核对", "SPARQL 语义推理"],
    ["引用是不是真的那句话", "本体 + 规则给出结论"],
    ["装载验收", "证据回拼"],
    ["进库后再查一遍", "source_pk 回到原始记录"],
    ["可查询的知识网", "PostgreSQL"],
    ["概念 · 关系 · 出处", "患者事实 · 单位 · 时间"],
    ["可执行的判定规则", "GraphDB"],
    ["机器直接跑", "本体 · 规则 · 来源"],
    ["×   诊断切点 · 控制目标", "LLM 负责理解与编排"],
    ["由人工写定，AI 不参与", "临床结论不由模型自由生成"],
    ["现状如实说：原文逐字核对 31 / 31 全过；结构体检目前还有 2 条新问题没修 —— 这不是一条全绿的流水线。", "返回“证据收据”：结论状态 · 规则依据 · 来源 · 原始事实 · 证据缺口"],
  ];

  for (const [oldText, newText] of architectureReplacements) {
    await replaceExact(presentation, 3, oldText, newText);
  }

  const pageUpdates = [
    [2, "01 / 9", "01 / 10"],
    [3, "02 / 9", "02 / 10"],
    [4, "02 / 9", "03 / 10"],
    [5, "03 / 9", "04 / 10"],
    [6, "04 / 9", "05 / 10"],
    [7, "05 / 9", "06 / 10"],
    [8, "06 / 9", "07 / 10"],
    [9, "07 / 9", "08 / 10"],
    [10, "08 / 9", "09 / 10"],
    [11, "09 / 9", "10 / 10"],
  ];
  for (const [slideNumber, oldText, newText] of pageUpdates) {
    await replaceExact(presentation, slideNumber, oldText, newText);
  }

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(`${renderDir}/${stem}.png`, await presentation.export({ slide, format: "png", scale: 1 }));
    await fs.writeFile(`${layoutDir}/${stem}.layout.json`, await (await slide.export({ format: "layout" })).text());
  }
  await writeBlob(
    "/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/architecture-slide/final-montage.webp",
    await presentation.export({ format: "webp", montage: true, scale: 1 }),
  );
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(finalPath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

