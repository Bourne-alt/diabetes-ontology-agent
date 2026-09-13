import sharp from "sharp";

await sharp("/Users/fabivs/myfile/code/diabetes-ontology-agent/output-claude/基于ontology-tools的智能体知识工厂架构图.svg", {
  density: 144,
})
  .png({ compressionLevel: 9 })
  .toFile("/Users/fabivs/myfile/code/diabetes-ontology-agent/output-claude/基于ontology-tools的智能体知识工厂架构图.png");
