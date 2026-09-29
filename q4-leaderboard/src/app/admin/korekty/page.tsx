import Link from 'next/link';
import { resolveCorrectionAction } from '@/app/actions/admin';
import { AdminEntryForm } from '@/components/admin/AdminEntryForm';
import { query } from '@/lib/db';
import { formatFull } from '@/lib/time';
import { formatPln } from '@/lib/validation';

export default async function CorrectionsPage() {
  const rows = await query<{
    id: number;
    userId: number;
    periodId: number;
    week: number;
    requested: number | string;
    message: string;
    createdAt: Date;
    nick: string;
    email: string;
    current: number | string | null;
  }>(
    `SELECT c.id, c.user_id AS userId, c.reporting_period_id AS periodId, p.week_number AS week, c.requested_value AS requested,
            c.message, c.created_at AS createdAt, u.public_nickname AS nick, u.email,
            (SELECT cumulative_revenue FROM revenue_entries e WHERE e.user_id = c.user_id AND e.reporting_period_id = c.reporting_period_id) AS current
     FROM correction_requests c
     JOIN users u ON u.id = c.user_id
     JOIN reporting_periods p ON p.id = c.reporting_period_id
     WHERE c.status = 'open' ORDER BY c.created_at`,
  );

  return (
    <div>
      <h1 className="text-2xl font-extrabold">Zgłoszenia korekt</h1>
      <p className="mt-1 text-sm text-muted">
        Uczestnik chciał wpisać niższą wartość niż wcześniej. Popraw wynik w odpowiednim tygodniu (np. zawyżony wpis z poprzedniego tygodnia) w
        karcie uczestnika albo zapisz zgłoszoną kwotę w bieżącym tygodniu poniżej.
      </p>
      {rows.length === 0 ? (
        <p className="card mt-4 px-4 py-8 text-center text-muted">Brak otwartych zgłoszeń.</p>
      ) : (
        <ul className="mt-4 grid gap-3">
          {rows.map((r) => (
            <li key={r.id} className="card space-y-3 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <Link href={`/admin/uzytkownicy/${r.userId}`} className="font-bold hover:text-accent">
                  {r.nick} <span className="font-normal text-muted">({r.email})</span>
                </Link>
                <span className="text-xs text-muted">{formatFull(r.createdAt)}</span>
              </div>
              <p className="text-sm">
                Tydzień {r.week}: prosi o <b>{formatPln(Number(r.requested))}</b> · obecny wpis w tym tygodniu:{' '}
                {r.current === null ? '—' : formatPln(Number(r.current))}
              </p>
              {r.message && <p className="rounded-lg bg-bg px-3 py-2 text-sm text-white/80">„{r.message}”</p>}
              <AdminEntryForm
                userId={r.userId}
                periodId={r.periodId}
                value={Number(r.requested)}
                correctionId={r.id}
                defaultReason="Korekta na prośbę uczestnika"
              />
              <form action={resolveCorrectionAction} className="flex gap-2">
                <input type="hidden" name="id" value={r.id} />
                <button name="status" value="resolved" className="btn-sm border border-line">Oznacz jako załatwione</button>
                <button name="status" value="dismissed" className="btn-sm border border-red-500/40 text-red-300">Odrzuć</button>
              </form>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
