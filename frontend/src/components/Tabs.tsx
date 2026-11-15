import { useId, type KeyboardEvent, type ReactNode } from 'react';
import '../styles/kit.css';

interface Props {
  label: string;
  items: readonly { id: string; label: string; content: ReactNode }[];
  active: string;
  onChange: (id: string) => void;
}

export function Tabs({ label, items, active, onChange }: Props) {
  const root = useId();

  const onKey = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next: number;
    switch (e.key) {
      case 'ArrowLeft': next = (index + items.length - 1) % items.length; break;
      case 'ArrowRight': next = (index + 1) % items.length; break;
      case 'Home': next = 0; break;
      case 'End': next = items.length - 1; break;
      default: return;
    }
    e.preventDefault();
    onChange(items[next].id);
    e.currentTarget.parentElement?.querySelectorAll('button')[next]?.focus();
  };

  return <>
    <div className="segmented kit-tabs" role="tablist" aria-label={label}>
      {items.map(({ id, label: title }, index) => <button key={id} type="button" role="tab"
        id={`${root}-tab-${id}`} aria-controls={`${root}-panel-${id}`}
        aria-selected={id === active} tabIndex={id === active ? 0 : -1}
        onClick={() => onChange(id)} onKeyDown={(e) => onKey(e, index)}>{title}</button>)}
    </div>
    {items.map(({ id, content }) => <div key={id} role="tabpanel" id={`${root}-panel-${id}`}
      aria-labelledby={`${root}-tab-${id}`} hidden={id !== active} tabIndex={0}>{content}</div>)}
  </>;
}
