import { useEffect, useState } from 'react';
import { client } from '../api/client';
import type { SystemModel } from '../api/types';
import { ErrorBoundary } from './ErrorBoundary';
import { SyntheticBadge } from './SyntheticBadge';
import { SystemViewer } from './SystemViewer';

export function SystemPreview({ systemId, allowSynthetic = false }: {
  systemId: string;
  allowSynthetic?: boolean;
}) {
  const [model, setModel] = useState<SystemModel | null>(null);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    client.getSystem(systemId).then((system) => {
      if (!current) return;
      if (system.provenance.synthetic && !allowSynthetic) setError('No real catalog model is available for this position.');
      else setModel(system);
    }).catch((e: Error) => { if (current) setError(e.message); });
    return () => { current = false; };
  }, [systemId, allowSynthetic]);
  if (error) return <p className="error" role="alert">Could not load the 3D model: {error}</p>;
  if (!model) return <p className="muted" role="status">Loading the 3D model…</p>;

  const synthetic = model.provenance.synthetic;
  return <>
    <h3>{model.name}{' '}<SyntheticBadge synthetic={synthetic} />{' '}
      {!synthetic && model.bodies.some((body) => body.facts.some((fact) => !fact.verified)) &&
        <span className="badge unverified-badge">UNVERIFIED VALUES</span>}
    </h3>
    <p className="muted small">{synthetic ? 'Synthetic demonstration model.' : 'Illustrative model based on catalog data.'} {model.representation_note}</p>
    <ErrorBoundary what="The 3D view">
      <SystemViewer system={model} selectedId={selectedId} onSelect={setSelectedId} fieldExists />
    </ErrorBoundary>
    <p><a href={`#/system/${model.id}${selectedId ? `/${selectedId}` : ''}`}>Open model and source details →</a></p>
  </>;
}
