// Info panel for one body of a 3D system ("entering" a planet/star).
import { Fragment, useEffect, useMemo, useState } from 'react';
import type { Body, Fact, SystemModel } from '../api/types';
// From the astro-free module: appearance.ts would pull astro.ts into the main chunk.
import { KIND_LABEL } from '../three/kindLabels';
// Types only: the module itself is loaded on demand (loadNotes), so it stays out of the main chunk.
import type { AppearanceNote, NoteTier } from '../three/appearanceNotes';
import {
  formatAu,
  formatOrbitPeriod,
  isNonFittedOrbit,
  modelValuesUnverified,
  twoSigFigs,
  variabilityAnimationNote,
  variabilityText,
} from '../three/bodyFormat';
// Astro-free too: fact origin chips and the unknown colour / size rules of the 3D view.
import {
  FACT_ORIGIN_LABEL,
  FACT_ORIGIN_MEANING,
  factOrigin,
  isColourKnown,
  isSizeKnown,
  keyFact,
  UNKNOWN_COLOUR_REASON,
  UNKNOWN_COLOUR_TEXT,
  UNKNOWN_SIZE_REASON,
  UNKNOWN_SIZE_TEXT,
  unknownReason,
  type FactOrigin,
} from '../three/factOrigin';
import '../three/system.css';

interface Props {
  system: SystemModel;
  body: Body;
  fieldExists: boolean;
  /** True when the linked field or the system is synthetic: never call it a SPHEREx field then. */
  fieldSynthetic?: boolean;
  /**
   * Dock / tab size (FE-12): name, kind, temperature and radius (or "unknown") and the fact origins, with
   * the full panel behind a disclosure. Default false.
   */
  compact?: boolean;
}

export function BodyPanel(props: Props) {
  if (props.compact) return <CompactBodyPanel {...props} />;
  return <FullBodyPanel {...props} />;
}

const R_SUN_KM = 695_700; // IAU 2015 nominal solar radius

/** Key data only; the full panel (facts, sources, drawing notes) opens below. */
function CompactBodyPanel(props: Props) {
  const { system, body } = props;
  const synthetic = system.provenance.synthetic;
  const parent = body.orbit ? system.bodies.find((b) => b.id === body.orbit!.parent) : undefined;
  const real = !synthetic;
  const teff = body.teff_k != null && body.teff_k > 0 ? body.teff_k : null;
  const radius = isSizeKnown(body) ? body.radius_km! : null;
  const stellar = body.kind === 'star' || body.kind === 'brown_dwarf';
  const colourUnknown = real && !isColourKnown(body);
  const sizeUnknown = real && !isSizeKnown(body);
  // Each value is shown under the label of the fact that gives it ("Radius (model estimate)"), with that fact's
  // origin and verified flag: a qualifier never stays folded in the disclosure while its value is visible.
  const teffFact = teff !== null ? keyFact(body.facts, 'temperature', teff) : null;
  const radiusFact = radius !== null ? keyFact(body.facts, 'radius', radius) : null;
  const origins = [...new Set(body.facts.map((f) => factOrigin(f, synthetic)))];
  const unverified = modelValuesUnverified(system);
  return (
    <div className="panel body-panel s3d-body s3d-body--compact">
      <h2>{body.name}</h2>
      <p className="muted small">
        {KIND_LABEL[body.kind] ?? body.kind}
        {body.spectral_type ? ` · ${body.spectral_type}` : ''}
        {parent ? ` · orbits ${parent.name}` : ''}
      </p>
      <dl className="s3d-body-key">
        <dt>{teffFact?.label ?? 'Temperature'}</dt>
        <dd>
          {teff !== null ? `~${Math.round(teff)} K` : colourUnknown ? `unknown: ${UNKNOWN_COLOUR_TEXT}` : 'unknown'}
          {teffFact && <FactFlags fact={teffFact} synthetic={synthetic} />}
        </dd>
        <dt>{radiusFact?.label ?? 'Radius'}</dt>
        <dd>
          {radius !== null
            ? `~${twoSigFigs(radius)} km${stellar ? ` (${twoSigFigs(radius / R_SUN_KM)} R☉)` : ''}`
            : sizeUnknown
              ? `unknown: ${UNKNOWN_SIZE_TEXT}`
              : 'unknown'}
          {radiusFact && <FactFlags fact={radiusFact} synthetic={synthetic} />}
        </dd>
      </dl>
      {(origins.length > 0 || unverified) && (
        <p className="s3d-origins small">
          {origins.length > 0 && <span className="muted">All facts:</span>}
          {origins.map((o) => (
            <OriginChip key={o} origin={o} />
          ))}
          {unverified && (
            <span className="unverified s3d-unverified" title="Some values of this system are estimates that no catalog or paper states">
              unverified
            </span>
          )}
        </p>
      )}
      <details className="s3d-disclosure">
        <summary>All facts, sources and drawing notes</summary>
        <BodyDetails {...props} heading={false} />
      </details>
    </div>
  );
}

