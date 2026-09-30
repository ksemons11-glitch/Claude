import Link from 'next/link';
import { getCurrentUser } from '@/lib/auth';
import { avatarUrl, getEvent } from '@/lib/data';
import { logoutAction } from '@/app/actions/auth';
import { Avatar } from './Avatar';

export async function Header({ wide = false }: { wide?: boolean }) {
  const [user, event] = await Promise.all([getCurrentUser(), getEvent()]);
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-bg/85 backdrop-blur">
      <div className={`mx-auto flex h-14 ${wide ? 'max-w-5xl' : 'max-w-3xl'} items-center justify-between gap-3 px-4`}>
        <Link href="/" className="truncate text-base font-extrabold tracking-tight">
          <span className="text-accent">●</span> {event.name}
        </Link>
        {user ? (
          <details className="relative">
            <summary className="flex cursor-pointer list-none items-center gap-2 rounded-full p-1 hover:bg-white/5">
              <Avatar src={avatarUrl(user)} size={34} />
              <span className="sr-only">Menu profilu</span>
            </summary>
            <nav className="card absolute right-0 mt-2 w-56 overflow-hidden p-1 shadow-2xl">
              <div className="truncate px-3 py-2 text-sm text-muted">{user.publicNickname}</div>
              <Link href="/konto" className="block rounded-lg px-3 py-2.5 hover:bg-white/5">Mój wynik</Link>
              <Link href="/konto/profil" className="block rounded-lg px-3 py-2.5 hover:bg-white/5">Profil</Link>
              {user.role === 'admin' && (
                <Link href="/admin" className="block rounded-lg px-3 py-2.5 hover:bg-white/5">Panel administratora</Link>
              )}
              <form action={logoutAction}>
                <button type="submit" className="block w-full rounded-lg px-3 py-2.5 text-left text-red-300 hover:bg-white/5">
                  Wyloguj
                </button>
              </form>
            </nav>
          </details>
        ) : (
          <Link href="/logowanie" className="btn-sm shrink-0 whitespace-nowrap bg-accent text-accent-fg">Zaloguj się</Link>
        )}
      </div>
    </header>
  );
}
