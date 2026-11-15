import { SyntheticBadge } from './SyntheticBadge';

const LABELS = {
  spherex: 'SPHEREx', catalog: 'Catalog', gaia: 'Gaia DR3',
  model: '3D MODEL', injected: 'INJECTED',
};

export function SourceBadge({ kind }: { kind: keyof typeof LABELS | 'synthetic' }) {
  if (kind === 'synthetic') return <SyntheticBadge synthetic />;
  return <span className={`badge u-badge u-badge--${kind === 'injected' ? 'warn' : kind}`}>{LABELS[kind]}</span>;
}
