import type { PublicRow } from '@/lib/leaderboard';
import { formatPln } from '@/lib/validation';
import { Avatar } from './Avatar';
import { ChangeBadge } from './ChangeBadge';

const styles = [
  { ring: 'ring-gold', text: 'text-gold', bg: 'from-gold/25', medal: '🥇', height: 'pt-2' },
  { ring: 'ring-silver', text: 'text-silver', bg: 'from-silver/20', medal: '🥈', height: 'pt-8' },
  { ring: 'ring-bronze', text: 'text-bronze', bg: 'from-bronze/20', medal: '🥉', height: 'pt-12' },
];

function Spot({ row, place, weekly }: { row: PublicRow; place: 0 | 1 | 2; weekly: boolean }) {
  const s = styles[place];
  const big = place === 0;
  return (
    <div className={`flex min-w-0 flex-1 flex-col items-center ${s.height}`}>
      <div className="relative">
        <Avatar src={row.avatarUrl} size={big ? 84 : 60} className={`ring-4 ${s.ring}`} />
        <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 text-2xl" aria-hidden>{s.medal}</span>
      </div>
      <div
        className={`mt-4 w-full rounded-t-2xl bg-gradient-to-b ${s.bg} to-transparent px-1.5 pb-3 pt-3 text-center ${row.isMe ? 'ring-1 ring-accent/60' : ''}`}
      >
        <div className={`text-xs font-bold uppercase tracking-wider ${s.text}`}>{row.rank}. miejsce</div>
        <div className={`mt-1 truncate font-bold ${big ? 'text-lg' : 'text-sm'}`}>{row.nickname}</div>
        <div className={`mt-0.5 font-extrabold tabular-nums ${big ? 'text-lg' : 'text-sm'}`}>
          {weekly ? `+${formatPln(row.value)}` : formatPln(row.value)}
        </div>
        {!weekly && (
          <div className="mt-1 h-5">
            <ChangeBadge change={row.change} isNew={row.isNew} />
          </div>
        )}
      </div>
    </div>
  );
}

export function Podium({ rows, weekly }: { rows: PublicRow[]; weekly: boolean }) {
  const [first, second, third] = rows;
  if (!first) return null;
  return (
    <section aria-label="Podium" className="flex items-start gap-2">
      {second ? <Spot row={second} place={1} weekly={weekly} /> : <div className="flex-1" />}
      <Spot row={first} place={0} weekly={weekly} />
      {third ? <Spot row={third} place={2} weekly={weekly} /> : <div className="flex-1" />}
    </section>
  );
}
