// Only explicitly named technical sections are collapsed. Safety and conclusions stay visible.
export function splitAnswer(text) {
  const blocks = text.split(/(?=^#{1,3}\s+)/m);
  const main = [], technical = [];
  for (const block of blocks) {
    if (/^#{1,3}\s+(?:技术与证据详情|技术详情|原始证据|规则编号与出处|完整出处)\s*$/m.test(block.split('\n')[0])) technical.push(block);
    else main.push(block);
  }
  return { main: main.join(''), technical: technical.join('\n') };
}
