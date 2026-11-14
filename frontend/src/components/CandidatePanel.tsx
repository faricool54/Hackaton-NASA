// Evidence report for one candidate (WS5 + WS6 copy). Keep the language honest:
// "unconfirmed" means "not matched to a catalog", never "new discovery".
import type { Candidate } from '../api/types';
import { formatRaDec, STATUS_LABEL } from '../api/format';
import { SpectrumChart } from './SpectrumChart';

export function CandidatePanel({ candidate }: { candidate: Candidate }) {
  const { motion, distance, known_match: km } = candidate;
  const first = candidate.detections[0];
  return (
    <div className="panel cand-panel">
      <h3>
        {km?.designation ?? candidate.id} <span className={`badge status-${candidate.status}`}>{STATUS_LABEL[candidate.status]}</span>
      </h3>
      <dl>
        <dt>Position (first detection)</dt>
        <dd>{formatRaDec(first.position.ra, first.position.dec)}</dd>
        <dt>Detections</dt>
        <dd>{candidate.detections.length}</dd>
        {motion && (
          <>
            <dt>Apparent motion</dt>
            <dd>
              {motion.rate_arcsec_per_hour.toFixed(2)}″/h toward PA {motion.position_angle_deg.toFixed(0)}°
            </dd>
          </>
        )}
        {distance && (
          <>
            <dt>Rough distance</dt>
            <dd>
              ~{distance.au_median.toFixed(1)} AU <span className="muted">({distance.method}; order of magnitude)</span>
            </dd>
          </>
        )}
        {km && (
          <>
            <dt>Catalog match</dt>
            <dd>
              {km.designation} ({km.object_type}) via {km.source}, {km.separation_arcsec.toFixed(1)}″ away
            </dd>
          </>
        )}
        <dt>Pipeline score</dt>
        <dd>{candidate.score.toFixed(2)}</dd>
      </dl>
      {candidate.spectrum.length > 0 && <SpectrumChart points={candidate.spectrum} />}
      {candidate.notes.length > 0 && (
        <ul className="notes">
          {candidate.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {/* TODO(WS5/WS3): image stamps per detection, orbit/distance plot, "what could it be?" explainer. */}
    </div>
  );
}
