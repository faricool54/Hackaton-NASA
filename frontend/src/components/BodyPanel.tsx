// Info panel for one body of a 3D system ("entering" a planet/star).
import type { Body, SystemModel } from '../api/types';
import { KIND_LABEL } from '../three/appearance';

interface Props {
  system: SystemModel;
  body: Body;
  fieldExists: boolean;
}

export function BodyPanel({ system, body, fieldExists }: Props) {
  const parent = body.orbit ? system.bodies.find((b) => b.id === body.orbit!.parent) : undefined;
  const children = system.bodies.filter((b) => b.orbit?.parent === body.id);
  return (
    <div className="panel body-panel">
      <h2>{body.name}</h2>
      <p className="muted small">
        {KIND_LABEL[body.kind] ?? body.kind}
        {body.spectral_type ? ` · ${body.spectral_type}` : ''}
        {parent ? ` · orbits ${parent.name}` : ''}
      </p>
      {body.description && <p>{body.description}</p>}

      <dl>
        {body.teff_k && (
          <>
            <dt>Temperature</dt>
            <dd>~{Math.round(body.teff_k)} K</dd>
          </>
        )}
        {body.orbit && (
          <>
            <dt>Orbit size</dt>
            <dd>
              {formatAu(body.orbit.semi_major_axis_au)}
              {body.orbit.quality && body.orbit.quality !== 'fitted' && (
                <span className="unverified"> {body.orbit.quality === 'assumed' ? 'assumed, not fitted' : 'hypothetical'}</span>
              )}
            </dd>
            <dt>Orbital period</dt>
            <dd>{formatPeriod(body.orbit.period_days)}</dd>
            {body.orbit.eccentricity > 0 && (
              <>
                <dt>Eccentricity</dt>
                <dd>{body.orbit.eccentricity.toFixed(2)}</dd>
              </>
            )}
          </>
        )}
        {body.variability && (
          <>
            <dt>Variability</dt>
            <dd>
              {body.variability.kind}
              {body.variability.period_days ? `, every ${formatPeriod(body.variability.period_days)}` : ''}
              {body.variability.amplitude_mag ? `, ±${(body.variability.amplitude_mag / 2).toFixed(1)} mag` : ''}
            </dd>
          </>
        )}
      </dl>
      {body.orbit?.note && <p className="muted small">Orbit: {body.orbit.note}</p>}

      {body.facts.length > 0 && (
        <table className="facts">
          <tbody>
            {body.facts.map((f, i) => (
              <tr key={i}>
                <th scope="row">{f.label}</th>
                <td>
                  {f.value}
                  {f.unit ? ` ${f.unit}` : ''}
                  {!f.verified && (
                    <span className="unverified" title="Not yet checked against its source">
                      {' '}
                      unverified
                    </span>
                  )}
                  {f.source && <div className="muted small">{f.source}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {children.length > 0 && (
        <p className="small">
          Orbited by:{' '}
          {children.map((c, i) => (
            <span key={c.id}>
              {i > 0 && ', '}
              <a href={`#/system/${system.id}/${c.id}`}>{c.name}</a>
            </span>
          ))}
        </p>
      )}
      {body.candidate_id && system.field_id && fieldExists && (
        <p className="small">
          Seen as candidate <strong>{body.candidate_id}</strong> in{' '}
          <a href={`#/field/${system.field_id}`}>the SPHEREx field</a>.
        </p>
      )}
    </div>
  );
}

function formatAu(au: number): string {
  if (au < 0.1) return `${au.toFixed(4)} AU (${Math.round(au * 1.496e8).toLocaleString('en')} km)`;
  return `${au.toLocaleString('en', { maximumFractionDigits: 2 })} AU`;
}

function formatPeriod(days: number): string {
  if (days < 2) return `${(days * 24).toFixed(1)} hours`;
  if (days < 730) return `${days.toFixed(1)} days`;
  return `${(days / 365.25).toLocaleString('en', { maximumFractionDigits: 1 })} years`;
}
