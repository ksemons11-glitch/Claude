import Link from 'next/link';
import { notFound } from 'next/navigation';
import { anonymizeUserAction, setUserStatusAction } from '@/app/actions/admin';
import { Avatar } from '@/components/Avatar';
import { AdminEntryForm } from '@/components/admin/AdminEntryForm';
import { ConfirmButton } from '@/components/admin/ConfirmButton';
import { getCurrentUser } from '@/lib/auth';
import { query } from '@/lib/db';
import { avatarUrl, getEvent, getPeriods, userColumns, type UserRow } from '@/lib/data';
import { formatDate, formatFull } from '@/lib/time';
import { formatPln } from '@/lib/validation';

const val = (v: number | string | null) => (v === null ? '—' : formatPln(Number(v)));

export default async function UserDetail({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  const [user] = await query<UserRow>(`SELECT ${userColumns()} FROM users WHERE id = ?`, [id]);
  if (!user) notFound();
  const me = await getCurrentUser();
  const event = await getEvent();
  const periods = await getPeriods(event.id);
  const entries = await query<{ periodId: number; value: number | string }>(
    'SELECT reporting_period_id AS periodId, cumulative_revenue AS value FROM revenue_entries WHERE user_id = ?',
    [id],
  );
  const byPeriod = new Map(entries.map((e) => [e.periodId, Number(e.value)]));
  const audit = await query<{ week: number; oldValue: number | null; newValue: number | null; reason: string | null; at: Date; by: string }>(
    `SELECT p.week_number AS week, a.old_value AS oldValue, a.new_value AS newValue, a.change_reason AS reason, a.changed_at AS at,
            COALESCE(c.public_nickname, '?') AS \`by\`
     FROM revenue_entry_audit_log a
     JOIN reporting_periods p ON p.id = a.reporting_period_id
     LEFT JOIN users c ON c.id = a.changed_by_user_id
     WHERE a.user_id = ? ORDER BY a.changed_at DESC LIMIT 100`,
    [id],
  );

  const statusButton = (status: string, label: string, cls: string) =>
    user.status !== status && (
      <form action={setUserStatusAction}>
        <input type="hidden" name="id" value={user.id} />
        <input type="hidden" name="status" value={status} />
        <button className={`btn-sm ${cls}`}>{label}</button>
      </form>
    );

  return (
    <div className="space-y-6">
      <Link href="/admin/uzytkownicy" className="text-sm text-muted hover:text-white">← Uczestnicy</Link>
      <section className="card flex flex-wrap items-center gap-4 p-4">
        <Avatar src={avatarUrl(user)} size={64} />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-extrabold">{user.publicNickname}</h1>
          <p className="text-sm text-muted">{user.email}</p>
          <p className="text-sm text-muted">Discord: <span className="text-white">{user.discordNickname}</span></p>
          <p className="text-sm text-muted">Status: <b className="text-white">{user.status}</b> · rejestracja {formatFull(user.createdAt)}</p>
          {user.deletionRequestedAt && user.status !== 'deleted' && (
            <p className="mt-1 text-sm text-red-300">Prośba o usunięcie konta: {formatFull(user.deletionRequestedAt)}</p>
          )}
        </div>
        {me?.id !== user.id && user.status !== 'deleted' && (
          <div className="flex flex-wrap gap-2">
            {statusButton('active', user.status === 'suspended' ? 'Odblokuj' : 'Aktywuj', 'bg-accent text-bg')}
            {user.status === 'active' && statusButton('suspended', 'Zablokuj', 'border border-gold/50 text-gold')}
            {user.status === 'pending' && statusButton('rejected', 'Odrzuć', 'border border-red-500/40 text-red-300')}
          </div>
        )}
      </section>

      <section className="card p-4">
        <h2 className="text-lg font-bold">Wyniki (narastająco)</h2>
        <p className="mb-3 text-sm text-muted">Korekta wymaga podania powodu i trafia do dziennika zmian. Puste pole = usunięcie wpisu.</p>
        <ul className="divide-y divide-line">
          {periods.map((p) => (
            <li key={p.id} className="grid gap-2 py-3 sm:grid-cols-[180px_1fr] sm:items-center">
              <div>
                <div className="font-semibold">Tydzień {p.weekNumber}</div>
                <div className="text-xs text-muted">
                  {formatDate(p.startsAt)}–{formatDate(p.endsAt)} · teraz: {val(byPeriod.get(p.id) ?? null)}
                </div>
              </div>
              <AdminEntryForm userId={user.id} periodId={p.id} value={byPeriod.get(p.id) ?? null} />
            </li>
          ))}
        </ul>
      </section>

      <section className="card p-4">
        <h2 className="mb-3 text-lg font-bold">Historia zmian</h2>
        {audit.length === 0 ? (
          <p className="text-sm text-muted">Brak zmian.</p>
        ) : (
          <ul className="divide-y divide-line text-sm">
            {audit.map((a, i) => (
              <li key={i} className="py-2">
                <b>Tydz. {a.week}:</b> {val(a.oldValue)} → {val(a.newValue)}{' '}
                <span className="text-muted">
                  · {a.by} · {formatFull(a.at)}
                  {a.reason && <> · „{a.reason}”</>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {me?.id !== user.id && user.status !== 'deleted' && (
        <section className="card border-red-500/30 p-4">
          <h2 className="text-lg font-bold text-red-300">Usunięcie / anonimizacja konta</h2>
          <p className="mt-1 text-sm text-muted">
            Usuwa e-mail, nick Discord, awatar i wyniki z rankingu. Operacji nie można cofnąć. Wpisz <b>USUŃ</b>, aby potwierdzić.
          </p>
          <form action={anonymizeUserAction} className="mt-3 flex gap-2">
            <input type="hidden" name="id" value={user.id} />
            <input name="confirm" required pattern="USUŃ" placeholder="USUŃ" className="input min-h-[40px] max-w-[160px]" />
            <ConfirmButton message="Na pewno trwale zanonimizować to konto?" className="btn-sm min-h-[40px] bg-red-500 text-white">
              Usuń dane
            </ConfirmButton>
          </form>
        </section>
      )}
    </div>
  );
}
