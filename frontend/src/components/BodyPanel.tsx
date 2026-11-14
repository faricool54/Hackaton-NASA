// Info panel for one body of a 3D system ("entering" a planet/star).
import { Fragment, useMemo, type CSSProperties } from 'react';
import type { Body, SystemModel } from '../api/types';
import { KIND_LABEL } from '../three/appearance';
import {
  appearanceNotes,
  FLAG_TEXT,
  NOTE_TIER_LABEL,
  NOTE_TIER_MEANING,
  NOTES_HEADER,
  SPHEREX_SCALE_NOTE,
  type AppearanceNote,
  type NoteTier,
} from '../three/appearanceNotes';
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

      <DrawingNotes system={system} body={body} />

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

// --- 'How this body is drawn' and 'At SPHEREx scale' (WS7 M6) ------------------------------------
// Inline styles only: styles.css belongs to WS5. Everything here is computed in the browser from the
// catalog values with the formulae stated on each row (three/appearanceNotes.ts); nothing here feeds
// the UNVERIFIED VALUES logic above.

/** Chip colours, readable on the dark panel background; not-drawn uses a dashed border. */
const TIER_COLOR: Readonly<Record<string, string>> = {
  measured: '#4ade80',
  derived: '#2dd4bf',
  model: '#7cc4ff',
  'range-pick': '#bef264',
  'class-typical': '#fb923c',
  theory: '#c084fc',
  illustrative: '#fbbf24',
  display: '#a5b4c8',
  'not-drawn': '#8e97ad',
};

const DETAILS_STYLE: CSSProperties = { marginTop: 10, borderTop: '1px solid var(--border)', paddingTop: 8 };
const SUMMARY_STYLE: CSSProperties = { cursor: 'pointer', fontWeight: 600, padding: '4px 0' };
const TABLE_STYLE: CSSProperties = { tableLayout: 'fixed' };
const WRAP: CSSProperties = { overflowWrap: 'anywhere' };
const NOTE_ROW_STYLE: CSSProperties = { borderTop: 'none', paddingTop: 0, paddingBottom: 6, overflowWrap: 'anywhere' };

function DrawingNotes({ system, body }: { system: SystemModel; body: Body }) {
  const result = useMemo(() => {
    try {
      return { rows: appearanceNotes(body, system), error: null as string | null };
    } catch (e) {
      return { rows: [] as AppearanceNote[], error: e instanceof Error ? e.message : String(e) };
    }
  }, [body, system]);
  if (result.error) {
    return <p className="muted small">The drawing notes could not be computed for this body ({result.error}).</p>;
  }
  const drawn = result.rows.filter((n) => n.section === 'drawn');
  const derived = result.rows.filter((n) => n.section === 'derived');
  const spherex = result.rows.filter((n) => n.section === 'spherex');
  return (
    <>
      <details style={DETAILS_STYLE}>
        <summary style={SUMMARY_STYLE}>
          How this body is drawn <span className="muted small">({drawn.length + derived.length} rows)</span>
        </summary>
        <p className="muted small">
          <span className="badge model">3D MODEL · NOT AN IMAGE</span> {NOTES_HEADER}. Both colour modes are listed;
          the 3D view opens in SPHEREx IR false colour.
        </p>
        <NotesTable rows={drawn} />
        {derived.length > 0 && (
          <>
            <p className="muted small" style={{ marginBottom: 0 }}>
              Physical quantities behind the drawing
            </p>
            <NotesTable rows={derived} />
          </>
        )}
      </details>
      <details style={DETAILS_STYLE}>
        <summary style={SUMMARY_STYLE}>
          At SPHEREx scale <span className="muted small">({spherex.length} rows)</span>
        </summary>
        <p className="muted small">
          {NOTES_HEADER}. {SPHEREX_SCALE_NOTE}
        </p>
        <NotesTable rows={spherex} />
      </details>
    </>
  );
}

function NotesTable({ rows }: { rows: readonly AppearanceNote[] }) {
  return (
    <table className="facts" style={TABLE_STYLE}>
      <tbody>
        {rows.map((n, i) => (
          <Fragment key={`${n.property}-${i}`}>
            <tr>
              <th scope="row" style={WRAP}>
                {n.property}
              </th>
              <td style={WRAP}>
                <ColourSwatch value={n.value} />
                {n.value}
                {n.unit ? ` ${n.unit}` : ''} <TierChip tier={n.tier} />
                {n.flags.length > 0 && (
                  <div className="small" style={{ color: 'var(--unconfirmed)' }}>
                    {n.flags.map((f) => FLAG_TEXT[f] ?? f).join('; ')}
                  </div>
                )}
              </td>
            </tr>
            <tr>
              <td colSpan={2} className="muted small" style={NOTE_ROW_STYLE}>
                {n.method}
                <br />
                <span style={{ fontStyle: 'italic' }}>Source: {n.citation}</span>
              </td>
            </tr>
          </Fragment>
        ))}
      </tbody>
    </table>
  );
}

function TierChip({ tier }: { tier: NoteTier }) {
  const color = TIER_COLOR[tier] ?? '#8e97ad';
  return (
    <span
      title={NOTE_TIER_MEANING[tier] ?? tier}
      style={{
        display: 'inline-block',
        fontSize: '0.66rem',
        fontWeight: 600,
        lineHeight: 1.5,
        letterSpacing: '0.02em',
        padding: '0 6px',
        borderRadius: 999,
        border: `1px ${tier === 'not-drawn' ? 'dashed' : 'solid'} ${color}`,
        color,
        whiteSpace: 'nowrap',
        verticalAlign: 'middle',
      }}
    >
      {NOTE_TIER_LABEL[tier] ?? tier.toUpperCase()}
    </span>
  );
}

/** A small square of the colour a row starts with ('#rrggbb …'), so the hex can be seen. */
function ColourSwatch({ value }: { value: string }) {
  const hex = /^#[0-9a-f]{6}\b/i.exec(value)?.[0];
  if (!hex) return null;
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-block',
        width: 10,
        height: 10,
        marginRight: 4,
        verticalAlign: 'middle',
        background: hex,
        border: '1px solid var(--border)',
        borderRadius: 2,
      }}
    />
  );
}
