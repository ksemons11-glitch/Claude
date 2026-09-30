import Link from 'next/link';
import { Header } from '@/components/Header';
import { ChangeBadge } from '@/components/ChangeBadge';
import { RevenueForm } from '@/components/forms/RevenueForm';
import { requireUser } from '@/lib/auth';
import { config } from '@/lib/config';
import { query } from '@/lib/db';
import { loadLeaderboard, myPosition } from '@/lib/leaderboard';
import { isPeriodOpen } from '@/lib/periods';
import { entryFor, previousCumulative } from '@/lib/revenue';
import { formatDate, formatDateTime, formatFull } from '@/lib/time';
import { formatPln } from '@/lib/validation';

const STATUS_TEXT: Record<string, { title: string; body: string; contact: string }> = {
  pending: {
    title: 'Konto oczekuje na akceptację organizatora',
    body: 'Sprawdzamy, czy jesteś uczestnikiem programu (po nicku z Discorda). Po akceptacji będziesz mógł dodawać wyniki.',
    contact: 'Jeśli akceptacja się przedłuża, napisz na Discordzie do',
  },
  rejected: {
    title: 'Konto nie zostało zaakceptowane',
    body: 'Jeśli uważasz, że to pomyłka, daj nam znać.',
    contact: 'Napisz na Discordzie do',
  },
  suspended: {
    title: 'Konto jest czasowo zablokowane',
    body: 'Chcesz wyjaśnić sytuację?',
    contact: 'Napisz na Discordzie do',
  },
};

export default async function AccountPage() {
  const user = await requireUser();
  const lb = await loadLeaderboard();

  if (user.status !== 'active') {
    const t = STATUS_TEXT[user.status] ?? STATUS_TEXT.pending;
    return (
      <>
        <Header />
        <main className="mx-auto max-w-xl px-4 py-8">
          <div className="card p-6 text-center">
            <div className="text-4xl" aria-hidden>{user.status === 'pending' ? '⏳' : '⚠️'}</div>
            <h1 className="mt-3 text-xl font-extrabold">{t.title}</h1>
            <p className="mt-2 text-muted">{t.body}</p>
            {config.supportDiscord && (
              <p className="mt-4 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm">
                {t.contact} <b className="text-accent-2">{config.supportDiscord}</b>.
              </p>
            )}
            <Link href="/konto/profil" className="btn-ghost mt-5 w-full">Edytuj profil</Link>
          </div>
        </main>
      </>
    );
  }

  const period = lb.currentPeriod;
  const open = period && lb.state.phase === 'running' && isPeriodOpen(period, lb.now);
  const [current, previousOrNull] = period
    ? await Promise.all([entryFor(user.id, period.id), previousCumulative(user.id, lb.event.id, period.weekNumber)])
    : [null, null];
  const previous = previousOrNull ?? 0;

  const history = await query<{ week: number; value: number | string; updatedAt: Date; startsAt: Date; endsAt: Date }>(
    `SELECT p.week_number AS week, e.cumulative_revenue AS value, e.updated_at AS updatedAt, p.starts_at AS startsAt, p.ends_at AS endsAt
     FROM revenue_entries e JOIN reporting_periods p ON p.id = e.reporting_period_id
     WHERE e.user_id = ? AND e.event_id = ? ORDER BY p.week_number`,
    [user.id, lb.event.id],
  );
  const rows = history.map((h, i) => ({
    ...h,
    value: Number(h.value),
    // A first entry after week 1 is not a weekly increase (see weeklyAt in lib/ranking).
    weekly: i === 0 && h.week !== lb.periods[0]?.weekNumber ? null : Number(h.value) - (i > 0 ? Number(history[i - 1].value) : 0),
  }));

  const pos = myPosition(lb, user.id);

  return (
    <>
      <Header />
      <main className="mx-auto max-w-xl px-4 pb-16 pt-6">
        {pos.row && (
          <section className="card mb-4 flex items-center gap-4 p-4">
            <div className="text-center">
              <div className="text-3xl font-extrabold tabular-nums text-accent">{pos.row.rank}.</div>
              <div className="text-[10px] uppercase tracking-wider text-muted">z {pos.total}</div>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-lg font-bold">
                {formatPln(pos.row.cumulative)} <ChangeBadge change={pos.row.change} isNew={pos.row.isNew} />
              </div>
              <div className="text-sm text-muted">
                {pos.row.rank === 1
                  ? 'Prowadzisz w rankingu! 🏆'
                  : pos.gap !== null
                    ? `Jesteś na ${pos.row.rank}. miejscu. Do kolejnej pozycji brakuje Ci ${formatPln(pos.gap)}.`
                    : ''}
              </div>
            </div>
          </section>
        )}

        <section className="card p-5">
          <h1 className="text-xl font-extrabold">
            {period ? `Twój wynik — tydzień ${period.weekNumber}` : 'Twój wynik'}
          </h1>
          {period && lb.state.phase === 'running' && (
            <p className="mt-1 text-sm text-muted">
              {formatDate(period.startsAt)}–{formatDate(period.endsAt)} · termin: <b className="text-white">{formatDateTime(period.entryDeadline)}</b>
              {lb.now > period.entryDeadline && <span className="text-gold"> (ostatnia szansa — zamknięcie {formatDateTime(period.endsAt)})</span>}
            </p>
          )}
          <div className="mt-5">
            {open ? (
              <RevenueForm current={current} previous={previous} />
            ) : lb.state.phase === 'before' ? (
              <p className="alert-info">Dodawanie wyników ruszy {lb.periods[0] ? formatDateTime(lb.periods[0].startsAt) : 'wkrótce'}. Wpiszesz wtedy całą sprzedaż od 1 października.</p>
            ) : lb.state.phase === 'finished' ? (
              <p className="alert-info">Q4 zakończony — wyniki są zamknięte. Dziękujemy!</p>
            ) : (
              <p className="alert-info">Ten tydzień jest już zamknięty. Wynik dodasz w kolejnym tygodniu.</p>
            )}
          </div>
        </section>

        <section className="mt-6">
          <h2 className="mb-2 px-1 text-sm font-bold uppercase tracking-wider text-muted">Twoja historia</h2>
          {rows.length === 0 ? (
            <p className="card px-4 py-6 text-center text-sm text-muted">Brak wpisów.</p>
          ) : (
            <ul className="card divide-y divide-line overflow-hidden">
              {rows.map((r) => (
                <li key={r.week} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div>
                    <div className="font-semibold">Tydzień {r.week}</div>
                    <div className="text-xs text-muted">zmieniono {formatFull(r.updatedAt)}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold tabular-nums">{formatPln(r.value)}</div>
                    {r.weekly === null ? (
                      <div className="text-xs text-muted">pierwszy wpis</div>
                    ) : (
                      <div className="text-sm tabular-nums text-emerald-400">+{formatPln(r.weekly)}</div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="mt-6 grid grid-cols-2 gap-2">
          <Link href="/" className="btn-ghost">Ranking</Link>
          <Link href="/konto/profil" className="btn-ghost">Profil</Link>
        </div>
      </main>
    </>
  );
}
