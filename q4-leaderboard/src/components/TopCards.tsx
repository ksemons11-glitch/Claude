import type { PublicRow } from '@/lib/leaderboard';
import { formatPln } from '@/lib/validation';
import { Avatar } from './Avatar';
import { ChangeBadge } from './ChangeBadge';

/** Places 4–10: highlighted, but simpler than the podium. */
export function TopCards({ rows, weekly }: { rows: PublicRow[]; weekly: boolean }) {
  if (rows.length === 0) return null;
  return (
    <section aria-label="Top 10" className="mt-6">
      <h2 className="mb-2 px-1 text-sm font-bold uppercase tracking-wider text-muted">Top 10</h2>
      <ol className="grid gap-2">
        {rows.map((row) => (
          <li
            key={`${row.rank}-${row.nickname}`}
            className={`card flex items-center gap-3 border-accent/15 bg-gradient-to-r from-accent/[0.07] to-transparent px-3 py-3 ${row.isMe ? 'ring-1 ring-accent/60' : ''}`}
          >
            <span className="w-8 text-center text-lg font-extrabold tabular-nums text-accent">{row.rank}</span>
            <Avatar src={row.avatarUrl} size={44} />
            <div className="min-w-0 flex-1">
              <div className="truncate font-bold">
                {row.nickname}
                {row.isMe && <span className="ml-1.5 text-xs text-accent">(Ty)</span>}
              </div>
              <div className="text-sm font-semibold tabular-nums text-white/90">
                {weekly ? `+${formatPln(row.value)}` : formatPln(row.value)}
              </div>
            </div>
            {!weekly && <ChangeBadge change={row.change} isNew={row.isNew} />}
          </li>
        ))}
      </ol>
    </section>
  );
}
