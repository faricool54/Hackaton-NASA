// Sky context map (WS5, P1). Placeholder until Aladin Lite is integrated.
//
// TODO(WS5): Aladin Lite v3 (https://aladin.cds.unistra.fr/AladinLite/doc/) loaded
// from a CDN on demand, centered on field.center with fov = size_deg * 3, the
// field footprint drawn as a box, candidate tracks as polylines, and survey
// layers 2MASS / AllWISE / DSS. Optional: SPHEREx HiPS if IRSA publishes one
// that Aladin can read (DR1 includes a spectral HiPS cube, see docs/DATA.md).
// Also an all-sky overview on the home page: where our fields are + ecliptic +
// Planet Nine search region (polygon from WS3, errante.science.planet_x).
import type { Field } from '../api/types';
import { formatRaDec } from '../api/format';

export function SkyMap({ field }: { field: Field }) {
  const { ra, dec } = field.center;
  const aladin = `https://aladin.cds.unistra.fr/AladinLite/?target=${ra}%20${dec}&fov=${field.size_deg * 4}&survey=P%2F2MASS%2Fcolor`;
  return (
    <div className="panel skymap-placeholder">
      <p>
        Field center {formatRaDec(ra, dec)} · {field.size_deg}° wide
      </p>
      <a href={aladin} target="_blank" rel="noreferrer">
        Open this position in Aladin Lite ↗
      </a>
    </div>
  );
}
