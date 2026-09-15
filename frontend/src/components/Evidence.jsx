import { bagSize } from '../lib/evidence.js';
import { asCompact, asText, asTextOrNull } from '../lib/text.js';
import Section from './Section.jsx';

const compact = (value) => asTextOrNull(asCompact(value));

// 版本号本身可能已经带 v / 前缀，别拼成 "vdmo:v21"。
function versionSuffix(version) {
  const text = asText(version);
  if (!text) return '';
  return ` · ${/^\d/.test(text) ? 'v' : ''}${text}`;
}

function Meta({ pairs }) {
  const kept = pairs.filter(([, v]) => v !== null && v !== undefined && v !== '');
  if (kept.length === 0) return null;
  return (
    <div className="ev__meta">
      {kept.map(([k, v], i) => (
        <span key={k}>
          {i > 0 && ' · '}
          <b>{k}</b> {asText(v)}
        </span>
      ))}
    </div>
  );
}

function Item({ kind, id, via, trust, body, quote, meta, caveat }) {
  return (
    <div className="ev__item" data-trust={trust ?? undefined}>
      <span className="ev__bar" />
      <div className="ev__main">
        <div className="ev__head">
          <span className="lbl">{asText(kind)}</span>
          {asTextOrNull(id) && <span className="ev__id">{asText(id)}</span>}
          {asTextOrNull(via) && <span className="ev__via">{asText(via)}</span>}
        </div>
        {asTextOrNull(quote) && <div className="ev__quote">{asText(quote)}</div>}
        {asTextOrNull(body) && <div className="ev__text">{asText(body)}</div>}
        {meta}
        {asTextOrNull(caveat) && <div className="ev__caveat">{asText(caveat)}</div>}
      </div>
    </div>
  );
}

export default function Evidence({ bag }) {
  const total = bagSize(bag);
  if (total === 0 && bag.patients.length === 0 && bag.notices.length === 0) return null;

  return (
    <Section defaultOpen={false}
      title={<>
        <h2>查看原始证据与出处</h2>
        <span className="lbl">{total ? `${total} 条` : ''}</span>
      </>}
    >
      <>
        {bag.patients.length > 0 && (
          <div style={{ marginBottom: 22 }}>
            <div className="lbl" style={{ marginBottom: 10 }}>患者与数据来源</div>
            <div>
              {bag.patients.map((p) => (
                <div className="srcrow" key={p.patientid}>
                  <span className="srcrow__k">患者</span>
                  <span className="srcrow__v">{asText(p.patientid)}</span>
                  {asTextOrNull(p.origin) && (
                    <span className={'chip ' + (p.origin === 'demo-cohort' ? 'chip--demo' : 'chip--indigo')}>
                      {asText(p.origin)}
                    </span>
                  )}
                  {asTextOrNull(p.tier) && <span className="chip chip--neutral">tier {asText(p.tier)}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="ev">
          {bag.inferred.map((f) => {
            const provisional = f.verificationStatus && f.verificationStatus !== 'Confirmed';
            return (
              <Item
                key={`i:${f.ruleId ?? f.conclusion}`}
                kind={provisional ? 'provisional' : 'inferred'}
                id={f.ruleId ? f.ruleId + versionSuffix(f.ruleVersion) : f.conclusion}
                via={f.tool}
                trust={provisional ? 'unverified' : null}
                body={[f.ruleId ? f.conclusion : null, f.interval && `区间 ${f.interval}`].filter(Boolean).join(' · ') || null}
                meta={<Meta pairs={[
                  ['verificationStatus', f.verificationStatus],
                  ['confirmationRequired', f.confirmationRequired === null ? null : String(f.confirmationRequired)],
                  ['appliesThreshold', f.appliesThreshold],
                  ['applicableContext', f.applicableContext],
                  ['basedOn', compact(f.basedOn)],
                ]} />}
                caveat={f.caveat
                  || (provisional ? `verificationStatus = ${f.verificationStatus}：这是判定状态，不是确诊结论。` : null)}
              />
            );
          })}

          {bag.quotes.map((q) => (
            <Item
              key={`q:${q.sha256}`}
              kind="quote"
              id={q.supports}
              via={q.tool}
              quote={q.quote}
              meta={<Meta pairs={[['sha256', q.sha256], ['supports', q.supports]]} />}
            />
          ))}

          {bag.asserted.map((a) => {
            const converted = a.sourceValue !== null && a.sourceValue !== undefined;
            return (
              <Item
                key={`a:${a.iri ?? a.test}`}
                kind={a.unverified ? 'unverified' : 'fact'}
                id={a.iri || a.test}
                via={a.tool}
                trust={a.unverified ? 'unverified' : null}
                body={[a.test, a.value !== null ? `${a.value}${a.unit ? ' ' + a.unit : ''}` : null]
                  .filter(Boolean).join(' = ') || null}
                meta={<Meta pairs={[
                  ['trust', a.trust],
                  ['origin', a.origin],
                  ['sqlRow', compact(a.sqlRow)],
                  ['换算自', converted ? `${a.sourceValue} ${a.sourceUnit ?? ''}` : null],
                ]} />}
                caveat={a.unverified ? 'trust_level = Unverified：不可作为可信测量或临床判断依据，仅供溯源。' : null}
              />
            );
          })}
        </div>

        {bag.notices.length > 0 && (
          <div style={{ marginTop: 16 }}>
            {bag.notices.map((n) => (
              <div className="ev__caveat" style={{ marginTop: 0 }} key={n.field + String(n.text).slice(0, 20)}>
                <b>{n.field}：</b> {asText(n.text)}
              </div>
            ))}
          </div>
        )}
      </>
    </Section>
  );
}
