export function ChangeBadge({ change, isNew }: { change: number | null; isNew?: boolean }) {
  if (isNew) {
    return <span className="rounded-md bg-sky-400/15 px-1.5 py-0.5 text-xs font-bold text-sky-300">NOWY</span>;
  }
  if (change === null) return null;
  if (change > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-sm font-bold text-emerald-400" title={`Awans o ${change}`}>
        <span aria-hidden>▲</span>
        {change}
        <span className="sr-only"> miejsc w górę</span>
      </span>
    );
  }
  if (change < 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-sm font-bold text-red-400" title={`Spadek o ${-change}`}>
        <span aria-hidden>▼</span>
        {-change}
        <span className="sr-only"> miejsc w dół</span>
      </span>
    );
  }
  return (
    <span className="text-sm font-bold text-muted" title="Bez zmian">
      <span aria-hidden>●</span>
      <span className="sr-only">bez zmian</span>
    </span>
  );
}
