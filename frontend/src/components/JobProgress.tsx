import { useEffect, useState } from 'react';
import { isTerminal, jobSteps, stageLabel } from '../api/jobs';
import type { JobStatusResponse } from '../api/types';
import '../styles/kit.css';

export function JobProgress({ job, onRetry, onChoosePosition }: {
  job: JobStatusResponse;
  onRetry?: () => void;
  onChoosePosition?: () => void;
}) {
  const [now, setNow] = useState(Date.now);
  const finished = isTerminal(job);
  useEffect(() => {
    if (finished) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [finished, job.id]);

  const elapsed = Math.floor(Math.max(0, (finished ? Date.parse(job.updated_at) : now) - Date.parse(job.created_at)) / 1000);
  const retry = job.status === 'failed' || job.status === 'pipeline_not_ready';
  return <div className="kit-job">
    <p role="status"><strong>{stageLabel(job)}</strong></p>
    {Number.isFinite(elapsed) && <p className="small muted">{Math.floor(elapsed / 60)}m {elapsed % 60}s elapsed</p>}
    <ol aria-label="Build steps">
      {jobSteps(job).map(({ label, current, complete }) => (
        <li key={label} aria-current={current ? 'step' : undefined}>{label}{complete && <span className="kit-sr-only"> complete</span>}</li>
      ))}
    </ol>
    {job.error_detail && <p>{job.error_detail}</p>}
    {retry && onRetry && <button type="button" onClick={onRetry}>Retry</button>}
    {job.status === 'no_coverage' && (onChoosePosition
      ? <button type="button" onClick={onChoosePosition}>Try another position</button>
      : <p>Try another position.</p>)}
  </div>;
}
