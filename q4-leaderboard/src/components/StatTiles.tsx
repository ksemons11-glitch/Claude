import { formatPln } from '@/lib/validation';

export function StatTiles({
  participants,
  totalRevenue,
  topWeekly,
  week,
  weeks,
}: {
  participants: number;
  totalRevenue: number;
  topWeekly: number | null;
  week: number | null;
  weeks: number;
}) {
  const tiles = [
    { label: 'Aktywni uczestnicy', value: String(participants) },
    { label: 'Łączny przychód', value: formatPln(totalRevenue) },
    { label: 'Top przyrost tygodnia', value: topWeekly !== null ? `+${formatPln(topWeekly)}` : '—' },
    { label: 'Tydzień Q4', value: week !== null ? `${week} / ${weeks}` : '—' },
  ];
  return (
    <section aria-label="Podsumowanie eventu" className="grid grid-cols-2 gap-2">
      {tiles.map((t) => (
        <div key={t.label} className="card px-3.5 py-3">
          <div className="text-xs font-medium text-muted">{t.label}</div>
          <div className="mt-1 truncate text-lg font-extrabold tabular-nums">{t.value}</div>
        </div>
      ))}
    </section>
  );
}
