import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { JobStatusResponse } from '../api/types';
import { EmptyState } from './EmptyState';
import { JobProgress } from './JobProgress';
import { Skeleton } from './Skeleton';
import { SourceBadge } from './SourceBadge';
import { Tabs } from './Tabs';

const job: JobStatusResponse = {
  id: 'build', status: 'queued', stage: 'queued', created_at: '2026-11-15T15:00:00Z',
  updated_at: '2026-11-15T15:01:03Z', result_field_id: null, error_detail: null,
};

describe('shared UI states', () => {
  it.each([
    ['queued', 'queued', 'Queued'],
    ['running', 'build', 'Building real observations'],
    ['running', 'publish', 'Publishing'],
    ['running', 'calibrating', 'calibrating'],
    ['ready', 'ready', 'Ready'],
    ['failed', 'interrupted', 'Build interrupted'],
    ['failed', 'build', 'Build failed'],
    ['no_coverage', 'build', 'No archive coverage'],
    ['pipeline_not_ready', 'build', 'Pipeline unavailable'],
  ] as const)('labels %s / %s', (status, stage, expected) => {
    const html = renderToStaticMarkup(<JobProgress job={{ ...job, status, stage }}
      onRetry={() => {}} onChoosePosition={() => {}} />);
    expect(html).toContain(`<p role="status"><strong>${expected}</strong></p>`);
    if (status === 'failed' || status === 'pipeline_not_ready') expect(html).toContain('>Retry<');
    if (status === 'no_coverage') expect(html).toContain('>Try another position<');
    if (status === 'ready') expect(html).toContain('1m 3s elapsed');
  });

  it('labels loading, empty and synthetic data', () => {
    expect(renderToStaticMarkup(<Skeleton label="Loading sequence" />)).toContain('aria-label="Loading sequence"');
    expect(renderToStaticMarkup(<EmptyState title="No sequence" action={<button>Retry</button>} />)).toContain('>Retry<');
    expect(renderToStaticMarkup(<SourceBadge kind="model" />)).toContain('3D MODEL');
    expect(renderToStaticMarkup(<SourceBadge kind="synthetic" />)).toContain('SYNTHETIC DATA · NOT SPHEREx');
  });

  it('announces the active and inactive tabs with their associated panels', () => {
    const html = renderToStaticMarkup(<Tabs label="Position views" active="time" onChange={() => {}}
      items={[{ id: 'time', label: 'Time', content: 'First panel' }, { id: 'spectrum', label: 'Spectrum', content: 'Second panel' }]} />);
    expect(html).toContain('role="tablist"');
    expect(html).toMatch(/aria-controls="[^"]+-panel-time" aria-selected="true" tabindex="0"/);
    expect(html).toMatch(/aria-labelledby="[^"]+-tab-spectrum" hidden=""/);
  });
});
