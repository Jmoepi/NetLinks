// Fit score with a visual progress bar and tone; the numeric value stays tabular and the
// provisional flag stays adjacent so the human-decision context is visible at a glance.

interface FitScoreProps {
  score: number;
  provisional?: boolean;
}

export function FitScore({ score, provisional = false }: FitScoreProps) {
  const value = Math.round(score * 10) / 10;
  const pct = Math.max(0, Math.min(100, value));
  const tone = pct >= 60 ? "ok" : pct >= 40 ? "warn" : "fail";
  const color = `var(--${tone})`;
  return (
    <div className="fit-score" data-tone={tone}>
      <div
        className="fit-score-track"
        role="progressbar"
        aria-label={provisional ? "Provisional fit score" : "Fit score"}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
      >
        <div className="fit-score-fill" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="fit-score-value">
        <span className="score-num" style={{ color }}>
          {value.toFixed(1)}
        </span>
        <span className="score">/ 100</span>
      </span>
      {provisional ? <span className="fit-score-flag">provisional</span> : null}
    </div>
  );
}
