export default function Citations({ quotes }) {
  return <section className="citation-panel" aria-label="引用依据">
    <h3>引用依据 <small>{quotes.length} 条</small></h3>
    {!quotes.length && <p>本次结果未提供可展示的文档引用。</p>}
    {quotes.map((q,i)=><article className="citation-card" key={`${q.document}:${q.sha256}:${i}`}>
      <header><span>{i+1}</span><strong>{q.document ? q.document.split(/[\\/]/).at(-1) : '文档名未提供'}</strong></header>
      {q.supports && <p className="citation-support">对应内容：{q.supports}</p>}
      <div className="citation-label">引用原文</div>
      <blockquote>{q.quote}</blockquote>
      {q.interpretation && <p className="citation-support">规则说明：{q.interpretation}</p>}
      {(q.locator||q.sha256||q.sourceFile) && <details><summary>查看出处位置与校验信息</summary>
        {q.sourceFile&&<p>文件：{q.sourceFile}</p>}{q.locator&&<p>位置：{q.locator}</p>}{q.sha256&&<p>内容哈希：{q.sha256}</p>}
      </details>}
    </article>)}
  </section>;
}
