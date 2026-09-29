import type { PublicRow } from '@/lib/leaderboard';
import { formatPln } from '@/lib/validation';
import { Avatar } from './Avatar';
import { ChangeBadge } from './ChangeBadge';

export function RankRow({ row, weekly }: { row: PublicRow; weekly: boolean }) {
  return (
    <li
      className={`flex items-center gap-3 px-3 py-2.5 ${row.isMe ? 'bg-accent/10 ring-1 ring-inset ring-accent/40' : ''}`}
    >
      <span className="w-9 shrink-0 text-right text-sm font-bold tabular-nums text-muted">{row.rank}.</span>
      <Avatar src={row.avatarUrl} size={36} />
      <span className="min-w-0 flex-1 truncate font-medium">
        {row.nickname}
        {row.isMe && <span className="ml-1.5 text-xs text-accent">(Ty)</span>}
      </span>
      <span className="text-right">
        <span className="block font-bold tabular-nums">{weekly ? `+${formatPln(row.value)}` : formatPln(row.value)}</span>
      </span>
      {!weekly && (
        <span className="w-10 shrink-0 text-right">
          <ChangeBadge change={row.change} isNew={row.isNew} />
        </span>
      )}
    </li>
  );
}
