import Link from 'next/link';
import { query } from '@/lib/db';
import { formatFull } from '@/lib/time';
import { formatPln } from '@/lib/validation';

const val = (v: number | string | null) => (v === null ? '—' : formatPln(Number(v)));

export default async function AuditPage() {
  const rows = await query<{
    id: number;
    userId: number;
    nick: string;
    week: number;
    oldValue: number | null;
    newValue: number | null;
    reason: string | null;
    at: Date;
    by: string;
    byAdmin: number;
  }>(
    `SELECT a.id, a.user_id AS userId, u.public_nickname AS nick, p.week_number AS week, a.old_value AS oldValue, a.new_value AS newValue,
            a.change_reason AS reason, a.changed_at AS at, COALESCE(c.public_nickname, '?') AS \`by\`, (c.role = 'admin') AS byAdmin
     FROM revenue_entry_audit_log a
     JOIN users u ON u.id = a.user_id
     JOIN reporting_periods p ON p.id = a.reporting_period_id
     LEFT JOIN users c ON c.id = a.changed_by_user_id
     ORDER BY a.changed_at DESC, a.id DESC LIMIT 300`,
  );
  return (
    <div>
      <h1 className="text-2xl font-extrabold">Dziennik zmian wyników</h1>
      <p className="mt-1 text-sm text-muted">Ostatnie 300 zmian. Korekty administratora są oznaczone na złoto.</p>
      <ul className="card mt-4 divide-y divide-line text-sm">
        {rows.length === 0 && <li className="px-4 py-8 text-center text-muted">Brak zmian.</li>}
        {rows.map((r) => (
          <li key={r.id} className={`px-4 py-2.5 ${Number(r.byAdmin) ? 'bg-gold/5' : ''}`}>
            <Link href={`/admin/uzytkownicy/${r.userId}`} className="font-bold hover:text-accent">{r.nick}</Link> · tydz. {r.week}:{' '}
            {val(r.oldValue)} → <b>{val(r.newValue)}</b>
            <span className="text-muted">
              {' '}· {formatFull(r.at)} · {Number(r.byAdmin) ? <span className="text-gold">admin {r.by}</span> : 'uczestnik'}
              {r.reason && <> · „{r.reason}”</>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
