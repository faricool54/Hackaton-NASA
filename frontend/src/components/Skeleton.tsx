import '../styles/kit.css';

export function Skeleton({ label, lines = 3 }: { label: string; lines?: number }) {
  return <div className="kit-skeleton" role="status" aria-label={label}>
    {Array.from({ length: lines }, (_, index) => <span key={index} aria-hidden="true" />)}
  </div>;
}
