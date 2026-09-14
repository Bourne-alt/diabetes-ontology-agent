import { Warning } from './Icons.jsx';
import { asText } from '../lib/text.js';
import Section from './Section.jsx';

export default function Gaps({ gaps }) {
  if (gaps.length === 0) return null;
  return (
    <Section
      className="gaps"
      title={<>
        <Warning />
        <h2>数据缺口与下一步 · 尚未排除</h2>
      </>}
      right={<span className="chip chip--terra">{gaps.length} 项</span>}
    >
      <div>
        {gaps.map((g, i) => (
          <div className="gaps__row" key={`${g.field}:${i}`}>
            <span className="gaps__k">{asText(g.field)}</span>
            <span className="gaps__v">{asText(g.text)}</span>
          </div>
        ))}
      </div>
      <div className="gaps__foot">
        上述条目不代表患者不存在相应情况，只表示本轮工具返回的证据不足以判定。
      </div>
    </Section>
  );
}
