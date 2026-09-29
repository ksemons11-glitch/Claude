import Link from 'next/link';
import type { UserRow } from '@/lib/data';
import { avatarUrl } from '@/lib/data';
import { myPosition, type Leaderboard } from '@/lib/leaderboard';
import { formatPln } from '@/lib/validation';
import { Avatar } from './Avatar';
import { ChangeBadge } from './ChangeBadge';

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="card mx-auto max-w-3xl border-accent/40 bg-card/95 p-3 shadow-[0_-8px_40px_rgba(0,0,0,0.5)] backdrop-blur">
        {children}
      </div>
    </div>
  );
}

export function MyPositionCard({ user, lb }: { user: UserRow; lb: Leaderboard }) {
  if (user.role === 'admin') return null;

  if (user.status !== 'active') {
    const text =
      user.status === 'pending'
        ? 'Twoje konto oczekuje na akceptację organizatora.'
        : user.status === 'suspended'
          ? 'Twoje konto jest czasowo zablokowane.'
          : 'Twoje konto nie zostało zaakceptowane.';
    return (
      <Shell>
        <p className="text-center text-sm text-muted">{text}</p>
      </Shell>
    );
  }

  const { row, gap } = myPosition(lb, user.id);
  const canReport = lb.state.phase === 'running';

  if (!row) {
    return (
      <Shell>
        <div className="flex items-center gap-3">
          <Avatar src={avatarUrl(user)} size={44} />
          <p className="flex-1 text-sm">Nie masz jeszcze wyniku. Dodaj swój przychód i pojaw się w rankingu!</p>
        </div>
        {canReport && (
          <Link href="/konto" className="btn-primary mt-3 w-full">Dodaj przychód</Link>
        )}
      </Shell>
    );
  }

  const message =
    row.rank === 1
      ? 'Prowadzisz w rankingu! 🏆'
      : gap !== null
        ? `Do kolejnego miejsca brakuje Ci ${formatPln(gap)}.`
        : '';

  return (
    <Shell>
      <div className="flex items-center gap-3">
        <div className="text-center">
          <div className="text-2xl font-extrabold leading-none tabular-nums text-accent">{row.rank}.</div>
          <div className="mt-1 text-[10px] uppercase tracking-wider text-muted">miejsce</div>
        </div>
        <Avatar src={row.avatarUrl} size={44} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-bold">{formatPln(row.cumulative)}</span>
            <ChangeBadge change={row.change} isNew={row.isNew} />
          </div>
          <div className="text-xs text-muted">
            {row.weekly !== null ? (
              <>
                Ten tydzień: <span className="font-semibold text-white">+{formatPln(row.weekly)}</span>
              </>
            ) : row.isNew ? (
              'Pierwszy wpis — w rankingu tygodniowym od następnego tygodnia'
            ) : (
              'Ten tydzień: brak wpisu'
            )}
          </div>
        </div>
      </div>
      {message && <p className="mt-2 text-sm font-medium">{message}</p>}
      {canReport && (
        <Link href="/konto" className="btn-primary mt-3 w-full">Zaktualizuj przychód</Link>
      )}
    </Shell>
  );
}