function FullBodyPanel(props: Props) {
  return (
    <div className="panel body-panel s3d-body">
      <BodyDetails {...props} heading />
    </div>
  );
}

function BodyDetails({ system, body, fieldExists, fieldSynthetic, heading }: Props & { heading: boolean }) {
  const parent = body.orbit ? system.bodies.find((b) => b.id === body.orbit!.parent) : undefined;
  const children = system.bodies.filter((b) => b.orbit?.parent === body.id);
  // A synthetic system can only point at synthetic frames, even if the caller did not say so.
  const syntheticField = fieldSynthetic === true || system.provenance.synthetic;
  const teff = body.teff_k != null && body.teff_k > 0 ? body.teff_k : null;
  // Real systems only: the synthetic demo's look is decoration, not drawn from Teff or a radius.
  const real = !system.provenance.synthetic;
  const colourUnknown = real && !isColourKnown(body);
  const sizeUnknown = real && !isSizeKnown(body);
  // The body's own reason from the pipeline note, else the generic one.
  const colourReason = (colourUnknown && unknownReason(system, body, 'temperature')) || UNKNOWN_COLOUR_REASON;
  const sizeReason = (sizeUnknown && unknownReason(system, body, 'radius')) || UNKNOWN_SIZE_REASON;
  const hasModelRows = teff !== null || colourUnknown || sizeUnknown || !!body.orbit || !!body.variability;
  const unverified = modelValuesUnverified(system);
  const animationNote = body.variability ? variabilityAnimationNote(body.variability) : null;
  return (
    <>
      {heading && (
        <>
          <h2>{body.name}</h2>
          <p className="muted small">
            {KIND_LABEL[body.kind] ?? body.kind}
            {body.spectral_type ? ` · ${body.spectral_type}` : ''}
            {parent ? ` · orbits ${parent.name}` : ''}
          </p>
        </>
      )}
      {body.description && <p>{body.description}</p>}

      {hasModelRows && (
        <>
          <p className="muted small">
            Model parameters used to draw the scene
            {unverified && (
              <span className="unverified s3d-unverified" title="Some values of this system are estimates that no catalog or paper states">
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
            {colourUnknown && (
              <>
                <dt>Temperature</dt>
                <dd>
                  unknown: {UNKNOWN_COLOUR_TEXT}
                  <div className="muted small">Why: {colourReason}.</div>
                </dd>
              </>
            )}
            {sizeUnknown && (
              <>
                <dt>Radius</dt>
                <dd>
                  unknown: {UNKNOWN_SIZE_TEXT}
                  <div className="muted small">Why: {sizeReason}.</div>
                </dd>
              </>
            )}
            {body.orbit && (
              <>
                <dt>Orbit size</dt>
                <dd>
                  {formatAu(body.orbit.semi_major_axis_au)}
                  {isNonFittedOrbit(body.orbit) && (
                    <span className="unverified s3d-unverified">
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
        <table className="facts s3d-facts">
          <tbody>
            {body.facts.map((f, i) => (
              <tr key={i}>
                <th scope="row">{f.label}</th>
                <td>
                  {f.value}
                  {f.unit ? ` ${f.unit}` : ''} <OriginChip origin={factOrigin(f, system.provenance.synthetic)} />
                  {!f.verified && (
                    <span className="unverified s3d-unverified" title="An estimate, or a value not found in its source">
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
    </>
  );
}

/**
 * Where a fact comes from: SPHEREx-measured, derived, catalog (not measured by SPHEREx), no source, or synthetic
 * demo. Colours: the provenance tokens of FRONTEND_PLAN §3.2 (three/system.css); the label always says it.
 */
function OriginChip({ origin }: { origin: FactOrigin }) {
  return (
    <span className={`s3d-origin s3d-origin--${origin}`} title={FACT_ORIGIN_MEANING[origin]}>
      {FACT_ORIGIN_LABEL[origin]}
    </span>
  );
}

/** A fact's origin chip and, when it is not verified, the same 'unverified' tag as its row in the facts table. */
function FactFlags({ fact, synthetic }: { fact: Fact; synthetic: boolean }) {
  return (
    <>
      {' '}
      <OriginChip origin={factOrigin(fact, synthetic)} />
      {!fact.verified && (
        <span className="unverified s3d-unverified" title="An estimate, or a value not found in its source">
          {' '}
          unverified
        </span>
      )}
    </>
  );
}

// --- 'How this body is drawn' and 'At SPHEREx scale' (WS7 M6) ------------------------------------
// Styles: three/system.css (.s3d-). Everything here is computed in the browser from the
// catalog values with the formulae stated on each row (three/appearanceNotes.ts); nothing here feeds
// the UNVERIFIED VALUES logic above.
//
// three/appearanceNotes.ts and its text tables are loaded on demand (dynamic import), the first
// time either section is opened, hovered or focused, so the main chunk does not carry them.

type NotesModule = typeof import('../three/appearanceNotes');

/** The notes module once loaded (shared by every panel), and the load in flight. */
let notesModule: NotesModule | null = null;
let notesLoading: Promise<NotesModule> | null = null;

function loadNotes(): Promise<NotesModule> {
  if (notesModule) return Promise.resolve(notesModule);
  notesLoading ??= import('../three/appearanceNotes').then(
    (m) => {
      notesModule = m;
      return m;
    },
    (e: unknown) => {
      notesLoading = null; // a later attempt retries the download
      throw e;
    },
  );
  return notesLoading;
}

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

function DrawingNotes({ system, body }: { system: SystemModel; body: Body }) {
  const [mod, setMod] = useState<NotesModule | null>(notesModule);
  // 0 = not requested yet; each retry after a failed download increments it.
  const [attempt, setAttempt] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (attempt === 0 || mod) return;
    let alive = true;
    loadNotes().then(
      (m) => {
        if (alive) setMod(m);
      },
      (e: unknown) => {
        if (alive) setLoadError(errorText(e));
      },
    );
    return () => {
      alive = false;
    };
  }, [attempt, mod]);

  const result = useMemo(() => {
    if (!mod) return null;
    try {
      return { rows: mod.appearanceNotes(body, system), error: null as string | null };
    } catch (e) {
      return { rows: [] as AppearanceNote[], error: errorText(e) };
    }
  }, [mod, body, system]);

  const request = () => setAttempt((a) => a || 1);
  const retry = () => {
    setLoadError(null);
    setAttempt((a) => a + 1);
  };
  const onToggle = (e: { currentTarget: HTMLDetailsElement }) => {
    if (e.currentTarget.open) request();
  };

  if (result?.error) {
    return <p className="muted small">The drawing notes could not be computed for this body ({result.error}).</p>;
  }
  const rows = result?.rows ?? null;
  const drawn = rows?.filter((n) => n.section === 'drawn') ?? [];
  const derived = rows?.filter((n) => n.section === 'derived') ?? [];
  const spherex = rows?.filter((n) => n.section === 'spherex') ?? [];
  const pending = loadError ? (
    <p className="muted small" role="alert">
      The drawing notes could not be downloaded ({loadError}).{' '}
      <button type="button" onClick={retry}>
        Retry
      </button>
    </p>
  ) : (
    <p className="muted small" role="status">
      Computing the drawing notes…
    </p>
  );
  const count = (n: number) => (rows ? <span className="muted small">({n} rows)</span> : null);
  return (
    <>
      <details className="s3d-notes-details" onToggle={onToggle}>
        <summary onPointerEnter={request} onFocus={request}>
          How this body is drawn {count(drawn.length + derived.length)}
        </summary>
        <p className="muted small">
          <span className="badge u-badge u-badge--model">3D MODEL · NOT AN IMAGE</span>{' '}
          {mod && (
            <>
              {mod.NOTES_HEADER}. Every colour mode is listed; the 3D view opens in{' '}
              {mod.SCENE_DRAWING_DEFAULTS.colourMode}.
            </>
          )}
        </p>
        {mod && rows ? (
          <>
            <NotesTable rows={drawn} notes={mod} />
            {derived.length > 0 && (
              <>
                <p className="muted small s3d-notes-sub">
                  Physical quantities behind the drawing
                </p>
                <NotesTable rows={derived} notes={mod} />
              </>
            )}
          </>
        ) : (
          pending
        )}
      </details>
      <details className="s3d-notes-details" onToggle={onToggle}>
        <summary onPointerEnter={request} onFocus={request}>
          At SPHEREx scale {count(spherex.length)}
        </summary>
        {mod && rows ? (
          <>
            <p className="muted small">
              {mod.NOTES_HEADER}. {mod.SPHEREX_SCALE_NOTE}
            </p>
            <NotesTable rows={spherex} notes={mod} />
          </>
        ) : (
          pending
        )}
      </details>
    </>
  );
}

function NotesTable({ rows, notes }: { rows: readonly AppearanceNote[]; notes: NotesModule }) {
  return (
    <table className="facts s3d-facts s3d-notes-table">
      <tbody>
        {rows.map((n, i) => (
          <Fragment key={`${n.property}-${i}`}>
            <tr>
              <th scope="row">{n.property}</th>
              <td>
                <ColourSwatch value={n.value} />
                {n.value}
                {n.unit ? ` ${n.unit}` : ''} <TierChip tier={n.tier} notes={notes} />
                {n.flags.length > 0 && (
                  <div className="small s3d-flags">
                    {n.flags.map((f) => notes.FLAG_TEXT[f] ?? f).join('; ')}
                  </div>
                )}
              </td>
            </tr>
            <tr>
              <td colSpan={2} className="muted small s3d-note-row">
                {n.method}
                <br />
                <span className="s3d-cite">Source: {n.citation}</span>
              </td>
            </tr>
          </Fragment>
        ))}
      </tbody>
    </table>
  );
}

/** Tier colours in three/system.css (.s3d-tier--<tier>); not-drawn uses a dashed border, the label always says it. */
function TierChip({ tier, notes }: { tier: NoteTier; notes: NotesModule }) {
  return (
    <span className={`s3d-tier s3d-tier--${tier}`} title={notes.NOTE_TIER_MEANING[tier] ?? tier}>
      {notes.NOTE_TIER_LABEL[tier] ?? tier.toUpperCase()}
    </span>
  );
}

/** A small square of the colour a row starts with ('#rrggbb …'), so the hex can be seen. */
function ColourSwatch({ value }: { value: string }) {
  const hex = /^#[0-9a-f]{6}\b/i.exec(value)?.[0];
  if (!hex) return null;
  // Dynamic: the colour of the row itself.
  return <span aria-hidden="true" className="s3d-colour-swatch" style={{ background: hex }} />;
}
