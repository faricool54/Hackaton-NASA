import { SHOWCASE_TARGETS, type ShowcaseTarget } from '../api/showcase';
import { showcaseSequence, type SearchSequence } from '../api/skySearch';
import { SyntheticBadge } from './SyntheticBadge';
import '../styles/search.css';

interface Props {
  sequences: SearchSequence[];
  activeName?: string;
  onPick: (target: ShowcaseTarget, sequence?: SearchSequence) => void;
}

export function TargetChips({ sequences, activeName, onPick }: Props) {
  return <div className="sx-targets" role="group" aria-label="Challenge targets">
    {SHOWCASE_TARGETS.map((target) => {
      const sequence = showcaseSequence(sequences, target);
      return <button key={target.fieldId} type="button" className="sx-target"
        aria-pressed={activeName === target.name} onClick={() => onPick(target, sequence)}>
        <span>{target.name} <SyntheticBadge synthetic={sequence?.field.synthetic ?? false} /></span>
        <span className="sx-target-detail">
          {target.testCase}{sequence && ` · ${sequence.field.n_frames} frames`}
        </span>
      </button>;
    })}
  </div>;
}
