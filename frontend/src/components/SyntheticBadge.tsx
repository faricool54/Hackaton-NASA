// Required by the project rules: synthetic data must ALWAYS be labelled in the UI.
export function SyntheticBadge({ synthetic }: { synthetic: boolean }) {
  if (!synthetic) return null;
  return (
    <span className="badge synthetic u-badge u-badge--synthetic" title="Generated for development — not real SPHEREx data">
      SYNTHETIC DATA · NOT SPHEREx
    </span>
  );
}
