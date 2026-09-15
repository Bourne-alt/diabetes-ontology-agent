import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Section from './Section.jsx';
import { splitAnswer } from '../lib/answerSections.js';

const plugins = [remarkGfm];
function Markdown({ text }) {
  return <ReactMarkdown remarkPlugins={plugins} skipHtml components={{
    a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    img: ({ alt }) => <span>{alt || '图片内容未加载'}</span>,
  }}>{text}</ReactMarkdown>;
}
export default function Answer({ draft, answer }) {
  const final = answer !== null;
  const text = final ? answer : draft;
  if (!text) return null;
  const parts = splitAnswer(text);
  return (
    <Section title={<><h2>给你的解答</h2><span className="answer-tag">{final ? '结合已查询的证据' : '正在整理'}</span></>}>
      {!final && <div className="draftnote">正在根据查询结果整理回答…</div>}
      <div className={'answer__body markdown' + (final ? '' : ' is-draft')} aria-live="polite">
        <Markdown text={parts.main} />
      </div>
      {parts.technical && <details className="technical-details"><summary>查看规则编号与原始证据</summary>
        <div className="markdown"><Markdown text={parts.technical} /></div>
      </details>}
    </Section>
  );
}
