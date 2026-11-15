// A field links back to the shared home map rather than allocating a second WebGL viewer.
import type { Field } from '../api/types';
import { formatRaDec } from '../api/format';
import { positionUrl } from '../api/jobs';

export function SkyMap({ field }: { field: Field }) {
  const { ra, dec } = field.center;
  const map = positionUrl(location.href, { ra, dec, size_deg: Math.min(0.5, Math.max(0.01, field.size_deg)),
    detectors: [field.frames[0]?.detector ?? 2] });
  return (
    <p className="fd-skymap small">
      <span>Field center <span className="u-mono">{formatRaDec(ra, dec)}</span> · {field.size_deg}° wide</span>
      <a href={map}>Explore this position on the SPHEREx map →</a>
    </p>
  );
}
