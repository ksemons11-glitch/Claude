import Link from 'next/link';
import { Header } from '@/components/Header';
import { Countdown } from '@/components/Countdown';
import { StatTiles } from '@/components/StatTiles';
import { Podium } from '@/components/Podium';
import { TopCards } from '@/components/TopCards';
import { RankRow } from '@/components/RankRow';
import { FullRanking } from '@/components/FullRanking';
import { MyPositionCard } from '@/components/MyPositionCard';
import { Avatar } from '@/components/Avatar';
import { getCurrentUser } from '@/lib/auth';
import { loadLeaderboard, parseView, toPublicRow, type RankingView } from '@/lib/leaderboard';
import { formatDate, formatDateTime } from '@/lib/time';
import { formatPln } from '@/lib/validation';

const LIST_END = 50;

/** Event name with its last word in the brand accent, like the headlines on nextlevel-marketing.pl. */
function BrandTitle({ name }: { name: string }) {
  const words = name.trim().split(/\s+/);
  if (words.length < 2) return <span className="text-accent">{name}</span>;
  const last = words.pop();
  return (
    <>
      {words.join(' ')} <span className="text-accent">{last}</span>
    </>
  );
}

export default async function Home({ searchParams }: { searchParams: Promise<{ view?: string }> }) {
  const view = parseView((await searchParams).view);
  const user = await getCurrentUser();
  const lb = await loadLeaderboard(user?.role === 'admin' && user.status === 'active');
  const canSee = lb.event.isPublicLeaderboard || user?.status === 'active';
  const weekly = view !== 'q4';
  const meId = user?.status === 'active' ? user.id : null;
  const all = lb.rankings[view];
  const rows = all.slice(0, LIST_END).map((r) => toPublicRow(r, meId));
  const topWeekly = lb.rankings.week[0]?.value ?? null;
  const period = lb.currentPeriod;
  const prevPeriod = lb.state.index > 0 ? lb.periods[lb.state.index - 1] : null;
  const shownPeriod = view === 'prev' ? prevPeriod : view === 'week' ? period : null;

  let countdown: { target: Date; label: string } | null = null;
  if (lb.state.phase === 'before' && lb.periods[0]) countdown = { target: lb.periods[0].startsAt, label: 'Start rankingu za' };
  else if (lb.state.phase === 'running' && period) {
    countdown =
      lb.now < period.entryDeadline
        ? { target: period.entryDeadline, label: `Termin wpisów — tydzień ${period.weekNumber}` }
        : { target: period.endsAt, label: `Ostatnia szansa! Tydzień ${period.weekNumber} zamyka się za` };
  }
  const daysToEnd = Math.max(0, Math.ceil((lb.event.endsAt.getTime() - lb.now.getTime()) / 86_400_000));

  const tabs: { key: RankingView; label: string }[] = [
    { key: 'q4', label: 'Cały Q4' },
    { key: 'week', label: 'Ten tydzień' },
    ...(prevPeriod ? [{ key: 'prev' as const, label: 'Poprzedni tydzień' }] : []),
  ];

  return (
    <>
      <Header />
      <main className={`mx-auto max-w-3xl px-4 pt-5 ${user ? 'pb-56' : 'pb-16'}`}>
        <section className="card glow overflow-hidden p-5 sm:p-7">
          <span className="eyebrow">Mentoring Ecommerce • Ranking Q4</span>
          <h1 className="mt-3 text-[28px] font-extrabold leading-[1.05] sm:text-4xl">
            <BrandTitle name={lb.event.name} />
          </h1>
          {lb.event.motivationText && <p className="mt-1.5 text-white/80">{lb.event.motivationText}</p>}
          <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
            {countdown ? (
              <Countdown target={countdown.target.toISOString()} label={countdown.label} />
            ) : (
              <p className="font-semibold text-accent">Q4 zakończony — dziękujemy za udział!</p>
            )}
            {lb.state.phase === 'running' && (
              <p className="text-xs text-muted">
                Do końca Q4: <span className="font-semibold text-white">{daysToEnd} dni</span>
              </p>
            )}
          </div>
          {period && lb.state.phase === 'running' && (
            <p className="mt-3 text-xs text-muted">
              Wpisuj wynik do {formatDateTime(period.entryDeadline)}. Edycja tygodnia zamyka się {formatDateTime(period.endsAt)}.
            </p>
          )}
          {!user && (
            <div className="mt-4 grid grid-cols-2 gap-2">
              <Link href="/rejestracja" className="btn-primary">Dołącz</Link>
              <Link href="/logowanie" className="btn-ghost">Zaloguj się</Link>
            </div>
          )}
        </section>

        {lb.preview && (
          <p className="alert-info mt-4">
            <b>Podgląd administratora.</b> Q4 jeszcze się nie zaczął, więc pokazujemy ranking tak, jakby trwał tydzień{' '}
            {lb.currentPeriod?.weekNumber}. Uczestnicy i goście widzą na razie ekran startowy.
          </p>
        )}

        {!canSee ? (
          <p className="alert-info mt-6">Ranking jest widoczny tylko dla zalogowanych uczestników.</p>
        ) : (
          <>
            <div className="mt-4">
              <StatTiles
                participants={lb.participantsCount}
                totalRevenue={lb.totalRevenue}
                topWeekly={topWeekly}
                week={period?.weekNumber ?? null}
                weeks={lb.periods.length}
              />
            </div>

            <nav aria-label="Rodzaj rankingu" className="sticky top-14 z-10 -mx-4 mt-6 bg-bg/90 px-4 py-2 backdrop-blur">
              <div className="grid auto-cols-fr grid-flow-col gap-1 rounded-full border border-line bg-card p-1">
                {tabs.map((t) => (
                  <Link
                    key={t.key}
                    href={t.key === 'q4' ? '/' : `/?view=${t.key}`}
                    scroll={false}
                    aria-current={view === t.key ? 'page' : undefined}
                    className={`flex min-h-[40px] items-center justify-center rounded-full px-2 text-center font-display text-sm font-bold leading-tight ${
                      view === t.key ? 'bg-gradient-to-br from-accent to-accent-2 text-accent-fg' : 'text-muted hover:text-white'
                    }`}
                  >
                    {t.label}
                  </Link>
                ))}
              </div>
            </nav>

            {shownPeriod && (
              <p className="mt-2 px-1 text-sm text-muted">
                Tydzień {shownPeriod.weekNumber}: {formatDate(shownPeriod.startsAt)}–{formatDate(shownPeriod.endsAt)} · ranking
                według przychodu wygenerowanego w tym tygodniu
              </p>
            )}

            {weekly && rows[0] && (
              <section className="card mt-4 border-gold/40 bg-gradient-to-r from-gold/15 to-transparent p-4" aria-label="Największy przyrost tygodnia">
                <div className="text-xs font-bold uppercase tracking-wider text-gold">🚀 Największy przyrost tygodnia</div>
                <div className="mt-2 flex items-center gap-3">
                  <Avatar src={rows[0].avatarUrl} size={52} className="ring-2 ring-gold" />
                  <div className="min-w-0">
                    <div className="truncate text-lg font-bold">{rows[0].nickname}</div>
                    <div className="text-xl font-extrabold tabular-nums text-gold">+{formatPln(rows[0].value)}</div>
                  </div>
                </div>
              </section>
            )}

            {rows.length === 0 ? (
              <div className="card mt-6 px-5 py-10 text-center">
                <div className="text-4xl" aria-hidden>🏁</div>
                <p className="mt-3 font-semibold">
                  {lb.state.phase === 'before'
                    ? `Ranking wystartuje ${lb.periods[0] ? formatDateTime(lb.periods[0].startsAt) : 'wkrótce'}. Zarejestruj się już teraz!`
                    : weekly
                      ? 'Nikt jeszcze nie zgłosił wyniku w tym tygodniu.'
                      : 'Ranking ruszy, gdy pierwsi uczestnicy dodadzą swoje wyniki.'}
                </p>
                {user?.status === 'active' && lb.state.phase === 'running' && (
                  <Link href="/konto" className="btn-primary mt-4">Dodaj swój wynik jako pierwszy</Link>
                )}
              </div>
            ) : (
              <>
                <div className="mt-6">
                  <Podium rows={rows.slice(0, 3)} weekly={weekly} />
                </div>
                <TopCards rows={rows.slice(3, 10)} weekly={weekly} />
                {rows.length > 10 && (
                  <section className="mt-6" aria-label="Miejsca 11–50">
                    <h2 className="mb-2 px-1 text-sm font-bold uppercase tracking-wider text-muted">Miejsca 11–{Math.min(LIST_END, all.length)}</h2>
                    <ol className="card divide-y divide-line overflow-hidden">
                      {rows.slice(10).map((r) => (
                        <RankRow key={`${r.rank}-${r.nickname}`} row={r} weekly={weekly} />
                      ))}
                    </ol>
                  </section>
                )}
                <FullRanking key={view} view={view} startOffset={LIST_END} total={all.length} />
              </>
            )}
          </>
        )}

        <footer className="mt-10 text-center text-xs text-muted">
          Ranking opiera się na wynikach deklarowanych przez uczestników. Publicznie widoczne są wyłącznie pseudonimy, awatary i wyniki.
        </footer>
      </main>
      {user && <MyPositionCard user={user} lb={lb} />}
    </>
  );
}
