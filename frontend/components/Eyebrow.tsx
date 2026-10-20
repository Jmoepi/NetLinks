/** Small uppercase label with the accent dot and a hairline, as in the design reference. */
export function Eyebrow({ label }: { label: string }) {
  return (
    <div className="eyebrow">
      <span>{label}</span>
      <span className="eyebrow-dot" aria-hidden="true" />
      <span className="eyebrow-line" aria-hidden="true" />
    </div>
  );
}
