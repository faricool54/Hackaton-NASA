// Info panel for one body of a 3D system ("entering" a planet/star).
import type { Body, SystemModel } from '../api/types';
import { KIND_LABEL } from '../three/appearance';
import {
  formatAu,
  formatOrbitPeriod,
  isNonFittedOrbit,
  modelValuesUnverified,
  variabilityAnimationNote,
  variabilityText,
} from '../three/bodyFormat';

interface Props {
  system: SystemModel;
  body: Body;
  fieldExists: boolean;
  /** True when the linked field or the system is synthetic: never call it a SPHEREx field then. */
  fieldSynthetic?: boolean;
}

export function BodyPanel({ system, body, fieldExists, fieldSynthetic }: Props) {
  const parent = body.orbit ? system.bodies.find((b) => b.id === body.orbit!.parent) : undefined;
  const children = system.bodies.filter((b) => b.orbit?.parent === body.id);
  // A synthetic system can only point at synthetic frames, even if the caller did not say so.
  const syntheticField = fieldSynthetic === true || system.provenance.synthetic;
  const teff = body.teff_k != null && body.teff_k > 0 ? body.teff_k : null;
  const hasModelRows = teff !== null || !!body.orbit || !!body.variability;
  const unverified = modelValuesUnverified(system);
  const animationNote = body.variability ? variabilityAnimationNote(body.variability) : null;
  return (
    <div className="panel body-panel">
      <h2>{body.name}</h2>
      <p className="muted small">
        {KIND_LABEL[body.kind] ?? body.kind}
        {body.spectral_type ? ` · ${body.spectral_type}` : ''}
        {parent ? ` · orbits ${parent.name}` : ''}
      </p>
      {body.description && <p>{body.description}</p>}

      {hasModelRows && (
        <>
          <p className="muted small">
            Model parameters used to draw the scene
            {unverified && (
              <span className="unverified" title="Some values of this system are estimates that no catalog or paper states">
                {' '}
                unverified
              </span>
            )}
          </p>
          <dl>
            {teff !== null && (
              <>
                <dt>Temperature</dt>
                <dd>~{Math.round(teff)} K</dd>
              </>
            )}
            {body.orbit && (
              <>
                <dt>Orbit size</dt>
                <dd>
                  {formatAu(body.orbit.semi_major_axis_au)}
                  {isNonFittedOrbit(body.orbit) && (
                    <span className="unverified">
                      {' '}
                      {body.orbit.quality === 'assumed' ? 'assumed, not fitted' : 'hypothetical'}
                    </span>
                  )}
                </dd>
                <dt>Orbital period</dt>
                <dd>{formatOrbitPeriod(body.orbit)}</dd>
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
                  {variabilityText(body.variability)}
                  {animationNote && <div className="muted small">{animationNote}</div>}
                </dd>
              </>
            )}
          </dl>
        </>
      )}
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
                    <span className="unverified" title="An estimate, or a value not found in its source">
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
          {syntheticField ? (
            <>
              Appears as synthetic candidate <strong>{body.candidate_id}</strong> in{' '}
              <a href={`#/field/${system.field_id}`}>the synthetic demo field</a>.
            </>
          ) : (
            <>
              Seen as candidate <strong>{body.candidate_id}</strong> in{' '}
              <a href={`#/field/${system.field_id}`}>the SPHEREx field</a>.
            </>
          )}
        </p>
      )}
    </div>
  );
}
