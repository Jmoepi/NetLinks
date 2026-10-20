/**
 * Mono accent section index, e.g. "01 / PROFILE". Decorative: it repeats the heading it sits above,
 * so it is hidden from assistive technology.
 */
export function SectionIndex({ n, label }: { n?: number; label: string }) {
  const prefix = n === undefined ? "" : `${String(n).padStart(2, "0")} / `;
  return (
    <span className="section-index" aria-hidden="true">
      {prefix}
      {label.toUpperCase()}
    </span>
  );
}
