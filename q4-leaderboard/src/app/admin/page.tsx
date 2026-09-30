import { approveUsersAction, setUserStatusAction } from '@/app/actions/admin';
import { Avatar } from '@/components/Avatar';
import { SelectAll } from '@/components/admin/SelectAll';
import { query } from '@/lib/db';
import { avatarUrl, userColumns, type UserRow } from '@/lib/data';
import { formatFull } from '@/lib/time';

export default async function PendingPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const q = ((await searchParams).q ?? '').trim();
  const like = `%${q}%`;
  const users = await query<UserRow>(
    `SELECT ${userColumns()} FROM users
     WHERE status = 'pending' ${q ? 'AND (email LIKE ? OR discord_nickname LIKE ? OR public_nickname LIKE ?)' : ''}
     ORDER BY created_at`,
    q ? [like, like, like] : [],
  );

  return (
    <div>
      <h1 className="text-2xl font-extrabold">Konta oczekujące na weryfikację</h1>
      <p className="mt-1 text-sm text-muted">Sprawdź nick z Discorda i zaakceptuj uczestników — pojedynczo lub zbiorczo.</p>

      <form className="mt-4 flex gap-2" role="search">
        <input name="q" defaultValue={q} placeholder="Szukaj: e-mail, Discord, nick" className="input" />
        <button className="btn-ghost">Szukaj</button>
      </form>

      {users.length === 0 ? (
        <p className="card mt-4 px-4 py-8 text-center text-muted">Brak kont oczekujących. 🎉</p>
      ) : (
        <>
          <form id="bulk" action={approveUsersAction} className="card mt-4 flex flex-wrap items-center justify-between gap-3 p-3">
            <SelectAll form="bulk" />
            <button className="btn-sm bg-accent text-accent-fg">Akceptuj zaznaczone</button>
          </form>
          <ul className="mt-3 grid gap-2">
            {users.map((u) => (
              <li key={u.id} className="card flex flex-wrap items-center gap-3 p-3">
                <input type="checkbox" name="ids" value={u.id} form="bulk" className="h-5 w-5 accent-accent" aria-label={`Zaznacz ${u.publicNickname}`} />
                <Avatar src={avatarUrl(u)} size={40} />
                <div className="min-w-0 flex-1">
                  <div className="font-bold">
                    Discord: <span className="text-accent-2">{u.discordNickname}</span>
                  </div>
                  <div className="truncate text-sm text-muted">
                    {u.publicNickname} · {u.email} · {formatFull(u.createdAt)}
                  </div>
                </div>
                <div className="flex gap-2">
                  <form action={approveUsersAction}>
                    <input type="hidden" name="ids" value={u.id} />
                    <button className="btn-sm bg-accent text-accent-fg">Akceptuj</button>
                  </form>
                  <form action={setUserStatusAction}>
                    <input type="hidden" name="id" value={u.id} />
                    <input type="hidden" name="status" value="rejected" />
                    <button className="btn-sm border border-red-500/40 text-red-300">Odrzuć</button>
                  </form>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
