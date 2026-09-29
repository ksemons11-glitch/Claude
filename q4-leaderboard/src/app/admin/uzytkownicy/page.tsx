import Link from 'next/link';
import { Avatar } from '@/components/Avatar';
import { query } from '@/lib/db';
import { avatarUrl, userColumns, type UserRow } from '@/lib/data';
import { loadLeaderboard } from '@/lib/leaderboard';
import { formatPln } from '@/lib/validation';

const STATUSES = [
  ['', 'Wszyscy'],
  ['active', 'Aktywni'],
  ['pending', 'Oczekujący'],
  ['suspended', 'Zablokowani'],
  ['rejected', 'Odrzuceni'],
  ['deletion', 'Prośby o usunięcie'],
  ['deleted', 'Usunięci'],
] as const;

const LABEL: Record<string, string> = {
  active: 'aktywny',
  pending: 'oczekuje',
  suspended: 'zablokowany',
  rejected: 'odrzucony',
  deleted: 'usunięty',
};

export default async function UsersPage({ searchParams }: { searchParams: Promise<{ q?: string; status?: string }> }) {
  const sp = await searchParams;
  const q = (sp.q ?? '').trim();
  const status = STATUSES.some(([k]) => k === sp.status) ? sp.status! : '';
  const where: string[] = [];
  const params: unknown[] = [];
  if (q) {
    where.push('(email LIKE ? OR discord_nickname LIKE ? OR public_nickname LIKE ?)');
    params.push(`%${q}%`, `%${q}%`, `%${q}%`);
  }
  if (status === 'deletion') where.push("deletion_requested_at IS NOT NULL AND status <> 'deleted'");
  else if (status) {
    where.push('status = ?');
    params.push(status);
  } else where.push("status <> 'deleted'");

  const users = await query<UserRow>(
    `SELECT ${userColumns()} FROM users ${where.length ? `WHERE ${where.join(' AND ')}` : ''} ORDER BY public_nickname LIMIT 500`,
    params,
  );
  const lb = await loadLeaderboard();
  const rankById = new Map(lb.rankings.q4.map((r) => [r.userId, r]));

  return (
    <div>
      <h1 className="text-2xl font-extrabold">Uczestnicy</h1>
      <form className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto_auto]" role="search">
        <input name="q" defaultValue={q} placeholder="Szukaj: e-mail, Discord, nick" className="input" />
        <select name="status" defaultValue={status} className="input sm:w-56">
          {STATUSES.map(([k, l]) => (
            <option key={k} value={k}>{l}</option>
          ))}
        </select>
        <button className="btn-ghost">Filtruj</button>
      </form>
      <p className="mt-3 text-sm text-muted">Wyników: {users.length}</p>
      <ul className="mt-2 grid gap-2">
        {users.map((u) => {
          const r = rankById.get(u.id);
          return (
            <li key={u.id}>
              <Link href={`/admin/uzytkownicy/${u.id}`} className="card flex items-center gap-3 p-3 hover:border-accent/40">
                <Avatar src={avatarUrl(u)} size={40} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-bold">
                    {u.publicNickname}
                    {u.role === 'admin' && <span className="ml-2 text-xs text-gold">ADMIN</span>}
                    {u.deletionRequestedAt && u.status !== 'deleted' && <span className="ml-2 text-xs text-red-300">prosi o usunięcie</span>}
                  </div>
                  <div className="truncate text-sm text-muted">
                    {u.email} · Discord: {u.discordNickname}
                  </div>
                </div>
                <div className="text-right text-sm">
                  <div className="font-semibold">{r ? `${r.rank}. · ${formatPln(r.cumulative)}` : '—'}</div>
                  <div className="text-muted">{LABEL[u.status]}</div>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
