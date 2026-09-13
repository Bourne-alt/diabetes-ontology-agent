import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const presentation = await PresentationFile.importPptx(await FileBlob.load(
  "/Users/fabivs/myfile/code/diabetes-ontology-agent/output-claude/project-presentation-with-architecture.pptx",
));
const snapshot = await presentation.inspect({
  kind: "slide,textbox,shape,image,table,chart,layout",
  include: "id,slide,name,text,textPreview,bbox,isPlaceholder,placeholders",
  maxChars: 240000,
});
await fs.writeFile(
  "/Users/fabivs/myfile/code/diabetes-ontology-agent/.codex-tmp/two-diagrams/template-inspect/template-inspect.ndjson",
  snapshot.ndjson,
);
