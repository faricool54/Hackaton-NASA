import type { ReactNode } from 'react';
import '../styles/kit.css';

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="kit-empty">
    <p><strong>{title}</strong></p>
    {children}
    {action && <div className="kit-empty-action">{action}</div>}
  </div>;
}
