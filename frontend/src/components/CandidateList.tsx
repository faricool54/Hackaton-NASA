import type { Candidate } from '../api/types';
import { STATUS_LABEL } from '../api/format';

interface Props {
  candidates: Candidate[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export function CandidateList({ candidates, selectedId, onSelect }: Props) {
  // AGENTS.md rule 12: an empty list means the optional analysis was not run or published, not "nothing moves here".
  if (!candidates.length) {
    return <p className="muted small fd-analysis">No candidate measurements provided: the moving-object analysis was not
      run (or its results were not published) for this field. This is not a negative detection result.</p>;
  }
  const sorted = [...candidates].sort((a, b) => b.score - a.score);
  return (
    <ul className="cand-list">
      {sorted.map((c) => (
        <li key={c.id}>
          <button
            className={`cand ${c.id === selectedId ? 'selected' : ''}`}
            onClick={() => onSelect(c.id === selectedId ? null : c.id)}
          >
            <span className={`badge status-${c.status}`}>{STATUS_LABEL[c.status] ?? c.status}</span>
            <span className="cand-id">{c.known_match?.designation ?? c.id}</span>
            <span className="muted">
              {c.motion ? `${c.motion.rate_arcsec_per_hour.toFixed(2)}″/h` : '—'} · {c.detections.length} det · score{' '}
              {c.score.toFixed(2)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
