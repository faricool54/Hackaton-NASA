import { objectTitle, summaryLines } from '../api/objectCard';
import type { ObjectContextResponse } from '../api/types';
import '../styles/object-card.css';

/** At most six lines of catalog context for the pinned map popup (FE-4). The same values and caveats as the card,
 *  from an answer already in hand (peekObjectContext / getObjectContextCached): it never fetches by itself. */
export function ObjectSummary({ data }: { data: ObjectContextResponse }) {
  const title = objectTitle(data);
  return <div className="oc-summary">
    <p className="oc-summary-title">
      <strong className="oc-clip" title={title}>{title}</strong>
      <span className="badge u-badge u-badge--catalog oc-badge">Catalog · not SPHEREx</span>
    </p>
    {summaryLines(data).map((line, i) => <p key={i} className={`oc-clip oc-tone-${line.tone}`} title={line.text}>{line.text}</p>)}
  </div>;
}
